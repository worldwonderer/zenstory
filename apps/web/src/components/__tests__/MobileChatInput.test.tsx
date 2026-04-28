import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MobileChatInput } from '../MobileChatInput'

const startRecording = vi.fn()
const stopRecording = vi.fn()
const cancelRecording = vi.fn()
const removeMaterial = vi.fn()
const removeQuote = vi.fn()

let currentVoiceState: {
  status: 'idle' | 'recording' | 'processing' | 'error'
  isRecording: boolean
  isProcessing: boolean
  duration: number
  volume: number
  error: string | null
  startRecording: typeof startRecording
  stopRecording: typeof stopRecording
  cancelRecording: typeof cancelRecording
  isSupported: boolean
} = {
  status: 'idle',
  isRecording: false,
  isProcessing: false,
  duration: 0,
  volume: 0.3,
  error: null,
  startRecording,
  stopRecording,
  cancelRecording,
  isSupported: true,
}

let lastVoiceOptions:
  | {
      onResult: (text: string) => void
      onError: (error: string) => void
      maxDuration: number
    }
  | undefined

const { mockUseMaterialAttachment, mockUseTextQuote } = vi.hoisted(() => ({
  mockUseMaterialAttachment: vi.fn(),
  mockUseTextQuote: vi.fn(),
}))

vi.mock('../../hooks/useVoiceInput', () => ({
  useVoiceInput: (options: typeof lastVoiceOptions) => {
    lastVoiceOptions = options
    return currentVoiceState
  },
}))

vi.mock('../../contexts/MaterialAttachmentContext', () => ({
  useMaterialAttachment: mockUseMaterialAttachment,
}))

vi.mock('../../contexts/TextQuoteContext', () => ({
  useTextQuote: mockUseTextQuote,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          'chat:input.placeholder': 'Type a message',
          'chat:input.attachedMaterials': 'Attached materials',
          'chat:input.quotedText': 'Quoted text',
          'chat:input.remove': 'Remove',
          'common:cancel': 'Cancel',
          'common:send': 'Send',
          'chat:voice.mobile_hold': 'Hold to talk',
          'chat:voice.mobile_stop': 'Release to stop',
          'chat:voice.unavailable': 'Voice unavailable',
          'chat:voice.recognizing': 'Recognizing',
        } as Record<string, string>
      )[key] ?? key,
  }),
}))

describe('MobileChatInput', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    lastVoiceOptions = undefined
    currentVoiceState = {
      status: 'idle',
      isRecording: false,
      isProcessing: false,
      duration: 0,
      volume: 0.3,
      error: null,
      startRecording,
      stopRecording,
      cancelRecording,
      isSupported: true,
    }
    mockUseMaterialAttachment.mockReturnValue({
      attachedMaterials: [],
      removeMaterial,
    })
    mockUseTextQuote.mockReturnValue({
      quotes: [],
      removeQuote,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('submits trimmed text and clears the draft', () => {
    const onSend = vi.fn()
    render(<MobileChatInput onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('Type a message')
    fireEvent.change(textarea, { target: { value: '  hello mobile  ' } })
    fireEvent.click(screen.getByTestId('mobile-send-button'))

    expect(onSend).toHaveBeenCalledWith('hello mobile')
    expect(textarea).toHaveValue('')
  })

  it('appends recognized voice text into the textarea', () => {
    render(<MobileChatInput onSend={vi.fn()} />)

    act(() => {
      lastVoiceOptions?.onResult('voice result')
      vi.runOnlyPendingTimers()
    })

    expect(screen.getByTestId('mobile-chat-input')).toHaveValue('voice result')
  })

  it('starts and stops recording on long press', async () => {
    currentVoiceState = {
      ...currentVoiceState,
      status: 'recording',
      isRecording: true,
    }

    render(<MobileChatInput onSend={vi.fn()} />)

    const voiceButton = screen.getByTestId('mobile-voice-input-button')
    fireEvent.touchStart(voiceButton)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })

    fireEvent.touchEnd(voiceButton)

    expect(startRecording).toHaveBeenCalledTimes(1)
    expect(stopRecording).toHaveBeenCalledTimes(1)
  })

  it('cancels recording on touch cancel and supports cancel action when disabled', async () => {
    currentVoiceState = {
      ...currentVoiceState,
      status: 'recording',
      isRecording: true,
    }
    const onCancel = vi.fn()

    const { rerender } = render(<MobileChatInput onSend={vi.fn()} />)
    const voiceButton = screen.getByTestId('mobile-voice-input-button')

    fireEvent.touchStart(voiceButton)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })
    fireEvent.touchCancel(voiceButton)

    expect(cancelRecording).toHaveBeenCalledTimes(1)

    rerender(<MobileChatInput onSend={vi.fn()} disabled={true} onCancel={onCancel} />)
    fireEvent.click(screen.getByTitle('Cancel'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('renders attachments and quotes and removes them', () => {
    mockUseMaterialAttachment.mockReturnValue({
      attachedMaterials: [{ id: 'material-1', title: 'Scene notes' }],
      removeMaterial,
    })
    mockUseTextQuote.mockReturnValue({
      quotes: [{ id: 'quote-1', text: 'A dramatic quote that should be truncated in mobile view.' }],
      removeQuote,
    })

    render(<MobileChatInput onSend={vi.fn()} />)

    expect(screen.getByText('Attached materials')).toBeInTheDocument()
    expect(screen.getByText('Scene notes')).toBeInTheDocument()
    expect(screen.getByText('Quoted text')).toBeInTheDocument()

    const removeButtons = screen.getAllByTitle('Remove')
    fireEvent.click(removeButtons[0]!)
    fireEvent.click(removeButtons[1]!)

    expect(removeMaterial).toHaveBeenCalledWith('material-1')
    expect(removeQuote).toHaveBeenCalledWith('quote-1')
  })
})
