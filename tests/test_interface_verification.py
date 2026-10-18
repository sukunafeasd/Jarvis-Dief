import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from core.interface_verification import verify_result
from actions.interface_control import interface_control


class VerificationTests(unittest.TestCase):
    def screen(self):
        return {'presentation':{'visible':False,'kind':'weather'},'workspace':{},
                'pinned_previews':[{'kind':'weather'}],'visual_scene':{'elements':[]},
                'protocols':{'ultron':{'visible':True}},'layout_animating':False}

    def test_clear_does_not_claim_protocol_or_pins_were_removed(self):
        result=verify_result('clear','',{'ok':True,'screen':self.screen()})
        self.assertTrue(result['ok'])
        self.assertEqual(result['scope'],'conteudo_temporario')
        self.assertEqual(result['preserved'],['weather','protocolo:ultron'])
        self.assertFalse(result['verification']['pixels_checked'])

    def test_false_success_on_remaining_temporary_content_is_error(self):
        for part in ('presentation','workspace','visual_scene'):
            screen=self.screen()
            if part=='presentation':screen[part]['visible']=True
            elif part=='workspace':screen[part]['terminal_open']=True
            else:screen[part]['elements']=[{'id':'test','visible':True,'pinned':False}]
            result=verify_result('clear','',{'ok':True,'screen':screen})
            self.assertFalse(result['ok'])
            self.assertIn('inspect',result['recovery'])

    def test_unpin_requires_real_absence(self):
        result=verify_result('unpin','clima',{'ok':True,'screen':self.screen()})
        self.assertFalse(result['ok'])
        screen=self.screen();screen['pinned_previews']=[]
        self.assertTrue(verify_result('unpin','clima',{'ok':True,'screen':screen})['ok'])

    def test_animation_is_not_reported_as_pixel_verification(self):
        screen=self.screen();screen['layout_animating']=True
        result=verify_result('move_pin','weather',{'ok':True,'screen':screen})
        self.assertTrue(result['verification']['layout_animating'])
        self.assertFalse(result['verification']['pixels_checked'])
        self.assertIsNone(result['verification']['postcondition_verified'])

    def test_textual_content_pin_has_data_identity(self):
        screen=self.screen();screen['presentation']['kind']=None
        screen['pinned_previews']=[{'kind':'data'}]
        self.assertTrue(verify_result('pin','',{'ok':True,'screen':screen})['ok'])

    def test_move_checks_actual_bounds_not_requested_flag(self):
        screen=self.screen();screen.update(scene_position='left',scene_viewport={'width':1200,'height':800},
            avatar_bounds={'x':0,'y':0,'width':1200,'height':800})
        self.assertFalse(verify_result('move','left',{'ok':True,'screen':screen})['ok'])
        screen['avatar_bounds']['width']=700
        self.assertTrue(verify_result('move','left',{'ok':True,'screen':screen})['ok'])

    def test_move_pin_checks_resolved_coordinates(self):
        screen=self.screen();screen['scene_viewport']={'width':1200,'height':800}
        screen['pinned_previews']=[{'kind':'weather','bounds':{'x':100,'y':80,'width':240,'height':160}}]
        result=verify_result('move_pin','weather',{'ok':True,'screen':screen},'{"x":0.5,"y":0.1}')
        self.assertFalse(result['ok'])
        result=verify_result('move_pin','weather',{'ok':True,'screen':screen},'{"x":0.083333333,"y":0.1}')
        self.assertTrue(result['ok'])

    def test_tool_adapter_exposes_failed_postcondition(self):
        player=SimpleNamespace(control_interface=Mock(return_value={'ok':True,'screen':self.screen()}))
        result=json.loads(interface_control({'action':'unpin','value':'clima'},player))
        self.assertFalse(result['ok'])

    def test_failed_operation_offers_reinspection_without_inventing_success(self):
        original={'ok':False,'error':'alvo inexistente'}
        result=verify_result('close','',original)
        self.assertFalse(result['ok'])
        self.assertIn('inspect',result['recovery'])
        self.assertEqual(original,{'ok':False,'error':'alvo inexistente'})


class NativeStateVerification(unittest.TestCase):
    import test_scene
    import test_fui_screens
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def player(self):
        return SimpleNamespace(control_interface=lambda action,value,setting:self.command(action,value,setting))

    def test_clear_returns_preserved_pin_and_real_empty_temporary_content(self):
        self.window._pin_data({'kind':'weather','temperature':18,'items':[]})
        self.window._show_content('Consulta','Uma resposta de teste.')
        result=json.loads(interface_control({'action':'clear'},self.player()))
        self.assertTrue(result['ok'])
        self.assertIn('weather',result['preserved'])
        self.assertFalse(result['screen']['presentation']['visible'])
        self.assertEqual(result['screen']['scene_viewport']['width'],self.window._scene_stage.width())

    def test_textual_response_pin_success_is_preserved_by_verifier(self):
        self.window._show_content('Consulta','Uma resposta de teste.')
        result=json.loads(interface_control({'action':'pin'},self.player()))
        self.assertTrue(result['ok'])
        self.assertIn('data',self.window._pin_previews)
        self.assertTrue(result['verification']['postcondition_verified'])

    def test_idle_move_changes_real_bounds_after_animation(self):
        from PyQt6.QtTest import QTest
        self.command('clear')
        before=self.window._center_split.geometry()
        result=json.loads(interface_control({'action':'move','value':'left'},self.player()))
        if result['screen']['layout_animating']:
            self.assertIsNone(result['verification']['postcondition_verified'])
        QTest.qWait(500);self.app.processEvents()
        screen=self.window.interface_snapshot()
        self.assertNotEqual(before,self.window._center_split.geometry())
        checked=verify_result('move','left',{'ok':True,'screen':screen})
        self.assertTrue(checked['ok'])
        self.assertTrue(checked['verification']['postcondition_verified'])

    def test_same_destination_does_not_restart_layout_animation(self):
        from PyQt6.QtTest import QTest
        self.window.hud.motion_reduced=False
        self.command('move','right')
        animation=next(item for item in self.window._scene_animations if item.targetObject() is self.window._center_split)
        QTest.qWait(50);self.app.processEvents()
        elapsed=animation.currentTime()
        self.window._layout_scene(True)
        self.assertIn(animation,self.window._scene_animations)
        self.assertGreaterEqual(animation.currentTime(),elapsed)
        QTest.qWait(500);self.app.processEvents()
        from PyQt6 import sip
        self.assertTrue(sip.isdeleted(animation) or animation.state()==animation.State.Stopped)

    def test_reduced_motion_layout_applies_without_geometry_tween(self):
        self.window.hud.motion_reduced=True
        self.command('move','left')
        self.assertEqual(self.window._scene_animations,[])
        bounds=self.window._center_split.geometry()
        self.assertLess(bounds.width(),self.window._scene_stage.width())
