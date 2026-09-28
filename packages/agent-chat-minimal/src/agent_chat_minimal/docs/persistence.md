# Persistence Domain

The canonical package separates chat persistence into four framework-independent
layers: dataclass models in `domain`, async protocols in `ports`, authorization
and lifecycle rules in `services`, and implementations in `adapters`. These
modules do not depend on FastAPI, LangGraph, assistant-stream, or SQLAlchemy.
Existing HTTP routes and legacy thread stores remain unchanged until PUIR-07.

Every service call receives a trusted `Principal`. Ownership is always derived
from `Principal.subject`; a `user_id` supplied by a request body or query is
never an authorization input. A missing entity raises `NotFoundError`, an
entity belonging to another principal raises `ForbiddenError`, and duplicate,
archived-mutation, or concurrent-change conditions raise `ConflictError`.

Sessions have stable IDs, aware UTC timestamps, and explicit `active` or
`archived` status. Archiving is reversible and preserves transcripts and
feedback. Archived sessions remain readable but cannot be renamed or receive
new messages or feedback. Messages have stable IDs and a positive,
session-local sequence. Their payload is transport-neutral so an adapter can
persist complete UI message data without importing a UI protocol.

There is at most one feedback record per `(session_id, message_id)`. Upsert
preserves its ID and creation timestamp; submitting the same rating, optional
comment, and metadata again returns the existing record unchanged. Ratings are
`positive` or `negative`.

`SessionService.delete` verifies ownership, invokes an optional
`CheckpointDeleter`, then removes feedback, transcript entries, and session
metadata. The checkpoint port deliberately has no implementation here: PUIR-06
owns the separately managed LangGraph checkpoint adapter. SQL-backed adapters
should execute application-store deletion in one transaction; SQLite support is
deferred to PUIR-05.

`InMemoryRepositories` supplies reference adapters for composition and fast
tests. New repository adapters should run the reusable repository contract tests
before being connected to the services.
