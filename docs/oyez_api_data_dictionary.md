# Oyez API — Data Dictionary

**Base URL:** `https://api.oyez.org`  
**Authentication:** None required  
**Format:** JSON  
**Rate limiting:** No documented limit; the app adds small `time.sleep` calls between batch requests as a courtesy  
**Local cache:** All responses are cached under `data_files/oyez_data/` via `utils/local_data.fetch_oyez()`. Cache is checked before any live call.

> All dates in the API are **Unix timestamps** (seconds since epoch, integer). Use
> `datetime.date.fromtimestamp(ts)` to convert. A value of `0` means "current /
> still serving" for `date_end` fields on roles.

---

## Table of Contents

1. [Endpoint Overview](#endpoint-overview)
2. [GET /cases — Term List](#get-cases--term-list)
3. [GET /cases/{term}/{docket} — Case Detail](#get-casestermdocket--case-detail)
   - [Top-level fields](#case-detail-top-level-fields)
   - [timeline\[\]](#timeline-array)
   - [lower_court](#lower_court-object)
   - [citation](#citation-object)
   - [decisions\[\]](#decisions-array)
   - [decisions[].votes\[\]](#decisionsvotes-array)
   - [heard_by\[\] / decided_by](#heard_by--decided_by)
   - [advocates\[\]](#advocates-array)
   - [oral_argument_audio\[\]](#oral_argument_audio-array)
   - [opinion_announcement\[\]](#opinion_announcement-array)
   - [written_opinion\[\]](#written_opinion-array)
4. [GET /case_media/oral_argument_audio/{id} — Oral Argument Detail](#get-case_mediaoral_argument_audioid--oral-argument-detail)
   - [transcript](#transcript-object)
   - [transcript.sections\[\]](#transcriptsections-array)
   - [sections[].turns\[\]](#sectionsturnsturn-object)
5. [GET /case_media/opinion_announcement_audio/{id} — Opinion Announcement Detail](#get-case_mediaopinion_announcement_audioid--opinion-announcement-detail)
6. [GET /case_document/written_opinion/{id} — Written Opinion Detail](#get-case_documentwritten_opinionid--written-opinion-detail)
7. [GET /justices — Justices List](#get-justices--justices-list)
8. [GET /people/{identifier} — Person Detail](#get-peopleidentifier--person-detail)
   - [roles\[\]](#roles-array)
9. [GET /courts — Courts List](#get-courts--courts-list)
10. [GET /courts/{identifier} — Court Detail](#get-courtsidentifier--court-detail)
11. [Known Dead / Unreliable Fields](#known-dead--unreliable-fields)
12. [Derived / Inferred Fields](#derived--inferred-fields)
13. [Pagination](#pagination)
14. [URL Patterns and Linking](#url-patterns-and-linking)
15. [Local Cache Structure](#local-cache-structure)
16. [Development Notes & Future Opportunities](#development-notes--future-opportunities)

---

## Endpoint Overview

| Endpoint | Returns | Used for |
|---|---|---|
| `GET /cases?filter=term:{year}&per_page={n}&page={p}` | Array of case summaries | Term browsing, Timeline tab, Docket Watch |
| `GET /cases/{term}/{docket}` | Full case detail object | Case drilldown, votes, journey, ML features |
| `GET /case_media/oral_argument_audio/{id}` | Audio metadata + full transcript | Oral Arguments tab |
| `GET /case_media/opinion_announcement_audio/{id}` | Audio metadata + transcript | (available, not yet used) |
| `GET /case_document/written_opinion/{id}` | Opinion metadata + Justia link | Written Opinions section |
| `GET /justices` | Array of current justices | Justice roster |
| `GET /people/{identifier}` | Full person detail | Justice Career tab, Advocate tracker |
| `GET /courts` | Array of all court compositions | Court history section |
| `GET /courts/{identifier}` | Court composition detail | Agreement matrix, heard_by details |

---

## GET /cases — Term List

```
GET /cases?filter=term:{year}&per_page={n}&page={p}
```

Returns an array of **case summary** objects for the given term year. The term year is the October start year (e.g., `2023` = October 2023 – June 2024 term).

Practical limits: Oyez typically has 60–70 cases per term. Use `per_page=300` to ensure you get everything in one call.

### Case Summary Object

| Field | Type | Example | Notes |
|---|---|---|---|
| `ID` | int | `63560` | Oyez internal ID |
| `name` | string | `"CFPB v. CFSA"` | Full case name, both parties |
| `href` | string | `"https://api.oyez.org/cases/2023/22-448"` | URL to full case detail |
| `view_count` | int | `0` | Oyez view count; always 0 in practice |
| `docket_number` | string | `"22-448"` | SCOTUS docket number |
| `timeline` | array | see below | Key dates for this case |
| `question` | string (HTML) | `"<p>Does…</p>"` | The certified question; HTML-encoded |
| `citation` | object | `{"volume":"601","page":null,"year":"2024","href":"…"}` | U.S. Reports citation |
| `term` | string | `"2023"` | The term year (as string) |
| `description` | string | `"A case in which…"` | One-sentence summary |
| `justia_url` | string | `"https://supreme.justia.com/…"` | Link to Justia page |

> **Not in summary:** `facts_of_the_case`, `conclusion`, `advocates`, `decisions`, `written_opinion`, `oral_argument_audio`, `lower_court`, `manner_of_jurisdiction`. Those are only in the full case detail.

---

## GET /cases/{term}/{docket} — Case Detail

```
GET /cases/2023/22-448
```

Returns the complete record for one case. This is the most data-rich endpoint.

### Case Detail Top-Level Fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `ID` | int | `63560` | Oyez internal ID |
| `name` | string | `"CFPB v. CFSA"` | Full case name |
| `href` | string | `"https://api.oyez.org/cases/2023/22-448"` | Canonical URL for this case |
| `view_count` | int | `0` | Oyez page views (always 0 in data) |
| `docket_number` | string | `"22-448"` | SCOTUS docket |
| `additional_docket_numbers` | string \| null | `null` | Consolidated dockets, if any |
| `manner_of_jurisdiction` | string (HTML) | `"Writ of <i>certiorari</i>"` | How the case reached SCOTUS |
| `first_party` | string | `"Consumer Financial Protection Bureau, et al."` | Petitioner name |
| `second_party` | string | `"Community Financial Services Association…"` | Respondent name |
| `first_party_label` | string | `"Petitioner"` | Role label for first party |
| `second_party_label` | string | `"Respondent"` | Role label for second party |
| `term` | string | `"2023"` | Term year |
| `facts_of_the_case` | string (HTML) \| null | `"<p>In response to…</p>"` | Background narrative; HTML |
| `question` | string (HTML) \| null | `"<p>Does…</p>"` | Certified question(s); HTML |
| `conclusion` | string (HTML) \| null | `"<p>The funding scheme…</p>"` | Holding summary; HTML |
| `description` | string \| null | `"A case in which…"` | One-sentence summary |
| `timeline` | array | see below | Key procedural dates |
| `lower_court` | object \| null | see below | Court below |
| `citation` | object | see below | U.S. Reports citation |
| `decisions` | array | see below | Vote records, winning party |
| `heard_by` | array | see below | Court composition when argued |
| `decided_by` | object \| null | same shape as `heard_by[0]` | Court composition when decided |
| `advocates` | array | see below | Arguing attorneys |
| `oral_argument_audio` | array | see below | Audio session references |
| `opinion_announcement` | array | see below | Opinion announcement audio references |
| `written_opinion` | array | see below | Written opinion documents |
| `related_cases` | null | `null` | Usually null in practice |
| `location` | null | `null` | Always null in practice |
| `justia_url` | string \| null | `"https://supreme.justia.com/…"` | External Justia link |
| `argument2_url` | null | `null` | Second argument URL (rare, null most cases) |
| `issue_area` | **always null** | `null` | **Dead field** — see Known Dead Fields |
| `disposition` | **always null** | `null` | **Dead field** — see Known Dead Fields |

---

### `timeline` Array

Each element is one procedural event.

| Field | Type | Example | Notes |
|---|---|---|---|
| `event` | string | `"Granted"` | Event name |
| `dates` | array of int | `[1677477600]` | Unix timestamps; usually one date, rarely more |
| `href` | string | `"https://api.oyez.org/case_timeline/…"` | Not useful to fetch |

**Known `event` values:**

| Value | Meaning |
|---|---|
| `"Granted"` | Cert granted |
| `"Argued"` | Oral argument date |
| `"Reargued"` | Case reargued |
| `"Decided"` | Decision date |
| `"Dismissed"` | Case dismissed (DIG, settled, etc.) |
| `"Remanded"` | Remanded without full decision |
| `"Petition Filed"` | Cert petition filed |

> **Usage note:** The timeline is the only reliable source of case dates. Always prefer `timeline` dates over `decided_on` or `argued_on` top-level fields (which don't exist in the response).

---

### `lower_court` Object

| Field | Type | Example | Notes |
|---|---|---|---|
| `ID` | int | `10` | Oyez taxonomy ID for the court |
| `name` | string | `"United States Court of Appeals for the Fifth Circuit"` | Full court name |
| `href` | string | `"https://api.oyez.org/taxonomy/term/10"` | Taxonomy URL (not very useful to fetch) |

> **Usage note:** `lower_court.name` is the field used to classify circuit (for ML features) and to build the court journey diagram. Parse by keyword — "court of appeals", "circuit", "appellate" → Appellate level; "supreme court of [state]" → also Appellate; everything else → Lower Court.

---

### `citation` Object

| Field | Type | Example | Notes |
|---|---|---|---|
| `volume` | string | `"601"` | U.S. Reports volume |
| `page` | string \| null | `null` | Page number; null until slip opinion is paginated |
| `year` | string | `"2024"` | Decided year |
| `href` | string | `"https://api.oyez.org/case_citation/…"` | Not useful to fetch |

---

### `decisions` Array

Each element represents a separate decision (the vast majority of cases have exactly one). Cases with multiple decisions may have been consolidated or have related cert grants.

| Field | Type | Example | Notes |
|---|---|---|---|
| `description` | string | `"The funding scheme…satisfies the Appropriations Clause."` | Plain-text holding summary |
| `votes` | array | see below | Per-justice vote records |
| `majority_vote` | int | `7` | Number of majority votes |
| `minority_vote` | int | `2` | Number of dissenting votes |
| `winning_party` | string \| null | `"CFPB"` | Short name of winning party; null for DIG/dismissed |
| `decision_type` | string \| null | `"majority opinion"` | Type of decision — see values below |
| `href` | string | `"https://api.oyez.org/decision/…"` | Not useful to fetch |

**Known `decision_type` values:**

| Value | Meaning |
|---|---|
| `"majority opinion"` | Standard majority decision |
| `"per curiam"` | Unanimous unsigned opinion |
| `"plurality opinion"` | No single rationale commands a majority |
| `"equally divided"` | 4-4 tie; lower court affirmed without precedent |
| `"dismissal - improvidently granted (DIG)"` | Cert dismissed as improvidently granted |
| `"affirmed by an equally divided Court"` | Same as equally divided |
| `"memorandum decision"` | Brief unreasoned order |
| `null` | Not yet decided or data missing |

> **Critical usage note:** `decision_type` is the only reliable source of outcome information. The top-level `disposition` field is always null. Use `(detail.get("decisions") or [{}])[0].get("decision_type")` everywhere.

---

### `decisions[].votes` Array

Each element is one justice's vote on one decision.

| Field | Type | Example | Notes |
|---|---|---|---|
| `member` | object | see Person object | Justice who voted |
| `vote` | string | `"majority"` | Vote type — see values below |
| `opinion_type` | string \| null | `"majority"` | Opinion authored, if any |
| `joining` | array \| null | `null` | Justices joining this justice's opinion |
| `seniority` | int | `2` | Seniority rank on this court (1 = Chief) |
| `ideology` | float | `0` | Oyez ideology score (rarely populated) |
| `href` | string | `"https://api.oyez.org/decision_vote/…"` | Not useful to fetch |

**`member` object (abbreviated):**

| Field | Type | Notes |
|---|---|---|
| `ID` | int | Oyez justice ID |
| `name` | string | Full name with suffix |
| `href` | string | Link to `/people/{identifier}` |
| `last_name` | string | Last name only |
| `roles` | array | Roles held (see Person Detail) |
| `thumbnail` | object | `{id, mime, size, href}` — PNG thumbnail URL |
| `length_of_service` | int | Days of service |
| `identifier` | string | URL slug (e.g., `"clarence_thomas"`) |

**Known `vote` values:**

| Value | Meaning |
|---|---|
| `"majority"` | Voted with the majority |
| `"concurrence"` | Agreed with outcome, different reasoning |
| `"concur in the judgment only"` | Agreed on result only |
| `"dissent"` | Voted against the majority |
| `"recusals"` | Recused; did not participate |
| `"none"` | No vote recorded |

---

### `heard_by` / `decided_by`

`heard_by` is an array (in case the case was argued before a different composition than it was decided). `decided_by` is a single object. Both have the same shape.

| Field | Type | Notes |
|---|---|---|
| `ID` | int | Oyez court ID |
| `name` | string | E.g., `"Roberts Court (2022-)"` |
| `href` | string | Link to `/courts/{identifier}` |
| `view_count` | int | Always 0 |
| `members` | array | Array of justice objects (same shape as `votes[].member` above) |
| `court_start` | int | Unix timestamp when this composition began |
| `images` | array \| null | Court photo references |
| `identifier` | string | URL slug (e.g., `"roberts13"`) |

---

### `advocates` Array

Each element is one attorney who argued before the Court.

| Field | Type | Example | Notes |
|---|---|---|---|
| `advocate` | object | Person object | The attorney (same shape as justice member, but most fields null for non-justices) |
| `advocate_description` | string | `"for the Petitioners"` | Role description |
| `href` | string | `"https://api.oyez.org/case_advocate/…"` | Not useful to fetch |

---

### `oral_argument_audio` Array

Each element is one oral argument session (most cases have one; a few have two, labeled in `title`).

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | int | `25479` | Audio session ID — use to fetch full transcript |
| `title` | string | `"Oral Argument - October 03, 2023"` | Display title with date |
| `public_note` | string \| null | `null` | Any public note on the recording |
| `unavailable` | bool | `false` | Whether audio is unavailable |
| `display_title` | string \| null | `null` | Override title if set |
| `href` | string | `"https://api.oyez.org/case_media/oral_argument_audio/25479"` | URL to fetch full audio + transcript |

---

### `opinion_announcement` Array

References to the announcement audio when the Court read its opinion from the bench.

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | int | `25684` | Announcement audio ID |
| `title` | string | `"Opinion Announcement - May 16, 2024"` | Display title |
| `unavailable` | bool | `false` | Whether audio is unavailable |
| `href` | string | `"https://api.oyez.org/case_media/opinion_announcement_audio/25684"` | URL to fetch full audio + transcript |

---

### `written_opinion` Array

References to written opinions filed in the case (majority, concurrences, dissents).

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | int | `17706` | Document ID |
| `title` | string | `"Concurring opinion"` | Opinion type label |
| `author` | null | `null` | Usually null (use `judge_full_name`) |
| `type` | object | `{"value":"concurring","label":"Concurring opinion"}` | Structured type |
| `justia_opinion_id` | int | `4891733` | Justia opinion ID |
| `justia_opinion_url` | string | `"https://supreme.justia.com/…"` | External opinion text link |
| `judge_full_name` | string | `"Elena Kagan"` | Author's full name |
| `judge_last_name` | string | `"Kagan"` | Author's last name |
| `title_overwrite` | null | `null` | Title override if set |
| `href` | string | `"https://api.oyez.org/case_document/written_opinion/17706"` | URL to fetch opinion detail |

---

## GET /case_media/oral_argument_audio/{id} — Oral Argument Detail

```
GET /case_media/oral_argument_audio/25479
```

Returns the full audio metadata and timestamped transcript for one oral argument session.

| Field | Type | Notes |
|---|---|---|
| `id` | int | Same as the `id` in the case's `oral_argument_audio` array |
| `title` | string | Display title |
| `media_file` | array | Audio file references (see below) |
| `transcript` | object | Full transcript (see below) |
| `public_note` | string \| null | Public note |
| `unavailable` | bool | Whether audio is unavailable |
| `damaged` | bool | Whether recording is damaged |
| `display_title` | string \| null | Display title override |

### `media_file` Array

Each element is one audio file in a different format.

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | int | `82180` | File ID |
| `mime` | string | `"audio/mpeg"` | MIME type (`audio/mpeg` = MP3, `audio/ogg` = OGG) |
| `size` | int | `22628382` | File size in bytes |
| `href` | string | `"https://s3.amazonaws.com/oyez.case-media.mp3/…"` | Direct audio file URL on S3 |

### `transcript` Object

| Field | Type | Notes |
|---|---|---|
| `title` | string | Transcript title |
| `duration` | float | Total duration in seconds |
| `sections` | array | List of argument sections (see below) |

### `transcript.sections` Array

| Field | Type | Notes |
|---|---|---|
| `start` | float | Start time in seconds |
| `stop` | float | End time in seconds |
| `byte_start` | int | Byte offset in audio stream |
| `byte_stop` | int | Byte offset end |
| `turns` | array | Speaker turns in this section |

### `sections[].turns` — Turn Object

| Field | Type | Example | Notes |
|---|---|---|---|
| `start` | float | `0.18` | Start time in seconds |
| `stop` | float | `11.44` | End time in seconds |
| `byte_start` | int | `0` | Byte offset |
| `byte_stop` | int | `0` | Byte offset end |
| `speaker` | object | Person object | The speaker (justice or advocate) |
| `text_blocks` | array | see below | Text segments for this turn |

### Turn `text_blocks` Array

| Field | Type | Example | Notes |
|---|---|---|---|
| `start` | float | `0.18` | Start time |
| `stop` | float | `11.44` | End time |
| `byte_start` | int | `0` | Byte offset |
| `byte_stop` | int | `0` | Byte offset end |
| `text` | string | `"We'll hear argument…"` | Spoken text for this segment |

> **Usage tip:** For a readable transcript preview, iterate `sections[:1]` → `turns[:N]` → join `text_blocks[].text`. The current app previews the first 6 turns, 400 characters each.

---

## GET /case_media/opinion_announcement_audio/{id} — Opinion Announcement Detail

```
GET /case_media/opinion_announcement_audio/25684
```

Same structure as oral argument audio above. The transcript here is the announcement read from the bench.

| Field | Type | Notes |
|---|---|---|
| `id` | int | Announcement audio ID |
| `title` | string | E.g., `"Opinion Announcement - May 16, 2024"` |
| `transcript` | object | Same `{title, duration, sections}` structure as oral argument |
| `media_file` | array | Same `{id, mime, size, href}` structure |
| `damaged` | bool | Whether recording is damaged |
| `unavailable` | bool | Whether audio is unavailable |

> **Opportunity:** Opinion announcements are not currently used by the app. The transcript could power a "Bench announcement" section — often shorter and more quotable than the full oral argument.

---

## GET /case_document/written_opinion/{id} — Written Opinion Detail

```
GET /case_document/written_opinion/17706
```

| Field | Type | Notes |
|---|---|---|
| `id` | int | Document ID |
| `title` | string | Opinion type label |
| `author` | null | Almost always null (use `judge_full_name`) |
| `opinion_body` | null | Always null — full text not provided |
| `media_files` | null | Always null — no PDF in API |
| `type` | object | `{value, label}` — e.g., `{value:"concurring", label:"Concurring opinion"}` |
| `justia_opinion_id` | int | Justia opinion ID for external link |
| `justia_opinion_url` | string | Full text available on Justia |
| `judge_full_name` | string | Opinion author's full name |
| `judge_last_name` | string | Opinion author's last name |
| `title_overwrite` | null | Always null |

> **Note:** Full opinion text is not available through Oyez. Justia is the external source for full text. The `justia_opinion_url` field links directly there.

---

## GET /justices — Justices List

```
GET /justices
```

Returns the current nine sitting justices as an array of abbreviated person objects.

Each item has the same shape as the abbreviated `member` object described in the votes section:

| Field | Type | Notes |
|---|---|---|
| `ID` | int | Oyez person ID |
| `name` | string | Full name |
| `href` | string | Link to `/people/{identifier}` for full detail |
| `view_count` | int | Always 0 |
| `last_name` | string | Last name only |
| `roles` | array | Array of role objects |
| `thumbnail` | object | `{id, mime, size, href}` thumbnail image |
| `length_of_service` | int | Days served as of the response date |
| `identifier` | string | URL slug |

---

## GET /people/{identifier} — Person Detail

```
GET /people/ketanji_brown_jackson
GET /people/elizabeth_b_prelogar
```

Returns the full profile for a justice or an advocate. Most biographical fields are null for non-justices.

| Field | Type | Example | Notes |
|---|---|---|---|
| `ID` | int | `33869` | Oyez ID |
| `name` | string | `"Ketanji Brown Jackson"` | Full name |
| `href` | string | `"https://api.oyez.org/people/…"` | Canonical URL |
| `first_name` | string | `"Ketanji"` | |
| `middle_name` | string \| null | `"david.kemp"` | Often a slug artifact; may not be a real middle name |
| `last_name` | string | `"Jackson"` | |
| `name_suffix` | string \| null | `null` | Suffix (Jr., III, etc.) |
| `date_of_birth` | int | `22136400` | Unix timestamp; 0 if unknown |
| `place_of_birth` | string \| null | `"Washington, DC"` | |
| `date_of_death` | int | `0` | Unix timestamp; 0 = living |
| `place_of_death` | string \| null | `null` | |
| `gender` | string \| null | `"Female"` | |
| `ethnicity` | null | `null` | Always null in practice |
| `family_status` | null | `null` | Always null in practice |
| `mother` | string \| null | `"Ellery Brown"` | Justices only |
| `father` | string \| null | `"Johnny Brown"` | Justices only |
| `mothers_occupation` | string \| null | `"School Principal"` | Justices only |
| `fathers_occupation` | string \| null | `"Lawyer"` | Justices only |
| `biography` | string (HTML) \| null | `"<p>Justice…</p>"` | Full bio; HTML-encoded |
| `roles` | array | see below | All judicial/government roles held |
| `thumbnail` | object \| null | `{id, mime, size, href}` | Thumbnail image (null for advocates) |
| `images` | array \| null | `[{file, image_field_caption}]` | Full-res photos |
| `religion` | string \| null | `"Protestant"` | Justices only |
| `length_of_service` | int | `1310` | Days of SCOTUS service |
| `identifier` | string | `"ketanji_brown_jackson"` | URL slug |
| `law_school` | string \| null | `"Harvard Law School"` | Justices only |
| `number_of_children` | int | `2` | Justices only |
| `home_state` | string \| null | `null` | Often null |

### `roles` Array

Each element is one judicial or government position.

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | int | `3520` | Role ID |
| `type` | string | `"scotus_justice"` | Role type; see values below |
| `date_start` | int | `1656565200` | Unix timestamp |
| `date_end` | int | `0` | Unix timestamp; `0` = still serving |
| `appointing_president` | string \| null | `"Barack Obama"` | President who appointed (null for some recent entries — data quality issue) |
| `role_title` | string | `"Associate Justice…"` | Full title |
| `institution_name` | string | `"Supreme Court of the United States"` | |
| `href` | string | `"https://api.oyez.org/preson_role/scotus_justice/3520"` | Not useful to fetch |

**Known `type` values:**

| Value | Meaning |
|---|---|
| `"scotus_justice"` | Supreme Court justice |
| `"judge"` | Lower court judge |
| `"attorney"` | Practicing attorney |
| `"government_official"` | Executive branch official |
| `"politician"` | Elected official |
| `"academic"` | Law professor |

---

## GET /courts — Courts List

```
GET /courts
```

Returns all historical court compositions (one per membership change) as an array.

Each element has the same shape as a court detail object (described below) — but with `members` already included in the list response.

---

## GET /courts/{identifier} — Court Detail

```
GET /courts/roberts13
```

| Field | Type | Example | Notes |
|---|---|---|---|
| `ID` | int | `63493` | Oyez court ID |
| `name` | string | `"Roberts Court (2022-)"` | Descriptive name |
| `href` | string | `"https://api.oyez.org/courts/roberts13"` | Canonical URL |
| `view_count` | int | `0` | Always 0 |
| `court_start` | int | `1656565200` | Unix timestamp when this composition began |
| `court_end` | int | `0` | Unix timestamp when it ended; `0` = current |
| `images` | null | `null` | Usually null |
| `identifier` | string | `"roberts13"` | URL slug |
| `members` | array | Array of person objects | Justice members (same abbreviated shape as `votes[].member`) |

> **Identifier naming convention:** The identifier follows a pattern of `{chief_last_name}{sequence}`. For example, `roberts1` through `roberts13` represent each distinct composition of the Roberts Court as justices joined or left.

---

## Known Dead / Unreliable Fields

These fields exist in the API schema and are returned in responses, but are **always `null`** and should not be used.

| Field | Location | Expected content | Reality | What to use instead |
|---|---|---|---|---|
| `issue_area` | Case detail top-level | Legal issue category | Always `null` | `utils/local_data.infer_issue_area(detail)` — keyword inference on `question` + `description` + `facts_of_the_case` |
| `disposition` | Case detail top-level | Outcome label (affirmed/reversed/etc.) | Always `null` | `(detail.get("decisions") or [{}])[0].get("decision_type")` — returns values like `"majority opinion"`, `"per curiam"` |
| `decided_on` | Case detail top-level | Decision date | Does not exist | `timeline` array — filter for `event == "Decided"` |
| `argued_on` | Case detail top-level | Argument date | Does not exist | `timeline` array — filter for `event == "Argued"` |
| `opinion_body` | Written opinion detail | Full text of opinion | Always `null` | Justia via `justia_opinion_url` |
| `media_files` | Written opinion detail | PDF of opinion | Always `null` | No PDF available through Oyez |
| `ideology` | `votes[].ideology` | Oyez ideology score | Always `0` or null | Not reliable; use the static lean lookup in `pages/Insights.py` |
| `ethnicity` | Person detail | Justice's ethnicity | Always `null` | Not available |
| `appointing_president` | `roles[]` | Appointing president | Null for some recent justices | Use the static `JUSTICES_DATA` lookup in `pages/Insights.py` |

---

## Derived / Inferred Fields

Fields the app computes from API data because the API does not provide them directly.

| Derived field | Source data | Code location | Notes |
|---|---|---|---|
| `issue_area` | `question` + `description` + `facts_of_the_case` text | `utils/local_data.infer_issue_area()` | Keyword matching across 15 legal categories; returns `"Unknown"` if no text available (term-list summaries are too thin) |
| `outcome` (affirm/reverse/other) | `decisions[0].decision_type` | `_classify_disposition()` / `_classify_disp()` in page files | Looks for "affirm" → respondent won; "revers"/"vacate"/"remand" → petitioner won; else "Other" |
| `court_level` | `lower_court.name` | `utils/oyez_api.extract_court_journey()` | Keyword inference: "court of appeals"/"circuit"/"appellate" or state supreme → "Appellate Court"; else → "Lower Court" |
| `circuit` | `lower_court.name` | `utils/ml_predictor.extract_circuit()` | Maps court name to one of the 12 numbered circuits + DC + Federal |
| `petitioner_type` | `first_party` name | `_classify_party()` in `pages/Analysis.py` | Classifies as Federal Government / State Gov / Corporation / Individual |
| `justice_lean` | Justice name | Static `JUSTICE_LEAN` dict | Conservative / Moderate / Liberal — not from API |
| `ideological_shift` | Computed from lean changes | `pages/Insights.py` Legacy Score | Per-president net directional impact |

---

## Pagination

The cases list endpoint supports pagination:

```
GET /cases?filter=term:{year}&per_page={n}&page={p}
```

| Parameter | Notes |
|---|---|
| `filter=term:{year}` | Required; `year` is the October start year (e.g., `2023`) |
| `per_page` | Items per page; maximum appears to be 300; safe to use 300 for a full term |
| `page` | 0-indexed page number |

A term typically has 60–70 cases. Using `per_page=300&page=0` returns everything in one request for any single term.

There is no standard `total_count` field in the response — you get the full array directly.

---

## URL Patterns and Linking

| Pattern | Notes |
|---|---|
| `https://api.oyez.org/cases/{term}/{docket}` | API case detail URL; stored in `href` |
| `https://www.oyez.org/cases/{term}/{docket}` | Public Oyez website page for the same case |
| `https://api.oyez.org/people/{identifier}` | API person detail URL |
| `https://www.oyez.org/justices/{identifier}` | Public Oyez website justice page |
| `https://api.oyez.org/courts/{identifier}` | API court composition URL |

**API → web URL conversion:**
```python
web_url = api_href.replace("api.oyez.org/cases", "www.oyez.org/cases")
```

This is already used in several places in the app for "Open on Oyez ↗" links.

---

## Local Cache Structure

The app's cache is at `data_files/oyez_data/`. It is checked before every API call in `utils/local_data.fetch_oyez()`.

```
data_files/oyez_data/
  cases/
    {term}/
      cases.json                       # Full term list response array
  case_detail/
    {term}/
      cases_{term}_{docket}.json       # Full case detail response
  justices/
    justices.json                      # /justices list response
  courts/
    {identifier}.json                  # /courts/{identifier} response
  dispositions_cache.json              # Pre-built: {href → {name, term, decision_type, winning_party}}
  api_fallback.log                     # URLs that were not in cache and were fetched live
```

**`dispositions_cache.json`** is a pre-computed flat index built from all local detail files. It maps each case's `href` to its `name`, `term`, `decision_type`, and `winning_party`. It contains 8,238 entries spanning 71 terms. Use it for fast outcome lookups without fetching individual detail files.

```python
# Fast lookup pattern:
cache = json.load(open("data_files/oyez_data/dispositions_cache.json"))
entry = cache.get(href)   # → {name, term, decision_type, winning_party}
```

---

## Development Notes & Future Opportunities

### What works reliably

- **Case metadata** — name, docket, parties, term, manner of jurisdiction, citation. Always populated.
- **Timeline events** — Granted/Argued/Decided dates. The most reliable date source in the API.
- **`facts_of_the_case` / `question` / `conclusion`** — Rich narrative text; HTML-encoded; present on nearly all decided cases.
- **`decisions[].votes`** — Per-justice vote records are complete and accurate for cases from the 1990s onward.
- **`decisions[].decision_type`** — The real outcome field. Always present for decided cases.
- **`decisions[].winning_party`** — Short name of the winning party; present for most cases but occasionally null on per curiam or DIG decisions.
- **`advocates`** — Complete for cases with oral argument.
- **`oral_argument_audio`** — Present for virtually all argued cases; transcripts are timestamped to the word level.
- **`lower_court.name`** — Reliable; the primary source for circuit classification and court journey diagrams.

### Known data quality issues

1. **`issue_area` is always null.** This is the most significant gap. The field exists in the schema but Oyez never populates it via the API. The keyword-inference workaround (`infer_issue_area()`) is reasonable but imprecise — it will mis-classify edge cases and return "Unknown" for any case where `question`/`description`/`facts_of_the_case` are empty (rare, but happens for very old or undocumented cases).

2. **`disposition` is always null.** Use `decisions[0].decision_type` instead. Note that `decision_type` describes *how* the Court decided (majority vs. per curiam vs. plurality), not *what* it decided (affirm/reverse). Outcome inference still requires reading `winning_party` and the text description.

3. **`appointing_president` in `roles[]`** is null for some recent justices (a data quality issue on Oyez's end). The static `JUSTICES_DATA` list in `pages/Insights.py` is a reliable fallback.

4. **Older terms (pre-1990)** have thinner data — fewer `votes` records, missing `oral_argument_audio`, and often null `facts_of_the_case`. The historical data section of the app uses a static pre-computed dataset for pre-1953 cases rather than relying on live API data.

5. **`winning_party`** is occasionally an internal Oyez label rather than the actual party name (e.g., `"CFPB"` rather than `"Consumer Financial Protection Bureau"`). It is best used for outcome direction (petitioner vs. respondent won) rather than display.

### Untapped endpoints / future feature ideas

| Opportunity | Details |
|---|---|
| **Opinion announcement transcripts** | `GET /case_media/opinion_announcement_audio/{id}` — The Court reads a summary of its opinion from the bench. These transcripts are shorter and more quotable than oral argument. Could add a "Read the announcement" panel to any case. |
| **Full argument audio playback** | The `media_file[].href` fields in oral argument detail are direct S3 MP3 URLs. An in-app audio player would be straightforward to add using an HTML audio element via `st.components.v1.html()`. |
| **Historical justice voting by issue** | The `decisions[].votes` data goes back to the 1950s. A long-range analysis (e.g., "how has the Court's unanimity rate changed by issue area over 70 years") is fully supported by the cached data. |
| **Advocate win-rate career tracking** | The `advocates[].advocate.href` field links to a full person record. Because each person has a unique `identifier`, it is possible to track every case an individual advocate argued across all terms by scanning `advocates` arrays. |
| **Audio duration analysis** | `transcript.duration` (in the oral argument detail) provides the total argument length in seconds. Plotting argument duration vs. decision complexity or vote split could be an interesting analytical feature. |
| **Justice question-count analysis** | The `transcript.turns` speaker-level data makes it possible to count exactly how many times each justice spoke during oral argument and how many words they used. This is a strong predictor of vote direction (more questions to one side → vote against that side). |
| **Second argument detection** | `argument2_url` is present on a very small number of cases (ones that were reargued). It is currently always null in the data but could be used to flag reargued cases automatically. |
| **Related cases linking** | `related_cases` is always null in the live API, but consolidated cases are indirectly detectable through `additional_docket_numbers`. Parsing that field could reconstruct consolidation relationships. |
| **Citation text in oral argument** | When a justice or advocate mentions a case name in `text_blocks[].text`, it is detectable with simple string matching. This could be used to build a basic citation graph directly from transcript text rather than scraped opinion text. |
| **Term comparison across the full history** | The `dispositions_cache.json` already has 8,238 cases across 71 terms. An extended version of the Term Comparator tab using this cache — rather than live API calls — could cover the full 1955–present range without any additional fetching. |

### Caching strategy notes

- The `fetch_oyez()` function checks the local cache first. A cache miss fetches live and logs the URL to `api_fallback.log`. It does **not** automatically write the live response to the cache — new terms need to be downloaded explicitly.
- For current-term data, the Term Calendar tab intentionally bypasses cache for the two most recent terms to get up-to-date statuses. All other tabs use cache-first.
- The `dispositions_cache.json` must be manually regenerated after downloading new term data. No auto-refresh mechanism exists today.

### ML predictor notes

The ML predictor (`utils/ml_predictor.py`) uses these API-derived features:

| Feature | Source |
|---|---|
| `circuit` | `lower_court.name` → `extract_circuit()` |
| `issue_area` | `infer_issue_area(detail)` keyword inference |
| `petitioner_type` | `first_party` text classification |
| `sol_gen_support` | Whether "United States" appears in `advocates` as petitioner-side |
| `circuit_split` | Inferred from `question`/`facts_of_the_case` text |
| `conservative_justices` | Static count based on `decided_by.members` names + lean lookup |
| Per-justice vote | `decisions[0].votes[].vote` for training labels |

Training target: reversal vs. affirmance, derived from `winning_party` vs. `first_party`/`second_party` matching. The model covers only cases with a determinable outcome (~70–80% of decided cases; DIG/per curiam/equally divided are excluded from training).
