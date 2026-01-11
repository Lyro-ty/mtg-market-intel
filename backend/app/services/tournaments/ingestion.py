"""
Tournament ingestion service.

Fetches tournament data from TopDeck.gg and stores it in the database.
Handles tournament details, standings, decklists, and meta statistics calculation.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Tournament, TournamentStanding, Decklist, DecklistCard, CardMetaStats
from app.services.tournaments.topdeck_client import TopDeckClient, TopDeckAPIError

logger = structlog.get_logger()


class TournamentIngestionService:
    """
    Service for ingesting tournament data from TopDeck.gg.

    Handles:
    - Fetching recent tournaments
    - Creating/updating tournament records
    - Processing standings and decklists
    - Calculating card meta statistics
    """

    def __init__(self, db: AsyncSession, client: TopDeckClient):
        """
        Initialize tournament ingestion service.

        Args:
            db: Database session
            client: TopDeck.gg API client
        """
        self.db = db
        self.client = client

    async def ingest_recent_tournaments(self, format: str, days: int = 30) -> dict[str, Any]:
        """
        Fetch and store recent tournaments for a format.

        The TopDeck.gg v2 API returns tournaments with standings included,
        so we can process everything from the initial response without
        making additional API calls per tournament.

        Args:
            format: MTG format (Modern, Pioneer, Standard, etc.)
                   Note: Format names are case-sensitive!
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with ingestion statistics:
            - tournaments_fetched: Number of tournaments retrieved from API
            - tournaments_created: Number of new tournaments stored
            - tournaments_updated: Number of existing tournaments updated
            - standings_created: Number of standings created
            - errors: List of error messages
        """
        stats = {
            "format": format,
            "days": days,
            "tournaments_fetched": 0,
            "tournaments_created": 0,
            "tournaments_updated": 0,
            "standings_created": 0,
            "errors": [],
        }

        try:
            # Fetch recent tournaments from TopDeck.gg
            # The v2 API returns tournaments with standings already included
            logger.info("Fetching recent tournaments", format=format, days=days)
            tournaments = await self.client.get_recent_tournaments(format, days)
            stats["tournaments_fetched"] = len(tournaments)

            # Process each tournament from the already-fetched data
            for tournament_data in tournaments:
                try:
                    result = await self._process_tournament_data(tournament_data)
                    if result["created"]:
                        stats["tournaments_created"] += 1
                    else:
                        stats["tournaments_updated"] += 1
                    stats["standings_created"] += result["standings_created"]

                except Exception as e:
                    error_msg = f"Failed to ingest tournament {tournament_data.get('id', 'unknown')}: {str(e)}"
                    logger.error(error_msg, error=str(e))
                    stats["errors"].append(error_msg)

            await self.db.commit()

            logger.info("Tournament ingestion completed", **stats)

        except TopDeckAPIError as e:
            error_msg = f"TopDeck API error: {str(e)}"
            logger.error(error_msg, error=str(e))
            stats["errors"].append(error_msg)
            await self.db.rollback()
        except Exception as e:
            error_msg = f"Unexpected error during tournament ingestion: {str(e)}"
            logger.error(error_msg, error=str(e))
            stats["errors"].append(error_msg)
            await self.db.rollback()
            raise

        return stats

    async def _process_tournament_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Process a normalized tournament data dict and store it.

        Args:
            data: Normalized tournament data from TopDeckClient.get_recent_tournaments()

        Returns:
            Dict with {created: bool, standings_created: int}
        """
        topdeck_id = data["id"]

        # Check if tournament already exists
        existing = await self.db.scalar(
            select(Tournament).where(Tournament.topdeck_id == topdeck_id)
        )

        if existing:
            # Update existing tournament
            existing.name = data["name"]
            existing.format = data["format"]
            existing.date = data["date"]
            existing.player_count = data["player_count"]
            existing.swiss_rounds = data.get("swiss_rounds")
            existing.top_cut_size = data.get("top_cut_size")
            existing.city = data.get("city")
            existing.venue = data.get("venue")
            existing.topdeck_url = data["url"]
            tournament = existing
            created = False
        else:
            # Create new tournament
            tournament = Tournament(
                topdeck_id=topdeck_id,
                name=data["name"],
                format=data["format"],
                date=data["date"],
                player_count=data["player_count"],
                swiss_rounds=data.get("swiss_rounds"),
                top_cut_size=data.get("top_cut_size"),
                city=data.get("city"),
                venue=data.get("venue"),
                topdeck_url=data["url"],
            )
            self.db.add(tournament)
            created = True

        await self.db.flush()

        # Process standings from the included data
        standings_created = 0
        for standing_data in data.get("standings", []):
            result = await self._process_standing_from_data(tournament, standing_data)
            if result:
                standings_created += 1

        await self.db.flush()

        logger.debug(
            "Processed tournament",
            topdeck_id=topdeck_id,
            name=tournament.name,
            created=created,
            standings_created=standings_created
        )

        return {"created": created, "standings_created": standings_created}

    async def _process_standing_from_data(
        self,
        tournament: Tournament,
        standing_data: dict[str, Any]
    ) -> Optional[TournamentStanding]:
        """
        Process a standing from the normalized tournament data.

        Args:
            tournament: Tournament object
            standing_data: Standing dict with rank, wins, losses, draws

        Returns:
            TournamentStanding object or None if skipped
        """
        rank = standing_data.get("rank", 0)
        wins = standing_data.get("wins", 0)
        losses = standing_data.get("losses", 0)
        draws = standing_data.get("draws", 0)

        # Calculate win rate
        total_games = wins + losses + draws
        win_rate = wins / total_games if total_games > 0 else 0.0

        # Use a placeholder player name since the v2 API doesn't include player names
        # in the standings (only decklist data which may be null)
        player_name = f"Player #{rank}"

        # Check if standing already exists for this tournament and rank
        existing = await self.db.scalar(
            select(TournamentStanding).where(
                and_(
                    TournamentStanding.tournament_id == tournament.id,
                    TournamentStanding.rank == rank
                )
            )
        )

        if existing:
            # Update existing standing
            existing.wins = wins
            existing.losses = losses
            existing.draws = draws
            existing.win_rate = win_rate
            return existing
        else:
            # Create new standing
            standing = TournamentStanding(
                tournament_id=tournament.id,
                player_name=player_name,
                rank=rank,
                wins=wins,
                losses=losses,
                draws=draws,
                win_rate=win_rate,
            )
            self.db.add(standing)
            return standing

    async def ingest_tournament_details(self, topdeck_id: str) -> Optional[Tournament]:
        """
        Fetch and store full tournament details with standings and decklists.

        Args:
            topdeck_id: TopDeck.gg tournament ID

        Returns:
            Tournament object if successful, None if tournament not found

        Raises:
            TopDeckAPIError: On API errors
        """
        try:
            # Fetch tournament details
            tournament_data = await self.client.get_tournament(topdeck_id)

            if not tournament_data:
                logger.warning("Tournament not found", topdeck_id=topdeck_id)
                return None

            # Check if tournament already exists
            existing = await self.db.scalar(
                select(Tournament).where(Tournament.topdeck_id == topdeck_id)
            )

            # Parse tournament date
            date_str = tournament_data.get("date")
            tournament_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')) if date_str else datetime.now(timezone.utc)

            # Extract venue info
            venue_data = tournament_data.get("venue", {}) or {}
            city = venue_data.get("city")
            venue_name = venue_data.get("name")

            if existing:
                # Update existing tournament
                existing.name = tournament_data["name"]
                existing.format = tournament_data["format"]
                existing.date = tournament_date
                existing.player_count = tournament_data["player_count"]
                existing.swiss_rounds = tournament_data.get("swiss_rounds")
                existing.top_cut_size = tournament_data.get("top_cut_size")
                existing.city = city
                existing.venue = venue_name
                existing.topdeck_url = tournament_data["url"]
                tournament = existing
            else:
                # Create new tournament
                tournament = Tournament(
                    topdeck_id=topdeck_id,
                    name=tournament_data["name"],
                    format=tournament_data["format"],
                    date=tournament_date,
                    player_count=tournament_data["player_count"],
                    swiss_rounds=tournament_data.get("swiss_rounds"),
                    top_cut_size=tournament_data.get("top_cut_size"),
                    city=city,
                    venue=venue_name,
                    topdeck_url=tournament_data["url"],
                )
                self.db.add(tournament)

            await self.db.flush()

            # Fetch and process standings
            standings_data = await self.client.get_tournament_standings(topdeck_id)

            for standing_data in standings_data:
                await self._process_standing(tournament, standing_data)

            await self.db.flush()

            logger.info(
                "Tournament ingested",
                topdeck_id=topdeck_id,
                name=tournament.name,
                standings_count=len(standings_data)
            )

            return tournament

        except TopDeckAPIError:
            raise
        except Exception as e:
            logger.error(
                "Failed to ingest tournament details",
                topdeck_id=topdeck_id,
                error=str(e)
            )
            raise

    async def _process_standing(
        self,
        tournament: Tournament,
        standing_data: dict[str, Any]
    ) -> TournamentStanding:
        """
        Process a tournament standing and associated decklist.

        Args:
            tournament: Tournament object
            standing_data: Standing data from TopDeck API

        Returns:
            TournamentStanding object
        """
        # Calculate win rate
        wins = standing_data.get("wins", 0)
        losses = standing_data.get("losses", 0)
        draws = standing_data.get("draws", 0)
        total_games = wins + losses + draws
        win_rate = wins / total_games if total_games > 0 else 0.0

        # Check if standing already exists
        existing = await self.db.scalar(
            select(TournamentStanding).where(
                and_(
                    TournamentStanding.tournament_id == tournament.id,
                    TournamentStanding.player_name == standing_data["player_name"]
                )
            )
        )

        if existing:
            # Update existing standing
            existing.player_id = standing_data.get("player_id")
            existing.rank = standing_data["rank"]
            existing.wins = wins
            existing.losses = losses
            existing.draws = draws
            existing.win_rate = win_rate
            standing = existing
        else:
            # Create new standing
            standing = TournamentStanding(
                tournament_id=tournament.id,
                player_name=standing_data["player_name"],
                player_id=standing_data.get("player_id"),
                rank=standing_data["rank"],
                wins=wins,
                losses=losses,
                draws=draws,
                win_rate=win_rate,
            )
            self.db.add(standing)

        await self.db.flush()

        # Fetch and process decklist if player_id is available
        player_id = standing_data.get("player_id")
        if player_id:
            try:
                decklist_data = await self.client.get_decklist(
                    tournament.topdeck_id,
                    player_id
                )

                if decklist_data:
                    await self._process_decklist(standing, decklist_data)

            except TopDeckAPIError as e:
                logger.warning(
                    "Failed to fetch decklist",
                    tournament_id=tournament.topdeck_id,
                    player_id=player_id,
                    error=str(e)
                )

        return standing

    async def _process_decklist(
        self,
        standing: TournamentStanding,
        decklist_data: dict[str, Any]
    ) -> Decklist:
        """
        Process a decklist and its cards.

        Args:
            standing: TournamentStanding object
            decklist_data: Decklist data from TopDeck API

        Returns:
            Decklist object
        """
        # Check if decklist already exists
        existing = await self.db.scalar(
            select(Decklist).where(Decklist.standing_id == standing.id)
        )

        if existing:
            # Update existing decklist
            existing.archetype_name = decklist_data.get("archetype")
            decklist = existing

            # Delete existing decklist cards to rebuild
            await self.db.execute(
                delete(DecklistCard).where(DecklistCard.decklist_id == decklist.id)
            )
        else:
            # Create new decklist
            decklist = Decklist(
                standing_id=standing.id,
                archetype_name=decklist_data.get("archetype"),
            )
            self.db.add(decklist)

        await self.db.flush()

        # Process mainboard cards
        mainboard_cards = decklist_data.get("mainboard", [])
        for card_data in mainboard_cards:
            await self._add_decklist_card(
                decklist,
                card_data["name"],
                card_data["quantity"],
                "mainboard"
            )

        # Process sideboard cards
        sideboard_cards = decklist_data.get("sideboard", [])
        for card_data in sideboard_cards:
            await self._add_decklist_card(
                decklist,
                card_data["name"],
                card_data["quantity"],
                "sideboard"
            )

        return decklist

    async def _add_decklist_card(
        self,
        decklist: Decklist,
        card_name: str,
        quantity: int,
        section: str
    ) -> Optional[DecklistCard]:
        """
        Add a card to a decklist.

        Args:
            decklist: Decklist object
            card_name: Card name
            quantity: Number of copies
            section: Card section (mainboard/sideboard/commander)

        Returns:
            DecklistCard object if card found in database, None otherwise
        """
        # Find card by name (case-insensitive)
        card = await self.db.scalar(
            select(Card)
            .where(func.lower(Card.name) == func.lower(card_name))
            .limit(1)
        )

        if not card:
            logger.warning(
                "Card not found in database",
                card_name=card_name,
                decklist_id=decklist.id
            )
            return None

        # Create decklist card
        decklist_card = DecklistCard(
            decklist_id=decklist.id,
            card_id=card.id,
            quantity=quantity,
            section=section,
        )
        self.db.add(decklist_card)

        return decklist_card

    async def update_card_meta_stats(self, format: str, period: str = "30d") -> int:
        """
        Recalculate CardMetaStats from tournament data.

        Calculates aggregated statistics for cards in a specific format and time period:
        - deck_inclusion_rate: Percentage of decks including the card
        - avg_copies: Average number of copies when included
        - top8_rate: Percentage of top 8 decks including the card
        - win_rate_delta: Win rate difference from format average

        Args:
            format: MTG format (modern, pioneer, standard, etc.)
            period: Time period (7d, 30d, 90d)

        Returns:
            Number of CardMetaStats records updated
        """
        # Parse period to days
        period_days = {
            "7d": 7,
            "30d": 30,
            "90d": 90,
        }.get(period, 30)

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=period_days)

        logger.info(
            "Updating card meta stats",
            format=format,
            period=period,
            cutoff_date=cutoff_date.isoformat()
        )

        # Get all tournaments in the period
        tournaments = await self.db.execute(
            select(Tournament)
            .where(
                and_(
                    Tournament.format == format,
                    Tournament.date >= cutoff_date
                )
            )
        )
        tournament_list = list(tournaments.scalars())

        if not tournament_list:
            logger.warning(
                "No tournaments found for period",
                format=format,
                period=period
            )
            return 0

        tournament_ids = [t.id for t in tournament_list]

        # Calculate format average win rate
        format_avg_win_rate_result = await self.db.execute(
            select(func.avg(TournamentStanding.win_rate))
            .join(Tournament)
            .where(Tournament.id.in_(tournament_ids))
        )
        format_avg_win_rate = format_avg_win_rate_result.scalar() or 0.0

        # Get all unique cards from decklists in these tournaments
        cards_in_meta = await self.db.execute(
            select(Card.id)
            .join(DecklistCard)
            .join(Decklist)
            .join(TournamentStanding)
            .where(TournamentStanding.tournament_id.in_(tournament_ids))
            .distinct()
        )
        card_ids = [row[0] for row in cards_in_meta]

        # Calculate stats for each card
        stats_updated = 0

        for card_id in card_ids:
            # Total decks in period
            total_decks_result = await self.db.execute(
                select(func.count(Decklist.id.distinct()))
                .join(TournamentStanding)
                .where(TournamentStanding.tournament_id.in_(tournament_ids))
            )
            total_decks = total_decks_result.scalar() or 0

            if total_decks == 0:
                continue

            # Decks with this card (mainboard only)
            decks_with_card_result = await self.db.execute(
                select(func.count(Decklist.id.distinct()))
                .join(DecklistCard)
                .join(TournamentStanding)
                .where(
                    and_(
                        DecklistCard.card_id == card_id,
                        DecklistCard.section == "mainboard",
                        TournamentStanding.tournament_id.in_(tournament_ids)
                    )
                )
            )
            decks_with_card = decks_with_card_result.scalar() or 0

            if decks_with_card == 0:
                continue

            # Deck inclusion rate
            deck_inclusion_rate = decks_with_card / total_decks

            # Average copies
            avg_copies_result = await self.db.execute(
                select(func.avg(DecklistCard.quantity))
                .join(Decklist)
                .join(TournamentStanding)
                .where(
                    and_(
                        DecklistCard.card_id == card_id,
                        DecklistCard.section == "mainboard",
                        TournamentStanding.tournament_id.in_(tournament_ids)
                    )
                )
            )
            avg_copies = avg_copies_result.scalar() or 0.0

            # Top 8 rate
            total_top8_result = await self.db.execute(
                select(func.count(Decklist.id.distinct()))
                .join(TournamentStanding)
                .where(
                    and_(
                        TournamentStanding.tournament_id.in_(tournament_ids),
                        TournamentStanding.rank <= 8
                    )
                )
            )
            total_top8 = total_top8_result.scalar() or 0

            top8_with_card_result = await self.db.execute(
                select(func.count(Decklist.id.distinct()))
                .join(DecklistCard)
                .join(TournamentStanding)
                .where(
                    and_(
                        DecklistCard.card_id == card_id,
                        DecklistCard.section == "mainboard",
                        TournamentStanding.tournament_id.in_(tournament_ids),
                        TournamentStanding.rank <= 8
                    )
                )
            )
            top8_with_card = top8_with_card_result.scalar() or 0

            top8_rate = top8_with_card / total_top8 if total_top8 > 0 else 0.0

            # Win rate delta
            avg_win_rate_with_card_result = await self.db.execute(
                select(func.avg(TournamentStanding.win_rate))
                .join(Decklist)
                .join(DecklistCard)
                .where(
                    and_(
                        DecklistCard.card_id == card_id,
                        DecklistCard.section == "mainboard",
                        TournamentStanding.tournament_id.in_(tournament_ids)
                    )
                )
            )
            avg_win_rate_with_card = avg_win_rate_with_card_result.scalar() or 0.0
            win_rate_delta = avg_win_rate_with_card - format_avg_win_rate

            # Upsert CardMetaStats
            existing = await self.db.scalar(
                select(CardMetaStats).where(
                    and_(
                        CardMetaStats.card_id == card_id,
                        CardMetaStats.format == format,
                        CardMetaStats.period == period
                    )
                )
            )

            if existing:
                existing.deck_inclusion_rate = deck_inclusion_rate
                existing.avg_copies = avg_copies
                existing.top8_rate = top8_rate
                existing.win_rate_delta = win_rate_delta
            else:
                meta_stat = CardMetaStats(
                    card_id=card_id,
                    format=format,
                    period=period,
                    deck_inclusion_rate=deck_inclusion_rate,
                    avg_copies=avg_copies,
                    top8_rate=top8_rate,
                    win_rate_delta=win_rate_delta,
                )
                self.db.add(meta_stat)

            stats_updated += 1

        await self.db.commit()

        logger.info(
            "Card meta stats updated",
            format=format,
            period=period,
            stats_updated=stats_updated
        )

        return stats_updated
