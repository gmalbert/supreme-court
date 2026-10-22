import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useData } from "../context";
import { useSearch } from "./SearchBox";
import { CaseList, Notice, Panel } from "./UI";
import { caseURL } from "../lib/data";
interface Message {
  role: "user" | "assistant";
  content: string;
  ids?: string[];
}
export default function Chat() {
  const { cases } = useData();
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [answering, setAnswering] = useState(false);
  const [available, setAvailable] = useState(false);
  const { results, busy, error: searchError, search } = useSearch();
  const request = useRef(0);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setAvailable(d.chat === true))
      .catch(() => setAvailable(false));
    return () => abort.current?.abort();
  }, []);
  const evidence = results
    .map((r) => cases.find((c) => c.id === r.id)!)
    .filter(Boolean)
    .slice(0, 8);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    request.current++;
    abort.current?.abort();
    setPending(query.trim());
    setError("");
    const prior =
      messages
        .at(-1)
        ?.ids?.map((id) => cases.find((c) => c.id === id)?.name)
        .filter(Boolean)
        .slice(0, 3)
        .join(" ") || "";
    search(
      query.trim() +
        (/^(it|they|what about|how about|compare|and |which|who)/i.test(
          query.trim(),
        )
          ? " " + prior
          : ""),
    );
  }
  async function ask() {
    if (!pending || !evidence.length) return;
    const sequence = ++request.current;
    const controller = new AbortController();
    abort.current = controller;
    setAnswering(true);
    setError("");
    try {
      const history = messages
        .slice(-10)
        .map(({ role, content }) => ({
          role,
          content: content.slice(0, 3000),
        }));
      while (
        history.length &&
        new TextEncoder().encode(JSON.stringify(history)).length > 18000
      )
        history.shift();
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: pending,
          caseIds: evidence.map((c) => c.id),
          history,
        }),
        signal: controller.signal,
      });
      const body = await response.json();
      if (!response.ok)
        throw new Error(
          body.error || "The assistant is unavailable. Please try again later.",
        );
      if (sequence === request.current) {
        setMessages((m) => [
          ...m,
          { role: "user", content: pending },
          {
            role: "assistant",
            content: body.answer,
            ids: body.sources.map((s: { id: string }) => s.id),
          },
        ]);
        setQuery("");
        setPending("");
      }
    } catch (e) {
      if (
        sequence === request.current &&
        !(e instanceof DOMException && e.name === "AbortError")
      )
        setError(e instanceof Error ? e.message : "Could not load an answer.");
    } finally {
      if (sequence === request.current) setAnswering(false);
    }
  }
  return (
    <>
      <Notice>
        Answers are grounded in retrieved case records. Verify citations and
        current law with the original sources. This tool provides legal
        information, not legal advice.
      </Notice>
      <div className="conversation" aria-live="polite">
        {messages.map((m, i) => (
          <article className={`message ${m.role}`} key={i}>
            <span className="eyebrow">
              {m.role === "user" ? "You" : "Archive assistant"}
            </span>
            <div className="long-text">{m.content}</div>
            {m.ids ? (
              <div className="source-links">
                {m.ids.map((id) => (
                  <Link key={id} to={caseURL(id)}>
                    {cases.find((c) => c.id === id)?.name || id} ↗
                  </Link>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
      <form className="search-form compact" onSubmit={submit}>
        <label htmlFor="research-question">Ask a question or follow up</label>
        <textarea
          id="research-question"
          maxLength={2000}
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="How has the Court approached student speech?"
        />
        <div className="actions">
          <button
            type="submit"
            className="button primary"
            disabled={busy || answering || !query.trim()}
          >
            {busy ? "Finding evidence…" : "Find supporting cases"}
          </button>
          {messages.length ? (
            <button
              type="button"
              className="button"
              onClick={() => {
                request.current++;
                abort.current?.abort();
                setMessages([]);
                setPending("");
                setAnswering(false);
              }}
            >
              Clear conversation
            </button>
          ) : null}
        </div>
      </form>
      {error || searchError ? (
        <Notice error>{error || searchError}</Notice>
      ) : null}
      {pending && !busy ? (
        <Panel title={`Evidence for “${pending}”`}>
          <CaseList rows={evidence} limit={8} />
          {evidence.length ? (
            <div className="actions">
              <button
                className="button primary"
                disabled={!available || answering}
                onClick={ask}
              >
                {answering ? "Preparing answer…" : "Ask AI using these sources"}
              </button>
              {!available ? (
                <p className="muted">
                  The AI assistant is not enabled on this deployment. Case
                  search and source records remain available.
                </p>
              ) : null}
            </div>
          ) : null}
        </Panel>
      ) : null}
    </>
  );
}
