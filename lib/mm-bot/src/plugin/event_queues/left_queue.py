from matchmaking.mm_event_bus import EventType
from plugin.connection import PluginConnection
from plugin.event_queues.base_event_queue import BaseEventQueue


class LeftQueueEventQueue(BaseEventQueue):
    def __init__(self):
        super().__init__()
        self.queue = self.mm_event_bus.subscribe(EventType.LEFT_QUEUE)

    async def check(self, connections: dict[str, PluginConnection]) -> None:
        event = self.mm_event_bus.get_new_left_queue(self.queue)
        if event is not None:
            command = self.command_builder.build_leave_queue()
            for player in event:
                await self.send_command(player.tm_account_id, command)
