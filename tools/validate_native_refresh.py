"""Isolated native refresh lifecycle; no accounts or AI calls."""
import os
import sys
import json
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='windows'
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tests'))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
import test_fui_screens
app=QApplication(sys.argv)
fixture=test_fui_screens.AllSettingsPagesTests();fixture.app=app;fixture.setUp()
window=fixture.window;window.resize(1366,768);window._ui_sounds.enabled=False
OUTPUT=BASE/'validation/daily-refresh-native';OUTPUT.mkdir(parents=True,exist_ok=True)
errors=[];checks=[];finished=False
model={'kind':'status','id':'native-refresh','refreshTransaction':True,'title':'ATUALIZANDO O DIA',
       'completed':0,'total':3,'items':[{'title':name,'status':'working','detail':'Consultando fonte'} for name in ('Noticias','Agenda','Clima')]}


def finish():
    global finished
    if finished:return
    finished=True
    (OUTPUT/'result.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
    fixture.tearDown();app.quit()


sys.excepthook=lambda kind,error,tb:(errors.append({'type':kind.__name__}),finish())


def start():
    window._show_manifestation(model)
    QTimer.singleShot(4000,held)


def held():
    window._show_manifestation({'kind':'weather','temperature':19})
    if not window._content_panel.isVisible() or window._presentation['model']['id']!='native-refresh':errors.append({'check':'persistent-refresh'})
    checks.append('refresh-remains-visible-and-rejects-unrelated-data')
    window.grab().save(str(OUTPUT/'collecting.png'))
    updated={**model,'completed':2,'items':[dict(item,status='ok' if index<2 else 'working') for index,item in enumerate(model['items'])]}
    window._show_manifestation(updated)
    QTimer.singleShot(500,progress)


def progress():
    window._content_spatial.page().runJavaScript('document.querySelector("[role=progressbar]")?.getAttribute("aria-valuenow")',got_progress)


def got_progress(value):
    if value!='67':errors.append({'check':'real-progress','value':value})
    checks.append('native-progress-matches-two-of-three-sources')
    window.grab().save(str(OUTPUT/'progress.png'))
    window._show_manifestation({'kind':'tasks','count':2,'narrationDriven':True,'refreshOwner':'native-refresh','items':[{'title':'Tarefa de teste'}]})
    window._apply_state('SPEAKING');window._advance_presentation(.2);window._apply_state('LISTENING')
    if window._settle_timer.isActive():errors.append({'check':'chapter-expiry'})
    checks.append('summary-chapter-does-not-expire-mid-transaction')
    window._show_manifestation({'kind':'status-end','id':'native-refresh'})
    if window._refresh_lock is not None:errors.append({'check':'release-lock'})
    checks.append('transaction-releases-after-summary')
    finish()


QTimer.singleShot(3000,start)
QTimer.singleShot(18000,lambda:(errors.append({'check':'timeout'}),finish()))
app.exec()
print(json.dumps({'ok':not errors,'checks':checks,'errors':errors}))
sys.exit(1 if errors else 0)
