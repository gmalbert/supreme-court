import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { SearchEngine } from "../src/lib/search";
import {
  certProbability,
  infer,
  predict,
  type ModelRelease,
} from "../src/lib/prediction";
import { agreement, rate, monthDay } from "../src/lib/data";
import type { CaseRecord, Catalog, SearchIndex } from "../src/types";
const read = <T>(p: string) =>
  JSON.parse(readFileSync(resolve("public/data", p), "utf8")) as T;
const cases = read<CaseRecord[]>("cases.json");
const catalog = read<Catalog>("catalog.json");
const engine = new SearchEngine(read<SearchIndex>("search.json"));
const names = (query: string) =>
  engine.search(query, 10).map((r) => cases.find((c) => c.id === r.id)!.name);
describe("real exported case corpus", () => {
  it("retains every case, stable IDs, votes, and known case detail", () => {
    expect(cases.length).toBeGreaterThan(8000);
    expect(new Set(cases.map((c) => c.id)).size).toBe(cases.length);
    const c = cases.find((c) => c.name === "Obergefell v. Hodges")!;
    expect(c).toBeTruthy();
    expect(c.votes.length).toBe(9);
    const d = read<any>("cases/" + c.id + ".json");
    expect(d.holding).toMatch(/marriage/i);
    expect(d.id).toBe(c.id);
  });
  it("finds named cases rather than generic text matches", () => {
    expect(names("What was the decision split in Pickering?")[0]).toMatch(
      /Pickering v\./,
    );
    expect(names("Obergefell v. Hodges")[0]).toBe("Obergefell v. Hodges");
    expect(names("Who wrote the Pike opinion?")[0]).toBe(
      "Pike v. Bruce Church, Inc.",
    );
  });
  it("retrieves the school speech landmarks in the top ten", () => {
    const result = names(
      "How has the Court treated student expression at school?",
    ).join("\n");
    for (const expected of [
      "Tinker",
      "Bethel",
      "Hazelwood",
      "Morse",
      "Mahanoy",
    ])
      expect(result).toContain(expected);
  });
  it("handles empty and unknown queries", () => {
    expect(engine.search("")).toEqual([]);
    expect(engine.search("zzxyzzqnotaword")).toEqual([]);
  });
  it("preserves curated collections rather than executing legacy pages", () => {
    expect(catalog.History.CONFIRMATIONS.length).toBeGreaterThan(20);
    expect(catalog.People.AMICUS_ORGS.length).toBeGreaterThan(10);
    expect(catalog.Topics.CONGRESS_RESPONSES.length).toBeGreaterThan(5);
    expect(catalog.History.CJ_ERAS.length).toBeGreaterThan(10);
  });
});
describe("browser calculations", () => {
  it("uses the visitor's calendar day for anniversaries", () => {
    expect(monthDay(new Date(2026, 9, 21, 23, 30))).toBe("10-21");
  });
  it("matches the live statistical baseline 68.4% and normalized splits", () => {
    const r = predict(
      {
        circuit: "9th Circuit",
        issue: "Criminal Procedure",
        party: "Federal Government",
        sg: false,
        split: false,
        conservatives: 6,
      },
      catalog,
    );
    expect(r.p).toBeCloseTo(0.684, 8);
    expect(Object.values(r.splits).reduce((a, b) => a + b, 0)).toBeCloseTo(
      1,
      10,
    );
    expect(r.justices).toHaveLength(9);
  });
  it("bounds predictions and cert estimates across the input domain", () => {
    for (const circuit of catalog["9_Predictions"].CIRCUIT_OPTIONS)
      for (const issue of catalog["9_Predictions"].ISSUE_OPTIONS) {
        const input = {
          circuit,
          issue,
          party: "Federal Government",
          sg: true,
          split: true,
          conservatives: 7,
        };
        const p = predict(input, catalog).p;
        expect(p).toBeGreaterThanOrEqual(0.05);
        expect(p).toBeLessThanOrEqual(0.95);
        expect(
          certProbability(
            input,
            Object.keys(catalog["9_Predictions"].CERT_FACTORS),
            catalog,
          ),
        ).toBeLessThanOrEqual(0.85);
      }
  });
  it("does not count unknown outcomes as affirmances", () => {
    expect(rate([{ outcome: "Unknown" } as CaseRecord])).toBeNull();
    expect(
      rate([
        { outcome: "Reversed" } as CaseRecord,
        { outcome: "Affirmed" } as CaseRecord,
        { outcome: "Unknown" } as CaseRecord,
      ]),
    ).toBe(0.5);
  });
  it("uses shared votes as the agreement denominator and excludes recusals", () => {
    const rows = [
      {
        votes: [
          { name: "A", vote: "majority" },
          { name: "B", vote: "concurrence" },
        ],
      },
      {
        votes: [
          { name: "A", vote: "dissent" },
          { name: "B", vote: "majority" },
        ],
      },
      {
        votes: [
          { name: "A", vote: "recusal" },
          { name: "B", vote: "majority" },
        ],
      },
    ] as CaseRecord[];
    expect(agreement(rows, ["A", "B"])[0][1]).toEqual({ value: 0.5, total: 2 });
  });
  it("matches Python sklearn inference fixtures without a Python runtime", () => {
    const model = read<ModelRelease>("model.json");
    for (const f of model.fixtures) {
      const p = infer(model.outcome, f.input)[model.outcome.classes.indexOf(1)];
      expect(p).toBeCloseTo(f.probability, 10);
    }
    expect(model.metrics.held_out_cases).toBeGreaterThan(0);
  });
});
