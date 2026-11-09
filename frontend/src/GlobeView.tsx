// Globe view (P4-08), laid out after the mock-up of pdfs/DiploMap.pdf: filters and visits on the left, the globe in
// the middle, the selected visit on the right, its related events below.
// Display rules (warehouse/profiling/gdelt_measures.md, table_contracts/v_kpi_visit.yml): cooperative share first and
// Goldstein as support; event counts beside the deltas, with the low-volume and overlap flags; a null mean shows "—",
// never 0; the visit days belong to neither window.
import { alpha3ToAlpha2 } from "i18n-iso-countries";
import { useState } from "react";
import { api, MOCK, useApi } from "./api";
import Globe, { plural } from "./Globe";
import type { Country, Leader, VisitEvent, VisitKpis, VisitSummary, VisitTypeLabel } from "./types";

export const SCOPE = { from: "2025-01-01", to: "2025-06-30" }; // visits of the first half of 2025 (report, §1)
const DAYS = 15; // length of each window in v_visit_event

const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const date = (day: string) => DATE.format(new Date(day));
const dateRange = (from: string, to: string) => DATE.formatRange(new Date(from), new Date(to)); // "10 – 12 Mar 2025"
const signed = (day: number) => (day > 0 ? `+${day}` : `−${-day}`);

// Emoji flag from the alpha-2 code (regional indicator letters); empty when the code is unknown.
const flag = (country: Country) =>
  String.fromCodePoint(...[...(alpha3ToAlpha2(country.iso3_code) ?? "")].map((c) => 0x1f1a5 + c.charCodeAt(0)));

const VISIT_TYPE: Record<VisitTypeLabel, string> = {
  state: "State visit",
  working: "Working visit",
  summit: "Summit",
  ceremony: "Ceremony",
  unknown: "Official visit",
};

// Root categories of the CAMEO codebook (DB/CAMEO.eventcodes.txt): the first two digits of an event code.
const CAMEO_ROOT = [
  "Make public statement",
  "Appeal",
  "Express intent to cooperate",
  "Consult",
  "Engage in diplomatic cooperation",
  "Engage in material cooperation",
  "Provide aid",
  "Yield",
  "Investigate",
  "Demand",
  "Disapprove",
  "Reject",
  "Threaten",
  "Protest",
  "Exhibit force posture",
  "Reduce relations",
  "Coerce",
  "Assault",
  "Fight",
  "Use unconventional mass violence",
];

const num = (value: number | null, delta = false) =>
  value === null ? "—" : `${delta && value > 0 ? "+" : ""}${value.toFixed(2)}`;
const pct = (value: number | null, delta = false) =>
  value === null ? "—" : delta ? `${value > 0 ? "+" : ""}${Math.round(value * 100)} pp` : `${Math.round(value * 100)}%`;

// Cooperative share leads (P2-11); the ⓘ hints carry the caveats of gdelt_measures.md.
const KPIS = [
  {
    key: "coop_share",
    label: "Cooperative share",
    fmt: pct,
    hint: "Share of cooperative events (CAMEO quad class 1–2). A rise after a visit is partly mechanical: the visit itself adds cooperative events.",
  },
  {
    key: "tone",
    label: "Article tone",
    fmt: num,
    hint: "Mean tone of the articles that first reported the events (GDELT AvgTone): the media coverage of the pair, not the relationship.",
  },
  {
    key: "goldstein",
    label: "Goldstein score",
    fmt: num,
    hint: "Mean Goldstein score: the mix of event types, not their intensity. It moves with tone; read the two as one signal.",
  },
] as const;

function Kpi({ kpi, kpis }: { kpi: (typeof KPIS)[number]; kpis: VisitKpis }) {
  const delta = kpis[`delta_${kpi.key}`];
  const trend = delta === null ? "none" : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  return (
    <div className="kpi" role="group" aria-label={kpi.label}>
      <p className="kpi-title">
        {kpi.label}
        {"\u00a0"}
        <span className="info" title={kpi.hint}>
          ⓘ
        </span>
      </p>
      <dl>
        <div>
          <dt>Before</dt>
          <dd>{kpi.fmt(kpis[`${kpi.key}_pre`])}</dd>
        </div>
        <div>
          <dt>After</dt>
          <dd>{kpi.fmt(kpis[`${kpi.key}_post`])}</dd>
        </div>
      </dl>
      <p className={`delta ${trend}`}>
        <span aria-hidden="true">{{ up: "▲ ", down: "▼ ", flat: "", none: "" }[trend]}</span>
        {kpi.fmt(delta, true)}
      </p>
    </div>
  );
}

// Events per day, cooperative and conflict stacked. The visit days sit in the middle, in neither window.
function WindowChart({ events, visitDays }: { events: VisitEvent[]; visitDays: number }) {
  if (!events.length) return <p className="muted">No GDELT event between the two countries in either window.</p>;
  const [W, H, LEFT, BASE] = [640, 130, 28, 104];
  const slot = (W - LEFT) / (2 * DAYS + 2); // 15 days, the visit on two slots, 15 days
  const x = (day: number) => LEFT + (day + DAYS + (day > 0 ? 1 : 0)) * slot; // day 0 = the visit's first slot
  const days = [...Array(DAYS).keys()].flatMap((i) => [-(i + 1), i + 1]).sort((a, b) => a - b);
  const count = (day: number, coop: boolean) =>
    events.filter((e) => e.day_offset === day && e.is_cooperative === coop).length;
  const max = Math.max(...days.map((d) => count(d, true) + count(d, false)));
  const unit = (BASE - 12) / max;
  const pre = events.filter((e) => e.day_offset < 0).length;
  return (
    <>
      <p className="legend">
        <span className="swatch coop" /> Cooperative <span className="swatch conflict" /> Conflict
      </p>
      <div className="scroll">
        <svg
          className="chart"
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`Events per day: ${pre} before the visit, ${events.length - pre} after`}
        >
          <line className="grid" x1={LEFT} x2={W} y1={BASE - max * unit} y2={BASE - max * unit} />
          <text className="tick" x={LEFT - 4} y={BASE - max * unit + 4} textAnchor="end">
            {max}
          </text>
          <line className="axis" x1={LEFT} x2={W} y1={BASE} y2={BASE} />
          <g>
            <title>{`Visit: ${plural(visitDays, "day")}, in neither window`}</title>
            <rect className="visit-band" x={x(0)} y={BASE - max * unit} width={2 * slot} height={max * unit} />
            <text className="tick" x={x(0) + slot} y={BASE + 14} textAnchor="middle">
              visit
            </text>
          </g>
          {days.map((day) => {
            const [coop, conflict] = [count(day, true), count(day, false)];
            return (
              <g key={day}>
                <title>{`Day ${signed(day)}: ${coop} cooperative, ${conflict} conflict`}</title>
                <rect className="hit" x={x(day)} y={0} width={slot} height={BASE} />
                {coop > 0 && (
                  <rect className="coop" x={x(day) + 1} y={BASE - coop * unit} width={slot - 2} height={coop * unit} />
                )}
                {conflict > 0 && (
                  <rect
                    className="conflict"
                    x={x(day) + 1}
                    y={BASE - (coop + conflict) * unit - (coop ? 2 : 0)}
                    width={slot - 2}
                    height={conflict * unit}
                  />
                )}
                {[1, 5, 10, 15].includes(Math.abs(day)) && (
                  <text className="tick" x={x(day) + slot / 2} y={BASE + 14} textAnchor="middle">
                    {signed(day)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </>
  );
}

const host = (url: string) => (URL.canParse(url) ? new URL(url).hostname.replace(/^www\./, "") : url);

// The visit card (right column) and its related events (bottom row), from the three per-visit routes.
function VisitDetails({ visitKey }: { visitKey: number }) {
  const [open, setOpen] = useState(true);
  const { data, error } = useApi(
    () => Promise.all([api.visit(visitKey), api.visitKpis(visitKey), api.visitEvents(visitKey)]),
    String(visitKey),
  );
  if (error)
    return (
      <section className="card visit">
        <p role="alert">{error}</p>
      </section>
    );
  if (!data)
    return (
      <section className="card visit">
        <p>Loading…</p>
      </section>
    );
  const [visit, kpis, events] = data;
  const [from, to] = [visit.visitor_country, visit.host_country];
  return (
    <>
      <section className="card visit" aria-label="Selected visit">
        <div className="visit-head">
          <span className="flags" aria-hidden="true">
            {flag(from)} <span>→</span> {flag(to)}
          </span>
          <div>
            <h2>
              {from.country_name} → {to.country_name}
            </h2>
            <p className="muted">{dateRange(visit.start_date_key, visit.end_date_key)}</p>
            <span className="pill">{VISIT_TYPE[visit.visit_type_label]}</span>
          </div>
        </div>
        <h3>
          {DAYS} days before / {DAYS} days after
        </h3>
        <div className="kpis">
          {KPIS.map((kpi) => (
            <Kpi key={kpi.key} kpi={kpi} kpis={kpis} />
          ))}
        </div>
        <div className="counts">
          <span className="counts-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <rect x="5" y="3" width="14" height="18" rx="2" />
              <path d="M8.5 8h7M8.5 12h7M8.5 16h4" />
            </svg>
          </span>
          <p>
            <b>PRE: {plural(kpis.n_events_pre, "event")}</b>
            <span>{dateRange(visit.pre_window_start, visit.pre_window_end)}</span>
          </p>
          <p>
            <b>POST: {plural(kpis.n_events_post, "event")}</b>
            <span>{dateRange(visit.post_window_start, visit.post_window_end)}</span>
          </p>
        </div>
        {kpis.is_low_volume && (
          <p className="note warn">⚠ Low volume: fewer than 10 events in a window, so the changes are fragile.</p>
        )}
        {kpis.has_overlap && (
          <p className="note warn">
            ⚠ Overlapping visit: another {from.country_name}–{to.country_name} visit shares these windows; their effects
            cannot be separated.
          </p>
        )}
        {visit.is_multilateral && (
          <p className="note">
            Multilateral visit: only the {from.country_name}–{to.country_name} events are counted.
          </p>
        )}
        <a className="primary" href="#related-events" onClick={() => setOpen(true)}>
          Explore related events →
        </a>
        <p className="note">ⓘ Observed changes do not imply causality.</p>
      </section>
      <details id="related-events" className="card related" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary>
          <h2>
            Related events <span className="muted">{MOCK ? "(illustrative)" : `(${events.length})`}</span>
          </h2>
        </summary>
        <h3>Events per day</h3>
        <WindowChart events={events} visitDays={visit.duration_days} />
        {events.length > 0 && (
          <div className="scroll">
            <table className="events">
              <caption>{plural(events.length, "event")}</caption>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Event</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.gdelt_event_id}>
                    <td>
                      {date(e.event_date_key)} <span className="muted">· day {signed(e.day_offset)}</span>
                    </td>
                    <td>
                      {e.actor1_country.country_name} → {e.actor2_country.country_name}:{" "}
                      {CAMEO_ROOT[Number(e.cameo_code.slice(0, 2)) - 1] ?? "Event"}{" "}
                      <span className="muted">
                        (CAMEO {e.cameo_code}, {e.is_cooperative ? "cooperative" : "conflict"})
                      </span>
                    </td>
                    <td>
                      {e.source_url && (
                        <a href={e.source_url} target="_blank" rel="noreferrer">
                          {host(e.source_url)} <span aria-hidden="true">↗</span>
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </>
  );
}

const countryOf = (leader: Leader) => leader.offices[leader.offices.length - 1].represented_country;

export default function GlobeView() {
  const leaders = useApi(api.leaders, "leaders");
  const [home, setHome] = useState("");
  const [leaderId, setLeaderId] = useState("");
  const [range, setRange] = useState(SCOPE);
  const [visitKey, setVisitKey] = useState<number | null>(null);
  const visits = useApi(leaderId ? () => api.visits(leaderId) : null, leaderId);

  const all = leaders.data ?? [];
  const homes = [...new Map(all.map((l) => [countryOf(l).iso3_code, countryOf(l)])).values()].sort((a, b) =>
    a.country_name.localeCompare(b.country_name),
  );
  const list: VisitSummary[] = ((leaderId && visits.data) || [])
    .filter((v) => v.start_date_key <= range.to && v.end_date_key >= range.from)
    .sort((a, b) => b.start_date_key.localeCompare(a.start_date_key)); // latest first
  const selected = list.find((v) => v.visit_key === visitKey);

  const chooseLeader = (id: string) => {
    setLeaderId(id);
    setVisitKey(null);
    const leader = all.find((l) => l.leader_id === id);
    if (leader) setHome(countryOf(leader).iso3_code);
  };
  const chooseHome = (iso3: string) => {
    setHome(iso3);
    const leader = all.find((l) => l.leader_id === leaderId);
    if (leader && iso3 && countryOf(leader).iso3_code !== iso3) chooseLeader("");
  };
  // A click on a country opens its latest visit (the list is latest first).
  const pick = (iso3: string) => setVisitKey(list.find((v) => v.host_country.iso3_code === iso3)!.visit_key);

  return (
    <div className="globe-view">
      <aside className="card filters">
        {leaders.error && <p role="alert">{leaders.error}</p>}
        <label htmlFor="leader">Leader</label>
        <select id="leader" value={leaderId} onChange={(e) => chooseLeader(e.target.value)}>
          <option value="">Choose a leader</option>
          {all
            .filter((l) => !home || countryOf(l).iso3_code === home)
            .map((l) => (
              <option key={l.leader_id} value={l.leader_id}>
                {l.leader_name}
              </option>
            ))}
        </select>
        <label htmlFor="home">Home country</label>
        <select id="home" value={home} onChange={(e) => chooseHome(e.target.value)}>
          <option value="">All countries</option>
          {homes.map((c) => (
            <option key={c.iso3_code} value={c.iso3_code}>
              {flag(c)} {c.country_name}
            </option>
          ))}
        </select>
        <fieldset>
          <legend>Date range</legend>
          <input
            type="date"
            aria-label="From"
            min={SCOPE.from}
            max={SCOPE.to}
            value={range.from}
            onChange={(e) => setRange({ ...range, from: e.target.value || SCOPE.from })}
          />
          <span aria-hidden="true">–</span>
          <input
            type="date"
            aria-label="To"
            min={SCOPE.from}
            max={SCOPE.to}
            value={range.to}
            onChange={(e) => setRange({ ...range, to: e.target.value || SCOPE.to })}
          />
        </fieldset>
        <hr />
        {visits.error && <p role="alert">{visits.error}</p>}
        {leaderId && <h2 className="label">Official visits ({list.length})</h2>}
        <ul className="visits">
          {list.map((v) => (
            <li key={v.visit_key}>
              <button
                aria-pressed={v.visit_key === visitKey}
                aria-label={`${v.host_country.country_name}, ${dateRange(v.start_date_key, v.end_date_key)}`}
                onClick={() => setVisitKey(v.visit_key)}
              >
                <span className="flag" aria-hidden="true">
                  {flag(v.host_country)}
                </span>
                <span>
                  <b>{v.host_country.country_name}</b>
                  <small>{dateRange(v.start_date_key, v.end_date_key)}</small>
                </span>
                <span className="chevron" aria-hidden="true">
                  ›
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <Globe visits={list} home={home || undefined} selected={selected} onPick={pick} />
      {selected ? (
        <VisitDetails key={selected.visit_key} visitKey={selected.visit_key} />
      ) : (
        <section className="card visit empty">
          <p className="muted">
            {leaderId ? "Choose a visit on the globe or in the list." : "Choose a leader to see their visits."}
          </p>
        </section>
      )}
    </div>
  );
}
