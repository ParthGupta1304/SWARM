import React from "react";
import { useConsole } from "../lib/console";
import {
  recall,
  precision,
  percent,
  duration,
  repeatability,
} from "../lib/metrics";
import {
  BENCHMARK_TICKET_SLOTS,
  TARGET_CATEGORIES,
} from "../utils/swarmConfig";

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
  const m = c.benchmark?.conditions[c.condition]?.metrics;
  const verified = new Set(
    c.findings.filter((f) => f.verified).map((f) => f.id),
  );
  const times = Object.entries(c.run?.finding_times_s || {})
    .filter(([id]) => verified.has(id))
    .map(([, time]) => time);
  const values = [
    percent(
      c.run
        ? recall(c.findings, c.config?.bugs || [], "emergent")
        : m?.emergent_recall?.mean,
    ),
    percent(c.run ? precision(c.run) : m?.precision_after_verifier?.mean),
    duration(
      times.length
        ? Math.min(...times)
        : (m?.time_to_first_find_s?.mean ?? undefined),
    ),
    percent(
      repeatability(
        c.benchmark?.runs.filter((r) => r.condition === c.condition) || [],
      ),
    ),
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
      </div>

      {/* 4 Ticket Cards + Pine Tree Backdrop + Target Categories Bar */}
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

        {/* Four meadow tickets — selected run measurements */}
        <ul className="grid grid-cols-2 gap-3.5 sm:gap-5 lg:grid-cols-4">
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
                className="relative z-20 flex h-full flex-col justify-between gap-6 px-6 py-6 sm:px-9 sm:py-8 motion-safe:animate-rise"
                style={{ animationDelay: `${idx * 110}ms` }}
              >
                <p className="text-[14px] leading-snug font-medium text-ink sm:text-[15px]">
                  {slot.label}
                </p>
                {/* Blank metric value area — no fabricated numbers */}
                <p
                  aria-label={`${slot.label}: ${values[idx]}`}
                  className="min-h-[44px] font-heading text-[clamp(2.3rem,4.3vw,3.65rem)] leading-none font-semibold tracking-[-0.035em] text-ink"
                >
                  {values[idx]}
                </p>
              </div>
            </li>
          ))}
        </ul>

        {/* Frosted 4-Column Target Categories Bar (Marketplaces, Booking, Fintech, Community) */}
        <div className="relative z-30 mt-5 overflow-hidden rounded-[30px] border border-white/90 bg-white/65 shadow-[0_24px_60px_-34px_rgba(20,23,15,0.45)] backdrop-blur-2xl sm:rounded-[34px]">
          <ul className="flex flex-wrap items-stretch justify-center text-ink">
            {TARGET_CATEGORIES.map((cat, idx) => (
              <li
                key={cat}
                className="flex h-[92px] basis-1/2 items-center justify-center px-4 lg:h-[124px] lg:flex-1 lg:basis-0 lg:border-l lg:border-black/[0.06] lg:first:border-l-0"
              >
                <span className="flex items-center gap-2">
                  <span
                    className={`font-heading text-[24px] leading-none tracking-[-0.03em] text-ink/55 sm:text-[28px] ${
                      idx === 0
                        ? "font-bold"
                        : idx === 1
                          ? "font-medium"
                          : idx === 2
                            ? "font-semibold italic"
                            : "font-semibold"
                    }`}
                  >
                    {cat}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
};
