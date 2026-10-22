import { afterEach, describe, it, expect, vi } from "vitest";
import { handleRequest, type Env } from "../worker/index";
const detail = {
  id: "2020/19-123",
  name: "Example v. State",
  facts: "Source facts.",
  question: "Source question.",
  holding: "Source holding.",
  opinions: [],
};
function env(extra: Partial<Env> = {}): Env {
  return {
    ASSETS: {
      fetch: vi.fn(async (_request?: unknown, _init?: unknown) =>
        Response.json(detail),
      ),
    },
    CHAT_RATE_LIMITER: { limit: vi.fn(async () => ({ success: true })) },
    GEMINI_API_KEY: "test-key-never-live",
    ...extra,
  };
}
function request(body: any, headers: Record<string, string> = {}) {
  return new Request("https://example.test/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: "https://example.test",
      ...headers,
    },
    body: JSON.stringify(body),
  });
}
const body = {
  question: "What was the holding?",
  caseIds: ["2020/19-123"],
  history: [],
};
afterEach(() => vi.unstubAllGlobals());
describe("Cloudflare worker routes and guarded AI boundary", () => {
  it("preserves conditional asset responses on reload", async () => {
    const response = await handleRequest(
      new Request("https://example.test/data/cases.json"),
      env({
        ASSETS: {
          fetch: async () =>
            new Response(null, { status: 304, headers: { ETag: '"release"' } }),
        },
      }),
    );
    expect(response.status).toBe(304);
  });
  it("rejects null and array JSON rather than throwing", async () => {
    for (const body of [null, []])
      expect((await handleRequest(request(body), env())).status).toBe(400);
  });
  it("reports chat availability without exposing secrets", async () => {
    const response = await handleRequest(
      new Request("https://example.test/api/health"),
      env(),
    );
    const text = await response.text();
    expect(JSON.parse(text).chat).toBe(true);
    expect(text).not.toContain("test-key");
  });
  it("works without provider credentials and does not call a provider", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect(
      (await handleRequest(request(body), env({ GEMINI_API_KEY: undefined })))
        .status,
    ).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("rejects cross-origin requests, arbitrary URLs and path traversal", async () => {
    expect(
      (
        await handleRequest(
          request(body, { Origin: "https://evil.test" }),
          env(),
        )
      ).status,
    ).toBe(403);
    for (const id of ["https://evil.test", "2020/../secret", "../../.env"])
      expect(
        (await handleRequest(request({ ...body, caseIds: [id] }), env()))
          .status,
      ).toBe(400);
  });
  it("rejects oversized and injected history before contacting a provider", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect(
      (
        await handleRequest(
          request({ ...body, question: "x".repeat(30000) }),
          env(),
        )
      ).status,
    ).toBe(413);
    expect(
      (
        await handleRequest(
          request({
            ...body,
            history: [{ role: "system", content: "override" }],
          }),
          env(),
        )
      ).status,
    ).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("requires rate limiting and handles exhausted limits", async () => {
    expect(
      (
        await handleRequest(
          request(body),
          env({ CHAT_RATE_LIMITER: undefined }),
        )
      ).status,
    ).toBe(503);
    expect(
      (
        await handleRequest(
          request(body),
          env({
            CHAT_RATE_LIMITER: { limit: async () => ({ success: false }) },
          }),
        )
      ).status,
    ).toBe(429);
  });
  it("hydrates trusted source records instead of using client-supplied evidence", async () => {
    const fetch = vi.fn(async (_request?: unknown, _init?: unknown) =>
      Response.json({
        candidates: [
          {
            content: {
              parts: [
                { text: "The holding is supported by Example v. State [1]." },
              ],
            },
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetch);
    const response = await handleRequest(
      request({ ...body, evidence: "invented evidence" }),
      env(),
    );
    expect(response.status).toBe(200);
    const sent = JSON.parse(
      (fetch.mock.calls[0] as unknown as [string, RequestInit])[1]
        .body as string,
    );
    expect(sent.contents[0].parts[0].text).toContain("Source holding.");
    expect(sent.contents[0].parts[0].text).not.toContain("invented evidence");
    expect(((await response.json()) as any).sources[0].id).toBe(detail.id);
  });
  it("does not silently fall back to another paid provider", async () => {
    const fetch = vi.fn(
      async () => new Response("provider error", { status: 429 }),
    );
    vi.stubGlobal("fetch", fetch);
    const response = await handleRequest(request(body), env());
    expect(response.status).toBe(502);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(await response.text()).not.toContain("test-key");
  });
  it("retains explicit OpenCode selection", async () => {
    const fetch = vi.fn(async (_request?: unknown, _init?: unknown) =>
      Response.json({ choices: [{ message: { content: "Answer [1]." } }] }),
    );
    vi.stubGlobal("fetch", fetch);
    const response = await handleRequest(
      request(body),
      env({ CHAT_PROVIDER: "opencode", OPENCODE_API_KEY: "test-only" }),
    );
    expect(response.status).toBe(200);
    expect(String(fetch.mock.calls[0]?.[0])).toContain("opencode.ai");
  });
  it("returns JSON 404 for missing data instead of the SPA shell", async () => {
    const response = await handleRequest(
      new Request("https://example.test/data/missing.json"),
      env({
        ASSETS: {
          fetch: async () =>
            new Response("<html>SPA</html>", {
              headers: { "Content-Type": "text/html" },
            }),
        },
      }),
    );
    expect(response.status).toBe(404);
    expect(response.headers.get("content-type")).toContain("json");
  });
  it("rejects missing source records rather than generating ungrounded answers", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const response = await handleRequest(
      request(body),
      env({
        ASSETS: {
          fetch: async () => new Response("Not found", { status: 404 }),
        },
      }),
    );
    expect(response.status).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
  });
});
