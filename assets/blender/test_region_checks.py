"""Synthetic masks establish metric semantics independently of character geometry."""
import unittest
import numpy as np
import sheets as S

class RegionChecks(unittest.TestCase):
    def test_region_iou_detects_internal_boundary_move(self):
        a = np.array([[1, 1, 2], [1, 2, 2]])
        b = np.array([[1, 2, 2], [1, 2, 2]])
        self.assertTrue(hasattr(S, 'region_iou'), 'region IoU missing')
        self.assertEqual(S.region_iou(a, b, ['hair', 'skin']), {'hair': 2/3, 'skin': 3/4})

    def test_shadow_islands_and_internal_edge(self):
        face = np.ones((7, 7), bool)
        shadow = np.zeros_like(face)
        shadow[1:3, 1:3] = True
        shadow[4, 4] = True
        self.assertTrue(hasattr(S, 'shadow_cleanliness'), 'shadow metric missing')
        result = S.shadow_cleanliness(shadow, face)
        self.assertEqual(result['islands'], 2)
        self.assertEqual(result['edge_pixels'], 12)
        self.assertEqual(S.shadow_cleanliness(face, face)['edge_pixels'], 0)

    def test_diagonal_shadow_is_connected(self):
        self.assertEqual(S.shadow_cleanliness(np.eye(3,dtype=bool), np.ones((3,3),bool))["islands"], 1)

    def test_region_segmentation_ignores_background(self):
        self.assertTrue(hasattr(S, 'segment_regions'), 'region segmentation missing')
        pixels = np.array([[[90,60,40], [240,180,130], [255,255,255]]], dtype=np.uint8)
        cfg = {'hair': {'colours': [[90,60,40]]}, 'skin': {'colours': [[240,180,130]]}}
        labels = S.segment_regions(pixels, np.array([[True,True,False]]), cfg)
        np.testing.assert_array_equal(labels, [[1,2,0]])

if __name__ == '__main__': unittest.main()
