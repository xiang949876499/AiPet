# Marketing Activity Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the marketing page from passive suggestions into an executable flow: choose a concrete campaign direction, generate copy, copy/publish drafts, and review posted content.

**Architecture:** Keep this scoped to the Vue workbench shell. Reuse existing `/api/workbench`, `/api/advisor`, `/content/generate`, and `/content/{id}/publish` behavior instead of adding new backend surface area.

**Tech Stack:** Vue 3, Vite, existing FastAPI HTML form endpoints.

---

### Task 1: Marketing Workflow State

**Files:**
- Modify: `frontend/src/App.vue`

- [x] **Step 1: Add state and computed campaign directions**

Use Vue refs for selected direction, copy notes, and publish status. Derive directions from existing opportunities and content count so the page works with real store data.

- [x] **Step 2: Add execution helpers**

Add helpers that ask the advisor for a campaign plan, copy content body/title, generate backend content, and post existing content items to the current publish endpoint.

### Task 2: Marketing View

**Files:**
- Modify: `frontend/src/App.vue`

- [x] **Step 1: Replace passive marketing cards**

Render a top execution bar, campaign direction cards, existing content drafts with copy/publish controls, and a small recommendation panel.

- [x] **Step 2: Keep fallback links**

Retain access to the legacy content calendar and activity generator for workflows that still need the old pages.

### Task 3: Styling And Verification

**Files:**
- Modify: `frontend/src/styles.css`

- [x] **Step 1: Add responsive marketing workflow styles**

Add focused layout classes for direction cards, action buttons, draft copy blocks, and status notes.

- [x] **Step 2: Verify**

Run:

```bash
npm run build
```

Expected: Vite build exits with code 0.
