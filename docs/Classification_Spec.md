**Classification Spec (V1)**

**Social Listening App — Thread-level, Delta-based, Binary Flag, HITL**

**0\) Purpose**  
Define **exactly** how threads move through:

* ingestion → rule/keyword scan → watching → GenAI evaluation → flagged/unflagged  
  …while controlling cost and avoiding repeated detections.

This spec is implementation-ready for Codex (no code, only decisions, inputs/outputs, states).  
---

**1\) Key definitions**

* **Thread**: original post \+ all comments.  
* **Delta**: new comments (and any edited post body, if you choose to track edits) since the last successful check.  
* **Rule stage**: cheap keyword/regex \+ basic location inference.  
* **GenAI stage**: expensive evaluation (per thread) triggered by policy.  
* **Flagged**: binary flagged=1 at thread level; sticky unless user dismisses.  
* **Watching**: thread is monitored more closely during an active window after first rule hit.

---

**2\) Inputs (configuration)**  
**2.1 Keyword config**

* SERVICE\_KEYWORDS: list (e.g., plumber, leak, water heater)  
* INTENT\_PHRASES: list (e.g., need, recommend, urgent, looking for)  
* NEGATIVE\_KEYWORDS: list (e.g., hiring, job, salary)  
* MATCH\_LOGIC: AND/OR rules (V1 default below)

**V1 default match logic**

* Rule hit if:  
  * (any SERVICE\_KEYWORD) AND (any INTENT\_PHRASE)  
  * OR an “emergency phrase” list (optional)  
* Rule hit blocked if NEGATIVE\_KEYWORDS found (configurable: hard block vs downgrade)

**2.2 Location config**

* SERVICE\_AREA: one of:  
  * ZIP list, or  
  * city/metro list, or  
  * radius \+ lat/long (V2-strong; V1 heuristic)  
* INCLUDE\_UNKNOWN\_LOCATION: boolean (default true in V1)  
* SUBREDDIT\_GEO\_MAP: mapping of subreddit → likely area (V1 major signal)

**2.3 Cost control config**

* ACTIVE\_WINDOW\_DAYS: default 5  
* MAX\_GENAI\_EVALS\_PER\_THREAD: default 5  
* GENAI\_COOLDOWN\_MINUTES: default 120 (i.e., don’t evaluate same thread more often than once per run in a 2-hr schedule)  
* DELTA\_MIN\_NEW\_COMMENTS: default 1 (don’t run GenAI unless there is at least one new comment since last eval)  
* MAX\_DELTA\_COMMENTS\_SENT: default 25 (truncate delta; include most recent \+ OP replies if possible)

**2.4 Workflow config**

* HITL\_REQUIRED: true (V1)  
* AUTO\_CLOSE\_WHEN\_DISMISSED: true (V1 suggested)  
* SNOOZE\_DEFAULT\_HOURS: 24 (optional)

---

**3\) Stored state fields used by this spec**  
From thread\_state:

* watching (0/1)  
* active\_until\_utc  
* closed (0/1)  
* in\_area (true/false/unknown)  
* last\_rule\_check\_at\_utc  
* last\_genai\_eval\_at\_utc  
* last\_seen\_comment\_at\_utc  
* genai\_eval\_count  
* flagged (0/1)  
* dismissed (0/1)  
* snoozed\_until\_utc

From threads/comments:

* created\_at\_utc, comment timestamps and ids

From detections:

* uniqueness keys for de-dupe

---

**4\) Rule stage spec (cheap filter)**  
**4.1 When it runs**  
On every scheduled run for:

* New threads  
* Threads that have new comments since last\_rule\_check\_at\_utc AND not closed

**4.2 What content is scanned**

* For a **new thread**: scan title \+ body and all currently available comments (or only OP \+ first N comments; your choice)  
* For an **existing thread**: scan only **delta comments** since last\_rule\_check\_at\_utc

**4.3 Outputs written**  
Create rule\_hits rows with:

* matched term  
* hit\_type  
* match\_context (title/body/comment)  
* associated comment\_pk if match came from a comment

Update thread\_state:

* last\_rule\_check\_at\_utc \= now  
* last\_seen\_comment\_at\_utc \= max(comment.created\_at\_utc) (if comments exist)  
* in\_area \+ location\_confidence \+ location\_evidence (if evaluated)

**4.4 Location inference rules (V1)**  
Compute in\_area:

* If subreddit in SUBREDDIT\_GEO\_MAP and maps inside service area → true  
* Else if text contains any configured city/ZIP tokens → true  
* Else if text contains explicit out-of-area signals (other states/cities list) → false  
* Else → unknown

**Gate behavior**

* If in\_area=false → stop processing thread (no GenAI), unless config says otherwise.  
* If in\_area=unknown → continue only if INCLUDE\_UNKNOWN\_LOCATION=true.

---

**5\) Watching policy (state transition)**  
**5.1 Start watching**  
Set watching=1 when:

* A thread has at least one **positive rule hit** (post or comment), and  
* thread is not dismissed

Also set:

* active\_until\_utc \= thread.created\_at\_utc \+ ACTIVE\_WINDOW\_DAYS

**5.2 Stop watching / close**  
Set closed=1 when any is true:

* now \> active\_until\_utc  
* user dismisses thread (V1: dismiss implies close)  
* (optional V2) thread appears resolved by OP

When closed=1, no more rule checks or GenAI checks unless manually reopened.  
---

**6\) GenAI trigger spec (expensive stage)**  
**6.1 Hard blockers (never run GenAI)**  
Do not run GenAI if any:

* closed=1  
* dismissed=1  
* snoozed\_until\_utc exists and now \< snoozed\_until\_utc  
* genai\_eval\_count \>= MAX\_GENAI\_EVALS\_PER\_THREAD  
* in\_area=false (unless override)  
* no new comments since last successful eval and no new rule hits in post/body

**6.2 Run GenAI when**  
Run GenAI if all prerequisites met and any trigger is true:  
**Trigger A (first-time hit)**

* Thread has a new positive rule hit since last run AND flagged=0

**Trigger B (watching \+ delta)**

* watching=1 AND there is **delta content** (\>= DELTA\_MIN\_NEW\_COMMENTS) since last\_genai\_eval\_at\_utc

**Trigger C (manual re-check)**

* User requests re-check from dashboard (optional V1)

**6.3 Cooldown**  
Even if triggered, skip if:

* now \- last\_genai\_eval\_at\_utc \< GENAI\_COOLDOWN\_MINUTES

---

**7\) GenAI input contract (what you send)**  
**7.1 Payload sections**  
**(1) Business Context**

* Service type (e.g., plumbing)  
* Service area (human-readable)  
* Tone preferences (professional, helpful, brief)

**(2) Thread Seed**

* Title  
* Post body  
* Subreddit  
* Thread URL  
* (Optional) short “known context” summary from prior eval if stored

**(3) Delta Comments**

* List of new comments since last\_genai\_eval\_at\_utc  
* Include:  
  * comment\_id  
  * author (optional)  
  * created\_at  
  * text  
* Truncate to MAX\_DELTA\_COMMENTS\_SENT with preference:  
  * OP comments  
  * most recent comments

**(4) Rule Evidence**

* Matched keywords/phrases and where they matched (helps focus)

**7.2 Output schema (required)**  
GenAI must return JSON-like structure:

* relevant (0/1)  
* draft\_response (string; required if relevant=1, optional otherwise)  
* detection\_items (array, optional):  
  * comment\_id (nullable)  
  * detection\_type  
  * evidence\_excerpt  
* short\_reason (string, optional)

---

**8\) GenAI output handling**  
**8.1 Write genai\_evals**  
Create one row per GenAI call:

* store relevant, short\_reason, delta\_from/to, prompt\_version, model, status, errors

Update thread\_state:

* last\_genai\_eval\_at\_utc \= now  
* genai\_eval\_count \+= 1

**8.2 If relevant=1**

* Set thread\_state.flagged=1 and flagged\_at\_utc if not already set  
* Store draft\_responses row as suggested  
* Write detections rows, **de-duped**:  
  * If comment\_id present: unique on (thread\_pk,comment\_pk,detection\_type)  
  * Else use source\_hash derived from evidence\_excerpt or a stable hash of (thread\_id \+ excerpt)

**8.3 If relevant=0**

* Do not flag thread  
* Keep watching as-is if within active window (because intent can emerge later)

---

**9\) De-dupe rules (explicit)**  
On each new GenAI eval:

* For each detection\_item:  
  1. Map comment\_id → comment\_pk if possible  
  2. Compute source\_hash if comment\_pk is null  
  3. Attempt insert into detections  
  4. If conflict/duplicate → ignore silently

Thread-level flagged is sticky:

* Once set to 1, it stays 1 unless user dismisses or archives.

---

**10\) HITL workflow rules (V1)**  
**10.1 Queue inclusion**  
A thread appears in the dashboard queue if:

* flagged=1  
* dismissed=0  
* (optional) not snoozed

**10.2 User actions and their effects**

* **Dismiss**:  
  * dismissed=1, closed=1, remove from queue  
* **Snooze (N hours)**:  
  * set snoozed\_until\_utc, keep flagged  
* **Approve/Copy**:  
  * set draft\_responses.status=approved (or log review\_actions)  
  * does NOT post externally  
* **Edit draft**:  
  * update draft\_responses.status=edited, store updated\_at  
* **Reopen** (optional):  
  * dismissed=0, closed=0, may reset active\_until\_utc or not (policy choice)

---

**11\) Default policy summary (recommended V1 defaults)**

* Rule scan: every run on deltas  
* Watching: starts on first rule hit; lasts 5 days  
* GenAI:  
  * runs on first rule hit  
  * then runs only when new comments arrive during active window  
  * max 5 evals per thread  
  * cooldown equals run interval  
* Flagging: binary, sticky  
* De-dupe: comment\_id or hash-based

