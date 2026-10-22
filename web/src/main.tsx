import {
  Component,
  lazy,
  Suspense,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { DataProvider, useData } from "./context";
import { loadInitial } from "./lib/data";
import { Notice } from "./components/UI";
import "./styles.css";
const Home = lazy(() => import("./pages/Home"));
const Cases = lazy(() => import("./pages/Cases"));
const CaseDetail = lazy(() => import("./pages/CaseDetail"));
const People = lazy(() => import("./pages/People"));
const History = lazy(() => import("./pages/History"));
const HistoricalData = lazy(() =>
  import("./pages/History").then((m) => ({ default: m.HistoricalData })),
);
const Analysis = lazy(() => import("./pages/Analysis"));
const CircuitCourts = lazy(() =>
  import("./pages/Analysis").then((m) => ({ default: m.CircuitCourts })),
);
const Geography = lazy(() => import("./pages/Geography"));
const Topics = lazy(() => import("./pages/Topics"));
const Legacy = lazy(() => import("./pages/Legacy"));
const Research = lazy(() => import("./pages/Research"));
const Predictions = lazy(() => import("./pages/Predictions"));
const links = [
  ["/", "Home", "🏠", ""],
  ["/Cases", "Cases", "⚖️", "Cases"],
  ["/People", "Justices & Advocates", "👥", "People"],
  ["/History", "Court History", "🏛️", "History & Courts"],
  ["/Historical_Data", "Full Timeline", "📜", ""],
  ["/Circuit_Courts", "Circuit Courts", "🗺️", ""],
  ["/Geography", "Geography", "🌎", ""],
  ["/Analysis", "Analytics", "📊", "Analysis"],
  ["/Topics", "Topics & Networks", "📚", ""],
  ["/Presidential_Legacy", "Presidential Legacy", "🏅", ""],
  ["/Research", "Research", "🔬", ""],
  ["/Predictions", "Predictions", "🔮", "Predictions"],
];
class Boundary extends Component<{ children: ReactNode }, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  render() {
    return this.state.error ? (
      <div className="fatal">
        <h1>We couldn’t display this page.</h1>
        <p>Your saved cases are still in this browser.</p>
        <button className="button" onClick={() => location.reload()}>
          Reload the archive
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
function Shell() {
  const { manifest, watchlist } = useData();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => {
    setOpen(false);
    window.scrollTo(0, 0);
    const title =
      links.find(([path]) => path === location.pathname)?.[1] || "Case record";
    document.title = `${title} · Supreme Scrutiny`;
  }, [location.pathname]);
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <button
        className="mobile-menu"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="sidebar"
      >
        ☰ <span>Supreme Scrutiny</span>
      </button>
      {open ? (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      ) : null}
      <aside className={`sidebar ${open ? "open" : ""}`} id="sidebar">
        <nav aria-label="Main navigation">
          {links.map(([path, label, icon, group]) => (
            <div key={path}>
              {group ? <div className="nav-group">{group}</div> : null}
              <NavLink to={path} end={path === "/"}>
                <span aria-hidden="true">{icon}</span>
                {label}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {location.pathname !== "/" ? (
            <img src="/brand.png" alt="Supreme Scrutiny" />
          ) : null}
          <small>🗄️ Data: {manifest.cases.toLocaleString()} cases</small>
          {watchlist.length ? (
            <Link to="/Cases">⭐ {watchlist.length} saved cases</Link>
          ) : null}
        </div>
      </aside>
      <div className="workspace">
        <main id="main">
          <Boundary key={location.pathname}>
            <Suspense
              fallback={<Notice>Loading this part of the archive…</Notice>}
            >
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/Cases" element={<Cases />} />
                <Route path="/case/*" element={<CaseDetail />} />
                <Route path="/People" element={<People />} />
                <Route path="/History" element={<History />} />
                <Route path="/Historical_Data" element={<HistoricalData />} />
                <Route path="/Circuit_Courts" element={<CircuitCourts />} />
                <Route path="/Geography" element={<Geography />} />
                <Route path="/Analysis" element={<Analysis />} />
                <Route path="/Topics" element={<Topics />} />
                <Route path="/Presidential_Legacy" element={<Legacy />} />
                <Route path="/Research" element={<Research />} />
                <Route path="/Predictions" element={<Predictions />} />
                <Route
                  path="*"
                  element={
                    <section>
                      <h1>Page not found</h1>
                      <p>This address is not in the archive.</p>
                      <Link to="/">Return to the overview →</Link>
                    </section>
                  }
                />
              </Routes>
            </Suspense>
          </Boundary>
        </main>
      </div>
    </>
  );
}
function Bootstrap() {
  const [data, setData] = useState<Awaited<
    ReturnType<typeof loadInitial>
  > | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    loadInitial()
      .then((v) => {
        if (active) setData(v);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  if (error)
    return (
      <div className="fatal">
        <h1>The archive couldn’t load.</h1>
        <Notice error>{error}</Notice>
        <button className="button" onClick={() => location.reload()}>
          Try again
        </button>
      </div>
    );
  if (!data)
    return (
      <div className="initial-loading" role="status">
        <span className="loading-mark">⚖</span>
        <h1>Supreme Scrutiny</h1>
        <p>Opening the archive…</p>
      </div>
    );
  return (
    <DataProvider data={data}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </DataProvider>
  );
}
createRoot(document.getElementById("root")!).render(
  <Boundary>
    <Bootstrap />
  </Boundary>,
);
