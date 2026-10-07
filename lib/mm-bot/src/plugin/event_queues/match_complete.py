import logging
from matchmaking.mm_event_bus import EventType
from plugin.connection import PluginConnection
from plugin.event_queues.base_event_queue import BaseEventQueue


class MatchCompleteEventQueue(BaseEventQueue):
    def __init__(self):
        super().__init__()
        self.queue = self.mm_event_bus.subscribe(EventType.NEW_COMPLETED_MATCH)

    async def check(self, connections: dict[str, PluginConnection]) -> None:
        event = self.mm_event_bus.get_new_completed_match(self.queue)
        # The plugin tracks matches against the queue it joined, so it isn't told about scrims
        if event is not None and not event.active_match.match_queue.is_scrim:
            logging.info(
                f"Sending Match Completed request to plugins for match {event.active_match.match_id}"
            )
            completed_match_command = self.command_builder.build_match_results(event)
            for player in event.active_match.participants():
                client = connections.get(player.tm_account_id)
                if client:
                    await self.send_command(client, completed_match_command)
