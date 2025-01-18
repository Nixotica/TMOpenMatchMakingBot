import logging
from typing import List
from matchmaking.party.active_party import ActiveParty
from models.player_profile import PlayerProfile
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from models.match_queue import MatchQueue
from matchmaking.match_queues.enum import QueueType
from matchmaking.match_queues.queued_party import QueuedParty, QueuedPlayer, QueuedTeam
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.constants import NUM_1v1v1v1_PLAYERS, NUM_LSC_PLAYERS


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

    def add_player(self, player: PlayerProfile) -> bool:
        """Adds a player to the active queue.

        Args:
            player (PlayerProfile): The player to add to the queue.

        Returns:
            bool: True if player was added to queue, False if they were already in the queue.
        """
        if not self.is_player_queued(player):
            self.player_parties.append(
                QueuedPlayer.new_joined_player(player, self.queue.queue_id)
            )
            logging.info(
                f"Added player {player.tm_account_id} to queue {self.queue.queue_id}."
            )
            return True
        else:
            logging.warning(
                f"Player {player.tm_account_id} attempted to join queue {self.queue.queue_id} they were already in."
            )
            return False

    def remove_player(self, player: PlayerProfile) -> None:
        """Remove a player from the queue.

        Args:
            player (PlayerProfile): The player to remove from the queue.
        """
        self.player_parties = [p for p in self.player_parties if player not in p.players()]
        logging.info(
            f"Removed player {player.tm_account_id} from queue {self.queue.queue_id}."
        )

    def add_party(self, party: ActiveParty) -> bool:
        """Adds a party to the active queue.

        Args:
            party (ActiveParty): The party to add to the queue.

        Returns:
            bool: True if party was added to queue, False if they were already in the queue.
        """
        team = QueuedTeam.new_joined_team(
            party.requester, party.accepter, self.queue.queue_id
        )
        if not self.is_player_queued(party.requester) and not self.is_player_queued(party.accepter):
            self.player_parties.append(team)
            logging.info(
                f"Added players {team.players()} to queue {self.queue.queue_id}."
            )
            return True
        else:
            logging.warning(
                f"Players {team.players()} attempted to join queue {self.queue.queue_id} they were already in."
            )
            return False
        
    def remove_party(self, party: ActiveParty) -> None:
        """Remove a party from the queue.

        Args:
            party (ActiveParty): The party to remove from the queue.
        """
        self.remove_player(party.accepter)
        self.remove_player(party.requester)

    def should_generate_match(self) -> bool:
        """Determines if a match should be generated from the current queue

        Returns:
            bool: True if a match should be generated, False otherwise.
        """
        if self.queue.type == QueueType.Queue1v1v1v1:
            logging.debug(
                f"Checking if should generate match for {self.queue.queue_id} length {len(self.player_parties)}."
            )
            if len(self.player_parties) >= NUM_1v1v1v1_PLAYERS:
                return True
        elif self.queue.type == QueueType.Queue2v2:
            logging.debug(
                f"Checking if should generate match for {self.queue.queue_id} length {len(self.player_parties)}."
            )
            total_players = 0
            for party in self.player_parties:
                total_players += len(party.players())
            return total_players >= 4
        elif self.queue.type == QueueType.QueueSoloTest:
            logging.debug(
                f"Checking if should generate match for {self.queue.queue_id} length {len(self.player_parties)}."
            )
            if len(self.player_parties) >= 1:
                return True
        elif self.queue.type == QueueType.QueueLSC:
            logging.debug(
                f"Checking if should generate match for {self.queue.queue_id} length {len(self.player_parties)}."
            )
            if len(self.player_parties) >= NUM_LSC_PLAYERS:
                return True
        
        return False

    def generate_match(self, bot_match_id: int) -> ActiveMatch:
        """Generates a match with the given bot match ID. 

        Args:
            bot_match_id (int): The ID to give to the current match (used in its event name)

        Returns:
            ActiveMatch: The active match created as an event.
        """
        if self.queue.type == QueueType.Queue1v1v1v1:
            players_in_match = self.player_parties[:NUM_1v1v1v1_PLAYERS]
            players_in_match = [p.players()[0] for p in players_in_match]
            return ActiveMatch.create_1v1v1v1(self.queue, bot_match_id, players_in_match)
        
        elif self.queue.type == QueueType.Queue2v2:
            solo_players: List[PlayerProfile] = []
            teams_in_match: List[Team2v2] = []

            for party in self.player_parties:
                # If this is a team, add it to teams in match
                if len(party.players()) == 2:
                    team_name = "Blue" if len(teams_in_match) == 0 else "Red"
                    teams_in_match.append(Team2v2(team_name, party.players()[0], party.players()[1]))

                # Otherwise add it to solo players
                if len(party.players()) == 1:
                    solo_players.append(party.players()[0])

                # If 2 solo players, make them a team
                if len(solo_players) == 2:
                    team_name = "Blue" if len(teams_in_match) == 0 else "Red"
                    teams_in_match.append(Team2v2(team_name, solo_players[0], solo_players[1]))
                    solo_players = []

                # if two teams in match, break
                if len(teams_in_match) == 2:
                    break

            teams = Teams2v2(teams_in_match[0], teams_in_match[1])
            return ActiveMatch.create_2v2(self.queue, bot_match_id, teams)
        
        elif self.queue.type == QueueType.QueueSoloTest:
            player_in_match = self.player_parties[0].players()[0]
            return ActiveMatch.create_solo(self.queue, bot_match_id, player_in_match)
        
        elif self.queue.type == QueueType.QueueLSC:
            players_in_match = self.player_parties[:NUM_LSC_PLAYERS]
            players_in_match = [p.players()[0] for p in players_in_match]
            return ActiveMatch.create_lsc(self.queue, bot_match_id, players_in_match)
        
        else:
            raise Exception("Invalid queue type")