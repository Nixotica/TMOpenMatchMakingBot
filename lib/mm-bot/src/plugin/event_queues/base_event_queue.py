import logging
from abc import abstractmethod
from aws.dynamodb import DynamoDbManager
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from matchmaking.mm_event_bus import MatchmakingManagerEventBus
from plugin.command_builder import CommandBuilder
from plugin.connection import PluginConnection


class BaseEventQueue:
    def __init__(self):
        self.command_builder = CommandBuilder()
        self.ddb_manager = DynamoDbManager()
        self.mm_manager = get_matchmaking_manager_v2()
        self.mm_event_bus = MatchmakingManagerEventBus()

    async def send_command(self, client: PluginConnection, response):
        try:
            if client:
                await client.send_command(response)
                return True
        except Exception as e:
            logging.exception(
                f"Failed trying to sending command to user: {client.identifier()}", e
            )
        return False

    @abstractmethod
    async def check(self, connections: dict[str, PluginConnection]):
        pass
