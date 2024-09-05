from typing import List
from models.player_profile import PlayerProfile
from models.match_queue import MatchQueue
from matchmaking.match_queues.enum import QueueType

class ActiveMatchQueue:
    def __init__(self):
        self.players: List[PlayerProfile] = []
        self.queue: MatchQueue

    def add_player(self, player: PlayerProfile) -> None:
        """Add a player to the queue. 

        Args:
            player (PlayerProfile): The player to add to the queue
        """
        self.players.append(player)

    def remove_player(self, player: PlayerProfile | int | str) -> None:
        """Remove a player from the queue.

        Args:
            player (PlayerProfile | int | str): The player to remove from the queue. Can be a PlayerProfile object, a string representing the TM account ID, or an integer representing the Discord account ID.
        """        
        if isinstance(player, int):
            self.players = [p for p in self.players if p.discord_account_id != player]
        elif isinstance(player, str):
            self.players = [p for p in self.players if p.tm_account_id != player]
        else:
            self.players.remove(player)

    def try_generate_match(self) -> int | None:
        """Generate a match if the current queue permits. 

        Returns:
            int | None: Return match ID if a match was generated, otherwise None
        """
        if self.queue.type == QueueType.Queue1v1v1v1 and len(self.players) >= 4:
            return self.generate_match(QueueType.Queue1v1v1v1)
        elif self.queue.type == QueueType.Queue2v2:
            return False # TODO - need to check if the players in the queue are "partied"
        else:
            return False
        
    def generate_match(self, queue_type: QueueType) -> int:
        """Generate a match from the current queue. 

        Returns:
            int: The match ID.
        """
        