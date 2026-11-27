// The globe of the Globe view (mock-up of pdfs/DiploMap.pdf): an orthographic projection of world-atlas drawn in SVG
// with d3-geo, a marker on each visited country and an arc from the visitor country. Drag to turn it; the buttons zoom
// and recentre. SVG rather than WebGL (globe.gl), so that the view stays testable in jsdom.
import { geoArea, geoCentroid, geoDistance, geoGraticule10, geoInterpolate, geoOrthographic, geoPath } from "d3-geo";
import type { Feature, MultiPolygon, Polygon } from "geojson";
import { numericToAlpha3 } from "i18n-iso-countries";
import { useEffect, useState } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import atlas from "world-atlas/countries-110m.json";
import type { VisitSummary } from "./types";

type Shape = Feature<Polygon | MultiPolygon, { name: string }>;

// Centre of the largest polygon, so that France sits in Europe and not halfway to French Guiana.
function centre(shape: Shape): [number, number] {
  const { geometry } = shape;
  if (geometry.type === "Polygon") return geoCentroid(geometry);
  const polygons = geometry.coordinates.map((coordinates) => ({ type: "Polygon" as const, coordinates }));
  return geoCentroid(polygons.reduce((a, b) => (geoArea(b) > geoArea(a) ? b : a)));
}

// world-atlas identifies countries by ISO 3166 numeric code, the API by ISO alpha-3. Three shapes have no code
// (N. Cyprus, Somaliland, Kosovo), so a visit there is listed but not drawn.
const topology = atlas as unknown as Topology<{ countries: GeometryCollection<{ name: string }> }>;
const COUNTRIES = (feature(topology, topology.objects.countries).features as Shape[]).map((shape) => ({
  shape,
  iso3: shape.id === undefined ? undefined : numericToAlpha3(shape.id),
  centre: centre(shape),
}));
const BY_ISO3 = new Map(COUNTRIES.map((c) => [c.iso3, c]));

const SIZE = 400;
const RADIUS = SIZE / 2 - 14; // room for the atmosphere halo
export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

interface Props {
  visits: VisitSummary[];
  home?: string; // ISO3 of the leader's country
  selected?: VisitSummary;
  onPick: (iso3: string) => void;
}

export default function Globe({ visits, home, selected, onPick }: Props) {
  // Face the middle of the selected visit's arc, so both countries show; else the leader's country.
  const from = BY_ISO3.get(selected?.visitor_country.iso3_code ?? home ?? "");
  const to = BY_ISO3.get(selected?.host_country.iso3_code ?? "");
  const [lon, lat] = from && to ? geoInterpolate(from.centre, to.centre)(0.5) : (from?.centre ?? [10, 30]);
  const [rotation, setRotation] = useState<[number, number]>([-lon, -lat]);
  const [zoom, setZoom] = useState(1);
  const recentre = () => {
    setRotation([-lon, -lat]);
    setZoom(1);
  };
  useEffect(recentre, [lon, lat]);

  const projection = geoOrthographic()
    .scale(RADIUS * zoom)
    .translate([SIZE / 2, SIZE / 2])
    .rotate(rotation);
  const path = geoPath(projection);
  const facing = (c: [number, number]) => geoDistance(c, [-rotation[0], -rotation[1]]) < Math.PI / 2;
  const at = (iso3: string) => {
    const country = BY_ISO3.get(iso3);
    return country && facing(country.centre) ? projection(country.centre) : null;
  };

  const hosts = [...new Map(visits.map((v) => [v.host_country.iso3_code, v.host_country])).values()];
  const origins = new Set([...visits.map((v) => v.visitor_country.iso3_code), ...(home ? [home] : [])]);
  const named = new Map(visits.flatMap((v) => [v.visitor_country, v.host_country]).map((c) => [c.iso3_code, c]));
  const labels = [...origins, selected?.host_country.iso3_code].filter((iso3) => iso3 && named.has(iso3));
  const halo = RADIUS * zoom;
  return (
    <div className="globe-wrap">
      <svg
        className="globe"
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        aria-label="Globe of the visited countries, drag to turn"
        onPointerMove={(e) =>
          e.buttons && setRotation(([l, p]) => [l + e.movementX / 3, Math.max(-90, Math.min(90, p - e.movementY / 3))])
        }
      >
        <defs>
          <radialGradient id="globe-halo" gradientUnits="userSpaceOnUse" cx={SIZE / 2} cy={SIZE / 2} r={halo + 14}>
            <stop offset={halo / (halo + 14)} stopColor="#7fb2ee" stopOpacity="0.55" />
            <stop offset="1" stopColor="#7fb2ee" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="globe-ocean" cx="40%" cy="35%" r="75%">
            <stop offset="0" stopColor="#4f8fcc" />
            <stop offset="0.6" stopColor="#1b4f86" />
            <stop offset="1" stopColor="#0b2a4d" />
          </radialGradient>
          <radialGradient id="globe-shade" cx="35%" cy="30%" r="80%">
            <stop offset="0" stopColor="#fff" stopOpacity="0.22" />
            <stop offset="0.55" stopColor="#fff" stopOpacity="0" />
            <stop offset="1" stopColor="#000" stopOpacity="0.3" />
          </radialGradient>
        </defs>
        <circle cx={SIZE / 2} cy={SIZE / 2} r={halo + 14} fill="url(#globe-halo)" />
        <path d={path({ type: "Sphere" }) ?? ""} fill="url(#globe-ocean)" />
        <path className="graticule" d={path(geoGraticule10()) ?? ""} />
        {COUNTRIES.map(({ shape }, i) => (
          <path key={i} className="land" d={path(shape) ?? ""} />
        ))}
        <path className="shade" d={path({ type: "Sphere" }) ?? ""} fill="url(#globe-shade)" />
        {visits.map((v) => {
          const a = BY_ISO3.get(v.visitor_country.iso3_code);
          const b = BY_ISO3.get(v.host_country.iso3_code);
          const d = a && b && path({ type: "LineString", coordinates: [a.centre, b.centre] });
          return (
            d && (
              <path key={v.visit_key} d={d} className={v.visit_key === selected?.visit_key ? "arc selected" : "arc"} />
            )
          );
        })}
        {[...origins].map((iso3) => {
          const p = at(iso3);
          return p && <circle key={iso3} className="dot origin" cx={p[0]} cy={p[1]} r={7} />;
        })}
        {hosts.map((country) => {
          const p = at(country.iso3_code);
          if (!p) return null; // far side of the globe
          const n = visits.filter((v) => v.host_country.iso3_code === country.iso3_code).length;
          const label = `${country.country_name}, ${plural(n, "visit")}`;
          const isSelected = country.iso3_code === selected?.host_country.iso3_code;
          return (
            <g
              key={country.iso3_code}
              className="marker"
              role="button"
              tabIndex={0}
              aria-label={label}
              aria-pressed={isSelected}
              onClick={() => onPick(country.iso3_code)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onPick(country.iso3_code)}
            >
              <title>{label}</title>
              <circle className="hit" cx={p[0]} cy={p[1]} r={12} />
              <circle className={isSelected ? "dot selected" : "dot"} cx={p[0]} cy={p[1]} r={isSelected ? 7 : 5} />
            </g>
          );
        })}
        {labels.map((iso3) => {
          const p = at(iso3!);
          const name = named.get(iso3!)!.country_name;
          const width = name.length * 6.6 + 14; // ponytail: estimated text width, measure with getBBox if labels clip
          return (
            p && (
              <g key={iso3} className="pill" transform={`translate(${p[0]},${p[1] + 12})`} aria-hidden="true">
                <rect x={-width / 2} width={width} height={18} rx={4} />
                <text y={13} textAnchor="middle">
                  {name}
                </text>
              </g>
            )
          );
        })}
      </svg>
      <div className="globe-legend" aria-hidden="true">
        <span>
          <i className="dot-key selected" /> Selected visit
        </span>
        <span>
          <i className="dot-key" /> Other visits
        </span>
      </div>
      <div className="zoom">
        <button aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(z * 1.5, 6))}>
          +
        </button>
        <button aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(z / 1.5, 1))}>
          −
        </button>
        <button aria-label="Recentre" onClick={recentre}>
          ⌖
        </button>
      </div>
    </div>
  );
}
