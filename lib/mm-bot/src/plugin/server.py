import asyncio
import logging
import threading
from plugin.connection import PluginConnection
from plugin.responses.base_response import BaseResponse

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
            self._connected_clients = {}
            
            logging.info(
                f"Instantiating plugin server."
            )

    def start_run_forever_in_thread(self):
        logging.info("Starting plugin server in a separate thread...")
        self._thread = threading.Thread(target=self._start_event_loop, daemon=True)
        self._thread.start()

    async def try_send_command(self, tm_account_id: str, response: BaseResponse):
        try:
            client: PluginConnection = self._connected_clients.get(tm_account_id)
            if client:
                await client.send_command(response)
                return True
        except Exception as e:
            logging.exception(f"Failed trying to sending command to user: {tm_account_id}", e)
        return False  

    def _start_event_loop(self):
        """Starts an event loop in the current thread to run async methods."""
        loop = asyncio.new_event_loop()  # Create a new event loop
        asyncio.set_event_loop(loop)  # Set this loop as the current event loop
        loop.run_until_complete(self._start_listen_server())  # Run the async method
        loop.run_forever()  # Keep the loop running

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

        # remove player from queue if they disconnect

        logging.info(f"Plugin connection from {writer.transport.get_extra_info('peername')} ({connection_id}) has been disconnected")


