"""Verificacao de contas salvas, sem iniciar fluxos de autorizacao."""
import importlib
import threading
from core.connection_states import ConnectionChecks


def saved_checks(plugins):
    from core import gmail_connection as gmail
    from core.whatsapp_web import PROFILE, transport
    from core.resource_policy import EXTERNAL, external_status
    if gmail.status().get('connected'):
        yield 'gmail', gmail.verify
    if PROFILE.exists():
        def whatsapp():
            value = transport.call('status')
            connected = bool(value.get('connected'))
            return {'ok': connected, 'state': 'connected' if connected else 'auth_required' if value.get('needs_link') else 'error',
                    'message': 'Sessao WhatsApp confirmada.' if connected else 'Nao foi possivel confirmar a sessao WhatsApp. Teste ou conecte novamente.'}
        yield 'whatsapp', whatsapp
    for plugin in plugins:
        name = plugin.get('name')
        if name not in EXTERNAL or not plugin.get('valid') or not plugin.get('enabled'):
            continue
        try:
            local = external_status(name)
        except Exception:
            yield name, lambda: {'ok':False,'state':'error','message':'Nao foi possivel consultar a configuracao desta conexao.'}
            continue
        if not (local.get('connected') or local.get('authorization_pending') or name == 'mcp_bridge' and local.get('configured')):
            continue
        if name in ('google_calendar', 'google_drive', 'gmail_compose'):
            from core.google_services import verify
            yield name, lambda name=name: verify(name)
        else:
            module = importlib.import_module('core.' + ('spotify_service' if name == 'spotify_control' else name))
            yield name, module.verify


class ConnectionVerifier:
    def __init__(self, checks=None):
        self.checks = checks or ConnectionChecks()
        self.lock = threading.RLock()
        self.inflight = set()
        self.scanning = False
        self.slots = threading.Semaphore(3)

    def schedule(self, plugins):
        with self.lock:
            if self.scanning:
                return
            self.scanning = True
        def scan():
            try:
                for provider, callback in saved_checks(plugins):
                    self.submit(provider, callback)
            finally:
                with self.lock:
                    self.scanning = False
        threading.Thread(target=scan, daemon=True, name='ConnectionInventory').start()

    def submit(self, provider, callback):
        with self.lock:
            record = self.checks.get(provider)
            if provider in self.inflight or record and not record.get('stale'):
                return False
            generation = self.checks.begin(provider)
            if generation is None:
                return False
            self.inflight.add(provider)
        def run():
            if not self.slots.acquire(timeout=60):
                self.checks.finish(provider,generation,'error','A fila de verificacao demorou demais. Teste novamente.')
                with self.lock:self.inflight.discard(provider)
                return
            try:
                timeout = threading.Timer(60, lambda: self.checks.finish(provider, generation, 'error', 'A verificacao demorou demais. Teste novamente para confirmar a conexao.'))
                timeout.daemon = True
                timeout.start()
                try:
                    value = callback()
                    if isinstance(value, dict):
                        ok = bool(value.get('ok'))
                        state, message = value.get('state', 'connected' if ok else 'error'), value.get('message', '')
                    else:
                        ok, message = value
                        state = 'connected' if ok else 'auth_required'
                except Exception as error:
                    state, message = 'error', 'Nao foi possivel verificar a conexao. Confira a rede ou teste novamente.'
                    if provider in ('google_calendar', 'google_drive', 'gmail_compose', 'spotify_control'):
                        try:
                            module = importlib.import_module('core.' + ('spotify_service' if provider == 'spotify_control' else 'google_services'))
                            details = module.error_details(error)
                            state, message = details['state'], details['message']
                        except Exception:
                            pass
                finally:
                    timeout.cancel()
                    with self.lock:
                        self.inflight.discard(provider)
                self.checks.finish(provider, generation, state, message)
            finally:
                self.slots.release()
        threading.Thread(target=run, daemon=True, name='ConnectionVerify-' + provider).start()
        return True
