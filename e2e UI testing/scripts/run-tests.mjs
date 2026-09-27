import { spawn } from "node:child_process";

const timestamp = new Date().toISOString().replaceAll(":", "-").replace(".", "-");
const runId = process.env.E2E_RUN_ID ?? timestamp;

console.log(`E2E screenshot run: screenshots/${runId}`);

const child = spawn("pnpm", ["exec", "playwright", "test", ...process.argv.slice(2)], {
  env: { ...process.env, E2E_RUN_ID: runId },
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code ?? 1;
});
