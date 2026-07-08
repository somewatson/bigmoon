# 📝 Big Moon Development Roadmap

## 🛠️ High Priority

### 9. Admin Activity Monitor - View Logs Integration
**Goal**: Enable administrators to view real-time task logs directly from the Activity Monitor page.
- [ ] **Globalize Log Modal**: Move `logModal` HTML from `index.html` to `layout.html` to make it accessible across all application pages.
- [ ] **Shared Log Logic**: Extract log-related JavaScript functions (`openLogs`, `refreshLogs`, `scrollToBottom`, `copyLogsToClipboard`) from `tasks.js` and move them to a shared script (e.g., `static/js/logs.js`) and include it in `layout.html`.
- [ ] **UI Update**: Add a "View Logs" button to the task rows in `app/templates/admin_activity.html`.
- [ ] **Verification**:
    - [ ] Open Activity Monitor as Admin.
    - [ ] Click "View Logs" for an active/failed task.
    - [ ] Verify logs load correctly and the modal functions (refresh, copy, etc.) work as expected.

### 10. UI Compression Savings Logic
**Goal**: Prevent displaying inaccurate file size savings in the UI if a file is still being compressed.
- [ ] **Logic Update**: Modify UI/API to hide or mark "savings" as pending until compression status is complete.
- [ ] **Verification**: Start a compression task and verify size savings are not shown until the task finishes.


