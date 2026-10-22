import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useData } from "../context";
import { SearchBox, useSearch } from "../components/SearchBox";
import {
  CaseList,
  CaseMetrics,
  Notice,
  PageTitle,
  Panel,
  Select,
  Tabs,
  TermRange,
  Trend,
} from "../components/UI";
import { counts } from "../lib/data";
export default function Cases() {
  const { cases, manifest } = useData();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const legacyCase = params.get("case") || "";
  const navigate = useNavigate();
  useEffect(() => {
    if (!legacyCase) return;
    const record = cases.find(
      (c) =>
        c.name === legacyCase ||
        c.id === legacyCase ||
        `https://api.oyez.org/cases/${c.id}` === legacyCase,
    );
    if (record)
      navigate(
        "/case/" + record.id.split("/").map(encodeURIComponent).join("/"),
        { replace: true },
      );
  }, [legacyCase, cases, navigate]);
  const [start, setStart] = useState(1955);
  const [end, setEnd] = useState(manifest.terms[0]);
  const [issue, setIssue] = useState("All issues");
  const [term, setTerm] = useState(String(manifest.terms[0]));
  const [savedOnly, setSavedOnly] = useState(false);
  const { watchlist } = useData();
  const { results, busy, error, search } = useSearch();
  useEffect(() => {
    if (q && !legacyCase) {
      search(q);
      if (!params.get("view"))
        setParams(
          (p) => {
            p.set("view", "Find by description");
            return p;
          },
          { replace: true },
        );
    }
  }, [q]);
  const byId = useMemo(() => new Map(cases.map((c) => [c.id, c])), [cases]);
  const filtered = useMemo(
    () =>
      cases.filter(
        (c) =>
          c.term >= start &&
          c.term <= end &&
          (issue === "All issues" || c.issue === issue) &&
          (!savedOnly || watchlist.includes(c.id)),
      ),
    [cases, start, end, issue, savedOnly, watchlist],
  );
  const ranked = q
    ? results.map((r) => byId.get(r.id)!).filter(Boolean)
    : [...cases].sort((a, b) => b.term - a.term);
  const issues = [
    "All issues",
    ...counts(cases, (c) => c.issue)
      .map((v) => v.label)
      .sort(),
  ];
  function setQuery(query: string) {
    setParams((p) => {
      p.set("q", query);
      return p;
    });
  }
  return (
    <>
      <PageTitle title="⚖️ Cases" eyebrow="Cases & arguments">
        Explore decisions, read the record, and follow the questions before the
        Court.
      </PageTitle>
      <Tabs
        items={[
          "Search cases",
          "Find by description",
          "Timeline browser",
          "Oral arguments",
          "Term calendar",
        ]}
      >
        {(selected) => (
          <>
            {selected === "Find by description" ||
            selected === "Search cases" ? (
              <>
                <p>
                  {selected === "Search cases"
                    ? "Search by case name across recent terms (2000–present)."
                    : "Describe a legal situation in plain language to find relevant Supreme Court cases."}
                </p>
                <SearchBox
                  compact
                  initial={q}
                  onSearch={setQuery}
                  busy={busy}
                  description={selected === "Find by description"}
                />
                {error ? <Notice error>{error}</Notice> : null}
                {q ? (
                  <div className="filters">
                    <Select
                      label="Issue area"
                      value={issue}
                      options={issues}
                      onChange={setIssue}
                    />
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={savedOnly}
                        onChange={(e) => setSavedOnly(e.target.checked)}
                      />
                      Saved cases only
                    </label>
                  </div>
                ) : null}
                {q ? (
                  <>
                    <p className="muted" aria-live="polite">
                      {busy
                        ? "Searching the archive…"
                        : q
                          ? `${results.length} ranked results for “${q}”`
                          : `${cases.length.toLocaleString()} cases · newest terms first`}
                    </p>
                    <CaseList
                      limit={Math.max(
                        3,
                        Math.min(20, Number(params.get("limit")) || 20),
                      )}
                      rows={(selected === "Search cases" && q
                        ? cases.filter((c) =>
                            `${c.name} ${c.docket}`
                              .toLowerCase()
                              .includes(q.toLowerCase()),
                          )
                        : ranked
                      ).filter(
                        (c) =>
                          (issue === "All issues" || c.issue === issue) &&
                          (!savedOnly || watchlist.includes(c.id)),
                      )}
                    />
                  </>
                ) : null}
              </>
            ) : null}
            {selected === "Timeline browser" ? (
              <>
                <div className="filters">
                  <TermRange
                    start={start}
                    end={end}
                    onStart={setStart}
                    onEnd={setEnd}
                  />
                  <Select
                    label="Issue area"
                    value={issue}
                    options={issues}
                    onChange={setIssue}
                  />
                </div>
                <CaseMetrics rows={filtered} />
                <Panel title="Cases by term">
                  <Trend
                    data={counts(filtered, (c) => String(c.term))
                      .map((v) => ({ year: +v.label, value: v.value }))
                      .sort((a, b) => a.year - b.year)}
                  />
                </Panel>
                <CaseList
                  rows={[...filtered].sort((a, b) => b.term - a.term)}
                />
              </>
            ) : null}
            {selected === "Oral arguments" || selected === "Term calendar" ? (
              <>
                <div className="filters">
                  <Select
                    label="Term"
                    value={term}
                    options={manifest.terms}
                    onChange={setTerm}
                  />
                </div>
                <Panel
                  title={
                    selected === "Oral arguments"
                      ? "Argument sessions"
                      : "Term docket"
                  }
                >
                  <p className="muted">
                    {selected === "Oral arguments"
                      ? "Open a case to read speaker-attributed transcripts and follow the original audio link."
                      : "Snapshot of scheduled arguments and recorded decisions; refreshes follow the data release schedule."}
                  </p>
                  <CaseList
                    rows={cases
                      .filter(
                        (c) =>
                          c.term === +term &&
                          (selected !== "Oral arguments" || c.audio > 0),
                      )
                      .sort((a, b) =>
                        (a.argued || "9999").localeCompare(b.argued || "9999"),
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
