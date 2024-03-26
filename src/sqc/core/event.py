from typing import List, Callable

__all__ = ["Event"]


class Event:

    __slots__ = ["targets"]

    def __init__(self):
        self.targets: List[Callable] = []

    def add(self, target: Callable) -> None:
        if target not in self.targets:
            self.targets.append(target)

    def remove(self, target: Callable) -> None:
        if target in self.targets:
            self.targets.remove(target)

    def __call__(self, *args, **kwargs) -> None:
        for target in self.targets:
            target(*args, **kwargs)
