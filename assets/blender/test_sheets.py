"""Numerical acceptance tests for fixed sheet registration and silhouette scoring."""

import unittest

import numpy as np
from PIL import Image

try:
    import sheets
except ImportError:
    sheets = None


class SheetTests(unittest.TestCase):
    def test_metric_registration_roundtrip_and_mirrored_profile(self):
        self.assertIsNotNone(sheets, "generic sheet calibration module is missing")
        c = sheets.Calibration(1.8, 20, 920, 300, 700)
        self.assertAlmostEqual(c.metres_per_pixel, 0.002)
        self.assertEqual(c.pixel_to_world(350, 420), (0.1, 1.0))
        self.assertEqual(c.world_to_pixel(0.1, 1.0), (350.0, 420.0))
        self.assertEqual(c.pixel_to_world(650, 420, side=True, sign=-1), (0.1, 1.0))

    def test_iou_penalizes_translation_and_missing_limbs(self):
        self.assertIsNotNone(sheets, "generic sheet calibration module is missing")
        a = np.zeros((20, 20), bool)
        a[2:12, 3:13] = True
        b = np.zeros_like(a)
        b[2:12, 8:18] = True
        self.assertAlmostEqual(sheets.iou(a, b), 1 / 3)
        self.assertEqual(sheets.iou(a, a), 1)
        self.assertEqual(sheets.iou(a, np.zeros_like(a)), 0)
        with self.assertRaises(ValueError):
            sheets.iou(np.zeros_like(a), np.zeros_like(a))
        with self.assertRaises(ValueError):
            sheets.iou(a, b[:10])

    def test_mask_removes_guides_and_keeps_enclosed_white(self):
        self.assertIsNotNone(sheets, "generic sheet calibration module is missing")
        a = np.full((80, 80, 3), 255, np.uint8)
        a[20, :] = 195
        a[30:65, 25:55] = 40
        a[35:60, 30:50] = 250
        m = sheets.silhouette(Image.fromarray(a))
        self.assertEqual(int(m.sum()), 35 * 30)
        self.assertTrue(m[40, 40])
        self.assertFalse(m[20, 5])

    def test_calibration_report_ties_landmarks_and_bounds_to_input_hashes(self):
        self.assertTrue(
            hasattr(sheets, "measure"), "calibration measurement report is missing"
        )
        result = sheets.measure("techbro")
        self.assertEqual(
            result["body"]["views"]["front"]["bounds_pixels"], [86, 21, 580, 857]
        )
        self.assertAlmostEqual(result["body"]["landmarks"]["crown"]["height_m"], 1.8)
        self.assertAlmostEqual(result["body"]["landmarks"]["soles"]["height_m"], 0)
        self.assertEqual(len(result["head"]["source_sha256"]), 64)
        self.assertIn("three_quarter", result["head"]["auxiliary_views"])


if __name__ == "__main__":
    unittest.main()
