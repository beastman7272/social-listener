  
**UI/Wireframes (V1)**

**Dashboard for Flagged Threads \+ Suggested Responses (HITL)**  
V1 goal: **fast triage \+ easy click-out \+ quick copy/edit of draft**. No platform posting.  
---

**1\) Global layout**  
**Top nav (persistent)**

* App name \+ business name (single-tenant)  
* Tabs: **Queue**, **All Threads**, **Rules/Config**, **Runs/Logs**  
* Right side: “Last run: time”, “Run now” button (optional), “Settings”

**Main content**

* Two-pane layout for speed:  
  * **Left:** list/queue  
  * **Right:** detail panel for selected thread

---

**2\) Primary screen: Flagged Queue (default landing)**  
**Left pane: Queue list**  
Each row/card shows:

* **Service tag(s)** (from keywords or detection\_type)  
* **Location badge**: In-area / Unknown / Out-of-area (out-of-area usually hidden)  
* **Recency**: “2h ago”, “1d ago”  
* **Source**: Reddit \+ subreddit name  
* **Title (truncated)** \+ small snippet from post or latest comment  
* **Status chips**: Suggested / Edited / Approved / Snoozed  
* Optional: “New comments” count since last view

**Controls above list**

* Search box (title/body/comments)  
* Filters:  
  * Location: In-area / Unknown  
  * Source/Subreddit  
  * Status: Suggested/Edited/Approved  
  * Service category (plumbing, HVAC, etc.)  
* Sort:  
  * Newest activity (default)  
  * Newest flagged  
  * Location confidence

**Right pane: Empty state**  
When nothing selected:

* “Select a thread to review”  
* Quick stats: flagged today, avg review time, etc. (optional)

---

**3\) Thread Detail View (right pane)**  
**Header section**

* **Title** (full)  
* Subheader line:  
  * Source \+ subreddit  
  * Created date/time  
  * **Open original thread** (primary link button)  
* Badges:  
  * In-area / Unknown (with confidence % if available)  
  * Watching / Closed  
  * Flagged timestamp

**Content tabs (within detail)**  
**Tab A: Conversation (default)**

* Post body (with line breaks preserved)  
* Comments chronological (or “Top then chronological” toggle)  
* Highlighting:  
  * Matched keyword hits highlighted  
  * OP comments marked “OP”  
* “New since last eval” divider line

**Tab B: Signals**

* Keyword/rule hits list (term \+ where matched \+ timestamp)  
* Location evidence (subreddit mapping / text tokens)  
* GenAI short reason (if stored)

**Tab C: History**

* GenAI eval history: time, relevant 0/1, delta range, status  
* Review actions history: dismissed/snoozed/approved edits

---

**4\) Draft Response Panel (right pane, below thread)**  
**Draft box (editable)**

* Label: “Suggested response”  
* Large editable text area  
* Buttons:  
  * **Copy** (primary)  
  * Save edit  
  * Reset to suggested (if edited)  
* Optional small helpers:  
  * “Tone: Friendly / Professional” (V2)  
  * “Shorten” / “Make more empathetic” (V2)

**Action buttons (workflow)**

* **Approve** (marks approved; keeps in “Approved” view)  
* **Snooze** (dropdown: 4h, 24h, 3d, custom)  
* **Dismiss** (confirm modal: “Remove from queue and close?”)

**Notes**

* Simple notes field (internal)  
* Tagging (optional V2)

---

**5\) Secondary screens**  
**A) All Threads**  
Purpose: visibility and debugging beyond the flagged queue.

* List of all ingested threads with filters:  
  * source/subreddit, date range, in\_area state, watching/closed, flagged/dismissed  
* Click-through opens same detail view.

**B) Rules/Config**  
Sections:

1. **Service Area**  
   * City/ZIP list (V1) or radius (placeholder)  
   * Include unknown location toggle  
2. **Keywords**  
   * Include keywords  
   * Intent phrases  
   * Negative keywords  
3. **Policy**  
   * Run frequency (2h)  
   * Active window days  
   * Max GenAI evals per thread  
   * Cooldown  
4. **Sources**  
   * Subreddit list  
   * Search queries (optional)  
5. Save changes \+ “Test rules” (optional)

**C) Runs/Logs**

* Runs list: run\_id, start/end, status, counts, errors  
* Click a run to see details:  
  * ingestion counts  
  * number of rule hits  
  * GenAI calls  
  * flagged threads list

---

**6\) Wireframe sketches (text-only)**  
**Queue (two-pane)**  
\+--------------------------------------------------------------+  
| Queue | All Threads | Rules/Config | Runs/Logs     Last run   |  
\+-------------------+------------------------------------------+  
| Filters/Search     |  Thread Detail                           |  
| \[search\_\_\_\_\_\]      |  Title                                   |  
| Loc: \[In/Unk\]      |  Reddit • r/Atlanta • Open Thread \-\>     |  
| Status: \[Sug/Ed\]   |  Badges: In-area | Watching | Flagged    |  
| Sort: Activity     |------------------------------------------|  
|------------------- |  \[Conversation | Signals | History\]      |  
| \[card\] leak...     |  Post body...                            |  
| \[card\] waterheater |  Comments... (OP marked)                 |  
| \[card\] emergency   |------------------------------------------|  
|                    |  Suggested response (editable)           |  
|                    |  \[Copy\] \[Save\] \[Approve\] \[Snooze\] \[X\]    |  
\+-------------------+------------------------------------------+

**Rules/Config**  
Service Area: \[ZIPs...\]  Include unknown: \[✓\]  
Keywords: Include\[...\] Intent\[...\] Negative\[...\]  
Policy: Window\[5d\] Max evals\[5\] Cooldown\[120m\]  
Sources: Subreddits\[...\]  \[Save\]  
---

**7\) V1 UX requirements (non-negotiables)**

* **Open original thread** button on every detail view  
* **Copy response** one-click  
* Fast queue triage: Dismiss/Snooze/Approve without navigating away  
* Preserve formatting (post \+ comments)  
* Visible location state (In/Unknown/Out)

