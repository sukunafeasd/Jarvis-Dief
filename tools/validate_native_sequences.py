"""Sequencias reais de widgets/WebEngine com dados sinteticos e perfil isolado."""
import os
import sys
import json
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='windows'
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tests'))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import test_interface_third_audit
app=QApplication(sys.argv)
fixture=test_interface_third_audit.ThirdInterfaceAudit();fixture.app=app;fixture.setUp()
window=fixture.window;window.resize(1366,768);window.hud.hud_style='core'
window._apply_state('LISTENING')
OUTPUT=BASE/'validation/interface-third-audit';OUTPUT.mkdir(parents=True,exist_ok=True)
errors=[];checks=[];finished=False


def finish():
    global finished
    if finished:return
    finished=True
    (OUTPUT/'native-result.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
    fixture.tearDown();app.quit()


def exception(kind,error,tb):
    errors.append({'type':kind.__name__});finish()


sys.excepthook=exception


def reopened():
    if not window._presentation or not window._content_panel.isVisible():errors.append({'check':'reopen'})
    checks.append('reopen-after-dismiss')
    window.grab().save(str(OUTPUT/'reopened-weather.png'))
    window._content_spatial.page().runJavaScript('getComputedStyle(document.querySelector("main")).opacity',opacity)


def opacity(value):
    if value!='1':errors.append({'check':'reopened-opacity','value':value})
    window._show_manifestation({'kind':'gmail','title':'GMAIL DE TESTE','items':[{'title':'Primeiro registro'},{'title':'Segundo registro'}]})
    fixture.command('focus','2')
    window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
    fixture.command('open','gmail')
    if window._presentation['focus']!=1:errors.append({'check':'history-focus'})
    checks.append('history-focus-preserved')
    QTimer.singleShot(1600,paused)


def paused():
    window.grab().save(str(OUTPUT/'restored-selection.png'))
    window._show_manifestation({'kind':'news','title':'NOTICIAS DE TESTE','narrationDriven':True,'items':[{'title':'Demonstracao sintetica'}]})
    window._apply_state('SPEAKING');window._advance_presentation(.2)
    fixture.command('close','presentation')
    result=fixture.command('resume')
    if not result['ok'] or not window._content_panel.isVisible():errors.append({'check':'resume-visible'})
    checks.append('closed-news-resumes-visible')
    QTimer.singleShot(700,lambda:(window.grab().save(str(OUTPUT/'resumed-news.png')),pins()))


def pins():
    window._show_manifestation({'kind':'gmail','title':'GMAIL DE TESTE','items':[{'title':f'Registro {i+1}'} for i in range(3)]})
    fixture.command('focus','3');fixture.command('pin');window._expand_pin('gmail')
    if window._presentation['focus']!=2:errors.append({'check':'pin-selected-record'})
    checks.append('pin-selected-record-preserved')
    window._show_manifestation({'kind':'weather','title':'CLIMA DE TESTE','temperature':19,'condition':'Nublado'})
    fixture.command('pin')
    window._update_pin('weather',{'kind':'weather','title':'CLIMA DE TESTE','temperature':27,'condition':'Nublado'})
    window._restore_pin()
    if window._presentation['model']['temperature']!=27:errors.append({'check':'pin-latest-data'})
    fixture.command('unpin','gmail')
    if not window._pinned_context or not window._pinned:errors.append({'check':'other-pin-removal'})
    checks.append('pin-latest-data-and-independent-removal')
    window._presentation=None;window._presentation_history=[]
    result=fixture.command('open','weather')
    if not result['ok']:errors.append({'check':'open-without-history'})
    checks.append('saved-pin-opens-without-history')
    QTimer.singleShot(1600,lambda:(window.grab().save(str(OUTPUT/'pinned-weather-latest.png')),operations()))


def operations():
    window._operation_event('app_control:open','running')
    progress=window._execution._progress
    window._operation_event('app_control:open','pending')
    if window._execution._progress!=progress:errors.append({'check':'operation-reveal-reset'})
    checks.append('operation-update-preserves-reveal')
    window._show_manifestation({'kind':'weather','title':'CLIMA DE TESTE','temperature':19})
    if not window._execution.isVisible():errors.append({'check':'manifestation-hides-pending'})
    checks.append('manifestation-preserves-pending-operation')
    window._operation_event('weather_report','finished')
    if window._environment.operation!='pending' or window._execution_settle.isActive():errors.append({'check':'pending-operation'})
    checks.append('pending-operation-survives-other-tool-completion')
    QTimer.singleShot(500,operations_finished)


def operations_finished():
    window.grab().save(str(OUTPUT/'pending-operation.png'))
    window._operation_event('app_control:open','cancelled')
    serial=window._environment.serial
    window._operation_event('app_control:open','finished')
    if window._environment.serial!=serial:errors.append({'check':'cancelled-operation-late-completion'})
    checks.append('late-completion-after-cancellation-ignored')
    window._operation_event('powershell_control','running')
    if not window._execution.isVisible() or 'PowerShell' not in window._execution.status.text():errors.append({'check':'powershell-stage-visible'})
    checks.append('powershell-stage-visible-without-executing-command')
    window._operation_event('powershell_control','cancelled')
    window._pin_data({'kind':'files','title':'ARQUIVOS DE TESTE','items':[],'emptyText':None})
    if 'Nenhum item' not in window._pin_previews['files']['label'].text():errors.append({'check':'empty-pin-fallback'})
    checks.append('null-empty-message-pins-with-readable-fallback')
    window._show_manifestation({'kind':'weather','temperature':float('inf'),'city':{},'forecast':[{'max':float('nan')}]})
    model=window._presentation['model']
    if model['temperature'] is not None or model['city']!='':errors.append({'check':'malformed-weather-normalization'})
    checks.append('invalid-weather-values-do-not-crash-native-panel')
    finish()


def start():
    window._show_manifestation({'kind':'weather','title':'CLIMA DE TESTE','temperature':19,'code':61,'rain':80,'condition':'Chuva'})
    fixture.command('settle');fixture.command('open','weather')
    QTimer.singleShot(1500,reopened)


QTimer.singleShot(3000,start)
QTimer.singleShot(15000,lambda:(errors.append({'check':'timeout'}),finish()))
app.exec()
print(json.dumps({'ok':not errors,'checks':checks,'errors':errors}))
sys.exit(1 if errors else 0)
