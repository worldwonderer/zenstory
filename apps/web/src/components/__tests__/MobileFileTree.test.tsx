import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MobileFileTree } from '../MobileFileTree';

const {
  mockSetSelectedItem,
  mockSwitchToEditor,
  mockGetTree,
  mockUpload,
  mockAddMaterial,
  mockRemoveMaterial,
  mockIsMaterialAttached,
  mockToastSuccess,
} = vi.hoisted(() => ({
  mockSetSelectedItem: vi.fn(),
  mockSwitchToEditor: vi.fn(),
  mockGetTree: vi.fn(),
  mockUpload: vi.fn(),
  mockAddMaterial: vi.fn(() => true),
  mockRemoveMaterial: vi.fn(),
  mockIsMaterialAttached: vi.fn(() => false),
  mockToastSuccess: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../contexts/ProjectContext', () => ({
  useProject: () => ({
    currentProjectId: 'project-1',
    selectedItem: null,
    setSelectedItem: mockSetSelectedItem,
    fileTreeVersion: 0,
  }),
}));

vi.mock('../../contexts/MobileLayoutContext', () => ({
  useMobileLayout: () => ({
    switchToEditor: mockSwitchToEditor,
  }),
}));

vi.mock('../../contexts/MaterialAttachmentContext', () => ({
  MAX_ATTACHED_MATERIALS: 5,
  useMaterialAttachment: () => ({
    addMaterial: mockAddMaterial,
    removeMaterial: mockRemoveMaterial,
    isMaterialAttached: mockIsMaterialAttached,
    isAtLimit: false,
  }),
}));

vi.mock('../../lib/toast', () => ({
  toast: {
    success: mockToastSuccess,
  },
}));

vi.mock('../../lib/api', () => ({
  fileApi: {
    getTree: (...args: unknown[]) => mockGetTree(...args),
    upload: (...args: unknown[]) => mockUpload(...args),
    create: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../SearchResultsDropdown', () => ({
  default: () => null,
  SearchResultsDropdown: () => null,
}));

vi.mock('../FileSearchInput', () => ({
  FileSearchInput: ({
    value,
    onChange,
    onFocus,
    onBlur,
    onKeyDown,
    placeholder,
  }: {
    value: string;
    onChange: (v: string) => void;
    onFocus?: () => void;
    onBlur?: () => void;
    onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
    placeholder?: string;
  }) => (
    <input
      data-testid="search-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onFocus={onFocus}
      onBlur={onBlur}
      onKeyDown={onKeyDown}
      placeholder={placeholder}
    />
  ),
}));

describe('MobileFileTree', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows upload entry on material folder and uploads txt file', async () => {
    mockGetTree.mockResolvedValue({
      tree: [
        {
          id: 'material-folder-id',
          title: '素材',
          file_type: 'folder',
          parent_id: null,
          order: 0,
          content: '',
          metadata: null,
          children: [],
        },
      ],
    });
    mockUpload.mockResolvedValue({
      id: 'snippet-1',
    });

    render(<MobileFileTree />);

    const uploadButton = await screen.findByTitle('editor:fileTree.uploadMaterial');
    expect(uploadButton).toBeInTheDocument();

    const inputClickSpy = vi.spyOn(HTMLInputElement.prototype, 'click');
    fireEvent.click(uploadButton);
    expect(inputClickSpy).toHaveBeenCalled();
    inputClickSpy.mockRestore();

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['line1\nline2'], 'material.txt', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockUpload).toHaveBeenCalledWith('project-1', file);
    });
    expect(mockToastSuccess).toHaveBeenCalledWith('editor:fileTree.uploadSuccess');
  });

  it('adds snippet to chat context when clicking add button', async () => {
    mockIsMaterialAttached.mockReturnValue(false);
    mockGetTree.mockResolvedValue({
      tree: [
        {
          id: 'snippet-1',
          title: '片段A',
          file_type: 'snippet',
          parent_id: null,
          order: 0,
          content: '',
          metadata: null,
          children: [],
        },
      ],
    });

    render(<MobileFileTree />);

    const addButton = await screen.findByTitle('editor:fileTree.addToChat');
    fireEvent.click(addButton);

    expect(mockAddMaterial).toHaveBeenCalledWith('snippet-1', '片段A');
  });
});
