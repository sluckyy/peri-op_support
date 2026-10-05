"""A stand-in for anthropic.Anthropic used by the interviewer tests --
no network. Each queued item is either a dict (returned as the JSON text
block), a raw string (returned verbatim, e.g. to simulate malformed
output), or an Exception instance (raised from create()). A callable
`responder(kwargs)` can be used instead of a queue for routing by prompt.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Callable


class FakeMessages:
    def __init__(self, queue: list[Any] | None = None,
                 responder: Callable[[dict[str, Any]], Any] | None = None,
                 stop_reason: str = "end_turn"):
        self.queue = list(queue or [])
        self.responder = responder
        self.stop_reason = stop_reason
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        item = self.responder(kwargs) if self.responder else self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        text = item if isinstance(item, str) else json.dumps(item)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        )


class FakeLLM:
    def __init__(self, queue: list[Any] | None = None,
                 responder: Callable[[dict[str, Any]], Any] | None = None,
                 stop_reason: str = "end_turn"):
        self.beta = SimpleNamespace(messages=FakeMessages(queue, responder, stop_reason))

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.beta.messages.calls


def is_extraction_call(kwargs: dict[str, Any]) -> bool:
    return "Patient's reply" in kwargs["messages"][0]["content"]
