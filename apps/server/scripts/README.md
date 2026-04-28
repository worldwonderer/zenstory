# Scripts

## release_preflight_check.py

发布前快速自检（配置 + Alembic heads）。

### 用法

```bash
cd apps/server
python scripts/release_preflight_check.py --strict
```

会检查：
- `ENVIRONMENT`（strict 模式要求 production/staging）
- `JWT_SECRET_KEY` 强度
- `ALLOW_LEGACY_UNTYPED_TOKENS` / `ALLOW_LEGACY_REFRESH_WITHOUT_JTI`
- `CORS_ORIGINS`
- `RATE_LIMIT_BACKEND`
- Alembic heads 是否唯一

