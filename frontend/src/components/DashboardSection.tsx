import React, { useState } from 'react';
import {
  AGENT_ROSTER,
  DASHBOARD_KPI_SLOTS,
  filterPlantedBugs,
} from '../utils/swarmConfig';

type ConditionKey = 'cond-b' | 'cond-c' | 'phase-2';
type BugFilterKey = 'all' | 'emergent' | 'single-user';

const CONDITION_DESCRIPTIONS: Record<
  ConditionKey,
  { title: string; subtitle: string }
> = {
  'cond-b': {
    title: 'Condition B · Single-persona isolated baseline',
    subtitle: 'Same model and token budget, no inter-agent interaction',
  },
  'cond-c': {
    title: 'Condition C · Swarmtest full interacting swarm',
    subtitle: 'Bazaar target · 6 persona roles · async rounds + barrier bursts',
  },
  'phase-2': {
    title: 'Phase 2 · Meko Datapack memory & regression run',
    subtitle: 'Recalls saved checks over MCP: fixed, still failing, or regressed',
  },
};

export const DashboardSection: React.FC = () => {
  const [activeCondition, setActiveCondition] = useState<ConditionKey>('cond-c');
  const [bugFilter, setBugFilter] = useState<BugFilterKey>('all');

  const visibleBugs = filterPlantedBugs(bugFilter);
  const conditionMeta = CONDITION_DESCRIPTIONS[activeCondition];

  return (
    <section
      id="performance"
      aria-labelledby="performance-title"
      className="relative isolate overflow-hidden bg-white py-24 sm:py-32"
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
          Monitor the live agent activity feed, findings stream, and benchmark scoreboard comparing isolated baselines against the full swarm.
        </p>
      </div>

      {/* Main Dashboard Container */}
      <div className="mx-auto mt-14 w-full max-w-[1180px] px-5 sm:px-8">
        <div className="rounded-[36px] border border-border bg-white p-2.5 shadow-[0_40px_90px_-60px_rgba(20,23,15,0.45)] sm:rounded-[42px] sm:p-3">
          <div className="rounded-[28px] bg-mist p-4 sm:rounded-[34px] sm:p-7">
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
                className="flex rounded-full border border-border bg-white p-1"
              >
                <button
                  type="button"
                  aria-pressed={activeCondition === 'cond-b'}
                  onClick={() => setActiveCondition('cond-b')}
                  className={`h-9 cursor-pointer rounded-full px-4 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap ${
                    activeCondition === 'cond-b'
                      ? 'bg-ink text-white'
                      : 'text-muted-foreground hover:text-ink'
                  }`}
                >
                  Condition B
                </button>
                <button
                  type="button"
                  aria-pressed={activeCondition === 'cond-c'}
                  onClick={() => setActiveCondition('cond-c')}
                  className={`h-9 cursor-pointer rounded-full px-4 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap ${
                    activeCondition === 'cond-c'
                      ? 'bg-ink text-white'
                      : 'text-muted-foreground hover:text-ink'
                  }`}
                >
                  Condition C
                </button>
                <button
                  type="button"
                  aria-pressed={activeCondition === 'phase-2'}
                  onClick={() => setActiveCondition('phase-2')}
                  className={`h-9 cursor-pointer rounded-full px-4 text-[13px] font-medium transition-colors focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap ${
                    activeCondition === 'phase-2'
                      ? 'bg-ink text-white'
                      : 'text-muted-foreground hover:text-ink'
                  }`}
                >
                  Phase 2
                </button>
              </div>
            </div>

            {/* 4 KPI Cards — Metric values strictly blank as unmeasured in PRD */}
            <dl className="mt-6 grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 lg:grid-cols-4">
              {DASHBOARD_KPI_SLOTS.map((slot) => (
                <div
                  key={slot.id}
                  data-testid={`dashboard-kpi-${slot.id}`}
                  className="rounded-[22px] border border-border bg-white px-5 py-4.5"
                >
                  <dt className="text-[13px] text-muted-foreground">{slot.label}</dt>
                  {/* Blank metric value area — no fabricated numbers */}
                  <dd
                    aria-label={`${slot.label} metric blank`}
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

            {/* Bottom 2-Column Grid: Planted Ground-Truth Bugs & Blank Chart (Left) + 6-Role Roster Table (Right) */}
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1.06fr_1fr]">
              {/* Left Card: Benchmark Plot (Blank) & Planted Bugs Oracle List */}
              <div className="flex flex-col justify-between rounded-[24px] border border-border bg-white p-5 sm:p-6">
                <div>
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h4 className="text-[15.5px] font-semibold text-ink">
                      Planted bugs &amp; benchmark recall
                    </h4>
                    <div
                      role="group"
                      aria-label="Filter planted bugs"
                      className="inline-flex rounded-full bg-mist p-0.5 text-[12px]"
                    >
                      <button
                        type="button"
                        onClick={() => setBugFilter('all')}
                        className={`cursor-pointer rounded-full px-2.5 py-1 font-medium transition-colors whitespace-nowrap ${
                          bugFilter === 'all'
                            ? 'bg-white text-ink shadow-xs'
                            : 'text-muted-foreground hover:text-ink'
                        }`}
                      >
                        All
                      </button>
                      <button
                        type="button"
                        onClick={() => setBugFilter('emergent')}
                        className={`cursor-pointer rounded-full px-2.5 py-1 font-medium transition-colors whitespace-nowrap ${
                          bugFilter === 'emergent'
                            ? 'bg-white text-ink shadow-xs'
                            : 'text-muted-foreground hover:text-ink'
                        }`}
                      >
                        Emergent
                      </button>
                      <button
                        type="button"
                        onClick={() => setBugFilter('single-user')}
                        className={`cursor-pointer rounded-full px-2.5 py-1 font-medium transition-colors whitespace-nowrap ${
                          bugFilter === 'single-user'
                            ? 'bg-white text-ink shadow-xs'
                            : 'text-muted-foreground hover:text-ink'
                        }`}
                      >
                        Single-user
                      </button>
                    </div>
                  </div>

                  {/* Blank Chart Area — gridlines present, data bars intentionally blank */}
                  <div
                    data-testid="dashboard-blank-chart"
                    className="mt-4 rounded-2xl border border-dashed border-border bg-mist/40 px-4 py-4"
                  >
                    <div className="flex h-[110px] flex-col justify-between">
                      <div className="border-b border-border/70" />
                      <div className="border-b border-border/70" />
                      <div className="border-b border-border/70" />
                      <div className="border-b border-border" />
                    </div>
                    <div className="mt-2 flex justify-between text-[11px] text-muted-foreground">
                      <span>Condition B (Isolated)</span>
                      <span>Condition C (Full swarm)</span>
                    </div>
                  </div>
                </div>

                {/* Frozen Planted Bug List (PRD Section 7) */}
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-left text-[13px]">
                    <thead>
                      <tr className="border-b border-border text-[11.5px] font-medium text-muted-foreground">
                        <th className="pb-2 pr-3 font-medium">ID</th>
                        <th className="pb-2 pr-3 font-medium">Planted bug description</th>
                        <th className="pb-2 pr-3 font-medium">Type</th>
                        <th className="pb-2 text-right font-medium">Recall</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {visibleBugs.map((bug) => (
                        <tr key={bug.id}>
                          <td className="py-2.5 pr-3 font-mono text-[12px] font-semibold text-ink">
                            {bug.id}
                          </td>
                          <td className="py-2.5 pr-3 text-ink/85">{bug.description}</td>
                          <td className="py-2.5 pr-3 whitespace-nowrap">
                            <span
                              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                                bug.type === 'emergent'
                                  ? 'bg-sage text-moss'
                                  : 'bg-mist text-muted-foreground'
                              }`}
                            >
                              {bug.type}
                            </span>
                          </td>
                          {/* Measured recall left blank */}
                          <td
                            data-testid={`bug-recall-${bug.id}`}
                            className="py-2.5 text-right font-mono text-[12px] text-muted-foreground tabular-nums"
                          >
                            {bug.measuredRecall}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Right Card: Agent Roster Table (PRD Section 5 — 6 Roles, metric columns blank) */}
              <div className="rounded-[24px] border border-border bg-white p-5 sm:p-6">
                <div className="flex items-baseline justify-between">
                  <h4 className="text-[15.5px] font-semibold text-ink">
                    Agent roster
                  </h4>
                  <span className="text-[12px] text-muted-foreground">
                    claude-haiku-5-5
                  </span>
                </div>

                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-left text-[13px]">
                    <caption className="sr-only">
                      Swarmtest persona roles with blank metric columns
                    </caption>
                    <thead>
                      <tr className="border-b border-border text-[11.5px] font-medium text-muted-foreground">
                        <th className="pb-2.5 pr-3 font-medium">Agent</th>
                        <th className="pb-2.5 px-2 text-right font-medium">Runs</th>
                        <th className="pb-2.5 px-2 text-right font-medium">Score</th>
                        <th className="pb-2.5 px-2 text-right font-medium">Cost</th>
                        <th className="pb-2.5 pl-3 text-right font-medium">Target</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {AGENT_ROSTER.map((agent) => (
                        <tr key={agent.id}>
                          <th scope="row" className="min-w-[155px] py-3 pr-3 font-normal">
                            <div className="font-medium text-ink whitespace-nowrap">
                              {agent.role}
                            </div>
                            <div className="text-[12px] text-muted-foreground">
                              {agent.objective}
                            </div>
                          </th>
                          {/* Blank metric cells — no fabricated run counts, scores, or costs */}
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
                            {agent.precisionMetric}
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
                                agent.category === 'normal'
                                  ? 'bg-sage text-moss'
                                  : 'bg-[#f8ead8] text-[#8a4b14]'
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
          </div>
        </div>
      </div>
    </section>
  );
};
