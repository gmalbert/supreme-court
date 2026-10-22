import { useMemo, useState } from "react";
import { useData } from "../context";
import { agreement, counts, percent } from "../lib/data";
import {
  Bars,
  CaseList,
  DataTable,
  Matrix,
  Notice,
  PageTitle,
  Panel,
  Select,
  Tabs,
  TermRange,
} from "../components/UI";
export default function Legacy() {
  const { cases, catalog, manifest } = useData();
  const data: any[][] = catalog["8_Presidential_Legacy"].JUSTICES_DATA || [];
  const presidents = [...new Set(data.map((j) => String(j[3])))];
  const [president, setPresident] = useState("Trump");
  const [start, setStart] = useState(manifest.terms[0] - 9);
  const [end, setEnd] = useState(manifest.terms[0]);
  const cohort = data.filter((j) => j[3] === president);
  const surnames = new Set(cohort.map((j) => j[0].split(" ").at(-1)));
  const sameCohort = (name: string) =>
    cohort.some((j) => name === j[0]) ||
    surnames.has(
      name
        .replace(/,? Jr\.?$/, "")
        .split(" ")
        .at(-1),
    );
  const rows = cases.filter((c) => c.term >= start && c.term <= end);
  const relevant = rows.filter((c) => c.votes.some((v) => sameCohort(v.name)));
  const names = counts(
    relevant.flatMap((c) => c.votes.filter((v) => sameCohort(v.name))),
    (v) => v.name,
  )
    .slice(0, 12)
    .map((v) => v.label);
  const matrix = useMemo(
    () => agreement(rows, names),
    [rows, JSON.stringify(names)],
  );
  const scores = presidents.map((p) => {
    const js = data.filter((j) => j[3] === p);
    return {
      President: p,
      Appointees: new Set(js.map((j) => j[0])).size,
      "Service years": js.reduce(
        (s, j) => s + (j[2] || new Date().getFullYear()) - j[1],
        0,
      ),
      "Still serving": js.filter((j) => j[2] === null).length,
    };
  });
  return (
    <>
      <PageTitle
        title="The presidential legacy"
        eyebrow="Appointments & influence"
      >
        Compare appointment cohorts and their recorded votes across the Court’s
        history.
      </PageTitle>
      <div className="filters">
        <Select
          label="Appointing president"
          value={president}
          options={presidents}
          onChange={setPresident}
        />
        <TermRange start={start} end={end} onStart={setStart} onEnd={setEnd} />
      </div>
      <Tabs
        items={[
          "Overview",
          "Cohort analysis",
          "Influence by issue",
          "Voting blocs",
          "Legacy score",
        ]}
      >
        {(selected) => (
          <>
            {selected === "Overview" ? (
              <>
                <Panel title={`${president} appointees`}>
                  <DataTable
                    rows={cohort.map((j) => ({
                      Justice: j[0],
                      From: j[1],
                      Through: j[2] || "Present",
                      Party: j[4],
                      Lean: j[5],
                      Seat: j[6],
                    }))}
                  />
                </Panel>
                <Panel title="Appointees by president">
                  <Bars
                    data={scores.map((r) => ({
                      label: r.President,
                      value: r.Appointees,
                    }))}
                  />
                </Panel>
              </>
            ) : null}
            {selected === "Cohort analysis" ? (
              <>
                <Panel title="Recorded cohort votes">
                  <Bars
                    data={counts(
                      relevant.flatMap((c) =>
                        c.votes.filter((v) => sameCohort(v.name)),
                      ),
                      (v) => v.vote,
                    )}
                  />
                </Panel>
                <CaseList rows={relevant} />
              </>
            ) : null}
            {selected === "Influence by issue" ? (
              <>
                <Notice>
                  Counts participation in recorded decisions, not causal
                  influence on outcomes.
                </Notice>
                <Panel title="Issue areas with cohort participation">
                  <Bars data={counts(relevant, (c) => c.issue)} />
                </Panel>
                <CaseList rows={relevant} />
              </>
            ) : null}
            {selected === "Voting blocs" ? (
              <Panel title="Within-cohort agreement">
                <Matrix names={names} values={matrix} />
              </Panel>
            ) : null}
            {selected === "Legacy score" ? (
              <>
                <Notice>
                  Service years and appointee counts describe tenure. They do
                  not measure the legal or social importance of a president’s
                  legacy.
                </Notice>
                <Panel title="Appointment and tenure measures">
                  <DataTable rows={scores} />
                  <Bars
                    data={scores.map((r) => ({
                      label: r.President,
                      value: r["Service years"],
                    }))}
                  />
                </Panel>
              </>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
