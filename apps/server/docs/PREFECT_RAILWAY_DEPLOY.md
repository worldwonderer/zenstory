# Prefect Railway 部署指南

## 概述

本指南介绍如何在 Railway 上部署 Prefect Server 和 Worker，用于素材库小说拆解流程。

## 架构

```
┌─────────────────┐     ┌─────────────────┐
│  Prefect Server │◄────│  Prefect Worker │
│   (调度服务器)   │     │   (执行节点)     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   PostgreSQL    │     │   API Server    │
│   (Prefect DB)  │     │   (业务数据库)   │
└─────────────────┘     └─────────────────┘
```

## 部署步骤

### 1. 使用现有 PostgreSQL 数据库

项目已有 PostgreSQL 服务，Prefect Server 将复用该数据库。

### 2. 在 Railway Web UI 配置 Dockerfile 路径

**重要**: Railway CLI 不支持直接指定 Dockerfile 路径，需要在 Web UI 中配置。

1. 打开 Railway 项目: https://railway.com/project/cbe4812b-c4fd-4d4d-ae13-b06395b2c7f0
2. 点击 `prefect-server` 服务
3. 进入 **Settings** → **Build**
4. 设置 **Dockerfile Path**: `apps/server/docker/Dockerfile.prefect-server`
5. 对 `prefect-worker` 服务重复上述步骤，设置路径为: `apps/server/docker/Dockerfile.prefect-worker`

### 3. 部署 Prefect Server

#### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `PREFECT_API_DATABASE_CONNECTION_URL` | PostgreSQL 连接字符串 | `postgresql+asyncpg://user:pass@host:5432/prefect` |
| `PORT` | 服务端口 (Railway 自动设置) | `4200` |

#### 部署命令

```bash
# 在 Railway 项目中添加服务
railway link
railway up --service prefect-server
```

### 3. 部署 Prefect Worker

#### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `PREFECT_API_URL` | Prefect Server API 地址 | `https://prefect-server.railway.app/api` |
| `PREFECT_WORK_POOL` | 工作池名称 | `zenstory-pool` |
| `DATABASE_URL` | 业务数据库连接 | `postgresql://...` |
| `API_SERVER_INTERNAL_URL` | API 服务内网地址（用于下载上传文件） | `http://server.railway.internal:8080` |
| `MATERIAL_INTERNAL_TOKEN` | Worker/API 共享内部鉴权 token | `your-random-secret` |
| `MATERIAL_LLM_PROVIDER` | LLM 提供商 | `anthropic` |
| `MATERIAL_ANTHROPIC_API_KEY` | API 密钥 | `sk-...` |
| `MATERIAL_ANTHROPIC_BASE_URL` | API 基础 URL | `https://open.bigmodel.cn/api/anthropic` |
| `MATERIAL_ANTHROPIC_MODEL` | 模型名称 | `glm-4.7` |

#### 部署命令

```bash
railway up --service prefect-worker
```

### 4. 创建工作池

部署完成后，需要在 Prefect Server 中创建工作池：

```bash
# 设置 API URL
export PREFECT_API_URL=https://your-prefect-server.railway.app/api

# 创建工作池
prefect work-pool create zenstory-pool --type process
```

### 5. 部署流程

```bash
# 部署所有流程
prefect deploy --all
```

## 验证部署

1. 访问 Prefect Server UI: `https://your-prefect-server.railway.app`
2. 检查工作池状态
3. 检查 Worker 是否在线

## 故障排除

### Worker 无法连接到 Server

检查 `PREFECT_API_URL` 是否正确设置。

同时检查文件下载链路配置：
- `API_SERVER_INTERNAL_URL` 必须使用内网域名（`server.railway.internal`），不要使用公网域名。
- API 服务与 Worker 服务都必须设置相同的 `MATERIAL_INTERNAL_TOKEN`。

### 数据库连接失败

确保 PostgreSQL 服务正常运行，连接字符串格式正确。
