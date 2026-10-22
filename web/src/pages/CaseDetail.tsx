import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useData } from "../context";
import { loadDetail, loadJSON } from "../lib/data";
import type { Argument, Detail } from "../types";
import {
  Bars,
  Notice,
  PageTitle,
  Panel,
  Tabs,
  DataTable,
} from "../components/UI";
function Transcript({ id }: { id: string }) {
  const [data, setData] = useState<Argument | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(100);
  useEffect(() => {
    let active = true;
    loadJSON<Argument>(`/data/arguments/${encodeURIComponent(id)}.json`)
      .then((v) => {
        if (active) setData(v);
      })
      .catch(() => {
        if (active)
          setError(
            "This transcript is unavailable in the snapshot. Use the Oyez link to consult the original record.",
          );
      });
    return () => {
      active = false;
    };
  }, [id]);
  if (error) return <Notice>{error}</Notice>;
  if (!data) return <Notice>Loading transcript…</Notice>;
  const rows = data.turns.filter((t) =>
    `${t.speaker} ${t.text}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <>
      <label className="field">
        <span>Find in transcript</span>
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setLimit(100);
          }}
          placeholder="Speaker or phrase"
        />
      </label>
      <p className="muted">
        {rows.length.toLocaleString()} speaking turns · times from original
        recording
      </p>
      <div className="transcript">
        {rows.slice(0, limit).map((t, i) => (
          <div className="turn" key={i}>
            <div>
              <b>{t.speaker}</b>
              <time>
                {Math.floor(t.start / 60)}:
                {String(Math.floor(t.start % 60)).padStart(2, "0")}
              </time>
            </div>
            <p>{t.text}</p>
          </div>
        ))}
      </div>
      {rows.length > limit ? (
        <button className="button" onClick={() => setLimit(limit + 100)}>
          Read more transcript
        </button>
      ) : null}
    </>
  );
}
export default function CaseDetail() {
  const params = useParams();
  const id = params["*"] || "";
  const { cases, watchlist, toggleSaved } = useData();
  const record = cases.find((c) => c.id === id);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [argument, setArgument] = useState("");
  useEffect(() => {
    setDetail(null);
    setError("");
    setArgument("");
    let active = true;
    loadDetail(id)
      .then((d) => {
        if (active) {
          setDetail(d);
          setArgument(d.arguments[0]?.id || "");
        }
      })
      .catch(() => {
        if (active)
          setError("Full case details are not available in this data release.");
      });
    return () => {
      active = false;
    };
  }, [id]);
  if (!record)
    return (
      <>
        <PageTitle title="Case not found" />
        <Notice>This case is not in the current archive.</Notice>
        <Link to="/Cases">Return to the case library</Link>
      </>
    );
  return (
    <>
      <Link to="/Cases" className="back-link">
        ← Case library
      </Link>
      <PageTitle
        title={record.name}
        eyebrow={`${record.term} term · Docket ${record.docket}`}
      >
        {record.issue} · {record.outcome} · {record.split || "Vote unavailable"}
      </PageTitle>
      <div className="actions">
        <button
          className="button"
          aria-pressed={watchlist.includes(id)}
          onClick={() => toggleSaved(id)}
        >
          {watchlist.includes(id) ? "★ Saved" : "☆ Save case"}
        </button>
        <a
          className="button"
          href={`https://www.oyez.org/cases/${id}`}
          target="_blank"
          rel="noreferrer"
        >
          Original record ↗
        </a>
        <button className="button" onClick={() => window.print()}>
          Print / save PDF
        </button>
      </div>
      {error ? <Notice>{error}</Notice> : null}
      {!detail && !error ? <Notice>Loading the case record…</Notice> : null}
      {detail ? (
        <Tabs
          items={[
            "Overview",
            "Votes & opinions",
            "Oral arguments",
            "Court journey",
          ]}
        >
          {(selected) => (
            <>
              {selected === "Overview" ? (
                <>
                  <Panel title="The legal question">
                    <p className="lead">
                      {detail.question || "No question recorded."}
                    </p>
                  </Panel>
                  <Panel title="Background & facts">
                    <p className="long-text">
                      {detail.facts ||
                        detail.description ||
                        "No background recorded."}
                    </p>
                  </Panel>
                  <Panel title="The Court’s conclusion">
                    <p className="long-text">
                      {detail.holding || "No conclusion recorded."}
                    </p>
                  </Panel>
                  <div className="two-columns">
                    <Panel title="Case record">
                      <dl>
                        <dt>Argued</dt>
                        <dd>{record.argued || "Not recorded"}</dd>
                        <dt>Decided</dt>
                        <dd>{record.decided || "Not recorded"}</dd>
                        <dt>Court below</dt>
                        <dd>{record.court}</dd>
                        <dt>Parties</dt>
                        <dd>
                          {detail.firstParty} / {detail.secondParty}
                        </dd>
                      </dl>
                    </Panel>
                    <Panel title="Advocates">
                      {detail.advocates.length ? (
                        detail.advocates.map((a) => (
                          <p key={a.name}>
                            <b>{a.name}</b>
                            <br />
                            {a.description}
                          </p>
                        ))
                      ) : (
                        <p>No advocate information recorded.</p>
                      )}
                    </Panel>
                  </div>
                </>
              ) : null}
              {selected === "Votes & opinions" ? (
                <>
                  <Panel title="Justice votes">
                    <DataTable
                      rows={record.votes.map((v) => ({
                        Justice: v.name,
                        Vote: v.vote,
                        Opinion: v.opinion || "",
                      }))}
                    />
                  </Panel>
                  {detail.decisions.length > 1 ? (
                    <Panel title="All recorded decisions">
                      {detail.decisions.map((d, i) => (
                        <details key={i}>
                          <summary>
                            Decision {i + 1}:{" "}
                            {d.description || "No description"}
                          </summary>
                          <DataTable
                            rows={d.votes.map((v) => ({
                              Justice: v.name,
                              Vote: v.vote,
                              Opinion: v.opinion || "",
                            }))}
                          />
                        </details>
                      ))}
                    </Panel>
                  ) : null}
                  <Panel title="Written opinions">
                    {detail.opinions.map((o, i) => (
                      <p key={i}>
                        <b>{o.title || o.type?.label || "Opinion"}</b>
                        {o.author ? ` · ${o.author}` : ""}
                        {o.url &&
                        /^https:\/\/supreme\.justia\.com\//.test(o.url) ? (
                          <>
                            {" "}
                            ·{" "}
                            <a href={o.url} target="_blank" rel="noreferrer">
                              Read opinion ↗
                            </a>
                          </>
                        ) : null}
                      </p>
                    ))}
                    {!detail.opinions.length ? (
                      <p>No written opinion links recorded.</p>
                    ) : null}
                  </Panel>
                </>
              ) : null}
              {selected === "Oral arguments" ? (
                <Panel title="Oral arguments">
                  {detail.arguments.length ? (
                    <>
                      <label className="field">
                        <span>Argument session</span>
                        <select
                          value={argument}
                          onChange={(e) => setArgument(e.target.value)}
                        >
                          {detail.arguments.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.title}
                            </option>
                          ))}
                        </select>
                      </label>
                      <p>
                        <a href={detail.oyez} target="_blank" rel="noreferrer">
                          Listen to the original audio on Oyez ↗
                        </a>
                      </p>
                      {argument &&
                      detail.arguments.find((a) => a.id === argument)
                        ?.transcriptAvailable ? (
                        <Transcript key={argument} id={argument} />
                      ) : (
                        <Notice>
                          This transcript is not present in the source snapshot.
                          The original Oyez record may have audio or additional
                          material.
                        </Notice>
                      )}
                    </>
                  ) : (
                    <Notice>
                      No oral argument sessions are recorded for this case.
                    </Notice>
                  )}
                </Panel>
              ) : null}
              {selected === "Court journey" ? (
                <Panel title="Path to the Supreme Court">
                  <ol className="journey">
                    <li>
                      <b>{record.court}</b>
                      <p>{record.circuit}</p>
                    </li>
                    <li>
                      <b>Supreme Court of the United States</b>
                      <p>
                        {record.outcome} ·{" "}
                        {record.decided || "Date unavailable"}
                      </p>
                    </li>
                  </ol>
                  <DataTable
                    rows={detail.timeline.map((v) => ({
                      Event: v.event,
                      Dates: v.dates
                        .map((t) =>
                          new Date(t * 1000).toISOString().slice(0, 10),
                        )
                        .join(", "),
                    }))}
                  />
                  <Bars
                    data={[
                      {
                        label: "Majority / concurrence",
                        value: record.majority,
                      },
                      { label: "Dissent / minority", value: record.dissent },
                    ]}
                  />
                </Panel>
              ) : null}
            </>
          )}
        </Tabs>
      ) : null}
    </>
  );
}
