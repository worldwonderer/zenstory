# Railway 部署 Prefect 指南

本指南介绍如何在 Railway 上部署素材库的 Prefect 工作流系统。

## 方案选择

### 方案 A: 自托管 Prefect Server（三个服务）

需要部署三个 Railway 服务：
1. **zenstory-api** - FastAPI 主服务
2. **zenstory-prefect-server** - Prefect Server
3. **zenstory-prefect-worker** - Prefect Worker

**优点**: 完全控制，数据私有
**缺点**: 成本较高（3个服务），需要维护

### 方案 B: Prefect Cloud（推荐）

使用 Prefect Cloud 托管服务，只需部署：
1. **zenstory-api** - FastAPI 主服务
2. **zenstory-prefect-worker** - Prefect Worker

**优点**: 免费监控 UI，简单易用，成本低
**缺点**: 数据存储在 Prefect Cloud

---

## 方案 A: 自托管部署步骤

### 1. 创建 PostgreSQL 数据库

在 Railway 项目中添加 PostgreSQL 服务，用于 Prefect Server。

### 2. 部署 Prefect Server

```bash
# 在 Railway 项目中创建新服务
railway service create prefect-server
```

配置：
- **Dockerfile**: `docker/Dockerfile.prefect-server`
- **Port**: 4200

环境变量：
```
PREFECT_API_DATABASE_CONNECTION_URL=${{Postgres.DATABASE_URL}}
PREFECT_SERVER_API_HOST=0.0.0.0
PREFECT_SERVER_API_PORT=4200
```

### 3. 部署 Prefect Worker

```bash
railway service create prefect-worker
```

配置：
- **Dockerfile**: `docker/Dockerfile.prefect-worker`

环境变量：
```
PREFECT_API_URL=https://prefect-server.up.railway.app/api
DATABASE_URL=${{Postgres.DATABASE_URL}}
MATERIAL_ANTHROPIC_API_KEY=your-api-key
MATERIAL_ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
MATERIAL_ANTHROPIC_MODEL=glm-4.7
```

### 4. 初始化 Work Pool

部署完成后，通过 Prefect Server UI 或 CLI 创建 Work Pool：

```bash
export PREFECT_API_URL=https://prefect-server.up.railway.app/api
prefect work-pool create zenstory-pool --type process
prefect deploy --all
```

### 5. 更新 API 服务

在 zenstory-api 服务中添加环境变量：
```
PREFECT_API_URL=https://prefect-server.up.railway.app/api
```

---

## 方案 B: Prefect Cloud 部署步骤（推荐）

### 1. 注册 Prefect Cloud

访问 https://app.prefect.cloud 注册账号（免费）。

### 2. 获取 API Key

在 Prefect Cloud 控制台：
1. 点击头像 → API Keys
2. 创建新的 API Key
3. 复制 Key 和 Account ID

### 3. 部署 Worker

在 Railway 中创建 prefect-worker 服务：

环境变量：
```
PREFECT_API_URL=https://api.prefect.cloud/api/accounts/<ACCOUNT_ID>/workspaces/<WORKSPACE_ID>
PREFECT_API_KEY=your-prefect-cloud-api-key
DATABASE_URL=${{Postgres.DATABASE_URL}}
MATERIAL_ANTHROPIC_API_KEY=your-api-key
MATERIAL_ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
MATERIAL_ANTHROPIC_MODEL=glm-4.7
```

### 4. 创建 Work Pool

在 Prefect Cloud UI 中：
1. 进入 Work Pools
2. 创建新的 Work Pool，名称为 `zenstory-pool`
3. 类型选择 `Process`

### 5. 部署 Flows

本地运行：
```bash
export PREFECT_API_URL=https://api.prefect.cloud/api/accounts/<ACCOUNT_ID>/workspaces/<WORKSPACE_ID>
export PREFECT_API_KEY=your-prefect-cloud-api-key

cd apps/server
prefect deploy --all
```

### 6. 更新 API 服务

在 zenstory-api 服务中添加环境变量：
```
PREFECT_API_URL=https://api.prefect.cloud/api/accounts/<ACCOUNT_ID>/workspaces/<WORKSPACE_ID>
PREFECT_API_KEY=your-prefect-cloud-api-key
```

---

## 环境变量汇总

### API 服务 (zenstory-api)

| 变量 | 说明 | 示例 |
|------|------|------|
| `PREFECT_API_URL` | Prefect API 地址 | 见上方配置 |
| `PREFECT_API_KEY` | Prefect Cloud API Key（方案B） | pnu_xxx |
| `DATABASE_URL` | 应用数据库 | postgresql://... |
| `MATERIAL_INTERNAL_TOKEN` | 与 Worker 共享的内部下载鉴权 token | 随机高强度字符串 |

### Worker 服务 (zenstory-prefect-worker)

| 变量 | 说明 |
|------|------|
| `PREFECT_API_URL` | Prefect API 地址 |
| `PREFECT_API_KEY` | Prefect Cloud API Key（方案B） |
| `DATABASE_URL` | 应用数据库（Worker 需要访问） |
| `API_SERVER_INTERNAL_URL` | API 服务内网地址（建议 `http://server.railway.internal:8080`） |
| `MATERIAL_INTERNAL_TOKEN` | 与 API 服务一致的内部下载鉴权 token |
| `MATERIAL_*` | 素材库 LLM 配置 |

---

## 验证部署

1. 检查 Worker 状态：
   - 方案 A: 访问 `https://prefect-server.up.railway.app`
   - 方案 B: 访问 `https://app.prefect.cloud`

2. 测试上传：
   - 在前端上传一个小说文件
   - 查看 Prefect UI 中的 Flow Run 状态

3. 查看日志：
   - Railway Dashboard → 选择服务 → Logs
