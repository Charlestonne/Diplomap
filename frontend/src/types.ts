// Shapes of the API responses, proposed to P1 for P1-12; src/mocks/*.json are example responses.
// They follow table_contracts/v_kpi_visit.yml, v_visit_event.yml and warehouse/diplomatic_graph/queries.cypher,
// with country codes (ISO3) instead of warehouse keys. Dates are ISO strings (YYYY-MM-DD).

export interface Leader {
  leader_id: string; // Wikidata QID
  leader_name: string;
  position_title: string | null;
  country_iso3: string;
  country_name: string;
}

export interface Visit {
  visit_key: number;
  leader_id: string;
  leader_name: string;
  visitor_iso3: string;
  host_iso3: string;
  host_name: string;
  start_date: string;
  end_date: string;
  duration_days: number;
  visit_type: string;
  is_multilateral: boolean;
  matched_in_gdelt: boolean;
}

// v_kpi_visit without visit_key. Means are null when their window has no event.
export interface VisitKpi {
  n_events_pre: number;
  n_events_post: number;
  coop_share_pre: number | null;
  coop_share_post: number | null;
  delta_coop_share: number | null;
  tone_pre: number | null;
  tone_post: number | null;
  delta_tone: number | null;
  goldstein_pre: number | null;
  goldstein_post: number | null;
  delta_goldstein: number | null;
  is_low_volume: boolean;
  has_overlap: boolean;
}

export interface VisitEvent {
  gdelt_event_id: number;
  visit_window: "PRE" | "POST";
  day_offset: number; // -15..-1 before the start, +1..+15 after the end
  event_date: string;
  actor1_iso3: string;
  actor2_iso3: string;
  cameo_code: string;
  is_cooperative: boolean;
  goldstein_scale: number;
  avg_tone: number;
  num_mentions: number;
  source_url: string | null;
}

export interface VisitDetail {
  visit: Visit;
  kpi: VisitKpi;
  events: VisitEvent[];
}

export interface NetworkEdge {
  leader_id: string;
  leader_name: string;
  relation: "VISITED" | "REPRESENTS";
  iso3: string;
  country_name: string;
  n_visits: number | null; // null on REPRESENTS
  days_on_site: number | null;
  first_visit: string | null;
  last_visit: string | null;
}

export interface SharedDestination {
  leader_a_id: string;
  leader_a: string;
  leader_b_id: string;
  leader_b: string;
  n_shared: number;
  shared_countries: string[];
}

export interface ReciprocalVisit {
  country_a: string;
  country_b: string;
  leaders_a_to_b: string[];
  leaders_b_to_a: string[];
  first_a_to_b: string;
  first_b_to_a: string;
}

export interface Network {
  edges: NetworkEdge[];
  shared_destinations: SharedDestination[];
  reciprocal_visits: ReciprocalVisit[];
}
