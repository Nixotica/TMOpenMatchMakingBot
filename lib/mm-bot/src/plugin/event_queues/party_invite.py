from matchmaking.mm_event_bus import EventType
from plugin.connection import PluginConnection
from plugin.event_queues.base_event_queue import BaseEventQueue


class PartyInviteEventQueue(BaseEventQueue):
    def __init__(self):
        super().__init__()
        self.queue = self.mm_event_bus.subscribe(EventType.NEW_PARTY_REQUEST)

    async def check(self, connections: dict[str, PluginConnection]) -> None:
        event = self.mm_event_bus.get_new_party_request(self.queue)
        if event is not None:
            command = self.command_builder.build_party_invitation([event.initiator])
            for player in event.receivers:
                client = connections.get(player.tm_account_id)
                if client:
                    await self.send_command(client, command)
