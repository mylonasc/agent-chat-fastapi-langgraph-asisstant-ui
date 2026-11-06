"use client";

import type { FC } from "react";
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import c from "react-syntax-highlighter/dist/esm/languages/prism/c";
import clojure from "react-syntax-highlighter/dist/esm/languages/prism/clojure";
import cpp from "react-syntax-highlighter/dist/esm/languages/prism/cpp";
import csharp from "react-syntax-highlighter/dist/esm/languages/prism/csharp";
import css from "react-syntax-highlighter/dist/esm/languages/prism/css";
import dart from "react-syntax-highlighter/dist/esm/languages/prism/dart";
import diff from "react-syntax-highlighter/dist/esm/languages/prism/diff";
import docker from "react-syntax-highlighter/dist/esm/languages/prism/docker";
import elixir from "react-syntax-highlighter/dist/esm/languages/prism/elixir";
import go from "react-syntax-highlighter/dist/esm/languages/prism/go";
import graphql from "react-syntax-highlighter/dist/esm/languages/prism/graphql";
import haskell from "react-syntax-highlighter/dist/esm/languages/prism/haskell";
import ini from "react-syntax-highlighter/dist/esm/languages/prism/ini";
import java from "react-syntax-highlighter/dist/esm/languages/prism/java";
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import jsx from "react-syntax-highlighter/dist/esm/languages/prism/jsx";
import kotlin from "react-syntax-highlighter/dist/esm/languages/prism/kotlin";
import less from "react-syntax-highlighter/dist/esm/languages/prism/less";
import lua from "react-syntax-highlighter/dist/esm/languages/prism/lua";
import makefile from "react-syntax-highlighter/dist/esm/languages/prism/makefile";
import markdown from "react-syntax-highlighter/dist/esm/languages/prism/markdown";
import markup from "react-syntax-highlighter/dist/esm/languages/prism/markup";
import objectivec from "react-syntax-highlighter/dist/esm/languages/prism/objectivec";
import perl from "react-syntax-highlighter/dist/esm/languages/prism/perl";
import php from "react-syntax-highlighter/dist/esm/languages/prism/php";
import powershell from "react-syntax-highlighter/dist/esm/languages/prism/powershell";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import r from "react-syntax-highlighter/dist/esm/languages/prism/r";
import ruby from "react-syntax-highlighter/dist/esm/languages/prism/ruby";
import rust from "react-syntax-highlighter/dist/esm/languages/prism/rust";
import sass from "react-syntax-highlighter/dist/esm/languages/prism/sass";
import scala from "react-syntax-highlighter/dist/esm/languages/prism/scala";
import scss from "react-syntax-highlighter/dist/esm/languages/prism/scss";
import sql from "react-syntax-highlighter/dist/esm/languages/prism/sql";
import swift from "react-syntax-highlighter/dist/esm/languages/prism/swift";
import toml from "react-syntax-highlighter/dist/esm/languages/prism/toml";
import tsx from "react-syntax-highlighter/dist/esm/languages/prism/tsx";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";
import yaml from "react-syntax-highlighter/dist/esm/languages/prism/yaml";
import oneDark from "react-syntax-highlighter/dist/esm/styles/prism/one-dark";

import type { SyntaxHighlighterProps } from "@assistant-ui/react-markdown";

import { cn } from "@/lib/utils";

const languages = {
  bash,
  c,
  clojure,
  cpp,
  csharp,
  css,
  dart,
  diff,
  docker,
  elixir,
  go,
  graphql,
  haskell,
  ini,
  java,
  javascript,
  json,
  jsx,
  kotlin,
  less,
  lua,
  makefile,
  markdown,
  markup,
  objectivec,
  perl,
  php,
  powershell,
  python,
  r,
  ruby,
  rust,
  sass,
  scala,
  scss,
  sql,
  swift,
  toml,
  tsx,
  typescript,
  yaml,
};

for (const [name, definition] of Object.entries(languages)) {
  SyntaxHighlighter.registerLanguage(name, definition);
}

// Common markdown fence names that do not match a registered grammar.
const aliases: Record<string, string> = {
  cjs: "javascript",
  cs: "csharp",
  "c#": "csharp",
  "c++": "cpp",
  dockerfile: "docker",
  htm: "markup",
  html: "markup",
  js: "javascript",
  json5: "json",
  jsonc: "json",
  kt: "kotlin",
  md: "markdown",
  mdx: "markdown",
  mjs: "javascript",
  "objective-c": "objectivec",
  objc: "objectivec",
  plaintext: "text",
  ps1: "powershell",
  py: "python",
  rb: "ruby",
  rs: "rust",
  sh: "bash",
  shell: "bash",
  text: "text",
  ts: "typescript",
  xml: "markup",
  yml: "yaml",
  zsh: "bash",
};

const registered = new Set(Object.keys(languages));

export function fenceLanguageFromNode(
  node: SyntaxHighlighterProps["node"],
): string | undefined {
  const className = node?.properties?.className;
  const classes = Array.isArray(className)
    ? className
    : typeof className === "string"
      ? [className]
      : [];
  for (const value of classes) {
    if (typeof value !== "string") continue;
    const match = /(?:^|\s)language-(\S+)/.exec(value);
    if (match) return match[1];
  }
  return undefined;
}

function resolveLanguage(language: string | undefined): {
  canonical: string;
  display: string;
} {
  const requested = (language ?? "").trim().toLowerCase().split(/\s+/)[0] ?? "";
  if (!requested || requested === "unknown") {
    return { canonical: "text", display: "text" };
  }
  const canonical = aliases[requested] ?? requested;
  if (registered.has(canonical)) return { canonical, display: canonical };
  return { canonical: "text", display: requested };
}

/**
 * Prism-based block renderer for chat Markdown. The explicit language imports
 * keep highlighting synchronous (streaming-friendly) while avoiding Prism's
 * entire language bundle. Unknown fences render as readable plain text.
 */
export const CodeBlock: FC<SyntaxHighlighterProps> = ({
  language,
  code,
  node,
}) => {
  // assistant-ui extracts the fence name with /\w+/, which truncates names
  // such as "c++" to "c". Recover the original class so aliases still work.
  const { canonical, display } = resolveLanguage(
    fenceLanguageFromNode(node) ?? language,
  );

  if (canonical === "text") {
    return (
      <pre
        className="aui-md-pre overflow-x-auto rounded-b-lg bg-[#282c34] p-4 font-mono text-sm leading-6 text-[#abb2bf]"
        data-language={display}
        data-highlighted="false"
      >
        <code>{code}</code>
      </pre>
    );
  }

  return (
    <SyntaxHighlighter
      language={canonical}
      style={oneDark}
      data-language={display}
      data-highlighted="true"
      customStyle={{
        margin: 0,
        borderRadius: "0 0 0.5rem 0.5rem",
        background: "#282c34",
        padding: "1rem",
        fontSize: "0.875rem",
        lineHeight: "1.6",
      }}
      codeTagProps={{
        className: cn("font-mono"),
        style: {
          background: "transparent",
          fontSize: "inherit",
          lineHeight: "inherit",
        },
      }}
    >
      {code}
    </SyntaxHighlighter>
  );
};
