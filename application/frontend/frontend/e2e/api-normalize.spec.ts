import { expect, test } from "@playwright/test";

import { parseRuntimeConfig } from "@/lib/runtime-config";

import { ApiError } from "../lib/api/errors";
import {
  normalizeAgents,
  normalizeFeedback,
  normalizeRagJob,
  normalizeRagPage,
  normalizeRagStatus,
  normalizeThreadList,
  normalizeThreadResponse,
  normalizeTranscript,
} from "../lib/api/normalize";

function expectMalformed(run: () => unknown, what: string) {
  let caught: unknown;
  try {
    run();
  } catch (error) {
    caught = error;
  }
  expect(caught).toBeInstanceOf(ApiError);
  expect((caught as ApiError).code).toBe("malformed_response");
  expect((caught as ApiError).message).toContain(what);
}

test("thread lists reject a non-array envelope", () => {
  expectMalformed(() => normalizeThreadList({ threads: [] }), "thread list");
});

test("thread lists skip malformed entries but keep valid ones", () => {
  const threads = normalizeThreadList([
    { id: "thread-1", title: "Kept", is_archived: false, user_id: "u" },
    { title: "Missing id" },
    null,
    "not a thread",
    { id: "thread-2" },
  ]);
  expect(threads).toEqual([
    { id: "thread-1", title: "Kept", is_archived: false, user_id: "u" },
    { id: "thread-2", title: "New Chat", is_archived: false, user_id: "" },
  ]);
});

test("a single thread response rejects a missing id", () => {
  expectMalformed(() => normalizeThreadResponse({ title: "No id" }), "thread");
});

test("transcripts reject an envelope without a messages array", () => {
  expectMalformed(() => normalizeTranscript({ message: [] }), "transcript");
});

test("transcripts skip non-object messages", () => {
  const transcript = normalizeTranscript({
    messages: [{ id: "m1", role: "user", content: [] }, 42, null],
  });
  expect(transcript.messages).toEqual([
    { id: "m1", role: "user", content: [] },
  ]);
});

test("feedback rejects an unknown rating", () => {
  expectMalformed(
    () =>
      normalizeFeedback({
        id: "f1",
        thread_id: "t1",
        message_id: "m1",
        rating: "meh",
      }),
    "feedback",
  );
});

test("feedback normalizes optional fields", () => {
  const feedback = normalizeFeedback({
    id: "f1",
    thread_id: "t1",
    message_id: "m1",
    rating: "positive",
    comment: 7,
    metadata: null,
  });
  expect(feedback).toMatchObject({
    id: "f1",
    rating: "positive",
    comment: null,
    metadata: {},
    created_at: "",
  });
});

test("agents reject a non-object envelope and drop non-string ids", () => {
  expectMalformed(() => normalizeAgents(["a", "b"]), "agent list");
  expect(normalizeAgents({ agents: ["a", 3, "b"], default: 1 })).toEqual({
    agents: ["a", "b"],
    default: null,
  });
});

test("RAG status defaults missing index and jobs", () => {
  expect(normalizeRagStatus({})).toEqual({ index: {}, jobs: [] });
  expectMalformed(() => normalizeRagStatus([]), "index status");
});

test("RAG status normalizes jobs and their source items", () => {
  const status = normalizeRagStatus({
    index: { document_count: 4, source_count: "not a number", is_empty: false },
    jobs: [
      {
        job_id: "job-1",
        status: "running",
        total_urls: 2,
        items: [
          { url: "https://example.com/a", status: "completed", chunks: 3 },
          { status: "queued" },
        ],
      },
      { status: "running" },
    ],
  });
  expect(status.index).toEqual({
    document_count: 4,
    source_count: undefined,
    is_empty: false,
    user_id: undefined,
    base_path: undefined,
    has_faiss: undefined,
    has_bm25: undefined,
    raw_sources_count: undefined,
  });
  expect(status.jobs).toHaveLength(1);
  expect(status.jobs[0]?.items).toEqual([
    {
      url: "https://example.com/a",
      status: "completed",
      chunks: 3,
      stage: undefined,
      documents: undefined,
      parser: undefined,
      error: null,
    },
  ]);
});

test("RAG jobs reject a missing job id and accept the legacy sources key", () => {
  expect(normalizeRagJob({ status: "running" })).toBeNull();
  expect(
    normalizeRagJob({
      job_id: "job-2",
      sources: [{ url: "https://example.com/b" }],
    })?.items,
  ).toHaveLength(1);
});

test("RAG pages reject a missing items array", () => {
  expectMalformed(() => normalizeRagPage({ total: 0 }), "index page");
  expect(normalizeRagPage({ items: [{ id: 1 }, "bad"] })).toEqual({
    total: 1,
    offset: 0,
    limit: 1,
    items: [{ id: 1 }],
  });
});

test("runtime config preserves an explicitly unavailable status endpoint", () => {
  const config = parseRuntimeConfig({
    tools: { web_rag: { enabled: true, status_path: null } },
  });

  expect(config.tools.web_rag).toEqual({ enabled: true, status_path: null });
});
