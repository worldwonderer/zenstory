# Core Module - Error Code System

## 概述

本模块实现了错误码系统，为国际化支持提供后端基础设施。

## 文件说明

### 1. `error_codes.py` - 错误码定义

定义了所有错误码常量和中英文错误消息映射。

**错误码格式**: `ERR_{MODULE}_{SPECIFIC_ERROR}`

**模块分类**:
- 1xxx: 通用错误 (Common errors)
- 2xxx: 认证授权错误 (Authentication & authorization)
- 3xxx: 项目错误 (Project errors)
- 4xxx: 文件错误 (File errors)
- 5xxx: 版本错误 (Version errors)
- 6xxx: 快照错误 (Snapshot errors)
- 7xxx: 导出错误 (Export errors)
- 8xxx: 聊天错误 (Chat errors)
- 9xxx: 语音错误 (Voice errors)

**主要类和函数**:
- `ErrorCode`: 错误码常量类
- `ERROR_MESSAGES`: 错误消息映射字典（支持 zh 和 en）
- `get_error_message(error_code, lang)`: 根据错误码和语言获取错误消息

### 2. `error_handler.py` - 统一错误处理器

提供了自定义异常类和全局异常处理。

**主要类**:
- `APIException`: 自定义 API 异常类，支持错误码

**主要函数**:
- `api_exception_handler()`: 处理 APIException 实例
- `http_exception_handler()`: 处理标准 HTTPException（向后兼容）
- `validation_exception_handler()`: 处理请求验证错误
- `general_exception_handler()`: 处理所有未处理的异常

### 3. `error_codes.py` 中的错误消息映射

错误消息翻译直接在 `ERROR_MESSAGES` 字典中维护，包含中文和英文两种语言。

### 4. `main.py` - 全局异常处理器注册

在应用启动时注册了四个全局异常处理器：
1. `APIException` → `api_exception_handler`
2. `StarletteHTTPException` → `http_exception_handler`
3. `RequestValidationError` → `validation_exception_handler`
4. `Exception` → `general_exception_handler`

## 使用方法

### 1. 在 API 中抛出错误

```python
from core.error_codes import ErrorCode
from core.error_handler import APIException

# 方式 1: 使用自定义 APIException（推荐）
raise APIException(
    error_code=ErrorCode.PROJECT_NOT_FOUND,
    status_code=404
)

# 方式 2: 标准 HTTPException（向后兼容，不推荐）
from fastapi import HTTPException
raise HTTPException(status_code=404, detail="Project not found")
```

### 2. 响应格式

**使用 APIException**:
```json
{
  "detail": "ERR_PROJECT_NOT_FOUND",
  "error_code": "ERR_PROJECT_NOT_FOUND"
}
```

**使用 HTTPException**:
```json
{
  "detail": "Project not found"
}
```

### 3. 错误码示例

```python
# 认证错误
ErrorCode.AUTH_INVALID_CREDENTIALS  # 用户名或密码错误
ErrorCode.AUTH_TOKEN_EXPIRED         # 登录已过期
ErrorCode.NOT_AUTHORIZED            # 您没有权限执行此操作

# 项目错误
ErrorCode.PROJECT_NOT_FOUND          # 项目不存在
ErrorCode.PROJECT_ALREADY_EXISTS     # 项目已存在

# 文件错误
ErrorCode.FILE_NOT_FOUND            # 文件不存在
ErrorCode.FILE_TYPE_INVALID         # 文件类型无效
```

## 错误消息翻译

前端使用后端返回的错误码，通过 i18n 系统查找对应的翻译消息。

**中文翻译位置**: `apps/web/public/locales/zh/errors.json`
**英文翻译位置**: `apps/web/public/locales/en/errors.json`

## Phase 1 完成内容

✅ 创建错误码定义文件 `core/error_codes.py`（包含错误消息映射）
✅ 实现统一错误处理器 `core/error_handler.py`
✅ 注册全局异常处理器到 `main.py`
✅ 所有文件通过 Python 编译验证

## 后续阶段

- **Phase 2**: 重构核心 API 文件（auth.py, projects.py, files.py）使用错误码
- **Phase 3**: 重构其他后端模块（versions.py, chat.py, voice.py, export.py, agent.py, services, middleware）
- **Phase 4-6**: 前端基础设施和组件改造
