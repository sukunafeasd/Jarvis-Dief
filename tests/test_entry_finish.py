import unittest
from pathlib import Path
from unittest.mock import patch

from core import startup


class EntryFinishTests(unittest.TestCase):
    def test_bootstrap_draws_and_closes_without_real_account_checks(self):
        import tkinter as tk
        from PIL import ImageGrab

        original_mainloop = tk.Tk.mainloop
        snapshots = []

        def preview(root, *args, **kwargs):
            def capture():
                root.update_idletasks()
                box = (root.winfo_rootx(), root.winfo_rooty(),
                       root.winfo_rootx()+root.winfo_width(),
                       root.winfo_rooty()+root.winfo_height())
                image = ImageGrab.grab(bbox=box)
                image.save(Path(__file__).resolve().parents[1]/'validation/startup-finish.png')
                snapshots.append(image.size)
            root.after(150, capture)
            return original_mainloop(root, *args, **kwargs)

        def simulated_checks(progress, stop, install=True):
            for name in ('Dependências', 'Arquivos', 'Áudio', 'IA', 'Gmail', 'WhatsApp'):
                progress(name, 'Verificação simulada', 'working')
                if stop.wait(.06):
                    return False
                progress(name, 'Dados de teste · nenhuma conta consultada', 'ok')
            return True

        with patch.object(startup, 'check_startup', side_effect=simulated_checks), \
                patch.object(tk.Tk, 'mainloop', preview):
            self.assertTrue(startup.bootstrap())
        self.assertEqual(snapshots, [(660, 440)])
