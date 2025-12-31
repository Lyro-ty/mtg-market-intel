# Phase 2: Connections (Simplified)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to connect and communicate without marketplace complexity

**Architecture:** Simple connection requests, basic messaging, community endorsements

**Tech Stack:** FastAPI, PostgreSQL, optional WebSocket for real-time

**Tasks:** 10 (reduced from 30 in original Phase 2)

---

## What Was Removed

| Original Feature | Why Removed |
|------------------|-------------|
| trade_proposals table | Can't verify trades we don't process |
| trade_proposal_items | Unnecessary complexity |
| Trade state machine | Overkill for introductions |
| Trade-based reputation | Unverifiable |
| Escrow integration | Marketplace complexity |
| Complex negotiation flow | Just connect people |

**New Approach:** We facilitate introductions, not transactions.

---

## Database Schema

```sql
-- Simple connection requests
CREATE TABLE connection_requests (
    id SERIAL PRIMARY KEY,
    requester_id INTEGER REFERENCES users(id) NOT NULL,
    recipient_id INTEGER REFERENCES users(id) NOT NULL,
    card_ids INTEGER[],  -- Cards they might discuss (optional context)
    message TEXT,        -- "Hey, I see you have X, interested in trading?"
    status VARCHAR(20) DEFAULT 'pending',  -- pending, accepted, declined, expired
    created_at TIMESTAMPTZ DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',
    UNIQUE(requester_id, recipient_id)  -- One active request per pair
);

CREATE INDEX ix_connection_requests_recipient ON connection_requests(recipient_id, status);
CREATE INDEX ix_connection_requests_requester ON connection_requests(requester_id);

-- Simple direct messages
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER REFERENCES users(id) NOT NULL,
    recipient_id INTEGER REFERENCES users(id) NOT NULL,
    content TEXT NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_messages_recipient ON messages(recipient_id, read_at);
CREATE INDEX ix_messages_conversation ON messages(
    LEAST(sender_id, recipient_id),
    GREATEST(sender_id, recipient_id),
    created_at DESC
);

-- Community endorsements (not trade-based)
CREATE TABLE user_endorsements (
    id SERIAL PRIMARY KEY,
    endorser_id INTEGER REFERENCES users(id) NOT NULL,
    endorsed_id INTEGER REFERENCES users(id) NOT NULL,
    endorsement_type VARCHAR(30) NOT NULL,  -- 'trustworthy', 'knowledgeable', 'responsive', 'fair_trader'
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(endorser_id, endorsed_id, endorsement_type)
);

CREATE INDEX ix_endorsements_endorsed ON user_endorsements(endorsed_id);

-- Blocked users
CREATE TABLE blocked_users (
    id SERIAL PRIMARY KEY,
    blocker_id INTEGER REFERENCES users(id) NOT NULL,
    blocked_id INTEGER REFERENCES users(id) NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(blocker_id, blocked_id)
);
```

---

## Task 2.1: Connection Request Flow

**Files:**
- Create: `backend/app/models/connection.py`
- Create: `backend/app/api/routes/connections.py`
- Create: `backend/app/schemas/connection.py`
- Test: `backend/tests/api/test_connections.py`

**Step 1: Write failing tests**

```python
# backend/tests/api/test_connections.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_send_connection_request(
    client: AsyncClient,
    auth_headers,
    test_user_2,
):
    """User can send connection request to another user."""
    response = await client.post(
        "/api/connections/request",
        headers=auth_headers,
        json={
            "recipient_id": test_user_2.id,
            "message": "Hey, interested in your Lightning Bolt!",
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_cannot_request_self(client: AsyncClient, auth_headers, test_user):
    """Cannot send connection request to yourself."""
    response = await client.post(
        "/api/connections/request",
        headers=auth_headers,
        json={"recipient_id": test_user.id}
    )
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_accept_connection_request(
    client: AsyncClient,
    auth_headers_2,  # Recipient's auth
    connection_request,  # Fixture that creates pending request
):
    """Recipient can accept connection request."""
    response = await client.post(
        f"/api/connections/{connection_request.id}/accept",
        headers=auth_headers_2,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

@pytest.mark.asyncio
async def test_list_pending_requests(
    client: AsyncClient,
    auth_headers_2,
    connection_request,
):
    """User can see pending connection requests."""
    response = await client.get(
        "/api/connections/pending",
        headers=auth_headers_2,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
```

**Step 2: Implement connection routes**

```python
# backend/app/api/routes/connections.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User, ConnectionRequest
from app.schemas.connection import ConnectionRequestCreate, ConnectionRequestResponse

router = APIRouter(prefix="/connections", tags=["connections"])

@router.post("/request", response_model=ConnectionRequestResponse, status_code=201)
async def send_connection_request(
    request: ConnectionRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a connection request to another user."""
    if request.recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot connect with yourself")

    # Check if blocked
    blocked = await db.execute(
        select(BlockedUser).where(
            BlockedUser.blocker_id == request.recipient_id,
            BlockedUser.blocked_id == current_user.id,
        )
    )
    if blocked.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Cannot send request to this user")

    # Check for existing request
    existing = await db.execute(
        select(ConnectionRequest).where(
            ConnectionRequest.requester_id == current_user.id,
            ConnectionRequest.recipient_id == request.recipient_id,
            ConnectionRequest.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Request already pending")

    connection = ConnectionRequest(
        requester_id=current_user.id,
        recipient_id=request.recipient_id,
        message=request.message,
        card_ids=request.card_ids,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)

    # Send notification
    notification_service = NotificationService(db)
    await notification_service.send(
        user_id=request.recipient_id,
        notification_type="connection_request",
        title="New Connection Request",
        message=f"{current_user.username} wants to connect!",
    )

    return connection

@router.get("/pending", response_model=list[ConnectionRequestResponse])
async def get_pending_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get pending connection requests for current user."""
    result = await db.execute(
        select(ConnectionRequest)
        .where(ConnectionRequest.recipient_id == current_user.id)
        .where(ConnectionRequest.status == "pending")
        .order_by(ConnectionRequest.created_at.desc())
    )
    return result.scalars().all()

@router.post("/{request_id}/accept")
async def accept_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a connection request."""
    request = await db.get(ConnectionRequest, request_id)
    if not request or request.recipient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already handled")

    request.status = "accepted"
    request.responded_at = datetime.now(timezone.utc)
    await db.commit()

    # Notify requester
    notification_service = NotificationService(db)
    await notification_service.send(
        user_id=request.requester_id,
        notification_type="connection_accepted",
        title="Connection Accepted!",
        message=f"{current_user.username} accepted your connection request",
    )

    return {"status": "accepted"}

@router.post("/{request_id}/decline")
async def decline_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Decline a connection request."""
    request = await db.get(ConnectionRequest, request_id)
    if not request or request.recipient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Request not found")

    request.status = "declined"
    request.responded_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "declined"}
```

**Step 3: Run tests**

```bash
pytest backend/tests/api/test_connections.py -v
```

**Step 4: Commit**

```bash
git add backend/app/models/connection.py backend/app/api/routes/connections.py \
        backend/app/schemas/connection.py backend/tests/api/test_connections.py
git commit -m "feat: connection request flow"
```

---

## Task 2.2: Basic Messaging

**Files:**
- Create: `backend/app/models/message.py`
- Create: `backend/app/api/routes/messages.py`
- Test: `backend/tests/api/test_messages.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_send_message_to_connection(
    client: AsyncClient,
    auth_headers,
    accepted_connection,  # Fixture with accepted connection
):
    """Can send message to accepted connection."""
    response = await client.post(
        "/api/messages",
        headers=auth_headers,
        json={
            "recipient_id": accepted_connection.recipient_id,
            "content": "Hey, want to meet at the LGS Saturday?",
        }
    )
    assert response.status_code == 201

@pytest.mark.asyncio
async def test_cannot_message_non_connection(
    client: AsyncClient,
    auth_headers,
    test_user_2,  # No connection
):
    """Cannot message user without connection."""
    response = await client.post(
        "/api/messages",
        headers=auth_headers,
        json={
            "recipient_id": test_user_2.id,
            "content": "Hey!",
        }
    )
    assert response.status_code == 403
```

**Step 2: Implement messaging**

```python
# backend/app/api/routes/messages.py
router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/", status_code=201)
async def send_message(
    message: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message to a connected user."""
    # Verify connection exists
    connected = await check_connection(db, current_user.id, message.recipient_id)
    if not connected:
        raise HTTPException(
            status_code=403,
            detail="Must have accepted connection to message"
        )

    # Check not blocked
    blocked = await db.execute(
        select(BlockedUser).where(
            BlockedUser.blocker_id == message.recipient_id,
            BlockedUser.blocked_id == current_user.id,
        )
    )
    if blocked.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Cannot message this user")

    msg = Message(
        sender_id=current_user.id,
        recipient_id=message.recipient_id,
        content=message.content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Send notification
    notification_service = NotificationService(db)
    await notification_service.send(
        user_id=message.recipient_id,
        notification_type="new_message",
        title="New Message",
        message=f"{current_user.username}: {message.content[:50]}...",
    )

    return msg

@router.get("/conversations")
async def get_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of conversations with last message."""
    query = """
        WITH conversation_partners AS (
            SELECT DISTINCT
                CASE
                    WHEN sender_id = :user_id THEN recipient_id
                    ELSE sender_id
                END as partner_id
            FROM messages
            WHERE sender_id = :user_id OR recipient_id = :user_id
        )
        SELECT
            u.id,
            u.username,
            u.avatar_url,
            m.content as last_message,
            m.created_at as last_message_at,
            (SELECT COUNT(*) FROM messages
             WHERE sender_id = u.id AND recipient_id = :user_id AND read_at IS NULL
            ) as unread_count
        FROM conversation_partners cp
        JOIN users u ON cp.partner_id = u.id
        JOIN LATERAL (
            SELECT content, created_at FROM messages
            WHERE (sender_id = :user_id AND recipient_id = u.id)
               OR (sender_id = u.id AND recipient_id = :user_id)
            ORDER BY created_at DESC LIMIT 1
        ) m ON true
        ORDER BY m.created_at DESC
    """
    result = await db.execute(text(query), {"user_id": current_user.id})
    return [dict(row._mapping) for row in result.all()]

@router.get("/with/{user_id}")
async def get_conversation(
    user_id: int,
    limit: int = Query(default=50, le=100),
    before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get messages with a specific user."""
    query = select(Message).where(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current_user.id),
        )
    ).order_by(Message.created_at.desc()).limit(limit)

    if before:
        query = query.where(Message.created_at < before)

    result = await db.execute(query)
    messages = result.scalars().all()

    # Mark as read
    await db.execute(
        update(Message)
        .where(Message.sender_id == user_id)
        .where(Message.recipient_id == current_user.id)
        .where(Message.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()

    return messages
```

**Step 3: Commit**

```bash
git commit -m "feat: basic messaging between connected users"
```

---

## Task 2.3: Messaging UI

**Files:**
- Create: `frontend/src/app/(protected)/messages/page.tsx`
- Create: `frontend/src/app/(protected)/messages/[userId]/page.tsx`
- Create: `frontend/src/components/messaging/ConversationList.tsx`
- Create: `frontend/src/components/messaging/MessageThread.tsx`

**Implementation:** Standard React components with React Query for data fetching. Polling every 10 seconds for new messages (WebSocket can be added later).

---

## Task 2.4: User Endorsements

**Files:**
- Create: `backend/app/models/endorsement.py`
- Create: `backend/app/api/routes/endorsements.py`
- Test: `backend/tests/api/test_endorsements.py`

```python
# backend/app/api/routes/endorsements.py
ENDORSEMENT_TYPES = ["trustworthy", "knowledgeable", "responsive", "fair_trader"]

@router.post("/users/{user_id}/endorse")
async def endorse_user(
    user_id: int,
    endorsement: EndorsementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Endorse another user."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot endorse yourself")

    if endorsement.endorsement_type not in ENDORSEMENT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid endorsement type")

    # Must have connection to endorse
    connected = await check_connection(db, current_user.id, user_id)
    if not connected:
        raise HTTPException(status_code=403, detail="Must be connected to endorse")

    # Check if already endorsed for this type
    existing = await db.execute(
        select(UserEndorsement).where(
            UserEndorsement.endorser_id == current_user.id,
            UserEndorsement.endorsed_id == user_id,
            UserEndorsement.endorsement_type == endorsement.endorsement_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already endorsed for this type")

    endo = UserEndorsement(
        endorser_id=current_user.id,
        endorsed_id=user_id,
        endorsement_type=endorsement.endorsement_type,
        comment=endorsement.comment,
    )
    db.add(endo)
    await db.commit()

    return {"success": True}

@router.get("/users/{user_id}/endorsements")
async def get_user_endorsements(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get endorsements for a user."""
    result = await db.execute(
        select(
            UserEndorsement.endorsement_type,
            func.count().label("count")
        )
        .where(UserEndorsement.endorsed_id == user_id)
        .group_by(UserEndorsement.endorsement_type)
    )
    return {row.endorsement_type: row.count for row in result.all()}
```

**Step 2: Display on public profile**

```tsx
// On public profile page
<div className="flex gap-2">
  {endorsements.trustworthy > 0 && (
    <Badge variant="outline">
      Trustworthy ({endorsements.trustworthy})
    </Badge>
  )}
  {endorsements.responsive > 0 && (
    <Badge variant="outline">
      Responsive ({endorsements.responsive})
    </Badge>
  )}
</div>
```

**Step 3: Commit**

```bash
git commit -m "feat: community endorsements for users"
```

---

## Task 2.5: Block/Report Users

**Files:**
- Create: `backend/app/api/routes/moderation.py`

```python
@router.post("/users/{user_id}/block")
async def block_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Block a user from messaging you."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    block = BlockedUser(
        blocker_id=current_user.id,
        blocked_id=user_id,
    )
    db.add(block)
    await db.commit()
    return {"success": True}

@router.post("/users/{user_id}/report")
async def report_user(
    user_id: int,
    report: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Report a user for inappropriate behavior."""
    # Store in reports table for admin review
    report = UserReport(
        reporter_id=current_user.id,
        reported_id=user_id,
        reason=report.reason,
        details=report.details,
    )
    db.add(report)
    await db.commit()

    # Optionally notify admins
    return {"success": True, "message": "Report submitted for review"}
```

---

## Task 2.6-2.10: (Abbreviated)

**Task 2.6: Location-Based Discovery**
- Filter matching by location
- "Users near Seattle with cards I want"

**Task 2.7: Notification Integration**
- Notify on new connection requests
- Notify on new messages

**Task 2.8: Discord Integration for Connections**
- DM when new connection request
- "You have 3 pending connection requests"

**Task 2.9: Public Want Lists**
- Optional flag to make want list public
- Shows on public profile

**Task 2.10: Connection Suggestions**
- Weekly email: "Users who match with you"
- Based on want list / available for trade overlap

---

## Phase 2 Completion Checklist

- [ ] Task 2.1: Connection request flow
- [ ] Task 2.2: Basic messaging
- [ ] Task 2.3: Messaging UI
- [ ] Task 2.4: User endorsements
- [ ] Task 2.5: Block/report users
- [ ] Task 2.6: Location-based discovery
- [ ] Task 2.7: Notification integration
- [ ] Task 2.8: Discord integration
- [ ] Task 2.9: Public want lists
- [ ] Task 2.10: Connection suggestions

**Success Criteria:**
- Users can connect and message each other
- Endorsements visible on profiles
- Blocking prevents unwanted contact
- Location filtering works in discovery
