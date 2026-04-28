import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as React from 'react'
import { MemoryRouter } from 'react-router-dom'

// Mock dependencies BEFORE importing Layout
const mockOpenSearch = vi.fn()
const mockSetActivePanel = vi.fn()
const mockSwitchToEditor = vi.fn()

// Create mutable mock values
let mockIsMobile = false
let mockActivePanel: 'files' | 'editor' | 'chat' = 'editor'

// Mock hooks
vi.mock('../../hooks/useMediaQuery', () => ({
   
  useIsMobile: vi.fn(() => mockIsMobile),
  useIsTablet: vi.fn(() => false),
}))

vi.mock('../../contexts/MobileLayoutContext', () => ({
  useMobileLayout: () => ({
    activePanel: mockActivePanel,
    setActivePanel: mockSetActivePanel,
    switchToEditor: mockSwitchToEditor,
    switchToFiles: vi.fn(),
    switchToChat: vi.fn(),
    isMobile: mockIsMobile,
  }),
  MobileLayoutProvider: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
}))

vi.mock('../../contexts/FileSearchContext', () => ({
  useFileSearchContext: () => ({
    isSearchOpen: false,
    openSearch: mockOpenSearch,
    closeSearch: vi.fn(),
    toggleSearch: vi.fn(),
  }),
  FileSearchProvider: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
}))

vi.mock('../../contexts/ProjectContext', () => ({
  useProject: () => ({
    project: null,
    isLoading: false,
    error: null,
    refetchProject: vi.fn(),
    selectedFile: null,
    setSelectedFile: vi.fn(),
    createProject: vi.fn(),
    updateProject: vi.fn(),
    deleteProject: vi.fn(),
  }),
  ProjectProvider: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
}))

vi.mock('../../contexts/MaterialAttachmentContext', () => ({
  useMaterialAttachment: () => ({
    addMaterial: vi.fn(),
    removeMaterial: vi.fn(),
  }),
  MaterialAttachmentProvider: ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
}))

vi.mock('../Header', () => ({
  Header: () => React.createElement('header', { 'data-testid': 'header' }, 'Header'),
}))

vi.mock('../BottomTabs', () => ({
  BottomTabs: ({
    activeTab,
    onTabChange,
  }: {
    activeTab: string
    onTabChange: (tab: string) => void
  }) =>
    React.createElement(
      'nav',
      { 'data-testid': 'bottom-tabs' },
      React.createElement('button', { onClick: () => onTabChange('files') }, 'Files'),
      React.createElement('button', { onClick: () => onTabChange('editor') }, 'Editor'),
      React.createElement('button', { onClick: () => onTabChange('chat') }, 'Chat'),
      React.createElement('span', null, `Active: ${activeTab}`)
    ),
}))

vi.mock('react-resizable-panels', () => ({
  Panel: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'panel' }, children),
  Group: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'group' }, children),
  Separator: () => React.createElement('div', { 'data-testid': 'separator' }),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) =>
      typeof fallback === 'string' ? fallback : key,
  }),
}))

// Import Layout after mocks are set up
import { Layout } from '../Layout'

const leftPanel = React.createElement('div', { 'data-testid': 'left-panel' }, 'Left Panel')
const middlePanel = React.createElement('div', { 'data-testid': 'middle-panel' }, 'Middle Panel')
const rightPanel = React.createElement('div', { 'data-testid': 'right-panel' }, 'Right Panel')

// Helper function to render with Router context (needed for SidebarTabs which uses useNavigate)
const renderWithRouter = (ui: React.ReactElement) => {
  const Wrapper = ({ children }: { children: React.ReactElement }) => (
    <MemoryRouter initialEntries={['/project/test-project-id']}>
      {children}
    </MemoryRouter>
  )
  return {
    ...render(ui, { wrapper: Wrapper }),
    rerenderWithRouter: (newUi: React.ReactElement) => {
      return render(newUi, { wrapper: Wrapper })
    }
  }
}

describe('Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsMobile = false
    mockActivePanel = 'editor'
  })

  afterEach(() => {
    mockIsMobile = false
    mockActivePanel = 'editor'
  })

  describe('Desktop Layout', () => {
    it('renders three-panel layout', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      expect(screen.getByTestId('header')).toBeInTheDocument()
      // Desktop layout uses Sidebar component (not left prop), editor-panel, and chat-panel
      expect(screen.getByTestId('editor-panel')).toBeInTheDocument()
      expect(screen.getByTestId('chat-panel')).toBeInTheDocument()
      // middle and right panels are nested inside editor-panel and chat-panel
      expect(screen.getByTestId('middle-panel')).toBeInTheDocument()
      expect(screen.getByTestId('right-panel')).toBeInTheDocument()
    })

    it('renders panels in correct order', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const panels = screen.getAllByTestId('panel')
      expect(panels).toHaveLength(3)
    })

    it('renders separators between panels', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const separators = screen.getAllByTestId('separator')
      expect(separators).toHaveLength(2)
    })

    it('renders header at the top', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const header = screen.getByTestId('header')
      expect(header.tagName).toBe('HEADER')
    })

    it('contains group element for panel layout', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const group = screen.getByTestId('group')
      expect(group).toBeInTheDocument()
    })

    it('has proper panel structure', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const panels = screen.getAllByTestId('panel')
      expect(panels).toHaveLength(3)

      // First panel contains Sidebar (not left prop), middle panel contains editor, right panel contains chat
      expect(panels[0]).toBeInTheDocument() // Sidebar
      expect(panels[1]).toHaveTextContent('Middle Panel')
      expect(panels[2]).toHaveTextContent('Right Panel')
    })

    it('listens for Cmd+K keyboard shortcut', async () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      fireEvent.keyDown(window, { metaKey: true, key: 'k' })

      await waitFor(() => {
        expect(mockOpenSearch).toHaveBeenCalled()
      })
    })

    it('listens for Ctrl+K keyboard shortcut', async () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      fireEvent.keyDown(window, { ctrlKey: true, key: 'k' })

      await waitFor(() => {
        expect(mockOpenSearch).toHaveBeenCalled()
      })
    })

    it('does not trigger search on regular key press', async () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      // Clear any previous calls
      mockOpenSearch.mockClear()

      fireEvent.keyDown(window, { key: 'k' })

      // Wait a bit to ensure no call is made
      await new Promise(resolve => setTimeout(resolve, 100))

      expect(mockOpenSearch).not.toHaveBeenCalled()
    })

    it('does not trigger search on Cmd+other key', async () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      // Clear any previous calls
      mockOpenSearch.mockClear()

      fireEvent.keyDown(window, { metaKey: true, key: 'p' })

      await new Promise(resolve => setTimeout(resolve, 100))

      expect(mockOpenSearch).not.toHaveBeenCalled()
    })

    it('does not render bottom tabs in desktop mode', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      expect(screen.queryByTestId('bottom-tabs')).not.toBeInTheDocument()
    })
  })

  describe('Mobile Layout', () => {
    beforeEach(() => {
      mockIsMobile = true
    })

    it('renders mobile layout when isMobile is true', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      expect(screen.getByTestId('header')).toBeInTheDocument()
      expect(screen.getByTestId('bottom-tabs')).toBeInTheDocument()
    })

    it('renders only active panel in mobile mode', () => {
      mockActivePanel = 'editor'
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      // In mobile layout, all panels are rendered but hidden with CSS (opacity-0, aria-hidden)
      // The active panel should be visible (not aria-hidden), inactive panels should be hidden
      const middlePanelElement = screen.getByTestId('middle-panel')
      expect(middlePanelElement).toBeInTheDocument()
      expect(middlePanelElement.closest('[aria-hidden="true"]')).toBeNull()

      // Inactive panels exist in DOM but are hidden
      const leftPanelElement = screen.queryByTestId('left-panel')
      if (leftPanelElement) {
        expect(leftPanelElement.closest('[aria-hidden="true"]')).not.toBeNull()
      }

      const rightPanelElement = screen.queryByTestId('right-panel')
      if (rightPanelElement) {
        expect(rightPanelElement.closest('[aria-hidden="true"]')).not.toBeNull()
      }
    })

    it('shows files panel when activePanel is files', () => {
      mockActivePanel = 'files'
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      // Files panel in mobile layout uses MobileFileTree, not the left prop
      // Check that inactive panels are hidden (aria-hidden)
      const middlePanelElement = screen.queryByTestId('middle-panel')
      if (middlePanelElement) {
        expect(middlePanelElement.closest('[aria-hidden="true"]')).not.toBeNull()
      }

      const rightPanelElement = screen.queryByTestId('right-panel')
      if (rightPanelElement) {
        expect(rightPanelElement.closest('[aria-hidden="true"]')).not.toBeNull()
      }
    })

    it('shows chat panel when activePanel is chat', () => {
      mockActivePanel = 'chat'
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      // Chat panel should be visible (not aria-hidden)
      const rightPanelElement = screen.getByTestId('right-panel')
      expect(rightPanelElement).toBeInTheDocument()
      expect(rightPanelElement.closest('[aria-hidden="true"]')).toBeNull()

      // Inactive panels should be hidden
      const leftPanelElement = screen.queryByTestId('left-panel')
      if (leftPanelElement) {
        expect(leftPanelElement.closest('[aria-hidden="true"]')).not.toBeNull()
      }

      const middlePanelElement = screen.queryByTestId('middle-panel')
      if (middlePanelElement) {
        expect(middlePanelElement.closest('[aria-hidden="true"]')).not.toBeNull()
      }
    })

    it('renders bottom navigation tabs', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      expect(screen.getByTestId('bottom-tabs')).toBeInTheDocument()
      expect(screen.getByText(/Active: editor/i)).toBeInTheDocument()
    })

    it('calls setActivePanel when tab is clicked', async () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const filesButton = screen.getByRole('button', { name: 'Files' })
      fireEvent.click(filesButton)

      await waitFor(() => {
        expect(mockSetActivePanel).toHaveBeenCalledWith('files')
      })
    })

    it('listens for Cmd+K keyboard shortcut in mobile mode', async () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      fireEvent.keyDown(window, { metaKey: true, key: 'k' })

      await waitFor(() => {
        expect(mockOpenSearch).toHaveBeenCalled()
      })
    })

    it('listens for Ctrl+K keyboard shortcut in mobile mode', async () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      fireEvent.keyDown(window, { ctrlKey: true, key: 'k' })

      await waitFor(() => {
        expect(mockOpenSearch).toHaveBeenCalled()
      })
    })

    it('removes keyboard event listener on unmount in mobile mode', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

      const { unmount } = renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      unmount()

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function))

      removeEventListenerSpy.mockRestore()
    })
  })

  describe('Responsive Behavior', () => {
    it('switches to mobile layout when isMobile becomes true', () => {
      mockIsMobile = false
      const { rerenderWithRouter } = renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      // Desktop mode - no bottom tabs
      expect(screen.queryByTestId('bottom-tabs')).not.toBeInTheDocument()

      // Switch to mobile
      mockIsMobile = true
      rerenderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      // Mobile mode - has bottom tabs
      expect(screen.getByTestId('bottom-tabs')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('has proper document structure', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      expect(screen.getByTestId('header')).toBeInTheDocument()
    })

    it('maintains focus management', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      // Focus should not be trapped
      expect(document.activeElement).toBe(document.body)
    })

    it('mobile layout has proper document structure', () => {
      mockIsMobile = true
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      expect(screen.getByTestId('header')).toBeInTheDocument()
      expect(screen.getByTestId('bottom-tabs')).toBeInTheDocument()
    })
  })

  describe('Cleanup', () => {
    it('removes keyboard event listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

      const { unmount } = renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      unmount()

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function))

      removeEventListenerSpy.mockRestore()
    })
  })

  describe('Styling', () => {
    it('has full screen container', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const header = screen.getByTestId('header')
      const container = header.closest('div')
      expect(container).toHaveClass('h-screen')
      expect(container).toHaveClass('w-screen')
    })

    it('has fixed positioning', () => {
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const header = screen.getByTestId('header')
      const container = header.closest('div')
      expect(container).toHaveClass('fixed')
      expect(container).toHaveClass('inset-0')
    })

    it('mobile layout has full screen container', () => {
      mockIsMobile = true
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const header = screen.getByTestId('header')
      const container = header.closest('div')
      expect(container).toHaveClass('h-screen')
      expect(container).toHaveClass('w-screen')
      expect(container).toHaveClass('fixed')
    })

    it('mobile layout has padding for bottom tabs', () => {
      mockIsMobile = true
      renderWithRouter(<Layout left={leftPanel} middle={middlePanel} right={rightPanel} />)

      const mainElement = screen.getByTestId('middle-panel').closest('main')
      expect(mainElement).toHaveClass('pb-14')
    })
  })
})
