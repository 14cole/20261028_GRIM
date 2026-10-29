"""Fill Materials: region shading by medium, holes kept open, conflicts hatched red (offscreen)."""
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.path import Path as MplPath
from PySide6.QtWidgets import QApplication
from ghost_backend.ui.app import GhostWorkspace

THIN = 0.001
R = 1.0


def _arc(radius, a0, a1, count):
    return [(radius * math.cos(a0 + (a1 - a0) * i / count), radius * math.sin(a0 + (a1 - a0) * i / count))
            for i in range(count + 1)]


def _segment(name, kind, props, points):
    lines = [f"Segment: {name} {kind}", "properties: " + " ".join(map(str, props))]
    lines += [f"{a[0]!r} {a[1]!r} {b[0]!r} {b[1]!r}" for a, b in zip(points, points[1:])]
    return "\n".join(lines)


def partial_coating_geo(core_pos=1):
    """A 0.001 in coating over the top half of a 2 in PEC disc (two T-junctions)."""
    segments = [
        _segment("shell", 3, [3, 0, 0, 1, 0], _arc(R + THIN, math.pi, 0.0, 64)),
        _segment("wall_r", 3, [3, 0, 0, 1, 0], [(R + THIN, 0.0), (R, 0.0)]),
        _segment("core_top", 4, [4, 0, 0, core_pos, 0], _arc(R, math.pi, 0.0, 64)),
        _segment("wall_l", 3, [3, 0, 0, 1, 0], [(-R, 0.0), (-(R + THIN), 0.0)]),
        _segment("core_bot", 2, [2, 0, 0, 0, 0], _arc(R, 2 * math.pi, math.pi, 64)),
    ]
    return ("Title: Thin partial coating\n" + "\n".join(segments)
            + "\nIBCS_Resistances:\nDielectrics:\n1 4.0 -0.4 1.0 0.0\n2 9.0 -0.9 1.0 0.0\n")


def closed_coating_geo():
    outer = _arc(R + THIN, 0.0, -2 * math.pi, 96)
    inner = _arc(R, 0.0, -2 * math.pi, 96)
    outer[-1], inner[-1] = outer[0], inner[0]
    return ("Title: Thin closed coating\n" + _segment("outer", 3, [3, 0, 0, 1, 0], outer) + "\n"
            + _segment("core", 4, [4, 0, 0, 1, 0], inner)
            + "\nIBCS_Resistances:\nDielectrics:\n1 4.0 -0.4 1.0 0.0\n")


class RegionPreviewTests(unittest.TestCase):
    png_dir = None      # set by the PNG helper below; tests leave it None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.workspace = GhostWorkspace()
        self.tab = self.workspace.geometry_tab
        self.workspace.resize(1500, 900)
        self.workspace.show()
        self.addCleanup(self._dispose)

    def _dispose(self):
        self.workspace.solver_tab._is_solving = False
        self.tab._set_dirty(False)
        self.workspace.close()
        self.workspace.deleteLater()
        self.app.processEvents()

    def _load(self, source):
        path = Path(self.folder.name) / "regions.geo"
        path.write_text(source, encoding="ascii")
        with mock.patch("ghost_backend.ui.geometry.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
                mock.patch("ghost_backend.ui.geometry.QMessageBox.information"):
            self.assertTrue(self.tab.load_geo())
        self.tab.chk_show_normals.setChecked(False)

    def _settle(self):
        # The preview is debounced: let the timer fire, then draw.
        self.tab._region_timer.setInterval(0)
        for _ in range(5):
            self.app.processEvents()
        self.tab.canvas.draw()

    def _patches(self):
        return [a for a in self.tab.region_artists if a.get_gid() and a.get_gid().startswith("region-")
                and hasattr(a, "get_path")]

    def test_toggle_shades_regions_by_medium_and_keeps_holes(self):
        self._load(closed_coating_geo())
        self.assertEqual(self.tab.region_artists, [])
        self.tab.chk_fill_materials.setChecked(True)
        self._settle()
        patches = {p.get_gid(): p for p in self._patches()}
        self.assertEqual(set(patches), {"region-dielectric 1", "region-conductor"})
        np.testing.assert_allclose(patches["region-dielectric 1"].get_facecolor()[:3],
                                   to_rgba(self.tab._diel_color(1))[:3])
        np.testing.assert_allclose(patches["region-conductor"].get_facecolor()[:3],
                                   to_rgba(self.tab._PEC_COLOR)[:3])
        # The 0.001 in ring is an outline plus an explicit hole subpath.
        ring = patches["region-dielectric 1"].get_path()
        self.assertEqual(int(np.count_nonzero(ring.codes == MplPath.MOVETO)), 2)
        legend = [a for a in self.tab.region_artists if a.__class__.__name__ == "Legend"][0]
        self.assertEqual([t.get_text() for t in legend.get_texts()], ["conductor", "dielectric 1"])
        self.assertIn("consistent", self.tab.lbl_status.text())
        self.tab.chk_fill_materials.setChecked(False)
        self._settle()
        self.assertEqual(self.tab.region_artists, [])
        self._save_png("closed_coating")

    def test_conflicting_region_is_hatched_red_with_message(self):
        self._load(partial_coating_geo(core_pos=2))
        self.tab.chk_fill_materials.setChecked(True)
        self._settle()
        conflict = [p for p in self._patches() if p.get_gid() == "region-conflict"]
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].get_hatch(), "////")
        np.testing.assert_allclose(conflict[0].get_edgecolor()[:3], (1.0, 0.0, 0.0))
        self.assertIn("core_top", self.tab.lbl_status.text())
        self.assertIn("set pos_mat=1", self.tab.lbl_status.text())
        # Hover inside the 0.001 in coating at the top shows the message.
        ax = self.tab.canvas.ax
        ax.set_xlim(-0.004, 0.004)
        ax.set_ylim(R - 0.003, R + 0.004)
        self.tab.canvas.draw()
        x, y = ax.transData.transform((0.0, R + THIN / 2))
        self.tab._on_region_hover(SimpleNamespace(inaxes=ax, x=x, y=y))
        self.assertIn("core_top", self.tab.canvas.toolTip())
        x, y = ax.transData.transform((0.0, R + 3 * THIN))
        self.tab._on_region_hover(SimpleNamespace(inaxes=ax, x=x, y=y))
        self.assertEqual(self.tab.canvas.toolTip(), "")
        self._save_png("partial_mislabeled")

    def test_preview_follows_edits(self):
        self._load(partial_coating_geo(core_pos=1))
        self.tab.chk_fill_materials.setChecked(True)
        self._settle()
        self.assertFalse([p for p in self._patches() if p.get_gid() == "region-conflict"])
        self._save_png("partial_correct")
        # Relabel core_top to dielectric 2 through its table dropdown.
        combo = self.tab.table.cellWidget(2, 4)
        combo.setCurrentIndex(combo.findData("2"))
        self._settle()
        self.assertTrue([p for p in self._patches() if p.get_gid() == "region-conflict"])
        # The analysis is cached: an unchanged geometry is not recomputed.
        report = self.tab._region_report
        self.tab._render_regions()
        self.assertIs(self.tab._region_report, report)

    def _isolate(self, material):
        combo = self.tab.cmb_material_isolation
        index = combo.findData(material)
        self.assertGreaterEqual(index, 0)
        combo.setCurrentIndex(index)
        self._settle()

    def test_single_fill_toggle_replaces_show_regions(self):
        from PySide6.QtWidgets import QCheckBox
        self.assertFalse(hasattr(self.tab, "chk_show_regions"))
        labels = [box.text() for box in self.tab.findChildren(QCheckBox)]
        self.assertNotIn("Show regions", labels)
        self.assertEqual(labels.count("Fill Materials"), 1)
        self.assertIn("conflicts stay visible", self.tab.chk_fill_materials.toolTip())
        self.assertFalse(hasattr(self.tab, "_render_fills"))
        self.assertFalse(hasattr(self.tab, "_draw_fill_faces"))
        import ghost_backend.geometry.preview as preview
        self.assertFalse(hasattr(preview, "build_material_faces"))

    def test_isolation_filter_shades_only_selected_medium(self):
        self._load(closed_coating_geo())
        self.tab.chk_fill_materials.setChecked(True)
        self._settle()
        self.tab.chk_isolation_context.setChecked(False)
        self._isolate("d1")
        self.assertEqual({p.get_gid() for p in self._patches()}, {"region-dielectric 1"})
        legend = [a for a in self.tab.region_artists if a.__class__.__name__ == "Legend"][0]
        self.assertEqual([t.get_text() for t in legend.get_texts()], ["dielectric 1"])
        self.assertIn("showing dielectric 1", self.tab.lbl_status.text())
        self._isolate("PEC")
        self.assertEqual({p.get_gid() for p in self._patches()}, {"region-conductor"})
        # Faint context keeps other media, much lighter, and out of the legend.
        self.tab.chk_isolation_context.setChecked(True)
        self._settle()
        alpha = {p.get_gid(): p.get_alpha() for p in self._patches()}
        self.assertEqual(set(alpha), {"region-dielectric 1", "region-conductor"})
        self.assertLess(alpha["region-dielectric 1"], 0.2)
        self.assertAlmostEqual(alpha["region-conductor"], 0.45)
        legend = [a for a in self.tab.region_artists if a.__class__.__name__ == "Legend"][0]
        self.assertEqual([t.get_text() for t in legend.get_texts()], ["conductor"])
        # Air shades nothing; every medium is hidden without context.
        self.tab.chk_isolation_context.setChecked(False)
        self._isolate("air")
        self.assertEqual(self._patches(), [])
        self._isolate(None)
        self.assertEqual({p.get_gid() for p in self._patches()}, {"region-dielectric 1", "region-conductor"})

    def test_isolation_keeps_conflicts_hatched_and_marked(self):
        self._load(partial_coating_geo(core_pos=2))
        self.tab.chk_fill_materials.setChecked(True)
        self._settle()
        self.tab.chk_isolation_context.setChecked(False)
        for material in (None, "PEC", "air", "d2"):
            self._isolate(material)
            gids = [a.get_gid() for a in self.tab.region_artists]
            self.assertIn("region-conflict", gids, material)
            self.assertIn("region-conflict-marker", gids, material)
            conflict = [p for p in self._patches() if p.get_gid() == "region-conflict"][0]
            self.assertEqual(conflict.get_hatch(), "////")
            marker = [a for a in self.tab.region_artists if a.get_gid() == "region-conflict-marker"][0]
            np.testing.assert_allclose(marker.get_edgecolor()[0][:3], (1.0, 0.0, 0.0))
            self.assertEqual("region-conductor" in gids, material in (None, "PEC"))
            self.assertIn("problem", self.tab.lbl_status.text())

    def test_detail_inset_and_bor_axis_closure(self):
        hull = _segment("hull", 2, [2, 0, 0, 0, 0], _arc(R, math.pi / 2, -math.pi / 2, 32))
        self._load("Title: BoR hull\n" + hull + "\nIBCS_Resistances:\nDielectrics:\n")
        self.tab.set_geometry_mode("bor")
        self.tab.chk_fill_materials.setChecked(True)
        self._settle()
        self.assertEqual({p.get_gid() for p in self._patches()}, {"region-conductor"})
        self.tab.chk_detail_inset.setChecked(True)
        self.tab.canvas.draw()
        self.tab.canvas.draw()
        inset = [a.get_gid() for a in self.tab._detail_ax.patches]
        self.assertIn("region-conductor", inset)
        self.tab.chk_fill_materials.setChecked(False)
        self.tab.canvas.draw()
        self.assertNotIn("region-conductor", [a.get_gid() for a in self.tab._detail_ax.patches])

    def _save_png(self, stem):
        if self.png_dir is None:
            return
        ax = self.tab.canvas.ax
        self.tab.chk_fill_materials.setChecked(True)
        self._settle()
        for suffix, view in (("full", ((-1.15, 1.15), (-1.15, 1.15))),
                             ("junction", ((R - 0.0025, R + 0.0035), (-0.002, 0.003)))):
            ax.set_xlim(*view[0])
            ax.set_ylim(*view[1])
            self.tab.canvas.draw()
            self.tab.canvas.figure.savefig(os.path.join(self.png_dir, f"{stem}_{suffix}.png"), dpi=110)


def save_merged_pngs(png_dir):
    """merged_fill_all.png and merged_fill_isolated.png for a thin partial coating."""
    case = RegionPreviewTests("test_single_fill_toggle_replaces_show_regions")
    case.setUpClass()
    case.setUp()
    try:
        case._load(partial_coating_geo(core_pos=2))
        case.tab.chk_fill_materials.setChecked(True)
        case.tab.chk_isolation_context.setChecked(False)
        case._settle()
        ax = case.tab.canvas.ax
        for stem, material in (("merged_fill_all", None), ("merged_fill_isolated", "d1")):
            case._isolate(material)
            ax.set_xlim(-1.15, 1.15)
            ax.set_ylim(-1.15, 1.15)
            case.tab.canvas.draw()
            case.tab.canvas.figure.savefig(os.path.join(png_dir, f"{stem}.png"), dpi=110)
    finally:
        case.doCleanups()


if __name__ == "__main__":
    unittest.main()
