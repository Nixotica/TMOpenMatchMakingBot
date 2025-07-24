from matchmaking.mm_event_bus import EventType
from plugin.connection import PluginConnection
from plugin.event_queues.base_event_queue import BaseEventQueue


class LeftPartyEventQueue(BaseEventQueue):
    def __init__(self):
        super().__init__()
        self.queue = self.mm_event_bus.subscribe(EventType.LEAVE_PARTY)

    async def check(self, connections: dict[str, PluginConnection]) -> None:
        event = self.mm_event_bus.get_leave_party(self.queue)
        if event is not None:
            command = self.command_builder.build_remove_players_from_party(
                [event.initiator]
            )
            for player in event.receivers:
                client = connections.get(player.tm_account_id)
                if client:
                    await self.send_command(client, command)
