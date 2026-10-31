import React, { useState } from "react";
import { BrandLogo } from "./Navbar";
import { useConsole } from "../lib/console";
import { useDialog } from "../lib/Modal";

interface CtaAndFooterProps {
  compact?: boolean;
  isCliModalOpen: boolean;
  onOpenCliModal: () => void;
  onCloseCliModal: () => void;
}

const FIREFLIES = [
  { left: "6%", top: "62%", delay: "0s", dur: "7s", fx: "16px", fy: "-24px" },
  {
    left: "13%",
    top: "78%",
    delay: "2.4s",
    dur: "8s",
    fx: "-12px",
    fy: "-18px",
  },
  {
    left: "19%",
    top: "55%",
    delay: "4.1s",
    dur: "6.5s",
    fx: "20px",
    fy: "-14px",
  },
  {
    left: "27%",
    top: "84%",
    delay: "1.2s",
    dur: "7.5s",
    fx: "10px",
    fy: "-26px",
  },
  {
    left: "33%",
    top: "69%",
    delay: "5.3s",
    dur: "8.5s",
    fx: "-18px",
    fy: "-20px",
  },
  {
    left: "48%",
    top: "74%",
    delay: "3s",
    dur: "6.8s",
    fx: "14px",
    fy: "-16px",
  },
  {
    left: "67%",
    top: "64%",
    delay: "1.8s",
    dur: "7.2s",
    fx: "-14px",
    fy: "-22px",
  },
  {
    left: "82%",
    top: "72%",
    delay: "3.6s",
    dur: "8.1s",
    fx: "12px",
    fy: "-19px",
  },
  {
    left: "91%",
    top: "60%",
    delay: "0.9s",
    dur: "6.9s",
    fx: "-16px",
    fy: "-24px",
  },
];

export const CtaAndFooter: React.FC<CtaAndFooterProps> = ({
  compact = false,
  isCliModalOpen,
  onOpenCliModal,
  onCloseCliModal,
}) => {
  const [copiedCommand, setCopiedCommand] = useState(false);
  const [copiedYaml, setCopiedYaml] = useState(false);

  const c = useConsole();
  const defaultYaml = c.yaml || c.configError || "Preparing configuration…";
  const dialogRef = useDialog(isCliModalOpen, onCloseCliModal);
  const [copyError, setCopyError] = useState("");

  const handleCopyCommand = async () => {
    try {
      await navigator.clipboard.writeText(
        "swarmtest run --config swarmtest.yaml",
      );
      setCopiedCommand(true);
      setCopyError("");
      setTimeout(() => setCopiedCommand(false), 2000);
    } catch {
      setCopyError("Clipboard unavailable. Select and copy the command below.");
    }
  };

  const handleCopyYaml = async () => {
    try {
      if (!c.yaml) throw new Error();
      await navigator.clipboard.writeText(c.yaml);
      setCopiedYaml(true);
      setCopyError("");
      setTimeout(() => setCopiedYaml(false), 2000);
    } catch {
      setCopyError(
        "Clipboard unavailable or configuration invalid. Select the YAML to copy it.",
      );
    }
  };

  return (
    <>
      {/* Pre-Footer Dusk Valley CTA Section */}
      {!compact && (
        <section
          id="get-started"
          aria-labelledby="cta-title"
          className="relative isolate overflow-hidden bg-white pt-16 sm:pt-24"
        >
          {/* Dusk Valley Background Image + Fireflies */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-[72%] overflow-hidden"
          >
            <img
              alt=""
              src="/images/dusk-valley.jpg"
              referrerPolicy="no-referrer"
              className="fade-top absolute inset-0 h-full w-full object-cover object-[50%_60%] [--fade:8%]"
            />
            {FIREFLIES.map((f, idx) => (
              <span
                key={idx}
                className="absolute size-[5px] rounded-full bg-[#f5f8d9] opacity-60 shadow-[0_0_10px_3px_rgba(236,244,186,0.65)] motion-safe:animate-firefly"
                style={
                  {
                    left: f.left,
                    top: f.top,
                    animationDelay: f.delay,
                    animationDuration: f.dur,
                    "--fx": f.fx,
                    "--fy": f.fy,
                  } as React.CSSProperties
                }
              />
            ))}
          </div>

          {/* Frosted Glass CTA Card */}
          <div className="mx-auto w-full max-w-[980px] px-5 pb-36 sm:px-8 sm:pb-48">
            <div className="relative overflow-hidden rounded-[36px] border border-white/80 bg-[linear-gradient(to_bottom,rgba(255,255,255,0.98)_0%,rgba(255,255,255,0.9)_42%,rgba(255,255,255,0.28)_100%)] px-6 pt-14 pb-16 text-center shadow-[0_50px_100px_-60px_rgba(20,30,80,0.7)] backdrop-blur-xl sm:rounded-[48px] sm:px-12 sm:pt-20 sm:pb-24">
              <span className="inline-flex items-center rounded-full bg-sage px-3.5 py-1.5 text-[14px] font-medium text-ink/90">
                Ready when you are
              </span>
              <h2
                id="cta-title"
                className="mx-auto mt-6 max-w-[22ch] font-heading text-[clamp(2.1rem,3.3vw,2.9rem)] leading-[1.15] tracking-[-0.03em] text-balance text-ink"
              >
                Test your app as a society before real users arrive.
              </h2>
              <p className="mx-auto mt-5 max-w-[48ch] text-[18px] leading-relaxed text-ink/85">
                Run Swarmtest from the command line against a disposable staging
                copy of your app with your configured Groq key in local .env.
              </p>
              <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={onOpenCliModal}
                  className="inline-flex h-13 cursor-pointer items-center justify-center gap-2 rounded-full bg-moss px-7 text-[16px] font-semibold text-white transition-[background-color,transform] duration-200 hover:bg-moss-deep active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-moss focus-visible:ring-offset-2 focus-visible:outline-none whitespace-nowrap"
                >
                  Get started with CLI
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Footer */}
      <footer className="bg-white px-3 pt-6 pb-3 sm:px-4 sm:pb-4">
        <div className="mx-auto w-full max-w-[1320px] rounded-[32px] bg-mist px-6 pt-6 sm:rounded-[44px] sm:px-8 sm:pt-8">
          {/* Top Meadow Ticket Banner */}
          <div className="ticket relative overflow-hidden rounded-[26px] bg-meadow px-6 py-10 [--notch:17px] sm:rounded-[34px] sm:px-12 sm:py-14 sm:[--notch:22px]">
            <div className="flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
              <div>
                <span className="inline-flex items-center rounded-full bg-white/60 px-3.5 py-1.5 text-[14px] font-medium text-ink/90">
                  CLI + swarmtest.yaml
                </span>
                <p className="mt-5 max-w-[18ch] font-heading text-[clamp(2rem,3.6vw,3rem)] leading-[1.1] tracking-[-0.03em] text-balance text-ink">
                  Put your first swarm to{" "}
                  <em className="italic text-moss-deep">work</em> on staging.
                </p>
              </div>
              <button
                type="button"
                onClick={onOpenCliModal}
                className="inline-flex h-14 shrink-0 cursor-pointer items-center justify-center gap-2 self-start rounded-full bg-moss px-7 text-[17px] font-semibold text-white transition-[background-color,transform] duration-200 hover:bg-moss-deep active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-moss focus-visible:ring-offset-2 focus-visible:outline-none md:self-auto whitespace-nowrap"
              >
                Run from CLI
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="size-5"
                  aria-hidden="true"
                >
                  <path d="M7 7h10v10" />
                  <path d="M7 17 17 7" />
                </svg>
              </button>
            </div>
          </div>

          {/* Footer Navigation Grid */}
          <div className="grid gap-12 px-2 py-12 sm:grid-cols-2 sm:py-16 lg:grid-cols-[1.4fr_1fr_1fr] lg:px-6">
            <div className="sm:col-span-2 lg:col-span-1">
              <a
                aria-label="Swarmtest home"
                href="/#hero"
                className="inline-flex items-center gap-2.5 rounded-xl text-ink focus-visible:ring-2 focus-visible:ring-moss focus-visible:ring-offset-4 focus-visible:ring-offset-mist focus-visible:outline-none"
              >
                <BrandLogo className="h-8" />
                <span className="font-heading text-[28px] leading-none font-medium tracking-[-0.035em]">
                  swarmtest
                </span>
              </a>
              <p className="mt-5 max-w-[38ch] text-[16px] leading-relaxed text-ink/65">
                Multi-agent testing system that puts normal users plus adaptive
                adversaries inside a real running application and proves what it
                found with deterministic replay.
              </p>
              <div className="mt-7 flex items-center gap-3">
                <a
                  href="/assets/aistudio/Swarmtest_PRD_Hackathon_Build__1__292fedf8.pdf"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex h-10 items-center gap-2 rounded-full bg-white px-4 text-[13.5px] font-medium text-ink shadow-[0_8px_20px_-14px_rgba(20,23,15,0.4)] transition-[background-color,transform] hover:-translate-y-0.5 hover:bg-sage focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap"
                >
                  Read PRD PDF
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="size-3.5"
                    aria-hidden="true"
                  >
                    <path d="M7 7h10v10" />
                    <path d="M7 17 17 7" />
                  </svg>
                </a>
              </div>
            </div>

            <nav aria-label="Product">
              <p className="text-[14px] font-medium text-ink">Product</p>
              <ul className="mt-5 space-y-3.5">
                <li>
                  <a
                    className="inline-flex items-center gap-1 rounded-md text-[16px] text-ink/70 transition-colors hover:text-moss"
                    href="/#workflow"
                  >
                    How it works
                  </a>
                </li>
                <li>
                  <a
                    className="inline-flex items-center gap-1 rounded-md text-[16px] text-ink/70 transition-colors hover:text-moss"
                    href="#oversight"
                  >
                    Verification
                  </a>
                </li>
                <li>
                  <a
                    className="inline-flex items-center gap-1 rounded-md text-[16px] text-ink/70 transition-colors hover:text-moss"
                    href="/dashboard"
                  >
                    Dashboard
                  </a>
                </li>
                <li>
                  <a
                    className="inline-flex items-center gap-1 rounded-md text-[16px] text-ink/70 transition-colors hover:text-moss"
                    href="#value"
                  >
                    Configuration
                  </a>
                </li>
              </ul>
            </nav>

            <nav aria-label="Safety & Architecture">
              <p className="text-[14px] font-medium text-ink">
                Safety &amp; Spec
              </p>
              <ul className="mt-5 space-y-3.5">
                <li>
                  <button
                    type="button"
                    onClick={onOpenCliModal}
                    className="cursor-pointer inline-flex items-center gap-1 rounded-md text-[16px] text-ink/70 transition-colors hover:text-moss"
                  >
                    swarmtest.yaml CLI
                  </button>
                </li>
                <li>
                  <a
                    className="inline-flex items-center gap-1 rounded-md text-[16px] text-ink/70 transition-colors hover:text-moss"
                    href="/assets/aistudio/Swarmtest_PRD_Hackathon_Build__1__292fedf8.pdf"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    PRD Specification
                  </a>
                </li>
                <li>
                  <a
                    className="inline-flex items-center gap-1 rounded-md text-[16px] text-ink/70 transition-colors hover:text-moss"
                    href="#oversight"
                  >
                    Meko Phase 2 Memory
                  </a>
                </li>
              </ul>
            </nav>
          </div>

          <div className="flex flex-col justify-between gap-3 border-t border-black/[0.07] px-2 py-6 text-[13.5px] text-ink/55 sm:flex-row lg:px-6">
            <p>© 2026 Swarmtest. Hackathon edition v0.1.</p>
            <p>
              Test only apps you own or have explicit permission to test.
              Synthetic data only.
            </p>
          </div>
        </div>
      </footer>

      {/* CLI & Onboarding Modal */}
      {isCliModalOpen && (
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="cli-modal-title"
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/45 p-4 backdrop-blur-xs"
        >
          <div className="w-full max-w-xl rounded-[32px] border border-border bg-white p-6 shadow-2xl sm:p-8">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="inline-flex items-center rounded-full bg-sage px-3 py-1 text-[12.5px] font-medium text-ink">
                  Distribution &amp; Onboarding
                </span>
                <h3
                  id="cli-modal-title"
                  className="mt-3 font-heading text-[24px] font-medium tracking-[-0.025em] text-ink"
                >
                  Run Swarmtest from the CLI
                </h3>
              </div>
              <button
                type="button"
                aria-label="Close CLI modal"
                onClick={onCloseCliModal}
                className="flex size-9 cursor-pointer items-center justify-center rounded-full bg-mist text-ink hover:bg-sage"
              >
                ✕
              </button>
            </div>

            <p className="mt-2 text-[14.5px] leading-relaxed text-muted-foreground">
              Customers run Swarmtest against a disposable staging environment
              it can reset for deterministic replay. Bring your configured Groq
              key in local .env.
            </p>

            <div className="mt-5">
              <div className="flex items-center justify-between">
                <span className="text-[12.5px] font-semibold text-ink">
                  CLI Command
                </span>
                <button
                  type="button"
                  onClick={handleCopyCommand}
                  className="cursor-pointer text-[12.5px] font-semibold text-moss hover:text-moss-deep"
                >
                  {copiedCommand ? "Copied!" : "Copy command"}
                </button>
              </div>
              <pre className="mt-1.5 overflow-x-auto rounded-2xl bg-mist px-4 py-3 font-mono text-[13px] text-ink">
                swarmtest run --config swarmtest.yaml
              </pre>
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between">
                <span className="text-[12.5px] font-semibold text-ink">
                  Selected swarmtest.yaml
                </span>
                <button
                  type="button"
                  onClick={handleCopyYaml}
                  className="cursor-pointer text-[12.5px] font-semibold text-moss hover:text-moss-deep"
                >
                  {copiedYaml ? "Copied!" : "Copy YAML"}
                </button>
              </div>
              <pre className="mt-1.5 max-h-[300px] overflow-y-auto rounded-2xl bg-mist px-4 py-3 font-mono text-[12px] leading-relaxed text-ink">
                {defaultYaml}
              </pre>
            </div>

            {copyError && (
              <p role="alert" className="mt-3 text-sm text-red-800">
                {copyError}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <a
                href="/dashboard"
                onClick={onCloseCliModal}
                className="ui-secondary"
              >
                Open dashboard
              </a>
              <button
                type="button"
                onClick={onCloseCliModal}
                className="inline-flex h-10 cursor-pointer items-center justify-center rounded-full bg-moss px-5 text-[14px] font-semibold text-white hover:bg-moss-deep"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
