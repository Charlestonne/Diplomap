// DiploMap: the Globe view (P4-08) and the Network view (P4-09).
import { useState } from "react";
import { MOCK } from "./api";
import GlobeView from "./GlobeView";
import NetworkView from "./NetworkView";

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
      <main>{tab === "globe" ? <GlobeView /> : <NetworkView />}</main>
    </>
  );
}
