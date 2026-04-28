#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";

const SOURCE_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".css"]);
const IGNORED_USAGE_PREFIXES = ["tw-"];

async function exists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function findRepoRoot(startDir) {
  let current = path.resolve(startDir);

  while (true) {
    const candidate = path.join(current, "apps", "web", "src");
    if (await exists(candidate)) {
      return current;
    }

    const parent = path.dirname(current);
    if (parent === current) {
      throw new Error("Unable to locate repository root containing apps/web/src");
    }
    current = parent;
  }
}

async function collectFiles(dirPath, files = []) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);

    if (entry.isDirectory()) {
      await collectFiles(fullPath, files);
      continue;
    }

    const ext = path.extname(entry.name);
    if (SOURCE_EXTENSIONS.has(ext)) {
      files.push(fullPath);
    }
  }

  return files;
}

function shouldIgnoreToken(tokenName) {
  return IGNORED_USAGE_PREFIXES.some((prefix) => tokenName.startsWith(prefix));
}

function extractUsageTokens(content, relativeFilePath) {
  const usageMap = new Map();
  const usageRegex = /var\(--([A-Za-z0-9_-]+)/g;
  const lines = content.split(/\r?\n/);

  lines.forEach((line, index) => {
    usageRegex.lastIndex = 0;
    let match = usageRegex.exec(line);
    while (match) {
      const token = match[1];
      if (!shouldIgnoreToken(token)) {
        const lineNumber = index + 1;
        const occurrence = `${relativeFilePath}:${lineNumber}`;
        const entries = usageMap.get(token) ?? [];
        entries.push(occurrence);
        usageMap.set(token, entries);
      }
      match = usageRegex.exec(line);
    }
  });

  return usageMap;
}

function extractDefinitionTokens(content) {
  const definitions = new Set();
  const definitionRegex = /--([A-Za-z0-9_-]+)\s*:/g;
  let match = definitionRegex.exec(content);

  while (match) {
    definitions.add(match[1]);
    match = definitionRegex.exec(content);
  }

  return definitions;
}

async function main() {
  const repoRoot = await findRepoRoot(process.cwd());
  const webSrcPath = path.join(repoRoot, "apps", "web", "src");
  const files = await collectFiles(webSrcPath);

  const definedTokens = new Set();
  const tokenUsage = new Map();

  for (const filePath of files) {
    const content = await fs.readFile(filePath, "utf8");
    const relativeFilePath = path.relative(repoRoot, filePath);
    const fileExt = path.extname(filePath);

    if (fileExt === ".css") {
      for (const token of extractDefinitionTokens(content)) {
        definedTokens.add(token);
      }
    }

    const usageInFile = extractUsageTokens(content, relativeFilePath);
    for (const [token, occurrences] of usageInFile.entries()) {
      const current = tokenUsage.get(token) ?? [];
      current.push(...occurrences);
      tokenUsage.set(token, current);
    }
  }

  const missingTokens = Array.from(tokenUsage.keys())
    .filter((token) => !definedTokens.has(token))
    .sort((a, b) => a.localeCompare(b));

  if (missingTokens.length === 0) {
    console.log(
      `✅ CSS token check passed: ${tokenUsage.size} referenced tokens, ${definedTokens.size} defined tokens, 0 missing.`
    );
    return;
  }

  console.error(
    `❌ CSS token check failed: found ${missingTokens.length} undefined token(s) in apps/web/src.`
  );
  console.error("Undefined tokens:");

  for (const token of missingTokens) {
    const occurrences = tokenUsage.get(token) ?? [];
    const samples = occurrences.slice(0, 3).join(", ");
    console.error(`- --${token} (${occurrences.length} usage${occurrences.length > 1 ? "s" : ""})`);
    if (samples) {
      console.error(`  e.g. ${samples}`);
    }
  }

  process.exitCode = 1;
}

main().catch((error) => {
  console.error("❌ CSS token check crashed:");
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
