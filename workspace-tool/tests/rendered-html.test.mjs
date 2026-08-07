import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function worker() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: built } = await import(workerUrl.href);
  return built;
}

test("server-renders the finished analyst workspace", async () => {
  const built = await worker();
  const response = await built.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /<title>CAISO Market Intelligence Workspace<\/title>/i);
  assert.match(html, /Ask the market/);
  assert.match(html, /Official sources first/);
  assert.match(html, /Source authority is part of the answer/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/i);
});

test("returns a source-grounded deterministic answer without credentials", async () => {
  const built = await worker();
  const response = await built.fetch(new Request("http://localhost/api/ask", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question: "Where is solar curtailment risk concentrated?" }) }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.mode, "verified_evidence_pack");
  assert.match(payload.answer, /HE 13/);
  assert.ok(payload.sources.some((item) => item.url.includes("Solar-Curtailment-AI-generator")));
  assert.ok(payload.limitations.length > 0);
});

test("ships product metadata and the bespoke social card", async () => {
  const [layout, packageJson] = await Promise.all([readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"), readFile(new URL("../package.json", import.meta.url), "utf8")]);
  assert.match(layout, /CAISO Market Intelligence Workspace/);
  assert.match(layout, /\/og\.png/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  await access(new URL("../public/og.png", import.meta.url));
  await assert.rejects(access(new URL("../app\/_sites-preview\/SkeletonPreview.tsx", root)));
});
