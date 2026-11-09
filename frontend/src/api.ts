// Client of the DiploMap API (contract P1-12). Without VITE_API_URL it answers with the example responses of
// src/mocks/, so the app runs without a backend: `npm run dev` (mocks) or
// `VITE_API_URL=http://localhost:8000 npm run dev` (real API).
import leaders from "./mocks/leaders.json";
import network from "./mocks/network.json";
import visit from "./mocks/visit.json";
import visitEvents from "./mocks/visit_events.json";
import visitKpis from "./mocks/visit_kpis.json";
import visits from "./mocks/visits.json";
import type { Leader, Network, VisitDetail, VisitEvent, VisitKpis, VisitSummary } from "./types";

async function get<T>(path: string, mock: () => T): Promise<T> {
  const base = import.meta.env.VITE_API_URL;
  if (!base) return mock();
  const response = await fetch(`${base}${path}`);
  if (!response.ok) throw new Error(`GET ${path}: ${response.status}`);
  return (await response.json()) as T;
}

// Per-visit mocks are keyed by visit_key; an unknown key answers 404 like the API.
function byVisit<T>(mocks: unknown, path: string, visitKey: number): T {
  const found = (mocks as Record<string, T>)[visitKey];
  if (found === undefined) throw new Error(`GET ${path}: 404`);
  return found;
}

export const api = {
  leaders: () => get("/leaders", () => leaders as Leader[]),

  visits: (leaderId?: string) =>
    get(leaderId ? `/visits?${new URLSearchParams({ leader_id: leaderId })}` : "/visits", () =>
      (visits as VisitSummary[]).filter((v) => !leaderId || v.leader_id === leaderId),
    ),

  visit: (visitKey: number) =>
    get(`/visits/${visitKey}`, () => byVisit<VisitDetail>(visit, `/visits/${visitKey}`, visitKey)),

  visitKpis: (visitKey: number) =>
    get(`/visits/${visitKey}/kpis`, () => byVisit<VisitKpis>(visitKpis, `/visits/${visitKey}/kpis`, visitKey)),

  visitEvents: (visitKey: number) =>
    get(`/visits/${visitKey}/events`, () =>
      byVisit<VisitEvent[]>(visitEvents, `/visits/${visitKey}/events`, visitKey),
    ),

  network: () => get("/network", () => network as Network),
};
