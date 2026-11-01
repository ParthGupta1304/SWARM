export interface AgentRoleSpec {
  id: string;
  role: string;
  model: string;
  objective: string;
  targets: string;
  defaultCount: number;
  category: "normal" | "adversary";
  /** Unmeasured metrics in PRD - kept strictly blank */
  runsMetric: "";
  precisionMetric: "";
  costMetric: "";
}

export interface PlantedBugSpec {
  id: string;
  type: "single-user" | "emergent";
  description: string;
  targetRole: string;
  /** Unmeasured detection rate in PRD - kept strictly blank */
  measuredRecall: "";
}

export interface BlankMetricSlot {
  id: string;
  label: string;
  sublabel: string;
  /** Strictly blank because measured data is not present in the PRD */
  value: "";
}

export interface SwarmYamlParams {
  casualBuyerCount: number;
  bargainHunterCount: number;
  impatientClickerCount: number;
  fraudsterCount: number;
  sockpuppetCount: number;
  trollCount: number;
  maxDollars: number;
  seed: number;
}

export const DEFAULT_SWARM_PARAMS: SwarmYamlParams = {
  casualBuyerCount: 2,
  bargainHunterCount: 2,
  impatientClickerCount: 1,
  fraudsterCount: 2,
  sockpuppetCount: 2,
  trollCount: 1,
  maxDollars: 0.5,
  seed: 1,
};

/**
 * Section 5: Agent roster (24-hour build, 6 roles)
 * No run counts, success rates, or dollar costs are fabricated; metric fields are blank.
 */
export const AGENT_ROSTER: AgentRoleSpec[] = [
  {
    id: "casual-buyer",
    role: "Casual buyer",
    model: "openai/gpt-oss-120b",
    objective: "Browse and buy normally",
    targets: "Single-user bugs",
    defaultCount: 6,
    category: "normal",
    runsMetric: "",
    precisionMetric: "",
    costMetric: "",
  },
  {
    id: "bargain-hunter",
    role: "Bargain hunter",
    model: "openai/gpt-oss-120b",
    objective: "Pay the lowest price possible",
    targets: "Coupon stacking (E2)",
    defaultCount: 4,
    category: "adversary",
    runsMetric: "",
    precisionMetric: "",
    costMetric: "",
  },
  {
    id: "impatient-clicker",
    role: "Impatient clicker",
    model: "openai/gpt-oss-120b",
    objective: "Double submit, retry, go back",
    targets: "Oversell race (E1)",
    defaultCount: 4,
    category: "adversary",
    runsMetric: "",
    precisionMetric: "",
    costMetric: "",
  },
  {
    id: "fraudster",
    role: "Fraudster",
    model: "openai/gpt-oss-120b",
    objective: "Get a refund and keep the item",
    targets: "Double refund (E4)",
    defaultCount: 2,
    category: "adversary",
    runsMetric: "",
    precisionMetric: "",
    costMetric: "",
  },
  {
    id: "sock-puppet-operator",
    role: "Sock puppet operator",
    model: "openai/gpt-oss-120b",
    objective: "Buy own items from second accounts",
    targets: "Self-dealing (E5)",
    defaultCount: 2,
    category: "adversary",
    runsMetric: "",
    precisionMetric: "",
    costMetric: "",
  },
  {
    id: "troll",
    role: "Troll",
    model: "openai/gpt-oss-120b",
    objective: "Reach a user who blocked them",
    targets: "Block bypass (E7)",
    defaultCount: 2,
    category: "adversary",
    runsMetric: "",
    precisionMetric: "",
    costMetric: "",
  },
];

/**
 * Section 7: Demo app (Bazaar) and planted ground-truth bugs
 */
export const PLANTED_BUGS: PlantedBugSpec[] = [
  {
    id: "E1",
    type: "emergent",
    description:
      "Oversell: two buyers check out the last unit at the same instant",
    targetRole: "Impatient clicker",
    measuredRecall: "",
  },
  {
    id: "E2",
    type: "emergent",
    description: "Coupon stacking via concurrent apply requests",
    targetRole: "Bargain hunter",
    measuredRecall: "",
  },
  {
    id: "E4",
    type: "emergent",
    description: "Refund plus dispute credit pays out twice",
    targetRole: "Fraudster",
    measuredRecall: "",
  },
  {
    id: "E5",
    type: "emergent",
    description:
      "Self-dealing: no same-owner check, so sock puppets inflate rank and rating",
    targetRole: "Sock puppet operator",
    measuredRecall: "",
  },
  {
    id: "E7",
    type: "emergent",
    description:
      "Block bypass: blocked user can still reach the person through item question threads",
    targetRole: "Troll",
    measuredRecall: "",
  },
  {
    id: "S1",
    type: "single-user",
    description: "Checkout returns 500 on a specific empty-cart edge case",
    targetRole: "Casual buyer",
    measuredRecall: "",
  },
  {
    id: "S2",
    type: "single-user",
    description: "Negative quantity accepted in cart",
    targetRole: "Casual buyer",
    measuredRecall: "",
  },
  {
    id: "S4",
    type: "single-user",
    description: "Search crashes on a special character",
    targetRole: "Casual buyer",
    measuredRecall: "",
  },
];

/**
 * Section 11: Evaluation plan metrics — values are strictly blank as they are unmeasured in the PRD.
 */
export const BENCHMARK_TICKET_SLOTS: BlankMetricSlot[] = [
  {
    id: "verified-precision",
    label: "Reviewed precision",
    sublabel: "Supported findings after deterministic replay",
    value: "",
  },
  {
    id: "time-taken",
    label: "Time taken",
    sublabel: "Average total time per recorded SWARM run",
    value: "",
  },
  {
    id: "estimated-run-cost",
    label: "Estimated run cost",
    sublabel: "Average exploration cost, excluding judging",
    value: "",
  },
];

export const DASHBOARD_KPI_SLOTS: BlankMetricSlot[] = [
  {
    id: "kpi-recall",
    label: "Emergent-bug recall",
    sublabel: "Condition B vs. Condition C",
    value: "",
  },
  {
    id: "kpi-precision",
    label: "Verified precision",
    sublabel: "Deterministic DB snapshot replay",
    value: "",
  },
  {
    id: "kpi-cost",
    label: "Cost per run",
    sublabel: "Tokens and dollars per run",
    value: "",
  },
  {
    id: "kpi-time",
    label: "Time taken",
    sublabel: "Elapsed run time",
    value: "",
  },
];

export const BUSINESS_OUTCOME_SLOTS: BlankMetricSlot[] = [
  {
    id: "measured-run-cost",
    label: "Measured cost per run",
    sublabel: "To be set from measured cost per run across held-out seeds.",
    value: "",
  },
  {
    id: "cost-per-verified-bug",
    label: "Cost per verified bug",
    sublabel: "From benchmark evaluation; no unmeasured claims.",
    value: "",
  },
  {
    id: "hosted-tier-pricing",
    label: "Hosted tier price per run",
    sublabel: "Open-source CLI core; paid hosted tiers priced on usage.",
    value: "",
  },
];

export const TARGET_CATEGORIES = [
  "marketplaces",
  "booking",
  "fintech",
  "community",
] as const;

export function filterPlantedBugs(
  filter: "all" | "emergent" | "single-user",
): PlantedBugSpec[] {
  if (filter === "all") return PLANTED_BUGS;
  return PLANTED_BUGS.filter((bug) => bug.type === filter);
}

export function computeSliderFillPercent(
  value: number,
  min: number,
  max: number,
): number {
  if (max <= min) return 0;
  const clamped = Math.min(Math.max(value, min), max);
  return ((clamped - min) / (max - min)) * 100;
}

// Runtime YAML is generated and validated by POST /api/config/export.
