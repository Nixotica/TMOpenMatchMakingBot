import logging
from typing import List

from matchmaking.constants import NUM_LSC_PLAYERS, NUM_1v1_PLAYERS, NUM_1v1v1v1_PLAYERS
from matchmaking.match_queues.enum import QueueType
from matchmaking.match_queues.queued_party import QueuedParty, QueuedPlayer, QueuedTeam
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile


class ActiveMatchQueue:
    """An active queue of players awaiting a match for the given MatchQueue."""

    def __init__(self, match_queue: MatchQueue):
        self.player_parties: List[QueuedParty] = []
        self.queue = match_queue

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
        for queued_party in self.player_parties:
            for player in players:
                if player in queued_party.players():
                    self.player_parties.remove(queued_party)

    def can_add_party(self, players: List[PlayerProfile]) -> bool:
        """Verifies if the given players can join the queue as a party.

        Args:
            players (List[PlayerProfile]): The party to verify if can queue together.

        Returns:
            bool: True if the party can join, False otherwise.
        """
        # Only for 2v2 matches can parties of 2+ players join.
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
            return await ActiveMatch.create_1v1v1v1(
                self.queue, bot_match_id, players_in_match
            )

        elif self.queue.type == QueueType.Queue1v1:
            players_in_match = self.player_parties[:NUM_1v1_PLAYERS]
            players_in_match = [p.players()[0] for p in players_in_match]
            return await ActiveMatch.create_1v1(
                self.queue, bot_match_id, players_in_match
            )

        elif self.queue.type.is_2v2():
            solo_players: List[PlayerProfile] = []
            teams_in_match: List[Team2v2] = []

            for party in self.player_parties:
                # If this is a team, add it to teams in match
                if len(party.players()) == 2:
                    team_name = "Blue" if len(teams_in_match) == 0 else "Red"
                    teams_in_match.append(
                        Team2v2(team_name, party.players()[0], party.players()[1])
                    )

                # Otherwise add it to solo players
                if len(party.players()) == 1:
                    solo_players.append(party.players()[0])

                # If 2 solo players, make them a team
                if len(solo_players) == 2:
                    team_name = "Blue" if len(teams_in_match) == 0 else "Red"
                    teams_in_match.append(
                        Team2v2(team_name, solo_players[0], solo_players[1])
                    )
                    solo_players = []

                # if two teams in match, break
                if len(teams_in_match) == 2:
                    break

            teams = Teams2v2(teams_in_match[0], teams_in_match[1])

            if self.queue.type == QueueType.Queue2v2:
                return await ActiveMatch.create_2v2(self.queue, bot_match_id, teams)
            elif self.queue.type == QueueType.QueueSim2v2:
                return await ActiveMatch.create_sim_2v2(self.queue, bot_match_id, teams)
            else:
                raise Exception("Invalid queue type")

        elif self.queue.type == QueueType.QueueSoloTest:
            player_in_match = self.player_parties[0].players()[0]
            return await ActiveMatch.create_solo(
                self.queue, bot_match_id, player_in_match
            )

        elif self.queue.type == QueueType.QueueLSC:
            players_in_match = self.player_parties[:NUM_LSC_PLAYERS]
            players_in_match = [p.players()[0] for p in players_in_match]
            return await ActiveMatch.create_lsc(
                self.queue, bot_match_id, players_in_match
            )

        else:
            raise Exception("Invalid queue type")
