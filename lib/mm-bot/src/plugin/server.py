import asyncio
import logging
import threading
from aws.dynamodb import DynamoDbManager
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from matchmaking.mm_event_bus import EventType, MatchmakingManagerEventBus
from plugin.connection import PluginConnection
from plugin.responses.base_response import BaseResponse
from plugin.command_builder import CommandBuilder


class PluginServer:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(PluginServer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            self._server = None
            self._thread = None
            self._event_thread = None
            self._connected_clients: dict[str, PluginConnection] = {}
            self._command_builder = CommandBuilder()
            self._ddb_manager = DynamoDbManager()
            self._mm_manager = get_matchmaking_manager_v2()
            self._mm_event_bus = MatchmakingManagerEventBus()
            self._match_ready_queue = self._mm_event_bus.subscribe(
                EventType.NEW_ACTIVE_MATCH
            )
            self._match_complete_queue = self._mm_event_bus.subscribe(
                EventType.NEW_COMPLETED_MATCH
            )
            self._queue_update_queue = self._mm_event_bus.subscribe(
                EventType.QUEUE_UPDATE
            )
            self._left_queue_queue = self._mm_event_bus.subscribe(EventType.LEFT_QUEUE)

            logging.info("Instantiating plugin server.")

    def start_run_forever_in_thread(self):
        logging.info("Starting plugin server in a separate thread...")
        self._thread = threading.Thread(target=self._start_event_loop, daemon=True)
        self._thread.start()

        logging.info("Starting plugin event bus worker in a separate thread...")
        self._event_thread = threading.Thread(
            target=self._start_event_worker_loop, daemon=True
        )
        self._event_thread.start()

    async def notify_shutdown(self):
        for _, client in self._connected_clients.items():
            await client.try_send_error("Better Matchmaking server shutdown")

    async def try_send_command(self, tm_account_id: str, response: BaseResponse):
        try:
            client: PluginConnection = self._connected_clients.get(tm_account_id)
            if client:
                await client.send_command(response)
                return True
        except Exception as e:
            logging.exception(
                f"Failed trying to sending command to user: {tm_account_id}", e
            )
        return False

    def _start_event_worker_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._start_event_worker())
        loop.run_forever()

    async def _start_event_worker(self):
        while True:
            try:
                completed_match = self._mm_event_bus.get_new_completed_match(
                    self._match_complete_queue
                )
                if completed_match is not None:
                    logging.info(
                        f"Sending Match Completed request to plugins for match {completed_match.active_match.match_id}"
                    )
                    completed_match_command = self._command_builder.build_match_results(
                        completed_match
                    )
                    for player in completed_match.active_match.participants():
                        await self.try_send_command(
                            player.tm_account_id, completed_match_command
                        )

                new_match = self._mm_event_bus.get_new_active_match(
                    self._match_ready_queue
                )
                if new_match is not None:
                    logging.info(
                        f"Sending Match Ready request to plugins for match {new_match.match_id}"
                    )
                    new_match_command = self._command_builder.build_match_ready(
                        new_match
                    )
                    for player in new_match.participants():
                        await self.try_send_command(
                            player.tm_account_id, new_match_command
                        )

                left_queue = self._mm_event_bus.get_new_left_queue(
                    self._left_queue_queue
                )
                if left_queue is not None:
                    left_queue_command = self._command_builder.build_leave_queue()
                    for player in left_queue:
                        await self.try_send_command(
                            player.tm_account_id, left_queue_command
                        )

                queue_update = self._mm_event_bus.get_new_queue_update(
                    self._queue_update_queue
                )
                if queue_update is not None:
                    queue = self._mm_manager.get_queue(queue_update)
                    if queue:
                        queue_update_command = self._command_builder.build_queue_update(
                            queue
                        )
                        for tm_account_id, _ in self._connected_clients.items():
                            await self.try_send_command(
                                tm_account_id, queue_update_command
                            )
            except Exception as e:
                logging.exception("Exception occurred in plugin event worker", e)
            finally:
                await asyncio.sleep(1)

    def _start_event_loop(self):
        """Starts an event loop in the current thread to run async methods."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._start_listen_server())
        loop.run_forever()

    async def _start_listen_server(self):
        logging.info("Plugin Server is listening on 0.0.0.0:27990")
        self._server = await asyncio.start_server(
            self._handle_connection, "0.0.0.0", 27990
        )
        async with self._server:
            await self._server.serve_forever()

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        peer_info = writer.transport.get_extra_info("peername")
        connection = PluginConnection(reader, writer)

        connection_id = None
        while True:
            close_connection = await connection.read_command()
            if close_connection:
                writer.close()
                await writer.wait_closed()
                break

            connection_id = connection.identifier()
            if self._connected_clients.get(connection_id) is None:
                logging.info(
                    f"A new plugin connection from {peer_info} has been established"
                )
                self._connected_clients[connection_id] = connection

        if connection_id and self._connected_clients.get(connection_id):
            del self._connected_clients[connection_id]
            self.remove_player_from_queue(connection_id)
            logging.info(
                f"Plugin connection from {peer_info} ({connection_id}) has been disconnected"
            )

    def remove_player_from_queue(self, tm_account_id: str):
        try:
            profile = self._ddb_manager.query_player_profile_for_tm_account_id(
                tm_account_id
            )
            if profile:
                self._mm_manager.remove_player_from_all_active_queues(profile)
        except Exception:
            logging.error(f"Unable to remove player {tm_account_id} from queues")
