import { Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export interface AccessibilityScanResult {
  violations: Array<{
    id: string;
    impact: 'minor' | 'moderate' | 'serious' | 'critical';
    description: string;
    help: string;
    helpUrl: string;
    nodes: Array<{ html: string; failureSummary: string; target: string[]; }>;
  }>;
  passes: number;
  incomplete: Array<unknown>;
}

export async function runAccessibilityScan(
  page: Page,
  options?: {
    include?: string[];
    exclude?: string[];
    disableRules?: string[];
    tags?: string[];
  }
): Promise<AccessibilityScanResult> {
  const builder = new AxeBuilder({ page });

  if (options?.include) {
    options.include.forEach(selector => builder.include(selector));
  }
  if (options?.exclude) {
    options.exclude.forEach(selector => builder.exclude(selector));
  }
  if (options?.disableRules) {
    builder.disableRules(options.disableRules);
  }
  if (options?.tags) {
    builder.withTags(options.tags);
  }

  const results = await builder.analyze();

  return {
    violations: results.violations.map(v => ({
      id: v.id,
      impact: v.impact as AccessibilityScanResult['violations'][0]['impact'],
      description: v.description,
      help: v.help,
      helpUrl: v.helpUrl,
      nodes: v.nodes.map(n => ({
        html: n.html,
        failureSummary: n.failureSummary || '',
        target: n.target as string[]
      }))
    })),
    passes: results.passes.length,
    incomplete: results.incomplete
  };
}

export async function checkWCAGAA(page: Page): Promise<AccessibilityScanResult> {
  return runAccessibilityScan(page, { tags: ['wcag2a', 'wcag2aa'] });
}

export async function checkWCAGAAA(page: Page): Promise<AccessibilityScanResult> {
  return runAccessibilityScan(page, { tags: ['wcag2a', 'wcag2aa', 'wcag2aaa'] });
}

export function assertNoCriticalViolations(result: AccessibilityScanResult): void {
  const ignoredRuleIds = new Set(
    (process.env.E2E_A11Y_IGNORE_RULE_IDS
      || 'aria-command-name,color-contrast,html-has-lang,nested-interactive,aria-allowed-attr,aria-prohibited-attr')
      .split(',')
      .map((id) => id.trim())
      .filter(Boolean)
  );
  const failOnSerious = process.env.E2E_A11Y_FAIL_ON_SERIOUS === 'true';

  const criticalOrSerious = result.violations.filter((v) => {
    if (ignoredRuleIds.has(v.id)) {
      return false;
    }
    if (v.impact === 'critical') {
      return true;
    }
    return failOnSerious && v.impact === 'serious';
  });

  if (criticalOrSerious.length > 0) {
    const messages = criticalOrSerious.map(v =>
      `${v.id} (${v.impact}): ${v.description}\n  ${v.helpUrl}`
    ).join('\n');
    const severityLabel = failOnSerious ? 'critical/serious' : 'critical';
    throw new Error(`Found ${criticalOrSerious.length} ${severityLabel} accessibility violations:\n${messages}`);
  }
}
