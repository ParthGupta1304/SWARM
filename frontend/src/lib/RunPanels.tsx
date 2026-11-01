import { useState } from "react";
import { useConsole } from "./console";
import { duration, foundIds, money, number, rounds } from "./metrics";
import { Modal } from "./Modal";

export function LiveToolbar() {
  const c = useConsole(),
    [confirm, setConfirm] = useState<"reset" | "benchmark" | null>(null);
  const unavailable =
    !c.connected ||
    !c.config ||
    !c.yaml ||
    !!c.configError ||
    c.pending ||
    c.state?.busy ||
    c.state?.reset_failed;
  const safe = (fn: () => Promise<unknown>) => {
    fn().catch(() => {});
  };
  return (
    <div className="mb-6 border-b border-border pb-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex items-center gap-2 text-[12px] text-muted-foreground">
          <span
            className={`size-2 rounded-full ${c.connected ? "bg-moss" : "bg-amber-600"}`}
          />
          <span role="status">
            {c.connected ? "Connected" : "Reconnecting to local service"}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <label className="min-w-0 flex-1 text-[12px] text-muted-foreground">
          Inspect run
          <select
            aria-label="Inspect run"
            value={c.selected}
            onChange={(e) => c.choose(e.target.value)}
            className="ui-select mt-1 w-full max-w-lg"
          >
            <option value="live">Live workspace</option>
            {c.history.map((row) => (
              <option key={row.run_id} value={row.run_id}>
                {new Date((row.saved_at || 0) * 1000).toLocaleString()} ·{" "}
                {row.condition} · {row.verified_ids.length} distinct ·{" "}
                {row.status}
                {row.model === "scripted-fixture" ? " · scripted" : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            className="ui-primary"
            disabled={!!unavailable}
            onClick={() => safe(() => c.start())}
          >
            Start run
          </button>
          <button
            className="ui-secondary"
            disabled={!c.state?.busy || c.state?.resetting || c.pending}
            onClick={() => safe(() => c.command("/api/stop"))}
          >
            Stop
          </button>
          <button
            className="ui-secondary"
            disabled={!!unavailable}
            onClick={() => setConfirm("benchmark")}
          >
            Run benchmark
          </button>
          <button
            className="ui-secondary text-[#a33737]"
            disabled={
              c.state?.reset_allowed === false ||
              c.state?.resetting ||
              c.pending
            }
            onClick={() => setConfirm("reset")}
          >
            Reset workspace
          </button>
        </div>
      </div>
      {(c.error || c.state?.error || c.run?.agents.some((a) => a.error)) && (
        <p
          role="alert"
          className="mt-4 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          {c.error ||
            c.state?.error ||
            "Some agent sessions ended with errors. Inspect individual agent sessions below for details."}
          {c.run?.agents?.some((a) => a.error?.includes("429"))
            ? " Groq rate limit reached. Wait for the account quota to recover."
            : ""}
        </p>
      )}
      {c.state?.resetting && (
        <p role="status" className="mt-4 rounded-2xl bg-sage p-3 text-sm">
          Stopping active work and resetting this workspace…
        </p>
      )}
      {c.run?.model === "scripted-fixture" && (
        <p className="mt-3 text-[12px] text-[#8a4b14]">
          Scripted rehearsal — decisions and usage are fixtures, not real AI
          discovery.
        </p>
      )}
      {confirm && (
        <Modal
          title={
            confirm === "reset"
              ? "Reset this workspace?"
              : "Run the six-run benchmark?"
          }
          close={() => setConfirm(null)}
        >
          <p className="text-sm leading-relaxed text-muted-foreground">
            {confirm === "reset"
              ? "This permanently deletes local run history, findings, reports, reviews and saved agent memory, then restores seeded Bazaar data. Active work finishes safely first. API keys and configuration are kept; Groq caching and quotas are unaffected."
              : `Runs isolated and swarm conditions across three seeds, at ${c.config?.benchmark_rounds || 3} rounds each. The cap is ${money(c.options?.max_dollars)} per run (${money((c.options?.max_dollars || 0) * 6)} across exploration), with separate budgeted judging overhead. This starts real model requests unless the launcher is scripted.`}
          </p>
          <div className="mt-6 flex justify-end gap-2">
            <button className="ui-secondary" onClick={() => setConfirm(null)}>
              Cancel
            </button>
            <button
              className="ui-primary"
              onClick={() => {
                const fn = confirm === "reset" ? c.reset : () => c.start(true);
                setConfirm(null);
                safe(fn);
              }}
            >
              {confirm === "reset" ? "Reset workspace" : "Start benchmark"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export function ComparisonChart() {
  const c = useConsole();
  const catalog = c.config?.bugs || [],
    ids = foundIds(c.findings);
  const expected = catalog.filter((b) => b.type === "emergent");
  const selected = expected.length
    ? expected.filter((b) => ids.has(b.id)).length / expected.length
    : null;
  const values = (
    [
      ["isolated", "Condition B"],
      ["swarm", "Condition C"],
    ] as const
  ).map(([key, label]) => ({
    label,
    value:
      c.evaluationBenchmark?.conditions[key]?.metrics.emergent_recall?.mean ??
      (c.run?.condition === key ? selected : null),
  }));
  return (
    <figure
      aria-label="Measured emergent bug recall"
      className="mt-4 rounded-2xl border border-border bg-mist/40 p-4"
    >
      <div className="flex h-[110px] items-end justify-around gap-6 border-b border-border bg-[linear-gradient(to_top,transparent_32%,#e9eae3_33%,transparent_34%,transparent_65%,#e9eae3_66%,transparent_67%)]">
        {values.map((row, i) => (
          <div
            key={row.label}
            className="flex h-full w-1/3 flex-col justify-end text-center"
          >
            <span className="mb-1 font-mono text-xs">
              {row.value == null ? "—" : `${(row.value * 100).toFixed(1)}%`}
            </span>
            <div
              className={`mx-auto w-full max-w-24 rounded-t-lg ${i ? "bg-moss" : "bg-meadow"}`}
              style={{
                height: row.value == null ? 0 : Math.max(2, row.value * 85),
              }}
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-around text-[11px] text-muted-foreground">
        {values.map((row) => (
          <span key={row.label}>{row.label}</span>
        ))}
      </div>
      <figcaption className="mt-2 text-[11px] text-muted-foreground">
        {c.historicalEvaluation
          ? "Historical real-AI benchmark · three matched seeds"
          : c.benchmark
            ? c.state?.gate?.source === "scripted-fixture"
              ? "Scripted benchmark · rehearsal only"
              : "Benchmark mean · three matched seeds"
            : "Selected run · the other condition is unmeasured"}
      </figcaption>
    </figure>
  );
}

export function RunPanels() {
  const c = useConsole(),
    r = c.run,
    points = rounds(r?.actions || []),
    [details, setDetails] = useState(false);
  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-[24px] border border-border bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h4 className="font-semibold">Round activity</h4>
          <span className="text-xs text-muted-foreground">
            {r
              ? `${r.status} · ${duration(r.elapsed_s)} · ${number(r.tokens_used)} total tokens · ${r.agents?.reduce((n, a) => n + a.invalid_tool_calls, 0) || 0} invalid decisions`
              : "Start a run or choose saved evidence"}
          </span>
        </div>
        {points.length ? (
          <>
            <figure
              aria-label="Executed API actions by round"
              className="mt-5 flex h-28 items-end gap-2 border-b border-border"
            >
              {points.map((p) => (
                <div
                  key={p.round}
                  className="flex min-w-0 flex-1 flex-col items-center justify-end"
                >
                  <span className="mb-1 font-mono text-[11px]">
                    {p.actions}
                  </span>
                  <div
                    className="w-full max-w-14 rounded-t-md bg-meadow"
                    style={{
                      height: Math.max(
                        4,
                        (p.actions /
                          Math.max(...points.map((x) => x.actions))) *
                          64,
                      ),
                    }}
                  />
                  <span className="py-1 text-[10px] text-muted-foreground">
                    R{p.round}
                  </span>
                </div>
              ))}
            </figure>
            <p className="mt-3 text-xs text-muted-foreground">
              Executed API actions. Invalid model decisions are counted
              separately; their tokens are included in the total.
            </p>
          </>
        ) : (
          <p className="py-8 text-sm text-muted-foreground">
            Recorded round activity will appear here.
          </p>
        )}
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span>Input {number(r?.efficiency?.prompt_tokens)}</span>
          <span>Output {number(r?.efficiency?.completion_tokens)}</span>
          <span>
            Cached {number(r?.efficiency?.cached_prompt_tokens)} ·{" "}
            {r?.efficiency?.cache_reporting || "unreported"}
          </span>
          <span>Context compactions {number(r?.efficiency?.compactions)}</span>
        </div>
        {r && c.history.some((h) => h.run_id === r.run_id) && (
          <div className="mt-4 flex flex-wrap gap-3">
            <a
              className="ui-text-link"
              href={`/api/history/${r.run_id}/download/json`}
            >
              Download JSON
            </a>
            <a
              className="ui-text-link"
              href={`/api/history/${r.run_id}/download/markdown`}
            >
              Report
            </a>
            <a
              className="ui-text-link"
              href={`/api/history/${r.run_id}/download/events`}
            >
              Event log
            </a>
          </div>
        )}
        <button
          className="ui-text-link mt-4"
          onClick={() => setDetails(!details)}
        >
          {details ? "Hide" : "Inspect"} recorded actions
        </button>
        {details && (
          <div className="mt-4 overflow-x-auto">
            <table className="ui-table">
              <caption className="sr-only">
                Latest twenty recorded actions
              </caption>
              <thead>
                <tr>
                  <th>Round</th>
                  <th>Actor</th>
                  <th>Operation</th>
                  <th>HTTP</th>
                  <th className="text-right">Tokens</th>
                </tr>
              </thead>
              <tbody>
                {(r?.actions || [])
                  .slice(-20)
                  .reverse()
                  .map((a) => (
                    <tr key={a.event_id}>
                      <td>{a.round + 1}</td>
                      <td>{a.agent_id}</td>
                      <td className="font-mono text-xs">
                        {a.request.method} {a.request.path}
                      </td>
                      <td>{a.response_status || "Transport error"}</td>
                      <td className="text-right tabular-nums">
                        {number(a.tokens_used)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {r && r.agents.length > 0 && (
        <details className="rounded-[24px] border border-border bg-white p-5">
          <summary className="cursor-pointer text-sm font-semibold">
            Inspect {r.agents.length} individual agent sessions
          </summary>
          <div className="mt-4 overflow-x-auto">
            <table className="ui-table">
              <thead>
                <tr>
                  <th>Actor</th>
                  <th>Actions</th>
                  <th>Invalid calls</th>
                  <th>Objective score</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {r.agents.map((a) => (
                  <tr key={a.agent_id}>
                    <td>{a.agent_id}</td>
                    <td>{a.steps}</td>
                    <td>
                      {a.invalid_tool_calls}/{a.total_tool_calls}
                    </td>
                    <td>
                      {a.score} {a.score_unit || "points"}
                    </td>
                    <td>
                      {a.error ||
                        a.stop_reason ||
                        "Completed configured rounds"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      {c.state?.gate && (
        <p role="status" className="px-2 text-xs text-muted-foreground">
          {c.state.gate.complete
            ? "Benchmark acceptance passed"
            : c.state.gate.pending.join(" · ")}
        </p>
      )}
    </div>
  );
}
