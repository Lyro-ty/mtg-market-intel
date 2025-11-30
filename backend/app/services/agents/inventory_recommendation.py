"""
Aggressive Inventory Recommendation Agent service.

Generates more aggressive buy/sell/hold recommendations for inventory items.
Uses lower thresholds and shorter time horizons than the standard market recommendations.
"""
import json
from datetime import date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Card, Marketplace, MetricsCardsDaily, Signal, 
    InventoryItem, InventoryRecommendation, ActionType
)
from app.services.llm import get_llm_client

logger = structlog.get_logger()


class InventoryRecommendationAgent:
    """
    Agent responsible for generating aggressive trading recommendations for inventory.
    
    Key differences from standard RecommendationAgent:
    - Lower ROI thresholds (5% vs 10%)
    - Lower confidence requirements (40% vs 60%)
    - Shorter time horizons (3 days vs 7 days)
    - More sensitive to price spreads (10% vs 20%)
    - Urgency levels for prioritization
    - Considers acquisition price for ROI calculations
    """
    
    # Aggressive thresholds (significantly lower than standard)
    MIN_ROI = 0.05  # 5% minimum ROI (vs 10% standard)
    MIN_CONFIDENCE = 0.40  # 40% confidence (vs 60% standard)
    DEFAULT_HORIZON_DAYS = 3  # 3 days (vs 7 days standard)
    SPREAD_THRESHOLD = 10.0  # 10% spread triggers arbitrage (vs 20% standard)
    MOMENTUM_THRESHOLD = 0.03  # 3% MA deviation (vs 5% standard)
    
    # Urgency thresholds
    CRITICAL_PROFIT_THRESHOLD = 30.0  # 30%+ profit opportunity = CRITICAL
    HIGH_PROFIT_THRESHOLD = 15.0  # 15%+ profit opportunity = HIGH
    CRITICAL_LOSS_THRESHOLD = -15.0  # 15%+ loss = CRITICAL sell
    HIGH_LOSS_THRESHOLD = -8.0  # 8%+ loss = HIGH sell
    
    def __init__(
        self,
        db: AsyncSession,
        min_roi: float | None = None,
        min_confidence: float | None = None,
        horizon_days: int | None = None,
    ):
        """
        Initialize the inventory recommendation agent.
        
        Args:
            db: Database session.
            min_roi: Minimum ROI threshold.
            min_confidence: Minimum confidence threshold.
            horizon_days: Time horizon for recommendations.
        """
        self.db = db
        self.llm = get_llm_client()
        self.min_roi = min_roi or self.MIN_ROI
        self.min_confidence = min_confidence or self.MIN_CONFIDENCE
        self.horizon_days = horizon_days or self.DEFAULT_HORIZON_DAYS
    
    def _determine_urgency(
        self, 
        action: str, 
        profit_pct: float | None, 
        confidence: float,
        spread_pct: float | None = None,
    ) -> str:
        """Determine urgency level based on potential profit/loss and confidence."""
        if action == ActionType.SELL.value:
            # For sells, higher losses = higher urgency
            if profit_pct is not None:
                if profit_pct <= self.CRITICAL_LOSS_THRESHOLD:
                    return "CRITICAL"
                elif profit_pct <= self.HIGH_LOSS_THRESHOLD:
                    return "HIGH"
                elif profit_pct >= self.CRITICAL_PROFIT_THRESHOLD:
                    return "CRITICAL"  # Great profit opportunity
                elif profit_pct >= self.HIGH_PROFIT_THRESHOLD:
                    return "HIGH"
            
            # High spread = urgent sell opportunity
            if spread_pct and spread_pct >= 25:
                return "HIGH"
        
        elif action == ActionType.HOLD.value:
            # For holds, high volatility or uncertainty = lower urgency
            if confidence < 0.5:
                return "LOW"
        
        # Check confidence for urgency boost
        if confidence >= 0.85:
            return "HIGH" if profit_pct and abs(profit_pct) >= 10 else "NORMAL"
        
        return "NORMAL"
    
    async def generate_recommendations(
        self,
        inventory_item_id: int,
        target_date: date | None = None,
    ) -> list[InventoryRecommendation]:
        """
        Generate aggressive recommendations for a specific inventory item.
        
        Args:
            inventory_item_id: Inventory item ID to generate recommendations for.
            target_date: Date to use for signals. Defaults to today.
            
        Returns:
            List of InventoryRecommendation objects.
        """
        target_date = target_date or date.today()
        recommendations = []
        
        # Get inventory item with card info
        inv_item = await self.db.get(InventoryItem, inventory_item_id)
        if not inv_item:
            return recommendations
        
        card = await self.db.get(Card, inv_item.card_id)
        if not card:
            return recommendations
        
        # Get latest metrics
        metrics_query = select(MetricsCardsDaily).where(
            MetricsCardsDaily.card_id == card.id,
        ).order_by(MetricsCardsDaily.date.desc()).limit(1)
        result = await self.db.execute(metrics_query)
        metrics = result.scalar_one_or_none()
        
        if not metrics:
            return recommendations
        
        # Get recent signals
        signals_query = select(Signal).where(
            Signal.card_id == card.id,
            Signal.date >= target_date - timedelta(days=3),
        )
        result = await self.db.execute(signals_query)
        signals = result.scalars().all()
        
        # Deactivate old recommendations for this item
        await self._deactivate_old_recommendations(inventory_item_id)
        
        # Calculate ROI from acquisition
        acquisition_price = float(inv_item.acquisition_price) if inv_item.acquisition_price else None
        current_value = float(metrics.avg_price) if metrics.avg_price else None
        roi_from_acquisition = None
        
        if acquisition_price and current_value and acquisition_price > 0:
            roi_from_acquisition = ((current_value - acquisition_price) / acquisition_price) * 100
        
        # Generate recommendations with aggressive thresholds
        
        # 1. Check for immediate sell opportunity (high profit from acquisition)
        profit_rec = await self._check_profit_opportunity(
            inv_item, card, metrics, signals, roi_from_acquisition
        )
        if profit_rec:
            recommendations.append(profit_rec)
        
        # 2. Check for spread arbitrage (aggressive threshold)
        spread_rec = await self._check_spread_opportunity(
            inv_item, card, metrics, signals, roi_from_acquisition
        )
        if spread_rec:
            recommendations.append(spread_rec)
        
        # 3. Check momentum signals (more sensitive)
        momentum_rec = await self._check_momentum_opportunity(
            inv_item, card, metrics, signals, roi_from_acquisition
        )
        if momentum_rec:
            recommendations.append(momentum_rec)
        
        # 4. Check for loss prevention (sell before further decline)
        loss_rec = await self._check_loss_prevention(
            inv_item, card, metrics, signals, roi_from_acquisition
        )
        if loss_rec:
            recommendations.append(loss_rec)
        
        # 5. Check trend signals
        trend_rec = await self._check_trend_opportunity(
            inv_item, card, metrics, signals, roi_from_acquisition
        )
        if trend_rec:
            recommendations.append(trend_rec)
        
        # Filter by minimum confidence
        recommendations = [r for r in recommendations if r.confidence >= self.min_confidence]
        
        # Add to database
        for rec in recommendations:
            self.db.add(rec)
        
        await self.db.flush()
        return recommendations
    
    async def _deactivate_old_recommendations(self, inventory_item_id: int) -> None:
        """Deactivate expired recommendations for an inventory item."""
        query = select(InventoryRecommendation).where(
            InventoryRecommendation.inventory_item_id == inventory_item_id,
            InventoryRecommendation.is_active == True,
            or_(
                InventoryRecommendation.valid_until < datetime.utcnow(),
                InventoryRecommendation.valid_until == None,
            ),
        )
        result = await self.db.execute(query)
        old_recs = result.scalars().all()
        
        for rec in old_recs:
            rec.is_active = False
    
    async def _check_profit_opportunity(
        self,
        inv_item: InventoryItem,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
        roi_from_acquisition: float | None,
    ) -> InventoryRecommendation | None:
        """Check for immediate profit-taking opportunity."""
        if roi_from_acquisition is None or roi_from_acquisition < self.HIGH_PROFIT_THRESHOLD:
            return None
        
        # Good profit opportunity - recommend sell
        confidence = min(0.90, 0.60 + (roi_from_acquisition / 100))
        urgency = self._determine_urgency(
            ActionType.SELL.value, 
            roi_from_acquisition, 
            confidence,
            float(metrics.spread_pct) if metrics.spread_pct else None
        )
        
        current_price = float(metrics.avg_price) if metrics.avg_price else None
        acquisition_price = float(inv_item.acquisition_price) if inv_item.acquisition_price else None
        
        rationale = (
            f"Excellent profit opportunity: {roi_from_acquisition:.1f}% gain since acquisition. "
            f"Current market price ${current_price:.2f} vs acquisition ${acquisition_price:.2f}. "
            f"Consider selling to lock in profits."
        )
        
        return InventoryRecommendation(
            inventory_item_id=inv_item.id,
            card_id=card.id,
            action=ActionType.SELL.value,
            urgency=urgency,
            confidence=confidence,
            horizon_days=self.horizon_days,
            current_price=current_price,
            target_price=current_price,  # Sell at current price
            potential_profit_pct=roi_from_acquisition,
            roi_from_acquisition=roi_from_acquisition,
            rationale=rationale,
            suggested_listing_price=current_price * 0.98 if current_price else None,  # Slight discount for quick sale
            valid_until=datetime.utcnow() + timedelta(days=self.horizon_days),
            is_active=True,
        )
    
    async def _check_spread_opportunity(
        self,
        inv_item: InventoryItem,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
        roi_from_acquisition: float | None,
    ) -> InventoryRecommendation | None:
        """Check for arbitrage opportunity based on market spread (aggressive threshold)."""
        if not metrics.spread_pct or float(metrics.spread_pct) < self.SPREAD_THRESHOLD:
            return None
        
        spread_pct = float(metrics.spread_pct)
        
        if metrics.min_price and metrics.max_price:
            potential_profit = (float(metrics.max_price) - float(metrics.min_price)) / float(metrics.min_price)
            
            if potential_profit * 100 < self.min_roi * 100:
                return None
            
            confidence = min(0.85, spread_pct / 40)  # More aggressive confidence scaling
            urgency = self._determine_urgency(
                ActionType.SELL.value,
                potential_profit * 100,
                confidence,
                spread_pct
            )
            
            rationale = (
                f"Price spread of {spread_pct:.1f}% detected across marketplaces. "
                f"Sell at highest market (${float(metrics.max_price):.2f}) for "
                f"{potential_profit*100:.1f}% arbitrage profit."
            )
            
            return InventoryRecommendation(
                inventory_item_id=inv_item.id,
                card_id=card.id,
                action=ActionType.SELL.value,
                urgency=urgency,
                confidence=confidence,
                horizon_days=self.horizon_days,
                current_price=float(metrics.avg_price) if metrics.avg_price else None,
                target_price=float(metrics.max_price),
                potential_profit_pct=potential_profit * 100,
                roi_from_acquisition=roi_from_acquisition,
                rationale=rationale,
                suggested_listing_price=float(metrics.max_price) * 0.95,
                valid_until=datetime.utcnow() + timedelta(days=self.horizon_days),
                is_active=True,
            )
        
        return None
    
    async def _check_momentum_opportunity(
        self,
        inv_item: InventoryItem,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
        roi_from_acquisition: float | None,
    ) -> InventoryRecommendation | None:
        """Check for momentum-based opportunity (aggressive sensitivity)."""
        momentum_signals = [s for s in signals if s.signal_type.startswith("momentum_")]
        
        if not momentum_signals:
            return None
        
        latest_signal = max(momentum_signals, key=lambda s: s.date)
        
        if latest_signal.signal_type == "momentum_down":
            # Downward momentum = SELL to avoid losses
            action = ActionType.SELL.value
            
            confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.55
            current_price = float(metrics.avg_price) if metrics.avg_price else None
            pct_7d = float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else 0
            
            # Boost confidence if we're already at a loss
            if roi_from_acquisition and roi_from_acquisition < 0:
                confidence = min(0.85, confidence + 0.15)
            
            urgency = self._determine_urgency(action, pct_7d, confidence)
            
            rationale = (
                f"Downward momentum detected with {pct_7d:.1f}% decline over 7 days. "
                f"Recommend selling to prevent further losses."
            )
            
            return InventoryRecommendation(
                inventory_item_id=inv_item.id,
                card_id=card.id,
                action=action,
                urgency=urgency,
                confidence=confidence,
                horizon_days=self.horizon_days,
                current_price=current_price,
                roi_from_acquisition=roi_from_acquisition,
                rationale=rationale,
                suggested_listing_price=current_price * 0.95 if current_price else None,
                valid_until=datetime.utcnow() + timedelta(days=self.horizon_days),
                is_active=True,
            )
        
        elif latest_signal.signal_type == "momentum_up" and roi_from_acquisition and roi_from_acquisition > 10:
            # Upward momentum + good profit = consider selling at peak
            action = ActionType.SELL.value
            confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.60
            
            current_price = float(metrics.avg_price) if metrics.avg_price else None
            target_price = current_price * 1.05 if current_price else None  # 5% above current
            
            urgency = self._determine_urgency(action, roi_from_acquisition, confidence)
            
            rationale = (
                f"Upward momentum detected. You're up {roi_from_acquisition:.1f}% from acquisition. "
                f"Consider selling near the peak to lock in profits."
            )
            
            return InventoryRecommendation(
                inventory_item_id=inv_item.id,
                card_id=card.id,
                action=action,
                urgency=urgency,
                confidence=confidence,
                horizon_days=self.horizon_days,
                current_price=current_price,
                target_price=target_price,
                potential_profit_pct=roi_from_acquisition,
                roi_from_acquisition=roi_from_acquisition,
                rationale=rationale,
                suggested_listing_price=current_price * 1.02 if current_price else None,
                valid_until=datetime.utcnow() + timedelta(days=self.horizon_days),
                is_active=True,
            )
        
        return None
    
    async def _check_loss_prevention(
        self,
        inv_item: InventoryItem,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
        roi_from_acquisition: float | None,
    ) -> InventoryRecommendation | None:
        """Check for loss prevention opportunity - sell before further decline."""
        if roi_from_acquisition is None or roi_from_acquisition > self.HIGH_LOSS_THRESHOLD:
            return None
        
        # We're at a loss - check if trend suggests further decline
        pct_7d = float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else 0
        pct_30d = float(metrics.price_change_pct_30d) if metrics.price_change_pct_30d else 0
        
        # Both short and long term declining = urgent sell
        if pct_7d < -3 and pct_30d < -5:
            confidence = 0.75
            urgency = self._determine_urgency(ActionType.SELL.value, roi_from_acquisition, confidence)
            
            current_price = float(metrics.avg_price) if metrics.avg_price else None
            acquisition_price = float(inv_item.acquisition_price) if inv_item.acquisition_price else None
            
            rationale = (
                f"Loss prevention alert: {roi_from_acquisition:.1f}% loss from acquisition price "
                f"(${acquisition_price:.2f} → ${current_price:.2f}). "
                f"Price continues declining ({pct_7d:.1f}% this week, {pct_30d:.1f}% this month). "
                f"Recommend selling to prevent further losses."
            )
            
            return InventoryRecommendation(
                inventory_item_id=inv_item.id,
                card_id=card.id,
                action=ActionType.SELL.value,
                urgency=urgency,
                confidence=confidence,
                horizon_days=self.horizon_days,
                current_price=current_price,
                potential_profit_pct=roi_from_acquisition,
                roi_from_acquisition=roi_from_acquisition,
                rationale=rationale,
                suggested_listing_price=current_price * 0.92 if current_price else None,  # Aggressive pricing to sell quickly
                valid_until=datetime.utcnow() + timedelta(days=self.horizon_days),
                is_active=True,
            )
        
        # Holding steady but at loss - HOLD and wait for recovery
        elif abs(pct_7d) < 3:
            confidence = 0.60
            urgency = "NORMAL"
            
            current_price = float(metrics.avg_price) if metrics.avg_price else None
            
            rationale = (
                f"Currently at {roi_from_acquisition:.1f}% loss, but price has stabilized "
                f"({pct_7d:.1f}% change this week). Consider holding for potential recovery."
            )
            
            return InventoryRecommendation(
                inventory_item_id=inv_item.id,
                card_id=card.id,
                action=ActionType.HOLD.value,
                urgency=urgency,
                confidence=confidence,
                horizon_days=self.horizon_days * 2,  # Longer horizon for recovery
                current_price=current_price,
                roi_from_acquisition=roi_from_acquisition,
                rationale=rationale,
                valid_until=datetime.utcnow() + timedelta(days=self.horizon_days * 2),
                is_active=True,
            )
        
        return None
    
    async def _check_trend_opportunity(
        self,
        inv_item: InventoryItem,
        card: Card,
        metrics: MetricsCardsDaily,
        signals: list[Signal],
        roi_from_acquisition: float | None,
    ) -> InventoryRecommendation | None:
        """Check for trend-based opportunity."""
        trend_signals = [s for s in signals if s.signal_type.startswith("trend_")]
        
        if not trend_signals:
            return None
        
        latest_signal = max(trend_signals, key=lambda s: s.date)
        
        if latest_signal.signal_type == "trend_bearish":
            action = ActionType.SELL.value
            confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.60
            
            # Boost confidence if already at profit
            if roi_from_acquisition and roi_from_acquisition > 5:
                confidence = min(0.85, confidence + 0.10)
            
            pct_7d = float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else 0
            pct_30d = float(metrics.price_change_pct_30d) if metrics.price_change_pct_30d else 0
            current_price = float(metrics.avg_price) if metrics.avg_price else None
            
            urgency = self._determine_urgency(action, pct_7d, confidence)
            
            rationale = (
                f"Bearish trend detected: {pct_7d:.1f}% (7d) and {pct_30d:.1f}% (30d) decline. "
                f"Recommend selling before further price erosion."
            )
            
            return InventoryRecommendation(
                inventory_item_id=inv_item.id,
                card_id=card.id,
                action=action,
                urgency=urgency,
                confidence=confidence,
                horizon_days=self.horizon_days,
                current_price=current_price,
                roi_from_acquisition=roi_from_acquisition,
                rationale=rationale,
                suggested_listing_price=current_price * 0.97 if current_price else None,
                valid_until=datetime.utcnow() + timedelta(days=self.horizon_days),
                is_active=True,
            )
        
        elif latest_signal.signal_type == "trend_bullish":
            # Bullish trend - hold if at loss, consider selling if at good profit
            if roi_from_acquisition and roi_from_acquisition > 20:
                action = ActionType.SELL.value
                confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.65
                urgency = "NORMAL"
                
                current_price = float(metrics.avg_price) if metrics.avg_price else None
                
                rationale = (
                    f"Bullish trend continues but you're up {roi_from_acquisition:.1f}%. "
                    f"Consider selling to realize profits while trend is favorable."
                )
            else:
                action = ActionType.HOLD.value
                confidence = float(latest_signal.confidence) if latest_signal.confidence else 0.65
                urgency = "LOW"
                
                current_price = float(metrics.avg_price) if metrics.avg_price else None
                
                rationale = (
                    f"Bullish trend detected. Hold position for potential further gains."
                )
            
            return InventoryRecommendation(
                inventory_item_id=inv_item.id,
                card_id=card.id,
                action=action,
                urgency=urgency,
                confidence=confidence,
                horizon_days=self.horizon_days,
                current_price=current_price,
                roi_from_acquisition=roi_from_acquisition,
                rationale=rationale,
                valid_until=datetime.utcnow() + timedelta(days=self.horizon_days),
                is_active=True,
            )
        
        return None
    
    async def run_inventory_recommendations(
        self,
        inventory_item_ids: list[int] | None = None,
        target_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Run recommendation generation for inventory items.
        
        Args:
            inventory_item_ids: List of inventory item IDs to process. None = all items.
            target_date: Date to use. Defaults to today.
            
        Returns:
            Summary of results.
        """
        target_date = target_date or date.today()
        
        # Get items to process
        if inventory_item_ids:
            items_query = select(InventoryItem).where(InventoryItem.id.in_(inventory_item_ids))
        else:
            items_query = select(InventoryItem)
        
        result = await self.db.execute(items_query)
        items = result.scalars().all()
        
        total_recommendations = 0
        sell_count = 0
        hold_count = 0
        critical_count = 0
        high_count = 0
        errors = 0
        
        for item in items:
            try:
                recs = await self.generate_recommendations(item.id, target_date)
                total_recommendations += len(recs)
                
                for rec in recs:
                    if rec.action == ActionType.SELL.value:
                        sell_count += 1
                    else:
                        hold_count += 1
                    
                    if rec.urgency == "CRITICAL":
                        critical_count += 1
                    elif rec.urgency == "HIGH":
                        high_count += 1
                        
            except Exception as e:
                logger.error("Failed to generate inventory recommendations", 
                           item_id=item.id, error=str(e))
                errors += 1
        
        await self.db.commit()
        
        return {
            "date": str(target_date),
            "items_processed": len(items),
            "total_recommendations": total_recommendations,
            "sell_recommendations": sell_count,
            "hold_recommendations": hold_count,
            "critical_alerts": critical_count,
            "high_priority": high_count,
            "errors": errors,
        }
