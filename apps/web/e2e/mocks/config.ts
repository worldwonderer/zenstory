/**
 * Centralized mock configuration for consistent testing
 */
export const mockConfig = {
  // Response delays for realistic testing (in milliseconds)
  delays: {
    fast: 100,
    normal: 500,
    slow: 2000,
    ai: 5000,
  },

  // Error scenarios
  errors: {
    network: { message: 'Network error', status: 0 },
    unauthorized: { message: 'Unauthorized', status: 401 },
    forbidden: { message: 'Forbidden', status: 403 },
    notFound: { message: 'Not found', status: 404 },
    serverError: { message: 'Internal server error', status: 500 },
    rateLimit: { message: 'Rate limited', status: 429 },
  },

  // AI response templates
  aiResponses: {
    short: '这是一个简短的AI响应示例。',
    long: '这是一个较长的AI响应示例，包含多个段落。\n\n第一段介绍主题。\n\n第二段展开讨论。\n\n第三段总结观点。',
    toolCall: { tool: 'create_file', status: 'success', message: '文件创建成功' },
    error: '处理请求时发生错误，请稍后重试。',
  },
};

/**
 * Get mock delay by type
 */
export function getMockDelay(type: keyof typeof mockConfig.delays = 'normal'): number {
  return mockConfig.delays[type];
}

/**
 * Get mock error by type
 */
export function getMockError(type: keyof typeof mockConfig.errors): (typeof mockConfig.errors)[keyof typeof mockConfig.errors] {
  return mockConfig.errors[type];
}
