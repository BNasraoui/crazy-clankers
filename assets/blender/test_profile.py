import unittest

import head_shape


class ProfileTests(unittest.TestCase):
    def test_measured_profile_interpolation_preserves_landmarks_without_overshoot(self):
        self.assertTrue(
            hasattr(head_shape, "interpolate_sections"),
            "shared measured profile interpolation is missing",
        )
        rows = [(0, 2, 4), (1, 3, 6), (2, 2, 8), (3, 2, 10)]
        for y in [0, 1, 2, 3]:
            self.assertEqual(
                head_shape.interpolate_sections(rows, y), tuple(rows[y][1:])
            )
        for i in range(301):
            a, b = head_shape.interpolate_sections(rows, i / 100)
            self.assertTrue(2 <= a <= 3)
            self.assertAlmostEqual(b, 4 + i / 50)
        self.assertEqual(head_shape.interpolate_sections(rows, -10), (2, 4))
        self.assertEqual(head_shape.interpolate_sections(rows, 10), (2, 10))


if __name__ == "__main__":
    unittest.main()
