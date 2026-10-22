import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { SearchResult } from "../types";
export function SearchBox({
  initial = "",
  onSearch,
  busy = false,
  compact = false,
}: {
  initial?: string;
  onSearch?: (query: string) => void;
  busy?: boolean;
  compact?: boolean;
}) {
  const [query, setQuery] = useState(initial);
  const navigate = useNavigate();
  useEffect(() => setQuery(initial), [initial]);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      if (onSearch) onSearch(query.trim());
      else navigate(`/Cases?q=${encodeURIComponent(query.trim())}`);
    }
  }
  return (
    <form
      className={`search-form ${compact ? "compact" : ""}`}
      onSubmit={submit}
    >
      <label htmlFor="case-query">
        Find a case or explore a legal question
      </label>
      <div className="search-input">
        <input
          id="case-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Try ‘student speech in public schools’"
          maxLength={1000}
        />
        <button type="submit" disabled={busy || !query.trim()}>
          {busy ? "Searching…" : "Search cases →"}
        </button>
      </div>
      <p>Search across names, facts, questions, and holdings.</p>
    </form>
  );
}
export function useSearch() {
  const worker = useRef<Worker | null>(null);
  const sequence = useRef(0);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => () => worker.current?.terminate(), []);
  function search(query: string) {
    if (!worker.current) {
      worker.current = new Worker(
        new URL("../search.worker.ts", import.meta.url),
        { type: "module" },
      );
      worker.current.onmessage = ({ data }) => {
        if (data.id !== sequence.current) return;
        setBusy(false);
        setError(data.error || "");
        setResults(data.results || []);
      };
      worker.current.onerror = () => {
        setBusy(false);
        setError("Search could not start. Refresh the page and try again.");
      };
    }
    setBusy(true);
    setError("");
    worker.current.postMessage({ id: ++sequence.current, query, limit: 100 });
  }
  return { results, busy, error, search };
}
