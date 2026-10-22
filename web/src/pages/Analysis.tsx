import { useMemo, useState } from "react";
import { useData } from "../context";
import {
  Bars,
  CaseList,
  CaseMetrics,
  DataTable,
  Notice,
  PageTitle,
  Panel,
  Select,
  Tabs,
  TermRange,
  Trend,
} from "../components/UI";
import {
  counts,
  isAffirm,
  isReverse,
  partyType,
  percent,
  rate,
} from "../lib/data";
import type { CaseRecord } from "../types";
export function OutcomePanels({ rows }: { rows: CaseRecord[] }) {
  return (
    <div className="two-columns">
      <Panel title="Cases by issue area">
        <Bars data={counts(rows, (c) => c.issue)} />
      </Panel>
      <Panel title="Recorded outcomes">
        <Bars data={counts(rows, (c) => c.outcome)} />
      </Panel>
    </div>
  );
}
export default function Analysis() {
  const { cases, catalog, manifest } = useData();
  const [start, setStart] = useState(manifest.terms[0] - 9);
  const [end, setEnd] = useState(manifest.terms[0]);
  const [term, setTerm] = useState(manifest.terms[0]);
  const [split, setSplit] = useState("All close decisions");
  const [party, setParty] = useState("All parties");
  const [issue, setIssue] = useState("All issues");
  const rows = useMemo(
    () =>
      cases.filter(
        (c) =>
          c.term >= start &&
          c.term <= end &&
          (issue === "All issues" || c.issue === issue),
      ),
    [cases, start, end, issue],
  );
  const close = rows.filter(
    (c) =>
      c.dissent > 0 &&
      (split === "All close decisions"
        ? c.majority - c.dissent <= 3
        : c.split === split),
  );
  const parties = counts(rows, (c) => partyType(c.party)).map(
    ({ label, value }) => {
      const subset = rows.filter((c) => partyType(c.party) === label);
      const known = subset.filter((c) => c.winner);
      return {
        Party: label,
        Cases: value,
        "Known winners": known.length,
        "Petitioner wins": known.filter(
          (c) =>
            c.winner.toLowerCase() === c.party.toLowerCase() ||
            /petitioner|appellant/i.test(c.winner),
        ).length,
      };
    },
  );
  return (
    <>
      <PageTitle title="📊 Analytics" eyebrow="Analytics">
        Look across terms, outcomes, and the cases that divided the Court.
      </PageTitle>
      <Tabs
        items={[
          "Term statistics",
          "Close decisions",
          "Win rates",
          "SCOTUS vs. Congress",
        ]}
      >
        {(selected) => (
          <>
            {selected === "Term statistics" ? (
              <>
                <div className="filters">
                  <Select
                    label="Term"
                    value={term}
                    options={manifest.terms}
                    onChange={(v) => setTerm(+v)}
                  />
                </div>
                <CaseMetrics rows={cases.filter((c) => c.term === term)} />
                <OutcomePanels rows={cases.filter((c) => c.term === term)} />
                <Panel title="Case listing">
                  <CaseList rows={cases.filter((c) => c.term === term)} />
                </Panel>
              </>
            ) : null}
            {selected !== "Term statistics" &&
            selected !== "SCOTUS vs. Congress" ? (
              <>
                <div className="filters">
                  <TermRange
                    start={start}
                    end={end}
                    onStart={setStart}
                    onEnd={setEnd}
                  />
                  <Select
                    label="Issue area"
                    value={issue}
                    options={[
                      "All issues",
                      ...counts(cases, (c) => c.issue).map((v) => v.label),
                    ]}
                    onChange={setIssue}
                  />
                </div>
                <CaseMetrics rows={rows} />
              </>
            ) : null}
            {selected === "Close decisions" ? (
              <>
                <div className="filters">
                  <Select
                    label="Vote split"
                    value={split}
                    options={["All close decisions", "5-4", "6-3", "7-2"]}
                    onChange={setSplit}
                  />
                </div>
                <div className="two-columns">
                  <Panel title="Vote splits">
                    <Bars data={counts(close, (c) => c.split)} />
                  </Panel>
                  <Panel title="Close decisions by term">
                    <Trend
                      data={counts(close, (c) => String(c.term))
                        .map((r) => ({ year: +r.label, value: r.value }))
                        .sort((a, b) => a.year - b.year)}
                    />
                  </Panel>
                </div>
                <Panel title="Majority participation in 5–4 cases">
                  <p className="muted">
                    Counts majority/concurrence votes in recorded 5–4 decisions;
                    participation alone does not identify a causal deciding
                    vote.
                  </p>
                  <Bars
                    data={counts(
                      rows
                        .filter((c) => c.split === "5-4")
                        .flatMap((c) =>
                          c.votes.filter((v) =>
                            /majority|concurrence/i.test(v.vote),
                          ),
                        ),
                      (v) => v.name,
                    ).slice(0, 15)}
                  />
                </Panel>
                <CaseList rows={close} />
              </>
            ) : null}
            {selected === "Win rates" ? (
              <>
                <Notice>
                  Party types are heuristic classifications from petitioner
                  names. Rates use only records with an identified winning
                  party.
                </Notice>
                <Panel title="Petitioner outcomes">
                  <DataTable
                    rows={parties.map((p) => ({
                      ...p,
                      "Win rate": p["Known winners"]
                        ? percent(p["Petitioner wins"] / p["Known winners"])
                        : "—",
                    }))}
                  />
                </Panel>
                <div className="filters">
                  <Select
                    label="Petitioner type"
                    value={party}
                    options={["All parties", ...parties.map((p) => p.Party)]}
                    onChange={setParty}
                  />
                </div>
                <Panel title="Outcomes by issue">
                  <Bars
                    data={counts(
                      rows.filter(
                        (c) =>
                          party === "All parties" ||
                          partyType(c.party) === party,
                      ),
                      (c) => c.issue,
                    )}
                  />
                </Panel>
                <CaseList
                  rows={rows.filter(
                    (c) =>
                      party === "All parties" || partyType(c.party) === party,
                  )}
                />
              </>
            ) : null}
            {selected === "SCOTUS vs. Congress" ? (
              <Panel title="Curated statutory and constitutional milestones">
                <p className="muted">
                  Editorial reference collection from the original app. It
                  includes invalidations, statutory interpretations, and
                  doctrine changes; entries are not all findings that a law is
                  unconstitutional.
                </p>
                <DataTable rows={catalog.Analysis.LAWS_STRUCK_DOWN || []} />
              </Panel>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
export function CircuitCourts() {
  const { cases, manifest } = useData();
  const [start, setStart] = useState(manifest.terms[0] - 9);
  const [end, setEnd] = useState(manifest.terms[0]);
  const [a, setA] = useState("9th Circuit");
  const [b, setB] = useState("6th Circuit");
  const [issue, setIssue] = useState("All issues");
  const rows = cases.filter(
    (c) =>
      c.term >= start &&
      c.term <= end &&
      (issue === "All issues" || c.issue === issue),
  );
  const circuits = counts(cases, (c) => c.circuit)
    .map((c) => c.label)
    .sort();
  const stats = circuits
    .map((c) => {
      const s = rows.filter((r) => r.circuit === c);
      return {
        Circuit: c,
        Cases: s.length,
        Reversed: s.filter(isReverse).length,
        Affirmed: s.filter(isAffirm).length,
        "Reversal rate": percent(rate(s)),
      };
    })
    .filter((c) => c.Cases);
  return (
    <>
      <PageTitle title="🏛️ Circuit Courts" eyebrow="The appellate landscape">
        Compare the lower courts whose decisions reach the Supreme Court.
      </PageTitle>
      <div className="filters">
        <TermRange start={start} end={end} onStart={setStart} onEnd={setEnd} />
        <Select
          label="Issue area"
          value={issue}
          options={[
            "All issues",
            ...counts(cases, (c) => c.issue).map((c) => c.label),
          ]}
          onChange={setIssue}
        />
      </div>
      <Tabs
        items={[
          "Circuit comparison",
          "Reversal scorecard",
          "Historical outcomes",
        ]}
      >
        {(selected) => (
          <>
            {selected === "Circuit comparison" ? (
              <>
                <div className="filters">
                  <Select
                    label="Circuit A"
                    value={a}
                    options={circuits}
                    onChange={setA}
                  />
                  <Select
                    label="Circuit B"
                    value={b}
                    options={circuits}
                    onChange={setB}
                  />
                </div>
                <div className="two-columns">
                  {[a, b].map((c, i) => (
                    <Panel title={c} key={i}>
                      <CaseMetrics rows={rows.filter((r) => r.circuit === c)} />
                      <Bars
                        data={counts(
                          rows.filter((r) => r.circuit === c),
                          (r) => r.issue,
                        )}
                      />
                      <CaseList
                        rows={rows.filter((r) => r.circuit === c)}
                        limit={5}
                      />
                    </Panel>
                  ))}
                </div>
              </>
            ) : null}
            {selected === "Reversal scorecard" ? (
              <Panel title="Circuit scorecard">
                <DataTable rows={stats} />
              </Panel>
            ) : null}
            {selected === "Historical outcomes" ? (
              <>
                <Panel title="Reversal rates by circuit">
                  <Bars
                    data={stats.map((s) => ({
                      label: s.Circuit,
                      value: parseFloat(s["Reversal rate"]) || 0,
                    }))}
                    format={(v) => `${v.toFixed(1)}%`}
                  />
                </Panel>
                <Notice>
                  These describe Supreme Court review of selected cases, not the
                  overall quality of a circuit’s decisions.
                </Notice>
                <CaseList rows={rows} />
              </>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
