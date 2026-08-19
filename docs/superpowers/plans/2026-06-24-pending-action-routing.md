# Pending Action Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let staff open a specific customer opportunity or pending reminder directly in the task workspace and focus the related task.

**Architecture:** Keep routing inside the existing Vue single-page workbench. A focused task id controls the active visual state, while the existing hash view switcher opens the task workspace and a post-render scroll locates the selected row.

**Tech Stack:** Vue 3, Vite, CSS.

---

### Task 1: Add pending-item routing state

**Files:**
- Modify: `frontend/src/App.vue`
- Test: `frontend/package.json` (`npm run build`)

- [x] **Step 1: Add a focused task ref and navigation helpers**

```js
const focusedTaskId = ref(null);

async function openTask(task) {
  focusedTaskId.value = task.id;
  setView("tasks");
  await nextTick();
  document.getElementById(`task-${task.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}
```

- [x] **Step 2: Route customer opportunities to their matching reminder**

```js
function openOpportunity(item) {
  const task = (data.value.reminders || []).find((candidate) => candidate.customer_name === item.customer_name);
  if (!task) focusedTaskId.value = null;
  return openTask(task);
}
```

- [x] **Step 3: Render action buttons and focused row state**

```vue
<button class="task-button primary" type="button" @click="openTask(task)">立即处理</button>
<div :id="`task-${task.id}`" :class="{ 'is-focused': focusedTaskId === task.id }">
```

- [x] **Step 4: Run the build**

Run: `npm run build`

Expected: Vite completes with exit code 0.

### Task 2: Clarify action hierarchy

**Files:**
- Modify: `frontend/src/styles.css`
- Test: `frontend/package.json` (`npm run build`)

- [x] **Step 1: Add a compact action cluster for customer rows**

```css
.feature-row-actions { display: flex; align-items: center; gap: 10px; }
```

- [x] **Step 2: Add a focused-task affordance**

```css
.task-row.is-focused { border-color: var(--accent); box-shadow: 0 0 0 3px oklch(82% 0.09 55 / 0.22); }
```

- [x] **Step 3: Run the build**

Run: `npm run build`

Expected: Vite completes with exit code 0.
