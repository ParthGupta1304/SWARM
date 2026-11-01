import React from "react";
import { useConsole } from "../lib/console";
import {
  recall,
  precision,
  money,
  percent,
  roleSummary,
  duration,
  averageDuration,
} from "../lib/metrics";
import { LiveToolbar, ComparisonChart, RunPanels } from "../lib/RunPanels";

type ConditionKey = "cond-b" | "cond-c";

const CONDITION_DESCRIPTIONS: Record<
  ConditionKey,
  { title: string; subtitle: string }
> = {
  "cond-b": {
    title: "Condition B · Single-persona isolated baseline",
    subtitle: "Same model and token budget, no inter-agent interaction",
  },
  "cond-c": {
    title: "Condition C · SWARM full interacting swarm",
    subtitle: "Bazaar target · 6 persona roles · async rounds + barrier bursts",
  },
};

export const DashboardSection: React.FC<{ compact?: boolean }> = ({
  compact = false,
}) => {
  const c = useConsole();
  const activeCondition: ConditionKey =
    c.condition === "isolated" ? "cond-b" : "cond-c";
  const setActiveCondition = (key: ConditionKey) => {
    c.setCondition(key === "cond-b" ? "isolated" : "swarm");
  };
  const conditionMeta = CONDITION_DESCRIPTIONS[activeCondition];
  const m = c.evaluationBenchmark?.conditions[c.condition]?.metrics;
  const DASHBOARD_KPI_SLOTS = [
    {
      id: "kpi-recall",
      label: "Emergent-bug recall",
      value: percent(
        c.run
          ? recall(c.findings, c.config?.bugs || [], "emergent")
          : m?.emergent_recall?.mean,
      ),
      sublabel: c.run
        ? "Emergent bugs verified in this run, when measured"
        : "Three-seed benchmark mean, when measured",
    },
    {
      id: "kpi-precision",
      label: "Reviewed precision",
      value: percent(
        c.run ? precision(c.run) : m?.precision_after_verifier?.mean,
      ),
      sublabel:
        "Supported findings / reviewed verified findings; measures false alarms",
    },
    {
      id: "kpi-cost",
      label: "Estimated run cost",
      value: money(c.run?.cost_usd ?? m?.cost_usd?.mean ?? undefined),
      sublabel: "Reported tokens × configured provider rates",
    },
    {
      id: "kpi-time",
      label: "Time taken",
      value: duration(
        c.run?.elapsed_s ??
          averageDuration(
            c.evaluationBenchmark?.runs.filter(
              (r) => r.condition === c.condition,
            ) || [],
          ),
      ),
      sublabel: c.run
        ? "Elapsed time for the selected run"
        : "Average total time across three recorded seeds",
    },
  ];
  const roster = (c.config?.roles || []).map((role) => {
    const stats = roleSummary(c.run?.agents || [], role.id);
    return {
      id: role.id,
      role: role.name,
      objective: role.objective,
      category: role.id === "casual_buyer" ? "normal" : "adversary",
      targets: role.id === "casual_buyer" ? "Normal" : "Adversary",
      runsMetric: c.run ? stats.steps : "—",
      precisionMetric: stats.score ?? "—",
      costMetric: money(stats.cost),
      scoreUnit: stats.unit,
      invalid: stats.invalid,
    };
  });
  return (
    <section
      id="performance"
      aria-labelledby="performance-title"
      className={`relative isolate overflow-hidden bg-white ${compact ? "pt-32 pb-12 sm:pt-40" : "py-24 sm:py-32"}`}
    >
      {/* Section Header */}
      <div className="mx-auto flex max-w-3xl flex-col items-center px-5 text-center">
        <span className="inline-flex items-center rounded-full bg-sage px-3.5 py-1.5 text-[14px] font-medium text-ink/90">
          Live dashboard
        </span>
        <h2
          id="performance-title"
          className="mt-6 font-heading text-[clamp(2.1rem,3.1vw,2.8rem)] leading-[1.18] tracking-[-0.03em] text-balance text-ink"
        >
          Every round, persona, and oracle. <br className="max-md:hidden" />
          In one calm view.
        </h2>
        <p className="mt-5 max-w-[54ch] text-[17px] leading-relaxed text-muted-foreground">
          Monitor the live agent activity feed, findings stream, and benchmark
          scoreboard comparing isolated baselines against the full swarm.
        </p>
      </div>

      {/* Main Dashboard Container */}
      <div className="mx-auto mt-14 w-full max-w-[1180px] px-5 sm:px-8">
        <div className="rounded-[36px] border border-border bg-white p-2.5 shadow-[0_40px_90px_-60px_rgba(20,23,15,0.45)] sm:rounded-[42px] sm:p-3">
          <div className="rounded-[28px] bg-mist p-4 sm:rounded-[34px] sm:p-7">
            <LiveToolbar />
            {/* Top Bar: Workspace Title + Condition Switcher */}
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-[17px] font-semibold text-ink">
                  {conditionMeta.title}
                </h3>
                <p className="text-[13px] text-muted-foreground">
                  {conditionMeta.subtitle}
                </p>
              </div>

              <div
                role="group"
                aria-label="Evaluation condition"
                className="flex flex-wrap rounded-2xl border border-border bg-white p-1 sm:rounded-full"
              >
                <button
                  type="button"
                  aria-pressed={activeCondition === "cond-b"}
                  onClick={() => setActiveCondition("cond-b")}
                  className={`h-9 cursor-pointer rounded-full px-4 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap ${
                    activeCondition === "cond-b"
                      ? "bg-ink text-white"
                      : "text-muted-foreground hover:text-ink"
                  }`}
                >
                  Condition B
                </button>
                <button
                  type="button"
                  aria-pressed={activeCondition === "cond-c"}
                  onClick={() => setActiveCondition("cond-c")}
                  className={`h-9 cursor-pointer rounded-full px-4 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap ${
                    activeCondition === "cond-c"
                      ? "bg-ink text-white"
                      : "text-muted-foreground hover:text-ink"
                  }`}
                >
                  Condition C
                </button>
              </div>
            </div>

            {c.historicalEvaluation && (
              <p className="mt-5 text-xs leading-relaxed text-muted-foreground">
                {c.evaluationLabel}
              </p>
            )}
            {/* Four KPI cards — measured values or explicit unmeasured states */}
            <dl className="mt-6 grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 lg:grid-cols-4">
              {DASHBOARD_KPI_SLOTS.map((slot) => (
                <div
                  key={slot.id}
                  data-testid={`dashboard-kpi-${slot.id}`}
                  className="rounded-[22px] border border-border bg-white px-5 py-4.5"
                >
                  <dt className="text-[13px] text-muted-foreground">
                    {slot.label}
                  </dt>
                  {/* Blank metric value area — no fabricated numbers */}
                  <dd
                    aria-label={`${slot.label}: ${slot.value}`}
                    className="mt-1.5 min-h-[38px] font-heading text-[clamp(1.6rem,2.3vw,2rem)] leading-tight font-semibold tracking-[-0.03em] text-ink"
                  >
                    {slot.value}
                  </dd>
                  <dd className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[12px] text-muted-foreground">
                    <span>{slot.sublabel}</span>
                  </dd>
                </div>
              ))}
            </dl>

            {/* Benchmark comparison and agent outcomes */}
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1.06fr_1fr]">
              {/* Measured benchmark recall */}
              <div className="flex flex-col self-start rounded-[24px] border border-border bg-white p-5 sm:p-6">
                <div>
                  <h4 className="text-[15.5px] font-semibold text-ink">
                    Benchmark recall
                  </h4>
                  <ComparisonChart />
                </div>
              </div>

              {/* Right Card: Agent roster — six roles with measured outcomes */}
              <div className="rounded-[24px] border border-border bg-white p-5 sm:p-6">
                <div className="flex items-baseline justify-between">
                  <h4 className="text-[15.5px] font-semibold text-ink">
                    Agent roster
                  </h4>
                </div>

                <div className="mt-4 overflow-x-auto">
                  <table className="w-full min-w-[420px] text-left text-[13px]">
                    <caption className="sr-only">
                      SWARM persona roles and recorded outcomes
                    </caption>
                    <thead>
                      <tr className="border-b border-border text-[11.5px] font-medium text-muted-foreground">
                        <th className="pb-2.5 pr-3 font-medium">Agent</th>
                        <th className="pb-2.5 px-2 text-right font-medium">
                          Actions
                        </th>
                        <th className="pb-2.5 px-2 text-right font-medium">
                          Score
                        </th>
                        <th className="pb-2.5 px-2 text-right font-medium">
                          Cost
                        </th>
                        <th className="pb-2.5 pl-3 text-right font-medium">
                          Category
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {roster.map((agent) => (
                        <tr key={agent.id}>
                          <th
                            scope="row"
                            className="min-w-[155px] py-3 pr-3 font-normal"
                          >
                            <div className="font-medium text-ink whitespace-nowrap">
                              {agent.role}
                            </div>
                            <div className="text-[12px] text-muted-foreground">
                              <span title={agent.objective}>
                                {agent.objective.slice(0, 55)}
                                {agent.objective.length > 55 ? "…" : ""}
                              </span>
                            </div>
                          </th>
                          {/* Measured role totals */}
                          <td
                            data-testid={`agent-runs-${agent.id}`}
                            className="py-3 px-2 text-right font-mono text-[12.5px] text-ink tabular-nums"
                          >
                            {agent.runsMetric}
                          </td>
                          <td
                            data-testid={`agent-score-${agent.id}`}
                            className="py-3 px-2 text-right font-mono text-[12.5px] text-ink tabular-nums"
                          >
                            <span title={agent.scoreUnit}>
                              {agent.precisionMetric}
                            </span>
                          </td>
                          <td
                            data-testid={`agent-cost-${agent.id}`}
                            className="py-3 px-2 text-right font-mono text-[12.5px] text-ink tabular-nums"
                          >
                            {agent.costMetric}
                          </td>
                          <td className="py-3 pl-3 text-right whitespace-nowrap">
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-medium ${
                                agent.category === "normal"
                                  ? "bg-sage text-moss"
                                  : "bg-[#f8ead8] text-[#8a4b14]"
                              }`}
                            >
                              {agent.targets}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            <RunPanels />
          </div>
        </div>
      </div>
    </section>
  );
};
