#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..", "..");
const webRoot = path.join(repoRoot, "apps", "web");
const srcRoot = path.join(webRoot, "src");
const localeRoot = path.join(webRoot, "public", "locales");

const LOCALES = ["zh", "en"];
const KEY_REGEX = /t\(\s*["'`]([^"'`]+)["'`]\s*,\s*\{[\s\S]{0,320}?defaultValue\s*:/g;

function walkFiles(dir) {
  const files = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === "dist" || entry.name === "__tests__") {
        continue;
      }
      files.push(...walkFiles(fullPath));
      continue;
    }

    if (!entry.isFile()) continue;
    if (!/\.(ts|tsx)$/.test(entry.name)) continue;
    if (entry.name.includes(".test.")) continue;
    files.push(fullPath);
  }
  return files;
}

function hasNestedPath(obj, dottedPath) {
  const parts = dottedPath.split(".");
  let current = obj;
  for (const part of parts) {
    if (typeof current !== "object" || current === null || !(part in current)) {
      return false;
    }
    current = current[part];
  }
  return true;
}

function collectNamespacedDefaultValueKeys() {
  const keyToFiles = new Map();
  const files = walkFiles(srcRoot);

  for (const file of files) {
    const content = fs.readFileSync(file, "utf8");
    for (const match of content.matchAll(KEY_REGEX)) {
      const rawKey = match[1];
      if (!rawKey || !rawKey.includes(":")) continue;
      if (rawKey.includes("${")) continue;
      const [ns, keyPath] = rawKey.split(":", 2);
      if (!ns || !keyPath) continue;
      const composite = `${ns}:${keyPath}`;
      if (!keyToFiles.has(composite)) {
        keyToFiles.set(composite, new Set());
      }
      keyToFiles.get(composite).add(path.relative(repoRoot, file));
    }
  }

  return keyToFiles;
}

function main() {
  const keyToFiles = collectNamespacedDefaultValueKeys();
  const missing = [];

  for (const compositeKey of [...keyToFiles.keys()].sort()) {
    const [ns, keyPath] = compositeKey.split(":", 2);
    for (const locale of LOCALES) {
      const localeFile = path.join(localeRoot, locale, `${ns}.json`);
      if (!fs.existsSync(localeFile)) {
        missing.push({
          locale,
          key: compositeKey,
          reason: "missing namespace file",
          exampleFile: [...keyToFiles.get(compositeKey)][0],
        });
        continue;
      }
      const data = JSON.parse(fs.readFileSync(localeFile, "utf8"));
      if (!hasNestedPath(data, keyPath)) {
        missing.push({
          locale,
          key: compositeKey,
          reason: "missing key",
          exampleFile: [...keyToFiles.get(compositeKey)][0],
        });
      }
    }
  }

  console.log(
    `[i18n-defaultValue-check] scanned keys=${keyToFiles.size}, missing=${missing.length}`
  );

  if (missing.length === 0) {
    console.log("[i18n-defaultValue-check] ✅ passed");
    process.exit(0);
  }

  console.error("[i18n-defaultValue-check] ❌ missing locale keys detected:");
  for (const item of missing) {
    console.error(
      `  - [${item.locale}] ${item.key} (${item.reason}) @ ${item.exampleFile}`
    );
  }
  process.exit(1);
}

main();
