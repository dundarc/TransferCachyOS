import json
import os
import subprocess
import unittest
from time import monotonic, sleep
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QProcess, QSettings, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from transfercachyos.catalog import APPS
from transfercachyos.services.backup import repository_fingerprint
from transfercachyos.services.packages import PACMAN_IN_TERMINAL
from transfercachyos.ui import backup, installed_apps, installer

TransferWindow = installer.TransferWindow


class TransactionSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, predicate):
        deadline = monotonic() + 3
        while not predicate() and monotonic() < deadline:
            self.app.processEvents()
            sleep(0.005)
        self.assertTrue(predicate())

    def backup_panel(self, root):
        panel = backup.BackupPanel("en", lambda: None)
        panel.settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
        source, target = root / "source", root / "backup"
        source.mkdir()
        target.mkdir()
        panel.sources.addItem(str(source))
        panel.target.setText(str(target))
        panel.password.setText("disposable")
        panel.repeat.setText("disposable")
        panel.refresh()
        return panel, source, target

    def approve(self):
        dialog = self.app.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        next(button for button in dialog.buttons()
             if dialog.buttonRole(button) == QMessageBox.ButtonRole.AcceptRole).click()

    def test_replacing_target_during_confirmation_stops_backup(self):
        with TemporaryDirectory() as directory, patch.object(backup, "RESTIC", "/usr/bin/true"):
            root = Path(directory)
            panel, _, target = self.backup_panel(root)

            def replace_target():
                target.rename(root / "original")
                target.mkdir()
                self.approve()

            with patch.object(panel, "start_operation") as start:
                QTimer.singleShot(0, replace_target)
                panel.show_plan()
            start.assert_not_called()
            self.assertEqual(panel.status_key, "backup_changed")

    def test_unchanged_target_can_start_backup(self):
        with TemporaryDirectory() as directory, patch.object(backup, "RESTIC", "/usr/bin/true"):
            panel, _, target = self.backup_panel(Path(directory))
            with patch.object(panel, "start_operation") as start:
                QTimer.singleShot(0, self.approve)
                panel.show_plan()
            start.assert_called_once_with(target, "disposable", "init", "running")

    def test_saved_target_must_match_its_previous_repository(self):
        with TemporaryDirectory() as directory:
            panel, source, target = self.backup_panel(Path(directory))
            config = target / "config"
            config.write_bytes(b"previous repository")
            panel.settings.setValue("backup_recipe", json.dumps([[str(source)], str(target)]))
            self.assertFalse(panel.saved_recipe_ready())
            panel.settings.setValue("backup_repository_fingerprint", repository_fingerprint(target))
            self.assertTrue(panel.saved_recipe_ready())
            config.write_bytes(b"replacement repository")
            self.assertFalse(panel.saved_recipe_ready())

    def test_timeout_is_not_presented_as_dependency_conflict(self):
        panel = installed_apps.PackagePanel("en")
        panel.show()
        self.addCleanup(panel.close)
        entry = installed_apps.Entry("gimp", "1", "GIMP")
        panel.explicit.add(entry.package)
        with patch.object(panel, "selection", return_value=entry):
            with patch.object(installed_apps, "command", side_effect=subprocess.TimeoutExpired(["pacman"], 5)):
                panel.confirm_remove()
                self.wait_until(lambda: not panel.preflight.running)
            self.assertTrue(panel.status.toPlainText().startswith(panel.t("timeout")))
            with patch.object(installed_apps, "command", side_effect=subprocess.CalledProcessError(
                1, ["pacman"], stderr="removing gimp breaks dependency",
            )):
                panel.confirm_remove()
                self.wait_until(lambda: not panel.preflight.running)
            self.assertTrue(panel.status.toPlainText().startswith(panel.t("required")))

    def test_install_waits_for_interactive_pacman_result(self):
        with patch.object(installer, "supported_system", return_value=True), patch.object(installer, "read_packages", return_value=set()):
            window = TransferWindow()
        self.assertNotIn("--noconfirm", PACMAN_IN_TERMINAL)
        self.assertIn("-Syu --needed --", PACMAN_IN_TERMINAL)
        with patch.object(installer, "interactive_terminal", return_value=("/fake/terminal", ("-e",))), \
             patch.object(installer.os, "access", return_value=True), patch.object(window.process, "start") as start:
            window.install([APPS[0]], ["firefox"])
        executable, arguments = start.call_args.args
        self.assertEqual(executable, "/fake/terminal")
        self.assertEqual(arguments[:3], ["-e", "/usr/bin/bash", "-c"])
        self.assertEqual(arguments[-1], "firefox")
        window.result_file.write_text("0\n", encoding="ascii")
        with patch.object(installer, "read_packages", return_value={"firefox"}):
            window.finished(0, QProcess.ExitStatus.NormalExit)
            self.wait_until(lambda: not window.query.running)
        self.assertEqual(window.status_key, "done")
        self.assertFalse(window.busy)


    def test_repository_check_can_be_stopped(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runner = root / "fake-restic"
            runner.write_text("#!/usr/bin/bash\nexec /usr/bin/sleep 30\n")
            runner.chmod(0o755)
            with patch.object(backup, "RESTIC", str(runner)):
                panel, _, target = self.backup_panel(root)
                (target / "config").write_bytes(b"test repository")
                panel.refresh()
                panel.check_button.click()
                self.assertTrue(panel.read_only)
                self.assertEqual(panel.process.arguments()[-1], "check")
                self.wait_until(lambda: panel.process.state() == QProcess.ProcessState.Running)
                panel.stop.click()
                self.wait_until(lambda: not panel.busy)
                self.assertEqual(panel.status_key, "cancelled")
                self.assertEqual(panel.secret, b"")


if __name__ == "__main__":
    unittest.main()
