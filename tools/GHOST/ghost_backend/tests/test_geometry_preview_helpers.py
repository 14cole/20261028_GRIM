"""Preview screen-space overlay regression tests."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghost_backend.geometry.preview import select_normal_samples, visible_segment_midpoint


class NormalSampleTests(unittest.TestCase):
    def test_dense_neighbors_are_thinned_and_selected_row_has_priority(self):
        candidates = [{"midpoint": (x, y), "row": i, "priority": 2}
                      for i, (x, y) in enumerate([(0, 0), (0, 1), (10, 0), (40, 0)])]
        candidates[1]["priority"] = 0
        result = select_normal_samples(candidates)
        self.assertEqual([item["row"] for item in result], [1, 3])

    def test_reversing_input_keeps_same_arrow_anchors(self):
        candidates = [{"midpoint": (x, 0), "row": 0} for x in (0, 20, 40, 60)]
        first = select_normal_samples(candidates)
        second = select_normal_samples(reversed(candidates))
        self.assertEqual(first, second)

    def test_viewport_excludes_nonfinite_and_offscreen_samples(self):
        candidates = [{"midpoint": point} for point in ((0, 0), (50, 50), (100, 50), (math.nan, 0))]
        self.assertEqual(select_normal_samples(candidates, bounds=(10, 10, 90, 90)), [candidates[1]])

    def test_arrow_footprints_do_not_overlap_even_when_anchors_are_spaced(self):
        first = {"midpoint": (0, 0), "footprint": (-5, -5, 30, 5)}
        second = {"midpoint": (40, 0), "footprint": (25, -5, 50, 5)}
        self.assertEqual(select_normal_samples([first, second]), [first])



class VisibleSegmentTests(unittest.TestCase):
    def test_long_segment_keeps_an_anchor_in_zoomed_view(self):
        self.assertEqual(visible_segment_midpoint((-100, 5), (1000, 5), (0, 0, 10, 10)), (5, 5))

    def test_clipped_diagonal_anchor(self):
        self.assertEqual(visible_segment_midpoint((-10, -10), (10, 10), (0, 0, 10, 10)), (5, 5))

    def test_visible_segment_retains_midpoint(self):
        self.assertEqual(visible_segment_midpoint((2, 3), (8, 5), (0, 0, 10, 10)), (5, 4))

    def test_reversed_segment_has_identical_anchor(self):
        a, b, box = (-151.6, 14.3), (350.7, 5.4), (0, 0, 80, 20)
        self.assertEqual(visible_segment_midpoint(a, b, box), visible_segment_midpoint(b, a, box))

    def test_disjoint_and_nonfinite_segments_are_excluded(self):
        self.assertIsNone(visible_segment_midpoint((-10, 1), (-5, 1), (0, 0, 10, 10)))
        self.assertIsNone(visible_segment_midpoint((math.nan, 1), (5, 1), (0, 0, 10, 10)))

    def test_boundary_and_point_segments(self):
        self.assertEqual(visible_segment_midpoint((-1, 0), (11, 0), (0, 0, 10, 10)), (5, 0))
        self.assertEqual(visible_segment_midpoint((4, 4), (4, 4), (0, 0, 10, 10)), (4, 4))

if __name__ == "__main__":
    unittest.main()
