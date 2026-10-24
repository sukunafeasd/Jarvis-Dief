import unittest
from unittest.mock import patch
from core import memory_recall as recall


class TopicContinuity(unittest.TestCase):
    def test_synonyms_keep_all_requested_topics(self):
        self.assertTrue(recall.topic_matches('O backup do computador usa disco externo',['backup','pc']))
        self.assertFalse(recall.topic_matches('O backup usa disco externo',['backup','agenda']))

    def test_expanded_candidates_still_filter_irrelevant_records(self):
        records={'projects':{'backup':{'value':'Decidimos manter o backup do computador no disco externo.'},
                             'agenda':{'value':'Decidimos usar a agenda do Google.'}}}
        with patch('memory.memory_manager.load_memory',return_value=records), patch('core.conversation_memory.path') as path:
            path.return_value.exists.return_value=False
            result=recall.retrieve('backup pc','O que combinamos sobre backup do PC?')
        self.assertEqual(len(result['items']),1)
        self.assertIn('disco externo',result['items'][0]['detail'])


if __name__=='__main__':unittest.main()
