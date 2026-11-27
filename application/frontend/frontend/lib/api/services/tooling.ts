import type { HttpTransport } from "../transport";

export type ToolValue = string | number | boolean;
export type ToolField = {
  label: string;
  type: "integer" | "boolean" | "enum";
  minimum: number | null;
  maximum: number | null;
  choices: string[];
  scope: "conversation" | "admin" | "startup";
  effect: "next_turn" | "reindex";
};
export type ManagedTool = {
  id: string;
  title: string;
  available: boolean;
  selected: boolean;
  enabled: boolean;
  config: Record<string, ToolValue>;
  fields: Record<string, ToolField>;
};
export type ToolSnapshot = {
  revision: number;
  global_revision: number;
  toolsets: string[];
  catalog: {
    id: string;
    title: string;
    description: string;
    available: boolean;
    selected: boolean;
    tools: ManagedTool[];
  }[];
};
export type ToolUpdate = {
  revision: number;
  global_revision: number;
  toolsets: string[];
  tools: Record<
    string,
    { enabled: boolean; config: Record<string, ToolValue> }
  >;
};

export class ToolingService {
  constructor(private readonly transport: HttpTransport) {}
  catalog() {
    return this.transport.request<ToolSnapshot>("/tooling");
  }
  admin(token: string) {
    return this.transport.request<ToolSnapshot>("/tooling/admin", {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  }
  saveAdmin(body: ToolUpdate, token: string) {
    return this.transport.request<ToolSnapshot>("/tooling/admin", {
      method: "PUT",
      body,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  }
  thread(id: string) {
    return this.transport.request<ToolSnapshot>(
      `/threads/${encodeURIComponent(id)}/tools`,
    );
  }
  saveThread(id: string, body: ToolUpdate) {
    return this.transport.request<ToolSnapshot>(
      `/threads/${encodeURIComponent(id)}/tools`,
      { method: "PUT", body },
    );
  }
}
