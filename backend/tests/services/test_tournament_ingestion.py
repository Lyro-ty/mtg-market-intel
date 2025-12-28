"""
Tests for tournament ingestion service.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models import (
    Card,
    Tournament,
    TournamentStanding,
    Decklist,
    DecklistCard,
    CardMetaStats,
)
from app.services.tournaments.ingestion import TournamentIngestionService
from app.services.tournaments.topdeck_client import TopDeckClient


@pytest.fixture
def mock_topdeck_client():
    """Create a mock TopDeck client."""
    client = MagicMock(spec=TopDeckClient)
    return client


@pytest.fixture
async def sample_cards(test_db):
    """Create sample cards for testing."""
    cards = [
        Card(
            scryfall_id="00000000-0000-0000-0000-000000000001",
            name="Lightning Bolt",
            set_code="LEA",
            collector_number="1",
        ),
        Card(
            scryfall_id="00000000-0000-0000-0000-000000000002",
            name="Counterspell",
            set_code="LEA",
            collector_number="2",
        ),
        Card(
            scryfall_id="00000000-0000-0000-0000-000000000003",
            name="Dark Ritual",
            set_code="LEA",
            collector_number="3",
        ),
    ]

    for card in cards:
        test_db.add(card)

    await test_db.commit()

    return cards


@pytest.fixture
def sample_tournament_data():
    """Sample tournament data from TopDeck API."""
    return {
        "id": "test-tournament-123",
        "name": "Test Modern Tournament",
        "format": "modern",
        "date": "2025-01-15T10:00:00Z",
        "player_count": 64,
        "swiss_rounds": 6,
        "top_cut_size": 8,
        "venue": {
            "name": "Local Game Store",
            "city": "Seattle"
        },
        "url": "https://topdeck.gg/tournaments/test-tournament-123",
    }


@pytest.fixture
def sample_standings_data():
    """Sample standings data from TopDeck API."""
    return [
        {
            "rank": 1,
            "player_name": "Alice",
            "player_id": "player-001",
            "wins": 6,
            "losses": 0,
            "draws": 0,
        },
        {
            "rank": 2,
            "player_name": "Bob",
            "player_id": "player-002",
            "wins": 5,
            "losses": 1,
            "draws": 0,
        },
    ]


@pytest.fixture
def sample_decklist_data():
    """Sample decklist data from TopDeck API."""
    return {
        "archetype": "Burn",
        "mainboard": [
            {"name": "Lightning Bolt", "quantity": 4},
            {"name": "Dark Ritual", "quantity": 2},
        ],
        "sideboard": [
            {"name": "Counterspell", "quantity": 3},
        ],
    }


@pytest.mark.asyncio
class TestTournamentIngestionService:
    """Test tournament ingestion service."""

    async def test_init(self, test_db, mock_topdeck_client):
        """Test service initialization."""
        service = TournamentIngestionService(test_db, mock_topdeck_client)

        assert service.db == test_db
        assert service.client == mock_topdeck_client

    async def test_ingest_recent_tournaments_success(
        self,
        test_db,
        mock_topdeck_client,
        sample_tournament_data,
        sample_standings_data,
        sample_decklist_data,
        sample_cards,
    ):
        """Test ingesting recent tournaments."""
        # Setup mock client responses
        mock_topdeck_client.get_recent_tournaments = AsyncMock(
            return_value=[{"id": "test-tournament-123"}]
        )
        mock_topdeck_client.get_tournament = AsyncMock(
            return_value=sample_tournament_data
        )
        mock_topdeck_client.get_tournament_standings = AsyncMock(
            return_value=sample_standings_data
        )
        mock_topdeck_client.get_decklist = AsyncMock(
            return_value=sample_decklist_data
        )

        # Create service and ingest
        service = TournamentIngestionService(test_db, mock_topdeck_client)
        stats = await service.ingest_recent_tournaments("modern", days=30)

        # Verify stats
        assert stats["format"] == "modern"
        assert stats["days"] == 30
        assert stats["tournaments_fetched"] == 1
        assert len(stats["errors"]) == 0

        # Verify tournament was created
        tournament = await test_db.scalar(
            select(Tournament).where(Tournament.topdeck_id == "test-tournament-123")
        )
        assert tournament is not None
        assert tournament.name == "Test Modern Tournament"
        assert tournament.format == "modern"
        assert tournament.player_count == 64

        # Verify standings were created
        standings = await test_db.execute(
            select(TournamentStanding).where(
                TournamentStanding.tournament_id == tournament.id
            )
        )
        standings_list = list(standings.scalars())
        assert len(standings_list) == 2
        assert standings_list[0].player_name == "Alice"
        assert standings_list[0].wins == 6
        assert standings_list[0].win_rate == 1.0

    async def test_ingest_tournament_details_new(
        self,
        test_db,
        mock_topdeck_client,
        sample_tournament_data,
        sample_standings_data,
    ):
        """Test ingesting a new tournament."""
        # Setup mock client
        mock_topdeck_client.get_tournament = AsyncMock(
            return_value=sample_tournament_data
        )
        mock_topdeck_client.get_tournament_standings = AsyncMock(
            return_value=sample_standings_data
        )
        mock_topdeck_client.get_decklist = AsyncMock(return_value=None)

        # Ingest tournament
        service = TournamentIngestionService(test_db, mock_topdeck_client)
        tournament = await service.ingest_tournament_details("test-tournament-123")

        # Verify tournament
        assert tournament is not None
        assert tournament.topdeck_id == "test-tournament-123"
        assert tournament.name == "Test Modern Tournament"
        assert tournament.city == "Seattle"
        assert tournament.venue == "Local Game Store"

        # Verify it's persisted
        await test_db.commit()
        db_tournament = await test_db.scalar(
            select(Tournament).where(Tournament.topdeck_id == "test-tournament-123")
        )
        assert db_tournament is not None

    async def test_ingest_tournament_details_existing(
        self,
        test_db,
        mock_topdeck_client,
        sample_tournament_data,
        sample_standings_data,
    ):
        """Test updating an existing tournament."""
        # Create existing tournament
        existing = Tournament(
            topdeck_id="test-tournament-123",
            name="Old Name",
            format="modern",
            date=datetime.now(timezone.utc),
            player_count=32,
            topdeck_url="https://old.url",
        )
        test_db.add(existing)
        await test_db.commit()

        # Setup mock client
        mock_topdeck_client.get_tournament = AsyncMock(
            return_value=sample_tournament_data
        )
        mock_topdeck_client.get_tournament_standings = AsyncMock(
            return_value=sample_standings_data
        )
        mock_topdeck_client.get_decklist = AsyncMock(return_value=None)

        # Ingest tournament
        service = TournamentIngestionService(test_db, mock_topdeck_client)
        tournament = await service.ingest_tournament_details("test-tournament-123")

        # Verify tournament was updated
        assert tournament.id == existing.id
        assert tournament.name == "Test Modern Tournament"
        assert tournament.player_count == 64

    async def test_ingest_tournament_not_found(self, test_db, mock_topdeck_client):
        """Test handling tournament not found."""
        mock_topdeck_client.get_tournament = AsyncMock(return_value=None)

        service = TournamentIngestionService(test_db, mock_topdeck_client)
        tournament = await service.ingest_tournament_details("nonexistent")

        assert tournament is None

    async def test_process_decklist(
        self,
        test_db,
        mock_topdeck_client,
        sample_decklist_data,
        sample_cards,
    ):
        """Test processing a decklist with cards."""
        # Create tournament and standing
        tournament = Tournament(
            topdeck_id="test-tournament-123",
            name="Test Tournament",
            format="modern",
            date=datetime.now(timezone.utc),
            player_count=64,
            topdeck_url="https://test.url",
        )
        test_db.add(tournament)
        await test_db.flush()

        standing = TournamentStanding(
            tournament_id=tournament.id,
            player_name="Alice",
            rank=1,
            wins=6,
            losses=0,
            draws=0,
            win_rate=1.0,
        )
        test_db.add(standing)
        await test_db.flush()

        # Process decklist
        service = TournamentIngestionService(test_db, mock_topdeck_client)
        decklist = await service._process_decklist(standing, sample_decklist_data)

        # Verify decklist
        assert decklist is not None
        assert decklist.standing_id == standing.id
        assert decklist.archetype_name == "Burn"

        await test_db.flush()

        # Verify cards were added
        cards = await test_db.execute(
            select(DecklistCard).where(DecklistCard.decklist_id == decklist.id)
        )
        card_list = list(cards.scalars())
        assert len(card_list) == 3  # 2 mainboard + 1 sideboard

        mainboard_cards = [c for c in card_list if c.section == "mainboard"]
        assert len(mainboard_cards) == 2

        sideboard_cards = [c for c in card_list if c.section == "sideboard"]
        assert len(sideboard_cards) == 1

    async def test_add_decklist_card_not_found(
        self,
        test_db,
        mock_topdeck_client,
    ):
        """Test handling card not found in database."""
        # Create decklist
        tournament = Tournament(
            topdeck_id="test-tournament-123",
            name="Test Tournament",
            format="modern",
            date=datetime.now(timezone.utc),
            player_count=64,
            topdeck_url="https://test.url",
        )
        test_db.add(tournament)
        await test_db.flush()

        standing = TournamentStanding(
            tournament_id=tournament.id,
            player_name="Alice",
            rank=1,
            wins=6,
            losses=0,
            draws=0,
            win_rate=1.0,
        )
        test_db.add(standing)
        await test_db.flush()

        decklist = Decklist(
            standing_id=standing.id,
            archetype_name="Test",
        )
        test_db.add(decklist)
        await test_db.flush()

        # Try to add non-existent card
        service = TournamentIngestionService(test_db, mock_topdeck_client)
        result = await service._add_decklist_card(
            decklist,
            "Nonexistent Card",
            4,
            "mainboard"
        )

        # Should return None and log warning
        assert result is None

    async def test_update_card_meta_stats(
        self,
        test_db,
        mock_topdeck_client,
        sample_cards,
    ):
        """Test calculating card meta statistics."""
        # Create tournament with decklists
        tournament = Tournament(
            topdeck_id="test-tournament-123",
            name="Test Tournament",
            format="modern",
            date=datetime.now(timezone.utc),
            player_count=64,
            topdeck_url="https://test.url",
        )
        test_db.add(tournament)
        await test_db.flush()

        # Create standings and decklists
        for i in range(10):
            standing = TournamentStanding(
                tournament_id=tournament.id,
                player_name=f"Player {i}",
                rank=i + 1,
                wins=6 - i // 2,
                losses=i // 2,
                draws=0,
                win_rate=(6 - i // 2) / 6.0,
            )
            test_db.add(standing)
            await test_db.flush()

            decklist = Decklist(
                standing_id=standing.id,
                archetype_name="Test Deck",
            )
            test_db.add(decklist)
            await test_db.flush()

            # Add Lightning Bolt to 8/10 decks
            if i < 8:
                decklist_card = DecklistCard(
                    decklist_id=decklist.id,
                    card_id=sample_cards[0].id,  # Lightning Bolt
                    quantity=4,
                    section="mainboard",
                )
                test_db.add(decklist_card)

            # Add Counterspell to 3/10 decks (first 3)
            if i < 3:
                decklist_card = DecklistCard(
                    decklist_id=decklist.id,
                    card_id=sample_cards[1].id,  # Counterspell
                    quantity=2,
                    section="mainboard",
                )
                test_db.add(decklist_card)

        await test_db.commit()

        # Update meta stats
        service = TournamentIngestionService(test_db, mock_topdeck_client)
        count = await service.update_card_meta_stats("modern", "30d")

        # Should update stats for cards that appear in decklists
        assert count >= 2

        # Verify Lightning Bolt stats
        bolt_stats = await test_db.scalar(
            select(CardMetaStats).where(
                and_(
                    CardMetaStats.card_id == sample_cards[0].id,
                    CardMetaStats.format == "modern",
                    CardMetaStats.period == "30d",
                )
            )
        )

        assert bolt_stats is not None
        assert bolt_stats.deck_inclusion_rate == 0.8  # 8/10 decks
        assert bolt_stats.avg_copies == 4.0
        assert bolt_stats.top8_rate >= 0.5  # At least 4/8 top 8 decks

    async def test_update_card_meta_stats_no_tournaments(
        self,
        test_db,
        mock_topdeck_client,
    ):
        """Test meta stats update with no tournaments."""
        service = TournamentIngestionService(test_db, mock_topdeck_client)
        count = await service.update_card_meta_stats("modern", "30d")

        # Should return 0 when no tournaments exist
        assert count == 0
