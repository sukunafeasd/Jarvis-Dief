"""Check UI postconditions without claiming to have inspected rendered pixels."""
from core.pin_targets import pin_target
import json


def verify_result(action,value,result,setting=''):
    if not isinstance(result,dict):return {'ok':False,'error':'Resposta da interface invalida. Consulte inspect antes de continuar.'}
    result=dict(result)
    if not result.get('ok'):
        result['recovery']='Consulte inspect; use IDs e alvos atuais. Nao anuncie sucesso nem repita a mesma acao sem verificar o estado.'
        return result
    screen=result.get('screen')
    if not isinstance(screen,dict):return result
    presentation=screen.get('presentation',{})
    workspace=screen.get('workspace',{})
    pins=screen.get('pinned_previews',[])
    actual={item.get('kind') for item in pins}
    residual=[];checks=[]
    if action=='clear':
        checks=[not presentation.get('visible'),not workspace.get('terminal_open'),not workspace.get('execution_open'),
                not any(item.get('visible') and not item.get('pinned') for item in screen.get('visual_scene',{}).get('elements',[]))]
        residual=[str(item.get('kind')) for item in pins]
        residual.extend('holograma:'+str(item['id']) for item in screen.get('visual_scene',{}).get('elements',[])
            if item.get('pinned') and item.get('id'))
        for name,state in screen.get('protocols',{}).items():
            if state.get('active') or state.get('visible'):residual.append('protocolo:'+name)
        if screen.get('daily_refresh',{}).get('visible'):residual.append('atualizacao_do_dia')
        result['scope']='conteudo_temporario'
        result['preserved']=residual
    elif action in ('pin','unpin'):
        key=pin_target(value) or presentation.get('kind') or 'data'
        checks=[key in actual if action=='pin' else key not in actual]
    elif action=='close_terminal' or action=='close' and value=='terminal':
        checks=[not workspace.get('terminal_open')]
    elif action=='close' and value=='execution':checks=[not workspace.get('execution_open')]
    elif action=='close':checks=[not presentation.get('visible')]
    elif action=='move_pin':
        key=pin_target(value)
        selected=next((item for item in pins if item.get('kind')==key),None)
        viewport=screen.get('scene_viewport',screen.get('pin_layout',{}).get('viewport',{}))
        width,height=viewport.get('width',0),viewport.get('height',0)
        if screen.get('layout_animating'):
            result['note']='Posicionamento ainda em transicao. Consulte inspect antes de confirmar a posicao final.'
        elif setting in ('row','column') and pins:
            axis='y' if setting=='row' else 'x'
            values=[item.get('bounds',{}).get(axis) for item in pins]
            checks=[all(isinstance(n,(int,float)) for n in values) and max(values)-min(values)<=2]
        elif selected and width and height:
            bounds=selected.get('bounds',{})
            checks=[all(key in bounds for key in ('x','y','width','height'))]
            if all(checks):
                checks.append(bounds['x']>=0 and bounds['y']>=0 and bounds['x']+bounds['width']<=width+2 and bounds['y']+bounds['height']<=height+2)
                try:requested=json.loads(setting)
                except (ValueError,TypeError):requested=None
                if isinstance(requested,dict):
                    checks.extend(abs(bounds[name]-requested[name]*(width if name in ('x','width') else height))<=2
                        for name in ('x','y','width','height') if name in requested)
                    result['resolved_bounds']=bounds
                elif setting:
                    checks=[]
        elif not selected:checks=[False]
    elif action=='move':
        if screen.get('layout_animating'):
            result['note']='Holograma em movimento. Consulte inspect para confirmar o enquadramento final.'
        else:
            bounds=screen.get('avatar_bounds',{});width=screen.get('scene_viewport',{}).get('width',0)
            if width and 'x' in bounds and 'width' in bounds:
                center=(bounds['x']+bounds['width']/2)/width
                if value in ('left','right'):checks=[center<.48 if value=='left' else center>.52]
                elif value=='center' and not presentation.get('visible'):checks=[abs(center-.5)<=.025]
                else:
                    result['note']='A composicao foi solicitada, mas o alinhamento final nao foi verificado. Consulte inspect e os bounds reais.'
            else:checks=[False]
    verified=all(checks) if checks else None
    result['verification']={'source':'application_state','pixels_checked':False,
        'postcondition_verified':verified,'layout_animating':bool(screen.get('layout_animating'))}
    if verified is False:
        result.update(ok=False,error='A interface nao confirmou o resultado solicitado.',
            recovery='Use este screen ou consulte inspect. Corrija o alvo/estado antes de tentar novamente; nao diga que concluiu.')
    elif action=='clear':
        result['note']='Limpeza limitada ao conteudo temporario. Fixados, protocolos e atualizacao do dia listados em preserved continuam presentes; nao diga que removeu tudo.'
    return result
