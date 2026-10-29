"""Band selection, completed-frame sequencing, restoration and encoded timing."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock

import numpy as np
from PIL import Image
from PySide6.QtTest import QTest

from GRIM_Backend.plotting.sweep_frames import make_sweep_frames
from GRIM_Backend.ui.sweep_export import SweepExporter, ffmpeg_executable, video_command, gif_command
from test_plot_analysis_features import _WindowCase, _point_grid


class FramePlanningTests(unittest.TestCase):
    def test_gif_order_timing_loop_and_single_frame(self):
        executable = ffmpeg_executable()
        if not executable:
            self.skipTest("FFmpeg unavailable")
        for count in (1, 3):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)][:count]
                for i, color in enumerate(colors, 1):
                    Image.new("RGB", (101, 81), color).save(folder / f"frame_{i:06d}.png")
                result = subprocess.run(gif_command(executable, folder, .35, folder / "sweep.gif"),
                    capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                with Image.open(folder / "sweep.gif") as gif:
                    self.assertEqual(gif.n_frames, count)
                    self.assertEqual(gif.info['loop'], 0)
                    self.assertEqual(gif.size, (101, 81))
                    for i, color in enumerate(colors):
                        gif.seek(i)
                        self.assertEqual(gif.info['duration'], 350)
                        self.assertEqual(gif.convert('RGB').getpixel((50,40)), color)

    def test_irregular_bands_keep_actual_samples_and_cover_final_edge(self):
        frames = make_sweep_frames([10, 8, 8.1, 8.4, 9.8], width=.4, unit="GHz")
        self.assertEqual(frames.selection(0), [1, 2, 3])
        self.assertEqual(frames.selection(len(frames)-1), [4, 0])
        self.assertEqual(frames.bounds[-1, 1], 10)
        self.assertTrue(all(len(frames.selection(i)) >= 2 for i in range(len(frames))))
        self.assertEqual(len({tuple(frames.selection(i)) for i in range(len(frames))}), len(frames))

    def test_full_band_single_frame_and_empty_band_error(self):
        self.assertEqual(len(make_sweep_frames([8, 9, 10], width=2)), 1)
        with self.assertRaisesRegex(ValueError, "at least 2"):
            make_sweep_frames([8, 9, 10], width=.1)

    def test_encoder_keeps_requested_frame_duration(self):
        executable = ffmpeg_executable()
        if not executable:
            self.skipTest("FFmpeg unavailable")
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for i, color in enumerate(("red", "green", "blue"), 1):
                Image.new("RGB", (101, 81), color).save(folder / f"frame_{i:06d}.png")
            result = subprocess.run(video_command(executable, folder, .4, folder / "movie.mp4"),
                capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            probe = Path(executable).with_name("ffprobe.exe")
            if probe.exists():
                details = json.loads(subprocess.check_output([str(probe), "-v", "error", "-show_streams",
                    "-of", "json", str(folder / "movie.mp4")]))["streams"][0]
                self.assertEqual(int(details["nb_frames"]), 3)
                self.assertAlmostEqual(float(details["duration"]), 1.2, places=3)
                self.assertEqual((details["width"], details["height"]), (102, 82))


class SweepIntegrationTests(_WindowCase):
    def wait(self, predicate, seconds=20):
        end = time.monotonic()+seconds
        while not predicate() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(predicate(), self.window.status.currentMessage())
        self.app.processEvents()

    def setup_range(self, mode="az_vs_range", asynchronous=False):
        w = self.window
        grid = _point_grid((-.1, 0, 0), azimuths=np.linspace(-4, 4, 9))
        row = w.table.rowCount()
        w._add_dataset_row(grid, "Point", "", file_name="")
        self.select_rows(row, freqs=tuple(range(len(grid.frequencies))))
        w._show_isar_workspace()
        w.btn_auto_plot.setChecked(False)
        w._plot_async_threshold = 0 if asynchronous else 10**9
        w._render_plot_mode(mode)
        if mode == "isar_image":
            self.wait(lambda: not getattr(w, "_isar_busy", False))
        elif asynchronous:
            self.wait(lambda: not getattr(w, "_ordinary_plot_pending", False))
        w.btn_slider.setChecked(True)
        self.app.processEvents()
        self.assertIsNotNone(w.plot_slider._frames)
        return w

    def test_range_frequency_bands_use_multiple_samples_and_keep_azimuths(self):
        w = self.setup_range()
        original_az = w._selected_indices(w.list_az)
        bar = w.plot_slider
        bar.step_mode.setCurrentIndex(bar.step_mode.findData("acquired"))
        bar.band_width.setValue(1.)
        w.chk_isar_freq_band.setChecked(True)
        w._on_plot_slider_moved(4)
        self.assertIn("updated", w.status.currentMessage())
        self.assertEqual(w._selected_indices(w.list_freq), set(bar._frames.selection(4)))
        self.assertGreater(len(w._selected_indices(w.list_freq)), 1)
        self.assertEqual(w._selected_indices(w.list_az), original_az)
        self.assertFalse(w.chk_isar_freq_band.isChecked())

    def test_isar_waits_before_advancing_and_supports_azimuth_windows(self):
        w = self.setup_range("isar_image")
        bar = w.plot_slider
        bar.seconds.setValue(.2)
        self.assertEqual(bar._play_timer.interval(), 200)
        w._on_plot_slider_moved(2)
        self.assertTrue(bar._busy)
        position = bar.slider.value()
        bar._play_step()
        self.assertEqual(bar.slider.value(), position)
        self.wait(lambda: not bar._busy)
        self.assertIn("ISAR image updated", w.status.currentMessage())
        bar.combo_axis.setCurrentIndex(bar.combo_axis.findData("azimuth"))
        bar.band_width.setValue(4)
        w._on_plot_slider_moved(1)
        self.wait(lambda: not bar._busy)
        self.assertEqual(len(w._selected_indices(w.list_az)), 5)
        self.assertIn("ISAR image updated", w.status.currentMessage())

    def test_async_png_export_captures_every_frame_and_restores_selection(self):
        w = self.setup_range(asynchronous=True)
        original = w._selected_indices(w.list_freq)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "images"
            exporter = SweepExporter(w, folder, seconds=.6, stride=30)
            count = len(exporter.positions)
            exporter.start()
            self.wait(lambda: exporter.finished)
            self.wait(lambda: not getattr(w, "_ordinary_plot_pending", False))
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete", manifest)
            self.assertEqual(len(manifest["frames"]), count)
            self.assertEqual(manifest["seconds_per_frame"], .6)
            self.assertEqual(w._selected_indices(w.list_freq), original)
            self.assertIsNone(w._sweep_export)
            self.assertEqual(len(list(folder.glob("frame_*.png"))), count)
            self.assertEqual(len({frame["label"] for frame in manifest["frames"]}), count)

    def test_isar_video_export(self):
        executable = ffmpeg_executable()
        if not executable:
            self.skipTest("FFmpeg unavailable")
        w = self.setup_range("isar_image")
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "video"
            exporter = SweepExporter(w, folder, kind="video", seconds=.3, stride=1000, executable=executable)
            exporter.start()
            self.wait(lambda: exporter.finished)
            self.wait(lambda: not getattr(w, "_isar_busy", False))
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete", manifest)
            self.assertEqual(len(manifest["frames"]), 2)
            self.assertGreater((folder / "sweep.mp4").stat().st_size, 1000)

    def test_isar_gif_export(self):
        executable = ffmpeg_executable()
        if not executable:
            self.skipTest("FFmpeg unavailable")
        w = self.setup_range("isar_image")
        original = w._selected_indices(w.list_freq)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "gif"
            exporter = SweepExporter(w, folder, kind="gif", seconds=.35, stride=1000, executable=executable)
            exporter.start()
            self.wait(lambda: exporter.finished)
            self.wait(lambda: not getattr(w, "_isar_busy", False))
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest['status'], 'complete', manifest)
            self.assertEqual(manifest['gif'], 'sweep.gif')
            self.assertEqual(w._selected_indices(w.list_freq), original)
            with Image.open(folder / 'sweep.gif') as gif:
                self.assertEqual(gif.n_frames, len(manifest['frames']))
                for i in range(gif.n_frames):
                    gif.seek(i)
                    self.assertEqual(gif.info['duration'], 350)

    def test_failed_frame_is_not_exported_and_cancel_restores_filters(self):
        w = self.setup_range()
        original = w._selected_indices(w.list_freq)
        w.chk_isar_freq_band.setChecked(True)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "failed"
            with mock.patch.object(w, "_render_plot_mode", side_effect=lambda mode: w.status.showMessage("No samples")):
                exporter = SweepExporter(w, folder)
                exporter.start()
                self.wait(lambda: exporter.finished)
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertFalse(list(folder.glob("frame_*.png")))
            self.assertEqual(w._selected_indices(w.list_freq), original)
            self.assertTrue(w.chk_isar_freq_band.isChecked())
            folder = Path(directory) / "canceled"
            exporter = SweepExporter(w, folder)
            exporter.start()
            exporter.cancel()
            self.assertEqual(json.loads((folder / "manifest.json").read_text())["status"], "canceled")
            self.assertEqual(w._selected_indices(w.list_freq), original)

    def test_cancel_during_async_frame_never_captures_stale_canvas(self):
        w = self.setup_range(asynchronous=True)
        original = w._selected_indices(w.list_freq)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "canceled"
            exporter = SweepExporter(w, folder)
            exporter.start()
            # Explicitly dispatch before processing Qt events so the worker's
            # completion cannot publish before cancellation is requested.
            exporter._next_frame()
            self.assertTrue(w.plot_slider._busy)
            exporter.cancel()
            self.wait(lambda: not w._ordinary_plot_pending)
            self.assertFalse(list(folder.glob("frame_*.png")))
            self.assertEqual(w._selected_indices(w.list_freq), original)
            self.assertEqual(json.loads((folder / "manifest.json").read_text())["status"], "canceled")

    def test_isar_publication_error_stops_export(self):
        w = self.setup_range("isar_image")
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "failed"
            with mock.patch("GRIM_Backend.plotting.modes.isar_mode.display_results", side_effect=ValueError("bad image")):
                exporter = SweepExporter(w, folder)
                exporter.start()
                self.wait(lambda: exporter.finished)
                self.wait(lambda: not getattr(w, "_isar_busy", False))
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertIn("bad image", manifest["detail"])
            self.assertFalse(list(folder.glob("frame_*.png")))
