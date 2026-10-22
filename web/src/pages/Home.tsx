import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useData } from "../context";
const destinations = [
  [
    "Cases",
    "⚖️",
    "Cases",
    "Search and browse 8,000+ cases by name, term, keyword, or plain-language description.",
  ],
  [
    "People",
    "👥",
    "Justices & Advocates",
    "Voting records, ideology drift over time, agreement matrices, and advocate win rates.",
  ],
  [
    "Predictions",
    "🔮",
    "Predictions",
    "ML-powered outcome predictions, cert grant estimator, model card, and docket watch.",
  ],
  [
    "Analysis",
    "📊",
    "Analytics",
    "Term-by-term statistics, issue-area breakdowns, reversal rates, and voting trends.",
  ],
];
export default function Home() {
  const { manifest } = useData();
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(15);
  const [error, setError] = useState(false);
  const navigate = useNavigate();
  return (
    <>
      <div className="home-heading">
        <img src="/brand.png" alt="Supreme Scrutiny logo" />
        <h1>Supreme Scrutiny</h1>
      </div>
      <hr />
      <form
        className="home-search"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim().length < 10) {
            setError(true);
            return;
          }
          navigate(
            `/Cases?q=${encodeURIComponent(query.trim())}&limit=${limit}`,
          );
        }}
      >
        <h4>🔍 Find Cases by Description</h4>
        <p className="caption">
          Describe a legal situation in plain language and find the most
          relevant Supreme Court cases.
        </p>
        <textarea
          aria-label="Describe a legal situation"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            "e.g. police searched a suspect's cell phone without a warrant\ne.g. government required a license to display a religious symbol\ne.g. employer fired a worker for union organizing activity"
          }
        />
        <div className="home-search-actions">
          <label className="field">
            Results <output>{limit}</output>
            <input
              type="range"
              min={3}
              max={20}
              value={limit}
              onChange={(e) => setLimit(+e.target.value)}
            />
          </label>
          <button className="button primary">🔍 Find Cases</button>
        </div>
        {error ? (
          <p role="alert">Please enter at least 10 characters.</p>
        ) : null}
      </form>
      <hr />
      <h3>Explore the Court</h3>
      <div className="destination-grid">
        {destinations.map(([path, icon, title, description]) => (
          <section className="destination" key={path}>
            <h4>
              {icon} {title}
            </h4>
            <p className="caption">{description}</p>
            <Link className="button" to={`/${path}`}>
              Open {title} →
            </Link>
          </section>
        ))}
      </div>
      <hr />
      <details className="about">
        <summary>ℹ️ About Supreme Scrutiny</summary>
        <p>
          <strong>Supreme Scrutiny</strong> is an open-source data visualization
          and analysis tool for U.S. Supreme Court history.
        </p>
        <p>
          <strong>Data sources and Coverage:</strong>
        </p>
        <ul>
          <li>
            <a href="https://www.oyez.org">Oyez</a> — case metadata, oral
            argument audio, and justice records
          </li>
          <li>
            Terms: {Math.min(...manifest.terms)}–{Math.max(...manifest.terms)}
          </li>
          <li>Cases: {manifest.cases.toLocaleString()}</li>
          <li>Voting data: Included for cases with recorded decisions</li>
        </ul>
      </details>
    </>
  );
}
