"""Local configuration and shared provider pacing; never expose credentials."""

import math
import os
import re
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from threading import Lock

import yaml
from dotenv import dotenv_values, find_dotenv, load_dotenv


def load_config(path):
    from swarm.runtime import RunConfig

    load_dotenv()
    path = Path(path).resolve()
    values = yaml.safe_load(path.read_text())
    for key, env in [("provider_base_url", "SWARMTEST_PROVIDER_URL"), ("model", "SWARMTEST_MODEL")]:
        if os.getenv(env):
            values[key] = os.environ[env]
    values["spec"] = str((path.parent / values.get("spec", "openapi.json")).resolve())
    for field in ("seed_fixture", "invariants"):
        if values.get(field):
            values[field] = str((path.parent / values[field]).resolve())
    if values.get("kill_file"):
        values["kill_file"] = str((path.parent / values["kill_file"]).resolve())
    if os.getenv("BAZAAR_VERSION"):
        values["bazaar_version"] = os.environ["BAZAAR_VERSION"]
    return RunConfig.model_validate(values)


def credential(config):
    # Read local credentials at run admission, without mutating process-wide env.
    # load_dotenv() at startup otherwise leaves a rotated key cached forever.
    path = find_dotenv()
    local = dotenv_values(path) if path else {}

    def current(name):
        return local.get(name) if name in local else os.getenv(name)

    if "api.groq.com" in config.provider_base_url:
        key = current("GROQ_API_KEY") or current(config.api_key_env)
    else:
        key = current(config.api_key_env)
    if not key and config.provider_base_url.startswith(("http://localhost:", "http://127.0.0.1:")):
        return "local"
    if not key:
        raise ValueError("Configure the model API key in local .env")
    return key


class ProviderPacer:
    """Shared token bucket with reserved estimates and actual-usage refunds."""

    def __init__(self, requests_per_minute, tokens_per_minute):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.lock = Lock()
        self.next_request = 0.0
        self.tokens = float(tokens_per_minute)
        self.updated = time.monotonic()
        self.blocked_until = 0.0
        self.wait_seconds = 0.0

    def _refill(self, now):
        self.tokens = min(
            self.tokens_per_minute,
            self.tokens + (now - self.updated) * self.tokens_per_minute / 60,
        )
        self.updated = now

    def wait(self, prompt_estimate, output_cap, cancelled=None):
        from swarm.budget import BudgetExhausted

        required = prompt_estimate + output_cap
        started = time.monotonic()
        while True:
            if cancelled and cancelled():
                raise BudgetExhausted("Run stopped before provider dispatch")
            with self.lock:
                now = time.monotonic()
                if required > self.tokens_per_minute:
                    raise BudgetExhausted("Prompt exceeds configured per-minute provider capacity")
                self._refill(now)
                if now >= max(self.next_request, self.blocked_until) and self.tokens >= required:
                    self.tokens -= required
                    self.next_request = now + 60 / self.requests_per_minute
                    self.wait_seconds += now - started
                    return required
            time.sleep(0.1)

    def finish(self, reservation, actual_tokens):
        with self.lock:
            self._refill(time.monotonic())
            self.tokens = min(self.tokens_per_minute, self.tokens + reservation - actual_tokens)

    def observe(self, headers):
        """Header feedback can lower configured capacity, never raise it."""
        headers = {str(k).lower(): str(v) for k, v in headers.items()}
        with self.lock:
            now = time.monotonic()
            self._refill(now)
            try:
                limit = float(headers.get("x-ratelimit-limit-tokens", "nan"))
                if math.isfinite(limit) and limit > 0:
                    self.tokens_per_minute = min(self.tokens_per_minute, limit)
                    self.tokens = min(self.tokens, self.tokens_per_minute)
            except ValueError:
                pass
            delay = _duration(headers.get("retry-after", ""), http_date=True)
            for resource in ("tokens", "requests"):
                try:
                    remaining = float(headers[f"x-ratelimit-remaining-{resource}"])
                except (KeyError, ValueError):
                    continue
                if not math.isfinite(remaining) or remaining < 0:
                    continue
                if resource == "tokens":
                    self.tokens = min(self.tokens, remaining)
                # Groq's request headers describe daily capacity, not RPM.
                if remaining == 0:
                    delay = max(
                        delay, _duration(headers.get(f"x-ratelimit-reset-{resource}", "")) or 60
                    )
            self.blocked_until = max(self.blocked_until, now + delay)


def _duration(value, *, http_date=False):
    try:
        seconds = float(value)
        return seconds if math.isfinite(seconds) and seconds >= 0 else 0
    except ValueError:
        pass
    parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)", value)
    if parts and "".join(n + unit for n, unit in parts) == value:
        scale = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}
        return sum(float(n) * scale[unit] for n, unit in parts)
    if http_date:
        try:
            return max(0, parsedate_to_datetime(value).timestamp() - time.time())
        except (ValueError, TypeError, OverflowError):
            pass
    return 0


def is_groq_cache(provider_base_url, model):
    from urllib.parse import urlsplit

    return urlsplit(str(provider_base_url)).hostname == "api.groq.com" and model in {
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-safeguard-20b",
    }


def completion_with_headers(client, kwargs):
    """Keep SDK response parsing and expose only rate headers to the pacer."""
    raw = client.chat.completions.with_raw_response.create(**kwargs)
    return raw.parse(), raw.headers
