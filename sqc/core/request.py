import logging
import time
import threading
import queue
from contextlib import ExitStack
from typing import Any, Callable, Optional

from .timer import Timer

__all__ = ["RequestHandler", "Request", "RequestTimeout"]


class RequestTimeout(Exception):

    ...


class Request:

    timeout: float = 4.0

    def __init__(self, target: Callable) -> None:
        self._target: Callable = target
        self._ready: threading.Event = threading.Event()
        self._result: Optional[Any] = None
        self._exc: Optional[Exception] = None

    def __call__(self, *args, **kwargs) -> None:
        try:
            self._result = self._target(*args, **kwargs)
        except Exception as exc:
            self._exc = exc
            logging.exception(exc)
        finally:
            self._ready.set()

    def get(self, timeout: float = None) -> Any:
        if timeout is None:
            timeout = self.timeout
        if self._ready.wait(timeout=timeout):
            if self._exc is not None:
                raise self._exc
            return self._result
        raise RequestTimeout(f"Request timeout: {self._target}")


class RequestHandler:

    def __init__(self, context_provider=None) -> None:
        self.interval: float = 1.0
        self.context_provider = context_provider
        self._queue: queue.Queue = queue.Queue()
        self._shutdown: threading.Event = threading.Event()
        self._thread = threading.Thread(target=self.event_loop)

    def start(self) -> None:
        self._thread.start()

    def submit(self, target: Callable) -> None:
        self._queue.put_nowait(Request(target))

    def insert_scheduled_requests(self) -> None:
        ...

    def request_stop(self) -> None:
        self._shutdown.set()

    @property
    def is_running(self) -> bool:
        return not self._shutdown.is_set()

    def event_loop(self) -> None:
        while self.is_running:
            try:
                t = Timer()
                with ExitStack() as stack:
                    if self.context_provider:
                        context = stack.enter_context(self.context_provider)
                    else:
                        context = None
                    while self.is_running:
                        self.handle_request(context, timeout=1.0)
                        if t.delta() > self.interval:
                            self.insert_scheduled_requests()
                            t.reset()
            except Exception as exc:
                logging.exception(exc)
                time.sleep(1.)
            time.sleep(.250)  # throttle

    def handle_request(self, context: Any, timeout: float) -> None:
        try:
            request: Request = self._queue.get(timeout=timeout)
            self._queue.task_done()
        except queue.Empty:
            ...
        else:
            request(context)

    def shutdown(self) -> None:
        self._shutdown.set()
        self._thread.join()
