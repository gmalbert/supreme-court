# Supreme Scrutiny — 6-Month Feature Roadmap

## Month 1: Case Explorer

- **Advanced search** — Filter by term, petitioner type, outcome, topic, and author simultaneously.
- **Quick stats bar** — Total opinions this term, reversal rate, most active justice.
- **Today in SCOTUS history** — Case decided on this date in past terms; uses `utils/today_in_history.py`.
- **Cert granted tracker** — Cases that have been granted certiorari but not yet decided.

## Month 2: Justice Profiles

- **Full justice biography** — Tenure, appointing president, prior judicial experience, notable opinions.
- **Voting agreement matrix** — Interactive heatmap for any combination of justices.
- **Career timeline** — Year-by-year opinion count and reversal rate.
- **Concurrence vs. dissent ratio** — How often a justice writes separately vs. joining the majority.

## Month 3: Analytics Deep-Dive

- **Voting coalition tracker** — Current term's bloc analysis with dendrogram.
- **Issue area trends** — Which legal topics have grown/shrunk on the Court's docket over the last 20 terms.
- **Cert grant rate by circuit** — Which circuit courts see the most SCOTUS review.
- **Swing justice analysis** — Who is the decisive vote on close decisions?

## Month 4: Oral Arguments

- **Argument transcript viewer** — Browse oral argument transcripts with justice-by-justice question highlighting.
- **Question count by justice** — Which justices are most/least active at oral argument.
- **Oyez audio links** — Direct links to oral argument recordings.

## Month 5: Prediction & Research

- **Current term predictions** — Model outcome predictions for pending argued cases.
- **Research export** — CSV/PDF export of filtered case sets for academic use.
- **Amicus brief tracker** — Count of amicus briefs filed per case as a feature for outcome prediction.

## Month 6: Automation

- **Weekly data sync** — GitHub Action fetches new Oyez opinions every Monday during the term.
- **Decision alert** — Email when a tracked case is decided.
- **Term recap report** — Auto-generated PDF at the end of each October Term.
