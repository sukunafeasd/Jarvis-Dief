"""Native settings/cards QA using disposable data and no account connections."""
import os
import sys
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ['QT_QPA_PLATFORM']='windows'
os.environ['DIEF_JARVIS_DATA_DIR']=tempfile.mkdtemp(prefix='dief-observatory-data-')
import ui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from test_observatory_settings import ObservatorySettingsTests, OUTPUT


def wait_for(predicate, seconds=15):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        QApplication.processEvents()
        if predicate():return
        QTest.qWait(100)
    raise AssertionError('Timed out waiting for renderer')


def main():
    app=QApplication(['DIEF visual validation']);app.setStyle('Fusion');app.setQuitOnLastWindowClosed(False)
    case=ObservatorySettingsTests();case.app=app
    report={};exceptions=[]
    original_hook=sys.excepthook
    sys.excepthook=lambda kind,value,tb:exceptions.append(kind.__name__+': '+str(value))
    try:
        case.setUp();hub=case.hub;window=case.window
        hub.name.setText('chefe');hub.city.setText('Porto Alegre, RS');hub.selected_color='#ff303b'
        hub.visual.setCurrentIndex(1);hub.interests.setPlainText('Tecnologia, ciência, notícias do Brasil')
        hub.show();hub.resize(1366,900);hub.open_page('profile')
        wait_for(lambda:hub.core_preview.view is not None and hub.core_preview.view._ready)
        from core.spatial_view import SpatialCoreView
        report['core_view_count']=len(hub.core_preview.findChildren(SpatialCoreView));assert report['core_view_count']==1
        QTest.qWait(500)
        assert hub.grab().save(str(OUTPUT/'native-profile.png'))
        a=hub.core_preview.view.grab().toImage();QTest.qWait(500);b=hub.core_preview.view.grab().toImage()
        report['core_moves']=a!=b
        colored=sum(1 for y in range(0,b.height(),2) for x in range(0,b.width(),2)
                    if b.pixelColor(x,y).red()>b.pixelColor(x,y).blue()*1.5 and b.pixelColor(x,y).red()>90)
        report['core_pixels']=colored;assert colored>150
        hub.open_page('connections');app.processEvents()
        report['hidden_core_poll_stopped']=not hub.core_preview.view._health.isActive()
        assert report['hidden_core_poll_stopped']
        case.test_responsive_connections_and_search_keep_actions_accessible()
        hub.resize(1366,900);hub.open_page('profile');QTest.qWait(300)
        report['core_poll_resumes']=hub.core_preview.view._health.isActive();assert report['core_poll_resumes']
        hub.showMinimized();QTest.qWait(150)
        report['minimized_core_poll_stopped']=not hub.core_preview.view._health.isActive();assert report['minimized_core_poll_stopped']
        hub.showNormal();hub.close();app.processEvents()
        window.resize(1366,900);window.show();window._overlay.hide()
        weather={'kind':'weather','title':'CLIMA','city':'Porto Alegre, RS','temperature':20.4,'condition':'Chuva',
                 'code':61,'humidity':92,'wind':12,'rain':85,'narrationDriven':False,
                 'forecast':[{'date':'2026-10-'+str(15+i),'max':23+i,'min':18,'rain':i*20,'code':code} for i,code in enumerate((61,2,0,61))]}
        samples=[weather,{'kind':'tasks','title':'TAREFAS','count':2,'items':[{'title':'Revisar projeto'},{'title':'Organizar documentos'}]},
                 {'kind':'system','title':'SISTEMA','cpu_percent':32,'ram_percent':61,'gpu_percent':28,'process_count':120,'uptime':'2h'}]
        for model in samples:window._pin_data(model)
        wait_for(lambda:all(p['view'] and p['view']._ready for p in window._pin_previews.values()),25)
        QTest.qWait(2000)
        for kind,pin in window._pin_previews.items():
            assert pin['widget'].grab().save(str(OUTPUT/f'native-pin-{kind}.png'))
        report['pins_ready']=True;report['exceptions']=exceptions;assert not exceptions
        report['passed']=report['core_moves'] and report['pins_ready']
        assert report['passed']
    finally:
        case.doCleanups();sys.excepthook=original_hook
        (OUTPUT/'native-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'output':str(OUTPUT),**report}),flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
