// Shapes of the API responses: a copy of the P1-12 contract (backend/schemas.py, backend/openapi.json).
// Change them only when that contract changes. Dates are ISO strings (YYYY-MM-DD); countries are nested objects.

export interface Country {
  iso3_code: string;
  country_name: string;
}

// GET /leaders

export interface Office {
  position_title: string | null;
  represented_country: Country;
  valid_from: string;
  valid_to: string | null; // null while the office is held
}

export interface Leader {
  leader_id: string; // Wikidata QID
  leader_name: string;
  offices: Office[]; // oldest first
}

// GET /visits?leader_id=  and  GET /visits/{visit_key}

export type VisitTypeLabel = "state" | "working" | "summit" | "ceremony" | "unknown";

export interface VisitSummary {
  visit_key: number;
  leader_id: string;
  leader_name: string;
  visitor_country: Country;
  host_country: Country;
  visit_type_label: VisitTypeLabel;
  start_date_key: string;
  end_date_key: string;
  duration_days: number;
  is_multilateral: boolean;
  matched_in_gdelt: boolean;
}

export interface VisitDetail extends VisitSummary {
  position_title: string | null;
  pre_window_start: string;
  pre_window_end: string;
  post_window_start: string;
  post_window_end: string;
  wiki_page_id: number;
  wiki_revision_id: number;
}

// GET /visits/{visit_key}/kpis  (v_kpi_visit). Means and deltas are null when their window has no event.

export interface VisitKpis {
  visit_key: number;
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

// GET /visits/{visit_key}/events  (v_visit_event)

export interface VisitEvent {
  visit_key: number;
  gdelt_event_id: number;
  visit_window: "PRE" | "POST";
  day_offset: number; // -15..-1 before the start, +1..+15 after the end
  event_date_key: string;
  actor1_country: Country;
  actor2_country: Country;
  cameo_code: string;
  is_cooperative: boolean;
  goldstein_scale: number;
  avg_tone: number;
  num_mentions: number;
  source_url: string | null;
}

// GET /network  (Neo4j projection)

export interface NetworkNode {
  id: string; // QID of a leader or ISO3 code of a country
  type: "leader" | "country";
  label: string;
  iso3_code: string | null; // null for leaders
}

export interface NetworkEdge {
  source: string; // leader id
  target: string; // country id
  type: "VISITED" | "REPRESENTS";
  n_visits: number | null; // null for REPRESENTS
  first_visit: string | null;
}

export interface SharedDestination {
  leader_a_id: string;
  leader_b_id: string;
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
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  shared_destinations: SharedDestination[];
  reciprocal_visits: ReciprocalVisit[];
}
