export type Condition = "swarm" | "isolated";
export type Options = {
  normal_agents: number;
  adversary_agents: number;
  max_dollars: number;
  seed: number;
};
export type Bug = {
  id: string;
  type: "emergent" | "single-user";
  description: string;
};
export type Config = Options & {
  model: string;
  provider: string;
  population_cap: number;
  max_dollars_cap: number;
  max_rounds: number;
  benchmark_rounds: number;
  token_budget: number;
  roles: { id: string; name: string; count: number; objective: string }[];
  bugs: Bug[];
};
export type Usage = {
  model_calls?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  cached_prompt_tokens?: number;
  cache_reporting?: string;
  cost_usd?: number;
  compactions?: number;
  repeat_redirections?: number;
  pacing_wait_s?: number;
};
export type Actor = {
  agent_id: string;
  role: string;
  steps: number;
  tokens_used: number;
  score: number;
  score_unit?: string;
  invalid_tool_calls: number;
  total_tool_calls: number;
  stop_reason?: string;
  error?: string;
  efficiency?: Usage;
};
export type Action = {
  event_id: string;
  agent_id: string;
  role: string;
  round: number;
  sequence: number;
  tool: string;
  request: {
    method: string;
    path: string;
    json_body?: unknown;
    query?: Record<string, unknown>;
  };
  response_status: number | null;
  tokens_used: number;
  latency_ms: number;
  concurrency_group?: string;
};
export type ReproAction = {
  event_id: string;
  agent_id: string;
  request: Action["request"];
  expected_status?: number;
};
export type Finding = {
  id: string;
  run_id: string;
  title: string;
  severity: string;
  type: "emergent" | "single-user";
  verified: boolean;
  mapped_bug_id?: string;
  involved_agents: string[];
  oracle_triggered: string;
  evidence: unknown[];
  verification?: unknown;
  causality?: string;
  minimal_repro_sequence: { seed: number; steps: { actions: ReproAction[] }[] };
};
export type Recheck = {
  finding_id: string;
  run_id: string;
  status: "running" | "completed" | "stopped" | "error";
  error?: string;
  target_version?: string;
  seed?: number;
  result?: {
    status: "verified" | "not_reproduced" | "error";
    attempts: unknown[];
  };
};
export type Run = {
  run_id: string;
  condition: Condition;
  seed: number;
  model: string;
  status: string;
  round?: number;
  token_budget: number;
  tokens_used: number;
  cost_usd: number;
  elapsed_s: number;
  actors?: number;
  actor_count?: number;
  agents: Actor[];
  efficiency?: Usage;
  findings?: Finding[];
  actions?: Action[];
  assessments?: Record<string, boolean>;
  rechecks?: Recheck[];
  saved_at?: number;
  source?: string;
  provenance?: { source?: string };
  finding_times_s?: Record<string, number>;
  stopped?: boolean;
};
export type History = Omit<Run, "agents"> & { verified_ids: string[] };
export type Metric = {
  mean: number | null;
  min: number | null;
  max: number | null;
  measured_runs?: number;
};
export type Benchmark = {
  conditions: Record<Condition, { metrics: Record<string, Metric> }>;
  runs: (Run & { findings?: Finding[]; found_bug_ids?: string[] })[];
  dev_seed?: number;
};
export type State = {
  generation: string;
  busy: boolean;
  error: string | null;
  resetting: boolean;
  reset_failed: boolean;
  reset_allowed: boolean;
  model: string;
  max_rounds: number;
  token_budget: number;
  runs: Run[];
  actions: Action[];
  findings: Finding[];
  benchmark: Benchmark | null;
  gate: { complete: boolean; pending: string[]; source?: string } | null;
  recheck?: Recheck | null;
};
