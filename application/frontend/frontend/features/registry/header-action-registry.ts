import { isAdminEnabled } from "@/lib/capabilities";

import type { HeaderActionRegistration } from "./types";

/**
 * Header navigation actions.
 *
 * Every entry must point at an implemented route backed by a real API. The
 * sharing action was removed because no share endpoint or route exists;
 * re-add it only together with the backend contract.
 */
export const HEADER_ACTION_REGISTRY: readonly HeaderActionRegistration[] = [
  {
    id: "tooling",
    isEnabled: (config) => Boolean(config.tooling?.enabled),
    label: "Manage toolsets",
    href: "/toolsets",
  },
  {
    id: "admin",
    isEnabled: isAdminEnabled,
    label: "Admin",
    href: "/admin",
  },
];
