import { useEffect, useState } from "react";
import { geoAlbersUsa, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import { useData } from "../context";
import { counts, loadJSON, percent, rate } from "../lib/data";
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
} from "../components/UI";
import type { CaseRecord } from "../types";
function StateMap({
  rows,
  onSelect,
  metric,
}: {
  rows: CaseRecord[];
  onSelect: (s: string) => void;
  metric: string;
}) {
  const [shapes, setShapes] = useState<any[]>([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    loadJSON<any>("/states.json")
      .then((topology) => {
        if (active)
          setShapes(
            (feature(topology, topology.objects.states) as any).features,
          );
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, []);
  const values = new Map(
    counts(rows, (c) => c.state).map((v) => [
      v.label,
      metric === "Cases reviewed"
        ? v.value
        : (rate(rows.filter((c) => c.state === v.label)) ?? 0) * 100,
    ]),
  );
  const max = Math.max(...values.values(), 1);
  const path = geoPath(geoAlbersUsa().scale(1050).translate([480, 285]));
  return error ? (
    <Notice>
      Map geometry is unavailable; the state table below contains the same data.
    </Notice>
  ) : (
    <svg
      className="state-map"
      viewBox="0 0 960 600"
      role="group"
      aria-label="Cases by state"
    >
      {shapes.map((f) => {
        const name = f.properties.name;
        const value = values.get(name) || 0;
        return (
          <path
            key={f.id}
            d={path(f) || ""}
            fill={`rgba(41,99,79,${0.08 + (0.85 * value) / max})`}
            stroke="#fff"
            strokeWidth="1"
            role="button"
            tabIndex={0}
            aria-label={`${name}: ${value.toFixed(1)} ${metric}`}
            onClick={() => onSelect(name)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(name);
              }
            }}
          >
            <title>
              {name}: {value.toFixed(1)} {metric}
            </title>
          </path>
        );
      })}
    </svg>
  );
}
export default function Geography() {
  const { cases, manifest, catalog } = useData();
  const [start, setStart] = useState(manifest.terms[0] - 9);
  const [end, setEnd] = useState(manifest.terms[0]);
  const [state, setState] = useState("All states");
  const [metric, setMetric] = useState("Cases reviewed");
  const [a, setA] = useState(manifest.terms[0]);
  const [b, setB] = useState(manifest.terms[0] - 1);
  const rows = cases.filter((c) => c.term >= start && c.term <= end);
  const stateRows = rows.filter((c) => c.state);
  return (
    <>
      <PageTitle title="The geography of review" eyebrow="States & terms">
        Follow where cases began and compare the Court across terms.
      </PageTitle>
      <Tabs
        items={["State impact map", "Term comparator", "Citation explorer"]}
      >
        {(selected) => (
          <>
            {selected === "State impact map" ? (
              <>
                <div className="filters">
                  <TermRange
                    start={start}
                    end={end}
                    onStart={setStart}
                    onEnd={setEnd}
                  />
                  <Select
                    label="Map metric"
                    value={metric}
                    options={["Cases reviewed", "Reversal rate (%)"]}
                    onChange={setMetric}
                  />
                  <Select
                    label="State drilldown"
                    value={state}
                    options={[
                      "All states",
                      ...counts(
                        cases.filter((c) => c.state),
                        (c) => c.state,
                      )
                        .map((s) => s.label)
                        .sort(),
                    ]}
                    onChange={setState}
                  />
                </div>
                <Notice>
                  States use Oyez case-location metadata where supplied. This is
                  not a complete measure of state impact.{" "}
                  {rows.length - stateRows.length} selected cases lack
                  state-location metadata.
                </Notice>
                <Panel title={metric}>
                  <StateMap
                    rows={stateRows}
                    onSelect={setState}
                    metric={metric}
                  />
                  <DataTable
                    rows={counts(stateRows, (c) => c.state).map((s) => ({
                      State: s.label,
                      Cases: s.value,
                      "Reversal rate": percent(
                        rate(stateRows.filter((c) => c.state === s.label)),
                      ),
                    }))}
                  />
                </Panel>
                <CaseList
                  rows={
                    state === "All states"
                      ? stateRows
                      : stateRows.filter((c) => c.state === state)
                  }
                />
              </>
            ) : null}
            {selected === "Term comparator" ? (
              <>
                <div className="filters">
                  <Select
                    label="Term A"
                    value={a}
                    options={manifest.terms}
                    onChange={(v) => setA(+v)}
                  />
                  <Select
                    label="Term B"
                    value={b}
                    options={manifest.terms}
                    onChange={(v) => setB(+v)}
                  />
                </div>
                <div className="two-columns">
                  {[a, b].map((year, i) => (
                    <Panel title={`${year} term`} key={i}>
                      <CaseMetrics
                        rows={cases.filter((c) => c.term === year)}
                      />
                      <Bars
                        data={counts(
                          cases.filter((c) => c.term === year),
                          (c) => c.issue,
                        )}
                      />
                      <h3>Vote splits</h3>
                      <Bars
                        data={counts(
                          cases.filter((c) => c.term === year),
                          (c) => c.split,
                        )}
                      />
                      <CaseList
                        rows={cases.filter((c) => c.term === year)}
                        limit={5}
                      />
                    </Panel>
                  ))}
                </div>
              </>
            ) : null}
            {selected === "Citation explorer" ? (
              <>
                <Notice>
                  The original citation network is curated, not an exhaustive
                  citation count or a determination that a case is still good
                  law.
                </Notice>
                <Panel title="Curated citation relationships">
                  <DataTable
                    rows={(catalog.Topics.EDGES_CN || []).map(
                      (v: string[]) => ({
                        Source: v[0],
                        Target: v[1],
                        Relationship: v[2],
                      }),
                    )}
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
