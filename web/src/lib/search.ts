import type { SearchIndex, SearchResult } from "../types";
export function tokens(query: string): string[] {
  return (
    query
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .match(/\b\w\w+\b/g) || []
  );
}
export function expandQuery(query: string) {
  let q = query;
  if (/\b(lgbtq?|queer)\b/i.test(q))
    q +=
      " gay lesbian bisexual transgender homosexual same-sex marriage sexual orientation gender identity";
  if (
    /speech|expression|first amendment/i.test(q) &&
    /school|student|campus/i.test(q)
  )
    q +=
      " Tinker Bethel Hazelwood Morse Mahanoy student speech First Amendment school-sponsored off-campus expression armband newspaper censorship";
  return q;
}
export class SearchEngine {
  private vocabulary: Map<string, number>;
  private nameFrequency = new Map<string, number>();
  private nameTokens: string[][];
  constructor(private index: SearchIndex) {
    this.vocabulary = new Map(index.terms.map((t, i) => [t, i]));
    this.nameTokens = (index.names || []).map((n) => tokens(n));
    for (const parts of this.nameTokens)
      for (const word of new Set(parts))
        this.nameFrequency.set(word, (this.nameFrequency.get(word) || 0) + 1);
  }
  search(query: string, limit = 20): SearchResult[] {
    const frequencies = new Map<number, number>();
    for (const t of tokens(expandQuery(query))) {
      const i = this.vocabulary.get(t);
      if (i !== undefined) frequencies.set(i, (frequencies.get(i) || 0) + 1);
    }
    const weights = [...frequencies].map(([i, n]) => [
      i,
      (1 + Math.log(n)) * this.index.idf[i],
    ]);
    const norm = Math.sqrt(weights.reduce((sum, [, w]) => sum + w * w, 0));
    if (!norm) return [];
    const scores = new Float64Array(this.index.ids.length);
    for (const [i, w] of weights) {
      const [docs, values] = this.index.postings[i];
      for (let j = 0; j < docs.length; j++)
        scores[docs[j]] += (w / norm) * values[j];
    }
    // Name lookups should not lose to short generic fact summaries. Only original
    // query words can pin a name; topic-expansion vocabulary cannot.
    const original = tokens(query),
      normalized = original.join(" ");
    const ignored = new Set([
      "what",
      "which",
      "who",
      "when",
      "where",
      "wrote",
      "about",
      "tell",
      "case",
      "cases",
      "court",
      "supreme",
      "school",
      "schools",
      "decision",
      "split",
      "opinion",
      "hold",
      "holding",
      "united",
      "states",
      "board",
      "education",
      "rights",
      "speech",
    ]);
    for (let i = 0; i < this.nameTokens.length; i++) {
      const name = this.nameTokens[i].join(" ");
      if (name === normalized || (name.length > 8 && normalized.includes(name)))
        scores[i] += 100;
      else {
        const distinct = original.filter(
          (t) =>
            !ignored.has(t) &&
            t.length > 3 &&
            (this.nameFrequency.get(t) || Infinity) <= 8,
        );
        const matches = distinct.filter((t) => this.nameTokens[i].includes(t));
        if (matches.length) scores[i] += matches.length * 2;
      }
      if (this.index.dockets?.[i] === query.trim()) scores[i] += 100;
    }
    return Array.from(scores, (score, i) => ({ id: this.index.ids[i], score }))
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
  }
}
