import type { CaseRecord, Catalog, Detail, Manifest } from "../types";
export function monthDay(date = new Date()) {
  return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
const cache = new Map<string, Promise<unknown>>();
export function loadJSON<T>(path: string): Promise<T> {
  let request = cache.get(path);
  if (!request) {
    request = fetch(path)
      .then(async (r) => {
        if (!r.ok || !r.headers.get("content-type")?.includes("json"))
          throw new Error(
            `Could not load ${path}. Please retry or refresh the data release.`,
          );
        return r.json();
      })
      .catch((error) => {
        cache.delete(path);
        throw error;
      });
    cache.set(path, request);
  }
  return request as Promise<T>;
}
export const loadInitial = () =>
  Promise.all([
    loadJSON<CaseRecord[]>("/data/cases.json"),
    loadJSON<Catalog>("/data/catalog.json"),
    loadJSON<Manifest>("/data/manifest.json"),
  ]);
export const detailPath = (id: string) =>
  "/data/cases/" + id.split("/").map(encodeURIComponent).join("/") + ".json";
export const loadDetail = (id: string) => loadJSON<Detail>(detailPath(id));
export const caseURL = (id: string) =>
  "/case/" + id.split("/").map(encodeURIComponent).join("/");
export const isReverse = (c: CaseRecord) => /revers|vacat/i.test(c.outcome);
export const isAffirm = (c: CaseRecord) => /affirm/i.test(c.outcome);
export const rate = (rows: CaseRecord[]) => {
  const known = rows.filter((c) => isReverse(c) || isAffirm(c));
  return known.length ? rows.filter(isReverse).length / known.length : null;
};
export const percent = (n: number | null) =>
  n === null ? "—" : `${(n * 100).toFixed(1)}%`;
export function counts<T>(rows: T[], key: (r: T) => string) {
  const groups = new Map<string, number>();
  for (const r of rows) {
    const k = key(r) || "Unknown";
    groups.set(k, (groups.get(k) || 0) + 1);
  }
  return [...groups]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}
export function downloadCSV(name: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const columns = Object.keys(rows[0]);
  const cell = (value: unknown) => {
    let s =
      value == null
        ? ""
        : typeof value === "object"
          ? JSON.stringify(value)
          : String(value);
    if (/^[=+@\-\t\r]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  };
  const blob = new Blob(
    [
      "\ufeff" +
        [
          columns.map(cell).join(","),
          ...rows.map((r) => columns.map((k) => cell(r[k])).join(",")),
        ].join("\r\n"),
    ],
    { type: "text/csv;charset=utf-8" },
  );
  const a = document.createElement("a");
  const url = URL.createObjectURL(blob);
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function partyType(party: string) {
  if (
    /united states|commissioner|secretary|department|federal|internal revenue/i.test(
      party,
    )
  )
    return "Federal Government";
  if (
    /state|california|texas|new york|city of|county|board|commonwealth|people|illinois|florida|ohio|michigan|virginia/i.test(
      party,
    )
  )
    return "State / Local Government";
  if (
    /inc\.|corp|company|co\.|llc|bank|association|union|railroad/i.test(party)
  )
    return "Organization";
  return "Individual / Other";
}
export function agreement(rows: CaseRecord[], names: string[]) {
  return names.map((a) =>
    names.map((b) => {
      let total = 0,
        same = 0;
      for (const c of rows) {
        const av = c.votes.find((v) => v.name === a),
          bv = c.votes.find((v) => v.name === b);
        const side = (v: string) =>
          /^(majority|concurrence)$/i.test(v)
            ? 1
            : /^(dissent|minority)$/i.test(v)
              ? 0
              : -1;
        if (av && bv && side(av.vote) >= 0 && side(bv.vote) >= 0) {
          total++;
          if (side(av.vote) === side(bv.vote)) same++;
        }
      }
      return { value: total ? same / total : null, total };
    }),
  );
}
