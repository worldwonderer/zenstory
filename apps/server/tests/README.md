# 测试文档

zenstory 后端测试套件使用 pytest 和相关工具为 FastAPI 应用提供全面的测试覆盖。

## 目录

- [测试目录结构](#测试目录结构)
- [快速开始](#快速开始)
- [运行测试](#运行测试)
- [常见 Fixtures](#常见-fixtures)
- [测试标记](#测试标记)
- [Mock 外部依赖](#mock-外部依赖)
- [测试示例](#测试示例)
- [最佳实践](#最佳实践)

## 测试目录结构

```
tests/
├── conftest.py                  # 共享 fixtures 和 pytest 配置
├── __init__.py
├── test_api/                    # API 集成测试
│   ├── __init__.py
│   ├── test_auth.py            # 认证 API 测试
│   ├── test_projects.py        # 项目 API 测试
│   ├── test_files.py           # 文件 API 测试
│   ├── test_versions.py        # 版本历史 API 测试
│   ├── test_agent.py           # Agent API 测试
│   ├── test_chat.py            # Chat API 测试
│   └── test_export.py          # 导出 API 测试
├── test_services/               # 服务层单元测试
│   ├── __init__.py
│   ├── test_file_version_service.py
│   ├── test_snapshot_service.py
│   ├── test_verification_service.py
│   └── test_export_service.py
├── test_agent/                  # Agent 系统测试
│   ├── __init__.py
│   ├── test_service.py         # Agent 核心服务
│   ├── test_context_assembler.py
│   ├── test_context_budget.py
│   └── test_file_executor.py
├── test_models/                 # 数据模型测试
│   ├── __init__.py
│   ├── test_entities.py        # 实体模型
│   └── test_file_model.py      # 文件模型
├── test_middleware/             # 中间件测试
│   ├── __init__.py
│   └── test_logging_middleware.py
├── test_core/                   # 核心功能测试
│   ├── __init__.py
│   └── test_error_handler.py
└── test_utils/                  # 工具函数测试
    ├── __init__.py
    └── test_security.py
```

## 快速开始

### 前置要求

1. **Python 环境**: Python 3.11 或 3.12
2. **虚拟环境**:
   ```bash
   cd apps/server
   # 推荐：优先使用 Python 3.12 环境（项目当前兼容性最佳）
   python3.12 -m venv .venv312
   source .venv312/bin/activate  # Windows: .venv312\Scripts\activate
   ```

3. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行测试并显示详细输出
pytest -v

# 运行特定测试文件
pytest tests/test_api/test_auth.py

# 运行特定测试函数
pytest tests/test_api/test_auth.py::test_register_success

# 运行测试并生成覆盖率报告
pytest --cov=. --cov-report=html --cov-report=term
```

### 使用 Makefile

```bash
# 检查当前测试环境解释器和关键依赖
make env-check

# 运行所有测试
make test

# 运行测试并生成覆盖率报告
make test-cov

# 只运行单元测试
make test-unit

# 只运行集成测试
make test-integration

# 运行测试（详细输出）
make test-verbose
```

## 运行测试

### 本地测试

测试使用 SQLite 文件数据库（临时文件）进行，无需启动 PostgreSQL 或 Redis。

```bash
# 基础测试运行
pytest

# 建立不受默认 addopts 影响的收集/基线口径
pytest -o addopts='' --collect-only -q tests

# 三条推荐 lane
make test-fast
make test-risk
make test-deep

# 带覆盖率报告
pytest --cov=. --cov-report=html
# 查看 HTML 报告: open htmlcov/index.html
```

### 使用 Docker 服务（可选）

如果需要测试 PostgreSQL 或 Redis 集成：

```bash
# 启动测试环境
make test-env-up
# 或
docker-compose -f docker-compose.test.yml up -d

# 运行测试
pytest

# 停止测试环境
make test-env-down
```

## 常见 Fixtures

### db_session

提供测试数据库会话，每个测试后自动清理数据。

```python
import pytest
from sqlmodel import Session
from models import User

@pytest.mark.unit
def test_create_user(db_session: Session):
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.username == "testuser"
```

### client (AsyncClient)

提供异步 HTTP 客户端用于测试 FastAPI 端点。

```python
import pytest
from httpx import AsyncClient

@pytest.mark.integration
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
```

### 创建测试数据的 Fixtures

```python
@pytest.fixture
def test_user(db_session: Session):
    """创建测试用户"""
    from services.core.auth_service import hash_password
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def test_project(db_session: Session, test_user):
    """创建测试项目"""
    project = Project(
        name="Test Project",
        description="A test project",
        user_id=test_user.id
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project
```

## 测试标记

使用 pytest 标记来分类测试：

- `@pytest.mark.unit`: 单元测试（快速，隔离）
- `@pytest.mark.integration`: 集成测试（较慢，可能使用外部服务）
- `@pytest.mark.slow`: 慢速测试（可能超过 1 秒）
- `@pytest.mark.asyncio`: 异步测试

```python
@pytest.mark.unit
def test_user_model(db_session: Session):
    """单元测试示例"""
    pass

@pytest.mark.integration
async def test_api_endpoint(client: AsyncClient):
    """集成测试示例"""
    pass
```

运行特定标记的测试：

```bash
# 只运行单元测试
pytest -m unit

# 只运行集成测试
pytest -m integration

# 排除慢速测试
pytest -m "not slow"
```

## Mock 外部依赖

### Mock OpenAI API

使用 `pytest-mock` 的 `mocker` fixture：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.integration
async def test_agent_stream(mocker, client: AsyncClient):
    # Mock OpenAI 客户端
    mock_llm = AsyncMock()
    mock_llm.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test response")))]
    )

    # 注入 mock
    mocker.patch("agent.core.llm_client.get_openai_client", return_value=mock_llm)

    # 测试代码
    response = await client.post("/agent/stream", json={...})
    assert response.status_code == 200
```

### Mock Redis 客户端

```python
@pytest.mark.unit
async def test_verification_service(mocker):
    # Mock Redis 客户端
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    mock_redis.get.return_value = "123456"
    mock_redis.delete.return_value = 1

    mocker.patch(
        "services.infra.redis_client.get_redis_client",
        return_value=mock_redis
    )

    # 测试验证码服务
    from services.features.verification_service import VerificationService
    result = await VerificationService.verify_code("test@example.com", "123456")
    assert result is True
```

### Mock 邮件服务

```python
@pytest.mark.unit
async def test_email_sending(mocker):
    # Mock Resend 客户端
    mock_resend = mocker.patch("resend.Resend")

    # 测试发送邮件
    from services.infra.email_client import EmailClient
    await EmailClient.send_verification_email("test@example.com", "123456")

    # 验证 mock 被调用
    mock_resend.return_value.emails.send.assert_called_once()
```

## 测试示例

### API 测试示例

```python
"""
tests/test_api/test_auth.py
"""
import pytest
from httpx import AsyncClient
from models import User
from services.core.auth_service import hash_password

@pytest.mark.integration
async def test_register_success(client: AsyncClient):
    """测试用户注册"""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "language": "zh"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["email_verified"] is False


@pytest.mark.integration
async def test_login_success(client: AsyncClient, db_session):
    """测试用户登录"""
    # 创建测试用户
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    # 测试登录
    response = await client.post(
        "/api/auth/login",
        data={  # OAuth2 使用 form data
            "username": "test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.integration
async def test_protected_route(client: AsyncClient):
    """测试受保护的路由"""
    # 无 token 访问
    response = await client.get("/api/auth/me")
    assert response.status_code == 401

    # 有 token 访问
    token = "your_test_token_here"
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
```

### 服务层测试示例

```python
"""
tests/test_services/test_export_service.py
"""
import pytest
from sqlmodel import Session
from models import File, Project, User
from services.features.export_service import export_drafts_to_txt

@pytest.fixture
def test_user(db_session: Session):
    """创建测试用户"""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        email_verified=True,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project(db_session: Session, test_user):
    """创建测试项目"""
    project = Project(
        name="Test Project",
        description="Test description",
        user_id=test_user.id
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.mark.unit
def test_export_single_draft(db_session: Session, test_project):
    """测试导出单个草稿"""
    # 创建草稿文件
    draft = File(
        title="第一章",
        content="这是第一章的内容",
        file_type="draft",
        project_id=test_project.id,
        order=1
    )
    db_session.add(draft)
    db_session.commit()

    # 测试导出
    result = export_drafts_to_txt(db_session, test_project.id)

    assert "第一章" in result
    assert "这是第一章的内容" in result
```

### 模型测试示例

```python
"""
tests/test_models/test_entities.py
"""
import pytest
from sqlmodel import Session
from models import User, Project
from sqlalchemy import select

@pytest.mark.unit
def test_user_model_fields(db_session: Session):
    """测试 User 模型字段验证"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password_123",
        is_active=True,
        email_verified=True
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # 验证所有字段
    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None


@pytest.mark.unit
def test_user_unique_email(db_session: Session):
    """测试邮箱唯一约束"""
    # 第一个用户
    user1 = User(
        username="user1",
        email="duplicate@example.com",
        hashed_password="password1"
    )
    db_session.add(user1)
    db_session.commit()

    # 第二个用户（相同邮箱）
    user2 = User(
        username="user2",
        email="duplicate@example.com",
        hashed_password="password2"
    )
    db_session.add(user2)

    # 应该抛出异常
    with pytest.raises(Exception):  # IntegrityError
        db_session.commit()


@pytest.mark.unit
def test_user_project_relationship(db_session: Session):
    """测试用户-项目关系"""
    # 创建用户
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed"
    )
    db_session.add(user)
    db_session.commit()

    # 创建项目
    project = Project(
        name="Test Project",
        user_id=user.id
    )
    db_session.add(project)
    db_session.commit()

    # 验证关系
    assert project.user_id == user.id
    assert project.user.username == "testuser"
```

## 最佳实践

### 1. 测试隔离

每个测试应该独立，不依赖其他测试的状态：

```python
# ❌ 不好：依赖测试顺序
def test_step_1():
    global.user = create_user()

def test_step_2():
    assert global.user is not None

# ✅ 好：每个测试独立
def test_create_user(db_session: Session):
    user = create_user(db_session)
    assert user.id is not None

def test_query_user(db_session: Session):
    user = create_user(db_session)
    found = db_session.get(User, user.id)
    assert found is not None
```

### 2. 使用唯一测试数据

避免 UNIQUE 约束冲突：

```python
# ❌ 不好：可能冲突
def test_1():
    User(username="test", email="test@example.com")

def test_2():
    User(username="test", email="test@example.com")  # 冲突!

# ✅ 好：使用唯一数据
def test_1():
    User(username="user1", email="user1@example.com")

def test_2():
    User(username="user2", email="user2@example.com")
```

### 3. 测试命名

使用描述性的测试名称：

```python
# ❌ 不好
def test_1():
    pass

# ✅ 好
def test_user_registration_with_duplicate_email_returns_400():
    pass
```

### 4. AAA 模式

Arrange-Act-Assert 模式：

```python
def test_user_update(db_session: Session):
    # Arrange: 准备测试数据
    user = create_user(db_session, username="oldname")

    # Act: 执行测试操作
    user.username = "newname"
    db_session.commit()

    # Assert: 验证结果
    db_session.refresh(user)
    assert user.username == "newname"
```

### 5. 测试边界情况

```python
@pytest.mark.unit
def test_delete_nonexistent_file(db_session: Session):
    """测试删除不存在的文件"""
    with pytest.raises(Exception):
        delete_file(db_session, file_id=99999)

@pytest.mark.unit
def test_create_file_with_empty_title(db_session: Session):
    """测试创建空标题文件"""
    with pytest.raises(ValidationError):
        File(title="", content="content")
```

### 6. 使用 Fixture 复用代码

```python
# ❌ 不好：重复代码
def test_1():
    user = User(username="test", email="test@example.com")
    db_session.add(user)
    db_session.commit()

def test_2():
    user = User(username="test2", email="test2@example.com")
    db_session.add(user)
    db_session.commit()

# ✅ 好：使用 fixture
@pytest.fixture
def test_user(db_session: Session):
    def _create(username, email):
        user = User(username=username, email=email)
        db_session.add(user)
        db_session.commit()
        return user
    return _create
```

### 7. 异步测试

使用 `@pytest.mark.asyncio` 和 `async/await`：

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_endpoint(client: AsyncClient):
    response = await client.get("/api/projects")
    assert response.status_code == 200
```

### 8. 密码和敏感数据测试

```python
# ✅ 好：使用 hash_password
from services.core.auth_service import hash_password

def test_user_password():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed)

# ❌ 不好：硬编码密码
assert user.hashed_password == "plaintext_password"
```

## 调试测试

### 查看输出

```bash
# 显示 print 输出
pytest -s

# 显示详细输出
pytest -vv

# 只显示失败的测试详情
pytest --tb=short
```

### 停在第一个失败

```bash
pytest -x
```

### 进入调试器

```python
def test_something():
    import pdb; pdb.set_trace()
    # 测试代码
```

或使用 pytest 的断点：

```bash
pytest --pdb
```

## 覆盖率报告

### 生成覆盖率报告

```bash
# HTML 报告
pytest --cov=. --cov-report=html
open htmlcov/index.html

# 终端报告
pytest --cov=. --cov-report=term

# XML 报告（用于 CI）
pytest --cov=. --cov-report=xml
```

### 覆盖率目标

- **整体覆盖率**: 目标 > 80%
- **核心模块**: 目标 > 90%
- **API 路由**: 目标 > 85%

## 常见问题

### 1. 测试数据库连接错误

确保使用 `db_session` fixture 而不是创建新的数据库连接。

### 2. 异步测试失败

确保使用 `@pytest.mark.asyncio` 和 `async/await`。

### 3. Mock 不生效

确保 mock 的路径与实际导入路径一致：

```python
# ❌ 不好
mocker.patch("module.Class", ...)

# ✅ 好
mocker.patch("actual.import.path.module.Class", ...)
```

### 4. 测试间数据污染

每个测试后 `db_session` 会自动清理，但如果使用原生 SQL 或其他 session，需要手动清理。

## 更多资源

- [Pytest 文档](https://docs.pytest.org/)
- [FastAPI 测试文档](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLModel 文档](https://sqlmodel.tiangolo.com/)
- [项目 CLAUDE.md](../../CLAUDE.md)
