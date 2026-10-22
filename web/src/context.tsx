import { createContext, useContext, useState, type ReactNode } from "react";
import type { CaseRecord, Catalog, Manifest } from "./types";
interface AppData {
  cases: CaseRecord[];
  catalog: Catalog;
  manifest: Manifest;
  watchlist: string[];
  toggleSaved: (id: string) => void;
}
const Context = createContext<AppData | null>(null);
export function DataProvider({
  data,
  children,
}: {
  data: [CaseRecord[], Catalog, Manifest];
  children: ReactNode;
}) {
  const [watchlist, setWatchlist] = useState<string[]>(() => {
    try {
      const data = JSON.parse(
        localStorage.getItem("supreme-scrutiny.saved.v1") || "[]",
      );
      return Array.isArray(data)
        ? data.filter((v) => typeof v === "string")
        : [];
    } catch {
      return [];
    }
  });
  const toggleSaved = (id: string) =>
    setWatchlist((previous) => {
      const next = previous.includes(id)
        ? previous.filter((v) => v !== id)
        : [...previous, id];
      try {
        localStorage.setItem("supreme-scrutiny.saved.v1", JSON.stringify(next));
      } catch {
        /* Private browsing can disable persistence. */
      }
      return next;
    });
  return (
    <Context.Provider
      value={{
        cases: data[0],
        catalog: data[1],
        manifest: data[2],
        watchlist,
        toggleSaved,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useData() {
  const data = useContext(Context);
  if (!data) throw new Error("Application data is unavailable.");
  return data;
}
