// Test a built/installed wheel, not the Next dev server. No LLM or screenshots.
// UI_PYTHON=/path/to/clean/venv/bin/python node scripts/verify-base-path.mjs
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import http from "node:http";
import { fileURLToPath } from "node:url";
import { chromium, expect } from "@playwright/test";

const browser = await chromium.launch({ headless: true });
const results = [];
try {
  for (const { prefix, preset } of ["", "/chat", "/platform/apps/chat"].flatMap(prefix =>
    ["minimal", "full"].map(preset => ({ prefix, preset })))) {
    for (const stripPrefix of [true, false]) {
      let port = 0; // Let the OS allocate an unused upstream port.
      const child = spawn(process.env.UI_PYTHON || "python3", [
        fileURLToPath(new URL("./base-path-server.py", import.meta.url)),
      ], { env: { ...process.env, BASE_PATH: prefix, UI_PRESET: preset, PORT: String(port) }, stdio: ["ignore", "pipe", "pipe"] });
      let output = "";
      child.stdout.on("data", chunk => { output += chunk; });
      child.stderr.on("data", chunk => { output += chunk; });
      const proxy = http.createServer((req, res) => {
        if (prefix && req.url === prefix) {
          res.writeHead(307, { Location: `${prefix}/` }).end();
          return;
        }
        if (!req.url.startsWith(`${prefix}/`)) {
          res.writeHead(404).end("Outside application prefix");
          return;
        }
        const upstream = http.request({
          hostname: "127.0.0.1", port,
          path: stripPrefix ? req.url.slice(prefix.length) : req.url,
          method: req.method, headers: req.headers,
        }, response => {
          res.writeHead(response.statusCode, response.headers);
          response.pipe(res);
        });
        upstream.on("error", error => { res.writeHead(502).end(String(error)); });
        req.pipe(upstream);
      });
      const page = await browser.newPage();
      const errors = [];
      const requests = [];
      page.on("pageerror", error => errors.push(String(error)));
      page.on("request", req => requests.push(req.url()));
      page.on("response", res => {
        // Missing feedback is the documented "not yet rated" state.
        if (res.status() >= 400 && !(res.status() === 404 && res.url().endsWith("/feedback"))) {
          errors.push(`${res.status()} ${res.url()}`);
        }
      });
      try {
        await new Promise((resolve, reject) => {
          child.stderr.on("data", () => { if (output.includes("Uvicorn running")) resolve(); });
          child.once("exit", code => reject(new Error(`Fixture exited ${code}: ${output}`)));
          child.once("error", reject);
          setTimeout(() => reject(new Error(`Fixture startup timed out: ${output}`)), 15000).unref();
        });
        port = Number(output.match(/Uvicorn running on http:\/\/127\.0\.0\.1:(\d+)/)[1]);
        proxy.listen(0, "127.0.0.1");
        await once(proxy, "listening");
        const origin = `http://127.0.0.1:${proxy.address().port}`;
        await page.goto(`${origin}${prefix || "/"}`);
        assert.equal(new URL(page.url()).pathname, `${prefix}/`);
        await page.getByLabel("Message input").waitFor();
        if (preset === "full") {
          await page.getByLabel("Message input").fill("Test prefix");
          await page.getByLabel("Message input").press("Enter");
          await page.getByText("Prefix test reply.", { exact: true }).waitFor();
          await page.context().setExtraHTTPHeaders({
            "x-agent-chat-subject": await page.evaluate(() => localStorage.getItem("agent-chat.anonymous-subject.v1")),
          });
          const threadsResponse = await page.request.get(`${origin}${prefix}/threads`);
          assert.equal(threadsResponse.status(), 200);
          const threads = await threadsResponse.json();
          assert.equal(threads.length, 1);
          // Wait for the browser's asynchronous transcript synchronization.
          const threadUrl = `${origin}${prefix}/threads/${threads[0].id}`;
          let messages = [];
          await expect.poll(async () => {
            messages = (await (await page.request.get(`${threadUrl}/messages`)).json()).messages;
            return messages.some(message => message.role === "assistant");
          }, { message: "Assistant transcript must synchronize" }).toBe(true).catch(error => {
            throw new Error(`${error}\nMessages: ${JSON.stringify(messages)}\nRequests: ${JSON.stringify(requests)}\n${output}`);
          });
          const message = messages.find(message => message.role === "assistant");
          const feedbackUrl = `${threadUrl}/messages/${message.id}/feedback`;
          assert.equal((await page.request.put(feedbackUrl, { data: { rating: "positive" } })).status(), 200);
          assert.equal((await page.request.get(feedbackUrl)).status(), 200);
          assert.equal((await page.request.delete(feedbackUrl)).status(), 200);
        }
        await page.reload();
        await page.getByLabel("Message input").waitFor();
        await page.goto(`${origin}${prefix}/admin/`);
        await page.getByRole("heading", { name: "Web RAG Admin", exact: true }).waitFor();
        await page.getByRole("link", { name: "Back to chat" }).click();
        await page.getByLabel("Message input").waitFor();
        assert.equal(new URL(page.url()).pathname, `${prefix}/`);
        assert.deepEqual(errors, [], output);
        assert(requests.some(url => url === `${origin}${prefix}/api/config`));
        assert(requests.some(url => url.includes(`${prefix}/_next/static/`)));
        assert(requests.every(url => !url.startsWith(origin) ||
          new URL(url).pathname === prefix ||
          new URL(url).pathname.startsWith(`${prefix}/`)), JSON.stringify(requests));
        results.push({ prefix: prefix || "/", preset, stripPrefix, status: "passed" });
      } finally {
        await page.close();
        proxy.closeAllConnections();
        await new Promise(resolve => proxy.close(resolve));
        if (child.exitCode === null && child.signalCode === null) {
          const exited = once(child, "exit");
          child.kill("SIGTERM");
          await exited;
        }
      }
    }
  }
} finally {
  await browser.close();
  console.log(JSON.stringify({ results }, null, 2));
}
