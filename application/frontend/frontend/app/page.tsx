"use client";

import { useRuntimeConfig } from "@/hooks/use-runtime-config";

import { Assistant } from "./assistant";
import { MinimalAssistant } from "./minimal-assistant";

function ConfigLoading() {
  return (
    <main className="flex h-dvh items-center justify-center text-sm text-muted-foreground">
      Loading chat configuration…
    </main>
  );
}

export default function Home() {
  const { config, loaded } = useRuntimeConfig();

  // Wait for the runtime manifest (or its compiled fallback) so the first
  // paint already matches the deployment preset instead of flashing.
  if (!loaded) return <ConfigLoading />;

  if (config.ui_preset === "minimal") return <MinimalAssistant />;
  return <Assistant />;
}
