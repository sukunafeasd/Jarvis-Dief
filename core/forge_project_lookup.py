"""Read saved project metadata without entering Forja or starting Codex."""
import json
import re
from core.protocol_commands import normalize


def requested(text):
    value=normalize(text)
    if not re.search(r'\bforja\b',value) or not re.search(r'\bprojetos?\b',value):return False
    return bool(re.search(r'\b(?:tem|tenho|tinha|existe|existem|havia|ha|liste|lista|mostre|mostrar|procure|consultar|quais|algum|alguns)\b',value)) and not bool(re.match(r'^(?:crie|criar|ative|ativar|abra|abrir|apague|exclua)\b',value))


def lookup(root=None):
    from core.local_data import ROOT
    from core.forge.files import pinned,identifier
    base=(ROOT/'forge') if root is None else root
    items=[];errors=0
    for folder,filename,kind in [('projects','manifest.json','project'),('library','artifact.json','artifact')]:
        directory=base/folder
        if not directory.exists():continue
        with pinned(directory) as target:
            children=list(target.iterdir())
        for child in children:
            try:
                if not child.is_dir():continue
                identifier(child.name)
                with pinned(child/filename) as file:
                    if file.stat().st_size>1024*1024:raise ValueError('Oversized project metadata')
                    data=json.loads(file.read_text('utf-8'));modified=file.stat().st_mtime
                if not isinstance(data,dict) or data.get('id')!=child.name or not isinstance(data.get('name'),str):raise ValueError('Invalid project identity')
                name=data['name'][:200]
                state=str(data.get('state') or ('saved' if kind=='artifact' else 'unknown'))
                label={'idle':'iniciado','running':'em andamento','completed':'concluido','error':'com falha','saved':'salvo na biblioteca','cancelled':'interrompido'}.get(state,'estado registrado: '+state)
                items.append({'id':'forge:'+kind+':'+child.name,'title':name,'detail':name+' - '+label+'.',
                              'source':'Projetos locais da Forja' if kind=='project' else 'Biblioteca local da Forja',
                              'project_id':data.get('project_id') if kind=='artifact' else child.name,'kind':kind,'state':state,'modified':modified})
            except (OSError,ValueError,TypeError,KeyError):errors+=1
    projects={item['project_id'] for item in items if item['kind']=='project'}
    items=[item for item in items if item['kind']=='project' or item['project_id'] not in projects]
    items.sort(key=lambda item:-item['modified'])
    return {'ok':not errors,'partial':bool(errors and items),'items':items,'total':len(items),'errors':errors,'source':'Projetos locais da Forja'}


def narration(result):
    from core.conversation_memory import redact
    items=result.get('items',[])
    if not items:
        return ('Nao consegui verificar todos os projetos locais da Forja, senhor.' if not result.get('ok') else
                'Nao encontrei projetos iniciados ou salvos na Forja deste computador, senhor. Nao vou confundir planos de conversa com um projeto existente.')
    opening=('Consegui ler parte da biblioteca, senhor. ' if result.get('partial') else 'Sim, senhor. ')
    details=' '.join(redact(item['detail']) for item in items[:3])
    extra=(' Ha mais '+str(len(items)-3)+' projetos; posso continuar a lista.' if len(items)>3 else '')
    return opening+details+extra
