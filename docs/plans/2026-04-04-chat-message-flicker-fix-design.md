# Chat message flicker fix design

## Goal
Reduce post-completion message-list flicker in AI chat, especially on long conversations where the user-visible message list keeps flashing after the agent finishes.

## Root cause
- The chat message list used virtualization with estimated heights for rich assistant messages.
- When the final assistant message landed, the virtualizer repeatedly corrected row measurements and offsets.
- Completion also triggered closely spaced scroll requests, amplifying the visible jitter.

## Design

### 1. Disable chat message virtualization
- Render the filtered chat messages directly in stable DOM order.
- Keep the existing `Row` component and `scrollToBottom` ref API.
- Remove virtualizer-specific positioning/measurement from `MessageList`.

### 2. Coalesce auto-scroll updates
- In `ChatPanel`, schedule bottom scrolling in a single RAF instead of firing immediately on every relevant state change.
- Drive the effect from stable, meaningful signals:
  - `messages.length`
  - accumulated streaming content
  - thinking content
  - conflict count
  - streaming state flags
  - `streamRenderItems.length`
- Avoid re-scrolling on metadata-only message updates such as backend hydration.

## Verification plan
- MessageList tests updated for non-virtualized rendering.
- ChatPanel mount smoke remains green.
- Stream hooks regression suite remains green.
- Web typecheck/build passes.
