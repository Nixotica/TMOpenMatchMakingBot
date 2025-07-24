from plugin.connection import PluginConnection
from plugin.event_queues.base_event_queue import BaseEventQueue
from plugin.event_queues.left_party import LeftPartyEventQueue
from plugin.event_queues.left_queue import LeftQueueEventQueue
from plugin.event_queues.match_complete import MatchCompleteEventQueue
from plugin.event_queues.match_ready import MatchReadyEventQueue
from plugin.event_queues.party_accepted import PartyAcceptedEventQueue
from plugin.event_queues.party_invite import PartyInviteEventQueue
from plugin.event_queues.queue_update import QueueUpdateEventQueue


class EventProcessor:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(EventProcessor, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            self._event_queues: list[BaseEventQueue] = [
                LeftPartyEventQueue(),
                LeftQueueEventQueue(),
                MatchCompleteEventQueue(),
                MatchReadyEventQueue(),
                QueueUpdateEventQueue(),
                PartyAcceptedEventQueue(),
                PartyInviteEventQueue(),
            ]

    async def loop(self, connections: dict[str, PluginConnection]) -> None:
        for event_queue in self._event_queues:
            event_queue.check(connections)
