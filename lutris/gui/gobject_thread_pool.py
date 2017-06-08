import queue
import threading
from multiprocessing import cpu_count
from gi.repository import GLib

work_queue = queue.Queue()


class ThreadWorker(threading.Thread):
    def __init__(self, func, data, finish_func):
        super().__init__(daemon=True)
        self.func = func
        self.data = data
        self.finish_func = finish_func

    def run(self):
        try:
            ret_data = self.func(self.data)
            GLib.idle_add(self.finish_func, (self, ret_data))
        except Exception as e:
            print(e)


class ThreadPool:
    def __init__(self, function, completed_function, max_workers=-1):
        # We expect these to be IO heavy tasks, so more threads shouldn't be
        # too harmful, this matches the number of ThreadPoolExecutor in stdlib.
        self._max_workers = cpu_count() * 5 if max_workers <= 0 else max_workers
        self._threads = set()
        self._queue = queue.Queue()
        self._finished_data = []
        self._completed = completed_function
        self._func = function

    def _on_finished(self, user_data):
        thread, data = user_data
        self._threads.remove(thread)
        self._finished_data.append(data)
        self._next_task()

    def _next_task(self):
        if self._queue.empty() and not self._threads:
            self._completed(self._finished_data)
            self._finished_data = []
            return

        try:
            while len(self._threads) < self._max_workers:
                thread = ThreadWorker(self._func, self._queue.get_nowait(), self._on_finished)
                self._threads.add(thread)
                thread.start()
        except queue.Empty:
            # Will run completed func next time around
            pass

    def queue_work(self, data):
        """Submit a list of work to be completed"""
        for d in data:
            self._queue.put_nowait(d)
        self._next_task()

    def clear_work(self):
        if not self._queue.empty():
            self._queue = queue.Queue()
