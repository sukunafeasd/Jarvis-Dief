"""On-demand capture of one authorized HWND; never a full desktop fallback."""
import ctypes
import io
from core.bounded_work import BoundedWork
from core.spectro_perception import foreground

_CAPTURE_WORK=BoundedWork(workers=1,capacity=1,name='EspectroCapture')


def capture(expected,authorized):
    return _CAPTURE_WORK.submit(lambda:_capture(expected,authorized)).result(timeout=6)


def _capture(expected,authorized):
    import win32gui,win32ui
    from ctypes import wintypes
    from PIL import Image
    def valid():
        if not authorized():return False
        current=foreground()
        return current.get('ok') and all(current.get(key)==expected.get(key) for key in ('handle','process_id','app'))
    if not valid():raise ValueError('Captura nao autorizada ou janela alterada.')
    handle=expected['handle']
    if win32gui.IsIconic(handle):raise ValueError('A janela esta minimizada.')
    left,top,right,bottom=win32gui.GetWindowRect(handle);width=right-left;height=bottom-top
    if not 0<width*height<=16000000:raise ValueError('Dimensoes da janela fora do limite.')
    dc=win32gui.GetWindowDC(handle);source=None;memory=None;bitmap=None
    try:
        source=win32ui.CreateDCFromHandle(dc);memory=source.CreateCompatibleDC()
        bitmap=win32ui.CreateBitmap();bitmap.CreateCompatibleBitmap(source,width,height);memory.SelectObject(bitmap)
        api=ctypes.WinDLL('user32',use_last_error=True)
        api.PrintWindow.argtypes=[wintypes.HWND,wintypes.HDC,wintypes.UINT];api.PrintWindow.restype=wintypes.BOOL
        if not valid() or not api.PrintWindow(handle,memory.GetSafeHdc(),2):raise ValueError('O aplicativo nao forneceu uma captura de sua janela.')
        if not valid():raise ValueError('Privacidade ou janela mudou durante a captura. Imagem descartada.')
        image=Image.frombuffer('RGB',(width,height),bitmap.GetBitmapBits(True),'raw','BGRX',0,1)
        if max(image.getextrema()[index][1]-image.getextrema()[index][0] for index in range(3))<3:
            raise ValueError('Captura sem conteudo verificavel. Use os controles de acessibilidade.')
        image.thumbnail((1280,720));buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=82)
        if not valid():raise ValueError('Privacidade ou janela mudou durante a codificacao. Imagem descartada.')
        return buffer.getvalue(),'image/jpeg'
    finally:
        if memory:memory.DeleteDC()
        if source:source.DeleteDC()
        if bitmap:win32gui.DeleteObject(bitmap.GetHandle())
        if dc:win32gui.ReleaseDC(handle,dc)
