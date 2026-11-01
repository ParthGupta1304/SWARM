import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type {
  Benchmark,
  Condition,
  Config,
  Finding,
  History,
  Options,
  Run,
  State,
} from "./types";

export async function request<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(
    url,
    body === undefined
      ? { cache: "no-store" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    let detail = "";
    try {
      detail = (await response.json()).detail;
    } catch {}
    throw new Error(
      typeof detail === "string"
        ? detail
        : `Request failed (HTTP ${response.status})`,
    );
  }
  return response.json();
}
export function download(name: string, content: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function clearBrowser() {
  localStorage.removeItem("bazaar-user");
  if ("caches" in window) {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter((k) => /^(swarm|bazaar)/.test(k))
        .map((k) => caches.delete(k)),
    );
  }
}
function useConsoleData() {
  const [state, setState] = useState<State | null>(null),
    [config, setConfig] = useState<Config | null>(null),
    [options, setOptions] = useState<Options | null>(null),
    [history, setHistory] = useState<History[]>([]),
    [selected, setSelected] = useState("live"),
    [saved, setSaved] = useState<Run | null>(null),
    [condition, setCondition] = useState<Condition>("swarm"),
    [connected, setConnected] = useState(false),
    [error, setError] = useState(""),
    [pending, setPending] = useState(false),
    [yaml, setYaml] = useState(""),
    [configError, setConfigError] = useState(""),
    [findingId, setFindingId] = useState("");
  const generation = useRef(""),
    retired = useRef(new Set<string>()),
    autoSelect = useRef(true),
    stateRef = useRef<State | null>(null),
    disposed = useRef(false),
    busyRef = useRef(false);
  const loadHistory = useCallback(async () => {
    const rows = await request<History[]>("/api/history");
    if (disposed.current) return;
    setHistory(rows);
    if (
      autoSelect.current &&
      !stateRef.current?.busy &&
      !stateRef.current?.runs.length
    ) {
      const latest =
        rows.find(
          (r) => r.status === "completed" && r.model !== "scripted-fixture",
        ) || rows.find((r) => r.status === "completed");
      if (latest) {
        autoSelect.current = false;
        setSelected(latest.run_id);
        setCondition(latest.condition);
      }
    }
  }, []);
  const accept = useCallback(
    (next: State) => {
      if (disposed.current || retired.current.has(next.generation)) return;
      if (generation.current && generation.current !== next.generation) {
        retired.current.add(generation.current);
        setHistory([]);
        setSaved(null);
        setSelected("live");
        setFindingId("");
        autoSelect.current = false;
        clearBrowser().catch(() => {});
      }
      generation.current = next.generation;
      sessionStorage.setItem("swarm-generation", next.generation);
      localStorage.setItem("swarm-workspace-generation", next.generation);
      stateRef.current = next;
      setState(next);
      setConnected(true);
      if (
        !next.resetting &&
        !next.reset_failed &&
        busyRef.current &&
        !next.busy
      )
        loadHistory().catch(() => {});
      busyRef.current = next.busy;
    },
    [loadHistory],
  );
  const refresh = useCallback(async () => {
    try {
      accept(await request<State>("/api/state"));
    } catch {
      if (!disposed.current) setConnected(false);
    }
  }, [accept]);
  useEffect(() => {
    disposed.current = false;
    request<Config>("/api/config")
      .then((c) => {
        if (disposed.current) return;
        setConfig(c);
        setOptions({
          normal_agents: c.normal_agents,
          adversary_agents: c.adversary_agents,
          max_dollars: c.max_dollars,
          seed: c.seed,
        });
      })
      .catch((e) => setError(e.message));
    refresh().then(() => loadHistory().catch(() => {}));
    const source = new EventSource("/api/stream");
    source.onmessage = (e) => {
      try {
        accept(JSON.parse(e.data));
      } catch {}
    };
    source.onerror = () => setConnected(false);
    source.addEventListener("unavailable", () => setConnected(false));
    const timer = setInterval(() => {
      refresh();
      request<Config>("/api/config")
        .then((c) => {
          if (disposed.current) return;
          setConfig(c);
          setOptions(
            (previous) =>
              previous || {
                normal_agents: c.normal_agents,
                adversary_agents: c.adversary_agents,
                max_dollars: c.max_dollars,
                seed: c.seed,
              },
          );
        })
        .catch(() => {});
    }, 4000);
    return () => {
      disposed.current = true;
      clearInterval(timer);
      source.close();
    };
  }, [accept, refresh, loadHistory]);
  useEffect(() => {
    let stale = false;
    if (selected === "live") {
      setSaved(null);
      return;
    }
    setSaved((previous) => (previous?.run_id === selected ? previous : null));
    request<Run>(`/api/history/${selected}`)
      .then((run) => {
        if (!stale) setSaved(run);
      })
      .catch((e) => {
        if (!stale) setError(e.message);
      });
    return () => {
      stale = true;
    };
  }, [selected, state?.generation]);
  useEffect(() => {
    if (!options) return;
    let stale = false;
    setConfigError("");
    setYaml("");
    const timer = setTimeout(async () => {
      try {
        const response = await fetch("/api/config/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(options),
        });
        if (!response.ok)
          throw new Error(
            (await response.json()).detail || "Invalid configuration",
          );
        const text = await response.text();
        if (!stale) setYaml(text);
      } catch (e) {
        if (!stale) setConfigError((e as Error).message);
      }
    }, 250);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [options]);
  useEffect(() => {
    if (
      selected === "live" ||
      !state?.recheck ||
      state.recheck.status === "running"
    )
      return;
    request<Run>(`/api/history/${selected}`)
      .then(setSaved)
      .catch(() => {});
  }, [state?.recheck?.status, state?.recheck?.finding_id, selected]);
  const current =
    state?.runs.find((r) => r.status === "running") ||
    state?.runs.at(-1) ||
    null;
  const candidate: Run | null =
    selected === "live"
      ? current
        ? {
            ...current,
            findings: (state?.findings || []).filter(
              (f) => f.run_id === current.run_id,
            ),
            actions: (state?.actions || []).filter(
              (a) =>
                (a as unknown as { run_id: string }).run_id === current.run_id,
            ),
          }
        : null
      : saved;
  const run = candidate?.condition === condition ? candidate : null;
  const findings = run?.findings || [],
    finding: Finding | null =
      findings.find((f) => f.id === findingId) || findings[0] || null;
  const command = async (path: string, body: unknown = {}) => {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await request(path, body);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setPending(false);
    }
  };
  const start = async (benchmark = false) => {
    autoSelect.current = false;
    setSelected("live");
    setSaved(null);
    setFindingId("");
    await command("/api/start", {
      condition: benchmark ? "benchmark" : condition,
      options,
    });
  };
  const reset = async () => {
    autoSelect.current = false;
    await command("/api/reset", { confirmed: true });
  };
  const choose = (id: string) => {
    autoSelect.current = false;
    setSelected(id);
    const row = history.find((r) => r.run_id === id);
    if (row) setCondition(row.condition);
    setFindingId("");
    setError("");
  };
  const changeCondition = (value: Condition) => {
    setCondition(value);
    const row = history.find(
      (r) => r.condition === value && r.status === "completed",
    );
    choose(row?.run_id || "live");
  };
  const recheck = async () => {
    if (finding)
      await command("/api/recheck", {
        run_id: finding.run_id,
        finding_id: finding.id,
      });
  };
  const review = async (correct: boolean, reviewer: string, note: string) => {
    if (finding) {
      const inBenchmark = benchmark?.runs.some(
        (r) => r.run_id === finding.run_id,
      );
      await command("/api/review", {
        finding_id: finding.id,
        correct,
        reviewer,
        note,
        ...(inBenchmark ? {} : { run_id: finding.run_id }),
      });
      const reviewed = await request<Run>(`/api/history/${finding.run_id}`);
      setFindingId(finding.id);
      setSaved(reviewed);
      setSelected(finding.run_id);
    }
  };
  const benchmark: Benchmark | null =
    state?.benchmark &&
    (!run || state.benchmark.runs.some((row) => row.run_id === run.run_id))
      ? state.benchmark
      : null;
  const historicalEvaluation =
    !run && !benchmark && !state?.busy && !!config?.evaluation;
  const evaluationBenchmark =
    benchmark || (historicalEvaluation ? config?.evaluation?.benchmark : null);
  const evaluationLabel = historicalEvaluation
    ? `Historical real-AI benchmark · ${config?.evaluation?.rounds_per_run} rounds per run · seeds 11, 22, 33. Separate from this workspace.`
    : run
      ? "Evaluation of the selected run. Multi-seed metrics require a matching benchmark."
      : "Evaluation of the current benchmark.";
  return {
    state,
    config,
    options,
    setOptions,
    history,
    selected,
    choose,
    run,
    findings,
    finding,
    setFindingId,
    condition,
    setCondition: changeCondition,
    connected,
    error,
    setError,
    pending,
    yaml,
    configError,
    start,
    reset,
    recheck,
    review,
    command,
    refresh,
    loadHistory,
    benchmark,
    evaluationBenchmark,
    historicalEvaluation,
    evaluationLabel,
  };
}
type ConsoleData = ReturnType<typeof useConsoleData>;
const ConsoleContext = createContext<ConsoleData | null>(null);
export function ConsoleProvider({ children }: { children: ReactNode }) {
  const value = useConsoleData();
  return (
    <ConsoleContext.Provider value={value}>{children}</ConsoleContext.Provider>
  );
}
export function useConsole() {
  const data = useContext(ConsoleContext);
  if (!data) throw new Error("Console provider missing");
  return data;
}
