from core.essential_plugins import respond
from core import spotify_service as spotify
PLUGIN={'name':'spotify_control','description':'Spotify por API oficial, preferível a cliques quando conectado. search retorna URIs REAIS; play usa uma delas, sem pesquisar no navegador. devices lista dispositivos Spotify Connect, current confirma reprodução. Comando aceito não prova música tocando: verifique current. Requer autorização e condições do Spotify/Premium; sem conta conectada informe, não invente sucesso.',
 'parameters':{'type':'OBJECT','properties':{
    'action':{'type':'STRING','enum':['status','search','devices','current','play','pause','next','previous','volume','transfer']},
    'query':{'type':'STRING','description':'Nome e artista na busca; play tambem aceita query e usa a URI real retornada, abre o aplicativo se faltar dispositivo e verifica a reproducao.'},
    **{key:{'type':'STRING'} for key in ('uri','device_id')},'limit':{'type':'INTEGER'},'volume':{'type':'INTEGER'}},'required':['action']}}
PLUGIN_SETTINGS={'namespace':'spotify_control','title':'Spotify','fields':[
    {'key':'client_id','type':'text','label':'Client ID do aplicativo Spotify (nao e chave da IA)'},
    {'key':'expected_account_id','type':'text','label':'ID da conta desejada (opcional; aparece apos conectar)'},
    {'key':'callback_info','type':'text','label':'Cadastre este retorno no Spotify Developer','default':spotify.REDIRECT,'readonly':True}],
    'setup_url':'https://developer.spotify.com/dashboard','setup_label':'Abrir cadastro de aplicativo Spotify',
    'action':{'label':'Autorizar Spotify','run':lambda values:spotify.connect()}}
def run(parameters,player=None,**kwargs):
    if parameters.get('action')=='status':return respond(spotify.status)
    def execute():
        result=spotify.run(parameters)
        if player and hasattr(player,'update_environment_media'):
            try:
                if 'playback' in result:player.update_environment_media(result['playback'])
                elif result.get('action') in ('pause','next','previous','transfer'):
                    # Accepted is not verified; remove the old visual until current confirms it.
                    player.update_environment_media(None)
            except Exception:
                pass
        return result
    return respond(execute,player if parameters.get('action')=='search' else None,'data','SPOTIFY','spotify_control')
