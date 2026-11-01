import React from "react";
import { useConsole } from "../lib/console";
import { percent, money, duration, averageDuration } from "../lib/metrics";
import { BENCHMARK_TICKET_SLOTS } from "../utils/swarmConfig";

const TOP_LEFT_OUTLINE_TILES = [
  { col: 1, row: 0, delay: "0s", dur: "5s" },
  { col: 3, row: 0, delay: "-1.7s", dur: "6s" },
  { col: 4, row: 0, delay: "-3.4s", dur: "7s" },
  { col: 0, row: 1, delay: "-5.1s", dur: "5s" },
  { col: 2, row: 1, delay: "-0.8s", dur: "6s" },
  { col: 3, row: 1, delay: "-2.5s", dur: "7s" },
  { col: 5, row: 1, delay: "-4.2s", dur: "5s" },
  { col: 1, row: 2, delay: "-5.9s", dur: "6s" },
];

const TOP_RIGHT_OUTLINE_TILES = [
  { col: 1, row: 0, delay: "0s", dur: "5s" },
  { col: 3, row: 0, delay: "-1.7s", dur: "6s" },
  { col: 5, row: 0, delay: "-3.4s", dur: "7s" },
  { col: 0, row: 1, delay: "-5.1s", dur: "5s" },
  { col: 2, row: 1, delay: "-0.8s", dur: "6s" },
  { col: 4, row: 1, delay: "-2.5s", dur: "7s" },
  { col: 1, row: 2, delay: "-4.2s", dur: "5s" },
  { col: 4, row: 2, delay: "-5.9s", dur: "6s" },
];

export const ProofSection: React.FC = () => {
  const c = useConsole();
  const evaluation = c.config?.evaluation;
  const m = evaluation?.benchmark.conditions.swarm?.metrics;
  const values = [
    percent(m?.precision_after_verifier?.mean),
    duration(
      averageDuration(
        evaluation?.benchmark.runs.filter((r) => r.condition === "swarm") || [],
      ),
    ),
    money(m?.cost_usd?.mean ?? undefined),
  ];
  const explanations = [
    "The share of verified findings supported by a judge or human review. High precision means fewer false alarms, not that every bug was found.",
    "Average total time per SWARM run across the three recorded seeds, including exploration and verification.",
    "Estimated exploration cost per run, based on reported tokens and configured provider rates. Benchmark values average three runs and exclude judging costs.",
  ];
  return (
    <section
      id="proof"
      aria-labelledby="proof-title"
      className="relative isolate overflow-hidden bg-white pt-24 pb-16 sm:pt-36"
    >
      {/* Top Left Outline Grid */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-[-38px] left-[-24px] max-lg:hidden"
        style={
          {
            "--tile": "76px",
            "--tile-gap": "6px",
            width:
              "calc(6 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
            height:
              "calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
          } as React.CSSProperties
        }
      >
        {TOP_LEFT_OUTLINE_TILES.map((t, idx) => (
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

      {/* Top Right Outline Grid */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-[-30px] right-[-30px] max-lg:hidden"
        style={
          {
            "--tile": "76px",
            "--tile-gap": "6px",
            width:
              "calc(6 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
            height:
              "calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
          } as React.CSSProperties
        }
      >
        {TOP_RIGHT_OUTLINE_TILES.map((t, idx) => (
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

      {/* Section Header */}
      <div className="relative z-20 mx-auto flex max-w-3xl flex-col items-center px-5 text-center">
        <span className="inline-flex items-center rounded-full bg-sage px-3.5 py-1.5 text-[14px] font-medium text-ink/90">
          Evaluation benchmark
        </span>
        <h2
          id="proof-title"
          className="mt-6 font-heading text-[clamp(2.1rem,3.1vw,2.8rem)] leading-[1.18] tracking-[-0.03em] text-balance text-ink"
        >
          Find the failures that only appear <br className="max-sm:hidden" />
          when real users collide.
        </h2>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Historical Groq benchmark · SWARM condition ·{" "}
          {evaluation?.rounds_per_run ?? "—"} rounds per run · seeds 11, 22, 33.
        </p>
      </div>

      {/* Three evaluation cards and pine tree backdrop */}
      <div className="group/stats relative mx-auto mt-14 w-full max-w-[1100px] px-5 sm:mt-20 sm:px-8 sm:pb-[calc(min(72vw,540px)*0.7)]">
        {/* Pine Tree Image */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute bottom-0 left-1/2 z-10 aspect-[3/4] w-[min(72vw,540px)] -translate-x-1/2 mix-blend-multiply max-sm:hidden motion-safe:animate-grow-tree"
        >
          <img
            alt=""
            src="/images/tree.jpg"
            referrerPolicy="no-referrer"
            className="fade-bottom h-full w-full object-contain object-bottom [--fade:10%]"
          />
        </div>

        {/* Three meadow tickets — fixed historical measurements */}
        <ul className="relative z-20 grid grid-cols-1 gap-3.5 sm:grid-cols-3 sm:gap-5">
          {BENCHMARK_TICKET_SLOTS.map((slot, idx) => (
            <li
              key={slot.id}
              data-testid={`proof-ticket-${slot.id}`}
              className="relative min-h-[172px] sm:min-h-[210px] lg:min-h-[228px]"
            >
              <div
                aria-hidden="true"
                className="ticket absolute inset-0 z-0 rounded-[28px] bg-meadow [--notch:17px] sm:rounded-[34px] sm:[--notch:22px] motion-safe:animate-rise"
                style={{ animationDelay: `${idx * 110}ms` }}
              />
              <div
                className="relative z-20 flex h-full flex-col justify-between gap-6 px-6 py-6 sm:py-8 lg:px-8 motion-safe:animate-rise"
                style={{ animationDelay: `${idx * 110}ms` }}
              >
                <p className="text-[14px] leading-snug font-medium text-ink sm:text-[15px]">
                  {slot.label}
                </p>
                {/* Measured evaluation value */}
                <p
                  aria-label={`${slot.label}: ${values[idx]}`}
                  className="min-h-[44px] font-heading text-[clamp(2.3rem,4.3vw,3.65rem)] leading-none font-semibold tracking-[-0.035em] text-ink"
                >
                  {values[idx]}
                </p>
                <p className="text-[12px] leading-relaxed text-ink/80">
                  {explanations[idx]}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
};
