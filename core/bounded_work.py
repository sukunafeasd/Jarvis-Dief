"""A bounded daemon pool: a timeout never creates replacement worker threads."""
import queue
import threading
from concurrent.futures import Future


class BoundedWork:
    def __init__(self, workers=8, capacity=24, name='JarvisSearch'):
        self.queue=queue.Queue(maxsize=capacity)
        self.stop=threading.Event()
        self.lock=threading.Lock()
        self.workers=workers;self.name=name;self.threads=[]

    def submit(self, callback):
        future=Future()
        with self.lock:
            if self.stop.is_set():raise RuntimeError('Consultas encerradas')
            self.queue.put_nowait((future,callback))
            if not self.threads:
                self.threads=[threading.Thread(target=self._work,daemon=True,name=self.name) for _ in range(self.workers)]
                for thread in self.threads:thread.start()
        return future

    def _work(self):
        while not self.stop.is_set():
            try:future,callback=self.queue.get(timeout=.25)
            except queue.Empty:continue
            try:
                if self.stop.is_set():future.cancel();continue
                if not future.set_running_or_notify_cancel():continue
                try:future.set_result(callback())
                except BaseException as error:future.set_exception(error)
            finally:self.queue.task_done()

    def close(self):
        cancelled=[]
        with self.lock:
            self.stop.set()
            while True:
                try:future,_=self.queue.get_nowait()
                except queue.Empty:break
                cancelled.append(future);self.queue.task_done()
        # Future callbacks run synchronously and may call submit/close again.
        for future in cancelled:future.cancel()
