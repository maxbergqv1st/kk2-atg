from __future__ import annotations

from abc import abstractmethod
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

I = TypeVar("I")
O = TypeVar("O")


class Runnable(BaseModel, Generic[I, O]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    def invoke(self, data: I) -> O: ...

    def __or__(self, other: Runnable) -> RunnableSequence:
        left = self.steps if isinstance(self, RunnableSequence) else [self]
        right = other.steps if isinstance(other, RunnableSequence) else [other]
        return RunnableSequence(steps=left + right)

    def __ror__(self, other: Runnable) -> RunnableSequence:
        left = other.steps if isinstance(other, RunnableSequence) else [other]
        right = self.steps if isinstance(self, RunnableSequence) else [self]
        return RunnableSequence(steps=left + right)


class RunnableLambda(Runnable[I, O]):
    func: Callable[[I], O]

    def invoke(self, data: I) -> O:
        return self.func(data)


class RunnableSequence(Runnable[Any, Any]):
    steps: list[Runnable]

    def invoke(self, data: Any) -> Any:
        for step in self.steps:
            data = step.invoke(data)
        return data
