import type { Catalog } from "../types";
export interface Inputs {
  circuit: string;
  issue: string;
  party: string;
  sg: boolean;
  split: boolean;
  conservatives: number;
}
export interface PortableModel {
  categories: string[][];
  mean: number[];
  scale: number[];
  classes: (string | number)[];
  coef: number[][];
  intercept: number[];
}
export interface ModelRelease {
  description: string;
  metrics: Record<string, unknown>;
  outcome: PortableModel;
  split: PortableModel | null;
  justices: Record<string, PortableModel>;
  referenceTerm: number;
  fixtures: {
    input: {
      circuit: string;
      issue: string;
      conservatives: number;
      term: number;
    };
    probability: number;
  }[];
}
export function infer(
  model: PortableModel,
  input: {
    circuit: string;
    issue: string;
    conservatives: number;
    term: number;
  },
) {
  const features = [
    ...model.categories[0].map((v) => Number(v === input.circuit)),
    ...model.categories[1].map((v) => Number(v === input.issue)),
    (input.conservatives - model.mean[0]) / model.scale[0],
    ((input.term - 2005) / 10 - model.mean[1]) / model.scale[1],
  ];
  const logits = model.coef.map((row, i) =>
    row.reduce((sum, w, j) => sum + w * features[j], model.intercept[i]),
  );
  if (logits.length === 1) {
    const p = 1 / (1 + Math.exp(-logits[0]));
    return [1 - p, p];
  }
  const max = Math.max(...logits),
    values = logits.map((v) => Math.exp(v - max)),
    total = values.reduce((a, b) => a + b, 0);
  return values.map((v) => v / total);
}
export function predictTrained(
  input: Inputs,
  catalog: Catalog,
  model: ModelRelease,
) {
  const x = { ...input, term: model.referenceTerm };
  let p = infer(model.outcome, x)[model.outcome.classes.indexOf(1)];
  if (input.sg) p = Math.min(0.93, p + 0.07);
  if (input.split) p = Math.min(0.93, p + 0.05);
  const splits = model.split
    ? Object.fromEntries(
        model.split.classes.map((c, i) => [
          String(c),
          infer(model.split!, x)[i],
        ]),
      )
    : predict(input, catalog).splits;
  const justices = catalog.currentJustices.map((j) => {
    const m = model.justices[j.short];
    return { ...j, value: m ? infer(m, x)[m.classes.indexOf(1)] : 0.5 };
  });
  return { p, splits, justices };
}
const clamp = (v: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, v));
export function predict(input: Inputs, catalog: Catalog) {
  const constants = catalog["9_Predictions"];
  const p = clamp(
    0.62 * 0.15 +
      (constants.CIRCUIT_REVERSAL_RATES[input.circuit] ?? 0.62) * 0.35 +
      (constants.ISSUE_REVERSAL_RATES[input.issue] ?? 0.62) * 0.25 +
      (constants.PETITIONER_BONUS[input.party] ?? 0) +
      (input.sg ? 0.1 : 0) +
      (input.split ? 0.08 : 0) +
      (input.conservatives - 5) * 0.025,
    0.05,
    0.95,
  );
  const splits: Record<string, number> = {
    "9-0": 0.08,
    "8-1": 0.1,
    "7-2": 0.15,
    "6-3": p * 0.28 + (1 - p) * 0.2,
    "5-4": p * 0.39 + (1 - p) * 0.47,
  };
  const sum = Object.values(splits).reduce((a, b) => a + b, 0);
  for (const key in splits) splits[key] /= sum;
  const adjustment = (input.conservatives - 5) * 0.025;
  const justices = catalog.currentJustices.map((j) => {
    const rates = constants._JUST_TEND?.[j.short] || {};
    let value = (rates[input.issue] ?? rates.default ?? 0.6) + adjustment * 0.3;
    if (j.lean === "Liberal") value = 1 - (1 - value) * (1 + adjustment * 0.2);
    value = clamp(value, 0.1, 0.9);
    if (p < 0.5) value = 1 - value;
    return { ...j, value };
  });
  return { p, splits, justices };
}
export function certProbability(
  input: Inputs,
  flags: string[],
  catalog: Catalog,
) {
  const c = catalog["9_Predictions"];
  let base = c.ISSUE_CERT_RATES[input.issue] ?? 0.015;
  if (input.sg) base += 0.038;
  if (input.split) base += 0.045;
  for (const flag of new Set(flags)) base += c.CERT_FACTORS[flag] ?? 0;
  return clamp(base * (c.CIRCUIT_CERT_MULT[input.circuit] ?? 1), 0.005, 0.85);
}
