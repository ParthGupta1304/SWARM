"""Thread-safe admission and actual usage accounting for all model calls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from threading import RLock


class BudgetExhausted(RuntimeError):
    pass


class BudgetAccountingError(RuntimeError):
    @property
    def user_message(self):
        return (
            "The provider's token usage could not be accounted for safely. "
            "The run stopped without inventing usage or cost."
        )


class ProviderCallError(BudgetAccountingError):
    """Safe provider diagnostics: never include raw SDK bodies, prompts or keys."""

    def __init__(self, status: int | None, code: str = "unspecified"):
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        self.code = (
            code
            if code
            in {
                "tool_use_failed",
                "invalid_api_key",
                "rate_limit_exceeded",
                "model_not_found",
                "permission_denied",
                "insufficient_quota",
                "context_length_exceeded",
                "invalid_request_error",
                "json_validate_failed",
                "account_deactivated",
                "billing_hard_limit_reached",
                "tokens_exceeded",
            }
            else "unspecified"
        )
        super().__init__(self.user_message)

    @property
    def user_message(self):
        if self.status == 401:
            detail = (
                "The provider rejected the API key. Update the key in local .env "
                "before starting a new run."
            )
        elif self.status == 403:
            detail = (
                "The provider denied access. Check this account's model permissions "
                "and restrictions."
            )
        elif self.status == 429:
            detail = (
                "The provider rate limit or account quota was reached. Wait for its "
                "reset or check account limits."
            )
        elif self.status == 400 and self.code == "tool_use_failed":
            detail = (
                "The model generated a malformed native tool call. This is a "
                "model-output error, not an API-key quota error."
            )
        elif self.status == 400 and self.code == "json_validate_failed":
            detail = (
                "The model generated invalid JSON that the provider could not validate. "
                "This is a model-output error, not an API-key error."
            )
        elif self.status == 400:
            detail = (
                "The provider rejected the request. Check the configured model and "
                "supported request options."
            )
        elif self.status and self.status >= 500:
            detail = (
                "The provider is temporarily unavailable. Try a new run after the service recovers."
            )
        else:
            detail = (
                "The provider request failed or timed out. Check connectivity and try a new run."
            )
        suffix = f" HTTP {self.status}" if self.status else ""
        return (
            f"{detail}{suffix} ({self.code}). "
            "Usage for that failed request is unknown; the run was stopped safely."
        )


@dataclass(frozen=True)
class UsageCounts:
    prompt: int
    completion: int
    total: int
    cached: int
    cache_reported: bool


def usage_counts(usage) -> UsageCounts:
    if usage is None:
        raise BudgetAccountingError("provider omitted usage; cannot measure this run")
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    total = getattr(usage, "total_tokens", None)
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None)
    if isinstance(details, dict):
        cached = details.get("cached_tokens")
    reported = cached is not None
    cached = cached if reported else 0
    if (
        not all(type(n) is int for n in (prompt, completion, total, cached))
        or min(prompt, completion, total, cached) < 0
        or total != prompt + completion
        or cached > prompt
    ):
        raise BudgetAccountingError("provider supplied inconsistent usage")
    return UsageCounts(prompt, completion, total, cached, reported)


class TokenBudget:
    def __init__(
        self,
        limit: int,
        *,
        parent: TokenBudget | None = None,
        max_dollars: float | None = None,
        input_price: float = 0,
        output_price: float = 0,
        cached_input_price: float | None = None,
    ):
        if limit <= 0:
            raise ValueError("token budget must be positive")
        self.parent = parent
        self.limit = limit
        self.used = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_prompt_tokens = 0
        self.cache_reported_calls = 0
        self.calls = 0
        self._reserved = 0
        self._lock = RLock()
        self.uncertain = False
        self.failure: BudgetAccountingError | None = None
        self.max_dollars = max_dollars
        self.input_price, self.output_price = input_price, output_price
        self.cached_input_price = input_price if cached_input_price is None else cached_input_price

    @property
    def cost_usd(self):
        return (
            (self.prompt_tokens - self.cached_prompt_tokens) * self.input_price
            + self.cached_prompt_tokens * self.cached_input_price
            + self.completion_tokens * self.output_price
        ) / 1e6

    def summary(self):
        with self._lock:
            return {
                "model_calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "cached_prompt_tokens": self.cached_prompt_tokens,
                "cache_reported_calls": self.cache_reported_calls,
                "cache_reporting": "reported"
                if self.calls and self.cache_reported_calls == self.calls
                else "partial"
                if self.cache_reported_calls
                else "unreported",
                "cost_usd": self.cost_usd,
            }

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
                raise self.failure or BudgetAccountingError("previous model call has unknown usage")
            remaining = self.limit - self.used - self._reserved - input_bound
            price = max(self.input_price, self.output_price, self.cached_input_price)
            if self.max_dollars is not None and price:
                monetary_tokens = int((self.max_dollars - self.cost_usd) * 1e6 / price)
                remaining = min(remaining, monetary_tokens - self._reserved - input_bound)
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
            try:
                counts = usage_counts(usage)
            except BudgetAccountingError as exc:
                self.fail(reservation, exc)
                raise
            self._reserved -= reservation
            if self.parent is not None:
                self.parent.finish(reservation, usage)
            self.used += counts.total
            self.prompt_tokens += counts.prompt
            self.completion_tokens += counts.completion
            self.cached_prompt_tokens += counts.cached
            self.calls += 1
            self.cache_reported_calls += int(counts.cache_reported)
            if counts.total > reservation or self.used + self._reserved > self.limit:
                self.uncertain = True
                self.failure = BudgetAccountingError("provider exceeded its reserved token bound")
                raise self.failure
            return counts.total

    def fail(self, reservation: int, error: BudgetAccountingError | None = None) -> None:
        if self.parent is not None:
            self.parent.fail(reservation, error)
        with self._lock:
            self._reserved -= reservation
            self.uncertain = True
            if self.failure is None:
                self.failure = error

    def release(self, reservation: int) -> None:
        """Release a call cancelled before it reaches the provider."""
        if self.parent is not None:
            self.parent.release(reservation)
        with self._lock:
            self._reserved -= reservation
