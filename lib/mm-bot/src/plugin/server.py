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
            self._connected_clients = {}
            self._command_builder = CommandBuilder()
            self._ddb_manager = DynamoDbManager()
            self._mm_manager = get_matchmaking_manager_v2()
            self._mm_event_bus = MatchmakingManagerEventBus()
            self._match_ready_queue = self._mm_event_bus.subscribe(EventType.NEW_ACTIVE_MATCH)
            self._match_complete_queue = self._mm_event_bus.subscribe(EventType.NEW_COMPLETED_MATCH)

            logging.info(
                f"Instantiating plugin server."
            )

    def start_run_forever_in_thread(self):
        logging.info("Starting plugin server in a separate thread...")
        self._thread = threading.Thread(target=self._start_event_loop, daemon=True)
        self._thread.start()

        logging.info("Starting plugin event bus worker in a separate thread...")
        self._event_thread = threading.Thread(target=self._start_event_worker_loop, daemon=True)
        self._event_thread.start()

    async def try_send_command(self, tm_account_id: str, response: BaseResponse):
        try:
            client: PluginConnection = self._connected_clients.get(tm_account_id)
            if client:
                await client.send_command(response)
                return True
        except Exception as e:
            logging.exception(f"Failed trying to sending command to user: {tm_account_id}", e)
        return False  
    
    def _start_event_worker_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._start_event_worker())
        loop.run_forever()

    async def _start_event_worker(self):
        while True:
            completed_match = self._mm_event_bus.get_new_completed_match(
                self._match_complete_queue
            )
            if completed_match is not None:
                logging.info(f"Sending Match Completed request to players connected via plugin for match: {completed_match.active_match.match_id}")
                completed_match_command = self._command_builder.build_match_results(completed_match)
                for player in completed_match.active_match.participants():
                    await self.try_send_command(player.tm_account_id, completed_match_command)

            new_match = self._mm_event_bus.get_new_active_match(
                self._match_ready_queue
            )
            if new_match is not None:
                logging.info(f"Sending Match Ready request to players connected via plugin for match: {new_match.match_id}")
                new_match_command = self._command_builder.build_match_ready(new_match)
                for player in new_match.participants():
                    await self.try_send_command(player.tm_account_id, new_match_command)

    def _start_event_loop(self):
        """Starts an event loop in the current thread to run async methods."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._start_listen_server())
        loop.run_forever()

    async def _start_listen_server(self):
        logging.info(f"Plugin Server is listening on 0.0.0.0:27990")
        self._server = await asyncio.start_server(self._handle_connection, "0.0.0.0", 27990)
        async with self._server:
            await self._server.serve_forever()

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        logging.info(f"A new plugin connection from {writer.transport.get_extra_info('peername')} has been established")
        
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
                self._connected_clients[connection_id] = connection

        if connection_id and self._connected_clients.get(connection_id):
            del self._connected_clients[connection_id]
            self.remove_player_from_queue(connection_id)

        logging.info(f"Plugin connection from {writer.transport.get_extra_info('peername')} ({connection_id}) has been disconnected")

    def remove_player_from_queue(self, tm_account_id: str):
        profile = self._ddb_manager.query_player_profile_for_tm_account_id(tm_account_id)
        if profile:
            self._mm_manager.remove_player_from_all_active_queues(profile)