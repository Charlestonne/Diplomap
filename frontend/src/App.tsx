// Base of the app (P4-07): every API call is wired and its response shown plainly.
// The Globe view (P4-08) and the Network view (P4-09) replace these lists.
import { useEffect, useState } from "react";
import { api } from "./api";
import type { VisitKpis } from "./types";

function useApi<T>(load: (() => Promise<T>) | null, key: string) {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  useEffect(() => {
    if (!load) return;
    let live = true;
    setState({});
    load().then(
      (data) => live && setState({ data }),
      (error: Error) => live && setState({ error: error.message }),
    );
    return () => {
      live = false;
    };
  }, [key]); // reload only when the key changes, not on each new `load` closure
  return state;
}

const fmt = (value: number | null, signed = false) =>
  value === null ? "—" : `${signed && value > 0 ? "+" : ""}${value.toFixed(2)}`;

// Labels from warehouse/profiling/gdelt_measures.md: cooperative share first, Goldstein as support.
const KPI_ROWS: [string, keyof VisitKpis, keyof VisitKpis, keyof VisitKpis][] = [
  ["Cooperative share", "coop_share_pre", "coop_share_post", "delta_coop_share"],
  ["Media tone of the coverage", "tone_pre", "tone_post", "delta_tone"],
  ["Event-type mix (Goldstein)", "goldstein_pre", "goldstein_post", "delta_goldstein"],
];

function VisitPanel({ visitKey }: { visitKey: number }) {
  const { data, error } = useApi(
    () => Promise.all([api.visit(visitKey), api.visitKpis(visitKey), api.visitEvents(visitKey)]),
    String(visitKey),
  );
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading…</p>;
  const [visit, kpis, events] = data;
  return (
    <section>
      <h2>
        {visit.leader_name} → {visit.host_country.country_name}, {visit.start_date_key} to {visit.end_date_key}
      </h2>
      <p>
        {kpis.n_events_pre} events before, {kpis.n_events_post} after
        {kpis.is_low_volume && " · Low volume: the deltas are fragile"}
        {kpis.has_overlap && " · Overlapping visit: the effects cannot be separated"}
      </p>
      <table>
        <thead>
          <tr>
            <th />
            <th>Before</th>
            <th>After</th>
            <th>Δ</th>
          </tr>
        </thead>
        <tbody>
          {KPI_ROWS.map(([label, pre, post, delta]) => (
            <tr key={label}>
              <th>{label}</th>
              <td>{fmt(kpis[pre] as number | null)}</td>
              <td>{fmt(kpis[post] as number | null)}</td>
              <td>{fmt(kpis[delta] as number | null, true)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>{events.length} events</h3>
      <ul>
        {events.map((e) => (
          <li key={e.gdelt_event_id}>
            {e.event_date_key} ({e.visit_window} {e.day_offset > 0 ? "+" : ""}
            {e.day_offset}) {e.actor1_country.iso3_code} → {e.actor2_country.iso3_code}, CAMEO {e.cameo_code}{" "}
            {e.source_url && (
              <a href={e.source_url} target="_blank" rel="noreferrer">
                source
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Visits() {
  const leaders = useApi(api.leaders, "leaders");
  const [leaderId, setLeaderId] = useState("");
  const [visitKey, setVisitKey] = useState<number | null>(null);
  const visits = useApi(leaderId ? () => api.visits(leaderId) : null, leaderId);
  return (
    <>
      {leaders.error && <p role="alert">{leaders.error}</p>}
      <label htmlFor="leader">Leader</label>{" "}
      <select
        id="leader"
        value={leaderId}
        onChange={(event) => {
          setLeaderId(event.target.value);
          setVisitKey(null);
        }}
      >
        <option value="">Choose a leader</option>
        {leaders.data?.map((l) => (
          <option key={l.leader_id} value={l.leader_id}>
            {l.leader_name} ({l.offices[l.offices.length - 1].represented_country.country_name})
          </option>
        ))}
      </select>
      {visits.error && <p role="alert">{visits.error}</p>}
      <ul>
        {leaderId &&
          visits.data?.map((v) => (
            <li key={v.visit_key}>
              <button onClick={() => setVisitKey(v.visit_key)}>
                {v.host_country.country_name}, {v.start_date_key} to {v.end_date_key}
              </button>
            </li>
          ))}
      </ul>
      {visitKey !== null && <VisitPanel visitKey={visitKey} />}
    </>
  );
}

function NetworkLists() {
  const { data, error } = useApi(api.network, "network");
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading…</p>;
  const label = new Map(data.nodes.map((n) => [n.id, n.label]));
  return (
    <>
      <h2>Leader–country graph</h2>
      <ul>
        {data.edges.map((e) => (
          <li key={`${e.source}-${e.type}-${e.target}`}>
            {label.get(e.source)}{" "}
            {e.type === "VISITED"
              ? `visited ${label.get(e.target)} (${e.n_visits}×)`
              : `represents ${label.get(e.target)}`}
          </li>
        ))}
      </ul>
      <h2>Shared destinations</h2>
      <ul>
        {data.shared_destinations.map((s) => (
          <li key={`${s.leader_a_id}-${s.leader_b_id}`}>
            {label.get(s.leader_a_id)} and {label.get(s.leader_b_id)}: {s.shared_countries.join(", ")}
          </li>
        ))}
      </ul>
      <h2>Reciprocal visits</h2>
      <ul>
        {data.reciprocal_visits.map((r) => (
          <li key={`${r.country_a}-${r.country_b}`}>
            {r.country_a} ↔ {r.country_b}
          </li>
        ))}
      </ul>
    </>
  );
}

export default function App() {
  const [tab, setTab] = useState<"globe" | "network">("globe");
  return (
    <main>
      <h1>DiploMap</h1>
      <nav>
        <button aria-pressed={tab === "globe"} onClick={() => setTab("globe")}>
          Globe
        </button>{" "}
        <button aria-pressed={tab === "network"} onClick={() => setTab("network")}>
          Network
        </button>
      </nav>
      {tab === "globe" ? <Visits /> : <NetworkLists />}
    </main>
  );
}
