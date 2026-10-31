import React, { useState } from "react";
import { useConsole, download } from "../lib/console";
import { money, foundIds } from "../lib/metrics";
import {
  BUSINESS_OUTCOME_SLOTS,
  computeSliderFillPercent,
} from "../utils/swarmConfig";

interface ValueSectionProps {
  onOpenCliModal: () => void;
}

const VALUE_OUTLINE_TILES = [
  { col: 0, row: 0, delay: "0s", dur: "5s" },
  { col: 2, row: 0, delay: "-1.7s", dur: "6s" },
  { col: 1, row: 1, delay: "-3.4s", dur: "7s" },
  { col: 0, row: 2, delay: "-5.1s", dur: "5s" },
];

export const ValueSection: React.FC<ValueSectionProps> = ({
  onOpenCliModal,
}) => {
  const c = useConsole();
  const casualBuyers = c.options?.normal_agents || 2,
    adversaryCount = c.options?.adversary_agents || 8,
    maxDollars = c.options?.max_dollars ?? 0.5;
  const cap = c.config?.population_cap || 10,
    normalMax = cap - 5,
    adversaryMax = cap - casualBuyers,
    budgetMax = c.config?.max_dollars_cap || 0.5;
  const setCasualBuyers = (n: number) => {
    if (c.options)
      c.setOptions({
        ...c.options,
        normal_agents: n,
        adversary_agents: Math.min(adversaryCount, cap - n),
      });
  };
  const setAdversaryCount = (n: number) => {
    if (c.options) c.setOptions({ ...c.options, adversary_agents: n });
  };
  const setMaxDollars = (n: number) => {
    if (c.options) c.setOptions({ ...c.options, max_dollars: n });
  };
  const [showYamlPreview, setShowYamlPreview] = useState(false);
  const yamlString =
    c.yaml || c.configError || "Preparing a validated configuration…";
  const unique = foundIds(c.findings).size;
  const ticketValues = [
    money(c.run?.cost_usd),
    unique && c.run ? money(c.run.cost_usd / unique) : "—",
    "Local CLI",
  ];
  return (
    <section
      id="value"
      aria-labelledby="value-title"
      className="relative isolate overflow-hidden bg-white py-24 sm:py-32"
    >
      {/* Left Outline Grid */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-16 -left-5 max-lg:hidden"
        style={
          {
            "--tile": "64px",
            "--tile-gap": "6px",
            width:
              "calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
            height:
              "calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
          } as React.CSSProperties
        }
      >
        {VALUE_OUTLINE_TILES.map((t, idx) => (
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
      <div className="mx-auto flex max-w-3xl flex-col items-center px-5 text-center">
        <span className="inline-flex items-center rounded-full bg-sage px-3.5 py-1.5 text-[14px] font-medium text-ink/90">
          Swarm configuration
        </span>
        <h2
          id="value-title"
          className="mt-6 font-heading text-[clamp(2.1rem,3.1vw,2.8rem)] leading-[1.18] tracking-[-0.03em] text-balance text-ink"
        >
          Exploration is expensive. <br className="max-sm:hidden" />
          Regression is deterministic.
        </h2>
        <p className="mt-5 max-w-[54ch] text-[17px] leading-relaxed text-muted-foreground">
          Configure your population mix and hard budget cap in swarmtest.yaml.
          Inspect recorded findings and repeat their API sequence on a fresh
          local database without another model call.
        </p>
      </div>

      {/* 2-Column Grid: Sliders (Left) + Measured value tickets (Right) */}
      <div className="mx-auto mt-14 grid w-full max-w-[1100px] gap-5 px-5 sm:px-8 lg:grid-cols-[1.1fr_1fr]">
        {/* Left Card: Configuration Sliders */}
        <div className="flex flex-col justify-center gap-8 rounded-[34px] border border-border bg-white p-7 shadow-[0_30px_80px_-60px_rgba(20,23,15,0.45)] sm:p-10">
          <div>
            <div className="flex items-baseline justify-between gap-4">
              <label
                htmlFor="slider-casual-buyers"
                className="text-[15.5px] font-medium text-ink"
              >
                Normal community agents
              </label>
              <output
                htmlFor="slider-casual-buyers"
                className="font-heading text-[24px] leading-none font-semibold tracking-[-0.02em] text-ink tabular-nums"
              >
                {casualBuyers}
              </output>
            </div>
            <p className="mt-1 text-[13.5px] text-muted-foreground">
              Browse and buy normally to generate realistic baseline traffic.
            </p>
            <input
              id="slider-casual-buyers"
              type="range"
              min={1}
              max={normalMax}
              step={1}
              value={casualBuyers}
              onChange={(e) => setCasualBuyers(Number(e.target.value))}
              className="range-moss mt-5"
              style={
                {
                  "--fill": `${computeSliderFillPercent(casualBuyers, 1, normalMax)}%`,
                } as React.CSSProperties
              }
            />
            <div
              aria-hidden="true"
              className="mt-2 flex justify-between text-[12px] text-muted-foreground"
            >
              <span>1</span>
              <span>{normalMax}</span>
            </div>
          </div>

          <div>
            <div className="flex items-baseline justify-between gap-4">
              <label
                htmlFor="slider-adversaries"
                className="text-[15.5px] font-medium text-ink"
              >
                Adaptive adversaries (5 roles)
              </label>
              <output
                htmlFor="slider-adversaries"
                className="font-heading text-[24px] leading-none font-semibold tracking-[-0.02em] text-ink tabular-nums"
              >
                {adversaryCount}
              </output>
            </div>
            <p className="mt-1 text-[13.5px] text-muted-foreground">
              Bargain hunters, impatient clickers, fraudsters, sock puppets, and
              trolls.
            </p>
            <input
              id="slider-adversaries"
              type="range"
              min={5}
              max={adversaryMax}
              step={1}
              value={adversaryCount}
              onChange={(e) => setAdversaryCount(Number(e.target.value))}
              className="range-moss mt-5"
              style={
                {
                  "--fill": `${computeSliderFillPercent(adversaryCount, 5, adversaryMax)}%`,
                } as React.CSSProperties
              }
            />
            <div
              aria-hidden="true"
              className="mt-2 flex justify-between text-[12px] text-muted-foreground"
            >
              <span>5</span>
              <span>{adversaryMax}</span>
            </div>
          </div>

          <div>
            <div className="flex items-baseline justify-between gap-4">
              <label
                htmlFor="slider-budget-cap"
                className="text-[15.5px] font-medium text-ink"
              >
                Budget cap per run
              </label>
              <output
                htmlFor="slider-budget-cap"
                className="font-heading text-[24px] leading-none font-semibold tracking-[-0.02em] text-ink tabular-nums"
              >
                ${maxDollars}
              </output>
            </div>
            <p className="mt-1 text-[13.5px] text-muted-foreground">
              Enforced per run with live token meter and global kill switch.
            </p>
            <input
              id="slider-budget-cap"
              type="range"
              min={0.01}
              max={budgetMax}
              step={0.01}
              value={maxDollars}
              onChange={(e) => setMaxDollars(Number(e.target.value))}
              className="range-moss mt-5"
              style={
                {
                  "--fill": `${computeSliderFillPercent(maxDollars, 0.01, budgetMax)}%`,
                } as React.CSSProperties
              }
            />
            <div
              aria-hidden="true"
              className="mt-2 flex justify-between text-[12px] text-muted-foreground"
            >
              <span>$0.01</span>
              <span>${budgetMax}</span>
            </div>
          </div>

          <label className="block text-sm font-medium">
            Development seed
            <input
              aria-label="Development seed"
              className="ui-select mt-2 w-full"
              type="number"
              min={0}
              max={2147483647}
              value={c.options?.seed ?? 1}
              onChange={(e) => {
                if (c.options)
                  c.setOptions({ ...c.options, seed: Number(e.target.value) });
              }}
            />
            <span className="mt-1 block text-xs font-normal text-muted-foreground">
              {casualBuyers + adversaryCount} of {cap} allowed agents · six
              regular rounds. Lower populations can reduce interaction coverage.
            </span>
          </label>
          <div className="pt-1">
            <button
              type="button"
              onClick={() => setShowYamlPreview((prev) => !prev)}
              className="text-[13.5px] font-semibold text-moss underline underline-offset-4 hover:text-moss-deep cursor-pointer"
            >
              {showYamlPreview
                ? "Hide swarmtest.yaml preview"
                : "Preview generated swarmtest.yaml"}
            </button>
            {c.configError && (
              <p role="alert" className="mt-3 text-sm text-red-800">
                {c.configError}
              </p>
            )}
            <button
              type="button"
              className="ui-secondary mt-4"
              disabled={!c.yaml || !!c.configError}
              onClick={() =>
                download("swarmtest.yaml", c.yaml, "application/yaml")
              }
            >
              Download swarmtest.yaml
            </button>
            {showYamlPreview && (
              <pre className="mt-3 overflow-x-auto rounded-2xl bg-mist p-4 font-mono text-[12px] leading-relaxed text-ink">
                {yamlString}
              </pre>
            )}
          </div>
        </div>

        {/* Right Column: 3 Ticket Cards with Selected run values */}
        <div className="flex flex-col gap-5">
          {/* Ticket 1: Measured cost per run */}
          <div
            data-testid="value-ticket-measured-run-cost"
            className="relative min-h-[168px]"
          >
            <div
              aria-hidden="true"
              className="ticket absolute inset-0 rounded-[30px] bg-meadow [--notch:18px] sm:rounded-[34px] sm:[--notch:22px]"
            />
            <div className="relative flex h-full flex-col justify-between gap-5 px-7 py-6 sm:px-9 sm:py-7">
              <p className="text-[15px] font-medium text-ink">
                {BUSINESS_OUTCOME_SLOTS[0].label}
              </p>
              <div>
                <p
                  aria-label="Estimated cost per run"
                  className="min-h-[44px] font-heading text-[clamp(2.4rem,4vw,3.3rem)] leading-none font-semibold tracking-[-0.035em] text-ink tabular-nums"
                >
                  {ticketValues[0]}
                </p>
                <p className="mt-2 text-[13px] text-ink/70">
                  Measured estimate for the selected run; fixtures are labelled.
                </p>
              </div>
            </div>
          </div>

          {/* Ticket 2: Cost per verified bug */}
          <div
            data-testid="value-ticket-cost-per-verified-bug"
            className="relative min-h-[168px]"
          >
            <div
              aria-hidden="true"
              className="ticket absolute inset-0 rounded-[30px] bg-meadow [--notch:18px] sm:rounded-[34px] sm:[--notch:22px]"
            />
            <div className="relative flex h-full flex-col justify-between gap-5 px-7 py-6 sm:px-9 sm:py-7">
              <p className="text-[15px] font-medium text-ink">
                {BUSINESS_OUTCOME_SLOTS[1].label}
              </p>
              <div>
                <p
                  aria-label="Cost per distinct verified bug"
                  className="min-h-[44px] font-heading text-[clamp(2.4rem,4vw,3.3rem)] leading-none font-semibold tracking-[-0.035em] text-ink tabular-nums"
                >
                  {ticketValues[1]}
                </p>
                <p className="mt-2 text-[13px] text-ink/70">
                  Selected run cost divided by distinct verified bug IDs.
                </p>
              </div>
            </div>
          </div>

          {/* Ticket 3: Hosted tier price per run + CTA */}
          <div
            data-testid="value-ticket-hosted-tier-pricing"
            className="relative min-h-[156px]"
          >
            <div
              aria-hidden="true"
              className="ticket absolute inset-0 rounded-[30px] bg-moss [--notch:18px] sm:rounded-[34px] sm:[--notch:22px]"
            />
            <div className="relative flex h-full flex-wrap items-center justify-between gap-5 px-7 py-6 sm:px-9 sm:py-7">
              <div>
                <p className="text-[14.5px] font-medium text-white/85">
                  Phase 1 distribution
                </p>
                <p
                  aria-label="Available mode"
                  className="mt-1 min-h-[38px] font-heading text-[clamp(2rem,3.4vw,2.75rem)] leading-none font-semibold tracking-[-0.035em] text-white tabular-nums"
                >
                  {ticketValues[2]}
                </p>
              </div>
              <button
                type="button"
                onClick={onOpenCliModal}
                className="inline-flex h-12 shrink-0 cursor-pointer items-center justify-center rounded-full bg-white px-5 text-[15px] font-semibold text-ink transition-transform hover:scale-[1.02] active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-meadow focus-visible:outline-none whitespace-nowrap"
              >
                Inspect CLI config
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
