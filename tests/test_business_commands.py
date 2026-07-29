import asyncio
import unittest

from handlers import native_features


class DummyMessage:
    text = "/ask@Chatrix_x_x_bot привет"
    caption = None


class BusinessCommandTest(unittest.TestCase):
    def test_business_command_is_dispatched(self):
        called = []
        original = native_features.BUSINESS_COMMANDS["ask"]

        async def fake_handler(message):
            called.append(message.text)

        try:
            native_features.BUSINESS_COMMANDS["ask"] = fake_handler
            handled = asyncio.run(native_features.dispatch_business_command(DummyMessage()))
        finally:
            native_features.BUSINESS_COMMANDS["ask"] = original

        self.assertTrue(handled)
        self.assertEqual(called, [DummyMessage.text])

    def test_unknown_business_command_is_not_swallowed(self):
        message = DummyMessage()
        message.text = "/unknown"
        self.assertFalse(asyncio.run(native_features.dispatch_business_command(message)))


if __name__ == "__main__":
    unittest.main()