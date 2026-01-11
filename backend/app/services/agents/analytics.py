"""
Analytics Agent service.

Computes market metrics, detects trends, and generates AI-powered insights.
"""
import json
from datetime import date, timedelta
from typing import Any

import numpy as np
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, MetricsCardsDaily, PriceSnapshot, Signal
from app.services.llm import get_llm_client

logger = structlog.get_logger()


class AnalyticsAgent:
    """
    Agent responsible for computing analytics and generating insights.
    
    Processes price data to compute:
    - Moving averages (7-day, 30-day)
    - Volatility metrics
    - Momentum indicators
    - Price change percentages
    - Market spread analysis
    
    Uses LLM to generate human-readable insights.
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize the analytics agent.
        
        Args:
            db: Database session for queries and updates.
        """
        self.db = db
        self.llm = get_llm_client()
    
    async def compute_daily_metrics(
        self,
        card_id: int,
        target_date: date | None = None,
    ) -> MetricsCardsDaily | None:
        """
        Compute daily aggregated metrics for a card.
        
        Args:
            card_id: Card ID to compute metrics for.
            target_date: Date to compute metrics for. Defaults to today.
            
        Returns:
            MetricsCardsDaily object or None if no data.
        """
        target_date = target_date or date.today()
        
        # Get price snapshots for the target date (USD only)
        # Use a 2-day window to handle cases where data might be slightly off
        # This makes metrics computation more robust with sparse data
        snapshots_query = select(PriceSnapshot).where(
            PriceSnapshot.card_id == card_id,
            func.date(PriceSnapshot.time) >= target_date - timedelta(days=1),
            func.date(PriceSnapshot.time) <= target_date,
            PriceSnapshot.currency == "USD",  # USD-only mode
        )
        result = await self.db.execute(snapshots_query)
        snapshots = result.scalars().all()
        
        if not snapshots:
            return None
        
        # Compute basic price metrics
        prices = [float(s.price) for s in snapshots]
        
        avg_price = np.mean(prices)
        min_price = min(prices)
        max_price = max(prices)
        median_price = np.median(prices)
        
        spread = max_price - min_price
        spread_pct = (spread / avg_price * 100) if avg_price > 0 else 0
        
        # Get unique marketplaces
        marketplace_ids = set(s.marketplace_id for s in snapshots)
        
        # Compute price changes
        price_change_1d = await self._compute_price_change(card_id, target_date, 1)
        price_change_7d = await self._compute_price_change(card_id, target_date, 7)
        price_change_30d = await self._compute_price_change(card_id, target_date, 30)
        
        # Log if price changes couldn't be computed (helps diagnose top movers issues)
        if price_change_1d is None or price_change_7d is None:
            logger.debug(
                "Price change computation",
                card_id=card_id,
                date=target_date,
                has_1d_change=price_change_1d is not None,
                has_7d_change=price_change_7d is not None,
            )
        
        # Compute moving averages
        ma_7d = await self._compute_moving_average(card_id, target_date, 7)
        ma_30d = await self._compute_moving_average(card_id, target_date, 30)
        
        # Compute volatility
        volatility_7d = await self._compute_volatility(card_id, target_date, 7)
        volatility_30d = await self._compute_volatility(card_id, target_date, 30)
        
        # Check if metrics already exist for this card/date
        existing_query = select(MetricsCardsDaily).where(
            MetricsCardsDaily.card_id == card_id,
            MetricsCardsDaily.date == target_date,
        )
        result = await self.db.execute(existing_query)
        metrics = result.scalar_one_or_none()
        
        if metrics:
            # Update existing
            metrics.avg_price = avg_price
            metrics.min_price = min_price
            metrics.max_price = max_price
            metrics.median_price = median_price
            metrics.spread = spread
            metrics.spread_pct = spread_pct
            metrics.total_listings = len(snapshots)
            metrics.num_marketplaces = len(marketplace_ids)
            metrics.price_change_1d = price_change_1d
            metrics.price_change_7d = price_change_7d
            metrics.price_change_30d = price_change_30d
            metrics.price_change_pct_1d = (price_change_1d / avg_price * 100) if avg_price and price_change_1d else None
            metrics.price_change_pct_7d = (price_change_7d / avg_price * 100) if avg_price and price_change_7d else None
            metrics.price_change_pct_30d = (price_change_30d / avg_price * 100) if avg_price and price_change_30d else None
            metrics.ma_7d = ma_7d
            metrics.ma_30d = ma_30d
            metrics.volatility_7d = volatility_7d
            metrics.volatility_30d = volatility_30d
        else:
            # Create new
            metrics = MetricsCardsDaily(
                card_id=card_id,
                date=target_date,
                avg_price=avg_price,
                min_price=min_price,
                max_price=max_price,
                median_price=median_price,
                spread=spread,
                spread_pct=spread_pct,
                total_listings=len(snapshots),
                num_marketplaces=len(marketplace_ids),
                price_change_1d=price_change_1d,
                price_change_7d=price_change_7d,
                price_change_30d=price_change_30d,
                price_change_pct_1d=(price_change_1d / avg_price * 100) if avg_price and price_change_1d else None,
                price_change_pct_7d=(price_change_7d / avg_price * 100) if avg_price and price_change_7d else None,
                price_change_pct_30d=(price_change_30d / avg_price * 100) if avg_price and price_change_30d else None,
                ma_7d=ma_7d,
                ma_30d=ma_30d,
                volatility_7d=volatility_7d,
                volatility_30d=volatility_30d,
            )
            self.db.add(metrics)
        
        await self.db.flush()
        return metrics
    
    async def _compute_price_change(
        self,
        card_id: int,
        target_date: date,
        days: int,
    ) -> float | None:
        """Compute price change over N days using closest available data."""
        past_date = target_date - timedelta(days=days)
        
        # Get average price for target date (or closest available within 2 days, USD only)
        # More lenient window to handle sparse data
        current_query = select(func.avg(PriceSnapshot.price)).where(
            PriceSnapshot.card_id == card_id,
            func.date(PriceSnapshot.time) >= target_date - timedelta(days=2),
            func.date(PriceSnapshot.time) <= target_date,
            PriceSnapshot.price.isnot(None),
            PriceSnapshot.price > 0,
            PriceSnapshot.currency == "USD",  # USD-only mode
        )
        result = await self.db.execute(current_query)
        current_price = result.scalar()
        
        # Get average price for past date (or closest available within 3 days window, USD only)
        # More lenient window for past data since it's older
        past_query = select(func.avg(PriceSnapshot.price)).where(
            PriceSnapshot.card_id == card_id,
            func.date(PriceSnapshot.time) >= past_date - timedelta(days=2),
            func.date(PriceSnapshot.time) <= past_date + timedelta(days=2),
            PriceSnapshot.price.isnot(None),
            PriceSnapshot.price > 0,
            PriceSnapshot.currency == "USD",  # USD-only mode
        )
        result = await self.db.execute(past_query)
        past_price = result.scalar()
        
        if current_price and past_price:
            return float(current_price) - float(past_price)
        return None
    
    async def _compute_moving_average(
        self,
        card_id: int,
        target_date: date,
        days: int,
    ) -> float | None:
        """Compute N-day moving average."""
        start_date = target_date - timedelta(days=days-1)
        
        query = select(func.avg(PriceSnapshot.price)).where(
            PriceSnapshot.card_id == card_id,
            func.date(PriceSnapshot.time) >= start_date,
            func.date(PriceSnapshot.time) <= target_date,
            PriceSnapshot.currency == "USD",  # USD-only mode
        )
        result = await self.db.execute(query)
        avg = result.scalar()
        
        return float(avg) if avg else None
    
    async def _compute_volatility(
        self,
        card_id: int,
        target_date: date,
        days: int,
    ) -> float | None:
        """Compute N-day volatility (standard deviation of daily returns)."""
        start_date = target_date - timedelta(days=days)
        
        # Get daily average prices (USD only)
        query = select(
            func.date(PriceSnapshot.time).label('date'),
            func.avg(PriceSnapshot.price).label('avg_price'),
        ).where(
            PriceSnapshot.card_id == card_id,
            func.date(PriceSnapshot.time) >= start_date,
            func.date(PriceSnapshot.time) <= target_date,
            PriceSnapshot.currency == "USD",  # USD-only mode
        ).group_by(func.date(PriceSnapshot.time)).order_by('date')
        
        result = await self.db.execute(query)
        rows = result.all()
        
        if len(rows) < 2:
            return None
        
        prices = [float(r.avg_price) for r in rows]
        
        # Compute daily returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        if not returns:
            return None
        
        return float(np.std(returns))
    
    async def generate_signals(
        self,
        card_id: int,
        target_date: date | None = None,
    ) -> list[Signal]:
        """
        Generate analytics signals for a card.
        
        Args:
            card_id: Card ID to analyze.
            target_date: Date to generate signals for.
            
        Returns:
            List of Signal objects.
        """
        target_date = target_date or date.today()
        signals = []
        
        # Get latest metrics
        metrics_query = select(MetricsCardsDaily).where(
            MetricsCardsDaily.card_id == card_id,
            MetricsCardsDaily.date == target_date,
        )
        result = await self.db.execute(metrics_query)
        metrics = result.scalar_one_or_none()
        
        if not metrics:
            return signals
        
        # Generate momentum signal
        momentum_signal = await self._generate_momentum_signal(metrics, card_id, target_date)
        if momentum_signal:
            signals.append(momentum_signal)
        
        # Generate volatility signal
        volatility_signal = await self._generate_volatility_signal(metrics, card_id, target_date)
        if volatility_signal:
            signals.append(volatility_signal)
        
        # Generate spread signal
        spread_signal = await self._generate_spread_signal(metrics, card_id, target_date)
        if spread_signal:
            signals.append(spread_signal)
        
        # Generate trend signal
        trend_signal = await self._generate_trend_signal(metrics, card_id, target_date)
        if trend_signal:
            signals.append(trend_signal)
        
        return signals
    
    async def _generate_momentum_signal(
        self,
        metrics: MetricsCardsDaily,
        card_id: int,
        target_date: date,
    ) -> Signal | None:
        """Generate momentum signal based on MA crossover."""
        if not metrics.ma_7d or not metrics.ma_30d:
            return None
        
        ma_ratio = metrics.ma_7d / metrics.ma_30d if metrics.ma_30d else 1.0
        
        if ma_ratio > 1.05:
            signal_type = "momentum_up"
            confidence = min(0.9, (ma_ratio - 1) * 5)
        elif ma_ratio < 0.95:
            signal_type = "momentum_down"
            confidence = min(0.9, (1 - ma_ratio) * 5)
        else:
            return None
        
        signal = Signal(
            card_id=card_id,
            date=target_date,
            signal_type=signal_type,
            value=float(ma_ratio),
            confidence=confidence,
            details=json.dumps({
                "ma_7d": float(metrics.ma_7d),
                "ma_30d": float(metrics.ma_30d),
                "ratio": float(ma_ratio),
            }),
        )
        self.db.add(signal)
        return signal
    
    async def _generate_volatility_signal(
        self,
        metrics: MetricsCardsDaily,
        card_id: int,
        target_date: date,
    ) -> Signal | None:
        """Generate volatility signal."""
        if not metrics.volatility_7d:
            return None
        
        vol = float(metrics.volatility_7d)
        
        if vol > 0.15:  # High volatility threshold
            signal_type = "volatility_high"
            confidence = min(0.9, vol * 3)
        elif vol < 0.03:  # Low volatility threshold
            signal_type = "volatility_low"
            confidence = 0.7
        else:
            return None
        
        signal = Signal(
            card_id=card_id,
            date=target_date,
            signal_type=signal_type,
            value=vol,
            confidence=confidence,
            details=json.dumps({
                "volatility_7d": vol,
                "volatility_30d": float(metrics.volatility_30d) if metrics.volatility_30d else None,
            }),
        )
        self.db.add(signal)
        return signal
    
    async def _generate_spread_signal(
        self,
        metrics: MetricsCardsDaily,
        card_id: int,
        target_date: date,
    ) -> Signal | None:
        """Generate market spread signal."""
        if not metrics.spread_pct:
            return None
        
        spread_pct = float(metrics.spread_pct)
        
        if spread_pct > 30:  # High spread threshold
            signal = Signal(
                card_id=card_id,
                date=target_date,
                signal_type="spread_high",
                value=spread_pct,
                confidence=min(0.9, spread_pct / 50),
                details=json.dumps({
                    "spread": float(metrics.spread) if metrics.spread else None,
                    "spread_pct": spread_pct,
                    "min_price": float(metrics.min_price) if metrics.min_price else None,
                    "max_price": float(metrics.max_price) if metrics.max_price else None,
                }),
            )
            self.db.add(signal)
            return signal
        
        return None
    
    async def _generate_trend_signal(
        self,
        metrics: MetricsCardsDaily,
        card_id: int,
        target_date: date,
    ) -> Signal | None:
        """Generate overall trend signal."""
        pct_7d = float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else 0
        pct_30d = float(metrics.price_change_pct_30d) if metrics.price_change_pct_30d else 0
        
        # Determine trend direction
        if pct_7d > 10 and pct_30d > 15:
            signal_type = "trend_bullish"
            confidence = min(0.85, (pct_7d + pct_30d) / 50)
        elif pct_7d < -10 and pct_30d < -15:
            signal_type = "trend_bearish"
            confidence = min(0.85, abs(pct_7d + pct_30d) / 50)
        elif abs(pct_7d) < 5 and abs(pct_30d) < 10:
            signal_type = "stable"
            confidence = 0.7
        else:
            return None
        
        signal = Signal(
            card_id=card_id,
            date=target_date,
            signal_type=signal_type,
            value=pct_7d,
            confidence=confidence,
            details=json.dumps({
                "price_change_pct_7d": pct_7d,
                "price_change_pct_30d": pct_30d,
            }),
        )
        self.db.add(signal)
        return signal
    
    async def generate_llm_insight(
        self,
        card_id: int,
        target_date: date | None = None,
    ) -> str | None:
        """
        Generate LLM-powered insight for a card.
        
        Args:
            card_id: Card ID to analyze.
            target_date: Date to generate insight for.
            
        Returns:
            Insight string or None.
        """
        target_date = target_date or date.today()
        
        # Get card info
        card_query = select(Card).where(Card.id == card_id)
        result = await self.db.execute(card_query)
        card = result.scalar_one_or_none()
        
        if not card:
            return None
        
        # Get metrics
        metrics_query = select(MetricsCardsDaily).where(
            MetricsCardsDaily.card_id == card_id,
            MetricsCardsDaily.date == target_date,
        )
        result = await self.db.execute(metrics_query)
        metrics = result.scalar_one_or_none()
        
        if not metrics:
            return None
        
        # Get recent signals for context
        signals_query = select(Signal).where(
            Signal.card_id == card_id,
            Signal.date == target_date,
        )
        result = await self.db.execute(signals_query)
        signals = result.scalars().all()
        
        # Build enhanced context for LLM
        # Note: Enhanced prompts expect numeric values, but we format them as strings for display
        # The base client will handle conversion and provide defaults
        context = {
            "card_name": card.name,
            "avg_price": f"{metrics.avg_price:.2f}" if metrics.avg_price else "N/A",
            "price_change_pct_7d": f"{metrics.price_change_pct_7d:.1f}" if metrics.price_change_pct_7d else "N/A",
            "price_change_pct_30d": f"{metrics.price_change_pct_30d:.1f}" if metrics.price_change_pct_30d else "N/A",
            "spread_pct": f"{metrics.spread_pct:.1f}" if metrics.spread_pct else "N/A",
            "volatility_7d": f"{metrics.volatility_7d:.4f}" if metrics.volatility_7d else "N/A",
            "total_listings": metrics.total_listings or 0,
            "signals": [
                {
                    "type": s.signal_type,
                    "confidence": float(s.confidence) if s.confidence else 0.5,
                    "value": float(s.value) if s.value is not None else None,
                }
                for s in signals
            ],
        }
        
        try:
            # Use enhanced prompts and caching by default
            insight = await self.llm.generate_explanation(
                context,
                use_cache=True,
                use_enhanced=True,
            )
            
            # Store insight in the latest signal
            signals_query = select(Signal).where(
                Signal.card_id == card_id,
                Signal.date == target_date,
            ).order_by(Signal.created_at.desc()).limit(1)
            result = await self.db.execute(signals_query)
            signal = result.scalar_one_or_none()
            
            if signal:
                signal.llm_insight = insight
                signal.llm_provider = self.llm.provider_name
            
            return insight
        except Exception as e:
            logger.error("Failed to generate LLM insight", card_id=card_id, error=str(e))
            return None
    
    async def run_daily_analytics(
        self,
        card_ids: list[int] | None = None,
        target_date: date | None = None,
        generate_insights: bool = True,
    ) -> dict[str, Any]:
        """
        Run daily analytics for multiple cards.
        
        Args:
            card_ids: List of card IDs to process. None = all cards.
            target_date: Date to process. Defaults to today.
            generate_insights: Whether to generate LLM insights.
            
        Returns:
            Summary of processing results.
        """
        target_date = target_date or date.today()
        
        # Get cards to process
        if card_ids:
            cards_query = select(Card).where(Card.id.in_(card_ids))
        else:
            cards_query = select(Card)
        
        result = await self.db.execute(cards_query)
        cards = result.scalars().all()
        
        processed = 0
        errors = 0
        
        for card in cards:
            try:
                # Compute metrics
                metrics = await self.compute_daily_metrics(card.id, target_date)
                
                if metrics:
                    # Generate signals
                    await self.generate_signals(card.id, target_date)
                    
                    # Generate LLM insight (for top cards only to save API costs)
                    if generate_insights and processed < 100:
                        await self.generate_llm_insight(card.id, target_date)
                    
                    processed += 1
            except Exception as e:
                logger.error("Failed to process card analytics", card_id=card.id, error=str(e))
                errors += 1
        
        await self.db.commit()
        
        return {
            "date": str(target_date),
            "cards_processed": processed,
            "errors": errors,
            "total_cards": len(cards),
        }

