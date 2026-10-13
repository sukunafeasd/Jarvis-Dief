import unittest
from unittest.mock import patch
import json
from core.environment_director import EnvironmentDirector
from plugins import spotify_control


class EnvironmentMediaTests(unittest.TestCase):
    def test_only_actual_progress_and_no_invented_audio(self):
        now=[1000];director=EnvironmentDirector(lambda:now[0])
        director.media_update({'is_playing':True,'progress_ms':5000,'item':{'duration_ms':90000,'name':'Faixa de teste'}})
        media=director.payload()['media']
        self.assertTrue(media['playing']);self.assertEqual(media['progress'],5000)
        self.assertNotIn('beat',media);self.assertNotIn('spectrum',media)
        director.media_update({'is_playing':False,'progress_ms':8000,'item':{'duration_ms':90000}})
        self.assertFalse(director.payload()['media']['playing'])
        now[0]+=31000;self.assertIsNone(director.payload()['media'])

    def test_plugin_notifies_from_verified_playback_only(self):
        class Player:
            def update_environment_media(self,playback):self.last=playback
        player=Player();playback={'is_playing':True,'item':{'name':'Demonstração'}}
        with patch.object(spotify_control.spotify,'run',return_value={'playback':playback,'playing':True}):
            result=spotify_control.run({'action':'current'},player)
        self.assertEqual(player.last,playback)
        self.assertTrue(json.loads(result)['ok'])
        with patch.object(spotify_control.spotify,'run',return_value={'accepted':True,'action':'pause'}):
            spotify_control.run({'action':'pause'},player)
        self.assertIsNone(player.last)
