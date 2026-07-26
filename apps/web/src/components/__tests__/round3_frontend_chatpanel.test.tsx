/**
 * Round-3 回归（ChatPanel 侧）：
 *
 * #24 的另一半 —— ChatPanel.handleSteer 必须把失败**抛回**给 MessageInput。
 * 它此前把异常吞在内部只弹一句 toast，于是调用方以为「已送达」，
 * 同步清空输入框并把持久化草稿覆写成空串，用户输入彻底无法找回。
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const mockAgentStreamState = vi.hoisted(() => ({
  isStreaming: false,
  sessionId: null as string | null,
}))

const sendSteeringMessageMock = vi.hoisted(() => vi.fn())

const capturedMessageInputProps = vi.hoisted(() => ({
  props: null as Record<string, unknown> | null,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('../../contexts/ProjectContext', () => ({
  useProject: () => ({
    currentProjectId: 'project-1',
    selectedItem: null,
    triggerFileTreeRefresh: vi.fn(),
    triggerEditorRefresh: vi.fn(),
    setSelectedItem: vi.fn(),
    appendFileContent: vi.fn(),
    finishFileStreaming: vi.fn(),
    startFileStreaming: vi.fn(),
    streamingFileId: null,
    enterDiffReview: vi.fn(),
  }),
}))

vi.mock('../../contexts/MobileLayoutContext', () => ({
  useMobileLayout: () => ({ isMobile: false }),
}))

vi.mock('../../contexts/MaterialAttachmentContext', () => ({
  useMaterialAttachment: () => ({
    attachedFileIds: [],
    attachedLibraryMaterials: [],
    clearMaterials: vi.fn(),
  }),
}))

vi.mock('../../contexts/TextQuoteContext', () => ({
  useTextQuote: () => ({ quotes: [], clearQuotes: vi.fn() }),
}))

const streamCallbacks = {
  onStart: vi.fn(),
  onContext: vi.fn(),
  onThinking: vi.fn(),
  onThinkingContent: vi.fn(),
  onSegmentStart: vi.fn(),
  onSegmentUpdate: vi.fn(),
  onSegmentUpdateToolCalls: vi.fn(),
  onSegmentEnd: vi.fn(),
  onComplete: vi.fn(async () => {}),
  onError: vi.fn(),
  onToolResult: vi.fn(),
  onFileCreated: vi.fn(),
  onFileContent: vi.fn(),
  onFileContentEnd: vi.fn(),
  onFileEditStart: vi.fn(),
  onFileEditApplied: vi.fn(),
  onFileEditEnd: vi.fn(),
  onSkillMatched: vi.fn(),
  onSkillsMatched: vi.fn(),
  onAgentSelected: vi.fn(),
  onIterationExhausted: vi.fn(),
  onRouterThinking: vi.fn(),
  onRouterDecided: vi.fn(),
  onHandoff: vi.fn(),
  onWorkflowStopped: vi.fn(),
  onWorkflowComplete: vi.fn(),
  onSessionStarted: vi.fn(),
  onParallelStart: vi.fn(),
  onParallelTaskStart: vi.fn(),
  onParallelTaskEnd: vi.fn(),
  onParallelEnd: vi.fn(),
  onSteeringReceived: vi.fn(),
}

vi.mock('../../hooks/useChatStreaming', () => ({
  useChatStreaming: () => ({
    streamRenderItems: [],
    clearStreamItems: vi.fn(),
    editProgress: null,
    setEditProgress: vi.fn(),
    aiSuggestions: [],
    setAiSuggestions: vi.fn(),
    isRefreshingSuggestions: false,
    setIsRefreshingSuggestions: vi.fn(),
    matchedSkills: [],
    setMatchedSkills: vi.fn(),
    getStreamCallbacks: vi.fn(() => streamCallbacks),
    clearIdleTimer: vi.fn(),
  }),
}))

vi.mock('../../hooks/useAgentStream', () => ({
  useAgentStream: () => ({
    state: {},
    startStream: vi.fn(),
    cancel: vi.fn(),
    reset: vi.fn(),
    isStreaming: mockAgentStreamState.isStreaming,
    isThinking: false,
    thinkingContent: '',
    conflicts: [],
    error: null,
    errorCode: null,
    sessionId: mockAgentStreamState.sessionId,
    sendSteeringMessage: sendSteeringMessageMock,
  }),
}))

vi.mock('../../hooks/useDraftPersistence', () => ({
  useDraftPersistence: () => ({
    draft: '',
    saveDraft: vi.fn(),
    clearDraft: vi.fn(),
  }),
}))

vi.mock('../../lib/chatApi', () => ({
  getRecentMessages: vi.fn(async () => []),
  createNewSession: vi.fn(async () => ({ id: 'session-1' })),
  submitMessageFeedback: vi.fn(),
}))

vi.mock('../../lib/agentApi', () => ({
  fetchSuggestions: vi.fn(async () => []),
}))

vi.mock('../../lib/api', () => ({
  fileVersionApi: {},
  versionApi: {},
}))

vi.mock('../MessageList', () => ({
  MessageList: React.forwardRef(() => <div data-testid="mock-message-list" />),
}))

vi.mock('../MessageInput', () => ({
  MessageInput: (props: Record<string, unknown>) => {
    capturedMessageInputProps.props = props
    return <div data-testid="mock-message-input" />
  },
}))

vi.mock('../ToolResultCard', () => ({
  ToolResultCard: () => <div data-testid="mock-tool-result-card" />,
}))

vi.mock('../ProjectStatusDialog', () => ({
  ProjectStatusDialog: () => null,
}))

vi.mock('../subscription/QuotaBadge', () => ({
  QuotaBadge: () => <div data-testid="mock-quota-badge" />,
}))

vi.mock('../../lib/toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { ChatPanel } from '../ChatPanel'
import { toast } from '../../lib/toast'

async function renderAndGetSteer(): Promise<(message: string) => Promise<void>> {
  render(<ChatPanel />)
  await waitFor(() => {
    expect(screen.getByTestId('mock-message-input')).toBeInTheDocument()
  })
  const onSteer = capturedMessageInputProps.props?.onSteer as
    | ((message: string) => Promise<void>)
    | undefined
  expect(typeof onSteer).toBe('function')
  return onSteer!
}

describe('round3 #24 ChatPanel.handleSteer 必须把失败抛回调用方', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    capturedMessageInputProps.props = null
    mockAgentStreamState.isStreaming = true
    mockAgentStreamState.sessionId = 'session-1'
    sendSteeringMessageMock.mockReset()
  })

  it('后端返回 404 时既弹 toast 也向上抛出', async () => {
    sendSteeringMessageMock.mockRejectedValue(new Error('Request failed: 404'))
    const onSteer = await renderAndGetSteer()

    await expect(onSteer('把主角改名为林川')).rejects.toThrow('Request failed: 404')
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('chat:input.steerFailed')
    expect(vi.mocked(toast.success)).not.toHaveBeenCalled()
  })

  it('流已结束时也必须抛出，而不是静默 return（否则输入框照样被清空）', async () => {
    mockAgentStreamState.isStreaming = false
    const onSteer = await renderAndGetSteer()

    await expect(onSteer('补一句')).rejects.toThrow()
    expect(sendSteeringMessageMock).not.toHaveBeenCalled()
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('chat:input.steerFailed')
  })

  it('成功时正常 resolve 并提示已送达', async () => {
    sendSteeringMessageMock.mockResolvedValue(undefined)
    const onSteer = await renderAndGetSteer()

    await expect(onSteer('换个视角写')).resolves.toBeUndefined()
    expect(sendSteeringMessageMock).toHaveBeenCalledWith('换个视角写')
    expect(vi.mocked(toast.success)).toHaveBeenCalledWith('chat:input.steerSent')
  })

  it('canSteer 只在本轮流拿到 session 之后才为真', async () => {
    mockAgentStreamState.sessionId = null
    await renderAndGetSteer()
    expect(capturedMessageInputProps.props?.canSteer).toBe(false)
  })
})
