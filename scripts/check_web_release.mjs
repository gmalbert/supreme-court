import { readdir, readFile, stat } from "node:fs/promises";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
// Docker runs this from web/, while CI and local instructions use the repo root.
const directory = process.argv[2]
  ? resolve(process.argv[2])
  : fileURLToPath(new URL("../web/dist/", import.meta.url));
async function walk(dir) {
  const list = await readdir(dir, { withFileTypes: true });
  return (
    await Promise.all(
      list.map(async (entry) =>
        entry.isDirectory()
          ? walk(join(dir, entry.name))
          : [join(dir, entry.name)],
      ),
    )
  ).flat();
}
const files = await walk(directory);
if (files.length > 20000)
  throw new Error(`Too many static assets: ${files.length}`);
for (const file of files) {
  if ((await stat(file)).size > 25 * 1024 ** 2)
    throw new Error(`Cloudflare asset exceeds 25 MiB: ${file}`);
  if (/(?:^|[\\/])(?:\.env|secrets\.toml|\.dev\.vars|.*\.py)$/.test(file))
    throw new Error(`Unexpected private/runtime file: ${file}`);
}
const manifest = JSON.parse(
  await readFile(join(directory, "data/manifest.json"), "utf8"),
);
if (
  !manifest.transcriptsIncluded ||
  manifest.cases < 8000 ||
  manifest.arguments < 8000
)
  throw new Error("Incomplete production data release.");
const routes = [
  "index.html",
  "data/search.json",
  "data/catalog.json",
  "data/model.json",
  "states.json",
];
for (const route of routes) await stat(join(directory, route));
console.log(
  `Verified ${files.length} deployable assets, ${manifest.cases} cases, ${manifest.arguments} arguments; release ${manifest.version}.`,
);
