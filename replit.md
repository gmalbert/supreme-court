# Workspace

## Overview

pnpm workspace monorepo using TypeScript, plus a Streamlit Python app for SCOTUS case visualization.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)
- **Python version**: 3.11
- **Streamlit app**: SCOTUS Case Visualizer (entry: `streamlit-app/cases.py`)

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally
- `streamlit run streamlit-app/cases.py --server.port 5000` — run the SCOTUS visualizer

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.

## Streamlit App Structure

```
streamlit-app/
├── cases.py                      # Main entry — case journey diagram + justice votes
├── .streamlit/config.toml        # Server config (port 5000, CORS/XSRF disabled for proxy)
├── utils/
│   ├── oyez_api.py               # Oyez API client (free, no key required)
│   └── charts.py                 # Plotly chart builders (journey diagram, voting, trends)
└── pages/
    ├── 1_Search_Cases.py         # Search by case name across terms
    ├── 2_Justice_Voting.py       # Justice voting patterns per case
    ├── 3_Timeline_Browser.py     # Multi-term timeline + issue area charts
    ├── 4_Statistics.py           # Dispositions, issue areas, case listing
    ├── 5_Justice_Career.py       # Full career overview: votes, dissent rate, issue areas
    ├── 6_Court_Comparison.py     # Side-by-side circuit court reversal/affirmance analysis
    ├── 7_Issue_Area_Decisions.py # Browse all decisions in a legal domain with drilldown
    ├── 8_Chief_Justice_Eras.py   # Warren/Burger/Rehnquist/Roberts court era comparisons
    └── 9_Landmark_Cases.py       # Curated landmark cases with journey + votes
```

### Data Source
- **Oyez API** (https://api.oyez.org) — free, no API key, covers cases from ~1792 onward with rich metadata, lower court info, justice votes, and oral argument audio links.

### Journey Diagram Design
- Circles are size 180, positioned in the left column (x=2 in data space)
- Court name labels are positioned in the right column (x=5.5) using data coordinates so they never overlap circles
- Short bold labels inside circles: "Trial Court", "Appeals Court", "SCOTUS"
