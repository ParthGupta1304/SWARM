"""Version 1 wire contracts shared with the runtime and dashboard."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

Nonempty = Annotated[str, Field(min_length=1)]
Severity = Literal["critical", "high", "medium", "low", "info"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    schema_version: Literal[1] = 1


class Request(Contract):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    path: Nonempty
    query: dict[str, str | int | float | bool] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    json_body: JsonValue = None

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        parsed = urlsplit(value)
        if not value.startswith("/") or value.startswith("//") or parsed.netloc or parsed.scheme:
            raise ValueError(
                "path must be relative to the configured target origin, e.g. /checkout"
            )
        if parsed.fragment or parsed.query or "\\" in value or any(ord(c) < 32 for c in value):
            raise ValueError(
                "use query for URL parameters; fragments and control characters forbidden"
            )
        return value

    @field_validator("headers")
    @classmethod
    def no_credentials(cls, headers: dict[str, str]) -> dict[str, str]:
        secret_headers = {
            "authorization",
            "cookie",
            "set-cookie",
            "x-api-key",
            "proxy-authorization",
        }
        if any(k.lower() in secret_headers for k in headers):
            raise ValueError(
                "inject credentials per agent at replay time; do not record auth headers"
            )
        return headers


class Event(Contract):
    event_id: Nonempty = Field(default_factory=lambda: str(uuid4()))
    run_id: Nonempty
    seed: int = Field(ge=0)
    round: int = Field(ge=0)
    sequence: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_id: Nonempty
    role: Nonempty
    tool: Nonempty
    request: Request
    response_status: int | None = Field(default=None, ge=100, le=599)
    response_body_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    db_changes: list[dict[str, JsonValue]] = Field(default_factory=list)
    latency_ms: float = Field(default=0, ge=0)
    tokens_used: int = Field(default=0, ge=0)
    concurrency_group: Nonempty | None = None
    error: str | None = None

    @field_validator("timestamp")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(UTC)


class ReplayAction(Contract):
    event_id: Nonempty
    agent_id: Nonempty
    request: Request
    expected_status: int | None = Field(default=None, ge=100, le=599)
    acceptable_statuses: list[Annotated[int, Field(ge=100, le=599)]] = Field(default_factory=list)


class ReplayStep(Contract):
    """Actions inside a step start together; steps finish in sequence."""

    actions: list[ReplayAction] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_agents(self) -> ReplayStep:
        agents = [action.agent_id for action in self.actions]
        if len(set(agents)) != len(agents):
            raise ValueError("one agent cannot execute two simultaneous actions")
        return self


class ReplayPlan(Contract):
    seed: int = Field(ge=0)
    steps: list[ReplayStep] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_events(self) -> ReplayPlan:
        ids = [action.event_id for step in self.steps for action in step.actions]
        if len(ids) != len(set(ids)):
            raise ValueError("replay event ids must be unique")
        return self


class Finding(Contract):
    id: Nonempty = Field(default_factory=lambda: str(uuid4()))
    run_id: Nonempty
    title: Nonempty
    severity: Severity
    type: Literal["single-user", "emergent"]
    evidence_events: list[Nonempty] = Field(min_length=1)
    involved_agents: list[Nonempty] = Field(min_length=1)
    minimal_repro_sequence: ReplayPlan
    oracle_triggered: Nonempty
    verified: bool = False
    mapped_bug_id: Nonempty | None = None
    suggested_fix: str | None = None
    evidence: list[dict[str, JsonValue]] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_evidence(self) -> Finding:
        actions = [a for step in self.minimal_repro_sequence.steps for a in step.actions]
        if set(self.evidence_events) != {a.event_id for a in actions}:
            raise ValueError("evidence_events must match replay action event ids")
        if set(self.involved_agents) != {a.agent_id for a in actions}:
            raise ValueError("involved_agents must match replay action agents")
        if self.type == "emergent" and len(set(self.involved_agents)) < 2:
            raise ValueError("emergent findings require at least two agents")
        return self
