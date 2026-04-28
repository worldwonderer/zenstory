#!/bin/bash
# Prefect Server 启动脚本
# 支持 Railway 环境变量

# 使用 Railway 提供的 PORT 或默认 4200
PORT=${PORT:-4200}

# 启动 Prefect Server
exec prefect server start --host 0.0.0.0 --port $PORT
