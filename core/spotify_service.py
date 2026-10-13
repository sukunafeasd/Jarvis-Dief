"""Spotify Connect via PKCE, sem segredo de cliente e sem cliques."""
import re
import secrets
import threading
import time
from core import integration_tokens as tokens

LOCK=threading.RLock()
REDIRECT='http://127.0.0.1:8767/callback'
SCOPE='user-read-private user-read-playback-state user-modify-playback-state user-read-currently-playing'


class SpotifyProblem(ValueError):
    def __init__(self, message, state='error'):
        super().__init__(message)
        self.state=state


def error_details(error):
    code=getattr(error,'http_status',None)
    reason=str(getattr(error,'reason','') or error).lower()
    if isinstance(error,SpotifyProblem):return {'message':str(error),'state':error.state}
    if code==401:return {'message':'Autorizacao Spotify expirada ou recusada. Use Reconectar para autorizar novamente.','state':'auth_required'}
    if code==403:
        if 'scope' in reason:return {'message':'Falta permissao de controle de reproducao. Reconecte e aceite os acessos solicitados pelo Spotify.','state':'auth_required'}
        return {'message':'Spotify recusou o acesso (403). Confira Premium e se esta conta esta autorizada no aplicativo do Spotify Developer. Reconectar sozinho nao remove esse bloqueio.','state':'error'}
    if code==404:return {'message':'Spotify nao encontrou um dispositivo de reproducao. Abra o Spotify e consulte devices antes de tentar tocar.','state':'error'}
    if code==429:return {'message':'Limite do Spotify atingido. Aguarde antes de testar novamente.','state':'error'}
    if isinstance(error,ValueError):return {'message':str(error),'state':'auth_required' if 'autorize' in reason else 'error'}
    return {'message':'Nao consegui concluir a conexao Spotify. Confira o Client ID e cadastre exatamente o retorno '+REDIRECT+'. Autorize a conta no navegador; salvar a credencial nao autoriza a conta.','state':'error'}


def open_player():
    import os
    try:os.startfile('spotify:')
    except (OSError,AttributeError):raise SpotifyProblem('Nao consegui abrir o Spotify. Abra o aplicativo, entre na conta e tente novamente.')


def playback_device(api, requested=None, launch=False):
    devices=api.devices().get('devices',[])
    if not devices and launch:
        open_player()
        for _ in range(16):
            time.sleep(.5)
            devices=api.devices().get('devices',[])
            if devices:break
    valid=[d for d in devices if d.get('id') and not d.get('is_restricted')]
    if requested:
        chosen=next((d for d in valid if d['id']==requested),None)
        if not chosen:raise SpotifyProblem('Dispositivo solicitado nao esta disponivel. Consulte devices e escolha um ID atual.')
        return chosen['id']
    active=[d for d in valid if d.get('is_active')]
    if len(active)==1:return active[0]['id']
    if len(valid)==1:return valid[0]['id']
    if len(valid)>1:raise SpotifyProblem('Ha mais de um dispositivo Spotify. Consulte devices e informe qual deve tocar; nao escolherei outro aparelho automaticamente.')
    raise SpotifyProblem('Spotify autorizado, mas nenhum dispositivo de reproducao apareceu. Abra o aplicativo e confirme que esta na mesma conta.')


def config():
    from memory.config_manager import get_plugin_config
    return get_plugin_config('spotify_control')


def status():
    try:value=tokens.read('spotify')
    except Exception:value={}
    expected=str(config().get('expected_account_id','')).strip()
    matches=not expected or expected==value.get('jarvis_account_id')
    return {'connected':bool(value.get('refresh_token') and value.get('jarvis_client_id')==config().get('client_id') and matches),
        'configured':bool(config().get('client_id')),'account':value.get('jarvis_account_id','') if matches else ''}


def auth(staged=False):
    from spotipy.cache_handler import CacheHandler
    from spotipy.oauth2 import SpotifyPKCE,start_local_http_server,SpotifyOauthError
    class ProtectedCache(CacheHandler):
        def __init__(self):self.pending=None
        def get_cached_token(self):
            if staged:return self.pending
            value=tokens.read('spotify')
            expected=str(config().get('expected_account_id','')).strip()
            return value if value.get('jarvis_client_id')==config().get('client_id') and (not expected or expected==value.get('jarvis_account_id')) else None
        def save_token_to_cache(self,value):
            if staged:self.pending=dict(value);return
            previous=tokens.read('spotify')
            tokens.write('spotify',{**value,'jarvis_client_id':config().get('client_id'),
                'jarvis_account_id':previous.get('jarvis_account_id','') if previous.get('jarvis_client_id')==config().get('client_id') else ''})
    class BoundedPKCE(SpotifyPKCE):
        def _get_auth_response_local_server(self,port):
            with start_local_http_server(port) as server:
                server.timeout=180;self._open_auth_url();server.handle_request()
                if getattr(server,'state',None)!=self.state:raise SpotifyOauthError('Autorização expirada ou estado inválido.')
                if not server.auth_code:raise SpotifyOauthError('A autorização não foi concluída.')
                return server.auth_code
    client=str(config().get('client_id','')).strip()
    if not re.fullmatch(r'[A-Za-z0-9]{16,128}',client):raise ValueError('Configure o identificador do aplicativo Spotify em Conexões. Cadastre o retorno '+REDIRECT)
    return BoundedPKCE(client_id=client,redirect_uri=REDIRECT,scope=SCOPE,state=secrets.token_urlsafe(32),
        cache_handler=ProtectedCache(),open_browser=True,requests_timeout=15)


def service():
    import spotipy
    manager=auth();cached=manager.cache_handler.get_cached_token()
    if not cached or not manager.validate_token(cached):raise ValueError('Autorize o Spotify nas conexões do Jarvis.')
    return spotipy.Spotify(auth_manager=manager,requests_timeout=15,retries=0,status_retries=0)


def connect():
    with LOCK:
        import spotipy
        manager=auth(staged=True)
        access=manager.get_access_token(check_cache=False)
        profile=spotipy.Spotify(auth=access,requests_timeout=15,retries=0,status_retries=0).current_user()
        identifier=profile.get('id') or profile.get('account_id')
        if not identifier:return False,'Nao consegui identificar a conta Spotify. Conexao anterior preservada.'
        expected=str(config().get('expected_account_id','')).strip()
        if expected and expected!=identifier:return False,'Conta Spotify diferente da solicitada. Conexao anterior preservada.'
        value=manager.cache_handler.get_cached_token()
        if not value or not value.get('refresh_token'):return False,'Autorizacao Spotify incompleta. Conexao anterior preservada.'
        tokens.write('spotify',{**value,'jarvis_client_id':config().get('client_id'),'jarvis_account_id':identifier})
        return True,'Spotify autorizado: '+str(profile.get('display_name') or identifier)+' · '+identifier


def verify():
    api=service();profile=api.current_user()
    identifier=profile.get('id') or profile.get('account_id')
    expected=str(config().get('expected_account_id','')).strip()
    if not identifier or expected and expected!=identifier:return False,'Conta Spotify nao corresponde a conta desejada. Reconecte escolhendo a conta correta.'
    with LOCK:
        saved=tokens.read('spotify')
        if saved:tokens.write('spotify',{**saved,'jarvis_account_id':identifier})
    devices=api.devices().get('devices',[])
    note=' · '+str(len(devices))+' dispositivo(s) de reproducao disponivel(is).'
    if not devices:note=' · Conta autorizada, mas nenhum dispositivo disponivel. Abra o Spotify; ao pedir play, o Jarvis tentara abri-lo.'
    return True,'Spotify confirmado: '+str(profile.get('display_name') or identifier)+' · '+identifier+note


def _run(parameters):
    with LOCK:
        api=service();action=parameters.get('action','current')
        device=parameters.get('device_id') or None
        if action=='search':
            query=str(parameters.get('query','')).strip()
            if not query:raise ValueError('Informe a música ou artista.')
            result=api.search(q=query,type='track',limit=max(1,min(10,int(parameters.get('limit',5)))))
            return {'tracks':[{'id':item['id'],'uri':item['uri'],'title':item['name'],
                'artists':[a['name'] for a in item.get('artists',[])],
                'image':next(iter(item.get('album',{}).get('images',[])),{}).get('url','')}
                for item in result.get('tracks',{}).get('items',[])],
                'complete':not bool(result.get('tracks',{}).get('next'))}
        if action=='devices':return api.devices()
        if action=='current':
            value=api.current_playback()
            return {'playback':value,'playing':bool(value and value.get('is_playing'))}
        if action not in ('play','pause','next','previous','volume','transfer'):raise ValueError('Ação Spotify inválida.')
        if action=='play':
            uri=parameters.get('uri')
            query=str(parameters.get('query','')).strip()
            if not uri and query:
                found=api.search(q=query,type='track',limit=1).get('tracks',{}).get('items',[])
                if not found:raise SpotifyProblem('Nao encontrei essa musica no Spotify. Informe nome ou artista.')
                uri=found[0].get('uri')
                if not uri:raise SpotifyProblem('A busca nao retornou uma URI valida. Nada foi tocado.')
            if uri and not re.fullmatch(r'spotify:track:[A-Za-z0-9]{22}',uri):raise ValueError('Use a URI real da música retornada na pesquisa.')
            device=playback_device(api,device,launch=True)
            api.start_playback(device_id=device,**({'uris':[uri]} if uri else {}))
            playback=None
            for _ in range(8):
                time.sleep(.25)
                playback=api.current_playback()
                if playback and playback.get('is_playing') and (not uri or (playback.get('item') or {}).get('uri')==uri):
                    return {'accepted':True,'verified':True,'action':action,'device_id':device,
                            'playback':playback,
                            'uri':(playback.get('item') or {}).get('uri'),'note':'Reproducao confirmada pela API.'}
            return {'accepted':True,'verified':False,'uncertain':True,'action':action,
                    'note':'Comando enviado uma vez, mas nao confirmei a musica tocando. Consulte current; nao repita automaticamente.'}
        elif action=='pause':api.pause_playback(device_id=device)
        elif action=='next':api.next_track(device_id=device)
        elif action=='previous':api.previous_track(device_id=device)
        elif action=='volume':
            volume=int(parameters.get('volume',-1))
            if not 0<=volume<=100:raise ValueError('Volume deve ficar entre 0 e 100.')
            api.volume(volume,device_id=device)
        else:
            if not device:raise ValueError('Escolha o identificador real obtido em devices.')
            api.transfer_playback(device,force_play=False)
        return {'accepted':True,'action':action,'note':'Comando aceito pela API. Consulte current para confirmar a reprodução; não repita envios sem confirmação.'}


def run(parameters):
    try:return _run(parameters)
    except SpotifyProblem:raise
    except Exception as error:
        details=error_details(error)
        raise SpotifyProblem(details['message'],details['state']) from error
