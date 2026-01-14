"""
Recommendation Agent service.

Generates actionable buy/sell/hold recommendations based on analytics.
"""
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, MetricsCardsDaily, Signal, Recommendation, ActionType
from app.services.llm import get_llm_client

logger = structlog.get_logger()


class RecommendationAgent:
    """
    Agent responsible for generating trading recommendations.
    
    Analyzes signals and metrics to generate actionable recommendations
    with clear rationales.
    """
    
    # Default thresholds (can be overridden via settings)
    DEFAULT_MIN_ROI = 0.10  # 10% minimum ROI for buy recommendations
    DEFAULT_MIN_CONFIDENCE = 0.60
    DEFAULT_HORIZON_DAYS = 7
    DEFAULT_SPREAD_THRESHOLD = 20.0  # 20% spread triggers arbitrage
    DEFAULT_MOMENTUM_THRESHOLD = 0.05  # 5% MA ratio deviation
    
    def __init__(
        self,
        db: AsyncSession,
        min_roi: float | None = None,
        min_confidence: float | None = None,
        horizon_days: int | None = None,
    ):
        """
        Initialize the recommendation agent.
        
        Args:
            db: Database session.
            min_roi: Minimum ROI threshold.
            min_confidence: Minimum confidence threshold.
            horizon_days: Time horizon for recommendations.
        """
        self.db = db
        self.llm = get_llm_client()
        self.min_roi = min_roi or self.DEFAULT_MIN_ROI
        self.min_confidence = min_confidence or self.DEFAULT_MIN_CONFIDENCE
        self.horizon_days = horizon_days or self.DEFAULT_HORIZON_DAYS
    
    async def generate_recommendations(
        self,
        card_id: int,
        target_date: date | None = None,
    ) -> list[Recommendation]:
        """
        Generate recommendations for a specific card.
        
        Args:
            card_id: Card ID to generate recommendations for.
            target_date: Date to use for signals. Defaults to today.
            
        Returns:
            List of Recommendation objects.
        """
        target_date = target_date or date.today()
        recommendations = []
        
        # Get card info
        card = await self.db.get(Card, card_id)
        if not card:
            return recommendations
        
        # Get latest metrics
        metrics_query = select(MetricsCardsDaily).where(
            MetricsCardsDaily.card_id == card_id,
        ).order_by(MetricsCardsDaily.date.desc()).limit(1)
        result = await self.db.execute(metrics_query)
        metrics = result.scalar_one_or_none()
        
        if not metrics:
            return recommendations
        
        # Get recent signals
        signals_query = select(Signal).where(
            Signal.card_id == card_id,
            Signal.date >= target_date - timedelta(days=3),
        )
        result = await self.db.execute(signals_query)
        signals = result.scalars().all()
        
        # Deactivate old recommendations for this card
        await self._deactivate_old_recommendations(card_id)
        
        # Analyze and generate recommendations
        
        # 1. Check for arbitrage opportunity (high spread)
        spread_rec = await self._check_spread_opportunity(card, metrics, signals)
        if spread_rec:
            recommendations.append(spread_rec)
        
        # 2. Check for momentum-based opportunity
        momentum_rec = await self._check_momentum_opportunity(card, metrics, signals)
        if momentum_rec:
            recommendations.append(momentum_rec)
        
        # 3. Check for trend-based opportunity
        trend_rec = await self._check_trend_opportunity(card, metrics, signals)
        if trend_rec:
            recommendations.append(trend_rec)
        
        # 4. Check for volatility-based opportunity
        volatility_rec = await self._check_volatility_opportunity(card, metrics, signals)
        if volatility_rec:
            recommendations.append(volatility_rec)

        # 5. Check for arbitrage opportunity (cross-marketplace)
        arbitrage_rec = await self._check_arbitrage_opportunity(card, metrics, signals)
        if arbitrage_rec:
            recommendations.append(arbitrage_rec)

        # 6. Check for meta-based opportunity (tournament data)
        meta_rec = await self._check_meta_opportunity(card, metrics, signals)
        if meta_rec:
            recommendations.append(meta_rec)

        # 7. Check for supply-based opportunity (scarcity)
        supply_rec = await self._check_supply_opportunity(card, metrics, signals)
        if supply_rec:
            recommendations.append(supply_rec)

        # Filter by minimum confidence
        recommendations = [r for r in recommendations if r.confidence >= self.min_confidence]
        
        # Add to database
        for rec in recommendations:
            self.db.add(rec)
        
        await self.db.flush()
        return recommendations
    
    async def _deactivate_old_recommendations(self, card_id: int) -> None:
        """Deactivate expired recommendations for a card."""
        query = select(Recommendation).where(
            Recommendation.card_id == card_id,
            Recommendation.is_active == True,
            or_(
                Recommendation.valid_until < datetime.now(timezone.utc),
                Recommendation.valid_until == None,
            ),
        )
        result = await self.db.execute(query)
        old_recs = result.scalars().all()
        
        for rec in old_recs:
            rec.is_active = False
    
    async def _check_spread_opportunity(
        self,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
    ) -> Recommendation | None:
        """Check for arbitrage opportunity based on market spread."""
        if not metrics.spread_pct or float(metrics.spread_pct) < self.DEFAULT_SPREAD_THRESHOLD:
            return None
        
        spread_pct = float(metrics.spread_pct)
        
        # High spread = buy at lowest market, sell at highest
        if metrics.min_price and metrics.max_price:
            potential_profit = (float(metrics.max_price) - float(metrics.min_price)) / float(metrics.min_price)
            
            if potential_profit < self.min_roi:
                return None
            
            confidence = min(0.85, spread_pct / 50)
            
            # Generate rationale
            metrics_dict = {
                "current_price": float(metrics.avg_price) if metrics.avg_price else 0,
                "min_price": float(metrics.min_price),
                "max_price": float(metrics.max_price),
                "spread_pct": spread_pct,
                "momentum": "neutral",
                "total_listings": metrics.total_listings,
            }
            
            try:
                rationale = await self.llm.generate_recommendation_rationale(
                    card.name, "BUY", metrics_dict
                )
            except Exception:
                rationale = (
                    f"Significant price spread of {spread_pct:.1f}% detected across marketplaces. "
                    f"Buy at ${metrics.min_price:.2f} on the cheapest marketplace for potential "
                    f"{potential_profit*100:.1f}% profit margin."
                )
            
            # Cap potential_profit_pct to reasonable maximum (9999.99%) to prevent overflow
            profit_pct = potential_profit * 100
            capped_profit_pct = min(profit_pct, 9999.99) if profit_pct else None
            
            return Recommendation(
                card_id=card.id,
                action=ActionType.BUY.value,
                confidence=confidence,
                horizon_days=self.horizon_days,
                current_price=float(metrics.min_price),
                target_price=float(metrics.max_price),
                potential_profit_pct=capped_profit_pct,
                rationale=rationale,
                source_signals=json.dumps(["spread_high"]),
                valid_until=datetime.now(timezone.utc) + timedelta(days=self.horizon_days),
                is_active=True,
            )
        
        return None
    
    async def _check_momentum_opportunity(
        self,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
    ) -> Recommendation | None:
        """Check for momentum-based trading opportunity."""
        momentum_signals = [s for s in signals if s.signal_type.startswith("momentum_")]
        
        if not momentum_signals:
            return None
        
        latest_signal = max(momentum_signals, key=lambda s: s.date)
        
        if latest_signal.signal_type == "momentum_up":
            # Strong upward momentum = consider buying
            action = ActionType.BUY.value
            rationale_action = "BUY"
        elif latest_signal.signal_type == "momentum_down":
            # Strong downward momentum = consider selling
            action = ActionType.SELL.value
            rationale_action = "SELL"
        else:
            return None
        
        confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.6
        
        metrics_dict = {
            "current_price": float(metrics.avg_price) if metrics.avg_price else 0,
            "price_change_pct_7d": float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else 0,
            "price_change_pct_30d": float(metrics.price_change_pct_30d) if metrics.price_change_pct_30d else 0,
            "spread_pct": float(metrics.spread_pct) if metrics.spread_pct else 0,
            "volatility_7d": float(metrics.volatility_7d) if metrics.volatility_7d else 0,
            "momentum": "rising" if action == ActionType.BUY.value else "falling",
            "total_listings": metrics.total_listings,
        }
        
        try:
            rationale = await self.llm.generate_recommendation_rationale(
                card.name, rationale_action, metrics_dict
            )
        except Exception:
            if action == ActionType.BUY.value:
                rationale = (
                    "Strong upward momentum detected with 7-day MA above 30-day MA. "
                    "Price trend suggests continued growth in the short term."
                )
            else:
                rationale = (
                    "Downward momentum detected with 7-day MA below 30-day MA. "
                    "Consider selling to avoid further price decline."
                )
        
        return Recommendation(
            card_id=card.id,
            action=action,
            confidence=confidence,
            horizon_days=self.horizon_days,
            current_price=float(metrics.avg_price) if metrics.avg_price else None,
            rationale=rationale,
            source_signals=json.dumps([latest_signal.signal_type]),
            valid_until=datetime.now(timezone.utc) + timedelta(days=self.horizon_days),
            is_active=True,
        )
    
    async def _check_trend_opportunity(
        self,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
    ) -> Recommendation | None:
        """Check for trend-based opportunity."""
        trend_signals = [s for s in signals if s.signal_type.startswith("trend_")]
        
        if not trend_signals:
            return None
        
        latest_signal = max(trend_signals, key=lambda s: s.date)
        
        if latest_signal.signal_type == "trend_bullish":
            action = ActionType.BUY.value
        elif latest_signal.signal_type == "trend_bearish":
            action = ActionType.SELL.value
        else:
            return None
        
        confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.65
        
        metrics_dict = {
            "current_price": float(metrics.avg_price) if metrics.avg_price else 0,
            "price_change_pct_7d": float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else 0,
            "price_change_pct_30d": float(metrics.price_change_pct_30d) if metrics.price_change_pct_30d else 0,
            "spread_pct": float(metrics.spread_pct) if metrics.spread_pct else 0,
            "volatility_7d": float(metrics.volatility_7d) if metrics.volatility_7d else 0,
            "momentum": "bullish" if action == ActionType.BUY.value else "bearish",
            "total_listings": metrics.total_listings,
        }
        
        try:
            rationale = await self.llm.generate_recommendation_rationale(
                card.name, action, metrics_dict
            )
        except Exception:
            pct_7d = float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else 0
            pct_30d = float(metrics.price_change_pct_30d) if metrics.price_change_pct_30d else 0
            
            if action == ActionType.BUY.value:
                rationale = (
                    f"Bullish trend detected with {pct_7d:.1f}% gain over 7 days and "
                    f"{pct_30d:.1f}% over 30 days. Consider buying for continued upside."
                )
            else:
                rationale = (
                    f"Bearish trend detected with {pct_7d:.1f}% decline over 7 days and "
                    f"{pct_30d:.1f}% over 30 days. Consider selling to limit losses."
                )
        
        return Recommendation(
            card_id=card.id,
            action=action,
            confidence=confidence,
            horizon_days=self.horizon_days,
            current_price=float(metrics.avg_price) if metrics.avg_price else None,
            rationale=rationale,
            source_signals=json.dumps([latest_signal.signal_type]),
            valid_until=datetime.now(timezone.utc) + timedelta(days=self.horizon_days),
            is_active=True,
        )
    
    async def _check_volatility_opportunity(
        self,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
    ) -> Recommendation | None:
        """Check for volatility-based opportunity."""
        vol_signals = [s for s in signals if s.signal_type.startswith("volatility_")]
        
        if not vol_signals:
            return None
        
        latest_signal = max(vol_signals, key=lambda s: s.date)
        
        # High volatility = HOLD (too risky)
        # Low volatility with good trend = opportunity
        if latest_signal.signal_type == "volatility_high":
            action = ActionType.HOLD.value
            rationale = (
                f"High volatility detected ({float(latest_signal.value)*100:.1f}% daily). "
                f"Wait for price stabilization before entering a position."
            )
        elif latest_signal.signal_type == "volatility_low":
            # Low volatility might indicate accumulation
            return None  # Not actionable on its own
        else:
            return None
        
        confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.6

        return Recommendation(
            card_id=card.id,
            action=action,
            confidence=confidence,
            horizon_days=self.horizon_days,
            current_price=float(metrics.avg_price) if metrics.avg_price else None,
            rationale=rationale,
            source_signals=json.dumps([latest_signal.signal_type]),
            valid_until=datetime.now(timezone.utc) + timedelta(days=self.horizon_days),
            is_active=True,
        )

    async def _check_arbitrage_opportunity(
        self,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
    ) -> Recommendation | None:
        """Check for cross-marketplace arbitrage opportunity."""
        arb_signals = [s for s in signals if s.signal_type == "arbitrage"]

        if not arb_signals:
            return None

        latest_signal = max(arb_signals, key=lambda s: s.date)

        # Arbitrage signals indicate buy opportunity at lowest market
        confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.7
        spread_value = float(latest_signal.value) if latest_signal.value else 0

        if spread_value < self.min_roi:
            return None

        metrics_dict = {
            "current_price": float(metrics.avg_price) if metrics.avg_price else 0,
            "min_price": float(metrics.min_price) if metrics.min_price else 0,
            "max_price": float(metrics.max_price) if metrics.max_price else 0,
            "spread_pct": float(metrics.spread_pct) if metrics.spread_pct else 0,
            "arbitrage_potential": spread_value * 100,
            "momentum": "neutral",
            "total_listings": metrics.total_listings,
        }

        try:
            rationale = await self.llm.generate_recommendation_rationale(
                card.name, "BUY", metrics_dict
            )
        except Exception:
            rationale = (
                f"Cross-marketplace arbitrage opportunity detected with {spread_value*100:.1f}% "
                f"potential profit. Buy at lowest marketplace price of ${metrics.min_price:.2f} "
                f"and sell at highest for ${metrics.max_price:.2f}."
            )

        # Cap potential_profit_pct
        profit_pct = spread_value * 100
        capped_profit_pct = min(profit_pct, 9999.99) if profit_pct else None

        return Recommendation(
            card_id=card.id,
            action=ActionType.BUY.value,
            confidence=confidence,
            horizon_days=3,  # Shorter horizon for arbitrage
            current_price=float(metrics.min_price) if metrics.min_price else None,
            target_price=float(metrics.max_price) if metrics.max_price else None,
            potential_profit_pct=capped_profit_pct,
            rationale=rationale,
            source_signals=json.dumps(["arbitrage"]),
            valid_until=datetime.now(timezone.utc) + timedelta(days=3),
            is_active=True,
        )

    async def _check_meta_opportunity(
        self,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
    ) -> Recommendation | None:
        """Check for meta-based opportunity from tournament data."""
        meta_signals = [s for s in signals if s.signal_type in ("meta_spike", "meta_drop", "top8_spike")]

        if not meta_signals:
            return None

        latest_signal = max(meta_signals, key=lambda s: s.date)

        if latest_signal.signal_type in ("meta_spike", "top8_spike"):
            # Card is seeing increased tournament play = BUY
            action = ActionType.BUY.value
            meta_direction = "increasing"
        elif latest_signal.signal_type == "meta_drop":
            # Card is seeing decreased tournament play = SELL
            action = ActionType.SELL.value
            meta_direction = "decreasing"
        else:
            return None

        confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.7
        meta_change = float(latest_signal.value) if latest_signal.value else 0

        metrics_dict = {
            "current_price": float(metrics.avg_price) if metrics.avg_price else 0,
            "price_change_pct_7d": float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else 0,
            "meta_share_change": meta_change * 100,
            "meta_direction": meta_direction,
            "momentum": meta_direction,
            "total_listings": metrics.total_listings,
        }

        try:
            rationale = await self.llm.generate_recommendation_rationale(
                card.name, action, metrics_dict
            )
        except Exception:
            if action == ActionType.BUY.value:
                rationale = (
                    f"Tournament meta share {meta_direction} by {meta_change*100:.1f}%. "
                    f"Increased competitive play typically precedes price appreciation. "
                    f"Consider buying before the market adjusts."
                )
            else:
                rationale = (
                    f"Tournament meta share {meta_direction} by {abs(meta_change)*100:.1f}%. "
                    f"Decreased competitive play often signals price decline. "
                    f"Consider selling to avoid losses."
                )

        return Recommendation(
            card_id=card.id,
            action=action,
            confidence=confidence,
            horizon_days=14,  # Longer horizon for meta trends
            current_price=float(metrics.avg_price) if metrics.avg_price else None,
            rationale=rationale,
            source_signals=json.dumps([latest_signal.signal_type]),
            valid_until=datetime.now(timezone.utc) + timedelta(days=14),
            is_active=True,
        )

    async def _check_supply_opportunity(
        self,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
    ) -> Recommendation | None:
        """Check for supply-based opportunity (scarcity signals)."""
        supply_signals = [s for s in signals if s.signal_type in ("supply_low", "supply_velocity")]

        if not supply_signals:
            return None

        latest_signal = max(supply_signals, key=lambda s: s.date)

        # Low supply or high sell velocity = potential price increase
        confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.65
        supply_value = float(latest_signal.value) if latest_signal.value else 0

        # Low supply is a buy signal (scarcity drives prices up)
        if latest_signal.signal_type == "supply_low":
            action = ActionType.BUY.value
            supply_note = f"Low supply detected with only {metrics.total_listings} listings"
        elif latest_signal.signal_type == "supply_velocity" and supply_value > 0:
            # High velocity (listings selling fast) = buy before shortage
            action = ActionType.BUY.value
            supply_note = f"High sales velocity of {supply_value*100:.1f}% inventory turnover"
        else:
            return None

        metrics_dict = {
            "current_price": float(metrics.avg_price) if metrics.avg_price else 0,
            "total_listings": metrics.total_listings,
            "supply_indicator": supply_value,
            "supply_note": supply_note,
            "momentum": "scarcity",
        }

        try:
            rationale = await self.llm.generate_recommendation_rationale(
                card.name, action, metrics_dict
            )
        except Exception:
            rationale = (
                f"{supply_note}. Scarcity typically drives price appreciation. "
                f"Current price ${metrics.avg_price:.2f} may increase as supply diminishes."
            )

        return Recommendation(
            card_id=card.id,
            action=action,
            confidence=confidence,
            horizon_days=self.horizon_days,
            current_price=float(metrics.avg_price) if metrics.avg_price else None,
            rationale=rationale,
            source_signals=json.dumps([latest_signal.signal_type]),
            valid_until=datetime.now(timezone.utc) + timedelta(days=self.horizon_days),
            is_active=True,
        )

    async def run_recommendations(
        self,
        card_ids: list[int] | None = None,
        target_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Run recommendation generation for multiple cards.
        
        Args:
            card_ids: List of card IDs to process. None = cards with recent signals.
            target_date: Date to use. Defaults to today.
            
        Returns:
            Summary of results.
        """
        target_date = target_date or date.today()
        
        # Get cards to process
        if card_ids:
            cards_query = select(Card).where(Card.id.in_(card_ids))
        else:
            # Get cards with recent signals
            recent_cards_query = select(Signal.card_id).where(
                Signal.date >= target_date - timedelta(days=3),
            ).distinct()
            result = await self.db.execute(recent_cards_query)
            card_ids = [row[0] for row in result.all()]
            
            cards_query = select(Card).where(Card.id.in_(card_ids)) if card_ids else select(Card).limit(0)
        
        result = await self.db.execute(cards_query)
        cards = result.scalars().all()
        
        total_recommendations = 0
        buy_count = 0
        sell_count = 0
        hold_count = 0
        errors = 0
        
        for card in cards:
            try:
                recs = await self.generate_recommendations(card.id, target_date)
                total_recommendations += len(recs)
                
                for rec in recs:
                    if rec.action == ActionType.BUY.value:
                        buy_count += 1
                    elif rec.action == ActionType.SELL.value:
                        sell_count += 1
                    else:
                        hold_count += 1
            except Exception as e:
                logger.error("Failed to generate recommendations", card_id=card.id, error=str(e))
                errors += 1
        
        await self.db.commit()
        
        return {
            "date": str(target_date),
            "cards_processed": len(cards),
            "total_recommendations": total_recommendations,
            "buy_recommendations": buy_count,
            "sell_recommendations": sell_count,
            "hold_recommendations": hold_count,
            "errors": errors,
        }

