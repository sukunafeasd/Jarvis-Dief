"""Apresentacao e mensagens de erro comuns as novas integracoes."""
import json


def respond(callback,player=None,kind=None,title=None,tool=None,refresh=None):
    try:
        data=callback();result={'ok':True,**data}
        if player and kind:
            items=data.get('items',data.get('files',data.get('tracks',[])))
            if data.get('event'):items=[data['event']]
            display=[{'id':item.get('id',''),'title':item.get('title') or item.get('summary') or item.get('name',''),
                'detail':item.get('description') or item.get('mimeType') or ', '.join(item.get('artists',[])),
                'due':item.get('start',{}).get('dateTime',item.get('start',{}).get('date',''))} for item in items]
            player.show_manifestation({'kind':kind,'title':title,'items':display,'source':title,'count':len(display),
                'tool':tool,'emptyText':'Nenhum item encontrado nesta consulta.',**({'refresh':refresh} if refresh else {})})
        return json.dumps(result,ensure_ascii=False)
    except Exception as error:
        code=getattr(getattr(error,'resp',None),'status',None) or getattr(error,'http_status',None)
        message=str(error) if isinstance(error,ValueError) else 'Não consegui confirmar a operação ('+type(error).__name__+'). Confira a conexão e as permissões.'
        if code in (401,403):message='O serviço recusou a autorização ou o acesso. Confira a conta, os escopos e as condições do provedor.'
        if code==429:message='Limite do provedor atingido. Aguarde antes de tentar novamente.'
        return json.dumps({'ok':False,'error':message,'uncertain':True,
            'instruction':'Não declare sucesso nem repita automaticamente uma alteração ou envio sem verificar o resultado.'},ensure_ascii=False)


def google_schema(name,title):
    from core import google_services as google
    return {'namespace':name,'title':title,'fields':[
        {'key':'expected_email','label':'Conta Google desejada','type':'text'},
        {'key':'credentials_path','label':'JSON OAuth para computador (vazio usa a credencial do Gmail)','type':'text'}],
        'setup_url':'https://console.cloud.google.com/apis/credentials',
        'setup_label':'Abrir credenciais no Google Cloud',
        'action':{'label':'Autorizar '+title,'run':lambda values:google.connect(name)}}
