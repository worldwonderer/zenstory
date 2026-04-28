# Quality Check Scripts

Unified code quality checking for backend and frontend.

## check-quality.sh - Unified Quality Checker

### Usage

```bash
./scripts/quality/check-quality.sh [all|backend|frontend|security|i18n]
```

### Check Types

| Type       | Description                                    |
|------------|------------------------------------------------|
| `all`      | Run all checks (backend + frontend) - default  |
| `backend`  | Ruff, MyPy, Bandit, Safety                     |
| `frontend` | CSS token check, ESLint, TypeScript check     |
| `security` | Bandit + Safety (security focused)             |
| `i18n`     | Hardcoded Chinese text detection               |

### Backend Checks

| Tool    | Purpose                    |
|---------|----------------------------|
| Ruff    | Python linting             |
| MyPy    | Type checking              |
| Bandit  | Security linting           |
| Safety  | Dependency vulnerabilities |

### Frontend Checks

| Tool         | Purpose                               |
|--------------|---------------------------------------|
| CSS Token    | Detect undefined `var(--token)` usage |
| ESLint       | JavaScript/TypeScript linting         |
| tsc          | TypeScript type checking              |

### Examples

```bash
# Run all checks
./scripts/quality/check-quality.sh all

# Backend only
./scripts/quality/check-quality.sh backend

# Frontend only
./scripts/quality/check-quality.sh frontend

# Security focused
./scripts/quality/check-quality.sh security

# i18n check
./scripts/quality/check-quality.sh i18n
```

### Prerequisites

**Backend:**
- Virtual environment at `apps/server/venv`
- Tools installed: `ruff`, `mypy`, `bandit`, `safety`

```bash
cd apps/server
source venv/bin/activate
pip install ruff mypy bandit safety
```

**Frontend:**
- Node.js 18+ with pnpm
- Dependencies installed

```bash
cd apps/web
pnpm install
```

### Exit Codes

- `0`: All checks passed
- `1`: One or more checks failed

## check-hardcoded-text.sh - i18n Hardcoded Text Detection

Detects hardcoded Chinese text in frontend source files that should be internationalized.

### Usage

```bash
./scripts/quality/check-hardcoded-text.sh
```

### What It Detects

- Chinese characters (`\u4e00-\u9fa5`) in `.tsx` and `.ts` files

### What It Excludes

- Comment lines (`//`)
- Lines using `useTranslation`
- Lines with `t('...')` or `t("...")`
- Lines with `i18n`
- Lines with `getLocale`
- Import statements

### Manual Review Required

The script may produce false positives for:
- String template variables
- Log messages
- API response handling

### i18n Best Practices

```tsx
// Bad - Hardcoded
<button>提交</button>

// Good - Using i18n
const { t } = useTranslation();
<button>{t('common.submit')}</button>
```

### Related Files

- `apps/web/public/locales/en/translation.json`
- `apps/web/public/locales/zh/translation.json`

## check-web-css-token-vars.mjs - CSS Token Guardrail

Detects undefined CSS custom properties used via `var(--token)` in `apps/web/src`.

### Usage

```bash
cd apps/web
pnpm lint:tokens
```

### What It Checks

- Scans `.ts`, `.tsx`, `.js`, `.jsx`, `.css` files under `apps/web/src`
- Collects all `var(--token)` references
- Collects all CSS custom property definitions (`--token:`) from web CSS files
- Fails if any referenced token has no definition

## check-i18n-defaultvalue-keys.mjs - defaultValue 翻译键覆盖校验

用于检测 `t("ns:key", { defaultValue: ... })` 场景下，`zh/en` locale 是否都存在对应 key，防止上线后 fallback 到默认文案。

### Usage

```bash
cd apps/web
pnpm lint:i18n-keys
```

### What It Checks

- 扫描 `apps/web/src` 非测试文件中的 `t("ns:key", { defaultValue: ... })`
- 校验 `apps/web/public/locales/{zh,en}/{ns}.json` 是否存在对应嵌套键
- 缺失时输出 `[locale] ns:key` 与示例源码文件，并返回非 0 退出码
