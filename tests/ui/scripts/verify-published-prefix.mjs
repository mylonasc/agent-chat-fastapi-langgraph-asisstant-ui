// Inspect an extracted published wheel without rebuilding its UI.
// node scripts/verify-published-prefix.mjs /path/to/extracted/agent_chat_minimal/web [...]
// Serves each unchanged export at / and behind a prefix-only static gateway.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { chromium } from "@playwright/test";

assert(process.argv.length > 2, "Pass extracted wheel web directories");
const browser = await chromium.launch({ headless: true });
const results = [];
try {
  for (const directory of process.argv.slice(2)) {
    const root = path.resolve(directory);
    for (const prefix of ["", "/platform/apps/chat"]) {
      const requests = [];
      const server = http.createServer(async (req, res) => {
        const pathname = new URL(req.url, "http://localhost").pathname;
        requests.push(pathname);
        if (!pathname.startsWith(`${prefix}/`)) {
          res.writeHead(404).end("Outside application prefix");
          return;
        }
        const relative = pathname.slice(prefix.length);
        if (relative === "/api/config") {
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ version: 1, ui_preset: "minimal", api_base: prefix }));
          return;
        }
        if (relative === "/agents") {
          res.setHeader("Content-Type", "application/json");
          res.end("[]");
          return;
        }
        const file = path.resolve(root, `.${relative.endsWith("/") ? `${relative}index.html` : relative}`);
        if (!file.startsWith(`${root}${path.sep}`)) {
          res.writeHead(403).end();
          return;
        }
        try {
          const content = await readFile(file);
          const types = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".woff2": "font/woff2" };
          res.setHeader("Content-Type", types[path.extname(file)] || "application/octet-stream");
          res.end(content);
        } catch {
          res.writeHead(404).end();
        }
      });
      await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
      const page = await browser.newPage();
      const failures = [];
      const pageErrors = [];
      page.on("response", response => {
        if (response.status() >= 400) failures.push({ path: new URL(response.url()).pathname, status: response.status() });
      });
      page.on("pageerror", error => pageErrors.push(String(error)));
      try {
        await page.goto(`http://127.0.0.1:${server.address().port}${prefix}/`);
        // Config is fetched in a React effect: unlike static DOM, it demonstrates client boot.
        await page.waitForFunction(() => performance.getEntriesByType("resource").some(entry => entry.name.endsWith("/api/config")), null, { timeout: 5000 }).catch(() => {});
        const clientBooted = requests.includes(`${prefix}/api/config`);
        const escapedAssets = failures.filter(item => item.path.startsWith("/_next/"));
        results.push({ directory: root, prefix: prefix || "/", clientBooted, escapedAssets, pageErrors });
        if (!prefix) assert(clientBooted, "Root control must boot the client");
        else {
          assert(!clientBooted, "Published prefix deployment unexpectedly boots; reassess the bug");
          assert(escapedAssets.length > 0, "Expected failed origin-root asset requests");
        }
      } finally {
        await page.close();
        server.closeAllConnections();
        await new Promise(resolve => server.close(resolve));
      }
    }
  }
} finally {
  await browser.close();
  console.log(JSON.stringify({ results }, null, 2));
}
