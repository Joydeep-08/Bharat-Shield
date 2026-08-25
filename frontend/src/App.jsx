import { useEffect, useMemo, useState, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Clock3,
  List,
  Map as MapIcon,
  MapPin,
  Search,
  ShieldCheck,
  Thermometer,
  Wind,
  Droplets,
  Sun,
  X,
  Radio,
} from "lucide-react";

import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Tooltip,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";
import "./App.css";

const RISK = {
  EXTREME: { color: "#b91c1c", tint: "#fdecec", border: "#f3b7b7" },
  HIGH: { color: "#c2560c", tint: "#fdf0e6", border: "#f1c497" },
  MODERATE: { color: "#92700a", tint: "#fbf5df", border: "#e6d38c" },
  LOW: { color: "#157a45", tint: "#eaf6ee", border: "#b9ddc4" },
};

const ACTION_PLAN = {
  EXTREME: [
    "Issue public alert: avoid outdoor exposure between 12:00–16:00.",
    "Open cooling shelters and public hydration points in affected wards.",
    "Suspend outdoor labour and school assembly during peak hours.",
    "Activate ambulance and heat-stroke triage readiness at nearby hospitals.",
  ],
  HIGH: [
    "Advise residents to limit strenuous outdoor activity at midday.",
    "Ensure construction and outdoor workers get hydration and rest breaks.",
    "Keep vulnerable groups — elderly, children, outdoor workers — under watch.",
    "Pre-position cooling shelters on standby in case conditions worsen.",
  ],
  MODERATE: [
    "Encourage hydration and light clothing during afternoon hours.",
    "Monitor vulnerable populations; no shelter activation required yet.",
    "Keep public heat-safety advisories visible in high-footfall areas.",
  ],
  LOW: [
    "No special action required — maintain routine monitoring.",
    "Continue standard public awareness on heat-safe practices.",
  ],
};

function formatRisk(level) {
  return RISK[level] || RISK.LOW;
}

function App() {
  const [cities, setCities] = useState([]);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [view, setView] = useState("map"); // "map" | "list"
  const searchRef = useRef(null);

  useEffect(() => {
    fetch("https://bharat-shield.onrender.com/cities")
      .then((res) => {
        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => setCities(data))
      .catch((err) =>
        console.error("Failed to load live city data:", err)
      );
  }, []);

  // Close search dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setIsSearchFocused(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const stats = useMemo(() => {
    return {
      total: cities.length,
      extreme: cities.filter((c) => c.current.risk_level === "EXTREME").length,
      high: cities.filter((c) => c.current.risk_level === "HIGH").length,
      moderate: cities.filter((c) => c.current.risk_level === "MODERATE").length,
      low: cities.filter((c) => c.current.risk_level === "LOW").length,
    };
  }, [cities]);

  // Cities currently at EXTREME or HIGH risk, worst first
  const alertCities = useMemo(() => {
    return cities
      .filter((c) => c.current.risk_level === "EXTREME" || c.current.risk_level === "HIGH")
      .sort((a, b) => b.current.risk_score - a.current.risk_score);
  }, [cities]);

  // Highest risk city
  const nationalPeak = useMemo(() => {
    if (cities.length === 0) return null;
    return cities.reduce((worst, c) =>
      c.current.risk_score > worst.current.risk_score ? c : worst
    );
  }, [cities]);

  const filteredCities = useMemo(() => {
    return cities.filter((city) =>
      `${city.name} ${city.state}`.toLowerCase().includes(search.toLowerCase())
    );
  }, [cities, search]);

  const handleSelectCity = (city) => {
    setSelected(city);
    setSearch(city.name);
    setIsSearchFocused(false);
  };

  return (
    <div className="app">

      {/* ================= HEADER ================= */}
      <header className="header">
        <div className="brand">
          <div className="brand-mark">
            <ShieldCheck size={19} />
          </div>
          <div>
            <h1>BHARAT-SHIELD</h1>
            <p>National Thermal Risk Early Warning System</p>
          </div>
        </div>

        <div className="live">
          <span className="live-dot"></span>
          LIVE · {stats.total} CITIES MONITORED
        </div>
      </header>

      {/* ================= NEWS BULLETIN / TICKER ================= */}
      {alertCities.length > 0 && (
        <div className="ticker-strip" role="region" aria-label="National Heat-Risk Ticker">
          <div className="ticker-badge">
            <Radio size={13} className="ticker-live-icon" />
            <span>NATIONAL BULLETIN</span>
          </div>

          <div className="ticker-viewport">
            <div className="ticker-track">
              {/* Double-render for infinite continuous scroll loop */}
              {[...alertCities, ...alertCities].map((c, idx) => {
                const risk = formatRisk(c.current.risk_level);
                return (
                  <button
                    key={`${c.name}-${idx}`}
                    className="ticker-item"
                    onClick={() => setSelected(c)}
                    type="button"
                  >
                    <span className="ticker-dot" style={{ background: risk.color }}></span>
                    <span className="ticker-city">{c.name}</span>
                    <span className="ticker-state">({c.state})</span>
                    <span
                      className="ticker-level-tag"
                      style={{
                        color: risk.color,
                        background: risk.tint,
                        borderColor: risk.border,
                      }}
                    >
                      {c.current.risk_level} {c.current.risk_score}
                    </span>
                    <span className="ticker-temp">{c.current.temperature_c}°C</span>
                    <span className="ticker-divider">•</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ================= STATS ================= */}
      <section className="stats">
        <Stat
          label="Cities Monitored"
          value={stats.total}
          icon={<Activity size={15} />}
        />
        <Stat
          label="Extreme Risk"
          value={stats.extreme}
          total={stats.total}
          color="#b91c1c"
        />
        <Stat
          label="High Risk"
          value={stats.high}
          total={stats.total}
          color="#c2560c"
        />
        <Stat
          label="Moderate"
          value={stats.moderate}
          total={stats.total}
          color="#92700a"
        />
        <Stat
          label="Low Risk"
          value={stats.low}
          total={stats.total}
          color="#157a45"
        />
      </section>

      {/* ================= MAIN ================= */}
      <main className="main">

        {/* ================= MAP / LIST SECTION ================= */}
        <section className="map-section">

          <div className="section-heading">
            <div>
              <p className="eyebrow">National Monitor</p>
              <h2>India Thermal Risk</h2>
              {nationalPeak && (
                <p className="national-peak">
                  Highest current risk: <b>{nationalPeak.name}</b>,{" "}
                  {nationalPeak.state} —{" "}
                  <span className="mono">
                    {nationalPeak.current.risk_score} ({nationalPeak.current.risk_level})
                  </span>
                </p>
              )}
            </div>

            <div className="heading-controls">
              {/* Autocomplete Search Box */}
              <div className="search-container" ref={searchRef}>
                <div className="search-box">
                  <Search size={16} />
                  <input
                    placeholder="Search city or state..."
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setIsSearchFocused(true);
                    }}
                    onFocus={() => setIsSearchFocused(true)}
                    aria-label="Search city or state"
                  />
                  {search && (
                    <button
                      className="search-clear"
                      onClick={() => {
                        setSearch("");
                        setIsSearchFocused(false);
                      }}
                      aria-label="Clear search"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>

                {isSearchFocused && search.trim().length > 0 && (
                  <div className="search-dropdown">
                    {filteredCities.length === 0 ? (
                      <div className="dropdown-empty">No matching cities found</div>
                    ) : (
                      filteredCities.slice(0, 7).map((city) => {
                        const risk = formatRisk(city.current.risk_level);
                        return (
                          <div
                            key={city.name}
                            className="dropdown-item"
                            onClick={() => handleSelectCity(city)}
                          >
                            <div className="dropdown-info">
                              <strong>{city.name}</strong>
                              <span>{city.state}</span>
                            </div>
                            <div className="dropdown-meta">
                              <span
                                className="dropdown-badge mono"
                                style={{
                                  color: risk.color,
                                  background: risk.tint,
                                  borderColor: risk.border,
                                }}
                              >
                                {city.current.risk_level} {city.current.risk_score}
                              </span>
                              <span className="dropdown-temp mono">
                                {city.current.temperature_c}°C
                              </span>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>

              <div className="view-toggle" role="group" aria-label="Switch view">
                <button
                  className={view === "map" ? "active" : ""}
                  onClick={() => setView("map")}
                >
                  <MapIcon size={13} /> Map
                </button>
                <button
                  className={view === "list" ? "active" : ""}
                  onClick={() => setView("list")}
                >
                  <List size={13} /> List
                </button>
              </div>
            </div>
          </div>

          {view === "map" ? (
            <div className="map-wrapper">
              <MapContainer
                center={[22.5, 79]}
                zoom={5}
                minZoom={4}
                maxZoom={10}
                scrollWheelZoom={true}
                className="india-map"
              >
                <TileLayer
                  attribution="&copy; OpenStreetMap contributors"
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {filteredCities.map((city) => {
                  const risk = formatRisk(city.current.risk_level);
                  const radius =
                    city.current.risk_level === "EXTREME"
                      ? 9
                      : city.current.risk_level === "HIGH"
                      ? 7.5
                      : city.current.risk_level === "MODERATE"
                      ? 6.5
                      : 5.5;

                  return (
                    <CircleMarker
                      key={city.name}
                      center={[city.latitude, city.longitude]}
                      radius={radius}
                      pathOptions={{
                        color: "#ffffff",
                        fillColor: risk.color,
                        fillOpacity: 0.9,
                        weight: 1.5,
                      }}
                      eventHandlers={{ click: () => setSelected(city) }}
                    >
                      <Tooltip direction="top" offset={[0, -6]}>
                        <div className="map-tooltip">
                          <strong>{city.name}</strong>
                          <span>{city.state}</span>
                          <b style={{ color: risk.color }}>
                            {city.current.risk_score} • {city.current.risk_level}
                          </b>
                          <small>HI {city.current.heat_index_c}°C</small>
                        </div>
                      </Tooltip>
                    </CircleMarker>
                  );
                })}
              </MapContainer>

              <div className="map-overlay">
                <div>
                  <span className="map-live-dot"></span>
                  LIVE THERMAL CONDITIONS
                </div>
                <p>{filteredCities.length} monitored cities</p>
              </div>

              <div className="map-legend">
                <div><span style={{ background: "#b91c1c" }} />Extreme</div>
                <div><span style={{ background: "#c2560c" }} />High</div>
                <div><span style={{ background: "#92700a" }} />Moderate</div>
                <div><span style={{ background: "#157a45" }} />Low</div>
              </div>
            </div>
          ) : (
            <div className="city-grid">
              {filteredCities.length === 0 ? (
                <p className="city-grid-empty">No cities match "{search}".</p>
              ) : (
                filteredCities
                  .slice()
                  .sort((a, b) => b.current.risk_score - a.current.risk_score)
                  .map((city) => {
                    const risk = formatRisk(city.current.risk_level);
                    return (
                      <button
                        key={city.name}
                        className={
                          "city-card" +
                          (selected?.name === city.name ? " is-selected" : "")
                        }
                        onClick={() => setSelected(city)}
                      >
                        <div className="city-top">
                          <span className="city-name">{city.name}</span>
                          <span
                            className="risk-dot"
                            style={{ background: risk.color }}
                          />
                        </div>
                        <div
                          className="city-risk mono"
                          style={{ color: risk.color }}
                        >
                          {city.current.risk_score}
                        </div>
                        <div className="city-level" style={{ color: risk.color }}>
                          {city.current.risk_level}
                        </div>
                        <div className="city-temp">
                          <span>Temp</span>
                          {city.current.temperature_c}°C
                        </div>
                      </button>
                    );
                  })
              )}
            </div>
          )}
        </section>

        {/* ================= RIGHT PANEL ================= */}
        <aside className="side-panel">
          {!selected ? (
            <EmptyPanel />
          ) : (
            <CityPanel city={selected} onClose={() => setSelected(null)} />
          )}
        </aside>
      </main>

      {/* ================= FOOTER ================= */}
      <footer>
        <div><span className="legend extreme"></span>Extreme</div>
        <div><span className="legend high"></span>High</div>
        <div><span className="legend moderate"></span>Moderate</div>
        <div><span className="legend low"></span>Low</div>
        <span className="footer-text">Bharat-Shield • Prototype</span>
      </footer>
    </div>
  );
}

/* =====================================================
   STAT COMPONENT
===================================================== */
function Stat({ label, value, color, icon, total }) {
  const pct = total ? Math.round((value / total) * 100) : null;

  return (
    <div className="stat" style={{ borderLeftColor: color || "transparent" }}>
      <div className="stat-top">
        {icon}
        <span className="stat-label">{label}</span>
      </div>

      <div className="stat-value mono">{value}</div>

      {pct !== null && (
        <div className="stat-bar">
          <span style={{ width: `${pct}%`, background: color }} />
        </div>
      )}
    </div>
  );
}

/* =====================================================
   EMPTY PANEL
===================================================== */
function EmptyPanel() {
  return (
    <div className="empty-panel">
      <div className="empty-icon">
        <MapPin size={22} />
      </div>
      <h3>Select a city</h3>
      <p>
        Choose any monitored city from the map, list, or news bulletin to inspect its
        current conditions, forecast, and recommended response.
      </p>
    </div>
  );
}

/* =====================================================
   CITY INTELLIGENCE PANEL
===================================================== */
function CityPanel({ city, onClose }) {
  const current = city.current;
  const peak = city.peak;
  const risk = formatRisk(current.risk_level);
  const peakRisk = formatRisk(peak.risk_level);
  const actions = ACTION_PLAN[current.risk_level] || ACTION_PLAN.LOW;

  return (
    <div className="city-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">City Intelligence</p>
          <h2>{city.name}</h2>
          <p className="state">{city.state}</p>
        </div>

        <button className="close" onClick={onClose} aria-label="Close city panel">
          <X size={18} />
        </button>
      </div>

      <div className="risk-hero" style={{ borderColor: risk.border, background: risk.tint }}>
        <div>
          <div className="risk-number mono">{current.risk_score}</div>
          <div className="risk-label" style={{ color: risk.color }}>
            {current.risk_level} RISK
          </div>
        </div>
        <AlertTriangle size={28} color={risk.color} />
      </div>

      <div className="metrics">
        <Metric icon={<Thermometer size={16} />} label="Temperature" value={`${current.temperature_c}°C`} />
        <Metric icon={<Droplets size={16} />} label="Humidity" value={`${current.humidity_percent}%`} />
        <Metric icon={<Wind size={16} />} label="Wind" value={`${current.wind_kmh} km/h`} />
        <Metric icon={<Sun size={16} />} label="Solar" value={`${current.solar_wm2} W/m²`} />
      </div>

      <div className="info-card">
        <div>
          <span>Heat Index</span>
          <strong className="mono">{current.heat_index_c}°C</strong>
        </div>
        <ArrowUpRight size={17} color="var(--text-dim)" />
      </div>

      <div className="peak-card">
        <div className="peak-title">
          <Clock3 size={15} />
          72-Hour Peak
        </div>

        <div className="peak-risk">{peak.risk_score}</div>

        <div className="peak-level" style={{ color: peakRisk.color }}>
          {peak.risk_level}
        </div>

        <p>
          {new Date(peak.time).toLocaleString("en-IN", {
            weekday: "short",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>

        <div className="peak-hi">
          Peak Heat Index: <strong>{peak.heat_index_c}°C</strong>
        </div>
      </div>

      <div className="action-plan">
        <div className="action-plan-head" style={{ color: risk.color }}>
          <ShieldCheck size={13} />
          Recommended Actions
        </div>
        <ul>
          {actions.map((action, i) => (
            <li key={i}>{action}</li>
          ))}
        </ul>
      </div>

      <div className="explanation">
        <p className="eyebrow">Initial Analysis</p>
        <p>
          Thermal risk is being evaluated using apparent temperature and
          current environmental conditions.
        </p>
      </div>
    </div>
  );
}

function Metric({ icon, label, value }) {
  return (
    <div className="metric">
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong className="mono">{value}</strong>
      </div>
    </div>
  );
}

export default App;