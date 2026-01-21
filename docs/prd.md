**Product Requirements Document**

**Social Listening App (V1) — Reddit-first, Location-aware, HITL**

**1\) Overview**  
A Python-based social listening app for a single small business that monitors public forum content (starting with Reddit) for service-intent posts within a target geography, captures posts \+ comments, and uses GenAI to flag relevant threads and draft suggested responses for human review and sending.

**2\) Goals**

* Identify **high-intent local leads** (e.g., “need a plumber”) from public threads.  
* Capture full **thread context** (post \+ comment thread \+ updates).  
* Apply a **two-stage filter**: keyword/rules first, GenAI second.  
* Provide a **human-in-the-loop dashboard** to review flagged threads and suggested responses.  
* Keep costs controlled via **delta-based thread evaluation** and a time window.

**3\) Non-goals (V1)**

* Auto-posting replies back to platforms  
* Multi-tenant / multi-business separation  
* Private groups / authenticated sources (Facebook Groups, etc.)  
* Real-time streaming (V1 runs on a schedule)

**4\) Primary User**

* A single small business owner / office manager (e.g., plumber, electrician, HVAC) who can only serve a defined local area.

**5\) Key Use Cases**

1. Business sets keywords and service area.  
2. App runs every N hours; ingests new Reddit threads/comments matching target subs or search terms.  
3. App flags relevant threads and generates a suggested reply.  
4. User reviews flagged items, edits response, and manually posts on the source platform.

**6\) Assumptions**

* V1 sources are public and accessible without authentication (Reddit).  
* Location filtering will be approximate and based on user-config \+ inferred signals (subreddit, text mentions).  
* GenAI evaluation is **per thread** and run on **thread deltas** (new comments since last evaluation).

**7\) Functional Requirements**  
**7.1 Ingestion & Scheduling**

* Run on a configurable schedule (default: every 2 hours).  
* Each run produces a run\_id with status, timestamps, and summary counts.  
* Ingest:  
  * New posts/threads  
  * New comments on known threads  
* Support pausing/resuming collectors.

**7.2 Normalization & Storage (SQLite)**  
Store normalized entities:

* Threads (post metadata \+ text)  
* Comments  
* Run logs  
* Keyword hits  
* GenAI decisions (binary flag)  
* Suggested responses (drafts)  
* Thread state (watching, active window, last\_checked, closed)

**7.3 Keyword/Rules Stage (Cheap Filter)**

* Configurable keyword sets:  
  * Service keywords (e.g., plumber, leak, water heater)  
  * Intent phrases (e.g., “need”, “recommend”, “emergency”)  
  * Negative keywords (e.g., “job”, “hiring” if unwanted)  
* Evaluate **only new content** (new threads \+ new comments) each run.  
* When a thread gets its first hit → set watching=1 for the remainder of its active window.

**7.4 Location Filtering**

* Business defines:  
  * Primary service area (e.g., city/ZIP list or radius from lat/long)  
  * Optional exclusions (states/cities to ignore)  
* Location inference signals (V1, heuristic):  
  * Subreddit (e.g., r/Atlanta, r/DecaturGA)  
  * Text mentions (city/ZIP/neighborhood)  
  * Optional user flair if available  
* Location filter outcomes:  
  * in\_area \= true/false/unknown  
  * Threads with unknown may be optionally included (config).

**7.5 GenAI Stage (Thread-level, Conditional)**  
Trigger GenAI when:

* New thread/comment content has keyword hits **OR**  
* watching=1 and new comments arrive within the active window

GenAI tasks:

* Binary relevance flag: relevant \= 0/1  
* If relevant: generate a suggested response draft (separate output field)  
* Output must include:  
  * thread\_id  
  * relevant  
  * draft\_response (if relevant)  
  * short\_reason (1–2 sentences, optional but helpful for review)

Cost controls:

* Only send **delta content** (new comments since last GenAI check), plus a short thread summary/seed (post \+ top context).  
* Active window: configurable (default 5 days from thread creation)  
* Max GenAI evaluations per thread: configurable (default 5\)

**7.6 De-duplication of Flagging**

* “Flag” is thread-level (once flagged, stays flagged unless manually dismissed).  
* Store detections keyed by:  
  * thread\_id \+ comment\_id (or stable text hash) \+ detection\_type  
* On re-eval, only create new detections for **newly flagged** comments/deltas.

**7.7 Dashboard (HITL)**  
Core views:

* **Flagged Queue**: threads marked relevant (sortable by recency, keyword category, location confidence)  
* **Thread Detail**:  
  * Original post \+ comment thread (chronological)  
  * Source link (click-out)  
  * Location inference \+ reason  
  * Draft response (editable)  
  * Actions: Approve (copy-ready), Dismiss, Snooze, Add Note  
* **Config**:  
  * Keywords, exclusions, active window, schedule, subreddit list, in\_area handling

V1 “send” behavior:

* No posting integration. Provide:  
  * “Copy response” button  
  * Link to open thread on platform

**8\) User Stories (Examples)**

* As a plumber, I want to see only threads likely within my metro area so I don’t waste time on out-of-state requests.  
* As an owner, I want suggested replies I can edit quickly so I can respond faster than competitors.  
* As a user, I want to dismiss irrelevant threads so they don’t keep showing up.

**9\) Success Metrics (V1)**

* Precision of flagged threads (target: ≥70% “useful” per human review)  
* Time-to-review per thread (median)  
* Cost per useful lead (GenAI tokens/run)  
* Coverage: number of relevant local threads found per week (baseline \+ improvement)

**10\) Risks & Constraints**

* Platform constraints / API limits / scraping brittleness (especially outside Reddit)  
* Location inference ambiguity (mitigate with “unknown” state \+ user config)  
* Noise/false positives from keyword-only triggers (mitigate with negatives \+ GenAI)  
* Data retention: store minimal PII; keep only what’s needed for review

**11\) Rollout Plan**  
**Milestone 1 (MVP ingestion):** Reddit collector, normalization, SQLite, run logs  
**Milestone 2 (Filtering):** keyword rules \+ watching logic \+ active window  
**Milestone 3 (GenAI):** thread-level delta eval \+ binary flag \+ drafts \+ dedupe detections  
**Milestone 4 (Dashboard):** flagged queue \+ thread detail \+ config UI  
**Milestone 5 (Quality):** evaluation set, tuning keywords/prompt pack, cost caps  
