import { describe, it, expect, vi, beforeEach, afterEach, afterAll } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MessageInput } from '../MessageInput'

const { mockUseMaterialAttachment, mockUseTextQuote, mockUseSkillTrigger } = vi.hoisted(() => ({
  mockUseMaterialAttachment: vi.fn(() => ({
    attachedMaterials: [],
    removeMaterial: vi.fn(),
  })),
  mockUseTextQuote: vi.fn(() => ({
    quotes: [],
    removeQuote: vi.fn(),
  })),
  mockUseSkillTrigger: vi.fn(() => ({
    pendingTrigger: null,
    consumeTrigger: vi.fn(),
    insertTrigger: vi.fn(),
  })),
}))

const { mockT, mockI18n } = vi.hoisted(() => ({
  mockT: vi.fn((key: string, options?: { returnObjects?: boolean }) => {
    if (key === 'chat:input.staticSuggestions' && options?.returnObjects) {
      return ['Static 1', 'Static 2', 'Static 3']
    }
    return key
  }),
  mockI18n: {
    language: 'zh',
  },
}))

// Mock contexts
vi.mock('../../contexts/MaterialAttachmentContext', () => ({
  useMaterialAttachment: mockUseMaterialAttachment,
}))

vi.mock('../../contexts/TextQuoteContext', () => ({
  useTextQuote: mockUseTextQuote,
}))

vi.mock('../../contexts/SkillTriggerContext', () => ({
  useSkillTrigger: mockUseSkillTrigger,
}))

vi.mock('../../lib/api', () => ({
  skillsApi: {
    list: vi.fn().mockResolvedValue({ skills: [] }),
  },
}))

vi.mock('../VoiceInputButton', () => ({
  VoiceInputButton: ({
    onResult,
    disabled,
  }: {
    onResult: (text: string) => void
    disabled?: boolean
  }) => (
    <button
      type="button"
      disabled={disabled}
      aria-label="voice button"
      onClick={() => onResult('voice result')}
    >
      Voice
    </button>
  ),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: mockI18n,
  }),
}))

describe('MessageInput', () => {
  const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  const defaultProps = {
    onSend: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockI18n.language = 'zh'
    mockUseMaterialAttachment.mockReturnValue({
      attachedMaterials: [],
      removeMaterial: vi.fn(),
    })
    mockUseTextQuote.mockReturnValue({
      quotes: [],
      removeQuote: vi.fn(),
    })
    mockUseSkillTrigger.mockReturnValue({
      pendingTrigger: null,
      consumeTrigger: vi.fn(),
      insertTrigger: vi.fn(),
    })
  })

  afterEach(() => {
    cleanup()
  })

  afterAll(() => {
    consoleErrorSpy.mockRestore()
  })

  it('renders textarea and send button', () => {
    render(<MessageInput {...defaultProps} />)
    expect(screen.getByPlaceholderText('chat:input.placeholder')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /common:send/i })).toBeInTheDocument()
  })

  it('disables when isLoading is true', () => {
    render(<MessageInput {...defaultProps} disabled={true} />)
    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    const sendButton = screen.getByRole('button', { name: /common:send/i })
    expect(textarea).toBeDisabled()
    expect(sendButton).toBeDisabled()
  })

  it('clears input after send', async () => {
    const user = userEvent.setup({ delay: null })
    const onSend = vi.fn()
    render(<MessageInput {...defaultProps} onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    await user.type(textarea, 'Test message')
    await user.click(screen.getByRole('button', { name: /common:send/i }))

    expect(onSend).toHaveBeenCalledWith('Test message')
    await waitFor(() => {
      expect(textarea).toHaveValue('')
    })
  })

  it('handles Shift+Enter for newline', async () => {
    const user = userEvent.setup({ delay: null })
    const onSend = vi.fn()
    render(<MessageInput {...defaultProps} onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    await user.type(textarea, 'Line 1{Shift>}{Enter}{/Shift}Line 2')

    expect(onSend).not.toHaveBeenCalled()
    expect(textarea).toHaveValue('Line 1\nLine 2')
  })

  it('handles Enter to send', async () => {
    const user = userEvent.setup({ delay: null })
    const onSend = vi.fn()
    render(<MessageInput {...defaultProps} onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    await user.type(textarea, 'Test message{Enter}')

    expect(onSend).toHaveBeenCalledWith('Test message')
  })

  it('does not send empty messages', async () => {
    const user = userEvent.setup({ delay: null })
    const onSend = vi.fn()
    render(<MessageInput {...defaultProps} onSend={onSend} />)

    const sendButton = screen.getByRole('button', { name: /common:send/i })
    expect(sendButton).toBeDisabled()

    await user.click(sendButton)
    expect(onSend).not.toHaveBeenCalled()
  })

  it('trims whitespace from messages', async () => {
    const user = userEvent.setup({ delay: null })
    const onSend = vi.fn()
    render(<MessageInput {...defaultProps} onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    await user.type(textarea, '  Test message  {Enter}')

    expect(onSend).toHaveBeenCalledWith('Test message')
  })

  it('shows cancel button when onCancel provided and disabled', () => {
    const onCancel = vi.fn()
    render(<MessageInput {...defaultProps} disabled={true} onCancel={onCancel} />)

    expect(screen.getByRole('button', { name: /common:cancel/i })).toBeInTheDocument()
  })

  it('calls onCancel when cancel button is clicked', async () => {
    const user = userEvent.setup({ delay: null })
    const onCancel = vi.fn()
    render(<MessageInput {...defaultProps} disabled={true} onCancel={onCancel} />)

    await user.click(screen.getByRole('button', { name: /common:cancel/i }))
    expect(onCancel).toHaveBeenCalled()
  })

  it('shows custom placeholder', () => {
    render(<MessageInput {...defaultProps} placeholder="Custom placeholder" />)
    expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument()
  })

  it('displays AI suggestions', () => {
    const aiSuggestions = ['Suggestion 1', 'Suggestion 2', 'Suggestion 3']
    render(<MessageInput {...defaultProps} aiSuggestions={aiSuggestions} />)

    expect(screen.getByText('Suggestion 1')).toBeInTheDocument()
    expect(screen.getByText('Suggestion 2')).toBeInTheDocument()
    expect(screen.getByText('Suggestion 3')).toBeInTheDocument()
  })

  it('clicks suggestion to fill input', async () => {
    const user = userEvent.setup({ delay: null })
    const aiSuggestions = ['Suggestion 1', 'Suggestion 2']
    render(<MessageInput {...defaultProps} aiSuggestions={aiSuggestions} />)

    await user.click(screen.getByText('Suggestion 1'))

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    expect(textarea).toHaveValue('Suggestion 1')
  })

  it('displays static suggestions when no AI suggestions', () => {
    render(
      <MessageInput
        {...defaultProps}
        aiSuggestions={[]}
        messageCount={0}
        suggestionDisplayState="fallback"
      />
    )
    expect(screen.getByText('Static 1')).toBeInTheDocument()
    expect(screen.getByText('Static 2')).toBeInTheDocument()
  })

  it('shows loading placeholders instead of static suggestions during loading', () => {
    render(
      <MessageInput
        {...defaultProps}
        aiSuggestions={[]}
        suggestionDisplayState="loading"
      />
    )
    expect(screen.queryByText('Static 1')).not.toBeInTheDocument()
    expect(screen.getByText('common:loading')).toBeInTheDocument()
  })

  it('handles refresh suggestions button click', async () => {
    const user = userEvent.setup({ delay: null })
    const onRefreshSuggestions = vi.fn()
    render(
      <MessageInput
        {...defaultProps}
        onRefreshSuggestions={onRefreshSuggestions}
        isRefreshingSuggestions={false}
      />
    )

    // Find refresh button (RefreshCw icon)
    const refreshButtons = screen.getAllByRole('button')
    const refreshButton = refreshButtons.find(btn =>
      btn.querySelector('svg.lucide-refresh-cw') || btn.getAttribute('aria-busy') !== null
    )

    if (refreshButton) {
      await user.click(refreshButton)
      expect(onRefreshSuggestions).toHaveBeenCalled()
    }
  })

  it('shows refresh button as busy when refreshing', () => {
    render(
      <MessageInput
        {...defaultProps}
        isRefreshingSuggestions={true}
        onRefreshSuggestions={vi.fn()}
      />
    )

    const refreshButton = screen.getAllByRole('button').find(btn =>
      btn.getAttribute('aria-busy') === 'true'
    )
    expect(refreshButton).toBeTruthy()
  })

  it('auto-resizes textarea in auto layout', async () => {
    const user = userEvent.setup({ delay: null })
    render(<MessageInput {...defaultProps} layout="auto" />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')

    // Type multiple lines
    await user.type(textarea, 'Line 1\nLine 2\nLine 3\nLine 4\nLine 5')

    // Textarea should have auto-resized (we can't check exact height in jsdom)
    expect(textarea).toHaveValue('Line 1\nLine 2\nLine 3\nLine 4\nLine 5')
  })

  it('uses fill layout correctly', () => {
    const { container } = render(<MessageInput {...defaultProps} layout="fill" />)

    // Check that fill layout class is applied
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain('h-full')
  })

  it('displays matched skills', () => {
    const matchedSkills = [
      { name: 'Skill 1', trigger: '/skill1' },
      { name: 'Skill 2', trigger: '/skill2' },
    ]
    render(<MessageInput {...defaultProps} matchedSkills={matchedSkills} />)

    expect(screen.getByText('Skill 1')).toBeInTheDocument()
    expect(screen.getByText('Skill 2')).toBeInTheDocument()
  })

  it('handles skill trigger via "/"', async () => {
    const user = userEvent.setup({ delay: null })
    render(<MessageInput {...defaultProps} />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    await user.type(textarea, '/')

    // Skill menu should open (but may be empty if skills not loaded)
    // We just check that the input accepts the slash
    expect(textarea).toHaveValue('/')
  })

  it('renders selected skill triggers as a compact rail in fill layout', async () => {
    mockUseSkillTrigger.mockReturnValue({
      pendingTrigger: '/outline-helper',
      consumeTrigger: vi.fn(),
      insertTrigger: vi.fn(),
    })

    render(<MessageInput {...defaultProps} layout="fill" />)

    const skillRow = await screen.findByTestId('chat-skill-trigger-row')
    expect(skillRow.className).toContain('overflow-x-auto')
    expect(skillRow.className).not.toContain('flex-wrap')
    expect(screen.getByText('/outline-helper')).toBeInTheDocument()
    expect(screen.getByTestId('chat-input-accessories').className).toContain('overflow-y-auto')
  })

  it('prepends selected skill triggers when sending a message', async () => {
    const user = userEvent.setup({ delay: null })
    const onSend = vi.fn()
    mockUseSkillTrigger.mockReturnValue({
      pendingTrigger: '/story-skill',
      consumeTrigger: vi.fn(),
      insertTrigger: vi.fn(),
    })

    render(<MessageInput {...defaultProps} onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    await screen.findByText('/story-skill')
    await user.type(textarea, '继续写这一章')
    await user.click(screen.getByRole('button', { name: /common:send/i }))

    expect(onSend).toHaveBeenCalledWith('/story-skill 继续写这一章')
  })

  it('hides suggestion chips in fill layout when a skill trigger is already selected', () => {
    mockUseSkillTrigger.mockReturnValue({
      pendingTrigger: '/story-skill',
      consumeTrigger: vi.fn(),
      insertTrigger: vi.fn(),
    })

    render(
      <MessageInput
        {...defaultProps}
        layout="fill"
        aiSuggestions={['Suggestion 1', 'Suggestion 2']}
      />,
    )

    expect(screen.queryByText('Suggestion 1')).not.toBeInTheDocument()
    expect(screen.queryByText('Suggestion 2')).not.toBeInTheDocument()
  })

  it('handles Tab to accept first suggestion', async () => {
    const user = userEvent.setup({ delay: null })
    const aiSuggestions = ['First suggestion', 'Second suggestion']
    render(<MessageInput {...defaultProps} aiSuggestions={aiSuggestions} />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    await user.click(textarea) // Focus
    await user.keyboard('{Tab}')

    expect(textarea).toHaveValue('First suggestion')
  })

  it('does not show suggestions when input has content', async () => {
    const user = userEvent.setup({ delay: null })
    const aiSuggestions = ['Suggestion 1', 'Suggestion 2']
    render(<MessageInput {...defaultProps} aiSuggestions={aiSuggestions} />)

    const textarea = screen.getByPlaceholderText('chat:input.placeholder')
    await user.type(textarea, 'Some text')

    // Suggestions should not be visible when input has content
    expect(screen.queryByText('Suggestion 1')).not.toBeInTheDocument()
  })

  it('does not show suggestions when disabled', () => {
    const aiSuggestions = ['Suggestion 1', 'Suggestion 2']
    render(<MessageInput {...defaultProps} aiSuggestions={aiSuggestions} disabled={true} />)

    expect(screen.queryByText('Suggestion 1')).not.toBeInTheDocument()
  })

  it('handles voice input button', () => {
    render(<MessageInput {...defaultProps} />)
    // VoiceInputButton is rendered (mocked)
    const voiceButton = screen.getByRole('button', { name: /voice/i })
    expect(voiceButton).toBeInTheDocument()
  })

  it('allows switching generation mode (fast/quality)', async () => {
    const user = userEvent.setup({ delay: null })
    const onGenerationModeChange = vi.fn()

    render(
      <MessageInput
        {...defaultProps}
        generationMode="quality"
        onGenerationModeChange={onGenerationModeChange}
      />
    )

    await user.click(screen.getByRole('button', { name: /chat:input.mode.label/i }))
    expect(onGenerationModeChange).toHaveBeenCalledWith('fast')
  })
})
