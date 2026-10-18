"""Read-only telemetry and host persistence with disposable personal data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from PyQt6.QtGui import QFont,QFontDatabase
from PyQt6.QtWidgets import QApplication,QLineEdit,QPushButton,QSlider,QSpinBox
from core import personality as p,conversation_memory as journal
from core.personality_view import PersonalityView
from memory import memory_manager as mm

OUTPUT=Path(tempfile.mkdtemp(prefix='dief-personality-visual-'))


class PersonalityInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        for name in ('segoeui.ttf','segoeuib.ttf'):
            if (fonts/name).exists():QFontDatabase.addApplicationFont(str(fonts/name))
        cls.app.setFont(QFont('Segoe UI',10))

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        change=patch.object(mm,'MEMORY_PATH',self.root/'memory/long_term.json')
        change.start();self.addCleanup(change.stop);self.addCleanup(self.folder.cleanup)

    def test_profile_is_read_only_responsive_and_refreshes(self):
        view=PersonalityView();self.addCleanup(view.close)
        view.setStyleSheet(view.styleSheet()+' PersonalityView { background:#061321; }')
        for kind in (QLineEdit,QPushButton,QSlider,QSpinBox):self.assertEqual(view.findChildren(kind),[])
        journal.observe_user('Prefiro respostas curtas e sem piadas.','ui:1')
        view.refresh();view.show()
        self.assertEqual(view.meters['detail'].value(),20)
        self.assertEqual(view.sources['detail'].text(),'Preferência explícita')
        for width in (850,600,390):
            view.resize(width,340);self.app.processEvents()
            self.assertEqual(view._columns,1 if width<520 else 2)
            for cell in view.cells:
                self.assertTrue(view.rect().contains(cell.geometry()))
            self.assertTrue(view.grab().save(str(OUTPUT/f'personality-{width}.png')))

    def test_malformed_event_is_unavailable_not_a_widget_crash(self):
        state=p._empty();state['events']=[None]
        p.path().parent.mkdir(parents=True);raw=json.dumps(state)
        p.path().write_text(raw,encoding='utf-8')
        view=PersonalityView();self.addCleanup(view.close)
        self.assertFalse(p.snapshot()['available'])
        self.assertIn('preservados',view.status.text())
        self.assertTrue(all(meter.isHidden() for meter in view.meters.values()))
        self.assertEqual(p.path().read_text(encoding='utf-8'),raw)

    def test_host_records_roles_and_deduplicates_final_turns(self):
        import main
        runner=main.JarvisLive.__new__(main.JarvisLive);runner.ui=Mock()
        async def exercise():
            await runner._remember_assistant_turn('Unsolicited startup message')
            await runner._remember_user_turn('Me chame de chefe.',{'serial':7})
            await runner._remember_user_turn('Me chame de chefe.',{'serial':7})
            await runner._remember_assistant_turn('Entendido, chefe.')
            await runner._remember_assistant_turn('Entendido, chefe.')
        asyncio.run(exercise())
        self.assertEqual(p.snapshot()['turns'],1)
        rows=journal.search('',limit=20)['items']
        self.assertEqual(len(rows),2)
        self.assertEqual({row['role'] for row in rows},{'user','assistant'})
        runner.ui.write_log.assert_not_called()

    def test_reconnection_builds_same_identity_without_credentials(self):
        import main
        journal.observe_user('Me chame de chefe. Prefiro respostas curtas.','config:1')
        journal.record('assistant','Podemos conversar sobre o observatorio.','config:assistant')
        runner=main.JarvisLive.__new__(main.JarvisLive)
        registry=Mock();registry.get_tool_declarations.return_value=[]
        runner._action_registry=runner._plugin_registry=registry
        runner._resume_handle=None;runner._enhanced_live=runner._tuned_live=False
        config=self.root/'config.json'
        for key in ('fake-provider-key-one','fake-provider-key-two'):
            config.write_text(json.dumps({'api_key':key,'assistant_name':'Dief Jarvis'}),encoding='utf-8')
            with patch.object(main,'API_CONFIG_PATH',config):instruction=runner._build_config().system_instruction
            self.assertIn('PERSONALIDADE CENTRAL DO JARVIS',instruction)
            self.assertIn('chefe',instruction);self.assertIn('observatorio',instruction)
            self.assertIn('"detail": 20',instruction)
            self.assertNotIn(key,instruction)


if __name__=='__main__':
    print('Capturas:',OUTPUT,flush=True);unittest.main()
