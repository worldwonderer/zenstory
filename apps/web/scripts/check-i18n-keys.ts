import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const LOCALES_DIR = join(__dirname, '../public/locales');
const _LOCALES = ['zh', 'en'];

const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const GRAY = '\x1b[90m';
const BOLD = '\x1b[1m';
const RESET = '\x1b[0m';

function getAllKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const keys: string[] = [];
  for (const key of Object.keys(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    const value = obj[key];
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      keys.push(...getAllKeys(value as Record<string, unknown>, fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys;
}

function loadJson(filePath: string): Record<string, unknown> | null {
  if (!existsSync(filePath)) return null;
  try {
    return JSON.parse(readFileSync(filePath, 'utf-8'));
  } catch {
    console.error(`${RED}  Failed to parse: ${filePath}${RESET}`);
    return null;
  }
}

function compareFiles(): void {
  const zhDir = join(LOCALES_DIR, 'zh');
  const enDir = join(LOCALES_DIR, 'en');

  if (!existsSync(zhDir) || !existsSync(enDir)) {
    console.error(`${RED}Missing locale directories${RESET}`);
    process.exit(1);
  }

  const zhFiles = readdirSync(zhDir).filter((f) => f.endsWith('.json')).sort();
  const enFiles = readdirSync(enDir).filter((f) => f.endsWith('.json')).sort();

  const allFiles = [...new Set([...zhFiles, ...enFiles])].sort();

  let totalChecked = 0;
  let totalMismatches = 0;

  console.log(`\n${BOLD}i18n Key Alignment Check${RESET}`);
  console.log(`${GRAY}Comparing zh/ and en/ locale files...\n${RESET}`);

  for (const file of allFiles) {
    const zhPath = join(zhDir, file);
    const enPath = join(enDir, file);
    const zhData = loadJson(zhPath);
    const enData = loadJson(enPath);

    if (!zhData && !enData) continue;

    totalChecked++;

    if (!zhData) {
      console.log(`${RED}  MISSING${RESET} zh/${file}`);
      totalMismatches++;
      continue;
    }
    if (!enData) {
      console.log(`${RED}  MISSING${RESET} en/${file}`);
      totalMismatches++;
      continue;
    }

    const zhKeys = new Set(getAllKeys(zhData));
    const enKeys = new Set(getAllKeys(enData));

    const onlyZh = [...zhKeys].filter((k) => !enKeys.has(k)).sort();
    const onlyEn = [...enKeys].filter((k) => !zhKeys.has(k)).sort();

    if (onlyZh.length === 0 && onlyEn.length === 0) {
      console.log(`${GREEN}  OK${RESET}      ${file} (${zhKeys.size} keys)`);
    } else {
      totalMismatches++;
      console.log(`${RED}  MISMATCH${RESET} ${file}`);
      for (const k of onlyZh) {
        console.log(`${YELLOW}    zh only: ${k}${RESET}`);
      }
      for (const k of onlyEn) {
        console.log(`${YELLOW}    en only: ${k}${RESET}`);
      }
    }
  }

  console.log(`\n${BOLD}Summary${RESET}`);
  console.log(`  Files checked: ${totalChecked}`);
  console.log(
    `  Result: ${
      totalMismatches === 0
        ? `${GREEN}All keys aligned${RESET}`
        : `${RED}${totalMismatches} file(s) with mismatches${RESET}`
    }\n`
  );

  process.exit(totalMismatches > 0 ? 1 : 0);
}

compareFiles();
