import logging
from matchmaking.mm_event_bus import EventType
from plugin.connection import PluginConnection
from plugin.event_queues.base_event_queue import BaseEventQueue


class MatchReadyEventQueue(BaseEventQueue):
    def __init__(self):
        super().__init__()
        self.queue = self.mm_event_bus.subscribe(EventType.NEW_ACTIVE_MATCH)

    async def check(self, connections: dict[str, PluginConnection]) -> None:
        event = self.mm_event_bus.get_new_active_match(self.queue)
        if event is not None:
            logging.info(
                f"Sending Match Ready request to plugins for match {event.match_id}"
            )
            command = self.command_builder.build_match_ready(event)
            for player in event.participants():
                client = connections.get(player.tm_account_id)
                if client:
                    logging.info(
                        "Sending match ready command to %s", client.identifier()
                    )
                    await self.send_command(client, command)

            self.mm_event_bus.add_queue_update(event.match_queue.queue_id)
