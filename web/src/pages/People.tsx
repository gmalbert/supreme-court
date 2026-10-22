import { useMemo, useState } from "react";
import { useData } from "../context";
import { agreement, counts, percent } from "../lib/data";
import {
  Bars,
  CaseList,
  DataTable,
  Matrix,
  Metrics,
  Notice,
  PageTitle,
  Panel,
  Select,
  Tabs,
  TermRange,
  Trend,
} from "../components/UI";
export default function People() {
  const { cases, catalog, manifest } = useData();
  const [start, setStart] = useState(manifest.terms[0] - 9);
  const [end, setEnd] = useState(manifest.terms[0]);
  const [name, setName] = useState(
    catalog.justices.find((j) => j.name.includes("Roberts"))?.name ||
      catalog.justices[0].name,
  );
  const [query, setQuery] = useState("");
  const rows = useMemo(
    () => cases.filter((c) => c.term >= start && c.term <= end),
    [cases, start, end],
  );
  const voted = rows.filter((c) => c.votes.some((v) => v.name === name));
  const votes = voted.map((c) => c.votes.find((v) => v.name === name)!);
  const justice = catalog.justices.find((j) => j.name === name);
  const names = useMemo(
    () =>
      counts(
        rows.flatMap((c) => c.votes),
        (v) => v.name,
      )
        .slice(0, 12)
        .map((v) => v.label),
    [rows],
  );
  const matrix = useMemo(() => agreement(rows, names), [rows, names]);
  const roleDate = (stamp: number | undefined) =>
    stamp != null && stamp !== 0
      ? new Date(stamp * 1000).toISOString().slice(0, 10)
      : "Present / not recorded";
  return (
    <>
      <PageTitle title="👥 Justices & Advocates" eyebrow="Justices & advocates">
        Explore careers, voting records, and the lawyers who argued before the
        bench.
      </PageTitle>
      <Tabs
        items={[
          "Justice careers",
          "Voting patterns",
          "Agreement matrix",
          "Ideological drift",
          "Advocates",
          "Amicus briefs",
          "Oral argument analytics",
        ]}
      >
        {(selected) => (
          <>
            {[
              "Justice careers",
              "Voting patterns",
              "Agreement matrix",
              "Ideological drift",
            ].includes(selected) ? (
              <div className="filters">
                <TermRange
                  start={start}
                  end={end}
                  onStart={setStart}
                  onEnd={setEnd}
                />
                {selected !== "Agreement matrix" ? (
                  <Select
                    label="Justice"
                    value={name}
                    options={catalog.justices.map((j) => j.name)}
                    onChange={setName}
                  />
                ) : null}
              </div>
            ) : null}
            {selected === "Justice careers" ||
            selected === "Voting patterns" ? (
              <>
                <Metrics
                  items={[
                    {
                      label: "Recorded votes",
                      value: votes.length.toLocaleString(),
                    },
                    {
                      label: "Majority / concurrence",
                      value: percent(
                        votes.length
                          ? votes.filter((v) =>
                              /^(majority|concurrence)$/i.test(v.vote),
                            ).length / votes.length
                          : null,
                      ),
                    },
                    {
                      label: "Dissents / minority",
                      value: votes.filter((v) =>
                        /^(dissent|minority)$/i.test(v.vote),
                      ).length,
                    },
                  ]}
                />
                {selected === "Justice careers" ? (
                  <Panel title={name}>
                    {justice?.biography ? (
                      <details>
                        <summary>Biography from Oyez</summary>
                        <p className="long-text">{justice.biography}</p>
                      </details>
                    ) : null}
                    <DataTable
                      rows={(justice?.roles || []).map((r) => ({
                        Role: r.role_title,
                        From: roleDate(r.date_start),
                        Through: roleDate(r.date_end),
                        "Appointing president": r.appointing_president,
                      }))}
                    />
                    <p className="muted">
                      {justice?.lean !== "Unclassified"
                        ? `Curated ideological classification: ${justice?.lean}.`
                        : ""}{" "}
                      Ideological labels simplify a more complex record.
                    </p>
                  </Panel>
                ) : null}
                <div className="two-columns">
                  <Panel title="Recorded vote types">
                    <Bars data={counts(votes, (v) => v.vote)} />
                  </Panel>
                  <Panel title="Issue areas">
                    <Bars data={counts(voted, (c) => c.issue)} />
                  </Panel>
                </div>
                <CaseList rows={voted} />
              </>
            ) : null}
            {selected === "Agreement matrix" ? (
              <Panel title="Pairwise voting agreement">
                <p className="muted">
                  Up to twelve most active justices in the selected period.
                  Hover cells for shared-case counts. Majority/concurrence and
                  dissent/minority are grouped separately; recusals are
                  excluded.
                </p>
                <Matrix names={names} values={matrix} />
              </Panel>
            ) : null}
            {selected === "Ideological drift" ? (
              <>
                <Notice>
                  This chart shows dissent participation over time, not an
                  estimated ideological score.
                </Notice>
                <Panel title={`${name}: dissent rate by term`}>
                  <Trend
                    label="% dissent"
                    data={manifest.terms
                      .filter((t) => t >= start && t <= end)
                      .map((t) => {
                        const vs = voted
                          .filter((c) => c.term === t)
                          .map((c) => c.votes.find((v) => v.name === name)!);
                        return {
                          year: t,
                          value: vs.length
                            ? (100 *
                                vs.filter((v) =>
                                  /dissent|minority/i.test(v.vote),
                                ).length) /
                              vs.length
                            : 0,
                        };
                      })
                      .sort((a, b) => a.year - b.year)}
                  />
                </Panel>
              </>
            ) : null}
            {selected === "Advocates" ? (
              <>
                <label className="field">
                  <span>Find an advocate</span>
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Name"
                  />
                </label>
                <Panel title="Advocate appearances and outcomes">
                  <p className="muted">
                    Precomputed across the snapshot. Win rates use known
                    outcomes; appearances can include cases with unknown
                    outcomes.
                  </p>
                  <DataTable
                    rows={catalog.advocates
                      .filter((a) =>
                        a.advocate.toLowerCase().includes(query.toLowerCase()),
                      )
                      .sort((a, b) => b.appearances - a.appearances)}
                  />
                </Panel>
              </>
            ) : null}
            {selected === "Amicus briefs" ? (
              <>
                <Notice>
                  Curated estimates retained from the original app; these are
                  not live counts of all filed briefs.
                </Notice>
                <Panel title="Amicus organizations">
                  <DataTable rows={catalog.People.AMICUS_ORGS || []} />
                </Panel>
                <Panel title="Selected landmark filings">
                  <DataTable rows={catalog.People.LANDMARK_AMICUS || []} />
                </Panel>
              </>
            ) : null}
            {selected === "Oral argument analytics" ? (
              <>
                <Panel title="Questioning patterns">
                  <p className="long-text">
                    {catalog.People.QUESTION_OUTCOME_INSIGHT ||
                      "Question frequency can inform analysis but does not establish how a justice will vote."}
                  </p>
                  <DataTable
                    rows={Object.entries(
                      catalog.People.QUESTION_PATTERNS || {},
                    ).map(([Justice, Patterns]) => ({ Justice, Patterns }))}
                  />
                </Panel>
                <Panel title="Inspect the underlying arguments">
                  <p>
                    Read speaker-attributed transcripts and search for questions
                    in each case’s Oral arguments tab.
                  </p>
                  <CaseList rows={rows.filter((c) => c.audio > 0)} limit={10} />
                </Panel>
              </>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
