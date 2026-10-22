import { useEffect, useState } from "react";
import { useData } from "../context";
import {
  certProbability,
  predict,
  predictTrained,
  type Inputs,
  type ModelRelease,
} from "../lib/prediction";
import { percent } from "../lib/data";
import { loadJSON } from "../lib/data";
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
} from "../components/UI";
export default function Predictions() {
  const { catalog, cases, manifest } = useData();
  const constants = catalog["9_Predictions"];
  const [input, setInput] = useState<Inputs>({
    circuit: "9th Circuit",
    issue: "Criminal Procedure",
    party: "Federal Government",
    sg: false,
    split: false,
    conservatives: 6,
  });
  const [result, setResult] = useState<ReturnType<typeof predict> | null>(null);
  const [cert, setCert] = useState<number | null>(null);
  const [factors, setFactors] = useState<string[]>([]);
  const [justice, setJustice] = useState(catalog.currentJustices[0].short);
  const [replacement, setReplacement] = useState("Liberal");
  const [model, setModel] = useState("Statistical baseline");
  const [trained, setTrained] = useState<ModelRelease | null>(null);
  useEffect(() => {
    loadJSON<ModelRelease>("/data/model.json")
      .then(setTrained)
      .catch(() => {});
  }, []);
  const set = <K extends keyof Inputs>(key: K, value: Inputs[K]) =>
    setInput((v) => ({ ...v, [key]: value }));
  const removed = catalog.currentJustices.find((j) => j.short === justice)!;
  const delta =
    (replacement === "Conservative" ? 1 : 0) -
    (removed.lean === "Conservative" ? 1 : 0);
  const simulated = predict(
    {
      ...input,
      conservatives: Math.max(4, Math.min(7, input.conservatives + delta)),
    },
    catalog,
  );
  return (
    <>
      <PageTitle
        title="Explore the possibilities"
        eyebrow="Predictions & scenarios"
      >
        Experiment with a transparent statistical baseline and hypothetical
        Court compositions.
      </PageTitle>
      <Notice>
        The live site used this statistical baseline, not a trained ML model. It
        is an illustrative heuristic, not a validated forecast. Its justice
        estimates and vote splits should not be interpreted as calibrated
        probabilities.
      </Notice>
      <Tabs
        items={[
          "Case outcome",
          "Cert grant",
          "Docket watch",
          "Justice simulator",
          "Model performance",
          "Model training",
          "Model card",
        ]}
      >
        {(selected) => (
          <>
            {["Case outcome", "Cert grant", "Justice simulator"].includes(
              selected,
            ) ? (
              <div className="prediction-form">
                <Select
                  label="Circuit of origin"
                  value={input.circuit}
                  options={constants.CIRCUIT_OPTIONS}
                  onChange={(v) => set("circuit", v)}
                />
                <Select
                  label="Issue area"
                  value={input.issue}
                  options={constants.ISSUE_OPTIONS}
                  onChange={(v) => set("issue", v)}
                />
                <Select
                  label="Petitioner type"
                  value={input.party}
                  options={Object.keys(constants.PETITIONER_BONUS)}
                  onChange={(v) => set("party", v)}
                />
                <label className="field">
                  <span>Conservative justices: {input.conservatives}</span>
                  <input
                    type="range"
                    min="4"
                    max="7"
                    value={input.conservatives}
                    onChange={(e) => set("conservatives", +e.target.value)}
                  />
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={input.sg}
                    onChange={(e) => set("sg", e.target.checked)}
                  />
                  Solicitor General supporting petitioner
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={input.split}
                    onChange={(e) => set("split", e.target.checked)}
                  />
                  Circuit split exists
                </label>
              </div>
            ) : null}
            {selected === "Case outcome" ? (
              <>
                <Select
                  label="Calculation"
                  value={model}
                  options={
                    trained
                      ? ["Statistical baseline", "Experimental offline model"]
                      : ["Statistical baseline"]
                  }
                  onChange={(v) => {
                    setModel(v);
                    setResult(null);
                  }}
                />
                {model !== "Statistical baseline" ? (
                  <Notice>
                    The exported model underperformed the majority-class
                    reference on held-out cases. It is experimental; the
                    original statistical baseline remains the default. See Model
                    performance for metrics.
                  </Notice>
                ) : null}
                <button
                  className="button primary"
                  onClick={() =>
                    setResult(
                      model !== "Statistical baseline" && trained
                        ? predictTrained(input, catalog, trained)
                        : predict(input, catalog),
                    )
                  }
                >
                  Generate prediction →
                </button>
                {result ? (
                  <>
                    <div className="prediction-result">
                      <span>{model}</span>
                      <h2>
                        {result.p >= 0.65
                          ? "Likely reversed"
                          : result.p >= 0.55
                            ? "Lean reverse"
                            : result.p <= 0.35
                              ? "Likely affirmed"
                              : result.p <= 0.45
                                ? "Lean affirm"
                                : "Toss-up"}
                      </h2>
                      <strong>{percent(result.p)}</strong>
                      <p>Heuristic reversal probability</p>
                    </div>
                    <div className="two-columns">
                      <Panel title="Illustrative vote split distribution">
                        <Bars
                          data={Object.entries(result.splits).map(
                            ([label, value]) => ({ label, value: value * 100 }),
                          )}
                          format={(v) => `${v.toFixed(1)}%`}
                        />
                      </Panel>
                      <Panel title="Per-justice baseline estimates">
                        <Bars
                          data={result.justices.map((j) => ({
                            label: j.short,
                            value: j.value * 100,
                          }))}
                          format={(v) => `${v.toFixed(1)}%`}
                        />
                      </Panel>
                    </div>
                    <Panel title="Historical circuit baseline">
                      <Bars
                        data={Object.entries(
                          constants.CIRCUIT_REVERSAL_RATES,
                        ).map(([label, value]) => ({
                          label,
                          value: Number(value) * 100,
                        }))}
                        format={(v) => `${v.toFixed(0)}%`}
                      />
                    </Panel>
                  </>
                ) : null}
              </>
            ) : null}
            {selected === "Cert grant" ? (
              <>
                <Panel title="Additional favorable factors">
                  {Object.keys(constants.CERT_FACTORS)
                    .filter(
                      (f) =>
                        ![
                          "Circuit Split",
                          "Federal Gov't Petitioner (SG)",
                        ].includes(f),
                    )
                    .map((f) => (
                      <label className="check" key={f}>
                        <input
                          type="checkbox"
                          checked={factors.includes(f)}
                          onChange={(e) =>
                            setFactors((v) =>
                              e.target.checked
                                ? [...v, f]
                                : v.filter((x) => x !== f),
                            )
                          }
                        />
                        {f}
                      </label>
                    ))}
                </Panel>
                <button
                  className="button primary"
                  onClick={() =>
                    setCert(certProbability(input, factors, catalog))
                  }
                >
                  Estimate cert probability
                </button>
                {cert !== null ? (
                  <div className="prediction-result">
                    <h2>{percent(cert)}</h2>
                    <p>
                      Illustrative grant estimate; not a trained certiorari
                      model.
                    </p>
                  </div>
                ) : null}
              </>
            ) : null}
            {selected === "Docket watch" ? (
              <>
                <Notice>
                  The snapshot’s latest term is {manifest.terms[0]}. Cases
                  without a recorded decision may be pending or have incomplete
                  metadata; this is not a live docket feed.
                </Notice>
                <CaseList
                  rows={cases.filter(
                    (c) => c.term === manifest.terms[0] && !c.decided,
                  )}
                />
              </>
            ) : null}
            {selected === "Justice simulator" ? (
              <>
                <div className="filters">
                  <Select
                    label="Justice to replace"
                    value={justice}
                    options={catalog.currentJustices.map((j) => j.short)}
                    onChange={setJustice}
                  />
                  <Select
                    label="Replacement lean"
                    value={replacement}
                    options={["Liberal", "Moderate", "Conservative"]}
                    onChange={setReplacement}
                  />
                </div>
                <Metrics
                  items={[
                    {
                      label: "Original reversal estimate",
                      value: percent(predict(input, catalog).p),
                    },
                    {
                      label: "Hypothetical estimate",
                      value: percent(simulated.p),
                    },
                    {
                      label: "Change",
                      value: `${((simulated.p - predict(input, catalog).p) * 100).toFixed(1)} pp`,
                    },
                  ]}
                />
                <Notice>
                  This changes only the baseline’s conservative-justice count
                  (within its 4–7 supported range). It does not predict a
                  replacement’s actual vote or reverse historical holdings.
                </Notice>
                <Panel title="Actual close decisions for context">
                  <CaseList
                    rows={cases.filter(
                      (c) =>
                        c.split === "5-4" &&
                        c.votes.some((v) => v.name.includes(justice)),
                    )}
                    limit={8}
                  />
                </Panel>
              </>
            ) : null}
            {selected === "Model performance" ? (
              <Panel title="Performance and validation">
                <p>
                  No measured accuracy or calibration is claimed for the
                  statistical baseline. The migration tests compare its output
                  against the original Python function.
                </p>
                <OfflineModel />
              </Panel>
            ) : null}
            {selected === "Model training" ? (
              <Panel title="Offline model builds">
                <p>
                  Training runs outside visitor requests. The repository
                  includes an offline training/export command and a manual
                  GitHub Actions workflow. It produces a browser-readable model
                  with held-out metrics; no Python server is required for
                  inference.
                </p>
                <p>
                  Use the model card to distinguish that optional model from the
                  original statistical baseline. A newly trained model is not
                  automatically promoted without validation.
                </p>
                <OfflineModel />
              </Panel>
            ) : null}
            {selected === "Model card" ? (
              <Panel title="Statistical baseline model card">
                <DataTable
                  rows={[
                    {
                      Property: "Outcome",
                      Value:
                        "Weighted historical circuit/issue rates + petitioner bonus + SG/split flags + court composition",
                    },
                    {
                      Property: "Training",
                      Value:
                        "None; fixed parameters retained from the original app",
                    },
                    {
                      Property: "Output range",
                      Value: "5%–95%; illustrative, not calibrated",
                    },
                    {
                      Property: "Feature weights",
                      Value:
                        "Base .15; circuit .35; issue .25; petitioner additive; SG +.10; circuit split +.08; conservative count +.025 per seat above 5",
                    },
                    {
                      Property: "Use",
                      Value:
                        "Exploration and education; not legal advice or a reliable case forecast",
                    },
                    {
                      Property: "Data",
                      Value:
                        "Historical Oyez snapshot; issue classifications inferred",
                    },
                  ]}
                />
              </Panel>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
function OfflineModel() {
  const [meta, setMeta] = useState<any>(null);
  useEffect(() => {
    loadJSON<any>("/data/model.json")
      .then(setMeta)
      .catch(() => setMeta(false));
  }, []);
  return meta === null ? (
    <p>Checking model release…</p>
  ) : meta === false ? (
    <p className="muted">
      No optional trained model is included in this release.
    </p>
  ) : (
    <>
      <DataTable
        rows={Object.entries(meta.metrics).map(([Metric, Value]) => ({
          Metric,
          Value,
        }))}
      />
      <p>{meta.description}</p>
    </>
  );
}
