import { writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
// Wrangler reads these bindings from a runtime-only file. Docker never copies or
// embeds a developer's .env/.dev.vars file into the image or build cache.
const allowed = [
  "GEMINI_API_KEY",
  "GOOGLE_API_KEY",
  "GEMINI_MODEL",
  "CHAT_PROVIDER",
  "OPENCODE_API_KEY",
  "OPENCODE_MODEL",
];
const bindings = allowed
  .filter((key) => process.env[key])
  .map((key) => `${key}=${JSON.stringify(process.env[key])}`)
  .join("\n");
if (bindings) await writeFile(".dev.vars", bindings + "\n", { mode: 0o600 });
const child = spawn(
  process.execPath,
  [
    "node_modules/wrangler/bin/wrangler.js",
    "dev",
    "--local",
    "--ip",
    "0.0.0.0",
    "--port",
    "8787",
  ],
  { stdio: "inherit" },
);
let stopping = false;
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => {
    stopping = true;
    child.kill(signal);
  });
child.on("error", (error) => {
  console.error("Could not start the local Cloudflare runtime:", error.message);
  process.exit(1);
});
child.on("exit", (code) => process.exit(stopping ? 0 : (code ?? 1)));
