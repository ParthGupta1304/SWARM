import React, { useEffect, useState } from "react";
import { BrandLogo } from "./Navbar";
import { useConsole } from "../lib/console";

export const OversightSection: React.FC = () => {
  const c = useConsole(),
    finding = c.finding;
  const check =
    finding && c.state?.recheck && c.state.recheck.finding_id === finding.id
      ? c.state.recheck
      : c.run?.rechecks?.filter((r) => r.finding_id === finding?.id).at(-1);
  const replayVerified = !!finding?.verified;
  const [reviewer, setReviewer] = useState(""),
    [note, setNote] = useState(""),
    [decision, setDecision] = useState("correct"),
    [reviewStatus, setReviewStatus] = useState("");
  const [showReproSteps, setShowReproSteps] = useState(false);
  useEffect(() => {
    setReviewer("");
    setNote("");
    setReviewStatus("");
    setShowReproSteps(false);
  }, [finding?.id, c.state?.generation]);

  return (
    <section
      id="oversight"
      aria-labelledby="oversight-title"
      className="relative isolate overflow-hidden bg-white py-24 sm:py-32"
    >
      <div className="mx-auto grid w-full max-w-[1180px] items-center gap-14 px-5 sm:px-8 lg:grid-cols-[1fr_1.08fr] lg:gap-20">
        {/* Left Column: Oracles Before Vibes & Deterministic Verification */}
        <div>
          <span className="inline-flex items-center rounded-full bg-sage px-3.5 py-1.5 text-[14px] font-medium text-ink/90">
            Oracles before vibes
          </span>
          <h2
            id="oversight-title"
            className="mt-6 font-heading text-[clamp(2.1rem,3.1vw,2.8rem)] leading-[1.18] tracking-[-0.03em] text-balance text-ink"
          >
            Deterministic proof on a fresh database snapshot.
          </h2>
          <p className="mt-5 max-w-[46ch] text-[17px] leading-relaxed text-muted-foreground">
            LLM nondeterminism is removed at verification time. Invariant checks
            come first, LLM triage comes second, and nothing is reported
            unverified without a clear label.
          </p>

          <ul className="mt-10 space-y-7">
            <li className="flex gap-4">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-sage text-moss">
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
                  <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
                  <path d="m9 12 2 2 4-4" />
                </svg>
              </span>
              <div>
                <h3 className="text-[17px] font-semibold text-ink">
                  SQL and Python invariant checks
                </h3>
                <p className="mt-1 text-[15.5px] leading-relaxed text-muted-foreground">
                  Enforce core invariants across every event window: inventory
                  never negative, money conserved, no duplicate refunds, and one
                  review per verified purchase.
                </p>
              </div>
            </li>

            <li className="flex gap-4">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-sage text-moss">
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
                  <path d="m12 14 4-4" />
                  <path d="M3.34 19a10 10 0 1 1 17.32 0" />
                </svg>
              </span>
              <div>
                <h3 className="text-[17px] font-semibold text-ink">
                  Deterministic snapshot replay
                </h3>
                <p className="mt-1 text-[15.5px] leading-relaxed text-muted-foreground">
                  Every run starts from a seeded database snapshot. The verifier
                  extracts the minimal action sequence and replays it cleanly to
                  confirm reproducibility.
                </p>
              </div>
            </li>

            <li className="flex gap-4">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-sage text-moss">
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
                  <path d="M15 12h-5" />
                  <path d="M15 8h-5" />
                  <path d="M19 17V5a2 2 0 0 0-2-2H4" />
                  <path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3" />
                </svg>
              </span>
              <div>
                <h3 className="text-[17px] font-semibold text-ink">
                  Append-only event log & Meko memory
                </h3>
                <p className="mt-1 text-[15.5px] leading-relaxed text-muted-foreground">
                  Every action, request, response hash, and DB change is
                  recorded. Phase 2 saves verified checks to a Meko Datapack so
                  regression re-checks require zero LLM calls.
                </p>
              </div>
            </li>
          </ul>
        </div>

        {/* Right Column: Meadow Backdrop + Interactive Replay Verifier Card */}
        <div>
          <div className="relative isolate flex min-h-[520px] items-center justify-center overflow-hidden rounded-[36px] bg-[linear-gradient(180deg,#f7dccb_0%,#e9dbee_38%,#b9c6ec_70%,#8ea07c_100%)] p-5 sm:min-h-[600px] sm:rounded-[44px] sm:p-10">
            <img
              alt=""
              src="/images/meadow.jpg"
              referrerPolicy="no-referrer"
              className="-z-10 absolute inset-0 h-full w-full object-cover motion-safe:animate-kenburns"
            />

            {/* Top Left Glass Tiles */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute top-6 left-6"
              style={
                {
                  "--tile": "clamp(40px, 5vw, 64px)",
                  "--tile-gap": "3px",
                  width:
                    "calc(2 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                  height:
                    "calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                } as React.CSSProperties
              }
            >
              {[
                { col: 0, row: 0, delay: "0s" },
                { col: 1, row: 1, delay: "-2.3s" },
                { col: 0, row: 2, delay: "-4.6s" },
              ].map((t, idx) => (
                <span
                  key={idx}
                  className="absolute"
                  style={{
                    left: `calc(${t.col} * (var(--tile) + var(--tile-gap)))`,
                    top: `calc(${t.row} * (var(--tile) + var(--tile-gap)))`,
                    width: "var(--tile)",
                    height: "var(--tile)",
                    borderRadius: "calc(var(--tile) * 0.17)",
                  }}
                >
                  <span
                    className="glass-tile absolute inset-0 motion-safe:animate-breathe"
                    style={{ borderRadius: "inherit", animationDelay: t.delay }}
                  />
                </span>
              ))}
            </div>

            {/* Bottom Right Glass Tiles */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute right-6 bottom-6"
              style={
                {
                  "--tile": "clamp(40px, 5vw, 64px)",
                  "--tile-gap": "3px",
                  width:
                    "calc(2 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                  height:
                    "calc(3 * (var(--tile) + var(--tile-gap)) - var(--tile-gap))",
                } as React.CSSProperties
              }
            >
              {[
                { col: 0, row: 0, delay: "-1.2s" },
                { col: 1, row: 1, delay: "-3.5s" },
                { col: 0, row: 2, delay: "-5.8s" },
              ].map((t, idx) => (
                <span
                  key={idx}
                  className="absolute"
                  style={{
                    left: `calc(${t.col} * (var(--tile) + var(--tile-gap)))`,
                    top: `calc(${t.row} * (var(--tile) + var(--tile-gap)))`,
                    width: "var(--tile)",
                    height: "var(--tile)",
                    borderRadius: "calc(var(--tile) * 0.17)",
                  }}
                >
                  <span
                    className="glass-tile absolute inset-0 motion-safe:animate-breathe"
                    style={{ borderRadius: "inherit", animationDelay: t.delay }}
                  />
                </span>
              ))}
            </div>

            {/* Interactive Verifier Card */}
            <div className="relative z-10 flex w-full max-w-[430px] flex-col gap-3">
              <div className="rounded-[28px] border border-white/85 bg-white/92 p-6 shadow-[0_32px_70px_-34px_rgba(20,23,15,0.55)] backdrop-blur-md">
                <label className="mb-4 block text-[12px] text-muted-foreground">
                  Finding evidence
                  <select
                    aria-label="Finding evidence"
                    className="ui-select mt-1 w-full"
                    value={finding?.id || ""}
                    onChange={(e) => {
                      c.setFindingId(e.target.value);
                      setReviewStatus("");
                    }}
                  >
                    <option value="" disabled>
                      Select a finding
                    </option>
                    {c.findings.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.mapped_bug_id || "Unmapped"} · {f.title}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-meadow text-ink">
                      <BrandLogo className="h-[16px]" />
                    </span>
                    <div>
                      <p className="text-[14.5px] font-semibold text-ink">
                        Replay verifier ·{" "}
                        {finding?.mapped_bug_id || "No finding selected"}
                      </p>
                      <p className="text-[12.5px] text-muted-foreground">
                        {finding?.involved_agents.join(" + ") ||
                          "Select a completed run"}{" "}
                        · Bazaar target
                      </p>
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-semibold ${
                      replayVerified
                        ? "bg-sage text-moss"
                        : "bg-[#f8ead8] text-[#8a4b14]"
                    }`}
                  >
                    <span
                      className={`size-1.5 rounded-full ${
                        replayVerified ? "bg-moss" : "bg-[#c9701d]"
                      }`}
                    />
                    {finding
                      ? replayVerified
                        ? "Original verified"
                        : "Original unverified"
                      : "Awaiting evidence"}
                  </span>
                </div>

                <p className="mt-5 text-[16px] leading-snug text-ink">
                  {finding?.title ||
                    "Choose a finding from the dashboard to inspect its recorded reproduction and independent verification."}
                </p>

                <p className="mt-3.5 rounded-2xl bg-mist px-4 py-3 text-[13px] text-ink/80">
                  Oracle:{" "}
                  <span className="font-mono font-medium">
                    {finding?.oracle_triggered || "—"}
                  </span>
                </p>

                {showReproSteps && (
                  <div className="mt-3 rounded-2xl border border-border bg-white px-4 py-3 font-mono text-[11.5px] leading-relaxed text-ink/85">
                    {finding?.minimal_repro_sequence.steps.map((step, i) => (
                      <div className="mb-2" key={i}>
                        {i + 1}.{" "}
                        {step.actions.length > 1 ? "Concurrent" : "Sequential"}
                        <ul>
                          {step.actions.map((action) => (
                            <li key={action.event_id}>
                              {action.agent_id}: {action.request.method}{" "}
                              {action.request.path}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                  <button
                    type="button"
                    disabled={
                      !finding || c.state?.busy || c.pending || !c.connected
                    }
                    onClick={() => c.recheck().catch(() => {})}
                    className="inline-flex h-11 cursor-pointer items-center justify-center rounded-full bg-moss px-4 text-[14px] font-semibold text-white transition-colors hover:bg-moss-deep focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap"
                  >
                    {check?.status === "running"
                      ? "Replaying…"
                      : "Replay on fresh DB"}
                  </button>
                  <button
                    type="button"
                    disabled={!finding}
                    onClick={() => setShowReproSteps((prev) => !prev)}
                    className="inline-flex h-11 cursor-pointer items-center justify-center rounded-full border border-border bg-white px-4 text-[14px] font-semibold text-ink transition-colors hover:bg-mist focus-visible:ring-2 focus-visible:ring-moss focus-visible:outline-none whitespace-nowrap"
                  >
                    {showReproSteps ? "Hide repro steps" : "See repro sequence"}
                  </button>
                </div>
                {check && (
                  <p
                    role="status"
                    className="mt-4 rounded-2xl bg-mist p-3 text-[12px]"
                  >
                    Recheck:{" "}
                    {check.status === "completed"
                      ? check.result?.status === "verified"
                        ? "Reproduced"
                        : check.result?.status === "not_reproduced"
                          ? "Not reproduced"
                          : "Inconclusive"
                      : check.status}{" "}
                    · target {check.target_version || "current"} · seed{" "}
                    {check.seed ?? "—"}. Original evidence is preserved.
                  </p>
                )}
                {finding && (
                  <details className="mt-4 border-t border-border pt-3">
                    <summary className="cursor-pointer text-[13px] font-semibold">
                      Original proof and human spot-check
                    </summary>
                    <p className="my-3 text-xs text-muted-foreground">
                      Replay does not automatically approve a finding.{" "}
                      {c.run?.assessments?.[finding.id] === undefined
                        ? "Not yet assessed."
                        : c.run.assessments[finding.id]
                          ? "Human/judge assessment: supported."
                          : "Human/judge assessment: unsupported."}
                    </p>
                    <details>
                      <summary className="cursor-pointer text-xs text-moss">
                        Inspect complete evidence
                      </summary>
                      <pre className="mt-2 max-h-64 overflow-auto rounded-xl bg-mist p-3 text-[10px] whitespace-pre-wrap break-words">
                        {JSON.stringify(finding, null, 2)}
                      </pre>
                    </details>
                    <form
                      className="mt-4 space-y-3"
                      onSubmit={async (e) => {
                        e.preventDefault();
                        setReviewStatus("");
                        try {
                          await c.review(
                            decision === "correct",
                            reviewer,
                            note,
                          );
                          setReviewStatus(
                            "Spot-check recorded against this evidence.",
                          );
                        } catch (error) {
                          setReviewStatus((error as Error).message);
                        }
                      }}
                    >
                      <label className="block text-xs">
                        Your name
                        <input
                          className="ui-select mt-1 w-full"
                          required
                          value={reviewer}
                          onChange={(e) => setReviewer(e.target.value)}
                        />
                      </label>
                      <label className="block text-xs">
                        Evidence decision
                        <select
                          className="ui-select mt-1 w-full"
                          value={decision}
                          onChange={(e) => setDecision(e.target.value)}
                        >
                          <option value="correct">Supported by evidence</option>
                          <option value="incorrect">Unsupported</option>
                        </select>
                      </label>
                      <label className="block text-xs">
                        Evidence note
                        <textarea
                          className="ui-select mt-1 w-full"
                          required
                          minLength={3}
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                        />
                      </label>
                      <button
                        className="ui-primary"
                        disabled={
                          c.pending ||
                          c.state?.busy ||
                          c.run?.status === "stopped"
                        }
                      >
                        Record spot-check
                      </button>
                      <p role="status" className="text-xs">
                        {reviewStatus}
                      </p>
                    </form>
                  </details>
                )}
              </div>

              {/* Bottom Pill Notification */}
              <div className="flex items-center gap-3 rounded-[22px] border border-white/60 bg-white/80 px-4 py-3 shadow-[0_18px_40px_-24px_rgba(20,23,15,0.45)] backdrop-blur-md">
                <span
                  aria-hidden="true"
                  className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[#e8cbb9] text-[12px] font-semibold text-[#5a2d14]"
                >
                  P2
                </span>
                <p className="text-[13px] leading-snug text-ink/85">
                  <strong className="font-semibold text-ink">
                    Planned for Phase 2:
                  </strong>{" "}
                  save verified findings for deterministic regression checks.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
