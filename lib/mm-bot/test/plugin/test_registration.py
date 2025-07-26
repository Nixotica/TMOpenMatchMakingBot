# Test script to validate both registration and check registration implementation
import json
import unittest
from plugin.request_parser import RequestParser
from plugin.requests.register_account import RegisterAccountRequest
from plugin.requests.check_registration import CheckRegistrationRequest
from plugin.responses.register_account import RegisterAccountResponse
from plugin.responses.check_registration import CheckRegistrationResponse
from plugin.responses.error import ErrorResponse


class TestRegistrationRequests(unittest.TestCase):
    def setUp(self):
        self.request_parser = RequestParser()

    def test_register_account_request_creation(self):
        """Test creating a RegisterAccountRequest"""
        request = RegisterAccountRequest(
            "test-user", "testuser#1234", "550e8400-e29b-41d4-a716-446655440000"
        )

        self.assertEqual(request.identifier(), "test-user")
        self.assertEqual(request.discord_username, "testuser#1234")
        self.assertEqual(
            request.ubisoft_account_id, "550e8400-e29b-41d4-a716-446655440000"
        )
        self.assertEqual(request.name(), "RegisterAccount")

    def test_check_registration_request_creation(self):
        """Test creating a CheckRegistrationRequest"""
        request = CheckRegistrationRequest(
            "test-user", "550e8400-e29b-41d4-a716-446655440000"
        )

        self.assertEqual(request.identifier(), "test-user")
        self.assertEqual(
            request.ubisoft_account_id, "550e8400-e29b-41d4-a716-446655440000"
        )
        self.assertEqual(request.name(), "CheckRegistration")

    def test_register_account_request_parsing(self):
        """Test parsing a RegisterAccount request from JSON"""
        register_request = {
            "User": "550e8400-e29b-41d4-a716-446655440000",
            "Version": "1.0.0",
            "Command": "RegisterAccount",
            "Payload": {
                "DiscordUsername": "testuser#1234",
                "UbisoftAccountId": "550e8400-e29b-41d4-a716-446655440001",
            },
        }

        parsed_request = self.request_parser.from_buffer(json.dumps(register_request))

        self.assertIsInstance(parsed_request, RegisterAccountRequest)
        self.assertEqual(
            parsed_request.identifier(), "550e8400-e29b-41d4-a716-446655440000"
        )

        # Type assertion for attribute access
        if isinstance(parsed_request, RegisterAccountRequest):
            self.assertEqual(parsed_request.discord_username, "testuser#1234")
            self.assertEqual(
                parsed_request.ubisoft_account_id,
                "550e8400-e29b-41d4-a716-446655440001",
            )

    def test_check_registration_request_parsing(self):
        """Test parsing a CheckRegistration request from JSON"""
        check_request = {
            "User": "550e8400-e29b-41d4-a716-446655440000",
            "Version": "1.0.0",
            "Command": "CheckRegistration",
            "Payload": {"UbisoftAccountId": "550e8400-e29b-41d4-a716-446655440001"},
        }

        parsed_request = self.request_parser.from_buffer(json.dumps(check_request))

        self.assertIsInstance(parsed_request, CheckRegistrationRequest)
        self.assertEqual(
            parsed_request.identifier(), "550e8400-e29b-41d4-a716-446655440000"
        )

        # Type assertion for attribute access
        if isinstance(parsed_request, CheckRegistrationRequest):
            self.assertEqual(
                parsed_request.ubisoft_account_id,
                "550e8400-e29b-41d4-a716-446655440001",
            )

    def test_register_account_request_parsing_with_missing_payload(self):
        """Test parsing RegisterAccount request with missing payload fields"""
        register_request = {
            "User": "550e8400-e29b-41d4-a716-446655440000",
            "Version": "1.0.0",
            "Command": "RegisterAccount",
            "Payload": {},
        }

        parsed_request = self.request_parser.from_buffer(json.dumps(register_request))

        self.assertIsInstance(parsed_request, RegisterAccountRequest)

        # Type assertion for attribute access
        if isinstance(parsed_request, RegisterAccountRequest):
            self.assertEqual(parsed_request.discord_username, "")
            self.assertEqual(parsed_request.ubisoft_account_id, "")

    def test_check_registration_request_parsing_with_missing_payload(self):
        """Test parsing CheckRegistration request with missing payload fields"""
        check_request = {
            "User": "550e8400-e29b-41d4-a716-446655440000",
            "Version": "1.0.0",
            "Command": "CheckRegistration",
            "Payload": {},
        }

        parsed_request = self.request_parser.from_buffer(json.dumps(check_request))

        self.assertIsInstance(parsed_request, CheckRegistrationRequest)

        # Type assertion for attribute access
        if isinstance(parsed_request, CheckRegistrationRequest):
            self.assertEqual(parsed_request.ubisoft_account_id, "")


class TestDiscordUsernameValidation(unittest.TestCase):
    def setUp(self):
        # Mock all dependencies to avoid initialization errors
        import unittest.mock
        from plugin.response_builder import ResponseBuilder

        # Create patches for all dependencies
        self.mm_patcher = unittest.mock.patch(
            "plugin.response_builder.get_matchmaking_manager_v2"
        )
        self.ddb_patcher = unittest.mock.patch(
            "plugin.response_builder.DynamoDbManager"
        )
        self.s3_patcher = unittest.mock.patch("aws.s3.S3ClientManager")
        self.cmd_builder_patcher = unittest.mock.patch(
            "plugin.response_builder.CommandBuilder"
        )

        # Start all patches
        mock_mm = self.mm_patcher.start()
        mock_ddb = self.ddb_patcher.start()
        mock_s3 = self.s3_patcher.start()
        mock_cmd_builder = self.cmd_builder_patcher.start()

        # Configure mocks
        mock_mm.return_value = unittest.mock.MagicMock()
        mock_ddb.return_value = unittest.mock.MagicMock()
        mock_s3.return_value = unittest.mock.MagicMock()
        mock_cmd_builder.return_value = unittest.mock.MagicMock()

        self.response_builder = ResponseBuilder()

    def tearDown(self):
        # Stop all patches
        self.mm_patcher.stop()
        self.ddb_patcher.stop()
        self.s3_patcher.stop()
        self.cmd_builder_patcher.stop()

    def test_valid_old_format_username(self):
        """Test validation of old Discord username format (username#1234)"""
        self.assertTrue(
            self.response_builder._is_valid_discord_username("testuser#1234")
        )
        self.assertTrue(
            self.response_builder._is_valid_discord_username("User123#9999")
        )

    def test_valid_new_format_username(self):
        """Test validation of new Discord username format (@username)"""
        self.assertTrue(self.response_builder._is_valid_discord_username("@testuser"))
        self.assertTrue(self.response_builder._is_valid_discord_username("testuser123"))
        self.assertTrue(
            self.response_builder._is_valid_discord_username("user.name_123")
        )

    def test_invalid_username_formats(self):
        """Test rejection of invalid Discord username formats"""
        # Too short
        self.assertFalse(self.response_builder._is_valid_discord_username("ab"))
        # Too long
        self.assertFalse(self.response_builder._is_valid_discord_username("a" * 33))
        # Invalid old format (wrong discriminator length)
        self.assertFalse(self.response_builder._is_valid_discord_username("user#123"))
        self.assertFalse(self.response_builder._is_valid_discord_username("user#12345"))
        # Invalid characters
        self.assertFalse(self.response_builder._is_valid_discord_username("user@name"))
        self.assertFalse(self.response_builder._is_valid_discord_username("user name"))


class TestRegistrationResponses(unittest.TestCase):
    def test_register_account_success_response(self):
        """Test creating a successful RegisterAccountResponse"""
        response = RegisterAccountResponse()

        self.assertEqual(response.name(), "RegisterAccountResponse")
        self.assertEqual(response.status_code(), 200)

        payload = response.payload()
        self.assertTrue(payload["Success"])
        # RegisterAccountResponse only contains Success field, no Message

    def test_register_account_error_response(self):
        """Test creating an error response for registration failure"""
        response = ErrorResponse("Registration failed")

        self.assertEqual(response.name(), "ErrorResponse")
        self.assertEqual(response.status_code(), 500)

        payload = response.payload()
        self.assertEqual(payload["ErrorMessage"], "Registration failed")
        self.assertFalse(payload["KeepAlive"])

    def test_check_registration_response_registered(self):
        """Test CheckRegistrationResponse for registered account"""
        response = CheckRegistrationResponse(True)

        self.assertEqual(response.name(), "CheckRegistrationResponse")
        self.assertEqual(response.status_code(), 200)

        payload = response.payload()
        self.assertTrue(payload["IsRegistered"])

    def test_check_registration_response_not_registered(self):
        """Test CheckRegistrationResponse for unregistered account"""
        response = CheckRegistrationResponse(False)

        self.assertEqual(response.name(), "CheckRegistrationResponse")
        self.assertEqual(response.status_code(), 200)

        payload = response.payload()
        self.assertFalse(payload["IsRegistered"])

    def test_response_encoding(self):
        """Test that responses can be properly encoded to JSON"""
        success_response = RegisterAccountResponse()
        error_response = ErrorResponse("Registration failed")
        check_response = CheckRegistrationResponse(True)

        # Test that encoding doesn't raise exceptions
        success_encoded = success_response.encode()
        error_encoded = error_response.encode()
        check_encoded = check_response.encode()

        # Verify the encoded data can be parsed back
        success_data = json.loads(success_encoded.decode())
        error_data = json.loads(error_encoded.decode())
        check_data = json.loads(check_encoded.decode())

        self.assertEqual(success_data["Command"], "RegisterAccountResponse")
        self.assertEqual(success_data["StatusCode"], 200)
        self.assertTrue(success_data["Payload"]["Success"])

        self.assertEqual(error_data["Command"], "ErrorResponse")
        self.assertEqual(error_data["StatusCode"], 500)
        self.assertEqual(error_data["Payload"]["ErrorMessage"], "Registration failed")

        self.assertEqual(check_data["Command"], "CheckRegistrationResponse")
        self.assertEqual(check_data["StatusCode"], 200)
        self.assertTrue(check_data["Payload"]["IsRegistered"])


if __name__ == "__main__":
    unittest.main()
