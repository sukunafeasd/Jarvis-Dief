import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock,AsyncMock
from core.forge_project_lookup import requested,lookup,narration


class ProjectLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def manifest(self,identifier='a'*32,name='Site iniciado',state='idle'):
        directory=self.root/'projects'/identifier;directory.mkdir(parents=True)
        (directory/'manifest.json').write_text(json.dumps({'id':identifier,'name':name,'state':state}),'utf-8')
        return directory

    def test_real_question_routes_to_projects_not_chat_history(self):
        for text in ('Tinha algum projeto na Forja que eu tinha comecado?','Jarvis, tem algum projeto na forja que eu comecei?','Quais projetos existem na Forja?','Liste meus projetos da Forja'):
            self.assertTrue(requested(text),text)
        for text in ('Crie um projeto na Forja','Ative o modo Forja','Lembra do plano da Forja?'):
            self.assertFalse(requested(text),text)

    def test_read_only_lookup_returns_real_project_and_keeps_files(self):
        directory=self.manifest();before=(directory/'manifest.json').read_bytes()
        result=lookup(self.root)
        self.assertTrue(result['ok']);self.assertEqual(result['total'],1)
        self.assertEqual(result['items'][0]['title'],'Site iniciado')
        self.assertIn('iniciado',narration(result));self.assertEqual((directory/'manifest.json').read_bytes(),before)

    def test_empty_library_does_not_become_a_conversation_search(self):
        result=lookup(self.root)
        self.assertTrue(result['ok']);self.assertEqual(result['items'],[])
        self.assertIn('Nao encontrei projetos',narration(result))
        self.assertFalse((self.root/'projects').exists())

    def test_corrupt_file_is_not_claimed_as_no_projects(self):
        directory=self.manifest();(directory/'manifest.json').write_text('{broken','utf-8')
        result=lookup(self.root)
        self.assertFalse(result['ok']);self.assertIn('Nao consegui verificar',narration(result))

    def test_project_and_its_saved_artifact_are_not_counted_twice(self):
        self.manifest();directory=self.root/'library'/('b'*32);directory.mkdir(parents=True)
        (directory/'artifact.json').write_text(json.dumps({'id':'b'*32,'name':'Site salvo','project_id':'a'*32}),'utf-8')
        self.assertEqual(lookup(self.root)['total'],1)


class ProjectRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_question_uses_catalog_without_entering_or_creating(self):
        import main
        owner=main.JarvisLive.__new__(main.JarvisLive);owner.ui=Mock();owner._forge_mode=False
        owner._protocol_voice_context=Mock(return_value=('test',));owner._protocol_voice_valid=Mock(return_value=True)
        owner._speak_protocol=AsyncMock();owner._route_memory_recall=AsyncMock()
        result={'ok':True,'items':[{'id':'forge:project:a','title':'Meu site','detail':'Meu site - iniciado.'}]}
        with patch('core.forge_project_lookup.lookup',return_value=result) as read:
            self.assertTrue(await owner._route_protocol_user_once('Jarvis, tinha algum projeto na Forja que eu tinha comecado?'))
        read.assert_called_once();owner._route_memory_recall.assert_not_awaited()
        owner.ui.forge_runtime.command.assert_not_called();self.assertFalse(owner._forge_mode)
        self.assertIn('Meu site',owner._speak_protocol.call_args.args[0])
        self.assertEqual(owner.ui.show_neural_memory.call_args.args[0]['items'][0]['title'],'Meu site')

if __name__=='__main__':unittest.main()
