import unittest
from unittest.mock import patch
from core.presentation_clock import PresentationClock
from actions.web_search import fetch_news_package
from core.news_media import ImageMetadata
from actions.news_briefing import news_briefing
from actions.web_search import web_search
from unittest.mock import Mock

class ClockTests(unittest.TestCase):
    def test_actual_pcm_anchor_is_not_delayed_by_slow_word_estimate(self):
        clock=PresentationClock()
        clock.enqueue('Primeira noticia com muitas palavras para testar a fala acelerada.',at=0,duration=1)
        clock.enqueue('Segunda noticia.',at=1,duration=.4)
        clock.advance(.1);clock.advance(.5)
        self.assertEqual(clock.advance(.4)['cues'],['Segunda noticia.'])

    def test_batched_ordinals_share_actual_audio_duration(self):
        clock=PresentationClock()
        clock.enqueue('Primeira noticia: pesquisa. Segunda noticia: satelite.',at=0,duration=2)
        self.assertIn('Primeira',clock.advance(.1)['cues'][0])
        self.assertEqual(clock.advance(.5)['cues'],[])
        self.assertIn('Segunda',clock.advance(.4)['cues'][0])
    def test_scene_change_preserves_played_time_but_discards_old_subject_cues(self):
        clock=PresentationClock();clock.advance(.5);clock.enqueue('Assunto antigo',at=2)
        clock.replace_scene()
        self.assertEqual(clock.elapsed,.5)
        self.assertFalse(clock.pending)
        clock.enqueue('Assunto atual',at=.5)
        self.assertEqual(clock.advance(.1)['cues'],['Assunto atual'])

    def test_backend_rest_is_independent_of_microphone_mute(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive)
        assistant.ui=Mock();assistant.ui.muted=False
        assistant._awake=True;assistant._manual_rest=False
        assistant.interrupt=Mock();assistant.set_speaking=Mock()
        assistant._ui_rest_toggle(True)
        self.assertTrue(assistant._manual_rest)
        self.assertFalse(assistant._awake)
        self.assertFalse(assistant.ui.muted)
        assistant.interrupt.assert_called_once()
        assistant._ui_rest_toggle(False)
        self.assertFalse(assistant._manual_rest)
        self.assertTrue(assistant._awake)
        self.assertFalse(assistant.ui.muted)
    def test_illustrated_order_keeps_spoken_article_and_image_together(self):
        records=[{'title':'Sem foto','url':'https://example.org/one'}, {'title':'Com foto','url':'https://example.org/two','image_url':'https://example.org/photo.jpg'}]
        with patch('core.profile.read_profile',return_value={'news_count':2,'news_interests':'ciência'}),patch('actions.web_search._ddg_news',return_value=records),patch('core.news_media.thumbnail',return_value='data:image/jpeg;base64,test'),patch('core.news_media.article_thumbnail',return_value=''):
            package=fetch_news_package()
        self.assertEqual(package['model']['items'][0]['title'],'Com foto')
        self.assertIn('1. Com foto',package['text'])
    def test_normal_news_and_search_news_never_fall_back_to_plain_scene(self):
        package={'text':'Primeira notícia','model':{'kind':'news','title':'NOTÍCIAS','items':[{'title':'Teste','image':'data:image/jpeg;base64,test'}]}}
        player=Mock()
        with patch('actions.news_briefing.fetch_news_package',return_value=package):
            news_briefing({'topic':'tecnologia'},player)
        player.show_manifestation.assert_called_once_with(package['model'])
        player.reset_mock()
        with patch('actions.web_search.fetch_news_package',return_value=package):
            web_search({'query':'notícias de tecnologia','mode':'search'},player=player)
        player.show_manifestation.assert_called_once_with(package['model'])
    def test_source_image_metadata_is_parsed_without_script_execution(self):
        parser=ImageMetadata()
        parser.feed('<script type="application/ld+json">{"@graph":[{"@type":"NewsArticle","image":{"url":"https://example.org/photo.jpg"}}]}</script>')
        self.assertEqual(parser.image,'https://example.org/photo.jpg')
    def test_data_and_transcript_do_not_advance_without_audio(self):
        clock=PresentationClock();clock.enqueue('Primeira notícia importante.');clock.enqueue('Segunda notícia.')
        self.assertEqual(clock.elapsed,0)
        self.assertFalse(clock.active)
        first=clock.advance(.2)
        self.assertEqual(first['cues'],['Primeira notícia importante.'])
        self.assertEqual(clock.advance(.2)['cues'],[])
        for _ in range(9):clock.advance(.2)
        self.assertEqual(len(clock.pending),0)

    def test_interruption_cancels_late_audio_and_queue(self):
        clock=PresentationClock();clock.enqueue('Não executar.');clock.cancel()
        self.assertEqual(clock.advance(.2)['cues'],[])
        self.assertFalse(clock.active)
        clock.enqueue('Nova resposta.');clock.resume()
        self.assertEqual(clock.advance(.2)['cues'],['Nova resposta.'])

    def test_queue_is_bounded(self):
        clock=PresentationClock()
        for i in range(1000):clock.enqueue(str(i))
        self.assertEqual(len(clock.pending),clock.MAX_PENDING)
        self.assertEqual(clock.advance(.1)['cues'],['0'])
        self.assertGreater(clock.dropped,0)

    def test_received_audio_anchor_does_not_fire_future_article_early(self):
        clock=PresentationClock()
        clock.enqueue('Segunda notícia.',at=12)
        for _ in range(20):
            self.assertEqual(clock.advance(.5)['cues'],[])
        for _ in range(3):clock.advance(.5)
        self.assertEqual(clock.advance(.5)['cues'],['Segunda notícia.'])

    def test_transcript_batch_is_separated_without_rushing_news(self):
        clock=PresentationClock()
        clock.enqueue('Primeira notícia: pesquisa brasileira. Segunda notícia: lançamento espacial.',at=0)
        self.assertIn('Primeira',clock.advance(.2)['cues'][0])
        self.assertEqual(clock.advance(.5)['cues'],[])
        clock.advance(.5)
        self.assertEqual(clock.advance(.5)['cues'],[])
        self.assertIn('Segunda',clock.advance(.5)['cues'][0])

    def test_email_ordinals_split_without_treating_weekdays_as_items(self):
        clock=PresentationClock()
        clock.enqueue('Primeiro e-mail: reunião na segunda-feira. Segundo e-mail: documentos.',at=0)
        self.assertEqual(len(clock.pending),2)
        self.assertIn('segunda-feira',clock.advance(.2)['cues'][0])

    def test_every_news_item_gets_image_attempt_and_shared_package(self):
        records=[{'title':'Primeira','image_url':'https://example.org/one.jpg','url':'https://example.org/one','source':'Fonte A'},
                 {'title':'Segunda','url':'https://example.org/two','source':'Fonte B'}]
        with patch('core.profile.read_profile',return_value={'news_count':2,'news_interests':'ciência'}),patch('actions.web_search._ddg_news',return_value=records),patch('core.news_media.thumbnail',return_value='data:image/jpeg;base64,test'),patch('core.news_media.article_thumbnail',return_value='data:image/jpeg;base64,other'):
            package=fetch_news_package()
        self.assertEqual(len(package['model']['items']),2)
        self.assertTrue(all(item['image'] for item in package['model']['items']))
        self.assertTrue(package['model']['narrationDriven'])
        self.assertIn('Primeira',package['text'])
