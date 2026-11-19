import { normalizeAgents } from "@/lib/api/normalize";
import type { AgentListing } from "@/lib/api/types";
import type { HttpTransport } from "@/lib/api/transport";

/** Available agent ids for the starter-page affordance. */
export class AgentsService {
  constructor(private readonly transport: HttpTransport) {}

  async list(): Promise<AgentListing> {
    return normalizeAgents(await this.transport.request<unknown>("/agents"));
  }
}
