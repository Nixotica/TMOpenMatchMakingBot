from typing import List
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.completed_match import CompletedMatch


class MatchStatusDistributer:
    """
    Distributes updated match statuses (new, completed) to concerned parties separately.
    """

    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(MatchStatusDistributer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):  # Avoid re-initializing the instance
            self.new_active_for_queue_view: List[ActiveMatch] = []
            self.new_completed_for_queue_view: List[CompletedMatch] = []

    def add_new_active_match(self, match: ActiveMatch) -> None:
        """Adds a new active match for all concerned parties to consume.

        Args:
            match (ActiveMatch): The active match to distribute.
        """
        self.new_active_for_queue_view.append(match)

    def add_new_completed_match(self, match: CompletedMatch) -> None:
        """Adds a new completed match for all concerned parties to consume.

        Args:
            match (CompletedMatch): The completed match to distribute.
        """
        self.new_completed_for_queue_view.append(match)

    def get_new_active_matches_for_queue_view(self, queue_id: str) -> List[ActiveMatch]:
        """Returns the new active matches for a given queue view and removes them from the list.

        Returns:
            List[ActiveMatch]: The new active matches for the given queue.
        """
        matches_to_return = []

        for match in self.new_active_for_queue_view:
            if match.match_queue.queue_id == queue_id:
                matches_to_return.append(match)
                self.new_active_for_queue_view.remove(match)

        return matches_to_return

    def get_new_completed_matches_for_queue_view(
        self, queue_id: str
    ) -> List[CompletedMatch]:
        """Returns the new completed matches for a given queue view and removes them from the list.

        Returns:
            List[CompletedMatch]: The new completed matches.
        """
        matches_to_return = []

        for match in self.new_completed_for_queue_view:
            if match.active_match.match_queue.queue_id == queue_id:
                matches_to_return.append(match)
                self.new_completed_for_queue_view.remove(match)

        return matches_to_return
