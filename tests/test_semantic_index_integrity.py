import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from core import semantic_memory as memory


class SemanticIndexIntegrity(unittest.TestCase):
    def test_invalid_request_does_not_read_store_or_load_model(self):
        requests=[{'query':None},{'query':{}},{'query':'  '},
                  {'query':'x'*1201},{'query':'projeto','limit':True},
                  {'query':'projeto','limit':1.5}]
        with patch('memory.memory_manager.load_memory') as load:
            for request in requests:
                with self.subTest(request=request), self.assertRaises(ValueError):
                    memory.run(request)
            load.assert_not_called()

    def test_empty_memory_does_not_need_optional_model(self):
        with patch('memory.memory_manager.load_memory',return_value={}), patch.dict(sys.modules,{'fastembed':None,'qdrant_client':None}):
            self.assertEqual(memory.run({'query':'projeto'})['items'],[])

    def test_partial_embeddings_never_replace_previous_index(self):
        records={'projects':{'one':{'value':'Projeto A'},'two':{'value':'Projeto B'}}}
        previous=Mock();candidate=Mock();embedding=Mock()
        embedding.embed.return_value=[np.array([.1,.2])]
        provider=SimpleNamespace(QdrantClient=Mock(return_value=candidate),models=Mock())
        with patch('memory.memory_manager.load_memory',return_value=records), \
             patch.dict(sys.modules,{'qdrant_client':provider,'fastembed':SimpleNamespace(TextEmbedding=Mock())}), \
             patch.object(memory,'CLIENT',previous), patch.object(memory,'SIGNATURE','old'), \
             patch.object(memory,'EMBEDDING',embedding):
            with self.assertRaisesRegex(ValueError,'Indice incompleto'):
                memory.run({'query':'projeto'})
            self.assertIs(memory.CLIENT,previous)
            self.assertEqual(memory.SIGNATURE,'old')
            previous.close.assert_not_called()
            candidate.close.assert_called_once()
            candidate.upsert.assert_not_called()


if __name__=='__main__':unittest.main()
