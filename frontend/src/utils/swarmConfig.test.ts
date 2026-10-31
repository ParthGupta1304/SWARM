import test from "node:test";
import assert from "node:assert/strict";
import {
  AGENT_ROSTER,
  PLANTED_BUGS,
  BENCHMARK_TICKET_SLOTS,
  DASHBOARD_KPI_SLOTS,
  BUSINESS_OUTCOME_SLOTS,
  DEFAULT_SWARM_PARAMS,
  filterPlantedBugs,
  computeSliderFillPercent,
} from "./swarmConfig";

test("no fabricated metrics exist in any metric slot or roster item", () => {
  for (const slot of BENCHMARK_TICKET_SLOTS) {
    assert.equal(slot.value, "", `Expected blank value for ${slot.id}`);
  }
  for (const slot of DASHBOARD_KPI_SLOTS) {
    assert.equal(slot.value, "", `Expected blank value for ${slot.id}`);
  }
  for (const slot of BUSINESS_OUTCOME_SLOTS) {
    assert.equal(slot.value, "", `Expected blank value for ${slot.id}`);
  }
  for (const agent of AGENT_ROSTER) {
    assert.equal(agent.runsMetric, "");
    assert.equal(agent.precisionMetric, "");
    assert.equal(agent.costMetric, "");
  }
  for (const bug of PLANTED_BUGS) {
    assert.equal(bug.measuredRecall, "");
  }
});

test("PRD agent roster has all 6 specified roles", () => {
  assert.equal(AGENT_ROSTER.length, 6);
  const roles = AGENT_ROSTER.map((a) => a.role);
  assert.deepEqual(roles, [
    "Casual buyer",
    "Bargain hunter",
    "Impatient clicker",
    "Fraudster",
    "Sock puppet operator",
    "Troll",
  ]);
});

test("PRD planted bugs filter correctly between emergent and single-user", () => {
  assert.equal(filterPlantedBugs("all").length, 8);
  assert.equal(filterPlantedBugs("emergent").length, 5);
  assert.equal(filterPlantedBugs("single-user").length, 3);
});

test("slider fill percentage computes accurately", () => {
  assert.equal(computeSliderFillPercent(5, 5, 105), 0);
  assert.equal(computeSliderFillPercent(55, 5, 105), 50);
  assert.equal(computeSliderFillPercent(105, 5, 105), 100);
});

test("default population and budget match the configured Phase 1 MVP", () => {
  assert.equal(
    Object.entries(DEFAULT_SWARM_PARAMS)
      .filter(([key]) => key.endsWith("Count"))
      .reduce((n, [, v]) => n + v, 0),
    10,
  );
  assert.equal(DEFAULT_SWARM_PARAMS.maxDollars, 0.5);
});
