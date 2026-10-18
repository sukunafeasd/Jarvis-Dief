import threading
import time
import unittest
from unittest.mock import Mock,patch
from core import search_locale
from actions import web_search as search


class LocaleTests(unittest.TestCase):
    def setUp(self):search_locale._CACHE.clear()

    def test_translation_preserves_source_url_and_requested_country(self):
        records=[{'title':'The economy grows in Japan today','snippet':'The latest figures were released today.',
                  'source':'Original','url':'https://example.org/japan','image_url':'https://example.org/photo'}]
        translate=Mock(return_value={'items':[{'id':0,'title':'A economia cresce no Japão','snippet':'Os dados foram divulgados hoje.',
                                                   'url':'https://attacker.invalid','source':'Wrong'}]})
        result=search_locale.localize_records(records,translate)
        self.assertEqual(result[0]['url'],records[0]['url'])
        self.assertEqual(result[0]['source'],'Original')
        self.assertTrue(result[0]['translated'])
        self.assertIn('Japão',result[0]['title'])
        search_locale.localize_records(records,translate)
        translate.assert_called_once()

    def test_failed_translation_does_not_silently_show_english(self):
        result=search_locale.localize_records([{'title':'The new market opens today','snippet':'With new products'}],lambda prompt:None)
        self.assertEqual(result,[])

    def test_language_detection_does_not_confuse_brasil_with_portuguese(self):
        for text in ('El gobierno de Brasil anuncia medidas','Markets surge in Brasil','TRUMP SIGNS NEW LAW','BREAKING NEWS'):
            self.assertFalse(search_locale.portuguese(text),text)
        self.assertTrue(search_locale.portuguese('Petrobras anuncia lucro recorde. Receita cresce 10%'))

    def test_correct_short_translations_use_context_instead_of_disappearing(self):
        for title,snippet in [('Petrobras anuncia lucro recorde','Receita cresce 10%'),
                              ('Dólar sobe','A moeda americana teve alta no mercado brasileiro nesta segunda-feira.')]:
            with self.subTest(title=title):
                records=[{'title':title,'snippet':snippet,'url':'https://example.org/real'}]
                result=search_locale.localize_records(records,lambda prompt:{'items':[{'id':0,'title':title,'snippet':snippet}]})
                self.assertEqual(len(result),1)
                self.assertEqual(result[0]['title'],title)
                self.assertEqual(result[0]['url'],records[0]['url'])

    def test_successful_foreign_provider_answer_still_requires_translation(self):
        with patch.object(search,'_gemini_search',return_value='The latest market figures were released today.'),patch.object(search,'_localized',return_value=[{'snippet':'Os dados do mercado foram divulgados hoje.'}]) as translate:
            self.assertEqual(search._search('mercado'),'Os dados do mercado foram divulgados hoje.')
            translate.assert_called_once()

    def test_empty_comparison_is_not_a_result(self):
        player=Mock()
        with patch.object(search,'_gemini_search',side_effect=OSError('offline')),patch.object(search,'_ddg_search',return_value=[]):
            result=search.web_search({'mode':'compare','items':['A','B']},player=player)
        self.assertTrue(result.startswith('Nenhum resultado'))
        player.show_manifestation.assert_not_called()

    def test_portuguese_result_does_not_spend_translation_call(self):
        translate=Mock()
        records=[{'title':'Novas pesquisas sobre o clima no Brasil','snippet':'Dados de hoje'}]
        self.assertEqual(search_locale.localize_records(records,translate),records)
        translate.assert_not_called()

    def test_media_deadline_releases_caller_without_waiting_for_worker(self):
        release=threading.Event()
        try:
            start=time.monotonic()
            result=search._parallel_bounded([lambda:release.wait(2),lambda:'ready'],.05)
            self.assertLess(time.monotonic()-start,.5)
            self.assertEqual(result,[None,'ready'])
        finally:release.set()

    def test_long_empty_query_still_uses_news_fallback(self):
        with patch.object(search,'_ddg_news',return_value=[]),patch.object(search,'_gemini_search',return_value='Notícias de fontes brasileiras com fatos verificados de hoje, em português.') as fallback:
            result=search._news('consulta sem resultados '*10)
        fallback.assert_called_once()
        self.assertIn('português',result)

    def test_failures_never_open_result_projection(self):
        for value in ('Nenhum resultado para: teste','Falha na pesquisa: teste','Informe o que deseja pesquisar.'):
            player=Mock()
            with patch.object(search,'_web_search',return_value=value):search.web_search({'query':'teste'},player=player)
            player.show_manifestation.assert_not_called()

