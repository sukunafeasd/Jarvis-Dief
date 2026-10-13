"""Opt-in real-provider/real-speaker test; microphone is silent, preferences untouched."""
import asyncio
import json
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main
from ui import JarvisUI,BASE_DIR
from PyQt6.QtCore import QTimer

class SilentMicrophone:
    def __init__(self,**kwargs):pass
    def __enter__(self):return self
    def __exit__(self,*args):pass

main.sd.RawInputStream=SilentMicrophone
main.get_brief_enabled=lambda:False
main.get_wake_word_enabled=lambda:False
ui=JarvisUI(str(BASE_DIR/'core/face_model.obj'))
ui._win.hud.hud_style='core'
assistant=main.JarvisLive(ui)
assistant._dashboard=None
stop=threading.Event()
samples=[];started=time.monotonic();sent=False;complete_at=None;captured=False;report_ok=False

async def background():
    task=asyncio.create_task(assistant.run())
    while not stop.is_set():await asyncio.sleep(.1)
    assistant._session_log=[]
    task.cancel()
    try:await task
    except asyncio.CancelledError:pass

thread=threading.Thread(target=lambda:asyncio.run(background()),daemon=True)
thread.start()

def receive_sample(sample):
    global captured
    if not isinstance(sample,dict):return
    sample['time']=round(time.monotonic()-started,2)
    samples.append(sample)
    if sample.get('partial') and not captured:
        ui._win.grab().save(str(BASE_DIR/'validation/live-news-typing.png'))
        captured=True

def finish():
    global report_ok
    timer.stop()
    model=(ui._win._presentation or {}).get('model',{})
    report={'connected':bool(getattr(ui._win,'_connection_status',{}).get('connected')),
            'news_presented':model.get('kind')=='news','images':sum(bool(item.get('image')) for item in model.get('items',[])),
            'partial_typing_seen':any(sample.get('partial') for sample in samples),
            'pcm_seconds':round(ui._win._presentation_clock.elapsed,2),'samples':samples}
    (BASE_DIR/'validation/live-projection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    ui._win.grab().save(str(BASE_DIR/'validation/live-news-final.png'))
    print('Live projection QA:',{key:value for key,value in report.items() if key!='samples'},flush=True)
    report_ok=report['connected'] and report['news_presented'] and report['partial_typing_seen'] and report['pcm_seconds']>0
    stop.set();ui._win.close();ui._app.quit()

def tick():
    global sent,complete_at
    elapsed=time.monotonic()-started
    if elapsed>45:finish();return
    if not sent and assistant.session:
        sent=True
        ui.on_text_command('Mostre duas notícias recentes sobre ciência usando news_briefing. Apresente a primeira e a segunda brevemente no seu holograma.')
    if (ui._win._presentation or {}).get('model',{}).get('kind')=='news':
        view=ui._win._content_spatial
        if view and view._loaded:
            view.page().runJavaScript("(()=>{const node=document.querySelector('.record.selected h2');const text=node?.textContent||'';const full=node?.getAttribute('aria-label')||'';return {chars:text.length,full:full.length,partial:text.length>0&&text.length<full.length,playback:document.body.dataset.playback,secondaryCore:document.body.dataset.secondaryCore,state:window.presentationStatus?.()}})()",receive_sample)
        if ui._win._presentation_clock.elapsed>2 and not ui._win.hud.speaking:
            complete_at=complete_at or time.monotonic()
            if time.monotonic()-complete_at>1.5:finish()
        else:complete_at=None

timer=QTimer();timer.timeout.connect(tick);timer.start(100)
ui.root.mainloop()
stop.set();thread.join(timeout=5)
sys.exit(0 if report_ok else 1)
