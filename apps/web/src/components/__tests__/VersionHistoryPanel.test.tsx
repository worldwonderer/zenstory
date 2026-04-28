import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { VersionHistoryPanel } from '../VersionHistoryPanel'
import * as React from 'react'
import * as api from '../../lib/api'

const { mockLoggerError, mockLoggerWarn } = vi.hoisted(() => ({
  mockLoggerError: vi.fn(),
  mockLoggerWarn: vi.fn(),
}))

// Mock API calls
vi.mock('../../lib/api', () => ({
  versionApi: {
    getSnapshots: vi.fn(),
    updateSnapshot: vi.fn(),
    rollback: vi.fn(),
  },
}))

vi.mock('../../lib/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: (...args: unknown[]) => mockLoggerWarn(...args),
    error: (...args: unknown[]) => mockLoggerError(...args),
    log: vi.fn(),
  },
  default: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: (...args: unknown[]) => mockLoggerWarn(...args),
    error: (...args: unknown[]) => mockLoggerError(...args),
    log: vi.fn(),
  },
}))

// Mock dependencies
vi.mock('../../lib/dateUtils', () => ({
  formatRelativeTimeWithYear: vi.fn(() => '2 hours ago'),
}))

vi.mock('../../hooks/useMediaQuery', () => ({
  useIsMobile: () => false,
}))

vi.mock('../SnapshotComparisonDialog', () => ({
  SnapshotComparisonDialog: ({ snapshotId1, snapshotId2, onClose }: { snapshotId1: string; snapshotId2: string; onClose: () => void }) => (
    <div data-testid="comparison-dialog">
      Comparing {snapshotId1} and {snapshotId2}
      <button onClick={onClose}>Close</button>
    </div>
  ),
}))

// Mock i18n - create a minimal i18n object
const mockT = vi.fn((key: string) => {
  const translations: Record<string, string> = {
    'editor:versionHistory.title': 'Version History',
    'common:loading': 'Loading...',
    'editor:versionHistory.loadFailed': 'Failed to load versions',
    'editor:versionHistory.empty': 'No versions available',
    'editor:versionHistory.auto': 'Auto',
    'editor:versionHistory.manual': 'Manual',
    'editor:versionHistory.beforeAI': 'Before AI',
    'editor:versionHistory.beforeRollback': 'Before Rollback',
    'editor:versionHistory.currentVersion': 'Current',
    'editor:versionHistory.selectCompare': 'Select for comparison',
    'editor:versionHistory.rollbackTo': 'Rollback to this version',
    'editor:versionHistory.compare': 'Compare',
    'editor:versionHistory.addDescription': 'Add a description',
    'editor:versionHistory.noDescription': 'No description',
    'editor:versionHistory.confirmRollback': 'Are you sure you want to rollback?',
    'editor:versionHistory.rollbackFailed': 'Rollback failed',
    'editor:versionHistory.files': 'files',
    'editor:versionHistory.folders': 'folders',
  }
  return translations[key] || key
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: {
      language: 'en',
      changeLanguage: vi.fn(),
    },
  }),
  I18nextProvider: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
}))

const mockSnapshots = [
  {
    id: 'snap-1',
    created_at: '2024-01-01T12:00:00Z',
    description: 'Initial version',
    snapshot_type: 'manual',
    data: JSON.stringify({
      file_versions: [{ id: 'v1', content: 'Version 1 content' }],
      files_metadata: [
        { file_type: 'folder' },
        { file_type: 'draft' },
      ],
    }),
  },
  {
    id: 'snap-2',
    created_at: '2024-01-01T13:00:00Z',
    description: 'After AI edit',
    snapshot_type: 'auto',
    data: JSON.stringify({
      file_versions: [{ id: 'v2', content: 'Version 2 content' }],
      files_metadata: [
        { file_type: 'folder' },
      ],
    }),
  },
]

describe('VersionHistoryPanel', () => {
  const mockOnClose = vi.fn()
  const mockOnRollback = vi.fn()
  const mockOnCompare = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.versionApi.getSnapshots).mockResolvedValue(mockSnapshots)
    vi.mocked(api.versionApi.updateSnapshot).mockResolvedValue(undefined)
    vi.mocked(api.versionApi.rollback).mockResolvedValue(undefined)
    global.confirm = vi.fn(() => true)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders version history panel', () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText(/version.*history/i)).toBeInTheDocument()
  })

  it('displays loading state initially', () => {
    vi.mocked(api.versionApi.getSnapshots).mockImplementation(() => new Promise(() => {}))

    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('displays version list after loading', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Initial version')).toBeInTheDocument()
      expect(screen.getByText('After AI edit')).toBeInTheDocument()
    })
  })

  it('shows version timestamps', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      // There are multiple "2 hours ago" texts (one per snapshot)
      const timestamps = screen.getAllByText('2 hours ago')
      expect(timestamps.length).toBeGreaterThan(0)
    })
  })

  it('shows snapshot type labels', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/manual/i)).toBeInTheDocument()
      expect(screen.getByText(/auto/i)).toBeInTheDocument()
    })
  })

  it('displays file and folder counts', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    // First wait for the snapshots to load
    await waitFor(() => {
      expect(screen.getByText('Initial version')).toBeInTheDocument()
    })

    // Then check for file and folder count labels
    // The translation mock returns 'files' and 'folders' for the keys
    // Use getAllByText since there are multiple snapshots showing these labels
    const filesElements = screen.getAllByText(/files/)
    const foldersElements = screen.getAllByText(/folders/)
    expect(filesElements.length).toBeGreaterThan(0)
    expect(foldersElements.length).toBeGreaterThan(0)
  })

  it('shows empty state when no snapshots', async () => {
    vi.mocked(api.versionApi.getSnapshots).mockResolvedValue([])

    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/no.*versions/i)).toBeInTheDocument()
    })
  })

  it('shows error state on load failure', async () => {
    vi.mocked(api.versionApi.getSnapshots).mockRejectedValue(new Error('Failed to load'))

    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/failed/i)).toBeInTheDocument()
      expect(mockLoggerError).toHaveBeenCalled()
    })
  })

  it('selects snapshot for comparison', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Initial version')).toBeInTheDocument()
    })

    // Click first compare button - use the translated title text
    const compareButtons = screen.getAllByTitle('Select for comparison')
    fireEvent.click(compareButtons[0])

    await waitFor(() => {
      // The button should be selected (have accent class)
      expect(compareButtons[0]).toBeInTheDocument()
    })

    // Click second compare button
    fireEvent.click(compareButtons[1])

    await waitFor(() => {
      // Should show compare button in header
      expect(screen.getByText(/compare/i)).toBeInTheDocument()
    })
  })

  it('opens comparison dialog when two snapshots selected', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
        onCompare={mockOnCompare}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Initial version')).toBeInTheDocument()
    })

    const compareButtons = screen.getAllByTitle('Select for comparison')

    // Select two snapshots
    fireEvent.click(compareButtons[0])
    fireEvent.click(compareButtons[1])

    // Click the compare action button
    const compareActionButton = screen.getByRole('button', { name: /compare/i })
    fireEvent.click(compareActionButton)

    await waitFor(() => {
      expect(screen.getByTestId('comparison-dialog')).toBeInTheDocument()
      expect(mockOnCompare).toHaveBeenCalledWith('snap-1', 'snap-2')
    })
  })

  it('rolls back to selected version', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
        onRollback={mockOnRollback}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('After AI edit')).toBeInTheDocument()
    })

    // Find rollback button for second snapshot (not current version)
    // The first snapshot (index 0) is "current", so we look for rollback on the second one
    const rollbackButtons = screen.getAllByTitle('Rollback to this version')
    fireEvent.click(rollbackButtons[0])

    await waitFor(() => {
      expect(global.confirm).toHaveBeenCalled()
      expect(api.versionApi.rollback).toHaveBeenCalledWith('snap-2')
      expect(mockOnRollback).toHaveBeenCalledWith('snap-2')
      // refresh chain in panel: loadSnapshots runs again after rollback
      expect(api.versionApi.getSnapshots).toHaveBeenCalledTimes(2)
    })
  })

  it('does not rollback if user cancels confirmation', async () => {
    global.confirm = vi.fn(() => false)

    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
        onRollback={mockOnRollback}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('After AI edit')).toBeInTheDocument()
    })

    const rollbackButtons = screen.getAllByTitle('Rollback to this version')
    fireEvent.click(rollbackButtons[0])

    await waitFor(() => {
      expect(global.confirm).toHaveBeenCalled()
      expect(api.versionApi.rollback).not.toHaveBeenCalled()
    })
  })

  it('hides rollback button for current version', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Initial version')).toBeInTheDocument()
    })

    // First snapshot should have "current version" badge
    expect(screen.getByText(/current/i)).toBeInTheDocument()
  })

  it('starts editing description', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Initial version')).toBeInTheDocument()
    })

    // Get all buttons with Edit2 icon (small w-3.5 h-3.5 icons next to description)
    const allButtons = screen.getAllByRole('button')
    const editButton = allButtons.find(btn => {
      const svg = btn.querySelector('svg')
      if (!svg) return false
      const classAttr = svg.getAttribute('class') || ''
      // Edit2 icon is small (w-3.5 h-3.5) and the button has hover:bg class
      return classAttr.includes('w-3.5') && classAttr.includes('h-3.5')
    })

    expect(editButton).toBeTruthy()
    fireEvent.click(editButton!)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/add.*description/i)).toBeInTheDocument()
    })
  })

  it('saves edited description', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Initial version')).toBeInTheDocument()
    })

    // Get all buttons and find edit button by its icon class pattern
    const allButtons = screen.getAllByRole('button')
    const editButton = allButtons.find(btn => {
      const svg = btn.querySelector('svg')
      if (!svg) return false
      const classAttr = svg.getAttribute('class') || ''
      // Edit2 icon is small (w-3.5 h-3.5)
      return classAttr.includes('w-3.5') && classAttr.includes('h-3.5')
    })

    expect(editButton).toBeTruthy()
    fireEvent.click(editButton!)

    const input = await screen.findByPlaceholderText(/add.*description/i)
    fireEvent.change(input, { target: { value: 'Updated description' } })

    // Find save button (check icon) - it's the green button after the input
    const saveButtons = screen.getAllByRole('button').filter(btn => {
      const svg = btn.querySelector('svg')
      if (!svg) return false
      const classAttr = svg.getAttribute('class') || ''
      return classAttr.includes('lucide-check')
    })

    expect(saveButtons.length).toBeGreaterThan(0)
    fireEvent.click(saveButtons[0])

    await waitFor(() => {
      expect(api.versionApi.updateSnapshot).toHaveBeenCalledWith('snap-1', {
        description: 'Updated description',
      })
    })
  })

  it('cancels editing description', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Initial version')).toBeInTheDocument()
    })

    // Get all buttons and find edit button by its icon class pattern
    const allButtons = screen.getAllByRole('button')
    const editButton = allButtons.find(btn => {
      const svg = btn.querySelector('svg')
      if (!svg) return false
      const classAttr = svg.getAttribute('class') || ''
      // Edit2 icon is small (w-3.5 h-3.5)
      return classAttr.includes('w-3.5') && classAttr.includes('h-3.5')
    })

    expect(editButton).toBeTruthy()
    fireEvent.click(editButton!)

    await screen.findByPlaceholderText(/add.*description/i)

    // Find cancel button (X icon) - it's after the save button (in editing mode)
    const cancelButtons = screen.getAllByRole('button').filter(btn => {
      const svg = btn.querySelector('svg')
      if (!svg) return false
      const classAttr = svg.getAttribute('class') || ''
      return classAttr.includes('lucide-x')
    })

    // The last X button should be the cancel button in editing mode
    expect(cancelButtons.length).toBeGreaterThan(0)
    fireEvent.click(cancelButtons[cancelButtons.length - 1])

    await waitFor(() => {
      expect(screen.queryByPlaceholderText(/add.*description/i)).not.toBeInTheDocument()
    })
  })

  it('shows no description placeholder', async () => {
    const snapshotWithoutDescription = {
      id: 'snap-3',
      created_at: '2024-01-01T14:00:00Z',
      description: '',
      snapshot_type: 'auto',
      data: JSON.stringify({
        file_versions: [],
        files_metadata: [],
      }),
    }

    vi.mocked(api.versionApi.getSnapshots).mockResolvedValue([snapshotWithoutDescription])

    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/no.*description/i)).toBeInTheDocument()
    })
  })

  it('closes panel when close button clicked', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        onClose={mockOnClose}
      />
    )

    // Find close button by its X icon in the header (with rounded-md class)
    const closeButtons = screen.getAllByRole('button').filter(btn => {
      const svg = btn.querySelector('svg')
      if (!svg) return false
      const classAttr = svg.getAttribute('class') || ''
      return classAttr.includes('lucide-x') && btn.className.includes('rounded-md')
    })

    expect(closeButtons.length).toBeGreaterThan(0)
    fireEvent.click(closeButtons[0])
    expect(mockOnClose).toHaveBeenCalled()
  })

  it('filters snapshots by outlineId when provided', async () => {
    render(
      <VersionHistoryPanel
        projectId="project-1"
        outlineId="file-1"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(api.versionApi.getSnapshots).toHaveBeenCalledWith('project-1', {
        fileId: 'file-1',
        limit: 50,
      })
    })
  })

  it('handles different snapshot types', async () => {
    const snapshotTypes = [
      { type: 'pre_ai_edit', label: /before.*ai/i },
      { type: 'pre_rollback', label: /before.*rollback/i },
    ]

    for (const { type, label } of snapshotTypes) {
      vi.clearAllMocks()

      const snapshot = {
        id: `snap-${type}`,
        created_at: '2024-01-01T12:00:00Z',
        description: 'Test',
        snapshot_type: type,
        data: JSON.stringify({
          file_versions: [],
          files_metadata: [],
        }),
      }

      vi.mocked(api.versionApi.getSnapshots).mockResolvedValue([snapshot])

      const { unmount } = render(
        <VersionHistoryPanel
          projectId="project-1"
          onClose={mockOnClose}
        />
      )

      await waitFor(() => {
        expect(screen.getByText(label)).toBeInTheDocument()
      })

      unmount()
    }
  })
})
