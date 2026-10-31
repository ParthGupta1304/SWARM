import React from "react";
import { BrandLogo } from "./Navbar";
import { useConsole } from "../lib/console";
import { money, percent, precision } from "../lib/metrics";
import { ComparisonChart } from "../lib/RunPanels";

const WORKFLOW_OUTLINE_TILES = [
  { col: 0, row: 0, delay: "0s", dur: "5s" },
  { col: 2, row: 0, delay: "-1.7s", dur: "6s" },
  { col: 1, row: 1, delay: "-3.4s", dur: "7s" },
  { col: 3, row: 1, delay: "-5.1s", dur: "5s" },
  { col: 0, row: 2, delay: "-0.8s", dur: "6s" },
];

export const WorkflowSection: React.FC = () => {
  const c = useConsole();
  return (
    <section
      id="workflow"
      aria-labelledby="workflow-title"
      className="relative isolate overflow-hidden bg-white py-24 sm:py-32"
    >
      {/* Top Right Outline Grid */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-10 -right-6 max-lg:hidden"
        style={
          {
            "--tile": "64px",
            "--tile-gap": "6px",
            width:
              "calc(4 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
            height:
              "calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
          } as React.CSSProperties
        }
      >
        {WORKFLOW_OUTLINE_TILES.map((t, idx) => (
          <span
            key={idx}
            className="outline-tile absolute motion-safe:animate-blink"
            style={{
              left: `calc(${t.col} * (var(--tile) + var(--tile-gap)))`,
              top: `calc(${t.row} * (var(--tile) + var(--tile-gap)))`,
              width: "var(--tile)",
              height: "var(--tile)",
              borderRadius: "calc(var(--tile) * 0.17)",
              animationDelay: t.delay,
              animationDuration: t.dur,
            }}
          />
        ))}
      </div>

      {/* Section Heading */}
      <div className="mx-auto flex max-w-3xl flex-col items-center px-5 text-center">
        <span className="inline-flex items-center rounded-full bg-sage px-3.5 py-1.5 text-[14px] font-medium text-ink/90">
          How it works
        </span>
        <h2
          id="workflow-title"
          className="mt-6 font-heading text-[clamp(2.1rem,3.1vw,2.8rem)] leading-[1.18] tracking-[-0.03em] text-balance text-ink"
        >
          Configure, run, and verify swarms <br className="max-md:hidden" />
          without importing an SDK.
        </h2>
        <p className="mt-5 max-w-[56ch] text-[17px] leading-relaxed text-muted-foreground">
          Point Swarmtest at a staging copy of your app using an OpenAPI spec
          and one config file. Agents act from the outside like real users while
          every action is logged.
        </p>
      </div>

      {/* 3 Step Cards */}
      <ol className="mx-auto mt-16 grid w-full max-w-[1180px] gap-5 px-5 sm:px-8 lg:grid-cols-3">
        {/* Step 01: Configure & Populate */}
        <li>
          <div className="h-full">
            <article className="flex h-full flex-col rounded-[34px] border border-border bg-white p-3 shadow-[0_24px_60px_-40px_rgba(20,23,15,0.35)]">
              <div className="relative flex min-h-[270px] items-center overflow-hidden rounded-[26px] px-6 py-8 sm:px-8 bg-[linear-gradient(160deg,#fbe4d4_0%,#f2dbe6_48%,#d9dbf6_100%)]">
                {/* Decorative glass tiles */}
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute top-4 right-4 opacity-80"
                  style={
                    {
                      "--tile": "44px",
                      "--tile-gap": "3px",
                      width:
                        "calc(2 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                      height:
                        "calc(2 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                    } as React.CSSProperties
                  }
                >
                  <span
                    className="absolute"
                    style={{
                      left: 0,
                      top: 0,
                      width: "var(--tile)",
                      height: "var(--tile)",
                      borderRadius: "calc(var(--tile) * 0.17)",
                    }}
                  >
                    <span
                      className="glass-tile absolute inset-0"
                      style={{ borderRadius: "inherit" }}
                    />
                  </span>
                  <span
                    className="absolute"
                    style={{
                      left: "calc(1 * (var(--tile) + var(--tile-gap)))",
                      top: "calc(1 * (var(--tile) + var(--tile-gap)))",
                      width: "var(--tile)",
                      height: "var(--tile)",
                      borderRadius: "calc(var(--tile) * 0.17)",
                    }}
                  >
                    <span
                      className="glass-tile absolute inset-0"
                      style={{ borderRadius: "inherit" }}
                    />
                  </span>
                </div>

                {/* Inner Persona Spec Preview (Appendix A) */}
                <div className="relative w-full">
                  <div className="w-full rounded-[22px] border border-white/80 bg-white/85 p-4 shadow-[0_22px_44px_-26px_rgba(46,52,98,0.45)] backdrop-blur-md">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-[12.5px] font-semibold text-ink">
                        <span className="flex size-6 items-center justify-center rounded-full bg-meadow">
                          <BrandLogo className="h-[11px]" />
                        </span>
                        fraudster-01
                      </span>
                      <span className="rounded-full bg-sage px-2.5 py-0.5 text-[11px] font-medium text-ink/80">
                        Persona spec
                      </span>
                    </div>
                    <p className="mt-3 rounded-2xl bg-mist px-3.5 py-3 text-left text-[12.5px] leading-relaxed text-ink/85">
                      Receive a refund while keeping the item. Patient, avoids
                      obvious patterns, tries a different route when blocked.
                      <span className="ml-0.5 inline-block h-3.5 w-px translate-y-0.5 bg-ink motion-safe:animate-caret" />
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[11px] font-medium text-ink/80">
                        checkout
                      </span>
                      <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[11px] font-medium text-ink/80">
                        open_dispute
                      </span>
                      <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[11px] font-medium text-ink/80">
                        request_refund
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-4 pt-7 pb-5 sm:px-5">
                <p className="flex items-center gap-2.5 text-[14px] font-medium text-muted-foreground">
                  <span className="rounded-full bg-sage px-2.5 py-0.5 font-mono text-[12px] text-ink/80">
                    01
                  </span>
                  Configure & Populate
                </p>
                <h3 className="mt-4 font-heading text-[25px] leading-tight tracking-[-0.025em] text-ink">
                  Define personas with hard objectives
                </h3>
                <p className="mt-3 text-[16px] leading-relaxed text-muted-foreground">
                  Configure your OpenAPI spec, base URL, seed, and population
                  mix in swarmtest.yaml. Adversaries get measurable scores and
                  attack primitives so conflict stays alive.
                </p>
              </div>
            </article>
          </div>
        </li>

        {/* Step 02: Run & Detect */}
        <li>
          <div className="h-full">
            <article className="flex h-full flex-col rounded-[34px] border border-border bg-white p-3 shadow-[0_24px_60px_-40px_rgba(20,23,15,0.35)]">
              <div className="relative flex min-h-[270px] items-center overflow-hidden rounded-[26px] px-6 py-8 sm:px-8 bg-[linear-gradient(160deg,#eef3d2_0%,#f3f6e6_45%,#dbe8f1_100%)]">
                {/* Decorative glass tiles */}
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute top-4 right-4 opacity-80"
                  style={
                    {
                      "--tile": "44px",
                      "--tile-gap": "3px",
                      width:
                        "calc(2 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                      height:
                        "calc(2 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                    } as React.CSSProperties
                  }
                >
                  <span
                    className="absolute"
                    style={{
                      left: 0,
                      top: 0,
                      width: "var(--tile)",
                      height: "var(--tile)",
                      borderRadius: "calc(var(--tile) * 0.17)",
                    }}
                  >
                    <span
                      className="glass-tile absolute inset-0"
                      style={{ borderRadius: "inherit" }}
                    />
                  </span>
                  <span
                    className="absolute"
                    style={{
                      left: "calc(1 * (var(--tile) + var(--tile-gap)))",
                      top: "calc(1 * (var(--tile) + var(--tile-gap)))",
                      width: "var(--tile)",
                      height: "var(--tile)",
                      borderRadius: "calc(var(--tile) * 0.17)",
                    }}
                  >
                    <span
                      className="glass-tile absolute inset-0"
                      style={{ borderRadius: "inherit" }}
                    />
                  </span>
                </div>

                {/* Inner Barrier Scheduler Event Log Card */}
                <div className="relative w-full">
                  <div className="w-full rounded-[22px] border border-white/80 bg-white/85 p-4 shadow-[0_22px_44px_-26px_rgba(46,52,98,0.45)] backdrop-blur-md">
                    <div className="flex items-center justify-between">
                      <span className="text-[12.5px] font-semibold text-ink">
                        Barrier Scheduler
                      </span>
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-sage px-2.5 py-0.5 text-[11px] font-medium text-moss">
                        <span className="size-1.5 rounded-full bg-moss" />
                        Running
                      </span>
                    </div>
                    <ol className="mt-3.5 space-y-2.5 text-left">
                      <li className="flex items-center gap-2.5 text-[12px]">
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-meadow/70 text-ink">
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="3"
                            className="size-3"
                          >
                            <path d="M20 6 9 17l-5-5" />
                          </svg>
                        </span>
                        <span className="min-w-0 flex-1 truncate text-ink/85">
                          Spawned concurrent agent rounds
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          FR-2
                        </span>
                      </li>
                      <li className="flex items-center gap-2.5 text-[12px]">
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-meadow/70 text-ink">
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="3"
                            className="size-3"
                          >
                            <path d="M20 6 9 17l-5-5" />
                          </svg>
                        </span>
                        <span className="min-w-0 flex-1 truncate text-ink/85">
                          Synchronized barrier burst on checkout
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          FR-4
                        </span>
                      </li>
                      <li className="flex items-center gap-2.5 text-[12px]">
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[#f8dcc9] text-[#8a3f14]">
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.5"
                            className="size-3"
                          >
                            <path d="M12 9v4" />
                            <path d="M12 17h.01" />
                          </svg>
                        </span>
                        <span className="min-w-0 flex-1 truncate text-ink/85">
                          Invariant check flagged oversell race
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          E1
                        </span>
                      </li>
                      <li className="flex items-center gap-2.5 text-[12px]">
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-meadow/70 text-ink">
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="3"
                            className="size-3"
                          >
                            <path d="M20 6 9 17l-5-5" />
                          </svg>
                        </span>
                        <span className="min-w-0 flex-1 truncate text-ink/85">
                          Queued minimal sequence for replay
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          FR-7
                        </span>
                      </li>
                    </ol>
                  </div>
                </div>
              </div>

              <div className="px-4 pt-7 pb-5 sm:px-5">
                <p className="flex items-center gap-2.5 text-[14px] font-medium text-muted-foreground">
                  <span className="rounded-full bg-sage px-2.5 py-0.5 font-mono text-[12px] text-ink/80">
                    02
                  </span>
                  Run & Detect
                </p>
                <h3 className="mt-4 font-heading text-[25px] leading-tight tracking-[-0.025em] text-ink">
                  Provoke races with barrier bursts
                </h3>
                <p className="mt-3 text-[16px] leading-relaxed text-muted-foreground">
                  Async agents act in rounds while the barrier scheduler forces
                  multiple agents to hit the same endpoint at the same instant,
                  checked by SQL and Python invariants.
                </p>
              </div>
            </article>
          </div>
        </li>

        {/* Step 03: Verify & Report */}
        <li>
          <div className="h-full">
            <article className="flex h-full flex-col rounded-[34px] border border-border bg-white p-3 shadow-[0_24px_60px_-40px_rgba(20,23,15,0.35)]">
              <div className="relative flex min-h-[270px] items-center overflow-hidden rounded-[26px] px-6 py-8 sm:px-8 bg-[linear-gradient(160deg,#dcdff7_0%,#e6e0f2_50%,#f7ddd0_100%)]">
                {/* Decorative glass tiles */}
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute top-4 right-4 opacity-80"
                  style={
                    {
                      "--tile": "44px",
                      "--tile-gap": "3px",
                      width:
                        "calc(2 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                      height:
                        "calc(2 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                    } as React.CSSProperties
                  }
                >
                  <span
                    className="absolute"
                    style={{
                      left: 0,
                      top: 0,
                      width: "var(--tile)",
                      height: "var(--tile)",
                      borderRadius: "calc(var(--tile) * 0.17)",
                    }}
                  >
                    <span
                      className="glass-tile absolute inset-0"
                      style={{ borderRadius: "inherit" }}
                    />
                  </span>
                  <span
                    className="absolute"
                    style={{
                      left: "calc(1 * (var(--tile) + var(--tile-gap)))",
                      top: "calc(1 * (var(--tile) + var(--tile-gap)))",
                      width: "var(--tile)",
                      height: "var(--tile)",
                      borderRadius: "calc(var(--tile) * 0.17)",
                    }}
                  >
                    <span
                      className="glass-tile absolute inset-0"
                      style={{ borderRadius: "inherit" }}
                    />
                  </span>
                </div>

                {/* Inner benchmark card with selected evidence */}
                <div className="relative w-full">
                  <div className="w-full rounded-[22px] border border-white/80 bg-white/85 p-4 shadow-[0_22px_44px_-26px_rgba(46,52,98,0.45)] backdrop-blur-md">
                    <div className="flex items-baseline justify-between">
                      <span className="text-[12.5px] font-semibold text-ink">
                        Benchmark harness
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        Selected evidence
                      </span>
                    </div>

                    {/* Unknown measurements remain explicit */}
                    <div className="mt-3 grid grid-cols-2 gap-2 text-left">
                      <div className="rounded-2xl bg-mist px-3 py-2.5">
                        <p className="text-[11px] text-muted-foreground">
                          Reviewed precision
                        </p>
                        <p
                          data-testid="workflow-precision"
                          className="mt-0.5 min-h-[28px] font-heading text-[22px] font-semibold tracking-[-0.03em] text-ink"
                        >
                          {percent(c.run ? precision(c.run) : null)}
                        </p>
                      </div>
                      <div className="rounded-2xl bg-mist px-3 py-2.5">
                        <p className="text-[11px] text-muted-foreground">
                          Cost per run
                        </p>
                        <p
                          data-testid="workflow-cost"
                          className="mt-0.5 min-h-[28px] font-heading text-[22px] font-semibold tracking-[-0.03em] text-ink"
                        >
                          {money(c.run?.cost_usd)}
                        </p>
                      </div>
                    </div>

                    <p className="mt-3 text-left text-[11px] text-muted-foreground">
                      Recall across evaluation conditions
                    </p>
                    <ComparisonChart />
                  </div>
                </div>
              </div>

              <div className="px-4 pt-7 pb-5 sm:px-5">
                <p className="flex items-center gap-2.5 text-[14px] font-medium text-muted-foreground">
                  <span className="rounded-full bg-sage px-2.5 py-0.5 font-mono text-[12px] text-ink/80">
                    03
                  </span>
                  Verify & Report
                </p>
                <h3 className="mt-4 font-heading text-[25px] leading-tight tracking-[-0.025em] text-ink">
                  Deterministic replay on a fresh DB
                </h3>
                <p className="mt-3 text-[16px] leading-relaxed text-muted-foreground">
                  Extract the minimal action sequence and replay it on a reset
                  database snapshot. Findings are ranked by severity with repro
                  steps and an evidence trail.
                </p>
              </div>
            </article>
          </div>
        </li>
      </ol>
    </section>
  );
};
