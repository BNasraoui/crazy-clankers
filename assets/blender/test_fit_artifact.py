"""The acceptance report must describe the delivered GLB, not a stale source mesh."""

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FitArtifactTests(unittest.TestCase):
    def test_exported_neutral_asset_passes_all_six_views(self):
        report = json.loads((ROOT / "assets/blender/reviews/v7-fit.json").read_text())
        self.assertIn(
            "asset_sha256", report, "fit must be remeasured from the exported GLB"
        )
        self.assertEqual(
            report["asset_sha256"],
            hashlib.sha256(
                (ROOT / "public/models/techbro-apose.glb").read_bytes()
            ).hexdigest(),
        )
        for kind, threshold in [("body", 0.9), ("head", 0.88)]:
            self.assertEqual(set(report[kind]), {"front", "right", "back"})
            self.assertGreaterEqual(min(report[kind].values()), threshold)


if __name__ == "__main__":
    unittest.main()
