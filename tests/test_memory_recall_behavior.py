from datetime import datetime,timedelta,timezone
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock,AsyncMock
from core.memory_recall import recall_request,retrieve,meaningful_history,narration,select_relevant,topic_matches,followup_topic
from core.neural_memory import retrieval_payload
from memory import memory_manager as memory
from core import conversation_memory


class RecallEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.patcher=patch.object(memory,'MEMORY_PATH',Path(self.folder.name)/'memory.json');self.patcher.start();self.addCleanup(self.patcher.stop)

    def test_exact_user_phrase_is_recall_not_forge_activation(self):
        self.assertEqual(recall_request('Jarvis, lembra do que planejamos para a Forja?'),'forja')
        self.assertEqual(recall_request('O que combinamos sobre o protocolo Ultron?'),'ultron')
        self.assertEqual(recall_request('Voce pode me lembrar do plano antigo da Forja?'),'forja')
        for text in ('Ative a Forja','Quero criar um site na Forja','Me lembra de ativar a Forja amanha','Voce pode me lembrar de pagar a conta amanha','Planejamos usar a Forja para criar projetos','A noticia diz que ele lembra da Forja','O que significa a palavra lembra?'):
            self.assertIsNone(recall_request(text),text)

    def test_durable_facts_are_retrieved_without_creating_anything(self):
        memory.remember('forja','Decidimos usar a Forja com Codex e biblioteca local.','projects')
        result=retrieve('forja')
        self.assertEqual(result['items'][0]['id'],'projects/forja')
        self.assertIn('biblioteca',narration(result))
        self.assertNotIn('ativar',narration(result))

    def test_natural_commands_do_not_search_for_the_command_words(self):
        for text in ('busca nas lembrancas','Jarvis, busca nas lembracas','por favor, busca nas lembrancas','pesquise nas memorias','entra no modo cerebro','ative a forma neural'):
            self.assertEqual(recall_request(text),'',text)
        for text in ('pesquisa nas memorias sobre a Forja','quero que voce procure nas lembrancas sobre a Forja','busca nas lembrancas da Forja'):
            self.assertEqual(recall_request(text),'forja',text)
        self.assertEqual(recall_request('procure nas lembrancas sobre Synapse'),'synapse')

    def test_followup_is_a_subject_not_a_new_command_or_greeting(self):
        for text in ('sobre a Forja','Forja','sobre a biblioteca da Forja'):
            self.assertIn('forja',followup_topic(text))
        for text in ('bom dia','obrigado','Como esta voce?','ative o protocolo ultron','me lembra de pagar amanha','se atualize','qual e o clima?','qual a hora','quanto de memoria tenho','nao, cancele','desligue o computador','mostre minhas mensagens','aumente o volume'):
            self.assertIsNone(followup_topic(text),text)

    def test_actual_spoken_requests_open_the_memory_mode(self):
        for text in ('Entra no modo lembranca, Jarvis.',
                     'Busca uma coisa nas lembrancas, Jeeves.',
                     'Meu querido, e, procura na lembranca uma coisa para mim.',
                     'Jarvis, eu quero que tu vai para aquele modo onde tu consegue puxar as lembrancas, etc, antigas.',
                     'Ja avisei que eu quero que tu mude para o modo lembrancas.',
                     'Busque nas suas lembrancas, Jarvis.',
                     'Da uma olhada nas lembrancas para mim'):
            self.assertEqual(recall_request(text),'',text)
        self.assertEqual(recall_request('Quero que voce busque na lembranca algo sobre musica que eu falei.'),'musica')
        self.assertEqual(recall_request('Entra no modo lembranca e busca o que falei sobre musica'),'musica')
        self.assertEqual(recall_request('Entra no modo lembranca e procura a Forja'),'forja')
        for text in ('Nao entre no modo lembranca','Eu nao quero procurar nas lembrancas','A noticia mandava procurar nas memorias','O que significa procurar nas lembrancas?',
                     'Entre no modo lembrancas mas nao agora','Entre no modo Forja para consultar as memorias',
                     'Se voce entrar no modo lembranca, o que acontece?','Se entrar no modo lembranca, o que acontece?'):
            self.assertIsNone(recall_request(text),text)

    def test_persisted_acknowledgements_and_mislabeled_transcripts_are_not_evidence(self):
        rows=[{'id':'projects/forja','detail':text} for text in (
            'Entendido, chefe. Ja minimizei o Spotify e a Forja pode ser aberta depois.',
            'Gostei do nome, modo Synapse! Vou projetar isso agora.',
            'Claro, senhor. Vou configurar a Forja para voce.',
            'O Spotify esta minimizado.',
            'O Spotify esta minimizado. Os eventos de hoje estao na agenda local.')]
        self.assertEqual(select_relevant({'ok':True,'items':rows},'forja','busca nas lembrancas da Forja')['items'],[])
        value={'id':'identity/city','detail':'Porto Alegre'}
        self.assertEqual(select_relevant({'ok':True,'items':[value]},'cidade')['items'][0]['detail'],'Porto Alegre')

    def test_fresh_transcripts_and_old_smalltalk_do_not_become_memories(self):
        for role,text in [('user','Jarvis, lembra do que planejamos para a Forja?'),('assistant','Podemos abrir a Forja quando quiser, senhor.'),('user','Decidimos usar a Forja com a biblioteca integrada e salvar os arquivos localmente.')]:
            conversation_memory.record(role,text,text)
        now=datetime.now(timezone.utc)
        connection=sqlite3.connect(conversation_memory.path())
        with connection:
            connection.execute('UPDATE messages SET created_at=? WHERE role=?',((now-timedelta(days=1)).isoformat(),'assistant'))
        connection.close()
        self.assertEqual(retrieve('forja')['items'],[])

    def test_older_meaningful_plan_wins_and_question_is_excluded(self):
        for i,text in enumerate(('Jarvis, lembra do que planejamos para a Forja?','Decidimos que a Forja deve usar o motor Codex e manter uma biblioteca de projetos.','Certo, a Forja esta aqui, tudo funcionando por enquanto.')):
            conversation_memory.record('user',text,str(i))
        connection=sqlite3.connect(conversation_memory.path())
        with connection:connection.execute('UPDATE messages SET created_at=?',((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),))
        connection.close()
        items=retrieve('forja')['items']
        self.assertEqual(len(items),1);self.assertIn('Codex',items[0]['detail'])
        self.assertEqual(len(retrieval_payload({'ok':True,'items':items},'x')['items']),1)

    def test_visual_adapter_rejects_raw_recent_history_even_from_tool(self):
        row={'id':'conversation:1','detail':'Decidimos usar a Forja com Codex e biblioteca de projetos.','at':datetime.now(timezone.utc).isoformat()}
        self.assertFalse(retrieval_payload({'ok':True,'items':[row]},'a')['active'])
        row['at']='invalid';self.assertFalse(meaningful_history(row))

    def test_short_old_preference_is_important_but_replayed_recall_is_not(self):
        at='2020-01-01T00:00:00+00:00'
        self.assertTrue(meaningful_history({'detail':'Prefiro respostas curtas.','at':at}))
        self.assertFalse(meaningful_history({'detail':'Encontrei um registro. No registro consta: Decidimos usar Codex na Forja para construir projetos.','at':at}))

    def test_empty_result_never_invites_unrequested_creation(self):
        result=retrieve('projeto inexistente')
        self.assertEqual(result['items'],[])
        self.assertIn('Nao encontrei',narration(result))
        self.assertNotIn('criar',narration(result))

    def test_legacy_credential_is_redacted_before_voice(self):
        key='sk-'+('x'*30)
        spoken=narration({'ok':True,'items':[{'detail':'Registro antigo: '+key}]})
        self.assertNotIn(key,spoken);self.assertIn('omitida',spoken)

    def test_ambiguous_recall_asks_topic_instead_of_dumping_history(self):
        memory.remember('forja','Decidimos usar a Forja com biblioteca local.','projects')
        result=retrieve('',exclude_text='Jarvis, lembra daquilo que falei?')
        self.assertEqual(result['items'],[]);self.assertTrue(result['needs_clarification'])
        self.assertIn('Qual assunto',narration(result))

    def test_mixed_topics_do_not_fill_requested_synapse_with_spotify_or_tasks(self):
        at='2020-01-01T00:00:00+00:00'
        rows=[{'id':'conversation:1','role':'user','at':at,'detail':'Decidimos que o modo Spotify deve minimizar a janela automaticamente.'},
              {'id':'conversation:2','role':'user','at':at,'detail':'Decidimos que as tarefas do modo de trabalho devem aparecer na agenda.'},
              {'id':'conversation:3','role':'user','at':at,'detail':'Decidimos que o modo Synapse deve conectar as lembrancas do projeto.'}]
        result=select_relevant({'ok':True,'items':rows},'modo Synapse','Lembra do modo Synapse?')
        self.assertEqual([row['id'] for row in result['items']],['conversation:3'])
        self.assertNotIn('Spotify',narration(result));self.assertNotIn('tarefas',narration(result))
        self.assertEqual(len(retrieval_payload(result,'test')['items']),1)

    def test_multiword_subject_requires_both_terms_and_whole_words(self):
        self.assertFalse(topic_matches('Modo de tarefas da Forja',['biblioteca','forja']))
        self.assertFalse(topic_matches('Programacao do sistema',['ram']))
        memory.remember('forja_motor','Decidimos usar Codex na Forja.','projects')
        memory.remember('forja_biblioteca','Decidimos usar biblioteca na Forja.','projects')
        self.assertEqual([row['id'] for row in retrieve('biblioteca Forja')['items']],['projects/forja_biblioteca'])

    def test_history_quotes_only_the_relevant_sentence(self):
        row={'id':'conversation:1','role':'user','at':'2020-01-01T00:00:00+00:00',
             'detail':'Decidimos minimizar Spotify ao iniciar o programa. Na Forja decidimos manter uma biblioteca local de projetos. As tarefas devem ficar na agenda.'}
        result=select_relevant({'ok':True,'items':[row]},'forja','Lembra da Forja?')
        self.assertEqual(result['items'][0]['detail'],'Na Forja decidimos manter uma biblioteca local de projetos.')
        self.assertNotIn('Spotify',narration(result));self.assertNotIn('agenda',narration(result))

    def test_nested_tool_record_does_not_preserve_the_unfiltered_detail(self):
        row={'id':'projects/forja','record':{'detail':'Decidimos minimizar o Spotify. Na Forja decidimos usar a biblioteca local.'}}
        result=select_relevant({'ok':True,'items':[row]},'forja','Lembra da Forja?')
        visual=retrieval_payload(result,'nested')
        self.assertEqual(visual['items'][0]['detail'],'Na Forja decidimos usar a biblioteca local.')

    def test_assistant_acknowledgements_are_not_user_memories(self):
        row={'id':'conversation:1','role':'assistant','at':'2020-01-01T00:00:00+00:00',
             'detail':'Entendido, chefe. Vou configurar o Spotify para minimizar a janela toda vez.'}
        self.assertEqual(select_relevant({'ok':True,'items':[row]},'spotify','Lembra do Spotify?')['items'],[])

    def test_general_inventory_uses_curated_facts_not_chat_transcripts(self):
        row={'id':'conversation:1','role':'user','at':'2020-01-01T00:00:00+00:00','detail':'Decidimos usar o Spotify para ouvir musica enquanto programamos.'}
        result=select_relevant({'ok':True,'items':[row,{'id':'preferences/music','detail':'Prefiro jazz.'}]},'','O que voce lembra sobre mim?')
        self.assertEqual([item['id'] for item in result['items']],['preferences/music'])

    def test_inventory_quantifiers_do_not_become_literal_search_terms(self):
        memory.remember('city','Porto Alegre','identity')
        for text in ('Lembra de tudo sobre mim','Busque todas as memorias','Lembra de mim'):
            result=retrieve(recall_request(text),exclude_text=text)
            self.assertEqual(result['items'][0]['id'],'identity/city',text)

    def test_preferences_question_retrieves_declared_preferences_not_app_state(self):
        memory.remember('music','Prefiro jazz enquanto trabalho.','preferences')
        memory.remember('state','O Spotify esta minimizado.','preferences')
        text='O que voce lembra das minhas preferencias?'
        query=recall_request(text);self.assertEqual(query,'preferencias')
        result=retrieve(query,exclude_text=text)
        self.assertEqual([item['id'] for item in result['items']],['preferences/music'])

    def test_selection_ranks_before_limiting_and_removes_repeated_facts(self):
        rows=[{'id':str(i),'detail':f'Atlas utiliza a versao {i} do motor.','score':score} for i,score in enumerate((.1,.2,.3,.99))]
        result=select_relevant({'ok':True,'items':rows},'Atlas','Lembra de Atlas?')
        self.assertEqual([item['id'] for item in result['items']],['3','2','1'])
        repeated=[{'id':'a','detail':'Decidimos usar SQLite no Atlas.'},{'id':'b','detail':'Combinamos usar SQLite no Atlas!'},
                  {'id':'c','detail':'Decidimos nao usar SQLite no Atlas.'}]
        result=select_relevant({'ok':True,'items':repeated},'Atlas','Lembra de Atlas?')
        self.assertEqual(len(result['items']),2)
        self.assertTrue(any('nao usar' in item['detail'] for item in result['items']))

    def test_nested_records_are_spoken_with_the_same_detail_as_the_projection(self):
        result=select_relevant({'ok':True,'items':[{'id':'projects/atlas','record':{'value':'Atlas deve usar SQLite e salvamento local.'}}]},'Atlas','Lembra de Atlas?')
        self.assertIn('SQLite',narration(result));self.assertNotIn('""',narration(result))

    def test_plural_topic_retrieves_singular_history(self):
        conversation_memory.record('user','Decidimos que a musica deve tocar pelo Spotify com volume baixo.','music-plan')
        connection=sqlite3.connect(conversation_memory.path())
        with connection:connection.execute('UPDATE messages SET created_at=?',((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),))
        connection.close()
        self.assertEqual(len(retrieve('musicas')['items']),1)


class RecallRoutingTests(unittest.IsolatedAsyncioTestCase):
    def runner(self):
        import main
        owner=main.JarvisLive.__new__(main.JarvisLive)
        owner.ui=Mock();owner._forge_mode=False
        owner._protocol_voice_context=Mock(return_value=('session',))
        owner._protocol_voice_valid=Mock(return_value=True)
        owner._speak_protocol=AsyncMock()
        return owner

    async def test_real_phrase_runs_retrieval_and_speaks_evidence_not_forge_offer(self):
        owner=self.runner();result={'ok':True,'items':[{'id':'projects/forja','detail':'Decidimos usar a biblioteca local na Forja.','title':'Forja'}]}
        with patch('core.memory_recall.retrieve',return_value=result) as search:
            self.assertTrue(await owner._route_protocol_user_once('Jarvis, lembra do que planejamos para a Forja?'))
        search.assert_called_once_with('forja',exclude_text='Jarvis, lembra do que planejamos para a Forja?')
        spoken=' '.join(call.args[0] for call in owner._speak_protocol.call_args_list)
        self.assertIn('Vou consultar',spoken);self.assertIn('biblioteca local',spoken);self.assertNotIn('ativar',spoken)
        self.assertFalse(owner._forge_mode)
        payload=owner.ui.show_neural_memory.call_args.args[0]
        self.assertTrue(payload['active']);self.assertEqual(payload['items'][0]['id'],'projects/forja')

    async def test_new_turn_cancels_old_result_and_second_speech(self):
        owner=self.runner();owner._protocol_voice_valid.return_value=False
        with patch('core.memory_recall.retrieve',return_value={'ok':True,'items':[]}):await owner._route_memory_recall('lembra','forja')
        self.assertEqual(owner._speak_protocol.await_count,1)
        self.assertFalse(owner.ui.show_neural_memory.call_args.args[0]['active'])

    async def test_ambiguous_question_enters_neural_without_inventing_evidence(self):
        owner=self.runner()
        with patch('core.memory_recall.retrieve') as search:await owner._route_memory_recall('lembra daquilo','')
        search.assert_not_called()
        payload=owner.ui.show_neural_memory.call_args.args[0]
        self.assertTrue(payload['active']);self.assertTrue(payload['awaitingTopic']);self.assertEqual(payload['items'],[])
        self.assertIn('Qual assunto',owner._speak_protocol.call_args.args[0])

    async def test_next_subject_completes_the_pending_search(self):
        owner=self.runner()
        with patch('core.memory_recall.retrieve',return_value={'ok':True,'items':[]}) as search:
            self.assertTrue(await owner._route_protocol_user_once('busca nas lembracas'))
            search.assert_not_called()
            self.assertTrue(await owner._route_protocol_user_once('sobre a Forja'))
        search.assert_called_once_with('forja',exclude_text='sobre a Forja')
        self.assertIsNone(owner._memory_topic_offer)

    async def test_pending_subject_does_not_steal_real_forge_inventory(self):
        owner=self.runner();owner._route_forge_project_lookup=AsyncMock(return_value=True)
        await owner._route_protocol_user_once('busca nas lembrancas')
        with patch('core.memory_recall.retrieve') as search:
            await owner._route_protocol_user_once('Tinha algum projeto na Forja que eu tinha comecado?')
        search.assert_not_called();owner._route_forge_project_lookup.assert_awaited_once()

    async def test_pending_subject_does_not_steal_briefing(self):
        owner=self.runner();owner._queue_daily_briefing=Mock(return_value=True)
        await owner._route_protocol_user_once('busca nas lembrancas')
        with patch('core.memory_recall.retrieve') as search:
            self.assertTrue(await owner._route_protocol_user_once('me atualize'))
        search.assert_not_called();owner._queue_daily_briefing.assert_called_once()

    async def test_pending_subject_does_not_steal_protocol_exit(self):
        owner=self.runner()
        await owner._route_protocol_user_once('busca nas lembrancas')
        with patch('core.memory_recall.retrieve') as search,patch('actions.ultron_protocol.ultron_protocol',return_value='{"ok":true,"speech":"Protocolo desativado."}') as command:
            self.assertTrue(await owner._route_protocol_user_once('desative o protocolo ultron'))
        search.assert_not_called();command.assert_called_once_with({'command':'desative o protocolo ultron'},owner.ui)

    async def test_old_or_other_session_offer_cannot_capture_a_subject(self):
        import time
        for offer in ({'at':time.monotonic()-40,'session':None},{'at':time.monotonic(),'session':object()}):
            owner=self.runner();owner._memory_topic_offer=offer
            with patch('core.memory_recall.retrieve') as search:
                self.assertFalse(await owner._route_protocol_user_once('sobre a Forja'))
            search.assert_not_called();self.assertIsNone(owner._memory_topic_offer)

    async def test_storage_failure_is_not_empty_memory(self):
        owner=self.runner()
        with patch('core.memory_recall.retrieve',side_effect=OSError('unavailable')):await owner._route_memory_recall('lembra','forja')
        self.assertIn('Nao consegui ler',owner._speak_protocol.call_args.args[0])
        self.assertTrue(owner.ui.show_neural_memory.call_args.args[0]['active'])
        self.assertEqual(owner.ui.show_neural_memory.call_args.args[0]['outcome'],'unavailable')

    async def test_empty_search_still_enters_brain_and_reports_no_evidence(self):
        owner=self.runner()
        with patch('core.memory_recall.retrieve',return_value={'ok':True,'items':[]}):
            await owner._route_protocol_user_once('busque nas lembrancas sobre musica')
        payload=owner.ui.show_neural_memory.call_args.args[0]
        self.assertTrue(payload['active']);self.assertEqual(payload['outcome'],'empty');self.assertEqual(payload['items'],[])
        self.assertIn('Nao encontrei',owner._speak_protocol.call_args.args[0])

    async def test_native_intro_and_evidence_share_one_speech_request(self):
        import main
        owner=self.runner()
        owner.session=SimpleNamespace(send_client_content=AsyncMock())
        owner._protocol_voice_context.return_value=(owner.session,1,10,False,None,None,None)
        owner._speak_protocol=main.JarvisLive._speak_protocol.__get__(owner)
        owner._fish_voice=None;owner._routing_protocol_input=False;owner._server_turn_open=False
        result={'ok':True,'items':[{'id':'projects/forja','detail':'Decidimos usar a biblioteca local na Forja.'}]}
        with patch('core.fish_audio.selected',return_value=False),patch('core.memory_recall.retrieve',return_value=result):
            await owner._route_memory_recall('lembra','forja')
            owner.session.send_client_content.assert_not_awaited()
            await owner._flush_protocol_voice()
        owner.session.send_client_content.assert_awaited_once()
        text=owner.session.send_client_content.call_args.kwargs['turns']['parts'][0]['text']
        self.assertIn('Vou consultar',text);self.assertIn('biblioteca local',text)
        self.assertFalse(owner._routing_protocol_input)

if __name__=='__main__':unittest.main()
