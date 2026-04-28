import { APIRequestContext } from '@playwright/test';

/**
 * Creates a project via API call
 * @param request - Playwright APIRequestContext
 * @param name - Project name
 * @param description - Optional project description
 * @returns Created project data
 * @throws Error if project creation fails
 */
export async function createProjectViaAPI(
  request: APIRequestContext,
  name: string,
  description?: string
) {
  const response = await request.post('/api/v1/projects', {
    data: { name, description: description || 'Test project' },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create project: ${response.status()}`);
  }

  return await response.json();
}

/**
 * Creates a file via API call
 * @param request - Playwright APIRequestContext
 * @param projectId - Parent project ID
 * @param file - File data including name, file_type, and optional content
 * @returns Created file data
 * @throws Error if file creation fails
 */
export async function createFileViaAPI(
  request: APIRequestContext,
  projectId: string,
  file: { name: string; file_type: string; content?: string }
) {
  const response = await request.post(`/api/v1/projects/${projectId}/files`, {
    data: file,
  });

  if (!response.ok()) {
    throw new Error(`Failed to create file: ${response.status()}`);
  }

  return await response.json();
}

/**
 * Cleans up test data by deleting a project
 * @param request - Playwright APIRequestContext
 * @param projectId - Project ID to delete
 */
export async function cleanupTestData(
  request: APIRequestContext,
  projectId: string
) {
  await request.delete(`/api/v1/projects/${projectId}`);
}
