import { useState } from "react";
import { useData } from "../context";
import { counts, isAffirm, isReverse, percent, rate } from "../lib/data";
import {
  Bars,
  CaseList,
  DataTable,
  Metrics,
  Notice,
  PageTitle,
  Panel,
  Select,
  Tabs,
  Trend,
} from "../components/UI";
export default function History() {
  const { catalog, cases, manifest } = useData();
  const [year, setYear] = useState(manifest.terms[0]);
  const justices: any[][] = catalog.History.JUSTICES || [];
  const active = justices.filter(
    (j) => j[1] <= year && (j[2] === null || j[2] >= year),
  );
  const [era, setEra] = useState("Roberts");
  const eras: any[] = catalog.History.CJ_ERAS || [];
  const chosen = eras.find((e) => e.cj === era);
  const rows = cases.filter(
    (c) => chosen && c.term >= chosen.start && c.term <= chosen.end,
  );
  return (
    <>
      <PageTitle title="🏛️ Court History" eyebrow="Court history">
        Trace the people, appointments, and eras that shaped the bench.
      </PageTitle>
      <Tabs
        items={[
          "Service timeline",
          "Court snapshot",
          "Ideological balance",
          "Chief Justice eras",
          "Confirmations",
        ]}
      >
        {(selected) => (
          <>
            {selected === "Service timeline" ? (
              <Panel title="Justice service since 1937">
                <div className="service-timeline">
                  {justices.map((j, i) => (
                    <div className="service-row" key={i}>
                      <span>{j[0]}</span>
                      <div>
                        <span
                          style={{
                            left: `${((j[1] - 1937) / 90) * 100}%`,
                            width: `${Math.max(1, (((j[2] || 2026) - Math.max(j[1], 1937)) / 90) * 100)}%`,
                            background:
                              j[4] === "Liberal"
                                ? "#497d9a"
                                : j[4] === "Conservative"
                                  ? "#a36959"
                                  : "#7d8868",
                          }}
                          title={`${j[1]}–${j[2] || "present"} · ${j[3]}`}
                        />
                      </div>
                      <small>
                        {j[1]}–{j[2] || "present"}
                      </small>
                    </div>
                  ))}
                </div>
                <DataTable
                  rows={justices.map((j) => ({
                    Justice: j[0],
                    Start: j[1],
                    End: j[2] || "Present",
                    President: j[3],
                    Lean: j[4],
                    Seat: j[5],
                  }))}
                />
              </Panel>
            ) : null}
            {selected === "Court snapshot" ||
            selected === "Ideological balance" ? (
              <>
                <label className="field">
                  <span>Year: {year}</span>
                  <input
                    type="range"
                    min="1953"
                    max={new Date().getFullYear()}
                    value={year}
                    onChange={(e) => setYear(+e.target.value)}
                  />
                </label>
                <Notice>
                  Ideological labels are curated summaries. Year-only service
                  dates can include both a departing justice and their
                  replacement.
                </Notice>
                <Panel title={`Court snapshot · ${year}`}>
                  <Bars data={counts(active, (j) => j[4])} />
                  <DataTable
                    rows={active.map((j) => ({
                      Justice: j[0],
                      President: j[3],
                      Lean: j[4],
                      Seat: j[5],
                    }))}
                  />
                </Panel>
                {selected === "Ideological balance" ? (
                  <Panel title="Composition over time">
                    <Trend
                      label="conservative seats (year-based)"
                      data={Array.from({ length: 74 }, (_, i) => 1953 + i)
                        .filter((y) => y <= new Date().getFullYear())
                        .map((y) => ({
                          year: y,
                          value: justices.filter(
                            (j) =>
                              j[1] <= y &&
                              (j[2] === null || j[2] >= y) &&
                              j[4] === "Conservative",
                          ).length,
                        }))}
                    />
                  </Panel>
                ) : null}
              </>
            ) : null}
            {selected === "Chief Justice eras" ? (
              <>
                <div className="filters">
                  <Select
                    label="Chief Justice era"
                    value={era}
                    options={eras.map((e) => e.cj)}
                    onChange={setEra}
                  />
                </div>
                <Metrics
                  items={[
                    {
                      label: "Period",
                      value: chosen ? `${chosen.start}–${chosen.end}` : "—",
                    },
                    { label: "Cases in snapshot", value: rows.length },
                    { label: "Reversal rate", value: percent(rate(rows)) },
                  ]}
                />
                <Panel title="Issue areas">
                  <Bars data={counts(rows, (c) => c.issue)} />
                </Panel>
                <CaseList rows={rows} />
              </>
            ) : null}
            {selected === "Confirmations" ? (
              <Panel title="Confirmation record">
                <p className="muted">
                  Curated Senate confirmation data from the original
                  application.
                </p>
                <DataTable rows={catalog.History.CONFIRMATIONS || []} />
              </Panel>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
export function HistoricalData() {
  const { cases, catalog, manifest } = useData();
  const [term, setTerm] = useState(manifest.terms[0]);
  const [metric, setMetric] = useState("Cases decided");
  const [from, setFrom] = useState(1790);
  const h = catalog["13_Historical_Data"];
  const early = (h.PRE_OYEZ_RAW || []).map((r: number[]) => ({
    year: r[0],
    argued: r[1],
    decided: r[2],
    reversed: r[3],
    affirmed: r[4],
    unanimous: r[5],
    source: "Curated historical series",
  }));
  const modern = manifest.terms.map((year) => {
    const s = cases.filter((c) => c.term === year);
    return {
      year,
      argued: s.filter((c) => c.argued).length,
      decided: s.filter((c) => c.decided).length,
      reversed: s.filter(isReverse).length,
      affirmed: s.filter(isAffirm).length,
      unanimous: s.filter((c) => c.dissent === 0 && c.votes.length > 0).length,
      source: "Oyez snapshot",
    };
  });
  const rows = [...early, ...modern]
    .sort((a, b) => a.year - b.year)
    .filter((r) => r.year >= from);
  const value = (r: any) =>
    metric === "Cases argued"
      ? r.argued
      : metric === "Reversed"
        ? r.reversed
        : metric === "Affirmed"
          ? r.affirmed
          : metric === "Reversal rate (%)"
            ? r.reversed + r.affirmed
              ? (100 * r.reversed) / (r.reversed + r.affirmed)
              : 0
            : r.decided;
  return (
    <>
      <PageTitle
        title="📜 Historical Data Explorer"
        eyebrow="1790 to the present"
      >
        Explore historical series alongside the modern case archive.
      </PageTitle>
      <Tabs
        items={[
          "Full timeline",
          "Outcomes",
          "Era comparison",
          "Milestones",
          "Term drilldown",
        ]}
      >
        {(selected) => (
          <>
            {selected === "Full timeline" || selected === "Outcomes" ? (
              <>
                <Notice>
                  Pre-1953 figures are curated historical estimates from the
                  original app. Modern counts come from the available Oyez
                  records; coverage and definitions differ. Early series
                  contains selected years, not every year.
                </Notice>
                <div className="filters">
                  <Select
                    label="Metric"
                    value={metric}
                    options={[
                      "Cases decided",
                      "Cases argued",
                      "Reversed",
                      "Affirmed",
                      "Reversal rate (%)",
                    ]}
                    onChange={setMetric}
                  />
                  <Select
                    label="Starting year"
                    value={from}
                    options={[1790, 1850, 1900, 1955, 2000]}
                    onChange={(v) => setFrom(+v)}
                  />
                </div>
                <Panel title={metric}>
                  <Trend
                    data={rows.map((r) => ({ year: r.year, value: value(r) }))}
                    label={metric}
                  />
                </Panel>
                <Panel title="Historical records">
                  <DataTable rows={rows} />
                </Panel>
              </>
            ) : null}
            {selected === "Era comparison" ? (
              <Panel title="Chief Justice eras">
                <DataTable
                  rows={(h.CJ_ERAS || []).map((e: any) => {
                    const s = cases.filter(
                      (c) => c.term >= e.start && c.term <= e.end,
                    );
                    return {
                      Era: e.cj,
                      Start: e.start,
                      End: e.end,
                      "Oyez cases": s.length,
                      "Reversal rate": percent(rate(s)),
                    };
                  })}
                />
              </Panel>
            ) : null}
            {selected === "Milestones" ? (
              <>
                <Panel title="Landmark institutional events">
                  <DataTable
                    rows={(h.MILESTONES || []).map((v: any) =>
                      Array.isArray(v)
                        ? { Year: v[0], Event: v[1], Description: v[2] }
                        : v,
                    )}
                  />
                </Panel>
                <Panel title="Milestones by category">
                  {Object.entries(h.MILESTONE_CATEGORIES || {}).map(
                    ([key, value]) => (
                      <details key={key}>
                        <summary>{key}</summary>
                        <pre className="record-text">
                          {JSON.stringify(value, null, 2)}
                        </pre>
                      </details>
                    ),
                  )}
                </Panel>
              </>
            ) : null}
            {selected === "Term drilldown" ? (
              <>
                <div className="filters">
                  <Select
                    label="Term"
                    value={term}
                    options={manifest.terms}
                    onChange={(v) => setTerm(+v)}
                  />
                </div>
                <CaseList rows={cases.filter((c) => c.term === term)} />
              </>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
