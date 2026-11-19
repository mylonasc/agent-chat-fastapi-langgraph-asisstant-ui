import { defineConfig } from "@playwright/test";
import path from "node:path";

/**
 * Capability-matrix e2e: one fake backend per deployment manifest.
 *
 * Each scenario runs the *same* static bundle with different `/api/config`
 * answers, proving the UI adapts at runtime instead of at build time. The
 * ports are fixed so the spec can address each scenario directly.
 */

const python = process.env.E2E_PYTHON ?? "python3";
const helper = path.join(__dirname, "helpers", "fake_backend.py");

function server(port: number, env: Record<string, string>) {
  return {
    command: `${python} ${helper}`,
    cwd: path.join(__dirname, ".."),
    url: `http://localhost:${port}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      E2E_PORT: String(port),
      E2E_UI_PRESET: "full",
      ...env,
    },
  };
}

export default defineConfig({
  testDir: __dirname,
  testMatch: /capabilities\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: {
    timeout: 30_000,
  },
  reporter: [["list"]],
  webServer: [
    // The assistant is turned off entirely.
    server(18080, {
      E2E_FEATURES: "agents,threads,transcripts",
    }),
    // Full preset without the thread-list capability: one conversation.
    server(18081, {
      E2E_FEATURES: "agents,assistant,transcripts",
    }),
    // Conversation persists in memory only; no transcript API.
    server(18082, {
      E2E_FEATURES: "agents,assistant,threads",
    }),
    // Admin header action present; Web RAG remains unavailable.
    server(18083, {
      E2E_FEATURES: "agents,assistant,threads,transcripts",
      E2E_TOOLS: "admin",
    }),
    // Both controls are exposed, but the fake backend intentionally has no
    // RAG routes so the recoverable admin error state can be inspected.
    server(18084, {
      E2E_FEATURES: "agents,assistant,threads,transcripts",
      E2E_TOOLS: "admin,web_rag",
    }),
  ],
});
