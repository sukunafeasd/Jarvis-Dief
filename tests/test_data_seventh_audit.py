import unittest
import test_scene
import test_fui_screens
from core.presentation_clock import PresentationClock, valid_time
from core.presentation_model import normalize_model, shown_number


class DataSeventhAudit(unittest.TestCase):
    def test_invalid_row_text_is_not_displayed_as_object(self):
        original = {'kind': 'gmail', 'items': [{'title': {'bad': 1}, 'detail': ['bad'], 'sender': 42}]}
        model = normalize_model(original)
        for field in ('title', 'detail', 'sender'):
            self.assertEqual(model['items'][0][field], '')
        self.assertEqual(original['items'][0]['title'], {'bad': 1})

    def test_optional_display_text_is_sanitized(self):
        model = normalize_model({'kind': 'weather', 'region': {}, 'observed': [], 'emptyText': None})
        for field in ('region', 'observed', 'emptyText'):
            self.assertEqual(model[field], '')

    def test_huge_integer_timestamp_is_rejected_without_exception(self):
        self.assertFalse(valid_time(10 ** 1000))
        clock = PresentationClock()
        clock.enqueue('Texto valido', at=10 ** 1000)
        self.assertEqual(clock.advance(.1)['cues'], ['Texto valido'])

    def test_unrenderable_number_uses_unavailable_marker(self):
        self.assertEqual(shown_number(10 ** 1000), '--')

    def test_invalid_numeric_data_cannot_reach_renderer(self):
        model = normalize_model({'kind': 'weather', 'temperature': float('inf'),
                                 'forecast': [{'max': float('nan')}], 'narrationDriven': True})
        self.assertIsNone(model['temperature'])
        self.assertIsNone(model['forecast'][0]['max'])
        self.assertIs(model['narrationDriven'], True)


class PinSeventhAudit(unittest.TestCase):
    setUpClass = classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp = test_fui_screens.AllSettingsPagesTests.setUp
    tearDown = test_fui_screens.AllSettingsPagesTests.tearDown

    def test_null_empty_message_can_be_pinned(self):
        self.window._pin_data({'kind': 'files', 'items': [], 'emptyText': None})
        self.assertIn('Nenhum item', self.window._pin_previews['files']['label'].text())

    def test_missing_empty_message_uses_available_text(self):
        self.window._pin_data({'kind': 'memory', 'items': [], 'emptyText': None, 'text': 'Contexto disponivel'})
        self.assertIn('Contexto disponivel', self.window._pin_previews['memory']['label'].text())

    def test_blank_record_uses_unavailable_message(self):
        self.window._pin_data({'kind': 'files', 'items': [{'title': None, 'detail': None}]})
        self.assertIn('Nenhum item', self.window._pin_previews['files']['label'].text())

    def test_empty_detail_does_not_hide_due_date(self):
        self.window._pin_data({'kind': 'tasks', 'items': [{'title': 'Revisar', 'detail': '', 'due': 'Hoje'}]})
        self.assertIn('Hoje', self.window._pin_previews['tasks']['label'].text())
