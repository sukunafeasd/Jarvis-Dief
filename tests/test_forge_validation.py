import hashlib
import tempfile
import unittest
from pathlib import Path
from core.forge.preview import PreviewServer
from core.forge_validation import validate_candidate

class RendererTests(unittest.TestCase):
    def render(self,source):
        with tempfile.TemporaryDirectory(prefix='forge-render-') as folder:
            root=Path(folder);data=source.encode();(root/'index.html').write_bytes(data)
            server=PreviewServer()
            try:
                url=server.publish(root,{'index.html':hashlib.sha256(data).hexdigest()},'index.html')
                return validate_candidate(url)
            finally:server.close()

    def test_valid_opaque_sandbox_does_not_trigger_playwright_serviceworker_error(self):
        result=self.render('''<!doctype html><body style="margin:0;background:black"><canvas id="c" width="500" height="300"></canvas><script>
        let blocked=false;try{void navigator.serviceWorker}catch(error){blocked=true}
        if(!blocked)throw Error('Service worker unexpectedly accessible');
        let ctx=document.getElementById('c').getContext('2d');ctx.fillStyle='#00ff88';ctx.fillRect(20,20,200,200);
        </script>''')
        self.assertEqual(result['console_errors'],[])
        self.assertTrue(all(result[key] for key in ('syntax','assets','initialized','nonblank','framing')))

    def test_real_script_error_is_not_hidden(self):
        result=self.render('<!doctype html><body style="background:black;color:white">Teste<script>throw Error("Erro real de teste")</script>')
        self.assertFalse(result['syntax']);self.assertTrue(result['console_errors'])
