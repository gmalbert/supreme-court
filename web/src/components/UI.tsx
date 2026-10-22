import { useId, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { CaseRecord } from "../types";
import { caseURL, downloadCSV, percent, rate } from "../lib/data";
import { useData } from "../context";
export function PageTitle({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-title">
      <h1>{title}</h1>
    </header>
  );
}
export function Panel({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title ? <h2>{title}</h2> : null}
      {children}
    </section>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      className={`notice ${error ? "error" : ""}`}
      role={error ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
export function Metrics({
  items,
}: {
  items: { label: string; value: ReactNode; note?: string }[];
}) {
  return (
    <div className="metrics">
      {items.map((i) => (
        <div className="metric" key={i.label}>
          <span>{i.label}</span>
          <strong>{i.value}</strong>
          {i.note ? <small>{i.note}</small> : null}
        </div>
      ))}
    </div>
  );
}
export function CaseMetrics({ rows }: { rows: CaseRecord[] }) {
  return (
    <Metrics
      items={[
        { label: "Cases", value: rows.length.toLocaleString() },
        {
          label: "Reversal rate",
          value: percent(rate(rows)),
          note: "Reversed/vacated ÷ known outcomes",
        },
        {
          label: "Close decisions",
          value: rows.filter((c) => c.split === "5-4").length,
        },
        { label: "Terms", value: new Set(rows.map((c) => c.term)).size },
      ]}
    />
  );
}
const tabLabels: Record<string, string> = {
  "Find by description": "💬 Find by Description",
  "Search cases": "🔍 Search Cases",
  "Timeline browser": "📅 Timeline Browser",
  "Oral arguments": "🎙️ Oral Arguments",
  "Term calendar": "🗓️ Term Calendar",
  "Case outcome": "🎯 Case Outcome Predictor",
  "Model performance": "📈 Model Performance",
  "Model training": "⚙️ Model Training",
  "Cert grant": "📋 Cert Grant Predictor",
  "Docket watch": "🔴 Docket Watch",
  "Justice simulator": "🔄 Justice Simulator",
  "Model card": "📄 Model Card",
  "Voting patterns": "Voting Patterns",
  "Justice careers": "Justice Career",
  "Agreement matrix": "Agreement Matrix",
  "Ideological drift": "Ideological Drift",
  Advocates: "🏆 Win Rates",
  "Amicus briefs": "📋 Amicus Brief Tracker",
  "Oral argument analytics": "🎙️ Oral Argument Analytics",
  "Term statistics": "📊 Term Statistics",
  "Close decisions": "⚖️ Close Decisions",
  "Win rates": "🏆 Win Rates",
  "SCOTUS vs. Congress": "🏛️ SCOTUS vs. Congress",
  "Chief Justice eras": "Chief Justice Eras",
  Confirmations: "Confirmation Timeline",
  "Service timeline": "Service Timeline",
  "Court snapshot": "Court Snapshot",
  "Ideological balance": "Ideological Balance",
  "Issue areas": "Issue Areas",
  Amendments: "Amendments",
  "Constitutional provisions": "Constitutional Provisions",
  "Landmark cases": "Landmark Cases",
  "Citation network": "Citation Network",
  "Precedent network": "Precedent Network",
};
export function Tabs({
  items,
  children,
}: {
  items: string[];
  children: (selected: string) => ReactNode;
}) {
  const [params, setParams] = useSearchParams();
  const id = useId();
  const groups: { name: string; items: string[] }[] = items.includes(
    "Justice careers",
  )
    ? [
        {
          name: "👨‍⚖️ Justices",
          items: [
            "Voting patterns",
            "Justice careers",
            "Agreement matrix",
            "Ideological drift",
          ],
        },
        {
          name: "⚖️ Advocates & Arguments",
          items: ["Advocates", "Amicus briefs", "Oral argument analytics"],
        },
      ]
    : items.includes("Service timeline")
      ? [
          {
            name: "Court Composition",
            items: [
              "Service timeline",
              "Court snapshot",
              "Ideological balance",
            ],
          },
          { name: "Chief Justice Eras", items: ["Chief Justice eras"] },
          { name: "Confirmation Timeline", items: ["Confirmations"] },
        ]
      : items.includes("Citation network")
        ? [
            {
              name: "📚 Legal Topics",
              items: [
                "Issue areas",
                "Amendments",
                "Constitutional provisions",
                "Landmark cases",
              ],
            },
            {
              name: "🕸️ Networks",
              items: ["Citation network", "Precedent network", "Coalitions"],
            },
          ]
        : [];
  const view = params.get("view") || "";
  const group =
    groups.find((g) => g.name === params.get("group")) ||
    groups.find((g) => g.items.includes(view)) ||
    groups[0];
  const visible = group?.items || items;
  const selected = visible.includes(view) ? view : visible[0];
  function choose(t: string) {
    setParams((p) => {
      p.set("view", t);
      return p;
    });
  }
  return (
    <>
      {groups.length ? (
        <div className="tabs" role="tablist" aria-label="Categories">
          {groups.map((g) => (
            <button
              key={g.name}
              role="tab"
              aria-selected={g === group}
              onClick={() =>
                setParams((p) => {
                  p.set("group", g.name);
                  p.set("view", g.items[0]);
                  return p;
                })
              }
            >
              {g.name}
            </button>
          ))}
        </div>
      ) : null}
      <div className="tabs" role="tablist" aria-label="Sections">
        {visible.map((t, i) => (
          <button
            role="tab"
            id={`${id}-tab-${i}`}
            aria-selected={selected === t}
            aria-controls={`${id}-panel`}
            key={t}
            onClick={() => choose(t)}
          >
            {tabLabels[t] || t}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${id}-panel`}
        aria-labelledby={`${id}-tab-${visible.indexOf(selected)}`}
      >
        {children(selected)}
      </div>
    </>
  );
}
export function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string | number;
  onChange: (v: string) => void;
  options: (string | number)[];
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
export function TermRange({
  start,
  end,
  onStart,
  onEnd,
}: {
  start: number;
  end: number;
  onStart: (v: number) => void;
  onEnd: (v: number) => void;
}) {
  const { manifest } = useData();
  return (
    <>
      <Select
        label="From term"
        value={start}
        options={[...manifest.terms].reverse()}
        onChange={(v) => onStart(Math.min(+v, end))}
      />
      <Select
        label="Through term"
        value={end}
        options={manifest.terms}
        onChange={(v) => onEnd(Math.max(+v, start))}
      />
    </>
  );
}
export function Bars({
  data,
  format = (v: number) => v.toLocaleString(),
  color,
}: {
  data: { label: string; value: number }[];
  format?: (v: number) => string;
  color?: string;
}) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return data.length ? (
    <div
      className="bars"
      role="img"
      aria-label={data.map((d) => `${d.label}: ${format(d.value)}`).join("; ")}
    >
      {data.map((d) => (
        <div className="bar-row" key={d.label}>
          <span title={d.label}>{d.label}</span>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{
                width: `${Math.max(1, (d.value / max) * 100)}%`,
                background: color,
              }}
            />
          </div>
          <b>{format(d.value)}</b>
        </div>
      ))}
    </div>
  ) : (
    <p className="muted">No matching data.</p>
  );
}
export function Trend({
  data,
  label = "Cases",
}: {
  data: { year: number; value: number }[];
  label?: string;
}) {
  if (!data.length) return <p>No matching data.</p>;
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <>
      <svg
        className="trend"
        viewBox="0 0 800 220"
        role="img"
        aria-label={`${label} from ${data[0].year} to ${data.at(-1)!.year}`}
      >
        <line x1="30" y1="185" x2="775" y2="185" stroke="#d7dfd8" />
        <polyline
          fill="none"
          stroke="#636efa"
          strokeWidth="3"
          points={data
            .map(
              (d, i) =>
                `${30 + (i / Math.max(1, data.length - 1)) * 745},${185 - (d.value / max) * 155}`,
            )
            .join(" ")}
        />
        {data.map((d, i) => (
          <circle
            key={d.year}
            cx={30 + (i / Math.max(1, data.length - 1)) * 745}
            cy={185 - (d.value / max) * 155}
            r="3"
            fill="#636efa"
          >
            <title>
              {d.year}: {d.value.toFixed(1)} {label}
            </title>
          </circle>
        ))}
        <text x="30" y="210">
          {data[0].year}
        </text>
        <text x="738" y="210">
          {data.at(-1)!.year}
        </text>
        <text x="30" y="18">
          {max.toFixed(0)} {label}
        </text>
      </svg>
      <details>
        <summary>View chart data</summary>
        <DataTable rows={data} />
      </details>
    </>
  );
}
export function DataTable({
  rows,
  columns,
  filename = "supreme-scrutiny.csv",
}: {
  rows: Record<string, any>[];
  columns?: string[];
  filename?: string;
}) {
  const [page, setPage] = useState(0);
  const keys = columns || Object.keys(rows[0] || {});
  const pages = Math.ceil(rows.length / 30);
  const current = Math.min(page, Math.max(0, pages - 1));
  return (
    <>
      <div className="table-tools">
        <span>{rows.length.toLocaleString()} records</span>
        <button
          className="button small"
          disabled={!rows.length}
          onClick={() =>
            downloadCSV(
              filename,
              rows.map((r) => Object.fromEntries(keys.map((k) => [k, r[k]]))),
            )
          }
        >
          ↓ Export CSV
        </button>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {keys.map((k) => (
                <th key={k}>{k.replaceAll("_", " ")}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(current * 30, (current + 1) * 30).map((r, i) => (
              <tr key={i}>
                {keys.map((k) => (
                  <td key={k}>
                    {typeof r[k] === "object"
                      ? JSON.stringify(r[k])
                      : String(r[k] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 ? (
        <div className="pagination">
          <button disabled={!current} onClick={() => setPage(current - 1)}>
            Previous
          </button>
          <span>
            {current + 1} / {pages}
          </span>
          <button
            disabled={current >= pages - 1}
            onClick={() => setPage(current + 1)}
          >
            Next
          </button>
        </div>
      ) : null}
      {!rows.length ? (
        <p className="muted">No records match these filters.</p>
      ) : null}
    </>
  );
}
export function CaseList({
  rows,
  limit = 20,
}: {
  rows: CaseRecord[];
  limit?: number;
}) {
  const { watchlist, toggleSaved } = useData();
  const [count, setCount] = useState(limit);
  return (
    <>
      <div className="case-list">
        {rows.slice(0, count).map((c) => (
          <article className="case-card" key={c.id}>
            <div>
              <div className="case-meta">
                <span>{c.term} term</span>
                <span>{c.issue}</span>
                {c.split ? <span>{c.split}</span> : null}
              </div>
              <Link to={caseURL(c.id)} className="case-name">
                {c.name}
              </Link>
              <p>{c.question || c.snippet || "Case metadata available."}</p>
              <div className="case-meta">
                <span>{c.outcome || "Outcome unavailable"}</span>
                <span>{c.decided || "Decision date unavailable"}</span>
              </div>
            </div>
            <button
              className="save"
              aria-label={`${watchlist.includes(c.id) ? "Unsave" : "Save"} ${c.name}`}
              aria-pressed={watchlist.includes(c.id)}
              onClick={() => toggleSaved(c.id)}
            >
              {watchlist.includes(c.id) ? "★" : "☆"}
            </button>
          </article>
        ))}
      </div>
      {!rows.length ? <Notice>No cases match these filters.</Notice> : null}
      {rows.length > count ? (
        <button className="button" onClick={() => setCount(count + limit)}>
          Show more cases ({rows.length - count} remaining)
        </button>
      ) : null}
    </>
  );
}
export function Matrix({
  names,
  values,
}: {
  names: string[];
  values: { value: number | null; total: number }[][];
}) {
  return (
    <div className="table-scroll">
      <table className="matrix">
        <thead>
          <tr>
            <th>Agreement</th>
            {names.map((n) => (
              <th key={n}>{n.split(" ").at(-1)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {names.map((n, i) => (
            <tr key={n}>
              <th>{n}</th>
              {values[i].map((v, j) => (
                <td
                  key={names[j]}
                  title={`${n} / ${names[j]}: ${v.total} shared cases`}
                  style={{
                    background:
                      v.value === null
                        ? "#eee"
                        : `rgba(41,99,79,${v.value * 0.8})`,
                    color: (v.value ?? 0) > 0.7 ? "white" : "#172b26",
                  }}
                >
                  {v.value === null ? "—" : `${Math.round(v.value * 100)}%`}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
