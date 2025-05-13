import json
import unittest
from plugin.constants import MIN_VERSION
from plugin.request_parser import RequestParser
from plugin.requests.invalid_version import InvalidVersionRequest


class TestMinVersionCheck(unittest.TestCase):
    def setUp(self):
        self.request_parser = RequestParser()

    def test_missing_version(self):
        buffer = json.dumps(
            {
                "User": "",
                "Command": "",
            }
        )

        response = self.request_parser.from_buffer(buffer)
        self.assertIsInstance(
            response,
            InvalidVersionRequest,
            "Requests with missing versions should be rejected",
        )

    def test_lower_than_required_version(self):
        buffer = json.dumps({"User": "", "Command": "", "Version": "0.1.2"})

        response = self.request_parser.from_buffer(buffer)
        self.assertIsInstance(
            response,
            InvalidVersionRequest,
            "Request version 0.1.2 is not in " + MIN_VERSION,
        )
