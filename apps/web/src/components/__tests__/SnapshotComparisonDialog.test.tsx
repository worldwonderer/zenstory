import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SnapshotComparisonDialog from '../SnapshotComparisonDialog'

const mockCompare = vi.fn()
const mockFileGet = vi.fn()
const loggerError = vi.fn()

const { mockT } = vi.hoisted(() => ({
  mockT: vi.fn((key: string) =>
    (
      {
        'editor:versionHistory.snapshotCompareTitle': 'Snapshot Compare',
        'editor:versionHistory.deletedFile': 'Deleted file',
        'editor:versionHistory.loadFailed': 'Failed to load comparison',
        'editor:versionHistory.comparing': 'Comparing snapshots',
        'editor:versionHistory.oldVersion': 'Old version',
        'editor:versionHistory.newVersion': 'New version',
        'editor:versionHistory.added': 'added',
        'editor:versionHistory.removed': 'removed',
        'editor:versionHistory.modified': 'modified',
        'editor:versionHistory.noDiff': 'No differences',
        'editor:versionHistory.addedFiles': 'Added files',
        'editor:versionHistory.removedFiles': 'Removed files',
        'editor:versionHistory.modifiedFiles': 'Modified files',
        'editor:versionHistory.versionPrefix': 'Version',
        'common:close': 'Close',
      } as Record<string, string>
    )[key] ?? key),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
  }),
}))

vi.mock('../../lib/api', () => ({
  versionApi: {
    compare: (...args: unknown[]) => mockCompare(...args),
  },
  fileApi: {
    get: (...args: unknown[]) => mockFileGet(...args),
  },
}))

vi.mock('../../lib/dateUtils', () => ({
  formatFullDate: (value: string) => `formatted:${value}`,
}))

vi.mock('../../lib/logger', () => ({
  logger: {
    error: (...args: unknown[]) => loggerError(...args),
  },
}))

vi.mock('../ui/Modal', () => ({
  Modal: ({
    open,
    title,
    footer,
    children,
  }: {
    open: boolean
    title: React.ReactNode
    footer: React.ReactNode
    children?: React.ReactNode
  }) => (open ? <div><div>{title}</div>{children}{footer}</div> : null),
}))

describe('SnapshotComparisonDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCompare.mockResolvedValue({
      snapshot1: { created_at: '2026-04-01T00:00:00Z' },
      snapshot2: { created_at: '2026-04-02T00:00:00Z' },
      changes: {
        added: [{ file_id: 'file-added', version_number: 1 }],
        removed: [{ file_id: 'file-removed', version_number: 2 }],
        modified: [{ file_id: 'file-modified', version_number: 3 }],
      },
    })
    mockFileGet
      .mockResolvedValueOnce({ title: 'Added Draft', file_type: 'draft' })
      .mockRejectedValueOnce(new Error('missing file'))
      .mockResolvedValueOnce({ title: 'Modified Draft', file_type: 'draft' })
  })

  it('loads and renders added, removed, and modified file groups', async () => {
    render(<SnapshotComparisonDialog snapshotId1="snap-1" snapshotId2="snap-2" onClose={vi.fn()} />)

    expect(await screen.findByText('Snapshot Compare')).toBeInTheDocument()
    expect(await screen.findByText('Added Draft')).toBeInTheDocument()
    expect(screen.getByText('Deleted file')).toBeInTheDocument()
    expect(screen.getByText('Modified Draft')).toBeInTheDocument()
    expect(screen.getByText('formatted:2026-04-01T00:00:00Z')).toBeInTheDocument()
    expect(screen.getByText('formatted:2026-04-02T00:00:00Z')).toBeInTheDocument()
  })

  it('renders the no-diff and error states', async () => {
    mockCompare.mockResolvedValueOnce({
      snapshot1: { created_at: '2026-04-01T00:00:00Z' },
      snapshot2: { created_at: '2026-04-02T00:00:00Z' },
      changes: {
        added: [],
        removed: [],
        modified: [],
      },
    })

    const { rerender } = render(
      <SnapshotComparisonDialog snapshotId1="snap-1" snapshotId2="snap-2" onClose={vi.fn()} />,
    )

    expect(await screen.findByText('No differences')).toBeInTheDocument()

    mockCompare.mockRejectedValueOnce(new Error('compare failed'))
    rerender(<SnapshotComparisonDialog snapshotId1="snap-a" snapshotId2="snap-b" onClose={vi.fn()} />)

    await waitFor(() => {
      expect(loggerError).toHaveBeenCalledWith('Failed to load comparison:', expect.any(Error))
      expect(screen.getByText('Failed to load comparison')).toBeInTheDocument()
    })
  })
})
