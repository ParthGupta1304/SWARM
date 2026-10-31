"""Local configuration and shared provider pacing; never expose credentials."""

import os
import time
from pathlib import Path
from threading import Lock

import yaml
from dotenv import load_dotenv


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
    if "api.groq.com" in config.provider_base_url:
        key = os.getenv("GROQ_API_KEY") or os.getenv(config.api_key_env)
    else:
        key = os.getenv(config.api_key_env)
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

    def wait(self, prompt_estimate, output_cap, cancelled=None):
        from swarm.budget import BudgetExhausted

        required = prompt_estimate + output_cap
        if required > self.tokens_per_minute:
            raise BudgetExhausted("Prompt exceeds configured per-minute provider capacity")
        while True:
            if cancelled and cancelled():
                raise BudgetExhausted("Run stopped before provider dispatch")
            with self.lock:
                now = time.monotonic()
                self.tokens = min(
                    self.tokens_per_minute,
                    self.tokens + (now - self.updated) * self.tokens_per_minute / 60,
                )
                self.updated = now
                if now >= self.next_request and self.tokens >= required:
                    self.tokens -= required
                    self.next_request = now + 60 / self.requests_per_minute
                    return required
            time.sleep(0.1)

    def finish(self, reservation, actual_tokens):
        with self.lock:
            self.tokens = min(self.tokens_per_minute, self.tokens + reservation - actual_tokens)
