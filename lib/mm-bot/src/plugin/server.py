import asyncio
import logging
import threading
from aws.dynamodb import DynamoDbManager
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from plugin.connection import PluginConnection
from plugin.event_processor import EventProcessor


class PluginServer:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(PluginServer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            self._thread = None
            self._loop = None
            self._server = None
            self._connected_clients: dict[str, PluginConnection] = {}
            self._ddb_manager = DynamoDbManager()
            self._mm_manager = get_matchmaking_manager_v2()
            self._event_processor = EventProcessor()
            logging.info("Instantiating plugin server.")

    def startup(self):
        self._stopped = False
        self._thread = threading.Thread(daemon=True, target=self._start_event_loops)
        self._thread.start()

    async def shutdown(self):
        for _, client in self._connected_clients.items():
            await client.try_send_error("Better Matchmaking server shutdown")

        if self._server:
            logging.info("Stopping plugin server listen server")
            self._server.close()

        if self._loop:
            logging.info("Stopping plugin server event loop")
            self._loop.stop()

        if self._thread:
            logging.info("Waiting for plugin server thread to exit")
            self._thread.join()

    def remove_player_from_queue(self, tm_account_id: str):
        try:
            profile = self._ddb_manager.query_player_profile_for_tm_account_id(
                tm_account_id
            )
            if profile:
                self._mm_manager.remove_player_from_all_active_queues(profile)
        except Exception:
            logging.error(f"Unable to remove player {tm_account_id} from queues")

    def _start_event_loops(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._loop.create_task(self._server_loop())
        self._loop.create_task(self._event_bus_loop())
        self._loop.run_forever()

    async def _event_bus_loop(self):
        logging.info("Starting plugin server event bus loop")
        while not self._stopped:
            try:
                await self._event_processor.loop(self._connected_clients)
            except Exception as e:
                logging.exception("Exception occurred in plugin event worker", e)
            finally:
                await asyncio.sleep(1)

    async def _server_loop(self):
        logging.info("Starting plugin server on 0.0.0.0:27990")
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
