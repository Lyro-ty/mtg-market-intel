"""
Tests for tournament API endpoints.
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Tournament, TournamentStanding, Decklist, DecklistCard, CardMetaStats


@pytest.mark.asyncio
async def test_get_tournaments_empty(client: AsyncClient):
    """Test getting tournaments when none exist."""
    response = await client.get("/api/tournaments")
    assert response.status_code == 200
    data = response.json()
    assert data["tournaments"] == []
    assert data["total"] == 0
    assert "attribution" in data
    assert data["attribution"] == "Data provided by TopDeck.gg"


@pytest.mark.asyncio
async def test_get_tournaments_list(client: AsyncClient, db_session: AsyncSession):
    """Test getting tournaments list."""
    # Create test tournaments
    tournament1 = Tournament(
        topdeck_id="test-tournament-1",
        name="Modern Championship",
        format="Modern",
        date=datetime.now(timezone.utc) - timedelta(days=1),
        player_count=64,
        swiss_rounds=6,
        top_cut_size=8,
        city="Seattle",
        venue="Test Venue",
        topdeck_url="https://topdeck.gg/tournament/test-tournament-1",
    )
    tournament2 = Tournament(
        topdeck_id="test-tournament-2",
        name="Pioneer Challenge",
        format="Pioneer",
        date=datetime.now(timezone.utc) - timedelta(days=7),
        player_count=32,
        swiss_rounds=5,
        top_cut_size=4,
        city="Portland",
        venue="Test Hall",
        topdeck_url="https://topdeck.gg/tournament/test-tournament-2",
    )
    db_session.add_all([tournament1, tournament2])
    await db_session.commit()

    # Test list endpoint
    response = await client.get("/api/tournaments")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tournaments"]) == 2
    assert data["total"] == 2
    assert data["attribution"] == "Data provided by TopDeck.gg"

    # Verify structure of first tournament
    t = data["tournaments"][0]
    assert t["topdeck_id"] == "test-tournament-1"
    assert t["name"] == "Modern Championship"
    assert t["format"] == "Modern"
    assert t["player_count"] == 64


@pytest.mark.asyncio
async def test_get_tournaments_filter_by_format(client: AsyncClient, db_session: AsyncSession):
    """Test filtering tournaments by format."""
    tournament1 = Tournament(
        topdeck_id="test-modern-1",
        name="Modern Event",
        format="Modern",
        date=datetime.now(timezone.utc),
        player_count=32,
        topdeck_url="https://topdeck.gg/tournament/test-modern-1",
    )
    tournament2 = Tournament(
        topdeck_id="test-pioneer-1",
        name="Pioneer Event",
        format="Pioneer",
        date=datetime.now(timezone.utc),
        player_count=32,
        topdeck_url="https://topdeck.gg/tournament/test-pioneer-1",
    )
    db_session.add_all([tournament1, tournament2])
    await db_session.commit()

    response = await client.get("/api/tournaments?format=Modern")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tournaments"]) == 1
    assert data["tournaments"][0]["format"] == "Modern"


@pytest.mark.asyncio
async def test_get_tournaments_filter_by_days(client: AsyncClient, db_session: AsyncSession):
    """Test filtering tournaments by days."""
    tournament_recent = Tournament(
        topdeck_id="test-recent",
        name="Recent Event",
        format="Modern",
        date=datetime.now(timezone.utc) - timedelta(days=3),
        player_count=32,
        topdeck_url="https://topdeck.gg/tournament/test-recent",
    )
    tournament_old = Tournament(
        topdeck_id="test-old",
        name="Old Event",
        format="Modern",
        date=datetime.now(timezone.utc) - timedelta(days=30),
        player_count=32,
        topdeck_url="https://topdeck.gg/tournament/test-old",
    )
    db_session.add_all([tournament_recent, tournament_old])
    await db_session.commit()

    response = await client.get("/api/tournaments?days=7")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tournaments"]) == 1
    assert data["tournaments"][0]["topdeck_id"] == "test-recent"


@pytest.mark.asyncio
async def test_get_tournaments_filter_by_min_players(client: AsyncClient, db_session: AsyncSession):
    """Test filtering tournaments by minimum players."""
    tournament_small = Tournament(
        topdeck_id="test-small",
        name="Small Event",
        format="Modern",
        date=datetime.now(timezone.utc),
        player_count=16,
        topdeck_url="https://topdeck.gg/tournament/test-small",
    )
    tournament_large = Tournament(
        topdeck_id="test-large",
        name="Large Event",
        format="Modern",
        date=datetime.now(timezone.utc),
        player_count=64,
        topdeck_url="https://topdeck.gg/tournament/test-large",
    )
    db_session.add_all([tournament_small, tournament_large])
    await db_session.commit()

    response = await client.get("/api/tournaments?min_players=32")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tournaments"]) == 1
    assert data["tournaments"][0]["player_count"] == 64


@pytest.mark.asyncio
async def test_get_tournaments_pagination(client: AsyncClient, db_session: AsyncSession):
    """Test tournament list pagination."""
    # Create 25 tournaments
    tournaments = [
        Tournament(
            topdeck_id=f"test-tournament-{i}",
            name=f"Tournament {i}",
            format="Modern",
            date=datetime.now(timezone.utc) - timedelta(days=i),
            player_count=32,
            topdeck_url=f"https://topdeck.gg/tournament/test-tournament-{i}",
        )
        for i in range(25)
    ]
    db_session.add_all(tournaments)
    await db_session.commit()

    # First page
    response = await client.get("/api/tournaments?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tournaments"]) == 10
    assert data["total"] == 25
    assert data["has_more"] is True

    # Second page
    response = await client.get("/api/tournaments?page=2&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tournaments"]) == 10

    # Last page
    response = await client.get("/api/tournaments?page=3&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tournaments"]) == 5
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_get_tournament_by_id(client: AsyncClient, db_session: AsyncSession):
    """Test getting a specific tournament with standings."""
    # Create card
    card = Card(
        scryfall_id="test-card-1",
        name="Lightning Bolt",
        set_code="TST",
        collector_number="1",
    )
    db_session.add(card)
    await db_session.flush()

    # Create tournament
    tournament = Tournament(
        topdeck_id="test-tournament-detail",
        name="Modern Championship",
        format="Modern",
        date=datetime.now(timezone.utc),
        player_count=64,
        swiss_rounds=6,
        top_cut_size=8,
        city="Seattle",
        venue="Test Venue",
        topdeck_url="https://topdeck.gg/tournament/test-tournament-detail",
    )
    db_session.add(tournament)
    await db_session.flush()

    # Create standings
    standing1 = TournamentStanding(
        tournament_id=tournament.id,
        player_name="Player 1",
        rank=1,
        wins=6,
        losses=0,
        draws=0,
        win_rate=1.0,
    )
    standing2 = TournamentStanding(
        tournament_id=tournament.id,
        player_name="Player 2",
        rank=2,
        wins=5,
        losses=1,
        draws=0,
        win_rate=0.833,
    )
    db_session.add_all([standing1, standing2])
    await db_session.flush()

    # Create decklist for standing1
    decklist = Decklist(
        standing_id=standing1.id,
        archetype_name="Burn",
    )
    db_session.add(decklist)
    await db_session.flush()

    # Add cards to decklist
    decklist_card = DecklistCard(
        decklist_id=decklist.id,
        card_id=card.id,
        quantity=4,
        section="mainboard",
    )
    db_session.add(decklist_card)
    await db_session.commit()

    # Test endpoint
    response = await client.get(f"/api/tournaments/{tournament.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == tournament.id
    assert data["name"] == "Modern Championship"
    assert data["format"] == "Modern"
    assert data["player_count"] == 64
    assert len(data["standings"]) == 2
    assert data["attribution"] == "Data provided by TopDeck.gg"

    # Verify standings
    assert data["standings"][0]["rank"] == 1
    assert data["standings"][0]["player_name"] == "Player 1"
    assert data["standings"][0]["wins"] == 6
    assert data["standings"][0]["decklist"] is not None
    assert data["standings"][0]["decklist"]["archetype_name"] == "Burn"


@pytest.mark.asyncio
async def test_get_tournament_not_found(client: AsyncClient):
    """Test getting non-existent tournament returns 404."""
    response = await client.get("/api/tournaments/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_decklist(client: AsyncClient, db_session: AsyncSession):
    """Test getting a specific decklist with cards."""
    # Create cards
    card1 = Card(
        scryfall_id="test-card-1",
        name="Lightning Bolt",
        set_code="TST",
        collector_number="1",
    )
    card2 = Card(
        scryfall_id="test-card-2",
        name="Mountain",
        set_code="TST",
        collector_number="2",
    )
    db_session.add_all([card1, card2])
    await db_session.flush()

    # Create tournament and standing
    tournament = Tournament(
        topdeck_id="test-tournament",
        name="Test Tournament",
        format="Modern",
        date=datetime.now(timezone.utc),
        player_count=32,
        topdeck_url="https://topdeck.gg/tournament/test",
    )
    db_session.add(tournament)
    await db_session.flush()

    standing = TournamentStanding(
        tournament_id=tournament.id,
        player_name="Test Player",
        rank=1,
        wins=5,
        losses=0,
        draws=0,
        win_rate=1.0,
    )
    db_session.add(standing)
    await db_session.flush()

    # Create decklist
    decklist = Decklist(
        standing_id=standing.id,
        archetype_name="Burn",
    )
    db_session.add(decklist)
    await db_session.flush()

    # Add cards to decklist
    decklist_card1 = DecklistCard(
        decklist_id=decklist.id,
        card_id=card1.id,
        quantity=4,
        section="mainboard",
    )
    decklist_card2 = DecklistCard(
        decklist_id=decklist.id,
        card_id=card2.id,
        quantity=18,
        section="mainboard",
    )
    db_session.add_all([decklist_card1, decklist_card2])
    await db_session.commit()

    # Test endpoint
    response = await client.get(f"/api/tournaments/{tournament.id}/decklists/{decklist.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == decklist.id
    assert data["archetype_name"] == "Burn"
    assert data["tournament_id"] == tournament.id
    assert data["tournament_name"] == "Test Tournament"
    assert data["player_name"] == "Test Player"
    assert data["rank"] == 1
    assert len(data["cards"]) == 2
    assert data["attribution"] == "Data provided by TopDeck.gg"

    # Verify cards
    assert data["cards"][0]["card_name"] == "Lightning Bolt"
    assert data["cards"][0]["quantity"] == 4
    assert data["cards"][0]["section"] == "mainboard"


@pytest.mark.asyncio
async def test_get_decklist_not_found(client: AsyncClient, db_session: AsyncSession):
    """Test getting non-existent decklist returns 404."""
    # Create tournament
    tournament = Tournament(
        topdeck_id="test-tournament",
        name="Test Tournament",
        format="Modern",
        date=datetime.now(timezone.utc),
        player_count=32,
        topdeck_url="https://topdeck.gg/tournament/test",
    )
    db_session.add(tournament)
    await db_session.commit()

    response = await client.get(f"/api/tournaments/{tournament.id}/decklists/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_meta_cards(client: AsyncClient, db_session: AsyncSession):
    """Test getting card meta statistics."""
    # Create cards
    card1 = Card(
        scryfall_id="test-card-1",
        name="Lightning Bolt",
        set_code="TST",
        collector_number="1",
    )
    card2 = Card(
        scryfall_id="test-card-2",
        name="Counterspell",
        set_code="TST",
        collector_number="2",
    )
    db_session.add_all([card1, card2])
    await db_session.flush()

    # Create meta stats
    meta1 = CardMetaStats(
        card_id=card1.id,
        format="Modern",
        period="30d",
        deck_inclusion_rate=0.45,
        avg_copies=3.8,
        top8_rate=0.62,
        win_rate_delta=0.05,
    )
    meta2 = CardMetaStats(
        card_id=card2.id,
        format="Modern",
        period="30d",
        deck_inclusion_rate=0.25,
        avg_copies=2.5,
        top8_rate=0.30,
        win_rate_delta=-0.02,
    )
    db_session.add_all([meta1, meta2])
    await db_session.commit()

    # Test endpoint
    response = await client.get("/api/meta/cards?format=Modern&period=30d")
    assert response.status_code == 200
    data = response.json()

    assert len(data["cards"]) == 2
    assert data["total"] == 2
    assert data["attribution"] == "Data provided by TopDeck.gg"

    # Verify first card (should be sorted by deck_inclusion_rate desc)
    assert data["cards"][0]["card_name"] == "Lightning Bolt"
    assert data["cards"][0]["deck_inclusion_rate"] == 0.45
    assert data["cards"][0]["avg_copies"] == 3.8


@pytest.mark.asyncio
async def test_get_meta_cards_filter_by_format(client: AsyncClient, db_session: AsyncSession):
    """Test filtering meta cards by format."""
    card = Card(
        scryfall_id="test-card-1",
        name="Lightning Bolt",
        set_code="TST",
        collector_number="1",
    )
    db_session.add(card)
    await db_session.flush()

    meta_modern = CardMetaStats(
        card_id=card.id,
        format="Modern",
        period="30d",
        deck_inclusion_rate=0.45,
        avg_copies=3.8,
        top8_rate=0.62,
        win_rate_delta=0.05,
    )
    meta_pioneer = CardMetaStats(
        card_id=card.id,
        format="Pioneer",
        period="30d",
        deck_inclusion_rate=0.30,
        avg_copies=3.5,
        top8_rate=0.50,
        win_rate_delta=0.03,
    )
    db_session.add_all([meta_modern, meta_pioneer])
    await db_session.commit()

    response = await client.get("/api/meta/cards?format=Modern&period=30d")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cards"]) == 1
    assert data["cards"][0]["format"] == "Modern"


@pytest.mark.asyncio
async def test_get_card_meta(client: AsyncClient, db_session: AsyncSession):
    """Test getting meta stats for a specific card."""
    card = Card(
        scryfall_id="test-card-1",
        name="Lightning Bolt",
        set_code="TST",
        collector_number="1",
    )
    db_session.add(card)
    await db_session.flush()

    # Create meta stats for multiple periods
    meta_7d = CardMetaStats(
        card_id=card.id,
        format="Modern",
        period="7d",
        deck_inclusion_rate=0.50,
        avg_copies=3.9,
        top8_rate=0.65,
        win_rate_delta=0.06,
    )
    meta_30d = CardMetaStats(
        card_id=card.id,
        format="Modern",
        period="30d",
        deck_inclusion_rate=0.45,
        avg_copies=3.8,
        top8_rate=0.62,
        win_rate_delta=0.05,
    )
    db_session.add_all([meta_7d, meta_30d])
    await db_session.commit()

    response = await client.get(f"/api/cards/{card.id}/meta")
    assert response.status_code == 200
    data = response.json()

    assert data["card_id"] == card.id
    assert data["card_name"] == "Lightning Bolt"
    assert len(data["stats"]) == 2
    assert data["attribution"] == "Data provided by TopDeck.gg"

    # Verify stats structure
    assert data["stats"][0]["format"] == "Modern"
    assert data["stats"][0]["period"] in ["7d", "30d"]


@pytest.mark.asyncio
async def test_get_card_meta_not_found(client: AsyncClient):
    """Test getting meta for non-existent card returns 404."""
    response = await client.get("/api/cards/999/meta")
    assert response.status_code == 404
