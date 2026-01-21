**Data Model / SQLite Schema (V1)**

Designed for: **Reddit-first**, **thread-level (post+comments)**, **delta re-eval**, **HITL**, **binary relevance flag**, **location-aware**, **audit-lite via source URL \+ run\_id**.  
---

**1\) Entity overview (what we store)**  
**Core content**

* threads (the post)  
* comments (all replies)

**Operational**

* runs (each scheduled execution)  
* thread\_state (watching, active window, last checks, counters)

**Decisioning**

* rule\_hits (keyword/rule matches; cheap stage)  
* genai\_evals (binary decisions; expensive stage)  
* draft\_responses (suggested replies)  
* detections (de-duped “why it was flagged” artifacts)

**HITL workflow**

* review\_actions (dismiss/snooze/approve/copy/notes)

**Configuration**

* config \+ optional keywords, geo\_rules tables (or JSON blobs in config for V1)

---

**2\) Tables and key fields**  
**A) runs**  
One row per scheduled run.  
**Fields**

* run\_id (PK, TEXT UUID)  
* started\_at\_utc (INTEGER epoch)  
* ended\_at\_utc (INTEGER epoch)  
* status (TEXT: running/success/failed/partial)  
* source (TEXT; in V1 likely “reddit” or “all”)  
* Counters (INTEGER): threads\_fetched, comments\_fetched, threads\_new, threads\_updated, rule\_hits, genai\_calls, threads\_flagged  
* error\_summary (TEXT, nullable)

**Indexes**

* started\_at\_utc

---

**B) threads**  
Canonical representation of a “thread” (one post).  
**Fields**

* thread\_pk (PK, INTEGER autoincrement)  
* source (TEXT; “reddit”)  
* source\_thread\_id (TEXT; stable platform ID)  
* url (TEXT; canonical link)  
* subreddit (TEXT)  
* title (TEXT)  
* body (TEXT)  
* author (TEXT, nullable)  
* created\_at\_utc (INTEGER)  
* last\_seen\_at\_utc (INTEGER) ← updated each ingestion  
* last\_content\_at\_utc (INTEGER) ← last known comment/post update time  
* is\_deleted / is\_removed (INTEGER 0/1, nullable)  
* Optional: score (INTEGER), num\_comments\_reported (INTEGER)

**Constraints**

* UNIQUE(source, source\_thread\_id)  
* Optional UNIQUE(url) (if canonicalization is consistent)

**Indexes**

* (source, created\_at\_utc)  
* subreddit  
* last\_content\_at\_utc

---

**C) comments**  
All comments in a thread, stored individually for delta detection.  
**Fields**

* comment\_pk (PK, INTEGER autoincrement)  
* thread\_pk (FK → threads.thread\_pk)  
* source (TEXT)  
* source\_comment\_id (TEXT)  
* parent\_source\_id (TEXT, nullable) ← parent comment id or thread id (platform-style)  
* author (TEXT, nullable)  
* body (TEXT)  
* created\_at\_utc (INTEGER)  
* last\_seen\_at\_utc (INTEGER)  
* is\_deleted (INTEGER 0/1, nullable)  
* Optional: depth (INTEGER), permalink (TEXT)

**Constraints**

* UNIQUE(source, source\_comment\_id)  
* FK(thread\_pk)

**Indexes**

* thread\_pk, created\_at\_utc (supports “new comments since last check”)  
* created\_at\_utc

---

**D) thread\_state**  
Your control-plane for **watching / active window / re-eval** and workflow state.  
**Fields**

* thread\_pk (PK, FK → threads.thread\_pk)  
* watching (INTEGER 0/1)  
* active\_until\_utc (INTEGER) ← created\_at \+ window\_days  
* closed (INTEGER 0/1) ← set when window ends or user closes  
* in\_area (TEXT: true/false/unknown)  
* location\_confidence (REAL 0–1, nullable)  
* location\_evidence (TEXT, nullable) ← e.g., “subreddit=r/Atlanta; text=Decatur”  
* last\_rule\_check\_at\_utc (INTEGER, nullable)  
* last\_genai\_eval\_at\_utc (INTEGER, nullable)  
* last\_seen\_comment\_at\_utc (INTEGER, nullable)  
* genai\_eval\_count (INTEGER default 0\)  
* flagged (INTEGER 0/1 default 0\) ← thread-level flag  
* flagged\_at\_utc (INTEGER, nullable)  
* dismissed (INTEGER 0/1 default 0\)  
* snoozed\_until\_utc (INTEGER, nullable)

**Indexes**

* flagged, dismissed, snoozed\_until\_utc  
* active\_until\_utc  
* watching

---

**E) rule\_hits**  
Stores results of the cheap filter and the evidence.  
**Fields**

* rule\_hit\_pk (PK, INTEGER autoincrement)  
* run\_id (FK → runs.run\_id)  
* thread\_pk (FK)  
* comment\_pk (FK, nullable) ← null means match was in post title/body  
* hit\_type (TEXT: keyword/phrase/negative/location)  
* matched\_term (TEXT)  
* match\_context (TEXT: title/body/comment)  
* created\_at\_utc (INTEGER)

**Indexes**

* thread\_pk, created\_at\_utc  
* run\_id

---

**F) genai\_evals**  
Each GenAI evaluation event for a thread (delta-based), binary output.  
**Fields**

* genai\_eval\_pk (PK, INTEGER autoincrement)  
* run\_id (FK → runs.run\_id)  
* thread\_pk (FK)  
* eval\_scope (TEXT: delta/thread\_seed)  
* delta\_from\_utc (INTEGER, nullable)  
* delta\_to\_utc (INTEGER, nullable)  
* relevant (INTEGER 0/1)  
* short\_reason (TEXT, nullable) ← optional human-friendly rationale  
* model (TEXT, nullable)  
* prompt\_version (TEXT, nullable)  
* created\_at\_utc (INTEGER)  
* tokens\_in / tokens\_out (INTEGER, nullable)  
* status (TEXT: success/failed)  
* error\_text (TEXT, nullable)

**Indexes**

* thread\_pk, created\_at\_utc  
* run\_id  
* relevant

---

**G) draft\_responses**  
Stores the suggested reply text (HITL editable), versioned.  
**Fields**

* draft\_pk (PK, INTEGER autoincrement)  
* thread\_pk (FK)  
* genai\_eval\_pk (FK, nullable) ← tie to evaluation that produced it  
* draft\_text (TEXT)  
* draft\_version (INTEGER default 1\)  
* status (TEXT: suggested/edited/approved/archived)  
* created\_at\_utc (INTEGER)  
* updated\_at\_utc (INTEGER)

**Indexes**

* thread\_pk, updated\_at\_utc  
* status

---

**H) detections**  
This is your **de-dupe mechanism** for “already flagged” items.  
**Fields**

* detection\_pk (PK, INTEGER autoincrement)  
* thread\_pk (FK)  
* comment\_pk (FK, nullable)  
* detection\_type (TEXT: lead\_intent/service\_need/etc.)  
* evidence\_text (TEXT, nullable) ← short excerpt or summary  
* source\_hash (TEXT) ← stable hash for de-dupe if no comment\_pk  
* created\_at\_utc (INTEGER)

**Constraints**

* UNIQUE(thread\_pk, comment\_pk, detection\_type) when comment\_pk present  
* Or UNIQUE(thread\_pk, source\_hash, detection\_type) fallback

**Indexes**

* thread\_pk  
* created\_at\_utc

---

**I) review\_actions**  
HITL workflow events: dismiss, snooze, approve, notes, etc.  
**Fields**

* action\_pk (PK, INTEGER autoincrement)  
* thread\_pk (FK)  
* action\_type (TEXT: dismiss/snooze/approve/copy/note/reopen)  
* action\_value (TEXT, nullable) ← e.g., snooze\_until timestamp, note text  
* actor (TEXT, nullable) ← “bill” or “system”  
* created\_at\_utc (INTEGER)

**Indexes**

* thread\_pk, created\_at\_utc  
* action\_type

---

**J) Configuration (two options)**  
**Option 1 (simplest V1): single config table**

* config\_key (PK, TEXT)  
* config\_value (TEXT) ← JSON blob  
* updated\_at\_utc (INTEGER)

Store keys like:

* keywords\_include, keywords\_intent, keywords\_negative  
* geo\_service\_area (zip list / city list / radius+latlong)  
* schedule\_minutes  
* active\_window\_days, max\_genai\_evals\_per\_thread  
* include\_unknown\_location (bool)  
* subreddits (list)

**~~Option 2 (more structured): keywords, geo\_rules tables~~**  
~~Useful once you need UI-driven edits and auditing~~.  
---

**3\) How this schema supports your re-eval policy (the tricky bit)**

* New comments are detected via comments.created\_at\_utc \> thread\_state.last\_rule\_check\_at\_utc  
* Rule stage logs rule\_hits (evidence)  
* Once first hit occurs: set thread\_state.watching=1 and active\_until\_utc  
* GenAI stage logs genai\_evals and increments thread\_state.genai\_eval\_count  
* De-dupe is enforced by detections uniqueness constraints  
* Thread-level “flag” is thread\_state.flagged=1 (sticky until dismissed)

---

**4\) Minimal indexes that matter most (V1)**

* comments(thread\_pk, created\_at\_utc) for delta pulls  
* threads(source, source\_thread\_id) UNIQUE for dedupe  
* thread\_state(flagged, dismissed, snoozed\_until\_utc) for queue performance  
* genai\_evals(thread\_pk, created\_at\_utc) for history

---

**5\) Schema versioning**  
Add a tiny schema\_migrations table:

* version (PK, INTEGER)  
* applied\_at\_utc (INTEGER)  
* notes (TEXT)

