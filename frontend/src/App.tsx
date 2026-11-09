// DiploMap: the Globe view (P4-08) and, until P4-09 replaces it, a plain list of the network.
import { useState } from "react";
import { api, MOCK, useApi } from "./api";
import GlobeView from "./GlobeView";

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

const GlobeIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <ellipse cx="12" cy="12" rx="4" ry="9" />
    <path d="M3 12h18" />
  </svg>
);

const NetworkIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <circle cx="12" cy="5" r="2.5" />
    <circle cx="5" cy="19" r="2.5" />
    <circle cx="19" cy="19" r="2.5" />
    <path d="M12 7.5v4m0 0-5.5 5.5m5.5-5.5 5.5 5.5" />
  </svg>
);

// Header after the mock-ups of pdfs/DiploMap.pdf: brand, view tabs, period of the data.
export default function App() {
  const [tab, setTab] = useState<"globe" | "network">("globe");
  return (
    <>
      <header className="topbar">
        <h1>
          <GlobeIcon /> DiploMap <small>Diplomatic travel explorer</small>
        </h1>
        <nav className="tabs">
          <button aria-pressed={tab === "globe"} onClick={() => setTab("globe")}>
            <GlobeIcon /> Globe
          </button>
          <button aria-pressed={tab === "network"} onClick={() => setTab("network")}>
            <NetworkIcon /> Network
          </button>
        </nav>
        <p className="scope">
          Jan – Jun 2025
          {MOCK && (
            <span title="Mock responses of src/mocks/; set VITE_API_URL to read the API"> · Illustrative data ⓘ</span>
          )}
        </p>
      </header>
      <main>{tab === "globe" ? <GlobeView /> : <NetworkLists />}</main>
    </>
  );
}
