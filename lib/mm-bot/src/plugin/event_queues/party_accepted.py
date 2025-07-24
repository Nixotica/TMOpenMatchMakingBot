from matchmaking.mm_event_bus import EventType
from plugin.connection import PluginConnection
from plugin.event_queues.base_event_queue import BaseEventQueue


class PartyAcceptedEventQueue(BaseEventQueue):
    def __init__(self):
        super().__init__()
        self.queue = self.mm_event_bus.subscribe(EventType.PARTY_REQUEST_ACCEPTED)

    async def check(self, connections: dict[str, PluginConnection]) -> None:
        event = self.mm_event_bus.get_party_request_accepted(self.queue)
        if event is not None:
            command = self.command_builder.build_add_players_to_party([event.initiator])
            for player in event.receivers:
                client = connections.get(player.tm_account_id)
                if client:
                    await self.send_command(client, command)
