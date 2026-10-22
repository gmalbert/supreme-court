import { createServer } from "node:net";
import { spawn } from "node:child_process";

function freePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close((error) => (error ? reject(error) : resolve(address.port)));
    });
  });
}
// Allocate once before Playwright starts. Its config is evaluated again in each
// worker process, so allocating ports in the config gives workers different URLs.
const env = { ...process.env };
if (!env.PLAYWRIGHT_BASE_URL) {
  env.PLAYWRIGHT_HTTP_PORT = String(await freePort());
  env.PLAYWRIGHT_INSPECTOR_PORT = String(await freePort());
}
const child = spawn(
  process.execPath,
  ["node_modules/@playwright/test/cli.js", "test", ...process.argv.slice(2)],
  { stdio: "inherit", env },
);
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => child.kill(signal));
child.on("error", (error) => {
  console.error(error.message);
  process.exit(1);
});
child.on("exit", (code) => process.exit(code ?? 1));
