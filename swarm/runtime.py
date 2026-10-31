"""Round coordinator and measured isolated/swarm benchmark callback."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event as StopEvent
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adapters.openapi import OpenAPIAdapter
from bench.metrics import BenchmarkRun
from detect.contracts import Event, Finding
from detect.store import EventStore
from memory.store import MemoryStore
from swarm.agent import AgentLoop, Decision
from swarm.budget import BudgetAccountingError, TokenBudget
from swarm.events import EventSlot, RunEvents


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    agent_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    tools: list[str] = Field(min_length=1)
    completion_tool: str | None = "checkout"
    token_budget: int = Field(default=20000, gt=0)
    max_steps: int = Field(default=40, gt=0)
    seeded_user_id: int | None = Field(default=None, gt=0)
    fixed_arguments: dict[str, str | int | bool] = Field(default_factory=dict)


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    project: str = Field(default="bazaar", min_length=1)
    spec: str = "openapi.json"
    app_base_url: str = "http://localhost:8001"
    provider_base_url: str = "http://localhost:11434/v1"
    model: str = "qwen2.5-coder:7b"
    api_key_env: str = "SWARMTEST_API_KEY"
    seed: int = Field(default=1, ge=0)
    max_rounds: int = Field(default=40, gt=0)
    token_budget: int = Field(default=60000, gt=0)
    kill_file: str | None = None
    # Set both to zero only for a provider known to be free, e.g. local Ollama.
    input_cost_per_million: float = Field(ge=0)
    output_cost_per_million: float = Field(ge=0)
    personas: list[Persona] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_actors(self) -> RunConfig:
        if len({p.agent_id for p in self.personas}) != len(self.personas):
            raise ValueError("persona agent IDs must be unique")
        return self


@dataclass(frozen=True)
class RoundWindow:
    run_id: str
    seed: int
    round: int
    condition: str
    events: tuple[Event, ...]  # current target lifetime only, never across isolated resets
    latest: tuple[Event, ...]


@dataclass
class RuntimeHooks:
    # Must reset only a caller-owned disposable application target, never the event DB.
    reset: Callable[[int], Awaitable[None]] | None = None
    detect: Callable[[RoundWindow], Awaitable[list[Finding]]] | None = None
    close: Callable[[], Awaitable[None]] | None = None
    progress: Callable[[dict], Awaitable[None]] | None = None


@dataclass
class RunResult:
    run_id: str
    condition: str
    seed: int
    model: str
    token_budget: int
    tokens_used: int
    cost_usd: float
    elapsed_s: float
    agents: list[dict]
    findings: list[Finding] = field(default_factory=list)
    finding_times_s: dict[str, float] = field(default_factory=dict)
    stopped: bool = False

    def benchmark_run(self) -> BenchmarkRun:
        if self.stopped:
            raise ValueError("a killed run cannot be scored as a completed benchmark")
        return BenchmarkRun.model_validate(
            {key: value for key, value in vars(self).items() if key not in {"agents", "stopped"}}
        )


class RunCoordinator:
    def __init__(
        self,
        config: RunConfig,
        store: EventStore,
        *,
        api_key: str = "ollama",
        hooks: RuntimeHooks | None = None,
        memory: MemoryStore | None = None,
        jsonl_path: str | Path | None = None,
    ):
        self.config, self.store, self.api_key = config, store, api_key
        self.hooks = hooks or RuntimeHooks()
        self.memory, self.jsonl_path = memory, jsonl_path
        self._stop = StopEvent()

    def stop(self) -> None:
        """Cooperative stop: finish in-flight calls, dispatch no further round."""
        self._stop.set()

    def stopping(self) -> bool:
        return self._stop.is_set() or bool(
            self.config.kill_file and Path(self.config.kill_file).exists()
        )

    async def run(
        self, condition: Literal["isolated", "swarm"] = "swarm", *, run_id: str | None = None
    ) -> RunResult:
        if condition not in {"isolated", "swarm"}:
            raise ValueError("condition must be isolated or swarm")
        if condition == "isolated" and self.hooks.reset is None:
            raise ValueError("isolated execution requires a disposable-target reset hook")
        config = self.config
        run_id = run_id or str(uuid4())
        if await asyncio.to_thread(self.store.events, run_id):
            raise ValueError("coordinated runs require a fresh run ID")
        started = time.perf_counter()
        events = await asyncio.to_thread(
            RunEvents, self.store, run_id, config.seed, self.jsonl_path
        )
        budget = TokenBudget(config.token_budget)
        adapter = OpenAPIAdapter(config.spec, config.app_base_url)
        agents = []

        async def publish(status: str, round_num: int = -1):
            if self.hooks.progress:
                await self.hooks.progress(
                    {
                        "run_id": run_id,
                        "condition": condition,
                        "seed": config.seed,
                        "status": status,
                        "round": round_num,
                        "tokens_used": budget.used,
                        "token_budget": budget.limit,
                        "cost_usd": (
                            budget.prompt_tokens * config.input_cost_per_million
                            + budget.completion_tokens * config.output_cost_per_million
                        )
                        / 1e6,
                        "elapsed_s": time.perf_counter() - started,
                        "agents": [agent.summary() for agent in agents],
                    }
                )

        try:
            for persona in config.personas:
                agent = AgentLoop(
                    agent_id=persona.agent_id,
                    role=persona.role,
                    objective=persona.objective,
                    score_desc=f"Complete {persona.completion_tool or 'the assigned objective'}",
                    provider_base_url=config.provider_base_url,
                    model=config.model,
                    api_key=self.api_key,
                    app_base_url=config.app_base_url,
                    run_id=run_id,
                    seed=config.seed,
                    tool_definitions=adapter.get_tool_definitions(persona.tools),
                    adapter=adapter,
                    events=events,
                    budget=TokenBudget(persona.token_budget, parent=budget),
                    completion_tool=persona.completion_tool,
                    seeded_user_id=persona.seeded_user_id,
                    fixed_arguments=persona.fixed_arguments,
                )
                agent.max_steps = persona.max_steps
                agents.append(agent)
                if self.memory is not None:
                    saved = await asyncio.to_thread(
                        self.memory.recall_agent_memory, config.project, agent.agent_id
                    )
                    if saved:
                        import json

                        agent.history = [
                            {"role": "user", "content": "Prior run memory: " + json.dumps(saved)}
                        ]
            await publish("running")
            random.Random(config.seed).shuffle(agents)
            findings, times = [], {}
            batches = [agents] if condition == "swarm" else [[agent] for agent in agents]
            for batch in batches:
                if self.stopping():
                    break
                if self.hooks.reset:
                    await self.hooks.reset(config.seed)
                for agent in batch:
                    if not await asyncio.to_thread(agent.start):
                        raise RuntimeError(f"actor setup failed: {agent.agent_id}: {agent.error}")
                causal: list[Event] = []
                for round_num in range(config.max_rounds):
                    if self.stopping():
                        break
                    active = [
                        agent
                        for agent in batch
                        if not agent.done
                        and not agent.stopped
                        and agent.total_tool_calls < agent.max_steps
                    ]
                    if not active:
                        break
                    decisions = await asyncio.gather(
                        *[asyncio.to_thread(agent.decide) for agent in active],
                        return_exceptions=True,
                    )
                    errors = [value for value in decisions if isinstance(value, BaseException)]
                    if errors:
                        raise RuntimeError("model decision failed") from errors[0]
                    await publish("running", round_num)
                    if budget.uncertain:
                        raise BudgetAccountingError("run aborted: model usage could not be bounded")
                    ready = [
                        (agent, decision)
                        for agent, decision in zip(active, decisions, strict=True)
                        if decision is not None
                    ]
                    if not ready:
                        continue
                    if self.stopping():
                        break
                    slots = events.reserve(
                        round_num,
                        [agent.agent_id for agent, _ in ready],
                        concurrent=condition == "swarm",
                    )
                    barrier = asyncio.Barrier(len(ready))

                    async def execute(
                        actor: AgentLoop,
                        decision: Decision,
                        slot: EventSlot,
                        gate: asyncio.Barrier = barrier,
                    ):
                        await gate.wait()
                        return await asyncio.to_thread(actor.execute, decision, slot)

                    # Await every write before detection or resetting the application.
                    outcomes = await asyncio.gather(
                        *[
                            execute(agent, decision, slot)
                            for (agent, decision), slot in zip(ready, slots, strict=True)
                        ],
                        return_exceptions=True,
                    )
                    errors = [value for value in outcomes if isinstance(value, BaseException)]
                    if errors:
                        raise RuntimeError("round failed; partial events retained") from errors[0]
                    latest = sorted(outcomes, key=lambda event: event.sequence)
                    causal.extend(latest)
                    await publish("running", round_num)
                    if self.hooks.detect:
                        window = RoundWindow(
                            run_id, config.seed, round_num, condition, tuple(causal), tuple(latest)
                        )
                        detected = await self.hooks.detect(window)
                        known_events = {event.event_id for event in causal}
                        for finding in detected:
                            if (
                                finding.run_id != run_id
                                or finding.minimal_repro_sequence.seed != config.seed
                                or not set(finding.evidence_events) <= known_events
                            ):
                                raise ValueError(
                                    "detector returned evidence outside current target window"
                                )
                            if finding.id in times:
                                continue
                            findings.append(finding)
                            times[finding.id] = time.perf_counter() - started
                            if self.memory is not None and finding.verified:
                                await asyncio.to_thread(
                                    self.memory.save_finding, config.project, finding
                                )
            if self.memory is not None:
                for agent in agents:
                    await asyncio.to_thread(
                        self.memory.save_agent_memory,
                        config.project,
                        agent.agent_id,
                        agent.summary(),
                    )
            cost = (
                budget.prompt_tokens * config.input_cost_per_million
                + budget.completion_tokens * config.output_cost_per_million
            ) / 1_000_000
            await publish("stopped" if self.stopping() else "completed")
            return RunResult(
                run_id,
                condition,
                config.seed,
                config.model,
                config.token_budget,
                budget.used,
                cost,
                time.perf_counter() - started,
                [agent.summary() for agent in agents],
                findings,
                times,
                self.stopping(),
            )
        except Exception:
            await publish("failed")
            raise
        finally:
            try:
                if self.hooks.close is not None:
                    await self.hooks.close()
            finally:
                for agent in agents:
                    await asyncio.to_thread(agent.close)


def benchmark_callback(
    config: RunConfig,
    store: EventStore,
    *,
    hook_factory: Callable[[RunConfig], RuntimeHooks],
    api_key: str = "ollama",
    memory: MemoryStore | None = None,
) -> Callable[[str, int, int], BenchmarkRun]:
    """Bridge into bench.run_benchmark; invoke from synchronous code.

    A fresh hook/pipeline instance per run prevents cross-condition deduplication.
    Agent memory is deliberately disabled for fair cold-start comparisons.
    """
    if memory is not None:
        raise ValueError("benchmark conditions must start without cross-run agent memory")

    def run_condition(condition: str, seed: int, token_budget: int) -> BenchmarkRun:
        updated = RunConfig.model_validate(
            {**config.model_dump(), "seed": seed, "token_budget": token_budget}
        )
        hooks = hook_factory(updated)
        if hooks.reset is None or hooks.detect is None:
            raise ValueError("benchmark requires explicit reset and detection/verification hooks")
        result = asyncio.run(
            RunCoordinator(updated, store, api_key=api_key, hooks=hooks).run(condition)
        )
        return result.benchmark_run()

    return run_condition
