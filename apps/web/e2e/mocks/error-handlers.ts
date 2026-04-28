import { http, HttpResponse, delay } from 'msw';
import { getMockError, getMockDelay } from './config';

/**
 * Error scenario handlers for testing error states
 */
export const errorHandlers = [
  // Network error (connection failure)
  http.get('/api/v1/test/network-error', () => {
    return HttpResponse.error();
  }),

  // 401 Unauthorized
  http.get('/api/v1/test/unauthorized', async () => {
    await delay(getMockDelay('fast'));
    const error = getMockError('unauthorized');
    return new HttpResponse(JSON.stringify({ message: error.message }), {
      status: error.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }),

  // 403 Forbidden
  http.get('/api/v1/test/forbidden', async () => {
    await delay(getMockDelay('fast'));
    const error = getMockError('forbidden');
    return new HttpResponse(JSON.stringify({ message: error.message }), {
      status: error.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }),

  // 404 Not Found
  http.get('/api/v1/test/not-found', async () => {
    await delay(getMockDelay('fast'));
    const error = getMockError('notFound');
    return new HttpResponse(JSON.stringify({ message: error.message }), {
      status: error.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }),

  // 500 Server Error
  http.get('/api/v1/test/server-error', async () => {
    await delay(getMockDelay('normal'));
    const error = getMockError('serverError');
    return new HttpResponse(JSON.stringify({ message: error.message }), {
      status: error.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }),

  // 429 Rate Limit
  http.get('/api/v1/test/rate-limit', async () => {
    await delay(getMockDelay('fast'));
    const error = getMockError('rateLimit');
    return new HttpResponse(JSON.stringify({ message: error.message }), {
      status: error.status,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': '60',
      },
    });
  }),

  // Slow response (timeout scenario)
  http.get('/api/v1/test/timeout', async () => {
    await delay(getMockDelay('slow'));
    return HttpResponse.json({ message: 'Slow response' });
  }),
];
