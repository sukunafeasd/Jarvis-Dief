"""Conversation-bound confirmations; no generated shell or ambiguous cleanup."""
import asyncio
import re
import time
import uuid
from .ultron_tools import WINDOWS_ACTIONS

def reply(speech,mode='info',**values):return {'speech':speech,'mode':mode,**values}


def intent(text):
    clean=' '.join(text.casefold().strip().rstrip('.!?').split())
    clean=re.sub(r'^jarvis(?:\s*[:,]\s*|\s+)','',clean)
    from core.protocol_commands import protocol_request
    request=protocol_request(text)
    if request and request[0]=='ultron':
        return ('ativar' if request[1]=='enter' else 'desativar')+' protocolo ultron'
    return clean


def discard(service,identifier):
    with service.ACTION_LOCK:service.PENDING.pop(identifier,None)


async def converse(service,payload):
    CONVERSATIONS=service.CONVERSATIONS
    identifier=payload.conversation_id
    if not re.fullmatch(r'[a-zA-Z0-9-]{16,64}',identifier):raise ValueError('Conversa invalida.')
    current=time.monotonic()
    for key in list(CONVERSATIONS):
        if current-CONVERSATIONS[key]['seen']>600 and not CONVERSATIONS[key]['lock'].locked():
            previous=CONVERSATIONS.pop(key);discard(service,previous.get('pending'))
    if identifier not in CONVERSATIONS:
        if len(CONVERSATIONS)>=32:raise ValueError('Limite de conversas locais atingido.')
        CONVERSATIONS[identifier]={'seen':current,'pending':None,'lock':asyncio.Lock()}
    conversation=CONVERSATIONS[identifier]
    async with conversation['lock']:
        conversation['seen']=current
        text=intent(payload.text)
        if text in {'sim','sim jarvis','sim, jarvis','sim senhor','sim, senhor','confirmo','pode fazer','sim pode fazer','pode executar'}:
            pending=conversation.get('pending')
            if not pending or payload.reply_to!=pending:return reply('Não há uma pergunta válida ligada a esta confirmação, senhor. Faça o pedido novamente.')
            conversation['pending']=None
            try:
                result=await asyncio.to_thread(service.confirm_action,pending)
            except (ValueError,OSError,KeyError):
                return reply('A ação não foi confirmada: o prazo, os arquivos, a permissão ou o estado mudaram. Preciso preparar uma nova confirmação, senhor.')
            if result.get('operation_id'):return reply('Solicitação aceita, senhor. Estou acompanhando a execução real do Windows. Ainda não vou anunciar sucesso.',mode='operation',result=result)
            if 'cleaned_files' in result:
                return reply(f"{result['cleaned_files']} temporários foram removidos com cópia de recuperação. "+('A limpeza foi parcial, senhor.' if result['state']=='partial' else 'Documentos e programas ficaram intactos, senhor.'),mode='vault',result=result)
            if result.get('recovery_path'):return reply(f"Recuperação concluída em uma nova pasta, senhor. {result['file_count']} arquivos recuperados, sem substituir os originais.",mode='vault',result=result)
            return reply(f"Backup concluído e verificado, senhor. {result['file_count']} arquivos no cofre.",mode='vault',result=result)
        if conversation.get('pending'):
            discard(service,conversation['pending']);conversation['pending']=None
        if text in {'não','nao','cancelar','cancela','não faça','nao faca','para','pare'}:return reply('Cancelei a ação pendente e a apresentação, senhor. Nada novo foi executado. Operações já aceitas pelo Windows não foram interrompidas.',mode='cancelled')
        if text in {'ativar protocolo ultron','desativar protocolo ultron'}:
            value=await service.command(service.Command(text=text))
            return reply('O protocolo já está analisando o sistema, senhor.' if value.get('already_running') else 'Protocolo ULTRON iniciado, senhor. Vou apresentar o diagnóstico baseado nas consultas reais do computador.' if text.startswith('ativar') else 'Protocolo desativado, senhor. O monitor local foi encerrado. Operações já aceitas pelo Windows podem continuar.',mode='activation' if text.startswith('ativar') else 'deactivation')
        if service.STATE['phase']=='idle':return reply('Para iniciar, diga ativar protocolo ultron, senhor. O planeta não é ativado por toque.')
        if text in {'status','diagnóstico','diagnostico','como está o pc','como esta o pc','o que encontrou','verifique o computador','analise o computador','atualize o diagnóstico','atualize o diagnostico'}:
            if service.STATE['scan']['running']:return reply('A análise ainda está em andamento, senhor. Vou aguardar os resultados antes de concluir.',mode='scan_wait')
            if text in {'verifique o computador','analise o computador','atualize o diagnóstico','atualize o diagnostico'}:
                await service.command(service.Command(text='ativar protocolo ultron'))
                return reply('Vou atualizar o diagnóstico com novas consultas locais, senhor.',mode='scan_wait')
            return reply('Vou apresentar as observações disponíveis, senhor.',mode='diagnostic')
        if text in {'ativar monitoramento','monitorar','monitorar o pc','monitoramento de emergência','monitoramento de emergencia'}:
            await service.monitor(service.Monitor(enabled=True));return reply('Monitor de recursos ativado, senhor. Vou acompanhar CPU, memória e disco enquanto esta sessão estiver aberta.',mode='monitor')
        if text in {'desativar monitoramento','parar monitoramento'}:
            await service.monitor(service.Monitor(enabled=False));return reply('Monitor de recursos desativado, senhor.',mode='monitor')
        simulations={'simular falha':'service_unavailable','simular serviço indisponível':'service_unavailable','simular servico indisponivel':'service_unavailable','simular disco':'disk_pressure','simular recuperação':'recovery_integrity','simular recuperacao':'recovery_integrity'}
        if text in simulations:
            record=await service.simulation(service.Simulation(scenario=simulations[text]));return reply('Simulação concluída em ambiente isolado, senhor. Nenhuma falha foi provocada no computador.',mode='simulation',result=record)
        if text in {'mostrar cofre','consultar cofre','listar backups','meus backups','cofre'}:
            records=await asyncio.to_thread(service.vault_list)
            return reply(f"Há {len(records)} cópias disponíveis no cofre, senhor. Posso recuperar a mais recente em uma nova pasta na área de trabalho." if records else 'O cofre ainda não tem cópias, senhor. Diga crie um backup da pasta e informe o caminho que deseja proteger.',mode='vault')
        actions={
            'segurança máxima':'security_max','seguranca maxima':'security_max','ativar segurança máxima':'security_max','ativar seguranca maxima':'security_max','ative toda a segurança':'security_max','ative toda a seguranca':'security_max',
            'varredura completa':'defender_full','faça uma varredura completa':'defender_full','faca uma varredura completa':'defender_full','varredura rápida':'defender_quick','varredura rapida':'defender_quick',
            'atualizar proteção':'defender_update','atualizar protecao':'defender_update','atualizar assinaturas':'defender_update',
            'verificar integridade profunda':'integrity_verify','verifique a integridade':'integrity_verify','verificar arquivos do windows':'integrity_verify',
            'reparar windows':'windows_repair','recuperar windows':'windows_repair','repare o windows':'windows_repair',
            'limpar temporários':'cleanup_temp','limpar temporarios':'cleanup_temp','limpeza segura':'cleanup_temp','limpa tudo':'cleanup_temp','limpe tudo':'cleanup_temp','limpar tudo':'cleanup_temp','otimizar o pc':'cleanup_temp'}
        prepared_payload=None;question=None
        if text in actions:
            action=actions[text];prepared_payload=service.Prepare(action=action)
            questions={
                'cleanup_temp':'Vou limitar a limpeza a {file_count} temporários deste usuário, com mais de sete dias. Vou guardar uma cópia antes de remover. Documentos, programas e configurações não serão apagados. Deseja fazer essa limpeza, senhor?',
                'security_max':'Posso atualizar as assinaturas e iniciar uma varredura completa. O Defender poderá colocar ameaças em quarentena. Não vou modificar políticas nem prometer proteção total. Deseja iniciar, senhor?',
                'defender_full':'A varredura completa pode levar tempo e consumir recursos. O Defender poderá colocar ameaças em quarentena. Deseja iniciar, senhor?',
                'defender_quick':'Posso executar uma varredura rápida. O Defender poderá colocar ameaças em quarentena. Deseja iniciar, senhor?',
                'defender_update':'Deseja atualizar as assinaturas do Microsoft Defender, sem alterar políticas de proteção, senhor?',
                'integrity_verify':'Posso verificar arquivos protegidos e a imagem do Windows, sem reparar arquivos. A análise pode demorar. Deseja iniciar, senhor?',
                'windows_repair':'Posso executar a recuperação da imagem e dos arquivos protegidos do Windows. Isso pode baixar componentes e substituir arquivos corrompidos, sem rollback automático. Não reiniciarei o computador. Deseja executar esse reparo, senhor?'}
            question=questions[action]
        elif text.startswith(('crie um backup da pasta ','criar backup da pasta ','backup da pasta ')):
            # Preserve case and punctuation inside the explicitly chosen path.
            match=re.search(r'(?:crie um |criar )?backup da pasta\s+(.+)',payload.text,re.IGNORECASE)
            if match:prepared_payload=service.Prepare(action='backup',path=match.group(1).strip().strip('"'));question='Vou copiar {file_count} arquivos da pasta escolhida para o cofre. Credenciais conhecidas ficam de fora; revise o conteúdo, pois nomes não detectam todos os segredos. Deseja criar o backup, senhor?'
        elif text in {'recuperar na área de trabalho','recuperar na area de trabalho','faça a recuperação na área de trabalho','faca a recuperacao na area de trabalho','recuperar último backup','recuperar ultimo backup'}:
            records=await asyncio.to_thread(service.vault_list)
            if not records:return reply('Não existe uma cópia para recuperar, senhor. Preciso de um backup real; não vou inventar uma recuperação.')
            newest=max(records,key=lambda item:item['created_at']);prepared_payload=service.Prepare(action='restore',backup_id=newest['id'],destination='desktop')
            question='Vou recuperar {file_count} arquivos da cópia mais recente em uma nova pasta na área de trabalho, sem substituir os originais. Deseja continuar, senhor?'
        if prepared_payload:
            try:prepared=await asyncio.to_thread(service.prepare_action,prepared_payload)
            except (ValueError,OSError) as error:
                message=str(error)
                if 'administradora' in message:return reply('Esta sessão não tem acesso de administrador, senhor. Não posso executar esse comando elevado nem contornar a confirmação do Windows. Posso continuar com o diagnóstico disponível.')
                if 'Nenhum temporario' in message:return reply('Não encontrei temporários elegíveis com mais de sete dias, senhor. Não vou ampliar a limpeza para documentos ou programas.')
                return reply('Não consegui preparar essa ação com segurança, senhor. Pode haver uma operação em andamento, falta de permissão, arquivo alterado ou fonte indisponível. Nada foi iniciado.')
            conversation['pending']=prepared['id'];return reply(question.format(**prepared['details']),mode='question',confirmation_id=prepared['id'],expires_in=prepared['expires_in'],scope=prepared['details'],action=prepared_payload.action)
        return reply('Posso apresentar o diagnóstico, monitorar recursos, consultar o cofre, simular falhas, preparar uma limpeza de temporários ou uma varredura do Defender, senhor. Reparos exigem administrador e uma confirmação específica. Qual ação deseja?',mode='options')
