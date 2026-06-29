# 📝 Big Moon Development Roadmap

## 🛠️ High Priority

### 6. Advanced Chat Synchronization
**Goal**: Implement a synchronized chat experience in the preview modal where chat follows the video playback.
- [x] **Data Management**: Store fetched chat messages in a variable instead of just rendering static HTML.
- [x] **Time Synchronization**: Implement a `timeupdate` listener on the video player to auto-scroll the chat container to the current timestamp.
- [x] **Interactive Seeking**: Implement "Click-to-Seek" functionality (clicking a chat message seeks the video to that timestamp).
- [x] **Visual Polish**: 
    - [x] Add a "current message" highlight effect.
    - [x] Format raw seconds into `MM:SS` timestamps.
    - [x] Implement smooth scrolling for the chat container.
- [x] **UI Fixes**: 
    - [x] Fix visibility of the "Download Chat" button in the preview modal.
    - [x] Add a "Download Chat" button to the Library view.

