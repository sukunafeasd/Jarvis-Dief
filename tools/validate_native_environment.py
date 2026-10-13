"""Executa Qt/WebEngine real com perfil temporario e sem conectar a IA."""
import os
import sys
import json
import traceback
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='windows'
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tests'))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import test_fui_screens
app=QApplication(sys.argv)
fixture=test_fui_screens.AllSettingsPagesTests();fixture.app=app
fixture.setUp()
window=fixture.window;window.resize(1366,768);window.hud.hud_style='core'
OUTPUT=BASE/'validation/environment-second-audit';OUTPUT.mkdir(parents=True,exist_ok=True)
errors=[];results=[];ticks=0


def exception(kind,error,tb):
    errors.append({'type':kind.__name__,'frames':[{'file':Path(item.filename).name,'line':item.lineno,'function':item.name} for item in traceback.extract_tb(tb)]})
    finish()


sys.excepthook=exception


def capture(label,continuation):
    window._layout_scene(False)
    window.grab().save(str(OUTPUT/(label+'.png')))
    collected={}
    def got(name,result):
        collected[name]=result
        if len(collected)==2:
            results.append({'label':label,**collected})
            continuation()
    window._space_view.page().runJavaScript('window.spaceDiagnostics && window.spaceDiagnostics()',lambda result:got('space',result))
    window.hud._spatial_core.page().runJavaScript('window.hologramDiagnostics && window.hologramDiagnostics()',lambda result:got('core',result))


steps=iter(['Saturno','analise','execucao','foco','normal','Saturno','clear'])


def step():
    value=next(steps,None)
    if value is None:finish();return
    request={'action':'clear' if value=='clear' else 'environment','value':'' if value=='clear' else value,'done':__import__('threading').Event()}
    window._apply_interface_request(request)
    if not request['result']['ok']:errors.append(request['result'])
    QTimer.singleShot(1900,lambda:capture(value,step))


def poll():
    global ticks
    ticks+=1
    if ticks>250:errors.append({'error':'Tempo limite para renderizadores prontos'});finish();return
    if window._environment.started:
        window._apply_state('SPEAKING')
        capture('entry-distant',lambda:QTimer.singleShot(1000,lambda:capture('entry-middle-1',
            lambda:QTimer.singleShot(1400,lambda:capture('entry-middle-2',
                lambda:QTimer.singleShot(2200,lambda:capture('entry-arrived',step)))))))
    else:QTimer.singleShot(100,poll)


finished=False
def finish():
    global finished
    if finished:return
    finished=True
    if not errors:
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        window.showFullScreen()
        target=window.hud._spatial_core.focusProxy() or window.hud._spatial_core
        QTest.keyClick(target,Qt.Key.Key_F11)
        if window.isFullScreen():errors.append({'error':'F11 nao saiu de tela cheia no WebEngine'})
        QTest.keyClick(target,Qt.Key.Key_F11)
        if not window.isFullScreen():errors.append({'error':'F11 nao voltou a tela cheia no WebEngine'})
        distant=next((frame for frame in results if frame['label']=='entry-distant'),{})
        arrived=next((frame for frame in results if frame['label']=='entry-arrived'),{})
        if distant.get('core',{}).get('travel',0)<10 or arrived.get('core',{}).get('travel',1)!=0:
            errors.append({'error':'Aproximacao do nucleo nao confirmada'})
        middle=[frame for frame in results if frame['label'].startswith('entry-middle')]
        if len(middle)!=2 or not all(frame.get('core',{}).get('coreVisible') for frame in middle):
            errors.append({'error':'Nucleo ausente durante aproximacao'})
        elif middle[0]['core']['travel']<=middle[1]['core']['travel']:
            errors.append({'error':'Camera nao avancou nos quadros intermediarios'})
        modes={'analise':'analysis','execucao':'execution','foco':'focus','normal':'assistant','Saturno':'exploration','clear':'assistant'}
        for frame in results:
            expected=modes.get(frame['label'])
            if expected and frame.get('space',{}).get('mode')!=expected:errors.append({'error':'Modo divergente','label':frame['label']})
            if frame['label']=='clear' and frame.get('space',{}).get('planet') is not None:errors.append({'error':'Planeta nao foi limpo'})
    (OUTPUT/'result.json').write_text(json.dumps({'errors':errors,'frames':results},indent=2),encoding='utf-8')
    fixture.tearDown();app.quit()


QTimer.singleShot(100,poll)
QTimer.singleShot(45000,lambda:(errors.append({'error':'Limite global de validacao'}),finish()))
app.exec()
print(json.dumps({'ok':not errors,'captures':len(results),'errors':errors}))
sys.exit(1 if errors else 0)
