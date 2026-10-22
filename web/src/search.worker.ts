import { SearchEngine } from "./lib/search";
import type { SearchIndex } from "./types";
let engine: Promise<SearchEngine> | undefined;
self.onmessage = async ({
  data,
}: MessageEvent<{ id: number; query: string; limit: number }>) => {
  try {
    engine ||= fetch("/data/search.json")
      .then(async (r) => {
        if (!r.ok) throw new Error("Search index unavailable.");
        return new SearchEngine((await r.json()) as SearchIndex);
      })
      .catch((e) => {
        engine = undefined;
        throw e;
      });
    self.postMessage({
      id: data.id,
      results: (await engine).search(data.query, data.limit),
    });
  } catch (e) {
    self.postMessage({
      id: data.id,
      error: e instanceof Error ? e.message : "Search failed.",
    });
  }
};
