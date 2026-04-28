#!/usr/bin/env node

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const DOCS_SOURCE_DIR = process.env.DOCS_SOURCE_DIR || path.join('apps', 'web', 'docs');
const DOCS_DIR = path.join(REPO_ROOT, DOCS_SOURCE_DIR);
const SCREENSHOT_DIR = path.join(REPO_ROOT, 'apps', 'web', 'public', 'docs-images');

const BASE_URL = process.env.DOCS_SCREENSHOT_BASE_URL || 'https://zenstory.ai';
const API_BASE_URL =
  process.env.DOCS_SCREENSHOT_API_BASE_URL ||
  (BASE_URL.includes('zenstory.ai') ? 'https://api.zenstory.ai' : 'http://localhost:8000');
const VIEWPORT_WIDTH = Number(process.env.DOCS_SCREENSHOT_WIDTH || 1600);
const VIEWPORT_HEIGHT = Number(process.env.DOCS_SCREENSHOT_HEIGHT || 1000);
const LOGIN_PATH = process.env.DOCS_SCREENSHOT_LOGIN_PATH || '/login';
const LOGIN_IDENTIFIER =
  process.env.DOCS_SCREENSHOT_IDENTIFIER ||
  process.env.E2E_TEST_USERNAME ||
  'e2e_test_user';
const LOGIN_PASSWORD =
  process.env.DOCS_SCREENSHOT_PASSWORD ||
  process.env.E2E_TEST_PASSWORD ||
  'E2eTestPassword123!';
const PROJECT_NAME = process.env.DOCS_SCREENSHOT_PROJECT_NAME || 'Docs Screenshot Project';
const ONLY_SLUGS = process.env.DOCS_SCREENSHOT_SLUGS
  ? new Set(
      process.env.DOCS_SCREENSHOT_SLUGS.split(",")
        .map((slug) => slug.trim())
        .filter(Boolean),
    )
  : null;

const PLACEHOLDER_REGEX = /^(\s*)(?:\*\*)?\[截图:\s*([^\]]+)\](?:\*\*)?\s*$/gm;
const ROUTE_MAP = {
  'getting-started/installation': { route: '/login', requiresAuth: false },
  'getting-started/first-project': { route: '/dashboard', requiresAuth: true },
  'user-guide/interface-overview': { route: '/project/:projectId', requiresAuth: true, fileKey: 'lore' },
  'user-guide/project-management': { route: '/dashboard/projects', requiresAuth: true },
  'user-guide/file-tree': { route: '/project/:projectId', requiresAuth: true, fileKey: 'outline' },
  'user-guide/editor': { route: '/project/:projectId', requiresAuth: true, fileKey: 'draft' },
  'user-guide/ai-assistant': { route: '/project/:projectId', requiresAuth: true, fileKey: 'draft' },
  'user-guide/skills': { route: '/dashboard/skills', requiresAuth: true },
  'user-guide/materials': { route: '/dashboard/materials', requiresAuth: true },
  'user-guide/version-history': { route: '/project/:projectId', requiresAuth: true, fileKey: 'draft' },
  'user-guide/export': { route: '/project/:projectId', requiresAuth: true, fileKey: 'character' },
  'advanced/ai-memory': { route: '/project/:projectId', requiresAuth: true, fileKey: 'draft' },
  'advanced/skill-creation': { route: '/dashboard/skills', requiresAuth: true },
  'advanced/material-analysis': { route: '/dashboard/materials', requiresAuth: true },
  'advanced/workflow-tips': { route: '/project/:projectId', requiresAuth: true, fileKey: 'outline' },
  'reference/keyboard-shortcuts': { route: '/project/:projectId', requiresAuth: true, fileKey: 'draft' },
  'reference/file-types': { route: '/project/:projectId', requiresAuth: true, fileKey: 'character' },
  'troubleshooting/common-issues': { route: '/project/:projectId', requiresAuth: true, fileKey: 'draft' },
};
const DEFAULT_ROUTE_TARGET = { route: '/dashboard', requiresAuth: true };


async function loadChromium() {
  try {
    const { chromium } = await import('@playwright/test');
    return chromium;
  } catch {
    const playwrightModulePath = path.join(REPO_ROOT, 'apps', 'web', 'node_modules', '@playwright', 'test', 'index.mjs');
    const { chromium } = await import(pathToFileURL(playwrightModulePath).href);
    return chromium;
  }
}

async function walkMarkdownFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      return walkMarkdownFiles(fullPath);
    }
    if (entry.isFile() && entry.name.endsWith('.md')) {
      return [fullPath];
    }
    return [];
  }));

  return files.flat();
}

function toPosixPath(input) {
  return input.split(path.sep).join('/');
}

async function ensureDir(filePath) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
}

async function loginWithDefaultUser(page) {
  const loginUrl = `${BASE_URL}${LOGIN_PATH}`;
  await page.goto(loginUrl, { waitUntil: 'networkidle', timeout: 90_000 });
  await page.waitForTimeout(600);

  if (!page.url().includes('/login')) {
    return;
  }

  await page.fill('#identifier', LOGIN_IDENTIFIER);
  await page.fill('#password', LOGIN_PASSWORD);

  await page.click('[data-testid="login-submit"], button[type="submit"]');

  try {
    await page.waitForURL(/\/dashboard|\/project\//, { timeout: 30_000 });
    return;
  } catch {
    // Fallback to token-based wait when SPA routing is delayed.
  }

  await page.waitForFunction(
    () => Boolean(localStorage.getItem('access_token')),
    { timeout: 90_000 },
  );

  if (page.url().includes('/login')) {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle', timeout: 90_000 });
  }
}

async function ensureProjectId(page) {
  const projectId = await page.evaluate(async ({ apiBaseUrl, projectName }) => {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      throw new Error('Missing access token after login');
    }

    const headers = {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    };

    const listResponse = await fetch(`${apiBaseUrl}/api/v1/projects`, { headers });
    if (!listResponse.ok) {
      throw new Error(`Failed to list projects: ${listResponse.status}`);
    }
    const projects = await listResponse.json();
    if (Array.isArray(projects) && projects.length > 0 && projects[0]?.id) {
      return projects[0].id;
    }

    const createResponse = await fetch(`${apiBaseUrl}/api/v1/projects`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name: projectName, project_type: 'novel' }),
    });
    if (!createResponse.ok) {
      throw new Error(`Failed to create project: ${createResponse.status}`);
    }
    const created = await createResponse.json();
    return created.id;
  }, { apiBaseUrl: API_BASE_URL, projectName: PROJECT_NAME });

  if (!projectId || typeof projectId !== 'string') {
    throw new Error('Failed to resolve a valid project id for screenshot routes.');
  }

  return projectId;
}

async function ensureProjectSeedData(page, projectId) {
  return page.evaluate(async ({ apiBaseUrl, currentProjectId }) => {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      throw new Error('Missing access token while seeding project data');
    }

    const authHeaders = { Authorization: `Bearer ${accessToken}` };
    const jsonHeaders = {
      ...authHeaders,
      'Content-Type': 'application/json',
    };

    const treeResponse = await fetch(`${apiBaseUrl}/api/v1/projects/${currentProjectId}/file-tree`, {
      headers: authHeaders,
    });
    if (!treeResponse.ok) {
      throw new Error(`Failed to load file tree for seed: ${treeResponse.status}`);
    }
    const treeData = await treeResponse.json();
    const treeNodes = Array.isArray(treeData?.tree) ? treeData.tree : [];

    const folderByTitle = {};
    for (const node of treeNodes) {
      if (node?.file_type === 'folder' && typeof node?.title === 'string') {
        folderByTitle[node.title] = node.id;
      }
    }

    const loreFolderId = folderByTitle['设定'] || folderByTitle['World Building'] || null;
    const characterFolderId = folderByTitle['角色'] || folderByTitle['Characters'] || folderByTitle['人物'] || null;
    const materialFolderId = folderByTitle['素材'] || folderByTitle['Materials'] || null;
    const outlineFolderId = folderByTitle['大纲'] || folderByTitle['Outlines'] || folderByTitle['构思'] || null;
    const draftFolderId = folderByTitle['正文'] || folderByTitle['Drafts'] || null;

    const listResponse = await fetch(`${apiBaseUrl}/api/v1/projects/${currentProjectId}/files`, {
      headers: authHeaders,
    });
    if (!listResponse.ok) {
      throw new Error(`Failed to list files for seed: ${listResponse.status}`);
    }
    const existingFiles = await listResponse.json();
    const files = Array.isArray(existingFiles) ? [...existingFiles] : [];

    const ensureFile = async ({ title, fileType, parentId, content }) => {
      const matched = files.find((file) =>
        file?.title === title &&
        file?.file_type === fileType &&
        (file?.parent_id ?? null) === (parentId ?? null),
      );
      if (matched?.id) {
        return matched.id;
      }

      const createResponse = await fetch(`${apiBaseUrl}/api/v1/projects/${currentProjectId}/files`, {
        method: 'POST',
        headers: jsonHeaders,
        body: JSON.stringify({
          title,
          file_type: fileType,
          content,
          parent_id: parentId,
        }),
      });
      if (!createResponse.ok) {
        throw new Error(`Failed to create seed file "${title}": ${createResponse.status}`);
      }
      const created = await createResponse.json();
      files.push(created);
      return created.id;
    };

    const loreId = await ensureFile({
      title: '世界观设定',
      fileType: 'lore',
      parentId: loreFolderId,
      content: '背景：灵渊王朝，灵脉枯竭。\n核心冲突：旧秩序与新法之争。',
    });

    const characterId = await ensureFile({
      title: '主角档案',
      fileType: 'character',
      parentId: characterFolderId,
      content: '姓名：沈砚\n性格：冷静克制，行动果断。\n目标：重建失落的术法体系。',
    });

    const outlineId = await ensureFile({
      title: '第一卷大纲',
      fileType: 'outline',
      parentId: outlineFolderId,
      content: '第1章：误入禁地\n第2章：旧敌重逢\n第3章：立誓追查真相',
    });

    const draftId = await ensureFile({
      title: '第一章 归墟夜雨',
      fileType: 'draft',
      parentId: draftFolderId,
      content: '夜雨打在青石巷，沈砚推开年久失修的木门。\n院中断碑上，竟浮起早已失传的灵纹。',
    });

    const snippetId = await ensureFile({
      title: '线索摘录',
      fileType: 'snippet',
      parentId: materialFolderId,
      content: '线索：城北古井、残页密文、白衣刺客口供。',
    });

    const ensureFileVersions = async ({ fileId, baseContent }) => {
      if (!fileId || typeof fileId !== 'string') return;
      if (!baseContent || typeof baseContent !== 'string') return;

      try {
        const listResponse = await fetch(
          `${apiBaseUrl}/api/v1/files/${fileId}/versions?limit=1`,
          { headers: authHeaders },
        );
        if (listResponse.ok) {
          const data = await listResponse.json();
          const total = typeof data?.total === 'number' ? data.total : 0;
          if (total >= 2) return;
        }
      } catch {
        // ignore and attempt to seed versions anyway
      }

      const createVersion = async ({
        content,
        changeType,
        changeSource,
        changeSummary,
      }) => {
        const response = await fetch(`${apiBaseUrl}/api/v1/files/${fileId}/versions`, {
          method: 'POST',
          headers: jsonHeaders,
          body: JSON.stringify({
            content,
            change_type: changeType,
            change_source: changeSource,
            change_summary: changeSummary,
          }),
        });
        if (!response.ok) {
          throw new Error(`Failed to create file version: ${response.status}`);
        }
      };

      try {
        await createVersion({
          content: baseContent,
          changeType: 'create',
          changeSource: 'system',
          changeSummary: '初始化版本',
        });

        await createVersion({
          content: `${baseContent}\n\n补充：雨声渐急，灯影摇曳。`,
          changeType: 'edit',
          changeSource: 'user',
          changeSummary: '补充一段环境细节',
        });

        await createVersion({
          content: `${baseContent}\n\n（AI 润色）夜雨敲窗，沈砚指尖微颤。`,
          changeType: 'ai_edit',
          changeSource: 'ai',
          changeSummary: 'AI 润色片段',
        });
      } catch (error) {
        console.warn('Failed to seed file versions for docs screenshots', error);
      }
    };

    await ensureFileVersions({
      fileId: draftId,
      baseContent:
        '夜雨打在青石巷，沈砚推开年久失修的木门。\n院中断碑上，竟浮起早已失传的灵纹。',
    });

    return {
      lore: loreId,
      character: characterId,
      outline: outlineId,
      draft: draftId,
      snippet: snippetId,
    };
  }, { apiBaseUrl: API_BASE_URL, currentProjectId: projectId });
}

function getRouteTarget(slug, projectId, projectSeed) {
  const target = ROUTE_MAP[slug] || DEFAULT_ROUTE_TARGET;
  let route = target.route;

  if (route.includes(':projectId')) {
    if (!projectId) {
      throw new Error(`Route for "${slug}" requires projectId but none was provided.`);
    }
    route = route.replace(':projectId', projectId);
  }

  if (target.fileKey && route.includes('/project/')) {
    const fileId = projectSeed?.[target.fileKey];
    if (fileId) {
      route = `${route}?file=${encodeURIComponent(fileId)}`;
    }
  }

  return {
    route,
    requiresAuth: target.requiresAuth,
  };
}

async function safeClickByRoleName(page, pattern) {
  try {
    await page.getByRole('button', { name: pattern }).first().click({ timeout: 3_000 });
    return true;
  } catch {
    return false;
  }
}

async function safeClickBySelectors(page, selectors) {
  for (const selector of selectors) {
    try {
      const locator = page.locator(selector).first();
      if (await locator.isVisible({ timeout: 1_500 })) {
        await locator.click({ timeout: 2_000 });
        return true;
      }
    } catch {
      // try next selector
    }
  }
  return false;
}

async function runPostAction(page, slug) {
  if (slug === 'reference/keyboard-shortcuts') {
    try {
      const searchInput = page.locator('input[role="searchbox"], input[aria-label*="搜索文件"], input[placeholder*="搜索文件"]').first();
      if (await searchInput.isVisible({ timeout: 2_000 })) {
        await searchInput.fill('第一章');
      } else {
        await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K');
      }
    } catch {
      // no-op
    }
    return;
  }

  if (slug === 'user-guide/ai-assistant') {
    try {
      const chatInput = page
        .locator(
          'textarea[placeholder*="描述你想创作"], textarea[placeholder*="Describe what"], textarea[placeholder*="Ask"], .chat-input textarea',
        )
        .first();
      if (await chatInput.isVisible({ timeout: 2_000 })) {
        await chatInput.fill('帮我写下一段冲突升级，突出人物动机与风险。');
      }
    } catch {
      // no-op
    }
    return;
  }

  if (slug === 'user-guide/version-history') {
    const clicked = await safeClickBySelectors(page, [
      'button[title*="版本历史"]:has-text("历史")',
      'button:has-text("历史")',
      'button:has-text("History")',
    ]);

    if (!clicked) {
      await safeClickByRoleName(page, /^(历史|History)$/i);
    }

    await page.waitForTimeout(800);
    return;
  }

  if (slug === 'user-guide/export') {
    await safeClickBySelectors(page, [
      '[aria-label*="导出正文"]',
      '[aria-label*="导出"]',
      '[title*="导出"]',
      '[aria-label*="Export"]',
      '[title*="Export"]',
    ]) || await safeClickByRoleName(page, /导出|Export/i);
    return;
  }

  if (slug === 'advanced/ai-memory') {
    await safeClickBySelectors(page, [
      '[title*="AI 记忆"]',
      '[aria-label*="AI记忆"]',
      '[aria-label*="AI 记忆"]',
      '[title*="AI Memory"]',
      '[aria-label*="AI Memory"]',
    ]) || await safeClickByRoleName(page, /AI记忆|AI Memory/i);
    return;
  }

  if (slug === 'advanced/skill-creation') {
    try {
      await page.getByRole('button', { name: '我的技能', exact: true }).click({ timeout: 3_000 });
    } catch {
      await safeClickByRoleName(page, /我的技能|My Skills/i);
    }

    await safeClickByRoleName(page, /创建技能|创建第一个技能|Create Skill|Create your first/i);
  }
}

async function main() {
  const mdFiles = await walkMarkdownFiles(DOCS_DIR);

  const targets = [];
  for (const file of mdFiles) {
    const relativeDocPath = toPosixPath(path.relative(DOCS_DIR, file));
    const slug = relativeDocPath.replace(/\.md$/i, '');
    if (ONLY_SLUGS && !ONLY_SLUGS.has(slug)) {
      continue;
    }
    const screenshotMarkdownPath = `/docs-images/${slug}.png`;
    const content = await fs.readFile(file, 'utf8');
    const hasPlaceholder = PLACEHOLDER_REGEX.test(content);
    PLACEHOLDER_REGEX.lastIndex = 0;

    const hasExistingScreenshotRef = content.includes(`(${screenshotMarkdownPath})`);
    if (hasPlaceholder || hasExistingScreenshotRef) {
      targets.push({ file, content, relativeDocPath, slug });
    }
  }

  if (targets.length === 0) {
    console.log('No screenshot placeholders or existing docs-image references found.');
    return;
  }

  console.log(`Found ${targets.length} markdown files requiring screenshot generation in ${DOCS_SOURCE_DIR}.`);

  const chromium = await loadChromium();
  const browser = await chromium.launch({ headless: true });
  const publicContext = await browser.newContext({
    viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
    locale: 'zh-CN',
    deviceScaleFactor: 1,
  });
  const publicPage = await publicContext.newPage();

  const needsAuth = targets.some((target) => {
    const routeTarget = ROUTE_MAP[target.slug] || DEFAULT_ROUTE_TARGET;
    return routeTarget.requiresAuth || routeTarget.route.includes(':projectId');
  });

  let authContext = null;
  let authPage = null;
  let projectId = null;
  let projectSeed = null;

  if (needsAuth) {
    authContext = await browser.newContext({
      viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
      locale: 'zh-CN',
      deviceScaleFactor: 1,
    });
    authPage = await authContext.newPage();
    await loginWithDefaultUser(authPage);
    projectId = await ensureProjectId(authPage);
    projectSeed = await ensureProjectSeedData(authPage, projectId);
  }

  let totalReplacements = 0;

  try {
    for (const target of targets) {
      const { relativeDocPath, slug } = target;
      const routeTarget = getRouteTarget(slug, projectId, projectSeed);
      const page = routeTarget.requiresAuth ? authPage : publicPage;
      if (!page) {
        throw new Error(`No available browser page for route "${routeTarget.route}" (auth=${routeTarget.requiresAuth}).`);
      }

      const route = routeTarget.route;
      const url = `${BASE_URL}${route}`;
      const screenshotRelativePath = `${slug}.png`;
      const screenshotAbsolutePath = path.join(SCREENSHOT_DIR, screenshotRelativePath);

      await ensureDir(screenshotAbsolutePath);
      await page.goto(url, { waitUntil: 'networkidle', timeout: 90_000 });
      await runPostAction(page, slug);
      await page.waitForTimeout(1_000);

      await page.screenshot({
        path: screenshotAbsolutePath,
        fullPage: false,
      });

      let replacements = 0;
      const updatedContent = target.content.replace(
        PLACEHOLDER_REGEX,
        (_, indentation, rawAlt) => {
          replacements += 1;
          const altText = String(rawAlt).trim();
          return `${indentation}![${altText}](/docs-images/${screenshotRelativePath})\n`;
        },
      );

      if (replacements > 0) {
        totalReplacements += replacements;
        await fs.writeFile(target.file, updatedContent, 'utf8');
      }

      console.log(
        `${relativeDocPath}: captured ${toPosixPath(path.relative(REPO_ROOT, screenshotAbsolutePath))} from ${route}, replaced ${replacements} placeholder(s).`,
      );
    }
  } finally {
    if (authContext) {
      await authContext.close();
    }
    await publicContext.close();
    await browser.close();
  }

  console.log(`Done. Replaced ${totalReplacements} placeholder(s) across ${targets.length} files.`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
