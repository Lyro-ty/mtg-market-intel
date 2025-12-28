# Collection, Want List & Insights API Design

**Date:** 2025-12-28
**Status:** Approved
**Author:** Claude + User

## Overview

Backend APIs to power three new frontend pages:
- **Collection** - Set completion tracking, milestones, portfolio stats
- **Want List** - Price target tracking with alerts
- **Insights** - Unified notifications for alerts, opportunities, and tips

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Want list alerts | Real-time job + on-demand | Best UX: background notifications AND live price comparison |
| Notification storage | Unified `Notification` table | Simpler queries, one place for all alert types |
| Collection stats | Cached + on-demand fallback | Fast reads with accurate data on inventory changes |
| Set card counts | Count from `cards` table | All English printings imported via Scryfall bulk |

---

## Database Models

### WantListItem

User's want list with price targets and alert preferences.

```python
class WantListItem(Base):
    __tablename__ = "want_list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), index=True)

    target_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # high, medium, low
    alert_enabled: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="want_list_items")
    card: Mapped["Card"] = relationship("Card")

    __table_args__ = (
        Index("ix_want_list_user_card", "user_id", "card_id", unique=True),
        Index("ix_want_list_alert_enabled", "alert_enabled"),
    )
```

### Notification

Unified notification table for all alert types.

```python
class NotificationType(str, Enum):
    PRICE_ALERT = "price_alert"           # Significant price drop in portfolio
    TARGET_HIT = "target_hit"             # Want list target reached
    SPIKE_DETECTED = "spike_detected"     # Price spike in portfolio
    OPPORTUNITY = "opportunity"           # Near target or undervalued card
    MILESTONE = "milestone"               # Collection achievement unlocked
    EDUCATIONAL = "educational"           # Tips and market insights

class NotificationPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional card reference
    card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cards.id", ondelete="SET NULL"), nullable=True)

    # Flexible metadata (price, change %, action URL, etc.)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Read status
    read: Mapped[bool] = mapped_column(default=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Deduplication hash
    dedup_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    card: Mapped["Card"] = relationship("Card", lazy="joined")

    __table_args__ = (
        Index("ix_notification_user_unread", "user_id", "read"),
        Index("ix_notification_user_type", "user_id", "type"),
        Index("ix_notification_created", "created_at"),
    )
```

### Set

Set metadata with cached card counts.

```python
class Set(Base):
    __tablename__ = "sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    set_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # expansion, core, masters, etc.
    released_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    card_count: Mapped[int] = mapped_column(default=0)  # Cached count from cards table
    icon_svg_uri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### CollectionStats

Cached per-user set completion statistics.

```python
class CollectionStats(Base):
    __tablename__ = "collection_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    set_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    owned_count: Mapped[int] = mapped_column(default=0)
    total_count: Mapped[int] = mapped_column(default=0)  # Denormalized from Set
    total_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    is_stale: Mapped[bool] = mapped_column(default=True, index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_collection_stats_user_set", "user_id", "set_code", unique=True),
        Index("ix_collection_stats_stale", "is_stale"),
    )
```

### UserMilestone

Tracks collection achievements.

```python
class MilestoneType(str, Enum):
    FIRST_RARE = "first_rare"
    FIRST_MYTHIC = "first_mythic"
    SET_25_PCT = "set_25_pct"
    SET_50_PCT = "set_50_pct"
    SET_75_PCT = "set_75_pct"
    SET_COMPLETE = "set_complete"
    MYTHIC_10 = "mythic_10"
    MYTHIC_25 = "mythic_25"
    VALUE_100 = "value_100"
    VALUE_500 = "value_500"
    VALUE_1000 = "value_1000"
    VALUE_5000 = "value_5000"

class UserMilestone(Base):
    __tablename__ = "user_milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    milestone_type: Mapped[str] = mapped_column(String(30), nullable=False)
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Context (which set, which card triggered it, etc.)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_milestone_user_type", "user_id", "milestone_type", unique=True),
    )
```

### User Model Extensions

Add to existing `User` model:

```python
# Notification preferences
email_alerts: Mapped[bool] = mapped_column(default=True)
price_drop_threshold: Mapped[int] = mapped_column(default=10)  # Notify if >X% drop
digest_frequency: Mapped[str] = mapped_column(String(10), default="instant")  # instant, daily, weekly

# Relationships
want_list_items: Mapped[list["WantListItem"]] = relationship("WantListItem", back_populates="user")
notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")
milestones: Mapped[list["UserMilestone"]] = relationship("UserMilestone", back_populates="user")
collection_stats: Mapped[list["CollectionStats"]] = relationship("CollectionStats", back_populates="user")
```

---

## API Routes

### Want List (`/api/want-list`)

```python
router = APIRouter(prefix="/api/want-list", tags=["want-list"])

@router.get("/")
async def list_want_list(
    current_user: User = Depends(get_current_user),
    priority: Optional[str] = None,
    sort_by: str = "priority",  # priority, price, date
    db: AsyncSession = Depends(get_db)
) -> WantListResponse:
    """
    List user's want list with current prices.
    Joins with cards table and latest price snapshots.
    """

@router.post("/")
async def add_to_want_list(
    item: WantListItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> WantListItem:
    """Add card to want list. Returns 409 if already exists."""

@router.patch("/{item_id}")
async def update_want_list_item(
    item_id: int,
    update: WantListItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> WantListItem:
    """Update target price, priority, notes, or alert toggle."""

@router.delete("/{item_id}")
async def remove_from_want_list(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """Remove card from want list."""

@router.get("/near-target")
async def get_near_target(
    current_user: User = Depends(get_current_user),
    threshold_pct: int = 10,
    db: AsyncSession = Depends(get_db)
) -> list[WantListItemWithPrice]:
    """Get cards within X% of target price. For dashboard widget."""
```

**Request/Response Schemas:**

```python
class WantListItemCreate(BaseModel):
    card_id: int
    target_price: Decimal
    priority: Literal["high", "medium", "low"] = "medium"
    alert_enabled: bool = True
    notes: Optional[str] = None

class WantListItemUpdate(BaseModel):
    target_price: Optional[Decimal] = None
    priority: Optional[Literal["high", "medium", "low"]] = None
    alert_enabled: Optional[bool] = None
    notes: Optional[str] = None

class WantListItemResponse(BaseModel):
    id: int
    card_id: int
    card_name: str
    set_code: str
    set_name: str
    image_url: Optional[str]
    current_price: Decimal
    target_price: Decimal
    priority: str
    alert_enabled: bool
    notes: Optional[str]
    added_date: datetime
    price_diff_pct: float  # Computed: (current - target) / current * 100
    is_near_target: bool   # Computed: within 10%
```

### Notifications (`/api/notifications`)

```python
router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("/")
async def list_notifications(
    current_user: User = Depends(get_current_user),
    type: Optional[str] = None,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
) -> NotificationListResponse:
    """List notifications, newest first. Paginated."""

@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UnreadCountResponse:
    """Quick count for nav badge. Cached in Redis."""

@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """Mark single notification as read."""

@router.post("/mark-all-read")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    type: Optional[str] = None,  # Optional: only mark specific type
    db: AsyncSession = Depends(get_db)
) -> MarkAllReadResponse:
    """Mark all notifications as read. Returns count updated."""

@router.delete("/{notification_id}")
async def dismiss_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """Permanently dismiss notification."""
```

**Response Schemas:**

```python
class NotificationResponse(BaseModel):
    id: int
    type: str
    priority: str
    title: str
    message: str
    card_name: Optional[str]
    set_code: Optional[str]
    current_price: Optional[Decimal]
    price_change: Optional[float]
    action: Optional[str]
    action_url: Optional[str]
    read: bool
    timestamp: datetime  # Formatted as "2 hours ago" on frontend

class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int

class UnreadCountResponse(BaseModel):
    count: int
    by_type: dict[str, int]  # e.g., {"alert": 2, "opportunity": 1}
```

### Collection (`/api/collection`)

```python
router = APIRouter(prefix="/api/collection", tags=["collection"])

@router.get("/sets")
async def get_set_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SetProgressResponse:
    """
    Get set completion progress.
    Uses cached CollectionStats, falls back to on-demand if stale.
    """

@router.get("/stats")
async def get_collection_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> CollectionStatsResponse:
    """Aggregate stats: total cards, sets, value, avg completion."""

@router.get("/milestones")
async def get_milestones(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> MilestonesResponse:
    """List achieved and unachieved milestones."""

@router.get("/rarity-distribution")
async def get_rarity_distribution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RarityDistributionResponse:
    """Card counts by rarity (mythic, rare, uncommon, common)."""

@router.post("/refresh")
async def refresh_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RefreshResponse:
    """Force recalculation. Marks stats stale and queues job."""
```

**Response Schemas:**

```python
class SetProgress(BaseModel):
    code: str
    name: str
    owned: int
    total: int
    value: Decimal
    completion_pct: float
    icon_url: Optional[str]

class SetProgressResponse(BaseModel):
    sets: list[SetProgress]
    is_calculating: bool  # True if stats are stale and being recalculated

class CollectionStatsResponse(BaseModel):
    total_cards: int
    unique_cards: int
    sets_started: int
    sets_complete: int
    total_value: Decimal
    avg_completion_pct: float
    is_calculating: bool

class MilestoneResponse(BaseModel):
    type: str
    title: str
    description: str
    achieved: bool
    achieved_at: Optional[datetime]
    metadata: Optional[dict]  # e.g., {"set_code": "MOM"} for set completion

class RarityDistributionResponse(BaseModel):
    mythic: int
    rare: int
    uncommon: int
    common: int
```

### Sets (`/api/sets`)

```python
router = APIRouter(prefix="/api/sets", tags=["sets"])

@router.get("/")
async def list_sets(
    set_type: Optional[str] = None,  # expansion, core, masters, etc.
    db: AsyncSession = Depends(get_db)
) -> list[SetResponse]:
    """List all sets with card counts."""

@router.get("/{code}")
async def get_set(
    code: str,
    db: AsyncSession = Depends(get_db)
) -> SetDetailResponse:
    """Get single set details."""
```

---

## Celery Background Tasks

### check_want_list_prices (hourly)

```python
@celery_app.task(bind=True, queue="default")
def check_want_list_prices(self):
    """
    Check all want list items with alerts enabled.
    Creates notifications when targets are hit or approached.
    """
    # Process in batches of 100 users
    for user_batch in batch_users(100):
        for user in user_batch:
            want_list = get_want_list_with_prices(user.id)

            for item in want_list:
                if not item.alert_enabled:
                    continue

                current = item.current_price
                target = item.target_price

                # Skip if notification sent in last 24h (cooldown)
                if has_recent_notification(user.id, item.card_id, hours=24):
                    continue

                if current <= target:
                    # Target hit!
                    create_notification(
                        user_id=user.id,
                        type=NotificationType.TARGET_HIT,
                        priority=NotificationPriority.HIGH,
                        title=f"{item.card_name} hit your target!",
                        message=f"Now ${current:.2f} (target: ${target:.2f})",
                        card_id=item.card_id,
                        metadata={"current_price": current, "target_price": target}
                    )
                elif current <= target * 1.10:
                    # Within 10% of target
                    create_notification(
                        user_id=user.id,
                        type=NotificationType.OPPORTUNITY,
                        priority=NotificationPriority.MEDIUM,
                        title=f"{item.card_name} approaching target",
                        message=f"${current:.2f} - only {((current-target)/target)*100:.0f}% above target",
                        card_id=item.card_id,
                        metadata={"current_price": current, "target_price": target}
                    )

        # Invalidate Redis cache for affected users
        invalidate_unread_count_cache(user_batch)
```

### check_portfolio_movements (hourly, after price sync)

```python
@celery_app.task(bind=True, queue="default")
def check_portfolio_movements(self):
    """
    Detect significant price movements in user portfolios.
    Respects user-configured thresholds.
    """
    for user_batch in batch_users(100):
        for user in user_batch:
            drop_threshold = user.price_drop_threshold or 10

            # Get inventory items with 24h price changes
            movements = get_inventory_price_movements(user.id, hours=24)

            for item in movements:
                change_pct = item.price_change_pct

                if has_recent_notification(user.id, item.card_id, hours=24):
                    continue

                if change_pct <= -drop_threshold:
                    # Significant drop
                    create_notification(
                        user_id=user.id,
                        type=NotificationType.PRICE_ALERT,
                        priority=NotificationPriority.HIGH if change_pct <= -15 else NotificationPriority.MEDIUM,
                        title=f"{item.card_name} dropped {abs(change_pct):.0f}%",
                        message=f"Now ${item.current_price:.2f}. Consider reviewing your position.",
                        card_id=item.card_id,
                        metadata={"price": item.current_price, "change_pct": change_pct}
                    )
                elif change_pct >= 15:
                    # Spike detected
                    create_notification(
                        user_id=user.id,
                        type=NotificationType.SPIKE_DETECTED,
                        priority=NotificationPriority.HIGH,
                        title=f"{item.card_name} spiked {change_pct:.0f}%!",
                        message=f"Now ${item.current_price:.2f}. Consider selling.",
                        card_id=item.card_id,
                        metadata={"price": item.current_price, "change_pct": change_pct}
                    )
```

### update_collection_stats (triggered on inventory change)

```python
@celery_app.task(bind=True, queue="default")
def update_collection_stats(self, user_id: int, set_codes: list[str] = None):
    """
    Recalculate collection stats for user.
    Called after inventory imports, additions, or deletions.
    """
    if set_codes is None:
        # Recalculate all sets
        set_codes = get_user_set_codes(user_id)

    for set_code in set_codes:
        # Calculate owned count and value
        stats = calculate_set_stats(user_id, set_code)

        # Upsert CollectionStats
        upsert_collection_stats(
            user_id=user_id,
            set_code=set_code,
            owned_count=stats.owned_count,
            total_count=stats.total_count,
            total_value=stats.total_value,
            is_stale=False
        )

    # Check for new milestones
    check_milestones(user_id)

    # Invalidate Redis cache
    invalidate_collection_cache(user_id)


def check_milestones(user_id: int):
    """Check and award new milestones."""
    existing = get_user_milestones(user_id)
    existing_types = {m.milestone_type for m in existing}

    stats = get_aggregate_stats(user_id)

    milestones_to_check = [
        (MilestoneType.FIRST_RARE, lambda: stats.rare_count >= 1),
        (MilestoneType.FIRST_MYTHIC, lambda: stats.mythic_count >= 1),
        (MilestoneType.MYTHIC_10, lambda: stats.mythic_count >= 10),
        (MilestoneType.MYTHIC_25, lambda: stats.mythic_count >= 25),
        (MilestoneType.VALUE_100, lambda: stats.total_value >= 100),
        (MilestoneType.VALUE_500, lambda: stats.total_value >= 500),
        (MilestoneType.VALUE_1000, lambda: stats.total_value >= 1000),
        (MilestoneType.VALUE_5000, lambda: stats.total_value >= 5000),
    ]

    # Check set-based milestones
    for set_stat in stats.sets:
        pct = set_stat.owned_count / set_stat.total_count * 100
        if pct >= 25:
            milestones_to_check.append((MilestoneType.SET_25_PCT, lambda: True, {"set_code": set_stat.code}))
        if pct >= 50:
            milestones_to_check.append((MilestoneType.SET_50_PCT, lambda: True, {"set_code": set_stat.code}))
        # ... etc

    for milestone_type, condition, *metadata in milestones_to_check:
        if milestone_type not in existing_types and condition():
            award_milestone(user_id, milestone_type, metadata[0] if metadata else None)

            # Create notification
            create_notification(
                user_id=user_id,
                type=NotificationType.MILESTONE,
                priority=NotificationPriority.MEDIUM,
                title=f"Achievement Unlocked: {milestone_type.title}",
                message=MILESTONE_DESCRIPTIONS[milestone_type],
                metadata=metadata[0] if metadata else None
            )
```

### sync_sets_from_scryfall (daily)

```python
@celery_app.task(bind=True, queue="low")
def sync_sets_from_scryfall(self):
    """
    Sync set metadata from Scryfall API.
    Updates card counts from local cards table.
    """
    # Fetch sets from Scryfall
    response = requests.get("https://api.scryfall.com/sets")
    scryfall_sets = response.json()["data"]

    for s in scryfall_sets:
        # Count cards in our database for this set
        card_count = count_cards_in_set(s["code"])

        upsert_set(
            code=s["code"],
            name=s["name"],
            set_type=s["set_type"],
            released_at=s.get("released_at"),
            card_count=card_count,
            icon_svg_uri=s.get("icon_svg_uri")
        )

    logger.info(f"Synced {len(scryfall_sets)} sets from Scryfall")
```

### cleanup_expired_notifications (daily)

```python
@celery_app.task(bind=True, queue="low")
def cleanup_expired_notifications(self):
    """
    Clean up old and expired notifications.
    """
    now = datetime.utcnow()

    # Delete expired notifications
    expired_count = delete_notifications_where(expires_at__lt=now)

    # Delete read notifications older than 30 days
    cutoff = now - timedelta(days=30)
    old_read_count = delete_notifications_where(read=True, created_at__lt=cutoff)

    # Delete unread notifications older than 90 days
    unread_cutoff = now - timedelta(days=90)
    old_unread_count = delete_notifications_where(created_at__lt=unread_cutoff)

    logger.info(f"Cleaned up {expired_count} expired, {old_read_count} old read, {old_unread_count} old unread")
```

---

## Production Improvements

### Batching & Performance

```python
def batch_users(batch_size: int = 100):
    """Yield users in batches to avoid memory issues."""
    offset = 0
    while True:
        users = db.query(User).offset(offset).limit(batch_size).all()
        if not users:
            break
        yield users
        offset += batch_size
```

Use `selectinload` / `joinedload` to avoid N+1:

```python
want_list = (
    db.query(WantListItem)
    .options(
        joinedload(WantListItem.card).joinedload(Card.price_snapshots)
    )
    .filter(WantListItem.user_id == user_id)
    .all()
)
```

### Notification Coalescing

Group similar notifications instead of spamming:

```python
def maybe_coalesce_notification(user_id: int, type: str, new_notification: dict):
    """
    Check if we should add to an existing coalesced notification
    instead of creating a new one.
    """
    # Look for recent unread notification of same type
    recent = get_recent_unread(user_id, type, hours=1)

    if recent and recent.metadata.get("coalesced"):
        # Add to existing
        cards = recent.metadata.get("cards", [])
        cards.append(new_notification["card_name"])
        recent.metadata["cards"] = cards
        recent.title = f"{len(cards)} cards approaching target"
        recent.message = ", ".join(cards[:3]) + ("..." if len(cards) > 3 else "")
        return recent

    return create_notification(**new_notification)
```

### Smart Deduplication

```python
def create_notification_with_dedup(user_id: int, type: str, card_id: int, **kwargs):
    """Create notification with deduplication."""
    # Generate dedup hash
    dedup_hash = hashlib.sha256(
        f"{user_id}:{type}:{card_id}:{date.today()}".encode()
    ).hexdigest()[:16]

    # Check for existing
    existing = db.query(Notification).filter(
        Notification.dedup_hash == dedup_hash,
        Notification.read == False
    ).first()

    if existing:
        # Update existing instead of creating new
        existing.created_at = datetime.utcnow()
        existing.metadata = kwargs.get("metadata")
        return existing

    return create_notification(
        user_id=user_id,
        type=type,
        card_id=card_id,
        dedup_hash=dedup_hash,
        **kwargs
    )
```

### Priority Queues

```python
# celery_app.py
from celery import Celery

celery_app = Celery("dualcaster")

celery_app.conf.task_queues = {
    "critical": {"exchange": "critical", "routing_key": "critical"},
    "default": {"exchange": "default", "routing_key": "default"},
    "low": {"exchange": "low", "routing_key": "low"},
}

celery_app.conf.task_routes = {
    "app.tasks.check_want_list_prices": {"queue": "default"},
    "app.tasks.check_portfolio_movements": {"queue": "default"},
    "app.tasks.update_collection_stats": {"queue": "default"},
    "app.tasks.sync_sets_from_scryfall": {"queue": "low"},
    "app.tasks.cleanup_expired_notifications": {"queue": "low"},
    "app.tasks.send_price_alert_email": {"queue": "critical"},
}
```

### Redis Caching

```python
# cache.py
import redis
from functools import wraps

redis_client = redis.Redis.from_url(settings.REDIS_URL)

def get_unread_count(user_id: int) -> int:
    """Get unread notification count with Redis cache."""
    cache_key = f"unread_count:{user_id}"

    cached = redis_client.get(cache_key)
    if cached:
        return int(cached)

    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.read == False
    ).count()

    redis_client.setex(cache_key, 300, count)  # 5 min TTL
    return count

def invalidate_unread_count(user_id: int):
    """Invalidate cache on notification change."""
    redis_client.delete(f"unread_count:{user_id}")

def get_near_target_count(user_id: int) -> int:
    """Get near-target want list count for dashboard."""
    cache_key = f"near_target:{user_id}"

    cached = redis_client.get(cache_key)
    if cached:
        return int(cached)

    count = calculate_near_target_count(user_id)
    redis_client.setex(cache_key, 300, count)
    return count
```

### Observability

```python
import time
import logging
from celery import Task

logger = logging.getLogger(__name__)

class ObservableTask(Task):
    """Base task with timing and error logging."""

    def __call__(self, *args, **kwargs):
        start = time.time()
        task_name = self.name

        try:
            result = super().__call__(*args, **kwargs)
            duration = time.time() - start

            logger.info(f"Task {task_name} completed in {duration:.2f}s")

            # Alert if task takes too long
            if duration > 300:  # 5 minutes
                send_alert(f"Task {task_name} took {duration:.0f}s")

            return result

        except Exception as e:
            duration = time.time() - start
            logger.error(f"Task {task_name} failed after {duration:.2f}s: {e}")
            raise

# Usage
@celery_app.task(bind=True, base=ObservableTask, queue="default")
def check_want_list_prices(self):
    ...
```

---

## Implementation Order

1. **Database migrations** - Create new tables
2. **Models** - WantListItem, Notification, Set, CollectionStats, UserMilestone
3. **API routes** - Want List, Notifications, Collection, Sets
4. **Celery tasks** - Price checks, stats updates, cleanup
5. **Redis caching** - Unread counts, near-target counts
6. **Frontend integration** - Replace mock data with API calls

---

## Task Schedule Summary

| Task | Frequency | Queue | Purpose |
|------|-----------|-------|---------|
| check_want_list_prices | Hourly | default | Price target alerts |
| check_portfolio_movements | Hourly | default | Portfolio spike/drop alerts |
| update_collection_stats | On inventory change | default | Recalculate set completion |
| sync_sets_from_scryfall | Daily | low | Update set metadata |
| cleanup_expired_notifications | Daily | low | Remove old notifications |
