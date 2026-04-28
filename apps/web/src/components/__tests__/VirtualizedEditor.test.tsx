import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { VirtualizedEditor } from '../VirtualizedEditor';
import { toast } from '../../lib/toast';

vi.mock('../../lib/naturalPolishApi', () => ({
  naturalPolishApi: {
    naturalPolish: vi.fn(),
  },
}));

vi.mock('../../lib/writingStatsApi', () => ({
  writingStatsApi: {
    recordStats: vi.fn(),
  },
}));

vi.mock('../../contexts/TextQuoteContext', () => ({
  useTextQuote: () => ({
    addQuote: vi.fn(),
  }),
}));

vi.mock('../../hooks/useVirtualizedEditor', () => ({
  useVirtualizedEditor: (_content: string, chunks: Array<{ id: string; content: string }>) => ({
    virtualizer: {
      measureElement: vi.fn(),
    },
    visibleChunks: chunks.map((chunk, index) => ({
      chunk,
      index,
      height: 80,
      startY: index * 80,
    })),
    totalSize: Math.max(chunks.length, 1) * 80,
  }),
  useEditorStats: (chunks: Array<{ content: string }>) => ({
    totalWords: chunks.reduce((acc, chunk) => acc + chunk.content.split(/\s+/).filter(Boolean).length, 0),
    totalChunks: chunks.length,
  }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
  }),
}));

vi.mock('../FileVersionHistory', () => ({
  FileVersionHistory: () => null,
}));

vi.mock('../InlineDiffEditor', () => ({
  InlineDiffEditor: () => null,
}));

vi.mock('../DiffToolbar', () => ({
  DiffToolbar: () => null,
}));

vi.mock('../SelectionToolbar', () => ({
  SelectionToolbar: () => null,
}));

describe('VirtualizedEditor', () => {
  const selectTextAndGetNaturalPolishButton = async (textarea: HTMLTextAreaElement) => {
    textarea.focus();
    textarea.setSelectionRange(0, 5);
    fireEvent.select(textarea);

    const button = screen.getByRole('button', { name: 'editor:naturalPolish' });
    await waitFor(() => {
      expect(button).toBeEnabled();
    });

    return button;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows natural polish action without admin gating', () => {
    render(
      <VirtualizedEditor
        projectId="project-1"
        fileId="file-1"
        fileType="draft"
        title="File 1"
        content="Hello world"
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
      />
    );

    expect(screen.getByRole('button', { name: 'editor:naturalPolish' })).toBeInTheDocument();
  });

  it('natural polish triggers diff review with rewritten text', async () => {
    const { naturalPolishApi } = await import('../../lib/naturalPolishApi');
    const naturalPolishMock = naturalPolishApi.naturalPolish as unknown as ReturnType<typeof vi.fn>;
    naturalPolishMock.mockResolvedValueOnce('Rewritten');

    const onEnterDiffReview = vi.fn();
    const { container } = render(
      <VirtualizedEditor
        projectId="project-1"
        fileId="file-1"
        fileType="draft"
        title="File 1"
        content="Hello world"
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onEnterDiffReview={onEnterDiffReview}
      />
    );

    const textarea = container.querySelector('textarea') as HTMLTextAreaElement;
    const naturalPolishButton = await selectTextAndGetNaturalPolishButton(textarea);
    fireEvent.click(naturalPolishButton);

    await waitFor(() => {
      expect(onEnterDiffReview).toHaveBeenCalledTimes(1);
    });
    expect(onEnterDiffReview).toHaveBeenCalledWith(
      'file-1',
      'Hello world',
      'Rewritten world'
    );
  });

  it('natural polish ignores stale response after file switch', async () => {
    const { naturalPolishApi } = await import('../../lib/naturalPolishApi');
    const naturalPolishMock = naturalPolishApi.naturalPolish as unknown as ReturnType<typeof vi.fn>;

    let resolvePolish: (value: string) => void = () => {};
    const deferred = new Promise<string>((resolve) => {
      resolvePolish = resolve;
    });
    naturalPolishMock.mockReturnValueOnce(deferred);

    const onEnterDiffReview = vi.fn();
    const { container, rerender } = render(
      <VirtualizedEditor
        projectId="project-1"
        fileId="file-1"
        fileType="draft"
        title="File 1"
        content="Hello world"
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onEnterDiffReview={onEnterDiffReview}
      />
    );

    const textarea = container.querySelector('textarea') as HTMLTextAreaElement;
    const naturalPolishButton = await selectTextAndGetNaturalPolishButton(textarea);
    fireEvent.click(naturalPolishButton);

    rerender(
      <VirtualizedEditor
        projectId="project-1"
        fileId="file-2"
        fileType="draft"
        title="File 2"
        content="Another content"
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onEnterDiffReview={onEnterDiffReview}
      />
    );

    resolvePolish('Rewritten');
    await waitFor(() => {
      expect(true).toBe(true);
    });

    expect(onEnterDiffReview).not.toHaveBeenCalled();
  });

  it('natural polish surfaces backend error message', async () => {
    const { naturalPolishApi } = await import('../../lib/naturalPolishApi');
    const naturalPolishMock = naturalPolishApi.naturalPolish as unknown as ReturnType<typeof vi.fn>;
    naturalPolishMock.mockRejectedValueOnce(new Error('ERR_QUOTA_AI_CONVERSATIONS_EXCEEDED'));

    const toastErrorSpy = vi.spyOn(toast, 'error').mockImplementation(() => {});

    const { container } = render(
      <VirtualizedEditor
        projectId="project-1"
        fileId="file-1"
        fileType="draft"
        title="File 1"
        content="Hello world"
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
      />
    );

    const textarea = container.querySelector('textarea') as HTMLTextAreaElement;
    const naturalPolishButton = await selectTextAndGetNaturalPolishButton(textarea);
    fireEvent.click(naturalPolishButton);

    await waitFor(() => {
      expect(toastErrorSpy).toHaveBeenCalledWith('ERR_QUOTA_AI_CONVERSATIONS_EXCEEDED');
    });
  });

  it('resets dirty state when switching files', () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onTitleChange = vi.fn();
    const onContentChange = vi.fn();

    const { rerender } = render(
      <VirtualizedEditor
        fileId="file-1"
        title="File 1"
        content="Original content from file one"
        onTitleChange={onTitleChange}
        onContentChange={onContentChange}
        onSave={onSave}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('editor:placeholder.titlePlaceholder'), {
      target: { value: 'File 1 updated title' },
    });

    expect(screen.getByText('editor:unsaved')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'editor:save' })).toBeEnabled();

    rerender(
      <VirtualizedEditor
        fileId="file-2"
        title="File 2"
        content="Another file content"
        onTitleChange={onTitleChange}
        onContentChange={onContentChange}
        onSave={onSave}
      />
    );

    expect(screen.queryByText('editor:unsaved')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'editor:save' })).toBeDisabled();
  });

  it('does not create content version when only title changes after async file switch', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onTitleChange = vi.fn();
    const onContentChange = vi.fn();

    const { rerender } = render(
      <VirtualizedEditor
        fileId="file-1"
        title="File 1"
        content="11111111111111111111"
        onTitleChange={onTitleChange}
        onContentChange={onContentChange}
        onSave={onSave}
      />
    );

    rerender(
      <VirtualizedEditor
        fileId="file-2"
        title="File 2"
        content="11111111111111111111"
        onTitleChange={onTitleChange}
        onContentChange={onContentChange}
        onSave={onSave}
      />
    );

    rerender(
      <VirtualizedEditor
        fileId="file-2"
        title="File 2"
        content="BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        onTitleChange={onTitleChange}
        onContentChange={onContentChange}
        onSave={onSave}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('editor:placeholder.titlePlaceholder'), {
      target: { value: 'File 2 - Renamed' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'editor:save' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });
    expect(onSave).toHaveBeenCalledWith(undefined);
  });

  it('saves once with edit version intent for significant content changes in small docs', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const StatefulEditor = () => {
      const [localTitle, setLocalTitle] = useState('Small File');
      const [localContent, setLocalContent] = useState('Old content for small doc');
      return (
        <VirtualizedEditor
          fileId="file-small-edit"
          title={localTitle}
          content={localContent}
          onTitleChange={setLocalTitle}
          onContentChange={setLocalContent}
          onSave={onSave}
        />
      );
    };

    const { container } = render(<StatefulEditor />);

    const textarea = container.querySelector('textarea');
    expect(textarea).toBeTruthy();
    fireEvent.change(textarea as HTMLTextAreaElement, {
      target: { value: 'Old content for small doc with extra content over ten chars' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'editor:save' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });
    expect(onSave).toHaveBeenCalledWith({
      change_type: 'edit',
      change_source: 'user',
      word_count: 11,
    });
  });

  it('saves once with skip_version for minor content changes in small docs', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const StatefulEditor = () => {
      const [localTitle, setLocalTitle] = useState('Small File');
      const [localContent, setLocalContent] = useState('1234567890abcdefghij');
      return (
        <VirtualizedEditor
          fileId="file-small-skip"
          title={localTitle}
          content={localContent}
          onTitleChange={setLocalTitle}
          onContentChange={setLocalContent}
          onSave={onSave}
        />
      );
    };

    const { container } = render(<StatefulEditor />);

    const textarea = container.querySelector('textarea');
    expect(textarea).toBeTruthy();
    fireEvent.change(textarea as HTMLTextAreaElement, {
      target: { value: '1234567890abcdefghik' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'editor:save' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });
    expect(onSave).toHaveBeenCalledWith({
      skip_version: true,
      word_count: 1,
    });
  });

  it('saves once with auto_save version intent for significant content changes in large docs', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onTitleChange = vi.fn();
    const onContentChange = vi.fn();
    const largeContent = 'word '.repeat(20010);

    const { container } = render(
      <VirtualizedEditor
        fileId="file-large-autosave"
        title="Large File"
        content={largeContent}
        onTitleChange={onTitleChange}
        onContentChange={onContentChange}
        onSave={onSave}
      />
    );

    const textarea = container.querySelector('textarea');
    expect(textarea).toBeTruthy();
    fireEvent.change(textarea as HTMLTextAreaElement, {
      target: { value: `${(textarea as HTMLTextAreaElement).value}${' extra'.repeat(120)}` },
    });
    fireEvent.click(screen.getByRole('button', { name: 'editor:save' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });
    expect(onSave).toHaveBeenCalledWith({
      change_type: 'auto_save',
      change_source: 'user',
      word_count: 20129,
    });
  });

  it('keeps editor scroll stable during IME composition updates', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);

    const StatefulEditor = () => {
      const [localTitle, setLocalTitle] = useState('IME File');
      const [localContent, setLocalContent] = useState('初始内容');
      return (
        <VirtualizedEditor
          fileId="file-ime"
          title={localTitle}
          content={localContent}
          onTitleChange={setLocalTitle}
          onContentChange={setLocalContent}
          onSave={onSave}
        />
      );
    };

    const { container } = render(<StatefulEditor />);
    const textarea = container.querySelector('textarea') as HTMLTextAreaElement;
    expect(textarea).toBeTruthy();

    const scrollContainer = textarea.closest('.overflow-auto') as HTMLDivElement;
    expect(scrollContainer).toBeTruthy();
    scrollContainer.scrollTop = 200;

    const createRect = ({
      top,
      bottom,
      height,
      width = 600,
      left = 0,
    }: {
      top: number;
      bottom: number;
      height: number;
      width?: number;
      left?: number;
    }) =>
      ({
        x: left,
        y: top,
        top,
        bottom,
        left,
        right: left + width,
        width,
        height,
        toJSON: () => ({}),
      }) as DOMRect;

    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function () {
      if (this === scrollContainer) {
        return createRect({ top: 100, bottom: 300, height: 200 });
      }
      if (this.tagName === 'TEXTAREA') {
        return createRect({ top: 40, bottom: 160, height: 120 });
      }
      return createRect({ top: 0, bottom: 0, height: 0, width: 0 });
    });

    fireEvent.focus(textarea);
    fireEvent.compositionStart(textarea);
    fireEvent.change(textarea, { target: { value: '中文输入法进行中' } });

    await waitFor(() => {
      expect(scrollContainer.scrollTop).toBe(200);
    });

    fireEvent.compositionEnd(textarea);
  });

  it('keeps the active chunk height stable while typing and only shrinks after blur', () => {
    render(
      <VirtualizedEditor
        fileId="file-height"
        title="Typing File"
        content={'line\n'.repeat(40)}
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
      />
    );

    const textarea = screen.getByPlaceholderText(
      'editor:placeholder.contentPlaceholder'
    ) as HTMLTextAreaElement;

    textarea.style.height = '600px';

    const measuredHeight = 320;
    Object.defineProperty(textarea, 'scrollHeight', {
      configurable: true,
      get: () => {
        if (textarea.style.height === '0px') {
          return measuredHeight;
        }
        const currentHeight = Number.parseFloat(textarea.style.height || '0');
        return Math.max(currentHeight, measuredHeight);
      },
    });

    textarea.focus();
    fireEvent.change(textarea, {
      target: { value: 'Shorter content after deleting a lot of text.' },
    });

    expect(textarea.style.height).toBe('600px');

    fireEvent.blur(textarea);

    expect(textarea.style.height).toBe(`${measuredHeight}px`);
  });

  it('uses outer container scroll and hides textarea inner scrollbar', () => {
    render(
      <VirtualizedEditor
        fileId="file-scroll"
        title="Scroll File"
        content={'line '.repeat(500)}
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
      />
    );

    const textarea = screen.getByPlaceholderText('editor:placeholder.contentPlaceholder');
    expect(textarea.className).toContain('overflow-y-hidden');
  });

  it('keeps the active chunk height stable while typing and only shrinks after blur', () => {
    render(
      <VirtualizedEditor
        fileId="file-height"
        title="Height File"
        content={'line '.repeat(500)}
        onTitleChange={vi.fn()}
        onContentChange={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
      />
    );

    const textarea = screen.getByPlaceholderText(
      'editor:placeholder.contentPlaceholder'
    ) as HTMLTextAreaElement;

    textarea.style.height = '480px';

    const measuredHeight = 240;
    Object.defineProperty(textarea, 'scrollHeight', {
      configurable: true,
      get: () => {
        if (textarea.style.height === '0px') {
          return measuredHeight;
        }
        const currentHeight = Number.parseFloat(textarea.style.height || '0');
        return Math.max(currentHeight, measuredHeight);
      },
    });

    textarea.focus();
    fireEvent.change(textarea, {
      target: { value: 'Edited chunk content that should not collapse mid-typing.' },
    });

    expect(textarea.style.height).toBe('480px');

    fireEvent.blur(textarea);

    expect(textarea.style.height).toBe(`${measuredHeight}px`);
  });
});
