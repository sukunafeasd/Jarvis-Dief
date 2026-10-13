import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from actions import weather_report, organizer
import test_scene


class ManifestationTests(unittest.TestCase):
    def test_weather_never_opens_browser_and_uses_real_response(self):
        geo = Mock(); geo.json.return_value = {"results": [{"name": "Porto Alegre", "country_code": "BR", "latitude": -30, "longitude": -51}]}
        forecast = Mock(); forecast.json.return_value = {"current": {"time": "2026-10-11T12:00", "temperature_2m": 19, "weather_code": 3, "relative_humidity_2m": 70, "wind_speed_10m": 8, "is_day": 1}, "daily": {"time": ["2026-10-11", "2026-10-12"], "weather_code": [3, 61], "temperature_2m_max": [23, 25], "temperature_2m_min": [16, 17], "precipitation_probability_max": [30, 80], "wind_speed_10m_max": [10, 12]}}
        player = Mock()
        with patch.object(weather_report.requests, "get", side_effect=[geo, forecast]), patch("webbrowser.open") as browser:
            result = json.loads(weather_report.weather_action({"city": "Porto Alegre", "time": "tomorrow"}, player))
        self.assertTrue(result["ok"])
        self.assertEqual(result["weather"]["temperature"], 25)
        self.assertEqual(result["weather"]["condition"], "Chuva")
        player.show_manifestation.assert_called_once()
        browser.assert_not_called()

    def test_weather_failure_does_not_invent_data(self):
        with patch.object(weather_report.requests, "get", side_effect=weather_report.requests.Timeout()):
            player = Mock()
            result = json.loads(weather_report.weather_action({"city": "Porto Alegre"}, player))
        self.assertFalse(result["ok"])
        self.assertNotIn("temperature", player.show_manifestation.call_args.args[0])

    def test_local_records_persist_and_complete_by_real_id(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(organizer, "DATABASE", Path(folder)/"test.sqlite3"):
            args = {"domain": "tasks", "action": "create", "title": "Exemplo", "priority": "high"}
            result = json.loads(organizer.organizer_action(args))
            self.assertEqual(result["data"]["count"], 1)
            entry_id = result["data"]["items"][0]["id"]
            result = json.loads(organizer.organizer_action({"domain": "tasks", "action": "list"}))
            self.assertEqual(result["data"]["items"][0]["title"], "Exemplo")
            result = json.loads(organizer.organizer_action({"domain": "tasks", "action": "complete", "id": entry_id}))
            self.assertEqual(result["data"]["count"], 0)
            result = json.loads(organizer.organizer_action({"domain": "calendar", "action": "create", "title": "Reunião", "date": "invalid"}))
            self.assertFalse(result["ok"])


class SpatialSceneTests(unittest.TestCase):
    setUpClass = classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp = test_scene.SceneTests.setUp
    tearDown = test_scene.SceneTests.tearDown
    command = test_scene.SceneTests.command
    def test_late_system_sample_never_reopens_other_scene(self):
        self.window._show_manifestation({"kind": "system", "title": "SISTEMA", "cpu_percent": 10})
        old = self.window._presentation
        self.window._show_manifestation({"kind": "tasks", "title": "TAREFAS", "count": 0, "items": []})
        self.window._receive_telemetry(old, {"cpu_percent": 90})
        self.assertEqual(self.window._presentation["model"]["kind"], "tasks")
    def test_structured_models_return_with_identity(self):
        self.window._show_manifestation({"kind": "tasks", "title": "TAREFAS", "count": 1, "items": [{"id": 7, "title": "Teste"}]})
        self.window._show_manifestation({"kind": "weather", "title": "CLIMA", "city": "Porto Alegre", "temperature": 19})
        self.assertTrue(self.command("return")["ok"])
        self.assertEqual(self.window.interface_snapshot()["presentation"]["kind"], "tasks")
        self.assertEqual(self.window.interface_snapshot()["presentation"]["selected_id"], 7)
        self.assertEqual(self.window._title_lbl.text(), "DIEF JARVIS")
        self.assertEqual(self.window.hud.y(), 0)
        self.assertLessEqual(self.window._clock_lbl.font().pointSize(), 15)
