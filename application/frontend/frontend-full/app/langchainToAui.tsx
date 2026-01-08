/**
 * Converts LangChain/LangGraph message dumps (from Python m.model_dump())
 * into assistant-ui's ThreadMessageLike shape:
 *
 *   { id, role, content: [{ type:"text", text }] }
 */

import type { ThreadMessageLike } from "@assistant-ui/react";

function getId(m: any): string {
  return (
    m?.id ||
    m?.kwargs?.id ||
    m?.additional_kwargs?.id ||
    (typeof crypto !== "undefined" ? crypto.randomUUID() : String(Math.random()))
  );
}

function extractTextContent(content: any): string {
  if (content == null) return "";

  if (typeof content === "string") return content;

  if (Array.isArray(content)) {
    const texts = content
      .map((p) => {
        if (typeof p === "string") return p;
        if (p?.type === "text" && typeof p?.text === "string") return p.text;
        if (typeof p?.text === "string") return p.text;
        if (typeof p?.content === "string") return p.content;
        return "";
      })
      .filter(Boolean);

    return texts.join("");
  }

  if (typeof content === "object") {
    if (typeof (content as any).text === "string") return (content as any).text;
    if (typeof (content as any).content === "string") return (content as any).content;
    try {
      return JSON.stringify(content);
    } catch {
      return String(content);
    }
  }

  return String(content);
}

function lcTypeToRole(t: string | undefined): ThreadMessageLike["role"] {
  const type = (t || "").toLowerCase();

  if (type === "human" || type === "user") return "user";
  if (type === "ai" || type === "assistant") return "assistant";
  if (type === "system") return "system";
  if (type === "tool") return "tool";

  if (type.includes("human")) return "user";
  if (type.includes("ai")) return "assistant";

  return "assistant";
}

export function langchainToAuiMessages(lcMessages: any[]): ThreadMessageLike[] {
  if (!Array.isArray(lcMessages)) return [];

  return lcMessages
    .map((m) => {
      const id = getId(m);
      const role = lcTypeToRole(m?.type);

      const rawContent =
        m?.content ??
        m?.kwargs?.content ??
        m?.kwargs?.kwargs?.content ??
        m?.additional_kwargs?.content;

      const text = extractTextContent(rawContent).trim();
      if (!text) return null;

      // ✅ assistant-ui expects `content`, NOT `parts`
      return {
        id,
        role,
        content: [{ type: "text", text }],
      } satisfies ThreadMessageLike;
    })
    .filter(Boolean) as ThreadMessageLike[];
}
