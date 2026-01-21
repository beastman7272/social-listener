  
**Architecture Overview (V1)**

**Social Listening App — Reddit-first, Location-aware, Thread-level GenAI, HITL**

**1\) Architecture principles**

* **Pipeline-first**: ingest → normalize → store → filter → GenAI → dashboard.  
* **Two-stage decisioning**: cheap rules run often; GenAI runs only when justified.  
* **Thread-centric**: treat a Reddit post \+ all comments as a **thread**; classify **per thread**, using **deltas**.  
* **Pluggable collectors**: Reddit is V1, but interfaces are designed to add X/Craigslist/Yelp later.  
* **Audit-lite**: keep the **source thread URL** and decision artifacts (run\_id, timestamps, prompt version).

---

**2\) Component diagram (conceptual)**  
**Scheduler**  
→ **Collector (Reddit)**  
→ **Normalizer**  
→ **SQLite Repository**  
→ **Rule Engine (keywords/location)**  
→ **Thread Watcher / Re-eval Policy**  
→ **GenAI Evaluator**  
→ **Draft Response Generator**  
→ **Dashboard API**  
→ **Web Dashboard (HITL UI)**  
Cross-cutting:

* **Run Logger & Metrics**  
* **Error handling / Retry Queue**  
* **Config Manager**

---

**3\) Core components and responsibilities**  
**A) Scheduler / Orchestrator**

* Triggers a “run” every N hours (default: 2).  
* Creates a run\_id, sets run status (running/success/fail), and captures counters.  
* Calls pipeline stages in order.  
* Enforces global cost/time caps per run.

**Key outputs**

* run\_id, run timestamps, status, ingest counts, GenAI calls, errors.

---

**B) Collector (Reddit V1)**

* Fetches new/updated threads from configured sources:  
  * Subreddit list (geo proxies like r/Atlanta, r/DecaturGA, etc.)  
  * Optional search queries (service keywords)  
* Pulls:  
  * Thread/post metadata (id, title, body, author, created\_utc, url)  
  * Comments (id, body, created\_utc, parent\_id, depth if available)  
* Supports pagination and incremental collection.

**Key design decision**

* Collector should return **raw platform objects** \+ stable IDs; it should not decide relevance.

---

**C) Normalizer**  
Converts platform-specific payloads into your internal canonical schema:

* thread (post) record  
* comment records  
* maps platform fields consistently:  
  * source \= reddit  
  * thread\_id, comment\_id  
  * timestamps normalized to UTC  
  * URL canonicalization

**Benefit**

* Everything downstream (rules, GenAI, UI) becomes platform-agnostic.

---

**D) SQLite Repository (Persistence Layer)**  
Encapsulates reads/writes so business logic doesn’t “know” SQL.

* Upserts threads/comments (dedupe by platform IDs).  
* Tracks “thread state” fields used for active windows and re-eval.  
* Stores rule hits, detections, GenAI decisions, and drafts.

**Important entities (conceptual)**

* Threads  
* Comments  
* Runs  
* Thread State (watching, window\_end, last\_checked, closed)  
* Rule Hits (what matched, where)  
* Detections (thread/comment-level)  
* GenAI Decisions (binary relevant \+ metadata)  
* Draft Responses (text \+ version)

---

**E) Rule Engine (Keywords \+ Location)**  
Runs every scheduled run (cheap), but only on **new content**:

* Checks:  
  * Service keywords \+ intent phrases  
  * Negative keywords  
  * Optional “resolved” phrases (V2)  
* Location heuristics:  
  * subreddit geo mapping  
  * text extraction (city/ZIP/neighborhood mentions)  
* Produces:  
  * rule\_hit \= 1/0  
  * in\_area \= true/false/unknown  
  * hit evidence (matched tokens/phrases)

**Output is not final relevance**—it is the **gate** for GenAI and/or “watching”.  
---

**F) Thread Watcher / Re-evaluation Policy**  
Controls *when* a thread gets re-checked and *how long* it remains active.

* Sets an **active window** (default 5 days from thread creation).  
* Marks thread as watching=1 once it has its first rule hit.  
* On each run:  
  * If new comments appear and within active window:  
    * run rule engine on deltas  
    * optionally trigger GenAI (based on policy)

**Cost control knobs**

* Active window length  
* Max GenAI evals per thread  
* Minimum time between GenAI evals (cooldown)

---

**G) GenAI Evaluator (Thread-level, Delta-based)**  
Triggered only when:

* New rule hit occurs, OR  
* thread is watching=1 and new comments arrived

Inputs to GenAI:

* Thread seed context (post \+ minimal prior context)  
* **Delta comments** since last GenAI check  
* Business profile snippet (service, service area constraints, tone)

Outputs:

* relevant (0/1)  
* optional short\_reason  
* optionally a structured “detection” (what indicates need \+ where)  
* prompt/version metadata for reproducibility

---

**H) Draft Response Generator**  
In V1 this can be one step with the evaluator or a second pass:

* If relevant=1, produce a **suggested response** for HITL editing.  
* Includes:  
  * short greeting \+ empathy  
  * service offer \+ local qualifier  
  * ask 1–2 clarifying questions  
  * safe CTA (phone/website) without spammy tone

Stores:

* draft\_text  
* draft\_version  
* links to thread \+ run\_id

---

**I) Dashboard API \+ Web UI (HITL)**  
**API responsibilities**

* Query flagged queue  
* Fetch thread detail (post \+ comments \+ deltas \+ drafts)  
* Update workflow states (dismiss, snooze, note)  
* Save edited drafts

**UI responsibilities**

* Flagged queue (most recent, in-area, keyword category)  
* Thread detail view:  
  * post \+ full comment thread  
  * source URL click-out  
  * draft response editor \+ copy button  
  * state actions (approve/copy, dismiss, snooze)

**V1 sending**

* Manual: user clicks the source link and pastes edited response.

---

**4\) End-to-end data flow (one run)**

1. Scheduler creates run\_id  
2. Reddit Collector fetches new threads \+ updates for existing threads  
3. Normalizer transforms into canonical thread/comment records  
4. Repository upserts threads/comments  
5. Rule Engine evaluates new content:  
   * sets rule\_hit, in\_area, evidence  
6. Watcher decides which threads are active \+ whether GenAI triggers  
7. GenAI evaluates thread deltas; writes relevant flag \+ decision metadata  
8. If relevant, Draft Generator writes suggested response  
9. Dashboard reads from SQLite to show queue \+ details

---

**5\) Operational concerns (V1)**  
**Logging & observability**

* Per run: counts (threads fetched, comments fetched, new threads, updated threads, rule hits, GenAI calls, relevant flags)  
* Error logs: collector failures, parse errors, GenAI timeouts  
* Cost metrics: tokens/calls per run \+ per thread

**Retry strategy**

* Collector: retry transient failures, resume paging  
* GenAI: retry once on transient errors; otherwise mark decision as “failed” and skip until next run

**Data retention**

* Keep thread/comment content for review (time-box if desired)  
* Store minimal user info (avoid unnecessary PII fields)

---

**6\) Extensibility points (for adding more platforms)**  
Define a standard interface per new platform:

* Collector contract: fetch\_threads() and fetch\_thread\_comments(thread\_id)  
* Normalizer mappings: platform → canonical fields  
* Dedupe keys: stable IDs \+ canonical URLs  
  Downstream (rules/GenAI/UI) stays the same.

