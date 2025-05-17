import logging
from typing import List, Optional

from aws.dynamodb import DynamoDbManager
from matchmaking.constants import (
    NUM_LSC_PLAYERS,
    NUM_1v1_PLAYERS,
    NUM_1v1v1v1_PLAYERS,
    NUM_2v2_PLAYERS,
)
from matchmaking.match_queues.constants import TEAM_BLUE, TEAM_RED
from matchmaking.match_queues.enum import QueueType
from matchmaking.match_queues.queued_party import QueuedParty, QueuedPlayer, QueuedTeam
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from matchmaking.mm_event_bus import MatchmakingManagerEventBus
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile


class ActiveMatchQueue:
    """An active queue of players awaiting a match for the given MatchQueue."""

    def __init__(self, match_queue: MatchQueue):
        self.player_parties: List[QueuedParty] = []
        self.queue = match_queue
        self.mm_event_bus = MatchmakingManagerEventBus()

    def player_count(self) -> int:
        """Get the number of players currently queued in this match queue.

        Returns:
            int: Number of players currently queued
        """
        if self.queue.type.is_2v2():
            total_players = 0
            for party in self.player_parties:
                total_players += len(party.players())
            return total_players
        return len(self.player_parties)

    def is_player_queued(self, player: PlayerProfile) -> bool:
        """Check if player is in this match queue.

        Args:
            player (PlayerProfile): The player to check.

        Returns:
            bool: Returns true if player is in queue, otherwise False.
        """
        for queued_player_party in self.player_parties:
            if player in queued_player_party.players():
                return True

        return False

    def add_party(self, players: List[PlayerProfile]) -> bool:
        """Adds a party to the active queue.

        Args:
            party (ActiveParty): The party to add to the queue.

        Returns:
            bool: True if party was added to queue, False if they were already in the queue.
        """
        # Reject players joining again if they are part of any queued party
        for player in players:
            if self.is_player_queued(player):
                return False

        # No support for parties more than 2 players
        if len(players) > 2:
            logging.warning("Attempted to add party of size greater than 2 to queue.")
            return False

        if len(players) == 1:
            self.player_parties.append(
                QueuedPlayer.new_joined_player(players[0], self.queue.queue_id)
            )
        elif len(players) == 2:
            self.player_parties.append(
                QueuedTeam.new_joined_team(players[0], players[1], self.queue.queue_id)
            )

        return True

    def remove_party(self, players: List[PlayerProfile]) -> None:
        """Removes a party from the queue.

        Args:
            players (List[PlayerProfile]): The party to remove from the queue.
        """
        player_parties_copy = self.player_parties.copy()
        for queued_party in player_parties_copy:
            for player in players:
                if (
                    player in queued_party.players()
                    and queued_party in self.player_parties
                ):
                    self.player_parties.remove(queued_party)

    def can_add_party(self, players: List[PlayerProfile]) -> bool:
        """Verifies if the given players can join the queue as a party.

        Args:
            players (List[PlayerProfile]): The party to verify if can queue together.

        Returns:
            bool: True if the party can join, False otherwise.
        """
        # Only for 2v2 matches can parties of 2+ players join.
        # TODO - parties should be allowed to do 1v1 against each other
        if (not self.queue.type.is_2v2()) and len(players) > 1:
            return False

        return True

    def should_generate_match(self) -> bool:
        """Determines if a match should be generated from the current queue

        Returns:
            bool: True if a match should be generated, False otherwise.
        """
        logging.debug(
            f"Checking if should generate match for {self.queue.queue_id} length {len(self.player_parties)}."
        )
        if self.queue.type == QueueType.Queue1v1v1v1:
            if len(self.player_parties) >= NUM_1v1v1v1_PLAYERS:
                return True
        elif self.queue.type == QueueType.Queue1v1:
            if len(self.player_parties) >= NUM_1v1_PLAYERS:
                return True
        elif self.queue.type.is_2v2():
            total_players = 0
            for party in self.player_parties:
                total_players += len(party.players())
            return total_players >= 4
        elif self.queue.type == QueueType.QueueSoloTest:
            if len(self.player_parties) >= 1:
                return True
        elif self.queue.type == QueueType.QueueLSC:
            if len(self.player_parties) >= NUM_LSC_PLAYERS:
                return True

        return False

    async def generate_match(self, bot_match_id: int) -> ActiveMatch:
        """Generates a match with the given bot match ID.

        Args:
            bot_match_id (int): The ID to give to the current match (used in its event name)

        Returns:
            ActiveMatch: The active match created as an event.
        """
        if self.queue.type == QueueType.Queue1v1v1v1:
            players_in_match = self.player_parties[:NUM_1v1v1v1_PLAYERS]
            players_in_match = [p.players()[0] for p in players_in_match]
            self.mm_event_bus.add_new_pending_match(
                self.queue.queue_id, bot_match_id, players_in_match
            )
            return await ActiveMatch.create_1v1v1v1(
                self.queue, bot_match_id, players_in_match
            )

        elif self.queue.type == QueueType.Queue1v1:
            players_in_match = self.player_parties[:NUM_1v1_PLAYERS]
            players_in_match = [p.players()[0] for p in players_in_match]
            self.mm_event_bus.add_new_pending_match(
                self.queue.queue_id, bot_match_id, players_in_match
            )
            return await ActiveMatch.create_1v1(
                self.queue, bot_match_id, players_in_match
            )

        elif self.queue.type.is_2v2():
            teams = self._get_2v2_teams_from_parties()
            if teams is None:
                raise Exception(
                    f"Failed to form teams from parties in queue {self.queue.queue_id}."
                    f"Player parties: {self.player_parties}"
                )

            self.mm_event_bus.add_new_pending_match(
                self.queue.queue_id, bot_match_id, teams.players()
            )
            if self.queue.type == QueueType.Queue2v2:
                return await ActiveMatch.create_2v2(self.queue, bot_match_id, teams)
            elif self.queue.type == QueueType.QueueScrim2v2:
                return await ActiveMatch.create_2v2_scrim(
                    self.queue, bot_match_id, teams
                )
            elif self.queue.type == QueueType.QueueSim2v2:
                return await ActiveMatch.create_sim_2v2(self.queue, bot_match_id, teams)
            else:
                raise Exception("Invalid queue type")

        elif self.queue.type == QueueType.QueueSoloTest:
            player_in_match = self.player_parties[0].players()[0]
            return await ActiveMatch.create_solo(
                self.queue, bot_match_id, player_in_match
            )

        # TODO - remove this shitty useless queue type
        elif self.queue.type == QueueType.QueueLSC:
            players_in_match = self.player_parties[:NUM_LSC_PLAYERS]
            players_in_match = [p.players()[0] for p in players_in_match]
            return await ActiveMatch.create_lsc(
                self.queue, bot_match_id, players_in_match
            )

        else:
            raise Exception("Invalid queue type")

    def _get_2v2_teams_from_parties(self) -> Optional[Teams2v2]:
        # If the first 4 parties are solo queued, form teams from them
        # TODO - if we have a lot of players queued at once in the future, we should check all of them and
        # perform a more intelligent elo balancing across all queued parties (even teams vs 2 solo players)
        first_four_parties = self.player_parties[:NUM_2v2_PLAYERS]
        if all(len(party.players()) == 1 for party in first_four_parties):
            teams = self._form_teams_from_solo_queued_players(
                [party.players()[0] for party in self.player_parties]
            )
            return teams

        # Otherwise form teams from the queued parties (only can be done deterministically)
        solo_players: List[PlayerProfile] = []
        teams_in_match: List[Team2v2] = []

        for party in self.player_parties:
            # If this is a team, add it to teams in match
            if len(party.players()) == 2:
                team_name = TEAM_BLUE if len(teams_in_match) == 0 else TEAM_RED
                teams_in_match.append(
                    Team2v2(team_name, party.players()[0], party.players()[1])
                )

            # Otherwise add it to solo players
            if len(party.players()) == 1:
                solo_players.append(party.players()[0])

            # If 2 solo players, make them a team
            if len(solo_players) == 2:
                team_name = TEAM_BLUE if len(teams_in_match) == 0 else TEAM_RED
                teams_in_match.append(
                    Team2v2(team_name, solo_players[0], solo_players[1])
                )
                solo_players = []

            # if two teams in match, break
            if len(teams_in_match) == 2:
                break

        teams = Teams2v2(teams_in_match[0], teams_in_match[1])
        return teams

    def _form_teams_from_solo_queued_players(
        self, players: List[PlayerProfile]
    ) -> Optional[Teams2v2]:
        """Forms teams from all solo queued players. It will try to balance the teams based on their
            elo rating on the queue's primary leaderboard such that (avg_elo_team1 - avg_elo_team2) is minimized.

        Args:
            players (List[PlayerProfile]): List of solo queued players (must be 4 players).

        Returns:
            Optional[Teams2v2]: Teams2v2 object with the teams formed from the players, or None if conditions not met.
        """
        if len(players) != NUM_2v2_PLAYERS:
            logging.warning(
                f"Attempted to form teams from {len(players)} players, but 2v2 requires exactly"
                f"{NUM_2v2_PLAYERS} players."
            )
            return None

        primary_leaderboard_id = self.queue.get_primary_leaderboard()
        if primary_leaderboard_id is None:
            logging.info(
                f"Queue {self.queue.queue_id} does not have a primary leaderboard ID. Naively forming teams"
            )

            return Teams2v2(
                team_a=Team2v2(TEAM_BLUE, players[0], players[1]),
                team_b=Team2v2(TEAM_RED, players[2], players[3]),
            )

        # Get all players' leaderboard elo ratings and sort them
        ddb_manager = self._get_ddb_manager()
        player_elos = [
            ddb_manager.get_or_create_player_elo(
                player.tm_account_id, primary_leaderboard_id
            )
            for player in players
        ]
        sorted_players = sorted(player_elos, key=lambda x: x.elo)
        sorted_tm_account_ids = [player.tm_account_id for player in sorted_players]
        sorted_players = [
            player
            for player in players
            if player.tm_account_id in sorted_tm_account_ids
        ]

        # Players ranked 1, 4 will be on one team, and players ranked 2, 3 will be on the other team
        return Teams2v2(
            team_a=Team2v2(TEAM_BLUE, sorted_players[0], sorted_players[3]),
            team_b=Team2v2(TEAM_RED, sorted_players[1], sorted_players[2]),
        )

    def _get_ddb_manager(self) -> DynamoDbManager:
        return DynamoDbManager()
