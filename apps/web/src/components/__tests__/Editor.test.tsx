import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach, afterAll } from 'vitest'
import { Editor } from '../Editor'
import * as React from 'react'
import * as api from '../../lib/api'
import { ApiError } from '../../lib/apiClient'

// Mock SimpleEditor component
vi.mock('../SimpleEditor', () => ({
  SimpleEditor: ({ fileTitle, content, onTitleChange, onContentChange, onSave, onFinishReview, isStreaming }: { fileTitle: string; content: string; onTitleChange?: (value: string) => void; onContentChange?: (value: string) => void; onSave?: () => void; onFinishReview?: () => void; isStreaming?: boolean }) => (
    <div data-testid="simple-editor">
      <input
        data-testid="title-input"
        value={fileTitle}
        onChange={(e) => onTitleChange?.(e.target.value)}
      />
      <textarea
        data-testid="content-input"
        value={content}
        onChange={(e) => onContentChange?.(e.target.value)}
      />
      <button data-testid="save-button" onClick={() => onSave?.()}>
        Save
      </button>
      <button data-testid="finish-review-button" onClick={() => onFinishReview?.()}>
        Finish Review
      </button>
      <div data-testid="content-display">{content}</div>
      {isStreaming && <div data-testid="streaming-indicator">Streaming...</div>}
    </div>
  ),
}))

vi.mock('../subscription/UpgradePromptModal', () => ({
  UpgradePromptModal: ({ open, title }: { open: boolean; title: string }) =>
    open ? <div data-testid="upgrade-modal">{title}</div> : null,
}))

// Mock API calls
vi.mock('../../lib/api', () => ({
  fileApi: {
    get: vi.fn(),
    getTree: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
  fileVersionApi: {
    getVersions: vi.fn(),
    createVersion: vi.fn(),
  },
}))

// Mutable state for mocking
let mockProjectContext: {
  currentProjectId: string;
  selectedItem: { id: string; type: string; title: string } | null;
  setSelectedItem: () => void;
  streamingFileId: string | null;
  streamingContent: string;
  triggerFileTreeRefresh: () => void;
  editorRefreshVersion: number;
  lastEditedFileId: string | null;
  diffReviewState: unknown;
  acceptEdit: () => void;
  rejectEdit: () => void;
  acceptAllEdits: () => void;
  rejectAllEdits: () => void;
  exitDiffReview: () => void;
  applyDiffReviewChanges: () => void;
} | null = null

// Mock contexts
vi.mock('../../contexts/MaterialLibraryContext', () => ({
  useMaterialLibraryContext: () => ({
    preview: null,
    isPreviewLoading: false,
    libraries: [],
    clearPreview: vi.fn(),
  }),
  MaterialLibraryProvider: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
}))

vi.mock('../../contexts/MaterialAttachmentContext', () => ({
  useMaterialAttachment: () => ({
    addMaterial: vi.fn(),
    removeMaterial: vi.fn(),
  }),
  MaterialAttachmentProvider: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
}))

vi.mock('../../contexts/MobileLayoutContext', () => ({
  useMobileLayout: () => ({
    isMobile: false,
  }),
  MobileLayoutProvider: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
}))

vi.mock('../../contexts/ProjectContext', () => ({
  useProject: () => mockProjectContext,
  ProjectProvider: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'editor:placeholder.selectFile': 'Select a file to edit',
        'editor:placeholder.folderSelected': 'Folder selected: ',
        'editor:placeholder.folderHint': 'Select a file to view its content',
        'editor:placeholder.loadFailed': 'Failed to load file',
        'common:loading': 'Loading...',
        // Enhanced empty state translations
        'editor:emptyStateTitle': 'Ready to Create',
        'editor:emptyStateDescription': 'Select a file from the left panel or create a new one to begin writing your story.',
        'editor:emptyStateHint': 'Tip: Use the AI assistant on the right to help with writing, brainstorming, and more.',
        'editor:fileTree.newDraft': 'New Chapter',
        'editor:fileTree.newOutline': 'New Outline',
        'editor:fileTree.newCharacter': 'New Character Sheet',
        'editor:fileTree.newLore': 'New World Building',
        'editor:showMore': 'More options',
        'editor:showLess': 'Show less',
        'editor:fileTree.shortcutHint': 'Ctrl+K',
        'editor:fileTree.searchFiles': 'Search files',
      }
      return translations[key] || key
    },
  }),
}))

const createMockProjectContext = (overrides = {}) => ({
  currentProjectId: 'project-1',
  selectedItem: null,
  setSelectedItem: vi.fn(),
  streamingFileId: null,
  streamingContent: '',
  triggerFileTreeRefresh: vi.fn(),
  editorRefreshVersion: 0,
  lastEditedFileId: null,
  diffReviewState: null,
  acceptEdit: vi.fn(),
  rejectEdit: vi.fn(),
  acceptAllEdits: vi.fn(),
  rejectAllEdits: vi.fn(),
  exitDiffReview: vi.fn(),
  applyDiffReviewChanges: vi.fn(),
  ...overrides,
})

const mockFile = {
  id: 'file-1',
  title: 'Test Chapter',
  content: 'Test content',
  file_type: 'draft',
  parent_id: null,
}

describe('Editor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
    mockProjectContext = createMockProjectContext()
    vi.mocked(api.fileApi.get).mockResolvedValue(mockFile)
    vi.mocked(api.fileApi.getTree).mockResolvedValue({
      tree: [
        {
          id: 'project-1-lore-folder',
          title: '设定',
          file_type: 'folder',
          parent_id: null,
          order: 0,
          metadata: null,
          children: [],
        },
        {
          id: 'project-1-character-folder',
          title: '角色',
          file_type: 'folder',
          parent_id: null,
          order: 1,
          metadata: null,
          children: [],
        },
        {
          id: 'project-1-outline-folder',
          title: '大纲',
          file_type: 'folder',
          parent_id: null,
          order: 2,
          metadata: null,
          children: [],
        },
        {
          id: 'project-1-draft-folder',
          title: '正文',
          file_type: 'folder',
          parent_id: null,
          order: 3,
          metadata: null,
          children: [],
        },
      ],
    })
    vi.mocked(api.fileApi.create).mockResolvedValue({
      ...mockFile,
      id: 'file-created',
      file_type: 'draft',
      title: 'New Chapter',
    })
    vi.mocked(api.fileVersionApi.getVersions).mockResolvedValue({ total: 0, items: [] })
    vi.mocked(api.fileApi.update).mockResolvedValue({ ...mockFile, title: 'Updated Title' })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  afterAll(() => {
    vi.restoreAllMocks()
  })

  it('renders empty state when no file selected', () => {
    mockProjectContext = createMockProjectContext({ selectedItem: null })
    render(<Editor />)
    // Check for enhanced empty state elements
    expect(screen.getByText('Ready to Create')).toBeInTheDocument()
    expect(screen.getByText(/select a file from the left panel/i)).toBeInTheDocument()
  })

  it('renders action cards in empty state', () => {
    mockProjectContext = createMockProjectContext({ selectedItem: null })
    render(<Editor />)
    // Primary action cards are visible by default
    expect(screen.getByText('New Chapter')).toBeInTheDocument()
    expect(screen.getByText('New Outline')).toBeInTheDocument()
    // Secondary actions are behind "more options" toggle
    expect(screen.getByText('More options')).toBeInTheDocument()
  })

  it('creates draft in draft folder from empty state', async () => {
    mockProjectContext = createMockProjectContext({ selectedItem: null })
    render(<Editor />)

    fireEvent.click(screen.getByText('New Chapter'))

    await waitFor(() => {
      expect(api.fileApi.create).toHaveBeenCalledWith(
        'project-1',
        expect.objectContaining({
          file_type: 'draft',
          parent_id: 'project-1-draft-folder',
        })
      )
    })
  })

  it('creates outline in outline folder from empty state', async () => {
    mockProjectContext = createMockProjectContext({ selectedItem: null })
    vi.mocked(api.fileApi.create).mockResolvedValue({
      ...mockFile,
      id: 'file-outline-created',
      file_type: 'outline',
      title: 'New Outline',
    })

    render(<Editor />)

    fireEvent.click(screen.getByText('New Outline'))

    await waitFor(() => {
      expect(api.fileApi.create).toHaveBeenCalledWith(
        'project-1',
        expect.objectContaining({
          file_type: 'outline',
          parent_id: 'project-1-outline-folder',
        })
      )
    })
  })

  it('renders AI assistant hint in empty state', () => {
    mockProjectContext = createMockProjectContext({ selectedItem: null })
    render(<Editor />)
    expect(screen.getByText(/Tip: Use the AI assistant/i)).toBeInTheDocument()
  })

  it('renders keyboard shortcut hint in empty state', () => {
    mockProjectContext = createMockProjectContext({ selectedItem: null })
    render(<Editor />)
    expect(screen.getByText('Ctrl')).toBeInTheDocument()
    expect(screen.getByText('K')).toBeInTheDocument()
    expect(screen.getByText(/Search files/i)).toBeInTheDocument()
  })

  it('renders folder selected state', () => {
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'folder-1', type: 'folder', title: 'My Folder' },
    })
    render(<Editor />)
    // The component renders: {t('editor:placeholder.folderSelected')}{selectedItem.title}
    // Which translates to "Folder selected: My Folder" (concatenated text)
    expect(screen.getByText(/folder.*selected.*my folder/i)).toBeInTheDocument()
  })

  it('renders loading state while fetching file', () => {
    vi.mocked(api.fileApi.get).mockImplementation(() => new Promise(() => {}))
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
    })
    render(<Editor />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('renders error state on fetch failure', async () => {
    vi.mocked(api.fileApi.get).mockRejectedValue(new Error('Failed to fetch'))
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      diffReviewState: null,
    })
    render(<Editor />)
    await waitFor(() => {
      expect(screen.getByText(/failed/i)).toBeInTheDocument()
    })
  })

  it('renders editor with file content', async () => {
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      diffReviewState: null,
    })
    render(<Editor />)
    await waitFor(() => {
      expect(api.fileApi.get).toHaveBeenCalledWith('file-1')
      expect(screen.getByTestId('simple-editor')).toBeInTheDocument()
    })
  })

  it('creates initial version if none exists', async () => {
    vi.mocked(api.fileVersionApi.getVersions).mockResolvedValue({ total: 0, items: [] })
    vi.mocked(api.fileVersionApi.createVersion).mockResolvedValue({ id: 'version-1' })
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      diffReviewState: null,
    })
    render(<Editor />)
    await waitFor(() => {
      expect(api.fileVersionApi.createVersion).toHaveBeenCalledWith('file-1', 'Test content', {
        changeType: 'create',
        changeSource: 'system',
        changeSummary: 'Initial version',
      })
    })
  })

  it('does not create version if file has no content', async () => {
    vi.mocked(api.fileApi.get).mockResolvedValue({ ...mockFile, content: '' })
    vi.mocked(api.fileVersionApi.getVersions).mockResolvedValue({ total: 0, items: [] })
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      diffReviewState: null,
    })
    render(<Editor />)
    await waitFor(() => {
      expect(screen.getByTestId('simple-editor')).toBeInTheDocument()
    })
    expect(api.fileVersionApi.createVersion).not.toHaveBeenCalled()
  })

  it('shows upgrade modal when initial version creation is blocked by quota', async () => {
    vi.mocked(api.fileVersionApi.getVersions).mockRejectedValue(
      new ApiError(402, 'ERR_QUOTA_FILE_VERSIONS_EXCEEDED')
    )
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      diffReviewState: null,
    })

    render(<Editor />)

    await waitFor(() => {
      expect(screen.getByTestId('upgrade-modal')).toBeInTheDocument()
    })
  })

  it('displays streaming content when file is being streamed', async () => {
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      streamingFileId: 'file-1',
      streamingContent: 'Streaming content...',
      diffReviewState: null,
    })
    render(<Editor />)
    await waitFor(() => {
      // The streaming content should be displayed in the editor
      expect(screen.getByTestId('content-display')).toHaveTextContent('Streaming content...')
    })
  })

  it('handles save operation', async () => {
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      diffReviewState: null,
    })
    render(<Editor />)
    await waitFor(() => {
      expect(screen.getByTestId('simple-editor')).toBeInTheDocument()
    })
    const saveButton = screen.getByTestId('save-button')
    fireEvent.click(saveButton)
    await waitFor(() => {
      expect(api.fileApi.update).toHaveBeenCalled()
    })
  })

  it('shows upgrade modal when save is blocked by file version quota', async () => {
    vi.mocked(api.fileApi.update).mockRejectedValue(
      new ApiError(402, 'ERR_QUOTA_FILE_VERSIONS_EXCEEDED')
    )
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      diffReviewState: null,
    })

    render(<Editor />)

    await waitFor(() => {
      expect(screen.getByTestId('simple-editor')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('save-button'))

    await waitFor(() => {
      expect(screen.getByTestId('upgrade-modal')).toBeInTheDocument()
    })
  })

  it('triggers file tree refresh when title changes', async () => {
    const triggerFileTreeRefresh = vi.fn()
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      triggerFileTreeRefresh,
      diffReviewState: null,
    })
    render(<Editor />)
    await waitFor(() => {
      expect(screen.getByTestId('simple-editor')).toBeInTheDocument()
    })
    const titleInput = screen.getByTestId('title-input')
    fireEvent.change(titleInput, { target: { value: 'New Title' } })
    // Click save to trigger the refresh
    const saveButton = screen.getByTestId('save-button')
    fireEvent.click(saveButton)
    await waitFor(() => {
      expect(triggerFileTreeRefresh).toHaveBeenCalled()
    })
  })

  it('saves reviewed content with ai version intent', async () => {
    const triggerFileTreeRefresh = vi.fn()
    const exitDiffReview = vi.fn()
    const applyDiffReviewChanges = vi.fn().mockReturnValue('Reviewed AI content')

    vi.mocked(api.fileVersionApi.getVersions).mockResolvedValue({ total: 1, items: [] })
    mockProjectContext = createMockProjectContext({
      selectedItem: { id: 'file-1', type: 'draft', title: 'Test Chapter' },
      diffReviewState: {
        isReviewing: true,
        fileId: 'file-1',
        originalContent: 'Original content',
        modifiedContent: 'Reviewed AI content',
        pendingEdits: [],
      },
      triggerFileTreeRefresh,
      exitDiffReview,
      applyDiffReviewChanges,
    })

    render(<Editor />)

    await waitFor(() => {
      expect(screen.getByTestId('simple-editor')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('finish-review-button'))

    await waitFor(() => {
      expect(api.fileApi.update).toHaveBeenCalledWith('file-1', {
        content: 'Reviewed AI content',
        change_type: 'ai_edit',
        change_source: 'ai',
        change_summary: 'AI edit (reviewed)',
      })
      expect(exitDiffReview).toHaveBeenCalled()
      expect(triggerFileTreeRefresh).toHaveBeenCalled()
    })
  })
})
