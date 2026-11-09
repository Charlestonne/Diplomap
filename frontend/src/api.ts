// Client of the DiploMap API. Without VITE_API_URL it answers with the example responses of src/mocks/,
// so the app runs without a backend: `npm run dev` (mocks) or `VITE_API_URL=http://localhost:8000 npm run dev`.
import leaders from "./mocks/leaders.json";
import network from "./mocks/network.json";
import visitDetails from "./mocks/visit_details.json";
import visits from "./mocks/visits.json";
import type { Leader, Network, Visit, VisitDetail } from "./types";

async function get<T>(path: string, mock: () => T): Promise<T> {
  const base = import.meta.env.VITE_API_URL;
  if (!base) return mock();
  const response = await fetch(`${base}${path}`);
  if (!response.ok) throw new Error(`GET ${path}: ${response.status}`);
  return (await response.json()) as T;
}

export const api = {
  leaders: () => get("/leaders", () => leaders as Leader[]),

  visits: (leaderId: string) =>
    get(`/leaders/${encodeURIComponent(leaderId)}/visits`, () =>
      (visits as Visit[]).filter((visit) => visit.leader_id === leaderId),
    ),

  visit: (visitKey: number) =>
    get(`/visits/${visitKey}`, () => {
      const detail = (visitDetails as unknown as Record<string, VisitDetail>)[visitKey];
      if (!detail) throw new Error(`GET /visits/${visitKey}: 404`);
      return detail;
    }),

  network: () => get("/network", () => network as Network),
};
