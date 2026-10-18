"""Factual projection payload shared by the voice tool and the scene."""
import json

LABELS={'defender':'Microsoft Defender','threats':'Ameacas detectadas','firewall':'Firewall','services':'Servicos','startup':'Inicializacao','events':'Eventos criticos'}

def projection(snapshot):
    findings=[]
    for item in snapshot.get('findings',[])[:12]:
        detail=item.get('detail','')
        try: detail=json.loads(detail)
        except (ValueError,TypeError): pass
        findings.append({'id':item.get('id'),'title':LABELS.get(item.get('id'),item.get('title','Observacao')),'severity':item.get('severity','info'),'detail':detail})
    return {'phase':snapshot.get('phase','idle'),'scan':snapshot.get('scan',{}),'telemetry':snapshot.get('telemetry',{}),'findings':findings,
            'vault_count':len(snapshot.get('vault',[])),'vault':snapshot.get('vault',[])[:4],'simulation_count':len(snapshot.get('simulations',[])),
            'monitor':snapshot.get('monitor',{}),'operations':snapshot.get('operations',[])[-6:],
            'confirmation_pending':bool(snapshot.get('confirmation',{}).get('pending')),
            'snapshot_serial':snapshot.get('snapshot_serial',0),
            'last_user_turn':snapshot.get('last_user_turn')}

def monitor_alerts(state):
    if not state.get('monitor',{}).get('enabled'):return []
    latest={event.get('kind'):event for event in state.get('monitor',{}).get('events',[])}
    result=[]
    for key in ('cpu_percent','memory_percent','disk_percent'):
        event=latest.get(key,{});value=state.get('telemetry',{}).get(key)
        if isinstance(value,(float,int)) and value>=event.get('threshold',101):
            result.append({'resource':key,'value':value,'threshold':event['threshold']})
    return result
