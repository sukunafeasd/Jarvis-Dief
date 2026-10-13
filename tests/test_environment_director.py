import unittest
from core.environment_director import EnvironmentDirector


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.now = 10000
        self.director = EnvironmentDirector(lambda: self.now)

    def test_start_is_once_and_reduced_has_no_travel(self):
        self.director.start(True)
        self.now += 1000
        self.director.start()
        self.assertEqual(self.director.entrance['at'], 10000)
        self.assertEqual(self.director.entrance['duration'], 0)

    def test_greeting_does_not_cancel_entrance_but_interruption_does(self):
        self.director.start()
        self.now += 400
        payload = self.director.payload(phase='speaking')
        self.assertIsNone(payload['entrance']['cancelAt'])
        self.director.interrupt()
        self.now += 100
        self.director.payload(phase='thinking')
        self.assertEqual(self.director.entrance['cancelAt'], 10400)

    def test_planet_alias_and_return(self):
        self.director.command('Saturno')
        self.assertEqual(self.director.payload()['planet'], 'saturn')
        self.assertEqual(self.director.payload()['mode'], 'exploration')
        self.director.command('voltar')
        self.assertIsNone(self.director.payload()['planet'])
        self.assertEqual(self.director.payload()['mode'], 'assistant')

    def test_explicit_mode_remains_during_reading(self):
        self.director.command('Terra')
        self.assertEqual(self.director.payload(domain='gmail')['mode'], 'exploration')
        self.assertEqual(self.director.payload(domain='news')['planet'],'earth')
        self.assertEqual(self.director.payload()['planet'], 'earth')

    def test_reject_arbitrary_renderer_code(self):
        with self.assertRaises(ValueError):
            self.director.command('eval(geometry)')

    def test_actual_operation_result(self):
        self.director.operation_event('running')
        self.assertEqual(self.director.payload()['mode'], 'execution')
        self.director.operation_event('failed')
        self.assertEqual(self.director.cue['kind'], 'warning')
        self.director.operation_event('completed')
        self.assertEqual(self.director.cue['kind'], 'resolved')
        self.assertIsNone(self.director.operation)

    def test_interrupt_clears_transient_operation_not_context(self):
        self.director.command('Marte')
        self.director.operation_event('running')
        self.director.interrupt()
        self.assertIsNone(self.director.operation)
        self.assertEqual(self.director.planet, 'mars')
        self.assertEqual(self.director.cue['kind'], 'settle')

    def test_inputs_bounded_and_hidden_retains_mode(self):
        self.director.command('foco')
        payload = self.director.payload(visible=False, level=900, reduced=True)
        self.assertFalse(payload['visible'])
        self.assertEqual(payload['level'], 1)
        self.assertEqual(payload['motion'], 'reduced')
        self.assertEqual(self.director.payload(level='invalid')['level'], 0)

    def test_no_news_or_music_invention(self):
        self.assertEqual(self.director.payload(domain='music')['mode'], 'assistant')
        self.assertEqual(self.director.snapshot()['artistic_orbits'], True)
        self.assertNotIn('playback', self.director.payload())

    def test_explicit_analysis_changes_mode_even_with_news_and_keeps_operation(self):
        self.director.operation_event('running','weather_report')
        self.director.command('analise')
        self.assertEqual(self.director.payload(domain='news')['mode'],'analysis')
        self.assertEqual(self.director.operation,'running')
        self.assertEqual(self.director.snapshot()['resolved_mode'],'analysis')


if __name__ == '__main__':
    unittest.main()
