import { expect, test } from "@playwright/test";

import {
  graphMarkerId,
  normalizeGraphResult,
} from "@/features/graph/normalize";
import {
  normalizeSourceIndexingResult,
  retrievalSourceItems,
} from "@/features/rag/source-normalize";

test("graph output validation drops malformed and dangling entries", () => {
  expect(
    normalizeGraphResult({
      directed: true,
      nodes: [{ id: "a", weight: 120 }, { nope: true }, { id: "b" }],
      edges: [
        { source: "a", target: "b", weight: "25" },
        { source: "a", target: "missing" },
      ],
    }),
  ).toEqual({
    directed: true,
    nodes: [
      { id: "a", label: undefined, weight: 100 },
      { id: "b", label: undefined, weight: undefined },
    ],
    edges: [
      {
        source: "a",
        target: "b",
        label: undefined,
        weight: 25,
      },
    ],
  });
  expect(normalizeGraphResult("not json")).toBeNull();
  expect(normalizeGraphResult({ nodes: [], edges: [] })).toBeNull();
});

test("graph instances receive fragment-safe distinct marker ids", () => {
  const first = graphMarkerId(":r1:");
  const second = graphMarkerId(":r2:");
  expect(first).toBe("graph-arrow-r1");
  expect(second).toBe("graph-arrow-r2");
  expect(first).not.toBe(second);
});

test("RAG tool variants normalize into one source view model", () => {
  const normalized = normalizeSourceIndexingResult({
    rag: {
      indexing: {
        job_id: "job-1",
        status: "running",
        total_urls: "3",
        completed_urls: 1,
        parser: { pdf_parser: "docling", docling_device: "cuda" },
        items: [
          { url: "https://valid.test", status: "complete", documents: 2 },
          { status: "missing-url" },
        ],
      },
      sources: ["https://valid.test", 4],
      chunks: ["chunk", null],
    },
    index_status: { source_count: 4, document_count: 7 },
  });

  expect(normalized.jobId).toBe("job-1");
  expect(normalized.total).toBe(3);
  expect(normalized.parserName).toBe("docling");
  expect(normalized.sources).toHaveLength(1);
  expect(normalized.retrievalSources).toEqual(["https://valid.test"]);
  expect(normalized.chunks).toEqual(["chunk"]);
  expect(normalized.indexedDocumentCount).toBe(7);
});

test("retrieval source normalization de-duplicates URLs", () => {
  expect(retrievalSourceItems(["https://a.test", "https://a.test"])).toEqual([
    expect.objectContaining({ url: "https://a.test", status: "retrieved" }),
  ]);
});
