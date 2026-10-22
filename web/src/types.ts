export interface Vote {
  name: string;
  vote: string;
  opinion?: string;
}
export interface CaseRecord {
  id: string;
  name: string;
  term: number;
  docket: string;
  issue: string;
  outcome: string;
  circuit: string;
  court: string;
  state: string;
  stateCode: string;
  argued: string;
  decided: string;
  split: string;
  majority: number;
  dissent: number;
  votes: Vote[];
  question: string;
  snippet: string;
  citation?: string;
  party: string;
  winner: string;
  audio: number;
  detail: boolean;
}
export interface Detail {
  id: string;
  name: string;
  facts: string;
  question: string;
  holding: string;
  description: string;
  firstParty: string;
  secondParty: string;
  lowerCourt: { name?: string };
  timeline: { event: string; dates: number[] }[];
  decisions: { description: string; winner: string; votes: Vote[] }[];
  opinions: {
    title: string;
    author: string;
    type?: { label?: string };
    url?: string;
  }[];
  advocates: { name: string; description: string }[];
  arguments: { id: string; title: string; transcriptAvailable: boolean }[];
  oyez: string;
  justia?: string;
}
export interface Argument {
  id: string;
  title: string;
  turns: { speaker: string; start: number; stop: number; text: string }[];
}
export interface Manifest {
  version: string;
  cases: number;
  details: number;
  arguments: number;
  terms: number[];
  latestDecision: string;
  source: string;
}
export interface Justice {
  id: string;
  name: string;
  lean: string;
  image: string;
  biography?: string;
  roles: {
    date_start?: number;
    date_end?: number;
    appointing_president?: string;
    role_title?: string;
  }[];
}
export interface CurrentJustice {
  short: string;
  full: string;
  lean: string;
  appointed_by: string;
  year_confirmed: number;
  seat: string;
}
// Curated legacy collections intentionally preserve heterogeneous row shapes.
export type Legacy = Record<string, any>;
export interface Catalog {
  History: Legacy;
  Analysis: Legacy;
  Topics: Legacy;
  People: Legacy;
  "8_Presidential_Legacy": Legacy;
  "13_Historical_Data": Legacy;
  "9_Predictions": Legacy;
  "10_Research": Legacy;
  "12_Geography": Legacy;
  legal: Legacy;
  currentJustices: CurrentJustice[];
  justices: Justice[];
  advocates: {
    advocate: string;
    appearances: number;
    wins: number;
    known_outcomes: number;
    win_rate: number;
  }[];
}
export interface SearchIndex {
  terms: string[];
  idf: number[];
  postings: [number[], number[]][];
  ids: string[];
  names?: string[];
  dockets?: string[];
}
export interface SearchResult {
  id: string;
  score: number;
}
