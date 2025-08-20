import unittest
from unittest.mock import Mock, patch, AsyncMock
import discord
import pytest
from views.leaderboard import LeaderboardView
from models.player_profile import PlayerProfile


class TestLeaderboardView(unittest.TestCase):
    def setUp(self):
        self.mock_bot = Mock()
        self.leaderboard_id = "test_leaderboard"
        
    @pytest.mark.asyncio
    @patch('views.leaderboard.DynamoDbManager')
    async def test_see_my_position_player_not_registered(self, mock_ddb_manager_class):
        """Test that unregistered users get appropriate error message"""
        # Create view inside the test to avoid event loop issues
        view = LeaderboardView(self.mock_bot, self.leaderboard_id)
        
        # Setup mocks
        mock_ddb_manager = Mock()
        mock_ddb_manager_class.return_value = mock_ddb_manager
        mock_ddb_manager.query_player_profile_for_discord_account_id.return_value = None
        
        # Create mock interaction
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "testuser"
        
        # Create mock button
        mock_button = Mock()
        
        # Execute the method
        await view.see_my_position(mock_interaction, mock_button)
        
        # Verify the response
        mock_interaction.response.send_message.assert_called_once_with(
            "You have not registered your account yet.",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    @patch('views.leaderboard.DynamoDbManager')
    async def test_see_my_position_player_not_found_on_leaderboard(self, mock_ddb_manager_class):
        """Test that players not on leaderboard get appropriate message about playing matches"""
        # Create view inside the test to avoid event loop issues
        view = LeaderboardView(self.mock_bot, self.leaderboard_id)
        
        # Setup mocks
        mock_ddb_manager = Mock()
        mock_ddb_manager_class.return_value = mock_ddb_manager
        
        # Mock registered player profile
        player_profile = PlayerProfile(
            tm_account_id="test_tm_account",
            discord_account_id=12345,
            matches_played=0
        )
        mock_ddb_manager.query_player_profile_for_discord_account_id.return_value = player_profile
        
        # Mock empty result from get_nearby_players_by_elo (player not on leaderboard)
        mock_ddb_manager.get_nearby_players_by_elo.return_value = (0, [])
        
        # Create mock interaction
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "testuser"
        
        # Create mock button
        mock_button = Mock()
        
        # Mock the update_embed method
        view.update_embed = AsyncMock()
        
        # Execute the method
        await view.see_my_position(mock_interaction, mock_button)
        
        # Verify the new response (after the fix)
        mock_interaction.response.send_message.assert_called_once_with(
            "testuser not found on leaderboard, you must play at least one match in this queue!",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    @patch('views.leaderboard.DynamoDbManager')
    async def test_see_my_position_player_found_but_position_invalid(self, mock_ddb_manager_class):
        """Test that players found in list but with invalid position get appropriate message"""
        # Create view inside the test to avoid event loop issues
        view = LeaderboardView(self.mock_bot, self.leaderboard_id)
        
        # Setup mocks
        mock_ddb_manager = Mock()
        mock_ddb_manager_class.return_value = mock_ddb_manager
        
        # Mock registered player profile
        player_profile = PlayerProfile(
            tm_account_id="test_tm_account",
            discord_account_id=12345,
            matches_played=0
        )
        mock_ddb_manager.query_player_profile_for_discord_account_id.return_value = player_profile
        
        # Mock result with players but our player not found in the list
        from models.player_elo import PlayerElo
        other_player_elo = PlayerElo(
            tm_account_id="other_player",
            leaderboard_id=self.leaderboard_id,
            elo=1200
        )
        mock_ddb_manager.get_nearby_players_by_elo.return_value = (1, [other_player_elo])
        
        # Create mock interaction
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 12345
        mock_interaction.user.name = "testuser"
        
        # Create mock button
        mock_button = Mock()
        
        # Mock the update_embed method
        view.update_embed = AsyncMock()
        
        # Execute the method
        await view.see_my_position(mock_interaction, mock_button)
        
        # Verify the response - should show the same message as when player not found
        mock_interaction.response.send_message.assert_called_once_with(
            "testuser not found on leaderboard, you must play at least one match in this queue!",
            ephemeral=True,
        )


if __name__ == '__main__':
    unittest.main()