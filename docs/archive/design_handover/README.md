# Design Handoff Package

This directory contains the technical specifications required for redesigning the frontend of the Podcast Transcriber application without modifying the backend.

## Contents

### 1. `data_models.ts`
This file contains the **Type Definitions** (TypeScript interfaces) that the frontend currently uses.
- **Why it's important**: The designer can see exactly what data fields are available for each component (e.g., `Summary` has `hooks`, `key_takeaways`, `actionable_advice`).
- **Constraint**: The new design **must** work with these existing data structures. Adding new fields would require backend changes.

### 2. `api_endpoints.md`
This document lists all the **API Endpoints** the frontend calls.
- **Why it's important**: It defines the "actions" the user can take (e.g., "Start Transcription", "Add Feed", "Chat with Episode").
- **Constraint**: The user flow should respect these available actions.

### 3. Visual Assets (Included)
The following screenshots of the current application are included in this directory:
- `dashboard_view.png`: The main dashboard showing statistics.
- `transcription_queue.png`: The interface for managing and tracking transcriptions.
- `episode_details.png`: The modal view showing episode summary, transcript, and actions.

**Note**: The "Chat Interface" screenshot is missing. This view is accessible by clicking "Chat About Episode" from the Episode Details modal. It typically shows a chat window where users can ask questions about the episode content.

### 4. Brand Assets (Missing)
You may want to provide:
    - Current Logo
    - Color Palette (if any)

### 5. User Stories
    - "As a user, I want to subscribe to a podcast feed..."
    - "As a user, I want to chat with my transcribed episodes..."
    - "As a user, I want to read structured summaries (Key Takeaways, Quotes)..."

## Designer Instructions
"We want to update the look and feel (UI/UX) of our application. However, the **Backend API and Data Models are fixed**.
Please design a new interface that utilizes the data structures defined in `data_models.ts` and respects the capabilities listed in `api_endpoints.md`."
