// Network view (P4-09), laid out after the mock-up of pdfs/DiploMap.pdf: filters on the left, the leader–country graph
// of GET /network (Neo4j projection) in the middle, the selected country on the right, its visits below.
// Leaders sit on the left, countries on the right; VISITED edges are solid arrows, REPRESENTS edges dashed. A node
// grows with the visits it made (leader) or received (country).
import { useState } from "react";
import { api, MOCK, useApi } from "./api";
import { plural } from "./Globe";
import { dateRange, flag, VISIT_TYPE } from "./GlobeView";
import type { NetworkNode } from "./types";

const [W, LX, CX, TOP, ROW] = [640, 160, 480, 40, 72]; // leader column x, country column x, row spacing
const radius = (visits: number) => 14 + 5 * Math.sqrt(visits);
const countryOf = (node: NetworkNode) => ({ iso3_code: node.iso3_code ?? node.id, country_name: node.label });
const byLabel = (a: NetworkNode, b: NetworkNode) => a.label.localeCompare(b.label);

const Person = ({ x, y, r }: { x: number; y: number; r: number }) => (
  <g className="person" transform={`translate(${x - r / 2} ${y - r / 2}) scale(${r / 24})`}>
    <circle cx="12" cy="8" r="4.5" />
    <path d="M3.5 22c0-5 3.8-8 8.5-8s8.5 3 8.5 8" />
  </g>
);

// Keyboard and pointer activation of an SVG node, as on the globe's markers.
const press = (label: string, pressed: boolean, act: () => void) => ({
  role: "button",
  tabIndex: 0,
  "aria-label": label,
  "aria-pressed": pressed,
  onClick: act,
  onKeyDown: (e: React.KeyboardEvent) => (e.key === "Enter" || e.key === " ") && act(),
});

export default function NetworkView() {
  const network = useApi(api.network, "network");
  const visits = useApi(() => api.visits(), "visits");
  const [countryId, setCountryId] = useState("");
  const [leaderId, setLeaderId] = useState("");
  if (network.error) return <p role="alert">{network.error}</p>;
  if (!network.data) return <p>Loading…</p>;

  const { nodes, edges, reciprocal_visits } = network.data;
  const label = new Map(nodes.map((n) => [n.id, n.label]));
  const visited = edges.filter((e) => e.type === "VISITED");
  const count = (id: string, end: "source" | "target") =>
    visited.filter((e) => e[end] === id).reduce((n, e) => n + (e.n_visits ?? 0), 0);
  const leaders = nodes.filter((n) => n.type === "leader").sort(byLabel);
  const countries = nodes.filter((n) => n.type === "country").sort(byLabel);
  // Until one is chosen, the panel shows the most visited country.
  const country =
    countryId || countries.reduce((a, b) => (count(b.id, "target") > count(a.id, "target") ? b : a), countries[0])?.id;

  const rows = Math.max(leaders.length, countries.length);
  const H = 2 * TOP + (rows - 1) * ROW;
  const place = (list: NetworkNode[], x: number, end: "source" | "target") =>
    new Map(list.map((n, i) => [n.id, { x, y: TOP + (i + (rows - list.length) / 2) * ROW, r: radius(count(n.id, end)) }]));
  const at = new Map([...place(leaders, LX, "source"), ...place(countries, CX, "target")]);
  const active = (source: string, target: string) => source === leaderId || target === country;

  const into = edges.filter((e) => e.target === country);
  const representatives = into.filter((e) => e.type === "REPRESENTS").map((e) => label.get(e.source));
  const reciprocal = reciprocal_visits
    .filter((r) => r.country_a === country || r.country_b === country)
    .map((r) => label.get(r.country_a === country ? r.country_b : r.country_a));
  const node = countries.find((c) => c.id === country);
  const table = (visits.data ?? [])
    .filter((v) => (!country || [v.host_country.iso3_code, v.visitor_country.iso3_code].includes(country)))
    .filter((v) => !leaderId || v.leader_id === leaderId)
    .sort((a, b) => b.start_date_key.localeCompare(a.start_date_key));

  return (
    <div className="network-view">
      <aside className="card filters">
        <label htmlFor="net-country">Country</label>
        <select id="net-country" value={country} onChange={(e) => setCountryId(e.target.value)}>
          {countries.map((c) => (
            <option key={c.id} value={c.id}>
              {flag(countryOf(c))} {c.label}
            </option>
          ))}
        </select>
        <label htmlFor="net-leader">Leader</label>
        <select id="net-leader" value={leaderId} onChange={(e) => setLeaderId(e.target.value)}>
          <option value="">All leaders</option>
          {leaders.map((l) => (
            <option key={l.id} value={l.id}>
              {l.label}
            </option>
          ))}
        </select>
        <hr />
        <h2 className="label">Node size</h2>
        <p className="muted small">Number of visits</p>
        <ul className="net-legend">
          <li>
            <span className="key leader" /> Leader: visits made
          </li>
          <li>
            <span className="key country" /> Country: visits received
          </li>
        </ul>
        <svg className="sizes" viewBox="0 0 220 56" aria-hidden="true">
          {[1, 3, 6, 10].map((n, i) => (
            <g key={n} transform={`translate(${28 + i * 54} 26)`}>
              <circle r={radius(n) / 1.6} />
              <text y={radius(10) / 1.6 + 8} textAnchor="middle">
                {n}
              </text>
            </g>
          ))}
        </svg>
        <h2 className="label">Edge type</h2>
        <ul className="net-legend">
          <li>
            <svg viewBox="0 0 40 10" aria-hidden="true">
              <path className="edge" d="M2 5h30" markerEnd="url(#arrow)" />
            </svg>
            Visited
          </li>
          <li>
            <svg viewBox="0 0 40 10" aria-hidden="true">
              <path className="edge represents" d="M2 5h34" />
            </svg>
            Represents
          </li>
        </ul>
        <p className="note">ⓘ One representative per country.</p>
      </aside>

      <section className="card graph" aria-label="Network graph">
        <h2>International visits and representation network</h2>
        <p className="muted">Leaders (left) and countries (right)</p>
        <div className="scroll">
          <svg className="network" viewBox={`0 0 ${W} ${H}`}>
            <defs>
              {["arrow", "arrow-active"].map((id) => (
                <marker key={id} id={id} className={id} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                  <path d="M0 1 9 5 0 9z" />
                </marker>
              ))}
            </defs>
            {edges.map((e) => {
              const [a, b] = [at.get(e.source)!, at.get(e.target)!];
              const [x1, x2, mid] = [a.x + a.r, b.x - b.r - 2, (a.x + b.x) / 2];
              const on = active(e.source, e.target);
              return (
                <path
                  key={`${e.source}-${e.type}-${e.target}`}
                  className={`edge ${e.type === "REPRESENTS" ? "represents" : ""} ${on ? "active" : ""}`}
                  d={`M${x1},${a.y} C${mid},${a.y} ${mid},${b.y} ${x2},${b.y}`}
                  strokeWidth={e.n_visits ? 1 + e.n_visits : undefined}
                  markerEnd={e.type === "VISITED" ? `url(#${on ? "arrow-active" : "arrow"})` : undefined}
                >
                  <title>
                    {e.type === "VISITED"
                      ? `${label.get(e.source)} visited ${label.get(e.target)} (${plural(e.n_visits ?? 0, "visit")})`
                      : `${label.get(e.source)} represents ${label.get(e.target)}`}
                  </title>
                </path>
              );
            })}
            {leaders.map((l) => {
              const { x, y, r } = at.get(l.id)!;
              return (
                <g
                  key={l.id}
                  className={`node leader ${l.id === leaderId ? "selected" : ""}`}
                  {...press(`${l.label}, ${plural(count(l.id, "source"), "visit")} made`, l.id === leaderId, () =>
                    setLeaderId(l.id === leaderId ? "" : l.id),
                  )}
                >
                  <circle cx={x} cy={y} r={r} />
                  <Person x={x} y={y} r={r} />
                  <text x={x - r - 10} y={y + 5} textAnchor="end">
                    {l.label}
                  </text>
                </g>
              );
            })}
            {countries.map((c) => {
              const { x, y, r } = at.get(c.id)!;
              return (
                <g
                  key={c.id}
                  className={`node country ${c.id === country ? "selected" : ""}`}
                  {...press(`${c.label}, ${plural(count(c.id, "target"), "visit")} received`, c.id === country, () =>
                    setCountryId(c.id),
                  )}
                >
                  <circle cx={x} cy={y} r={r} />
                  <text className="flag" x={x} y={y} fontSize={r * 1.1} textAnchor="middle" dominantBaseline="central">
                    {flag(countryOf(c))}
                  </text>
                  <text x={x + r + 10} y={y + 5}>
                    {c.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </section>

      {node && (
        <section className="card visit country-panel" aria-label="Selected country">
          <div className="visit-head">
            <span className="flags" aria-hidden="true">
              {flag(countryOf(node))}
            </span>
            <div>
              <h2>{node.label}</h2>
              <p className="muted">
                {plural(new Set(into.filter((e) => e.type === "VISITED").map((e) => e.source)).size, "leader")} visited ·{" "}
                {plural(representatives.length, "representative")}
              </p>
            </div>
          </div>
          <h3>Leaders</h3>
          <ul className="net-leaders">
            {into.map((e) => (
              <li key={`${e.source}-${e.type}`}>
                <span className="key leader" aria-hidden="true" />
                <span>
                  <b>{label.get(e.source)}</b>
                  <small>{e.type === "VISITED" ? plural(e.n_visits ?? 0, "visit") : "Representative"}</small>
                </span>
                <span className={`badge ${e.type.toLowerCase()}`}>{e.type}</span>
              </li>
            ))}
          </ul>
          <h3>About {node.label}</h3>
          <dl className="about">
            <dt>Visits received</dt>
            <dd>{count(node.id, "target")}</dd>
            <dt>Visits made</dt>
            <dd>{edges.filter((e) => e.type === "REPRESENTS" && e.target === node.id).reduce((n, e) => n + count(e.source, "source"), 0)}</dd>
            <dt>Representative</dt>
            <dd>{representatives.join(", ") || "—"}</dd>
            <dt>Reciprocal visits with</dt>
            <dd>{reciprocal.join(", ") || "—"}</dd>
          </dl>
        </section>
      )}

      <section className="card wide" aria-label="Recent visits">
        <h2>
          Recent visits {node && <span className="muted">involving {node.label}</span>}{" "}
          {MOCK && <span className="muted">(illustrative data)</span>}
        </h2>
        {visits.error && <p role="alert">{visits.error}</p>}
        <div className="scroll">
          <table className="events">
            <thead>
              <tr>
                <th>Visiting leader</th>
                <th>From</th>
                <th>To</th>
                <th>Type</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {table.map((v) => (
                <tr key={v.visit_key}>
                  <td>{v.leader_name}</td>
                  <td>
                    {flag(v.visitor_country)} {v.visitor_country.country_name}
                  </td>
                  <td>
                    {flag(v.host_country)} {v.host_country.country_name}
                  </td>
                  <td>
                    <span className="pill">{VISIT_TYPE[v.visit_type_label]}</span>
                  </td>
                  <td>{dateRange(v.start_date_key, v.end_date_key)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
