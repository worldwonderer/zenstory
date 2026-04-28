# File tree refresh race fix design

## Goal
Fix the bug where AI-created or AI-updated chapters do not appear in the left file tree until a full page refresh, while also reducing one backend performance amplifier for large projects.

## Root cause
- The chat streaming layer triggers multiple file-tree refreshes during a single AI run.
- The file tree views issue overlapping `getTree()` requests and accept whichever response returns last.
- For larger projects, the backend `/file-tree` endpoint takes longer because it rebuilds the full tree for every request, widening the overlap window.

## Design

### 1. Frontend correctness fix
- Add request-level cancellation and latest-request guards to:
  - `FileTree`
  - `FileTreePane`
  - `MobileFileTree`
- Each view aborts the previous in-flight tree request before starting a new one.
- Each view ignores stale/aborted responses and only applies the latest successful result.
- Abort errors are treated as expected control flow and should not clear the tree.

### 2. Frontend API surface
- Extend `fileApi.getTree()` to accept optional `RequestInit`, allowing callers to pass `AbortSignal` without changing call sites that do not need it.

### 3. Backend performance amplifier reduction
- Add a targeted active-file index for the `project_id + is_deleted=false` access pattern used by the full tree endpoint.
- Create it during `init_db()` for both SQLite and PostgreSQL using `CREATE INDEX IF NOT EXISTS`.

## Verification plan
- Frontend tests covering stale tree responses not overriding newer tree state.
- Existing chat-stream refresh tests remain green.
- Web typecheck/build passes.
- Backend import check confirms new index SQL is wired into startup.
