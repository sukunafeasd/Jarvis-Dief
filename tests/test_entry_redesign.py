"""Entry screens: no accounts, installation or real elevation in these tests."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class EntryRedesignTests(unittest.TestCase):
    def test_status_and_animation_do_not_invent_success(self):
        import tkinter as tk
        from core.fui_bootstrap import BootstrapSurface
        root = tk.Tk()
        try:
            surface = BootstrapSurface(root)
            surface.update_status('IA', 'Configuracao pendente', 'pending')
            surface.update_status('Arquivos', 'Arquivo indisponivel', 'error')
            self.assertEqual(surface.checked, set())
            surface.update_status('Arquivos', 'Verificado', 'ok')
            self.assertEqual(surface.checked, {'Arquivos'})
            surface.update_status('Arquivos', 'Tentando novamente', 'working')
            self.assertEqual(surface.checked, set())
            count = len(surface.canvas.find_all())
            for frame in range(30):
                surface.animate(frame / 10)
            self.assertEqual(count, len(surface.canvas.find_all()))
            root.update_idletasks()
            for label in surface.rows.values():
                self.assertLess(label.winfo_y()+label.winfo_height(), surface.progress_y)
                self.assertLess(label.winfo_x()+label.winfo_width(), surface.width)
        finally:
            root.destroy()

    def test_admin_rejection_retries_and_never_elevates_automatically(self):
        from PyQt6.QtWidgets import QApplication
        from core.elevation_dialog import ElevationDialog
        app = QApplication.instance() or QApplication([])
        calls = []
        dialog = ElevationDialog(lambda: calls.append(True) or False, reduced=True)
        try:
            dialog.show()
            app.processEvents()
            self.assertEqual(calls, [])
            dialog.elevate()
            self.assertEqual(len(calls), 1)
            self.assertTrue(dialog.continue_button.isEnabled())
            self.assertIn('não foi concedida', dialog.notice.text())
            self.assertFalse(dialog.timer.isActive())
            for width, height in ((580,560),(840,580),(960,720)):
                dialog.resize(width, height)
                app.processEvents()
                self.assertLessEqual(dialog.continue_button.geometry().right(), dialog.width())
                self.assertGreaterEqual(dialog.notice.height(), dialog.notice.heightForWidth(dialog.notice.width()))
        finally:
            dialog.close()


if __name__ == '__main__':
    unittest.main()
