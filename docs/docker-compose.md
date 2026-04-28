# zenstory Docker Compose 使用指南

## Quick Start（推荐）

只需配置一个 LLM API Key 即可启动：

```bash
# 1. 设置 API Key
export DEEPSEEK_API_KEY=your-key-here
# 或: export ANTHROPIC_API_KEY=your-key-here

# 2. 启动
docker compose up -d --build

# 3. 访问
# Web:  http://localhost:5173
# API:  http://localhost:8000/docs
```

使用 SQLite，无需外部数据库。数据持久化在 Docker volume 中。

## 生产部署（PostgreSQL + Redis）

```bash
# 1. 准备环境文件
cp apps/server/.env.docker.example apps/server/.env.docker
cp apps/web/.env.docker.example apps/web/.env.docker

# 2. 编辑 apps/server/.env.docker，填入：
#    - DEEPSEEK_API_KEY 或 ANTHROPIC_API_KEY
#    - JWT_SECRET_KEY（至少 32 字符）
#    - DATABASE_URL（如需覆盖默认连接）

# 3. 启动
docker compose -f docker-compose.full.yml up -d --build
```

## 开发热更新

开发模式请使用 `docker-compose.mini-local.yml`，支持挂载本地代码进行热更新。

## 常用命令

```bash
docker compose up -d --build      # 启动并构建
docker compose down -v            # 停止并删除容器/卷
docker compose logs -f server     # 查看后端日志
docker compose ps                 # 查看服务状态
```

## 故障排查

### 端口冲突

```bash
lsof -i :5173  # Web
lsof -i :8000  # Server
```

修改端口：`SERVER_PORT=9000 WEB_PORT=3000 docker compose up -d`

### 服务不健康

```bash
docker compose logs --tail=100 server
curl -f http://localhost:8000/health
```
