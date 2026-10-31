"""Thread-safe admission and actual usage accounting for all model calls."""

from __future__ import annotations

import json
from threading import RLock


class BudgetExhausted(RuntimeError):
    pass


class BudgetAccountingError(RuntimeError):
    pass


class TokenBudget:
    def __init__(self, limit: int, *, parent: TokenBudget | None = None):
        if limit <= 0:
            raise ValueError("token budget must be positive")
        self.parent = parent
        self.limit = limit
        self.used = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self._reserved = 0
        self._lock = RLock()
        self.uncertain = False

    def reserve(
        self, messages: list[dict], tools: list[dict] | None, output_cap: int
    ) -> tuple[int, int]:
        # Conservative byte-based bound for byte-token providers, including wire
        # framing allowance. Provider-reported usage is authoritative on return.
        input_bound = (
            len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False).encode())
            + 1024
        )
        with self._lock:
            if self.uncertain:
                raise BudgetAccountingError("previous model call has unknown usage")
            remaining = self.limit - self.used - self._reserved - input_bound
            output = min(output_cap, remaining)
            if output <= 0:
                raise BudgetExhausted("insufficient budget for prompt plus output")
            if self.parent is not None:
                reservation, output = self.parent.reserve(messages, tools, output)
            else:
                reservation = input_bound + output
            self._reserved += reservation
            return reservation, output

    def finish(self, reservation: int, usage) -> int:
        with self._lock:
            self._reserved -= reservation
            if usage is None:
                if self.parent is not None:
                    self.parent.finish(reservation, usage)
                self.uncertain = True
                raise BudgetAccountingError("provider omitted usage; cannot measure this run")
            prompt = getattr(usage, "prompt_tokens", None)
            completion = getattr(usage, "completion_tokens", None)
            total = getattr(usage, "total_tokens", None)
            if (
                not all(isinstance(n, int) for n in (prompt, completion, total))
                or min(prompt, completion, total) < 0
                or total != prompt + completion
            ):
                self.uncertain = True
                if self.parent is not None:
                    self.parent.finish(reservation, usage)
                raise BudgetAccountingError("provider supplied inconsistent usage")
            if self.parent is not None:
                self.parent.finish(reservation, usage)
            self.used += total
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            if total > reservation or self.used + self._reserved > self.limit:
                self.uncertain = True
                raise BudgetAccountingError("provider exceeded its reserved token bound")
            return total

    def fail(self, reservation: int) -> None:
        if self.parent is not None:
            self.parent.fail(reservation)
        with self._lock:
            self._reserved -= reservation
            self.uncertain = True
