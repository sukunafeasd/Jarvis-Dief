"""Non-blocking release checks; network workers never access Qt widgets."""
import queue
import threading
import time

from core.distribution import latest_release
from core.update_status import release_status


class UpdateWatch:
    def __init__(self, current, fetch=latest_release, interval=1800):
        self.current=current
        self.fetch=fetch
        self.interval=interval
        self.next_check=0
        self.busy=False
        self.results=queue.Queue()
        self.seen=set()
        self.failures=0

    def tick(self, now=None):
        now=time.monotonic() if now is None else now
        available=None
        while not self.results.empty():
            release=self.results.get_nowait()
            self.busy=False
            if release is None:
                self.failures=min(self.failures+1,5)
                self.next_check=now+min(300,30*(2**(self.failures-1)))
                continue
            self.failures=0
            self.next_check=now+self.interval
            if release and release_status({'current':self.current},release)[0]=='available':
                if release['version'] not in self.seen:
                    self.seen.add(release['version']);available=release
        if not self.busy and now>=self.next_check:
            self.busy=True;self.next_check=now+self.interval
            def query():
                try:release=self.fetch()
                except Exception:release=None
                self.results.put(release)
            threading.Thread(target=query,daemon=True,name='UpdateWatch').start()
        return available
