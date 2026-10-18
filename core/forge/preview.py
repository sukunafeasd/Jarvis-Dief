"""Read-only loopback server for a single verified immutable project revision."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
import secrets
import threading
from urllib.parse import unquote, urlsplit

from .files import read_file, relative


class PreviewServer:
    def __init__(self):
        self.lock = threading.RLock()
        self.routes = {}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.serve(False)

            def do_HEAD(self):
                self.serve(True)

            def serve(self, head):
                expected_host = '127.0.0.1:%s' % self.server.server_port
                if self.headers.get('Host') != expected_host:
                    self.send_error(403)
                    return
                try:
                    self.connection.settimeout(2)
                    path = unquote(urlsplit(self.path).path, errors='strict')
                    parts = path.split('/', 2)
                    if len(parts) != 3:
                        raise ValueError('Invalid route')
                    token, name = parts[1:]
                    relative(name)
                    with owner.lock:
                        route = owner.routes.get(token)
                        if not route or name not in route['files']:
                            raise ValueError('Unknown asset')
                        data = read_file(route['root'], name)
                        if hashlib.sha256(data).hexdigest() != route['files'][name]:
                            raise ValueError('Asset changed after validation')
                    self.send_response(200)
                    self.send_header('Content-Type', mimetypes.guess_type(name)[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(len(data)))
                    self.send_header('Cache-Control', 'no-store')
                    # Sandboxed documents have opaque origins; local ES modules need CORS.
                    self.send_header('Access-Control-Allow-Origin', 'null')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.send_header('Referrer-Policy', 'no-referrer')
                    self.send_header('Content-Security-Policy',
                                     "sandbox allow-scripts; default-src 'self' data: blob:; "
                                     "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                                     "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                                     "form-action 'none'; object-src 'none'; base-uri 'none'")
                    self.end_headers()
                    if not head:
                        self.wfile.write(data)
                except (ValueError, OSError, UnicodeError):
                    self.send_error(404)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.server.block_on_close = False
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .1},
                                       name='ForgePreview', daemon=True)
        self.thread.start()

    def publish(self, root, files, entrypoint, keep_url=None, category='project'):
        relative(entrypoint)
        if not entrypoint.endswith('.html') or entrypoint not in files:
            raise ValueError('An HTML entrypoint in this revision is required')
        token = secrets.token_urlsafe(24)
        with self.lock:
            # Last stable revision and latest candidate can coexist, bounded to two routes.
            keep_token = urlsplit(keep_url or '').path.split('/')[1:2]
            if category == 'project':
                self.routes = {k: v for k, v in self.routes.items()
                               if k in keep_token or v['category'] == 'library'}
            elif sum(v['category'] == 'library' for v in self.routes.values()) >= 32:
                raise ValueError('Too many pinned library previews; close unused previews')
            self.routes[token] = {'root': root, 'files': dict(files), 'category': category}
        return 'http://127.0.0.1:%s/%s/%s' % (self.server.server_port, token, entrypoint)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        with self.lock:
            self.routes.clear()
