import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp" / "backend"))

from main import ACHIEVEMENTS_CATALOG  # noqa: E402


class AchievementsCatalogTest(unittest.TestCase):
    def test_catalog_can_be_encoded_as_json(self):
        payload = json.dumps(
            {"achievements": ACHIEVEMENTS_CATALOG},
            ensure_ascii=False,
        ).encode("utf-8")

        self.assertNotIn(b"\\ud", payload)
        self.assertGreater(len(payload), 100)

    def test_badges_stay_compact_for_mobile_ui(self):
        for item in ACHIEVEMENTS_CATALOG:
            self.assertLessEqual(len(item["icon"]), 2, item["id"])


if __name__ == "__main__":
    unittest.main()
