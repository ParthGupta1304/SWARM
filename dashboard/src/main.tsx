import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Event = { id: number; type?: string; event_type?: string; actor_id: number | null; payload: Record<string, unknown>; created_at: string };
type Finding = { id: string | number; bug_id?: string; mapped_bug_id?: string; title: string; severity: string; verified: boolean; created_at: string };
type Summary = { version: string; enabled_bugs: string[]; events: number; findings: number; verified_findings: number };

const api = import.meta.env.VITE_BAZAAR_API_URL ?? "http://localhost:8000";

function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const refresh = async () => {
      const [nextSummary, nextEvents, nextFindings] = await Promise.all([
        fetch(`${api}/api/dashboard/summary`).then((r) => r.json()),
        fetch(`${api}/api/events?limit=30`).then((r) => r.json()),
        fetch(`${api}/api/findings`).then((r) => r.json())
      ]);
      setSummary(nextSummary); setEvents(nextEvents); setFindings(nextFindings);
    };
    refresh().catch(console.error);
    const source = new EventSource(`${api}/api/events/stream`);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("activity", (raw) => {
      const next = JSON.parse((raw as MessageEvent).data) as Event;
      setEvents((current) => [next, ...current.filter((item) => item.id !== next.id)].slice(0, 30));
      refresh().catch(console.error);
    });
    return () => source.close();
  }, []);

  const severity = useMemo(() => findings.reduce<Record<string, number>>((counts, finding) => {
    counts[finding.severity] = (counts[finding.severity] ?? 0) + 1; return counts;
  }, {}), [findings]);

  return <main>
    <header><div><p className="eyebrow">SWARM / LIVE</p><h1>Bazaar swarm console</h1></div><span className={connected ? "status live" : "status"}>{connected ? "stream connected" : "reconnecting"}</span></header>
    <section className="metrics">
      <Metric label="release" value={summary?.version ?? "..."} />
      <Metric label="activity events" value={summary?.events ?? 0} />
      <Metric label="findings" value={summary?.findings ?? 0} />
      <Metric label="verified" value={summary?.verified_findings ?? 0} />
    </section>
    <section className="grid">
      <article><h2>Planted-bug scoreboard</h2><p className="muted">Enabled: {summary?.enabled_bugs.join(", ") || "loading"}</p><div className="scoreboard">{["E1", "E2", "E4", "E5", "E7", "S1", "S2", "S4"].map((bug) => {
        const hit = findings.find((finding) => (finding.mapped_bug_id ?? finding.bug_id) === bug); return <div className={hit ? "bug found" : "bug"} key={bug}><strong>{bug}</strong><span>{hit ? (hit.verified ? "verified" : "reported") : "not found"}</span></div>;
      })}</div></article>
      <article><h2>Finding stream</h2><p className="muted">{Object.entries(severity).map(([name, count]) => `${count} ${name}`).join(" · ") || "No findings yet"}</p><ul className="findings">{findings.slice(0, 8).map((finding) => <li key={finding.id}><b>{finding.mapped_bug_id ?? finding.bug_id}</b><span>{finding.title}</span><em>{finding.verified ? "verified" : "pending replay"}</em></li>)}</ul></article>
      <article className="wide"><h2>Agent activity</h2><ul className="events">{events.map((event) => <li key={event.id}><time>{new Date(event.created_at).toLocaleTimeString()}</time><b>{event.type ?? event.event_type}</b><span>{JSON.stringify(event.payload)}</span></li>)}</ul></article>
    </section>
  </main>;
}

function Metric({ label, value }: { label: string; value: string | number }) { return <div className="metric"><span>{label}</span><strong>{value}</strong></div>; }

createRoot(document.getElementById("root")!).render(<App />);
