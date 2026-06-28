# 🏗️ JS Refactoring Plan: Modularizing index.js

## Goal
Split the monolithic `app/static/js/index.js` into modular, page-specific files to improve maintainability and reduce file size.

## Architecture
The refactor will move from a single file to a structured directory of scripts.

### 1. Core & Shared (`core.js`)
Contains foundational logic used by all pages:
- Global state: `currentTab`.
- Utility: `apiFetch`, `updateConnectionStatus`, `showToast`.
- Navigation: `showTab`, sidebar toggle logic, `DOMContentLoaded` event.

### 2. Page-Specific Modules
Each file will handle the logic for its respective UI tab:
- `search.js`: `searchVideos`, `toggleFavorite`, `downloadVideo`, `previewVideo`.
- `favorites.js`: `loadFavorites`, `removeFavorite`.
- `automation.js`: `loadMonitored`, `addFavToAutomation`, `updateMonitored`, `deleteMonitored`.
- `library.js`: `loadLibrary`, `handleFileSelection`, `bulkDelete`, `bulkCompress`, `checkThumbnailStatus`.
- `compress.js`: `loadFiles`, `compressFile`.
- `tasks.js`: `loadTasks`, `viewTaskLogs`, `fetchLogs`, `cancelTask`, `retryTask`, `clearFailedTasks`.

### 3. UI Components & Modals (`modals.js`)
Cross-cutting UI elements:
- Preview modal logic: `closePreview`.
- Log modal logic: `closeLogs`, `copyLogsToClipboard`, `refreshLogs`, `scrollToBottom`.

---

## Execution Strategy (Agent Workflow)

### Phase 1: Foundation (`core-dev` agent)
- Extract `apiFetch` and navigation logic.
- Create `core.js`.
- Update `index.html` to include `core.js`.

### Phase 2: Feature Extraction (Parallel agents)
- **`search-dev`**: Move search/preview logic to `search.js`.
- **`fav-dev`**: Move favorites/automation logic to `favorites.js` and `automation.js`.
- **`lib-dev`**: Move library/bulk action logic to `library.js`.
- **`comp-dev`**: Move compression logic to `compress.js`.
- **`task-dev`**: Move task/log logic to `tasks.js`.
- **`modal-dev`**: Move modal helpers to `modals.js`.

### Phase 3: Integration & Cleanup (`integration-dev` agent)
- Ensure `window.func = func` assignments are maintained for inline HTML `onclick` handlers.
- Verify script loading order in `index.html`.
- Perform a final sweep of `index.js` to remove redundant code.

## Verification Checklist
- [ ] All tabs load their data correctly.
- [ ] Sidebar navigation works across all tabs.
- [ ] "Preview" and "View Logs" modals open and close.
- [ ] API calls (Search, Download, Compress) still function.
- [ ] No `ReferenceError` in browser console.
