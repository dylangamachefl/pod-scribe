# DESIGN_SPEC.md

# Application Redesign: Podcast Knowledge OS

**Version:** 2.0
**Vision:** Shift from "Podcast Manager" (Admin tool) to "Knowledge Operating System" (Insight tool).

---

## 1. Global Architecture (The App Shell)

**Concept:** A productivity-focused interface replacing top tabs with a persistent sidebar.

### 1.1 Sidebar Navigation (Left)

* **Header:** App Logo / Branding.
* **Section: Inbox (Triage)**
* **"New Arrivals"**: Counter badge showing pending episodes (derived from `GET /episodes/queue` count).
* **"Processing"**: Live status indicator. Visible only when `TranscriptionStatus.is_running` is true.


* **Section: Library (Knowledge)**
* **"All Summaries"**: Main grid view.
* **"Favorites"**: Local filter.


* **Section: Smart Tags (Dynamic)**
* List top 5 most frequent concepts from `Summary.key_topics`.


* **Section: System**
* **"Manage Feeds"**: Opens Feed Modal.
* **"System Health"**: Visual indicator using `/health` and `/stats`.



### 1.2 Global Chat Drawer (Right)

* **Behavior:** Collapsible drawer (overlay or push) accessible from any screen.
* **Trigger:** "Sparkles" icon in top-right header or "Chat" buttons on cards.

---

## 2. View: The Inbox (Input & Triage)

**Goal:** Rapidly scan new feed items, select valuable ones, and trigger transcription. Replaces the fragmented "Feeds" and "Queue" tabs.

### 2.1 The Feed List

* **Data Source:** `GET /episodes/queue` merged with `POST /episodes/fetch` results.
* **Layout:** Horizontal "Mailbox" style rows.
* **Row Content:**
* **Checkbox:** For batch selection.
* **Title:** `episode_title`.
* **Meta:** `feed_title` • `published_date`.
* **Action:** "Play" button (uses `audio_url` for preview).



### 2.2 The Action Bar (Header)

* **"Sync Feeds"**: Triggers `POST /episodes/fetch`.
* **"Transcribe Selected"**: Primary CTA. Triggers `POST /transcription/start` with payload `{ episode_ids: [...] }`.

### 2.3 Live Status Banner (Pinned Top)

* **Visibility:** Conditionally rendered when polling `GET /transcription/status` returns `is_running: true`.
* **Visuals:** Dark card with progress bar.
* **Data Mapping:**
* "Processing: {current_episode}".
* "Stage: {stage} ({progress}%)".
* "GPU: {gpu_name} • VRAM: {vram_used_gb}GB" (Technical trust signal).



---

## 3. View: Smart Library (Storage & Discovery)

**Goal:** Browse processed insights using faceted search. Replaces the static "Library" grid.

### 3.1 The "Smart Card" Component

* **Data Source:** `GET /summaries`.
* **Visual Hierarchy:**
* **Eyebrow:** `podcast_name`.
* **Title:** `episode_title`.
* **The Hook (Crucial):** Display `Summary.hook` instead of generic summary text. This drives engagement.
* **Tags:** Display first 3 items from `key_topics`.
* **Footer:** "Chat" icon action.



### 3.2 Sidebar Facets

* **Logic:** Client-side aggregation of `Summary.concepts` and `Summary.key_topics` across all fetched summaries.
* **Interaction:** Clicking a tag (e.g., "LLMs") filters the main grid immediately.

---

## 4. View: Episode Executive Brief (Consumption)

**Goal:** A magazine-style layout for deep reading. Replaces the standard Modal.

### 4.1 Header & Controls

* **Content:** Title, Date, Duration.
* **Media:** Sticky "Play" bar and "Watch on YouTube" button (if link exists).
* **Tabs:** [Insights] [Full Transcript] [Chat].

### 4.2 Section: The Hero (Context)

* **Left Column (The Hook):** Large typography displaying `Summary.hook`.
* **Right Column (The Perspective):** A colored card displaying `Summary.perspectives` (e.g., "The speaker takes a contrarian view...").

### 4.3 Section: The Knowledge Grid (Bento Box)

* **Left Box (Glossary):** Interactive pills generated from `Summary.concepts` (`{ term, definition }`).
* **Right Box (Action Plan):** Checklist UI generated from `Summary.actionable_advice`.

### 4.4 Section: Deep Dive

* **Content:** Interwoven layout of `Summary.summary` text and `Summary.key_takeaways` cards.
* **Quotes:** Pull-quotes using `Summary.quotes` inserted between paragraphs.

---

## 5. View: Global Chat (Synthesis)

**Goal:** Persistent AI assistant for Q&A across the library.

### 5.1 Context Manager

* **Mode Switcher:** Dropdown in drawer header.
* *Option A:* "Library Search" (Queries all vectors).
* *Option B:* "Ask this Episode" (Appends context/filter for current episode).



### 5.2 Message Design

* **AI Response:** Markdown text.
* **Citations:** Render `SourceCitation` objects as clickable chips or cards.
* **Card Data:** `podcast_name`, `timestamp`, `text_snippet` (proof of truth), `relevance_score`.



### 5.3 Backend Integration

* **Endpoint:** `POST /chat`.
* **Payload:** `{ question: string, conversation_history: [] }`.

---

## 6. Implementation Plan (Next Steps)

1. **Frontend Setup:** Scaffold the Sidebar Layout (App Shell).
2. **Phase 1:** Build the **Inbox** to enable data ingestion/transcription.
3. **Phase 2:** Build the **Smart Library** and **Episode Brief** for consumption.
4. **Phase 3:** Integrate the **Chat Drawer** component globally.
