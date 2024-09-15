import logging
from typing import List
from models.player_profile import PlayerProfile
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from models.match_queue import MatchQueue
from matchmaking.match_queues.enum import QueueType
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.constants import NUM_1v1v1v1_PLAYERS

class ActiveMatchQueue:
    """An active queue of players awaiting a match for the given MatchQueue.
    """
    def __init__(self, match_queue: MatchQueue):
        self.players: List[PlayerProfile] = []
        self.teams: List[Team2v2] = []
        self.queue = match_queue

    def add_player(self, player: PlayerProfile) -> bool:
        """Adds a player to the active queue.

        Args:
            player (PlayerProfile): _description_

        Returns:
            bool: True if player was added to queue, False if they were already in the queue. 
        """
        if player not in self.players:
            self.players.append(player)
            logging.info(f"Added player {player.tm_account_id} to queue {self.queue.queue_id}.")
            return True
        else:
            logging.warn(f"Player {player.tm_account_id} attempted to join queue {self.queue.queue_id} they were already in.")
            return False

    def remove_player(self, player: PlayerProfile | int | str) -> None:
        """Remove a player from the queue.

        Args:
            player (PlayerProfile | int | str): The player to remove from the queue. Can be a PlayerProfile object, a string representing the TM account ID, or an integer representing the Discord account ID.
        """        
        if isinstance(player, int):
            self.players = [p for p in self.players if p.discord_account_id != player]
            logging.info(f"Removed player {player} from queue {self.queue.queue_id}.")
        elif isinstance(player, str):
            self.players = [p for p in self.players if p.tm_account_id != player]
            logging.info(f"Removed player {player} from queue {self.queue.queue_id}.")
        else:
            self.players.remove(player)
            logging.info(f"Removed player {player.tm_account_id} from queue {self.queue.queue_id}.")

    def add_team(self, team: Team2v2) -> None:
        """Add a team to the queue.

        Args:
            team (Team2v2): The team to add to the queue
        """
        logging.info(f"Added team {team} to queue {self.queue.queue_id}.")
        self.teams.append(team)

    def remove_team(self, team: Team2v2) -> None:
        """Remove a team from the queue.

        Args:
            team (Team2v2): The team to remove from the queue.
        """
        self.teams.remove(team)
        logging.info(f"Removed team {team} from queue {self.queue.queue_id}.")

    def try_generate_match(self) -> ActiveMatch | None:
        """Generate a match if the current queue permits. 

        Returns:
            int | None: Return match ID if a match was generated, otherwise None
        """
        if self.queue.type == QueueType.Queue1v1v1v1.value:
            logging.debug(f"Checking if should generate match for {self.queue.queue_id} length {len(self.players)}.")
            if len(self.players) >= NUM_1v1v1v1_PLAYERS:
                players_in_match = self.players[:NUM_1v1v1v1_PLAYERS]
                return ActiveMatch.create_1v1v1v1(self.queue, players_in_match)
        elif self.queue.type == QueueType.Queue2v2.value:
            logging.debug(f"Checking if should generate match for {self.queue.queue_id} length {len(self.teams)}.")
            if len(self.teams) >= 2:
                teams_in_match = self.teams[:2]
                teams = Teams2v2(teams_in_match[0], teams_in_match[1])
                return ActiveMatch.create_2v2(self.queue, teams)
        else:
            return None
