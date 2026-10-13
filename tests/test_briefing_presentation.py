import copy
import unittest
from core.briefing_presentation import chapters, requested, speech_prompt


class BriefingPresentationTests(unittest.TestCase):
    def test_specific_request_does_not_trigger_unrelated_daily_summary(self):
        for text in ['abre spotify', 'le meus emails', 'mostre tarefas', 'qual o clima']:
            self.assertFalse(requested(text))
        for text in ['bom dia Jarvis', 'Jarvis', 'me atualiza']:
            self.assertTrue(requested(text))
        self.assertFalse(requested(''))

    def test_every_news_chapter_has_the_matching_article_only_in_speech(self):
        package = {'data': {'tasks': {'count': 3, 'items': []}, 'news': {
            'model': {'kind': 'news', 'items': [{'title': 'Pesquisa cientifica', 'detail': 'Primeira fonte'},
                                               {'title': 'Novo satelite', 'detail': 'Segunda fonte'}]}}}}
        original = copy.deepcopy(package)
        sequence = chapters(package)
        self.assertEqual([c['model']['kind'] for c in sequence], ['tasks', 'news', 'news'])
        for index, chapter in enumerate(sequence[1:]):
            self.assertEqual(chapter['model']['focus'], index)
            self.assertEqual(chapter['facts'], original['data']['news']['model']['items'][index])
            self.assertNotIn('TAREFAS', speech_prompt(chapter))
        self.assertEqual(package, original)
        self.assertEqual(sequence[1]['model']['newsSequenceId'],sequence[2]['model']['newsSequenceId'])
        self.assertFalse(sequence[1]['model']['newsLast'])
        self.assertTrue(sequence[2]['model']['newsLast'])

    def test_empty_or_failed_collection_does_not_invent_chapters(self):
        self.assertEqual(chapters({'data': {}, 'unavailable': ['news']}), [])
