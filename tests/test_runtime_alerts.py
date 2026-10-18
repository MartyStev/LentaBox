import unittest
from unittest.mock import AsyncMock, patch

import httpx

from core import alerts, embeddings, runtime


class RuntimeTests(unittest.TestCase):
    def test_threshold_is_validated(self):
        self.assertEqual(runtime.parse("cluster_threshold", "0,9"), 0.9)
        with self.assertRaises(ValueError):
            runtime.parse("cluster_threshold", "1.5")
        with self.assertRaises(ValueError):
            runtime.parse("nope", "1")

    def test_bool_setting_and_load_skips_garbage(self):
        self.assertIs(runtime.parse("autosync", "вкл"), True)
        runtime.load({"fuzzy_threshold": "garbage", "autosync": "on"})
        self.assertIs(runtime.get("autosync"), True)
        runtime.load({"autosync": "off"})


class AlerterTests(unittest.IsolatedAsyncioTestCase):
    async def test_cooldown_suppresses_repeats(self):
        now = [0.0]
        client = AsyncMock()
        alerter = alerts.Alerter(client, 2, cooldown=100, clock=lambda: now[0])
        self.assertTrue(await alerter.notify("k", "text"))
        now[0] = 50
        self.assertFalse(await alerter.notify("k", "text"))
        self.assertTrue(await alerter.notify("other", "text"))
        now[0] = 150
        self.assertTrue(await alerter.notify("k", "text"))
        self.assertEqual(client.send_message.await_count, 3)

    async def test_send_failure_does_not_raise(self):
        client = AsyncMock()
        client.send_message.side_effect = RuntimeError("flood")
        self.assertFalse(await alerts.Alerter(client, 2).notify("k", "t"))


class EmbeddingRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_transport_errors_then_succeeds(self):
        calls = []

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, url, json):
                calls.append(1)
                if len(calls) < 3:
                    raise httpx.ConnectError("refused")
                response = httpx.Response(
                    200, json={"data": [{"embedding": [1.0]}]},
                    request=httpx.Request("POST", url),
                )
                return response

        with patch.object(embeddings.httpx, "AsyncClient", FakeClient), \
             patch.object(embeddings.asyncio, "sleep", new=AsyncMock()):
            self.assertEqual(await embeddings.embed("text"), [1.0])
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
