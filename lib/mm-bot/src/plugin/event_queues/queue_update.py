from matchmaking.mm_event_bus import EventType
from plugin.connection import PluginConnection
from plugin.event_queues.base_event_queue import BaseEventQueue


class QueueUpdateEventQueue(BaseEventQueue):
    def __init__(self):
        super().__init__()
        self.queue = self.mm_event_bus.subscribe(EventType.QUEUE_UPDATE)

    async def check(self, connections: dict[str, PluginConnection]) -> None:
        event = self.mm_event_bus.get_new_queue_update(self.queue)
        if event is not None:
            queue = self.mm_manager.get_queue(event)
            if queue:
                queue_update_command = self.command_builder.build_queue_update(queue)
                for tm_account_id, _ in connections.items():
                    await self.send_command(tm_account_id, queue_update_command)
