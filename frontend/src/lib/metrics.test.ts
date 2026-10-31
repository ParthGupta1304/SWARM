import test from "node:test";
import assert from "node:assert/strict";
import {
  foundIds,
  recall,
  precision,
  rounds,
  repeatability,
  roleSummary,
} from "./metrics";
import type { Finding, Run, Action, Actor } from "./types";
const findings = [
  { id: "one", verified: true, mapped_bug_id: "E2" },
  { id: "two", verified: true, mapped_bug_id: "E2" },
  { id: "three", verified: false, mapped_bug_id: "E7" },
] as Finding[];
test("distinct verified catalog IDs do not double-count repeated findings", () => {
  assert.deepEqual([...foundIds(findings)], ["E2"]);
  assert.equal(
    recall(
      findings,
      [
        { id: "E2", type: "emergent", description: "" },
        { id: "E7", type: "emergent", description: "" },
      ],
      "emergent",
    ),
    0.5,
  );
});
test("replay success is not silently treated as human-reviewed precision", () => {
  const run: Pick<Run, "findings" | "assessments"> = {
    findings,
    assessments: { one: true },
  };
  assert.equal(precision(run), null);
  run.assessments = { one: true, two: false };
  assert.equal(precision(run), 0.5);
});
test("round plots count executed events without inflating billed usage", () => {
  const data = [
    { round: 0, tokens_used: 11 },
    { round: 0, tokens_used: 7 },
    { round: 1, tokens_used: 3 },
  ] as Action[];
  assert.deepEqual(rounds(data), [
    { round: 1, actions: 2, tokens: 18 },
    { round: 2, actions: 1, tokens: 3 },
  ]);
});
test("repeatability requires three seeds and distinguishes repeated IDs", () => {
  assert.equal(repeatability([{ found_bug_ids: ["E2"] }]), null);
  assert.equal(
    repeatability([
      { found_bug_ids: ["E2", "E7"] },
      { found_bug_ids: ["E2"] },
      { found_bug_ids: ["E2"] },
    ]),
    0.5,
  );
});
test("different score units are never combined into one invented role score", () => {
  const actors = [
    {
      role: "r",
      steps: 2,
      score: 1,
      score_unit: "purchases",
      invalid_tool_calls: 0,
    },
    {
      role: "r",
      steps: 1,
      score: 2,
      score_unit: "coupons",
      invalid_tool_calls: 1,
    },
  ] as Actor[];
  assert.equal(roleSummary(actors, "r").score, undefined);
  assert.equal(roleSummary(actors, "r").cost, undefined);
  assert.equal(roleSummary(actors, "r").invalid, 1);
});
