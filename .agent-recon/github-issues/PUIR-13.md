Parent: #22

Priority: P1

## Why

The packaged full UI currently exposes nonfunctional RAG/admin/share features,
while attachments and specialized tools also lack complete backend contracts.
Optional features need explicit capability boundaries.

## Implementation

- Gate RAG, admin, sharing, attachments, and specialized tool renderers using
  runtime capabilities.
- Make RAG/admin an optional backend module and dependency extra.
- Require authorization for admin/config/download routes.
- Hide sharing until a real public-session API and `/full`-aware route exist.
- Hide attachments until transport, storage, limits, and security are complete.
- Define a schema-driven tool renderer registration extension point.

## Acceptance Criteria

- Baseline full preset has no broken controls or background polling.
- Disabled APIs return explicit JSON 404/501 responses.
- Admin data/actions require an authorized principal.
- Optional RAG installation and activation are documented and tested.
- Unknown tools render safely through the generic fallback.

## Dependencies

- PUIR-08
- PUIR-09
- PUIR-10
