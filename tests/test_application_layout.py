import os
import unittest
from pathlib import Path
from string import Formatter
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QSettings, QTimer
from PySide6.QtWidgets import QApplication

from transfercachyos.i18n import LANGUAGES, messages
from transfercachyos.ui.main_window import MainWindow
from transfercachyos.ui.read_task import ReadTask

PROJECT = Path(__file__).resolve().parents[1]


class ApplicationLayoutTests(unittest.TestCase):
    def test_install_manifest_covers_python_code_and_translations(self):
        manifest = (PROJECT / "packaging/install-manifest.txt").read_text().splitlines()
        sources = {line.split()[1] for line in manifest}
        runtime_files = {
            str(path.relative_to(PROJECT))
            for path in (PROJECT / "src/transfercachyos").rglob("*")
            if path.suffix in (".py", ".json")
        }
        self.assertEqual({path for path in sources if path.startswith("src/")}, runtime_files)

    def test_languages_have_matching_keys_and_placeholders(self):
        baseline = messages("en")

        def fields(message):
            return sorted(field for _, field, _, _ in Formatter().parse(message) if field is not None)

        for language in LANGUAGES:
            with self.subTest(language=language):
                translated = messages(language)
                self.assertEqual(translated.keys(), baseline.keys())
                for section, items in baseline.items():
                    self.assertEqual(translated[section].keys(), items.keys())
                    for key, message in items.items():
                        self.assertEqual(fields(translated[section][key]), fields(message), (section, key))

    def test_main_navigation_and_languages(self):
        app = QApplication.instance() or QApplication([])
        config = Path(self.enterContext(TemporaryDirectory())) / "settings.ini"
        settings = QSettings(str(config), QSettings.Format.IniFormat)
        with patch("transfercachyos.ui.installer.supported_system", return_value=False), \
             patch("transfercachyos.ui.installer.QSettings", return_value=settings):
            window = MainWindow()
        window.show()
        self.addCleanup(window.close)
        self.assertEqual(window.count(), 5)
        self.assertIs(window.currentWidget(), window.daily)
        for index, language in enumerate(LANGUAGES):
            with self.subTest(language=language):
                window.installer.language_box.setCurrentIndex(index)
                app.processEvents()
                self.assertEqual(window.daily.language, language)
                self.assertEqual(window.backup.language, language)
                self.assertTrue(all(window.tabText(i) for i in range(window.count())))
        with patch.object(window.packages, "reload"):
            for panel in (window.installer, window.flatpak, window.packages, window.system,
                          window.checklist, window.migration, window.backup):
                window.open_panel(panel)
                self.assertTrue(panel.isVisible())


    def test_read_request_keeps_qt_events_responsive(self):
        app = QApplication.instance() or QApplication([])
        owner = QObject()
        task = ReadTask(owner)
        release = Event()
        observed = []
        task.completed.connect(lambda data, error: observed.append((data, error)))
        task.start(lambda: release.wait(2))
        self.assertFalse(task.start(lambda: None))
        QTimer.singleShot(0, release.set)
        deadline = monotonic() + 3
        while not observed and monotonic() < deadline:
            app.processEvents()
            sleep(0.005)
        self.assertEqual(observed, [(True, None)])

    def test_closing_window_cancels_read_only_jobs(self):
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        window.show()
        panel = window.daily
        panel.start_jobs([
            ("scan", "/usr/bin/sleep", ["30"]),
            ("scan", "/usr/bin/sleep", ["30"]),
        ])
        self.assertTrue(panel.busy)
        window.close()
        deadline = monotonic() + 3
        while window.isVisible() and monotonic() < deadline:
            app.processEvents()
            sleep(0.005)
        self.assertFalse(window.isVisible())
        self.assertFalse(panel.busy)
        self.assertEqual(panel.jobs, [])
        self.assertEqual(panel.disk_status.text(), panel.t("cancelled"))


if __name__ == "__main__":
    unittest.main()
