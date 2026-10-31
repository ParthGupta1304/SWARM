import type { Action, Actor, Bug, Finding, Run } from "./types";
export const money = (value: number | undefined) =>
  value === undefined
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 4,
        maximumFractionDigits: 5,
      }).format(value);
export const number = (value: number | undefined) =>
  value === undefined ? "—" : new Intl.NumberFormat("en-US").format(value);
export const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${(value * 100).toFixed(1)}%`;
export const duration = (seconds: number | undefined) =>
  seconds === undefined
    ? "—"
    : seconds < 60
      ? `${seconds.toFixed(1)}s`
      : `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
export function foundIds(findings: Finding[] = []) {
  return new Set(
    findings
      .filter((f) => f.verified && f.mapped_bug_id)
      .map((f) => f.mapped_bug_id!),
  );
}
export function recall(findings: Finding[], bugs: Bug[], type?: Bug["type"]) {
  const expected = bugs.filter((b) => !type || b.type === type);
  const ids = foundIds(findings);
  return expected.length
    ? expected.filter((b) => ids.has(b.id)).length / expected.length
    : null;
}
export function precision(run: Pick<Run, "findings" | "assessments"> | null) {
  const f = (run?.findings || []).filter((f) => f.verified),
    a = run?.assessments;
  if (!f.length || !a || f.some((f) => typeof a[f.id] !== "boolean"))
    return null;
  return f.filter((f) => a[f.id]).length / f.length;
}
export function rounds(actions: Action[]) {
  const rows = new Map<
    number,
    { round: number; actions: number; tokens: number }
  >();
  for (const a of actions) {
    const row = rows.get(a.round) || {
      round: a.round + 1,
      actions: 0,
      tokens: 0,
    };
    row.actions++;
    row.tokens += a.tokens_used;
    rows.set(a.round, row);
  }
  return [...rows.values()].sort((a, b) => a.round - b.round);
}
export function roleSummary(actors: Actor[], role: string) {
  const rows = actors.filter((a) => a.role === role);
  const units = new Set(rows.map((a) => a.score_unit || "objective points"));
  return {
    count: rows.length,
    steps: rows.reduce((n, a) => n + a.steps, 0),
    invalid: rows.reduce((n, a) => n + a.invalid_tool_calls, 0),
    score:
      rows.length && units.size === 1
        ? rows.reduce((n, a) => n + a.score, 0)
        : undefined,
    unit: [...units][0],
    cost:
      rows.length && rows.every((a) => a.efficiency?.cost_usd !== undefined)
        ? rows.reduce((n, a) => n + (a.efficiency?.cost_usd || 0), 0)
        : undefined,
  };
}

export function repeatability(rows: { found_bug_ids?: string[] }[]) {
  if (rows.length !== 3) return null;
  const ids = new Set(rows.flatMap((r) => r.found_bug_ids || []));
  return ids.size
    ? [...ids].filter((id) => rows.every((r) => r.found_bug_ids?.includes(id)))
        .length / ids.size
    : null;
}
