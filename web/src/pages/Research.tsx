import { useState } from "react";
import { useData } from "../context";
import {
  CaseList,
  Notice,
  PageTitle,
  Panel,
  Select,
  Tabs,
  DataTable,
} from "../components/UI";
import { CuratedRecord } from "./Topics";
import Chat from "../components/Chat";
export default function Research() {
  const { catalog, cases } = useData();
  const doctrines = catalog.Topics.DOCTRINES || {};
  const [doctrine, setDoctrine] = useState(Object.keys(doctrines)[0]);
  const [query, setQuery] = useState("");
  return (
    <>
      <PageTitle title="🔬 Research" eyebrow="Research">
        Ask grounded questions, trace doctrines, and inspect the underlying
        record.
      </PageTitle>
      <Tabs
        items={[
          "Ask the archive",
          "Doctrine evolution",
          "Congressional responses",
          "Justice simulator",
        ]}
      >
        {(selected) => (
          <>
            {selected === "Ask the archive" ? <Chat /> : null}
            {selected === "Doctrine evolution" ? (
              <>
                <Select
                  label="Doctrine"
                  value={doctrine}
                  options={Object.keys(doctrines)}
                  onChange={setDoctrine}
                />
                <Panel title={doctrine}>
                  <CuratedRecord value={doctrines[doctrine]} />
                </Panel>
              </>
            ) : null}
            {selected === "Congressional responses" ? (
              <>
                <Notice>
                  Curated congressional responses from the original app; not a
                  comprehensive legislative tracker.
                </Notice>
                <Panel title="Court and Congress">
                  <DataTable rows={catalog.Topics.CONGRESS_RESPONSES || []} />
                </Panel>
              </>
            ) : null}
            {selected === "Justice simulator" ? (
              <>
                <Notice>
                  Inspect actual close decisions before using the hypothetical
                  bench simulator on Predictions. A replacement justice’s
                  behavior cannot be inferred from an ideological label alone.
                </Notice>
                <label className="field">
                  <span>Filter close decisions</span>
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </label>
                <CaseList
                  rows={cases.filter(
                    (c) =>
                      c.split === "5-4" &&
                      c.name.toLowerCase().includes(query.toLowerCase()),
                  )}
                />
                <a
                  href="/Predictions?view=Justice+simulator"
                  className="button"
                >
                  Open hypothetical simulator →
                </a>
              </>
            ) : null}
          </>
        )}
      </Tabs>
    </>
  );
}
