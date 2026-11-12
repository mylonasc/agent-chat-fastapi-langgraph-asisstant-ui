// Run against an installed wheel/sdist, never the dev server or source PYTHONPATH:
// UI_PYTHON=/path/to/venv/bin/python node scripts/verify-prefix.mjs
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import http from "node:http";
import { fileURLToPath } from "node:url";
import { chromium, expect } from "@playwright/test";

assert(process.env.UI_PYTHON, "Set UI_PYTHON to an installed-artifact environment");
const browser = await chromium.launch({ headless: true });
const results = [];
try {
  for (const prefix of ["", "/chat", "/platform/apps/chat"]) {
    for (const preset of ["minimal", "full"]) {
      for (const stripPrefix of [true, false]) {
        const child = spawn(process.env.UI_PYTHON, [fileURLToPath(new URL("./prefix-server.py", import.meta.url))], {
          env: { ...process.env, PYTHONPATH: "", BASE_PATH: prefix, UI_PRESET: preset },
          stdio: ["ignore", "pipe", "pipe"],
        });
        let output = "";
        child.stdout.on("data", chunk => { output += chunk; });
        child.stderr.on("data", chunk => { output += chunk; });
        let upstreamPort;
        const proxy = http.createServer((req, res) => {
          if (prefix && req.url === prefix) {
            res.writeHead(307, { Location: `${prefix}/` }).end();
          } else if (!req.url.startsWith(`${prefix}/`)) {
            res.writeHead(404).end("Outside application prefix");
          } else {
            const upstream = http.request({
              hostname: "127.0.0.1", port: upstreamPort,
              path: stripPrefix ? req.url.slice(prefix.length) : req.url,
              method: req.method, headers: req.headers,
            }, response => {
              res.writeHead(response.statusCode, response.headers);
              response.pipe(res);
            });
            upstream.on("error", error => res.writeHead(502).end(String(error)));
            req.pipe(upstream);
          }
        });
        const page = await browser.newPage();
        const errors = [];
        const requests = [];
        page.on("pageerror", error => errors.push(String(error)));
        page.on("requestfailed", request => {
          // Navigating/unmounting cancels document probes and React API effects.
          if (request.failure()?.errorText === "net::ERR_ABORTED") return;
          errors.push(`${request.url()}: ${request.failure()?.errorText}`);
        });
        page.on("request", request => requests.push(request.url()));
        page.on("response", response => {
          // Absence of a rating is represented by 404, not a transport error.
          if (response.status() >= 400 && !(response.status() === 404 && response.url().endsWith("/feedback"))) {
            errors.push(`${response.status()} ${response.url()}`);
          }
        });
        try {
          upstreamPort = await new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error(`Startup timeout: ${output}`)), 20000);
            const inspect = () => {
              const match = output.match(/Uvicorn running on http:\/\/127\.0\.0\.1:(\d+)/);
              if (match) { clearTimeout(timer); resolve(Number(match[1])); }
            };
            child.stderr.on("data", inspect);
            child.once("error", error => { clearTimeout(timer); reject(error); });
            child.once("exit", code => { clearTimeout(timer); reject(new Error(`Fixture exited ${code}: ${output}`)); });
          });
          proxy.listen(0, "127.0.0.1");
          await once(proxy, "listening");
          const origin = `http://127.0.0.1:${proxy.address().port}`;
          await page.goto(`${origin}${prefix || "/"}`);
          assert.equal(new URL(page.url()).pathname, `${prefix}/`);
          const composer = page.getByLabel("Message input");
          await composer.fill("Test prefixed chat");
          await composer.press("Enter");
          await page.getByText("Prefix test reply.", { exact: true }).waitFor();
          if (preset === "full") {
            await page.context().setExtraHTTPHeaders({
              "x-agent-chat-subject": await page.evaluate(() => localStorage.getItem("agent-chat.anonymous-subject.v1")),
            });
            const response = await page.request.get(`${origin}${prefix}/threads`);
            assert.equal(response.status(), 200);
            const threads = await response.json();
            assert.equal(threads.length, 1);
            const threadUrl = `${origin}${prefix}/threads/${threads[0].id}`;
            let messages;
            await expect.poll(async () => {
              messages = (await (await page.request.get(`${threadUrl}/messages`)).json()).messages;
              return messages.some(message => message.role === "assistant");
            }).toBe(true);
            const message = messages.find(message => message.role === "assistant");
            const feedbackUrl = `${threadUrl}/messages/${message.id}/feedback`;
            assert.equal((await page.request.put(feedbackUrl, { data: { rating: "positive" } })).status(), 200);
            assert.equal((await page.request.get(feedbackUrl)).status(), 200);
            assert.equal((await page.request.delete(feedbackUrl)).status(), 200);
          }
          await Promise.all([
            page.waitForResponse(response => response.url() === `${origin}${prefix}/api/config`),
            page.reload(),
          ]);
          await expect(composer).toBeVisible();
          await page.goto(`${origin}${prefix}/admin`);
          await page.getByRole("heading", { name: "Web RAG Admin", exact: true }).waitFor();
          await page.getByRole("link", { name: "Back to chat" }).click();
          await expect(composer).toBeVisible();
          assert.equal(new URL(page.url()).pathname, `${prefix}/`);
          assert(requests.includes(`${origin}${prefix}/api/config`));
          assert(requests.some(url => url.includes(`${prefix}/_next/static/`)));
          assert(requests.every(url => !url.startsWith(origin) || new URL(url).pathname === prefix || new URL(url).pathname.startsWith(`${prefix}/`)), JSON.stringify(requests));
          assert.deepEqual(errors, [], output);
          results.push({ prefix: prefix || "/", preset, stripPrefix, status: "passed" });
        } catch (error) {
          throw new Error(`${JSON.stringify({ prefix, preset, stripPrefix, errors, requests })}\n${output}`, { cause: error });
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
  }
} finally {
  await browser.close();
  console.log(JSON.stringify({ results }, null, 2));
}
