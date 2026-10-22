import { Link } from "react-router-dom";
import { useData } from "../context";
import { monthDay } from "../lib/data";
import { SearchBox } from "../components/SearchBox";
import { CaseList, Metrics, Panel } from "../components/UI";
const destinations = [
  [
    "Cases",
    "Case library",
    "Read the facts, trace the arguments, and examine the decisions.",
    "01",
  ],
  [
    "People",
    "The people of the Court",
    "Explore justice voting records, careers, and advocates.",
    "02",
  ],
  [
    "Analysis",
    "Patterns in the decisions",
    "Compare terms, close decisions, and outcomes.",
    "03",
  ],
  [
    "History",
    "Two centuries of history",
    "Follow the changing bench and Chief Justice eras.",
    "04",
  ],
  [
    "Topics",
    "Constitutional questions",
    "Trace amendments, doctrines, and landmark cases.",
    "05",
  ],
  [
    "Predictions",
    "Explore the possibilities",
    "Experiment with the statistical outcome calculator.",
    "06",
  ],
];
export default function Home() {
  const { cases, manifest, watchlist } = useData();
  const today = monthDay();
  const anniversary = cases
    .filter((c) => c.decided.slice(5) === today)
    .sort((a, b) => b.term - a.term)[0];
  return (
    <>
      <section className="hero">
        <div className="eyebrow">An independent lens on the highest court</div>
        <h1>
          Understand the cases.
          <br />
          <em>See the bigger picture.</em>
        </h1>
        <p>
          Explore Supreme Court history through its decisions, its people, and
          the patterns that connect them.
        </p>
        <SearchBox />
        <div className="example-links">
          Explore: <Link to="/Cases?q=free%20speech">Free speech</Link>
          <Link to="/Cases?q=equal%20protection">Equal protection</Link>
          <Link to="/Cases?q=search%20and%20seizure">Search & seizure</Link>
        </div>
      </section>
      <Metrics
        items={[
          {
            label: "Cases in the archive",
            value: manifest.cases.toLocaleString(),
          },
          {
            label: "Terms covered",
            value: `${Math.min(...manifest.terms)}–${Math.max(...manifest.terms)}`,
          },
          {
            label: "Argument sessions",
            value: manifest.arguments.toLocaleString(),
          },
          { label: "Latest recorded decision", value: manifest.latestDecision },
        ]}
      />
      {anniversary ? (
        <Panel title="On this day in Court history">
          <CaseList rows={[anniversary]} />
        </Panel>
      ) : null}
      <div className="section-heading">
        <div className="eyebrow">Follow your curiosity</div>
        <h2>Explore the Court</h2>
      </div>
      <div className="destination-grid">
        {destinations.map(([path, title, description, n]) => (
          <Link to={`/${path}`} className="destination" key={path}>
            <span className="destination-number">{n}</span>
            <h3>{title}</h3>
            <p>{description}</p>
            <span className="destination-arrow">Explore →</span>
          </Link>
        ))}
      </div>
      {watchlist.length ? (
        <Panel title="Your saved cases">
          <CaseList rows={cases.filter((c) => watchlist.includes(c.id))} />
        </Panel>
      ) : null}
      <Panel title="About this archive">
        <p>
          Case records and oral-argument transcripts come from Oyez. Issue areas
          and party types are inferred categories; historical and ideological
          annotations are curated context. Coverage varies by term. A snapshot
          is a research starting point—verify current law and case status with
          authoritative sources.
        </p>
        <p className="muted">
          Data release {manifest.version} · Court records are served from
          versioned files. Saved cases stay in this browser.
        </p>
        <a href="https://www.oyez.org" target="_blank" rel="noreferrer">
          Visit Oyez ↗
        </a>
      </Panel>
    </>
  );
}
