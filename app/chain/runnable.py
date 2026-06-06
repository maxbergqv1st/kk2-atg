from __future__ import annotations

from abc import abstractmethod
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict


class Runnable(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    def invoke(self, data: Any) -> Any: ...

    def __or__(self, other: Runnable) -> RunnableSequence:
        left = self.steps if isinstance(self, RunnableSequence) else [self]
        right = other.steps if isinstance(other, RunnableSequence) else [other]
        return RunnableSequence(steps=left + right)

    def __ror__(self, other: Runnable) -> RunnableSequence:
        left = other.steps if isinstance(other, RunnableSequence) else [other]
        right = self.steps if isinstance(self, RunnableSequence) else [self]
        return RunnableSequence(steps=left + right)


class RunnableLambda(Runnable):
    func: Callable[[Any], Any]

    def invoke(self, data: Any) -> Any:
        return self.func(data)


class RunnableSequence(Runnable):
    steps: list[Runnable]

    def invoke(self, data: Any) -> Any:
        for step in self.steps:
            data = step.invoke(data)
        return data
