import hashlib
import hmac
import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp" / "backend"))
import main


class WebAppOriginsTest(unittest.TestCase):
    origins = [
        "https://your-body-pro.vercel.app",
        "https://app.pasekaproduction.ru:9443",
        "https://app.pasekaproduction.ru",
    ]

    def setUp(self):
        self.db = SimpleNamespace(
            is_subscription_active=AsyncMock(return_value=True),
            get_user_profile=AsyncMock(return_value={"onboarding_completed": True}),
        )
        for replacement in [patch.object(main, "db", self.db), patch.object(main, "BOT_TOKEN", "test-token"), patch.dict("os.environ", {"DEBUG": "false"})]:
            replacement.start()
            self.addCleanup(replacement.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        data = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 42})}
        secret = hmac.new(b"WebAppData", b"test-token", hashlib.sha256).digest()
        data["hash"] = hmac.new(secret, "\n".join(f"{k}={v}" for k, v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
        self.init_data = urlencode(data)

    def preflight(self, origin):
        return self.client.options("/api/me", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type,x-telegram-init-data",
        })

    def test_legacy_and_current_entrypoints_pass_real_cors_middleware(self):
        for origin in self.origins:
            with self.subTest(origin=origin):
                response = self.preflight(origin)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)
        self.db.is_subscription_active.assert_not_awaited()

    def test_unrelated_origins_are_rejected(self):
        for origin in ["https://unrelated.vercel.app", "https://your-body-pro.vercel.app.evil.example", "null"]:
            with self.subTest(origin=origin):
                response = self.preflight(origin)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("access-control-allow-origin", response.headers)

    def test_signed_paid_user_can_read_access_from_both_origins(self):
        for origin in self.origins:
            with self.subTest(origin=origin):
                response = self.client.get("/api/me", headers={"Origin": origin, "X-Telegram-Init-Data": self.init_data})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["subscription_active"])
                self.assertEqual(response.headers["access-control-allow-origin"], origin)

    def test_inactive_status_header_is_visible_to_cross_origin_clients(self):
        self.db.is_subscription_active.return_value = False
        response = self.client.get("/api/me", headers={"Origin": self.origins[0], "X-Telegram-Init-Data": self.init_data})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.headers["x-subscription-status"], "inactive")
        exposed = response.headers["access-control-expose-headers"].lower()
        self.assertIn("x-subscription-status", exposed)

    def test_allowing_legacy_origin_does_not_bypass_authentication(self):
        for init_data in ["", "invalid-data"]:
            with self.subTest(init_data=init_data):
                response = self.client.get("/api/me", headers={"Origin": self.origins[0], "X-Telegram-Init-Data": init_data})
                self.assertEqual(response.status_code, 401)
        self.db.is_subscription_active.assert_not_awaited()
