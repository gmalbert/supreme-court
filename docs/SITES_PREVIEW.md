# Supreme Scrutiny review checkpoint

Preview: https://supreme-scrutiny-preview.gmalbert.chatgpt.site

The preview is private to the owner's account. It includes the complete case and
transcript snapshot; AI answers are disabled. Production hosting and DNS have not
changed.

## Saved implementation

- Migration branch: `codex/cloudflare-react-migration`.
- React conversion: `e9471bb`.
- Streamlit appearance, Docker Compose, installation guide, and tests: `fc49cce`.
- Published Sites source commit: `d4fe7bf04f90b1cc00575c95f7da1b7ae3181a2e`.
- Site project: `appgprj_6ad9de8cd6bc8191a9970ea8eef907b8`.
- Successful deployment: `appgdep_6ad9e4fe40148191b2c9b8e6f3e2bdae`.

The separate Sites checkout is retained at
`C:/Users/Greg/.codex/visualizations/2026/10/22/01a1613c-c26f-7303-9439-3cfdecb1a291/supreme-scrutiny-sites`.
Its `.openai/hosting.json` records the project identity and static SPA settings.
Reuse that identity for subsequent preview updates.

## Sites-specific packaging

Sites limits the expanded deployment archive to 256 MiB. The preview therefore
stores all 8,294 transcripts as losslessly compressed `.json.gz` files, bringing
the static release to approximately 206 MiB. Its JSON loader handles both raw
gzip and responses already decoded by the hosting platform. The main Cloudflare
migration checkout continues to use the original JSON export.

The Sites checkout includes frontend source, dependency lockfile, and a Vite
configuration that preserves the static corpus during frontend rebuilds.
The exact published source is committed and pushed to the Site's repository.

## Validation and remaining review

The main conversion passed 20 desktop/mobile Playwright checks, 23 unit tests,
three export tests, compilation of 92 Python files, the production build, and a
Wrangler deployment dry run. Docker startup remains unverified locally because
Docker is not installed on this machine.

The Sites adaptation passed desktop/mobile checks of the homepage, search,
saved cases, all 55 feature sections, model-card layout, transcript loading,
CSV downloads, and transcript filtering. An additional browser check verified
raw gzip decoding. Sites confirmed successful private deployment.

Custom charts and consolidated analysis subviews still have visual differences
from Streamlit. Use the hosted preview for the next round of annotations.
Unrelated pre-existing local work remains outside these migration commits.
