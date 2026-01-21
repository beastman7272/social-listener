# agents.md

## Purpose

This file defines **how Codex should operate** when working on this repository.

Codex is acting as a **disciplined implementation assistant**, not a product designer or architect. All product decisions are already made and documented elsewhere.

---

## Authoritative Documents (Source of Truth)

The following documents in `./docs/` are **authoritative** and must not be re-interpreted, extended, or contradicted:

* Product Requirements Document (PRD)
* Architecture Overview
* Data Model / SQLite Schema
* Classification Spec
* Wireframes

If there is ambiguity, Codex must **defer and ask**, not invent.

---

## Project Scope (V1 Only)

Codex must implement **V1 only**, exactly as specified.

Explicit non-goals:

* No auto-posting to platforms
* No multi-tenant support
* No real-time streaming
* No platforms beyond Reddit
* No speculative “future-proofing”

---

## Tech Stack (Non-Negotiable)

* Python
* Flask (server-rendered, Jinja templates)
* SQLite (local file, path via `instance/`)
* PRAW for Reddit ingestion
* OpenAI API for GenAI evaluation
* No frontend frameworks (React, Vue, etc.)

---

## Architectural Rules

* **Pipeline-first design**: ingestion → normalization → storage → rules → GenAI → HITL
* **Thread-centric**: a thread = post + all comments
* **Delta-based evaluation**: only new content triggers re-processing
* **Two-stage decisioning**:

  * Cheap rules first
  * GenAI only when policy allows
* **HITL is mandatory**: GenAI never auto-acts

---

## Code Organization Rules

Follow this structure unless explicitly instructed otherwise:

```
app/
  routes/        # Flask route handlers (UI + API)
  services/      # Business logic (rules, GenAI, orchestration)
  collectors/    # Platform-specific ingestion (Reddit V1)
  repo/          # SQLite persistence layer (no business logic)
templates/
static/
scripts/
instance/
docs/
```

Rules:

* Route handlers should be thin
* SQL must be encapsulated in `repo/`
* Services must not embed raw SQL
* Collectors must not decide relevance

---

## Database Rules

* SQLite schema must match the Data Model exactly
* No silent schema changes
* Add migrations deliberately
* Thread-level flags are **sticky**
* De-duplication rules must be enforced as specified

---

## GenAI Rules

* GenAI is expensive; never call it casually
* Only trigger GenAI per Classification Spec
* Always log:

  * prompt version
  * model
  * timestamps
  * token counts (if available)
* GenAI output must be structured and validated
* Draft responses are suggestions only (HITL)

---

## UI / UX Rules

* Server-rendered HTML using Jinja
* Wireframes are authoritative
* Every flagged thread must:

  * link to original source
  * allow one-click copy of draft
* No posting integrations in V1
* Optimize for fast triage, not polish

---

## Working Style Expectations

* Prefer clarity over abstraction
* Avoid clever patterns unless explicitly requested
* Implement incrementally, ticket-by-ticket
* Do not bundle unrelated changes
* Ask before refactoring

---

## When in Doubt

If Codex encounters:

* Conflicting guidance
* Missing detail
* Ambiguity that affects behavior

➡️ **Stop and ask the human before proceeding.**
