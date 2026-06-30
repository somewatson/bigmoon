# 📝 Big Moon Development Roadmap

## 🛠️ High Priority

### 7. Admin Activity Monitor
**Goal**: Create a dedicated view for administrators to monitor system-wide user activity and task status.
- [ ] **Backend API**:
    - [ ] Implement `/admin/activity` route to render the monitor page.
    - [ ] Implement `/api/admin/activity` endpoint to provide real-time JSON stats (all tasks + user mapping).
- [ ] **Frontend UI**:
    - [ ] Add "Activity Monitor" link to the admin navigation submenu.
    - [ ] Create `admin_activity.html` with global stats cards.
    - [ ] Implement a live-updating task table with status filters.
    - [ ] Add user-specific activity summaries.
- [ ] **Verification**:
    - [ ] Verify admin-only access (403 for regular users).
    - [ ] Test real-time updates via polling.

### 6. Advanced Chat Synchronization
**Goal**: Implement a synchronized chat experience in the preview modal where chat follows the video playback.
... (remaining items)

