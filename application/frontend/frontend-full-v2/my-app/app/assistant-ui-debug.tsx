"use client";

export const AUI_DEBUG = true;

export function dbg(tag: string, payload?: any) {
  if (!AUI_DEBUG) return;
  console.log(`%c${tag}`, "color:#7c3aed;font-weight:700", payload ?? "");
}
export function warn(tag: string, payload?: any) {
  if (!AUI_DEBUG) return;
  console.warn(`%c${tag}`, "color:#d97706;font-weight:700", payload ?? "");
}
export function err(tag: string, payload?: any) {
  if (!AUI_DEBUG) return;
  console.error(`%c${tag}`, "color:#dc2626;font-weight:700", payload ?? "");
}

export function describeObject(name: string, obj: any) {
  const keys = Object.keys(obj ?? {});
  const types: Record<string, string> = {};
  for (const k of keys) {
    const v = obj?.[k];
    types[k] =
      v == null
        ? String(v)
        : Array.isArray(v)
          ? "array"
          : typeof v === "function"
            ? "function"
            : typeof v;
  }
  dbg(`[describe:${name}]`, { keys, types });
}
