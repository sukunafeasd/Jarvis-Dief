"""One runtime shared by settings, voice and saved-artifact views."""
import threading
import json
import time
_factory_lock=threading.RLock()
_catalog_stamp=None
_catalog=[]
_catalog_read_at=0.


def saved_artifacts_named(name):
    """Resolve persisted names without starting Codex or waiting for its work queue."""
    from core.local_data import ROOT
    from core.protocol_commands import normalize
    global _catalog_stamp,_catalog,_catalog_read_at
    library=ROOT/'forge'/'library'
    try:stamp=(str(library),library.stat().st_mtime_ns)
    except OSError:return []
    with _factory_lock:
        now=time.monotonic()
        if stamp!=_catalog_stamp or now-_catalog_read_at>=2:
            from core.forge.files import pinned
            records=[]
            try:
                with pinned(library) as folder:
                    for child in folder.iterdir():
                        try:
                            with pinned(child/'artifact.json') as path:
                                if path.stat().st_size>65536:continue
                                item=json.loads(path.read_text('utf-8'))
                            if isinstance(item,dict) and item.get('id')==child.name and isinstance(item.get('name'),str):
                                records.append({'id':item['id'],'name':item['name']})
                        except (OSError,ValueError,KeyError,TypeError):continue
            except (OSError,ValueError):return []
            _catalog_stamp=stamp;_catalog=records;_catalog_read_at=now
        return [dict(item) for item in _catalog if normalize(item['name'])==normalize(name)]

def runtime_for(window):
    with _factory_lock:
        runtime=getattr(window,'_forge_runtime',None)
        if runtime is None:
            from core.forge import Runtime
            runtime=Runtime();window._forge_runtime=runtime
        return runtime
