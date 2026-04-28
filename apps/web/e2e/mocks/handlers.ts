import { http, HttpResponse } from 'msw'
import chatDefaultResponse from './responses/chat-default.json' with { type: 'json' }

/**
 * MSW handler for POST /api/v1/agent/stream
 * Returns SSE stream with pre-recorded AI response events
 */
export const agentStreamHandler = http.post('/api/v1/agent/stream', () => {
  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder()

      // Send each event from the pre-recorded response
      chatDefaultResponse.forEach((event) => {
        const eventType = typeof event.type === 'string' ? event.type : 'content'
        const payload = event.data ?? {}
        const eventData = `event: ${eventType}\ndata: ${JSON.stringify(payload)}\n\n`
        controller.enqueue(encoder.encode(eventData))
      })

      controller.close()
    },
  })

  return new HttpResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  })
})

/**
 * MSW handler for POST /api/v1/agent/suggest
 * Returns static suggestions array
 */
export const agentSuggestHandler = http.post('/api/v1/agent/suggest', () => {
  return HttpResponse.json({
    suggestions: ['创建角色', '写一段对话', '添加场景'],
  })
})

/**
 * All MSW handlers for AI endpoints
 */
export const handlers = [agentStreamHandler, agentSuggestHandler]
