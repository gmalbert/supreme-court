import { useState } from "react";
import { Link } from "react-router-dom";
import { useData } from "../context";
import { caseURL, counts } from "../lib/data";
import {
  Bars,
  CaseList,
  DataTable,
  Notice,
  PageTitle,
  Panel,
  Select,
  Tabs,
  TermRange,
} from "../components/UI";
export function CuratedRecord({ value }: { value: any }) {
  if (value === null || value === undefined) return null;
  if (typeof value !== "object") return <p>{String(value)}</p>;
  if (Array.isArray(value))
    return (
      <div className="curated-records">
        {value.map((v, i) => (
          <div key={i}>
            {Array.isArray(v) ? (
              <p>
                {v.map((x: any, j: number) =>
                  typeof x === "string" &&
                  /^https:\/\/(api\.|www\.)?oyez\.org\//.test(x) ? (
                    <a
                      key={j}
                      href={x.replace("api.oyez.org", "www.oyez.org")}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {" "}
                      Original record ↗{" "}
                    </a>
                  ) : (
                    <span key={j}>
                      {j ? " · " : ""}
                      {typeof x === "object"
                        ? JSON.stringify(x)
                        : String(x ?? "")}
                    </span>
                  ),
                )}
              </p>
            ) : (
              <CuratedRecord value={v} />
            )}
          </div>
        ))}
      </div>
    );
  return (
    <dl>
      {Object.entries(value).map(([k, v]) => (
        <div key={k}>
          <dt>{k.replaceAll("_", " ")}</dt>
          <dd>
            <CuratedRecord value={v} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
function Network({ nodes, edges }: { nodes: any[]; edges: any[] }) {
  const nodeIds = new Map(nodes.map((n, i) => [n[0], i]));
  const point = (i: number) => ({
    x: 460 + Math.cos((i / nodes.length) * Math.PI * 2) * 310,
    y: 305 + Math.sin((i / nodes.length) * Math.PI * 2) * 235,
  });
  return (
    <>
      <svg
        viewBox="0 0 920 610"
        className="network"
        role="img"
        aria-label="Curated case relationship network"
      >
        {edges.map((e, i) => {
          const a = nodeIds.get(e[0]),
            b = nodeIds.get(e[1]);
          if (a === undefined || b === undefined) return null;
          const from = point(a),
            to = point(b);
          return (
            <line
              key={i}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke={/overrul/i.test(e[2]) ? "#a44e42" : "#9bb9a9"}
              strokeWidth="1.5"
            >
              <title>
                {e[0]} → {e[1]}: {e[2]}
              </title>
            </line>
          );
        })}
        {nodes.map((n, i) => {
          const p = point(i);
          return (
            <g key={n[0]}>
              <circle cx={p.x} cy={p.y} r="7" fill="#29634f" />
              <text x={p.x + 10} y={p.y + 3} fontSize="10">
                {String(n[1]).slice(0, 30)}
              </text>
              <title>
                {n[1]} ({n[2]})
              </title>
            </g>
          );
        })}
      </svg>
      <DataTable
        rows={edges.map((e) => ({
          Source: nodes.find((n) => n[0] === e[0])?.[1] || e[0],
          Target: nodes.find((n) => n[0] === e[1])?.[1] || e[1],
          Relationship: e[2],
          Note: e[3] || "",
        }))}
      />
    </>
  );
}
export default function Topics() {
  const { cases, catalog, manifest } = useData();
  const [start, setStart] = useState(1955);
  const [end, setEnd] = useState(manifest.terms[0]);
  const [issue, setIssue] = useState("First Amendment");
  const amendments =
    catalog.Topics.AMENDMENTS || catalog.legal.amendments || {};
  const doctrines = catalog.Topics.DOCTRINES || {};
  const [amendment, setAmendment] = useState(Object.keys(amendments)[0]);
  const [doctrine, setDoctrine] = useState(Object.keys(doctrines)[0]);
  const [relation, setRelation] = useState("All relationships");
  const edges: any[] = catalog.Topics.EDGES_CN || [];
  return (
    <>
      <PageTitle title="📚 Topics & Networks" eyebrow="Topics & networks">
        Explore issue areas, constitutional provisions, and the relationships
        between landmark decisions.
      </PageTitle>
      <Tabs
        items={[
          "Issue areas",
          "Amendments",
          "Constitutional provisions",
          "Landmark cases",
          "Citation network",
          "Precedent network",
          "Coalitions",
        ]}
      >
        {(selected) => (
          <>
            {selected === "Issue areas" ? (
              <>
                <div className="filters">
                  <Select
                    label="Issue area"
                    value={issue}
                    options={counts(cases, (c) => c.issue)
                      .map((r) => r.label)
                      .sort()}
                    onChange={setIssue}
                  />
                  <TermRange
                    start={start}
                    end={end}
                    onStart={setStart}
                    onEnd={setEnd}
                  />
                </div>
                <Panel title="Decisions by term">
                  <Bars
                    data={counts(
                      cases.filter(
                        (c) =>
                          c.issue === issue && c.term >= start && c.term <= end,
                      ),
                      (c) => String(c.term),
                    )}
                  />
                </Panel>
                <CaseList
                  rows={cases.filter(
                    (c) =>
                      c.issue === issue && c.term >= start && c.term <= end,
                  )}
                />
              </>
            ) : null}
            {selected === "Amendments" ? (
              <>
                <Select
                  label="Constitutional provision"
                  value={amendment}
                  options={Object.keys(amendments)}
                  onChange={setAmendment}
                />
                <Panel title={amendment}>
                  <CuratedRecord value={amendments[amendment]} />
                </Panel>
              </>
            ) : null}
            {selected === "Constitutional provisions" ? (
              <>
                <Select
                  label="Doctrine"
                  value={doctrine}
                  options={Object.keys(doctrines)}
                  onChange={setDoctrine}
                />
                <Panel title={doctrine}>
                  <CuratedRecord value={doctrines[doctrine]} />
                </Panel>
              </>
            ) : null}
            {selected === "Landmark cases" ? (
              <>
                {Object.entries(catalog.Topics.LANDMARK_CASES_LT || {}).map(
                  ([name, value]) => (
                    <Panel title={name} key={name}>
                      <CuratedRecord value={value} />
                    </Panel>
                  ),
                )}
              </>
            ) : null}
            {selected === "Citation network" ||
            selected === "Precedent network" ? (
              <>
                <Notice>
                  These are curated relationships retained from the original
                  app, not an automated citator or current-law check.
                </Notice>
                {selected === "Citation network" ? (
                  <>
                    <Select
                      label="Relationship"
                      value={relation}
                      options={[
                        "All relationships",
                        ...new Set(edges.map((e) => e[2])),
                      ]}
                      onChange={setRelation}
                    />
                    <Panel title="How landmark cases connect">
                      <Network
                        nodes={catalog.Topics.CASES_CN || []}
                        edges={edges.filter(
                          (e) =>
                            relation === "All relationships" ||
                            e[2] === relation,
                        )}
                      />
                    </Panel>
                  </>
                ) : (
                  <Panel title="Precedent relationships">
                    <DataTable
                      rows={(catalog.Topics.EDGES_PN || []).map((e: any[]) => ({
                        From: e[0],
                        To: e[1],
                        Relationship: e[2],
                        Explanation: e[3],
                      }))}
                    />
                  </Panel>
                )}
              </>
            ) : null}
            {selected === "Coalitions" ? (
              <Panel title="Explore voting coalitions">
                <p>
                  Use the agreement matrix to inspect pairwise voting agreement
                  with a consistent shared-case denominator.
                </p>
                <Link className="button" to="/People?view=Agreement+matrix">
                  Open agreement matrix →
                </Link>
              </Panel>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
