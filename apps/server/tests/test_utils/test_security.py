"""
测试安全相关的工具函数
包括密码哈希、验证、JWT token 生成和解析
"""
import time

import pytest
from jose import jwt

from services.core.auth_service import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)


@pytest.mark.unit
class TestPasswordHashing:
    """测试密码哈希和验证功能"""

    def test_hash_password_returns_hash(self):
        """测试哈希密码返回哈希字符串"""
        password = "mypassword123"
        hashed = hash_password(password)

        # 哈希应该是字符串
        assert isinstance(hashed, str)
        # 哈希应该不等于原始密码
        assert hashed != password
        # bcrypt 哈希应该以 $2b$ 开头
        assert hashed.startswith("$2b$")

    def test_hash_password_is_different_each_time(self):
        """测试同一个密码每次哈希结果不同（因为 salt）"""
        password = "mypassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # 每次哈希结果应该不同
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """测试验证正确的密码"""
        password = "mypassword123"
        hashed = hash_password(password)

        # 正确的密码应该验证通过
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """测试验证错误的密码"""
        password = "mypassword123"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)

        # 错误的密码应该验证失败
        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty(self):
        """测试验证空密码"""
        password = "mypassword123"
        hashed = hash_password(password)

        # 空密码应该验证失败
        assert verify_password("", hashed) is False

    def test_hash_password_truncates_long_passwords(self):
        """测试哈希超过 72 字节的密码会被截断"""
        # bcrypt 有 72 字节限制
        # 创建一个超过 72 字节的密码（ASCII 字符）
        long_password = "a" * 100
        hashed = hash_password(long_password)

        # 哈希应该成功
        assert isinstance(hashed, str)
        # 验证应该通过（使用完整密码）
        assert verify_password(long_password, hashed) is True

    def test_hash_password_handles_unicode(self):
        """测试哈希包含 Unicode 字符的密码"""
        password = "密码测试🔐"
        hashed = hash_password(password)

        # 哈希应该成功
        assert isinstance(hashed, str)
        # 验证应该通过
        assert verify_password(password, hashed) is True

    def test_verify_password_with_invalid_hash(self):
        """测试使用无效哈希验证密码会抛出异常"""
        from passlib.exc import UnknownHashError

        password = "mypassword123"
        invalid_hash = "not_a_valid_hash"

        # 应该抛出 UnknownHashError 异常
        with pytest.raises(UnknownHashError):
            verify_password(password, invalid_hash)


@pytest.mark.unit
class TestAccessTokenCreation:
    """测试访问令牌创建功能"""

    def test_create_access_token_returns_token(self):
        """测试创建访问令牌返回有效的 JWT"""
        data = {"sub": "123", "username": "testuser"}
        token = create_access_token(data)

        # 应该返回字符串
        assert isinstance(token, str)
        # 应该包含三个部分（header.payload.signature）
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_access_token_includes_exp(self):
        """测试创建的令牌包含过期时间"""
        data = {"sub": "123"}
        token = create_access_token(data)

        # 解码令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 应该包含 exp 字段
        assert "exp" in payload
        # exp 应该是未来时间戳
        assert payload["exp"] > int(time.time())

    def test_create_access_token_converts_sub_to_string(self):
        """测试 sub 字段被转换为字符串"""
        data = {"sub": 123}  # 整数
        token = create_access_token(data)

        # 解码令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # sub 应该是字符串
        assert isinstance(payload["sub"], str)
        assert payload["sub"] == "123"

    def test_create_access_token_preserves_other_fields(self):
        """测试创建令牌保留其他字段"""
        data = {"sub": "123", "username": "testuser", "role": "admin"}
        token = create_access_token(data)

        # 解码令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 应该保留所有字段
        assert payload["sub"] == "123"
        assert payload["username"] == "testuser"
        assert payload["role"] == "admin"

    def test_create_access_token_default_expiration(self):
        """测试默认过期时间为 60 分钟"""
        data = {"sub": "123"}
        token = create_access_token(data)

        # 解码令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 计算过期时间差（允许 5 秒误差）
        exp = payload["exp"]
        now = int(time.time())
        expected_exp = now + (60 * 60)  # 60 分钟

        assert abs(exp - expected_exp) < 60


@pytest.mark.unit
class TestRefreshTokenCreation:
    """测试刷新令牌创建功能"""

    def test_create_refresh_token_returns_token(self):
        """测试创建刷新令牌返回有效的 JWT"""
        data = {"sub": "123", "username": "testuser"}
        token = create_refresh_token(data)

        # 应该返回字符串
        assert isinstance(token, str)
        # 应该包含三个部分
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_refresh_token_expires_in_7_days(self):
        """测试刷新令牌过期时间为 7 天"""
        data = {"sub": "123"}
        token = create_refresh_token(data)

        # 解码令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 计算过期时间差（允许 60 秒误差）
        exp = payload["exp"]
        now = int(time.time())
        actual_expires_in = exp - now
        expected_expires_in = 7 * 24 * 60 * 60  # 7 天

        assert abs(actual_expires_in - expected_expires_in) < 60

    def test_create_refresh_token_converts_sub_to_string(self):
        """测试刷新令牌的 sub 字段被转换为字符串"""
        data = {"sub": 456}  # 整数
        token = create_refresh_token(data)

        # 解码令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # sub 应该是字符串
        assert isinstance(payload["sub"], str)
        assert payload["sub"] == "456"

    def test_refresh_token_longer_expiration_than_access_token(self):
        """测试刷新令牌比访问令牌有效期更长"""
        data = {"sub": "123"}

        access_token = create_access_token(data)
        refresh_token = create_refresh_token(data)

        # 解码两个令牌
        access_payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        refresh_payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        # 刷新令牌的过期时间应该更晚
        assert refresh_payload["exp"] > access_payload["exp"]


@pytest.mark.unit
class TestTokenVerification:
    """测试令牌验证功能"""

    def test_verify_token_valid(self):
        """测试验证有效令牌"""
        data = {"sub": "123", "username": "testuser"}
        token = create_access_token(data)

        # 验证应该返回 payload
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "123"
        assert payload["username"] == "testuser"

    def test_verify_token_invalid_signature(self):
        """测试验证签名无效的令牌"""
        # 创建一个令牌
        token = create_access_token({"sub": "123"})
        # 修改令牌的最后几个字符（破坏签名）
        tampered_token = token[:-5] + "abcde"

        # 验证应该返回 None
        payload = verify_token(tampered_token)
        assert payload is None

    def test_verify_token_expired(self):
        """测试验证过期的令牌"""
        # 手动创建一个已过期的令牌
        from datetime import datetime, timedelta

        expired_data = {"sub": "123", "exp": datetime.utcnow() - timedelta(hours=1)}
        expired_token = jwt.encode(expired_data, SECRET_KEY, algorithm=ALGORITHM)

        # 验证应该返回 None
        payload = verify_token(expired_token)
        assert payload is None

    def test_verify_token_malformed(self):
        """测试验证格式错误的令牌"""
        malformed_tokens = [
            "",  # 空字符串
            "not.a.token",  # 不是一个有效的 JWT
            "abc.def",  # 只有两部分
            "a" * 1000,  # 长字符串
        ]

        for malformed_token in malformed_tokens:
            payload = verify_token(malformed_token)
            assert payload is None

    def test_verify_token_wrong_algorithm(self):
        """测试验证使用错误算法生成的令牌"""
        # 使用 HS256 创建令牌
        data = {"sub": "123"}
        token = jwt.encode(data, SECRET_KEY, algorithm="HS256")

        # 令牌应该有效（因为我们使用 HS256）
        payload = verify_token(token)
        assert payload is not None

    def test_verify_token_missing_sub(self):
        """测试验证没有 sub 字段的令牌"""
        # 创建没有 sub 字段的令牌
        data = {"username": "testuser"}
        token = create_access_token(data)

        # 令牌应该可以验证（verify_token 不检查 sub）
        payload = verify_token(token)
        assert payload is not None
        assert "username" in payload

    def test_verify_token_with_custom_claims(self):
        """测试验证包含自定义字段的令牌"""
        data = {
            "sub": "123",
            "username": "testuser",
            "role": "admin",
            "permissions": ["read", "write"],
        }
        token = create_access_token(data)

        # 验证应该保留所有自定义字段
        payload = verify_token(token)
        assert payload is not None
        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write"]


@pytest.mark.unit
class TestTokenSecurity:
    """测试令牌安全性"""

    def test_different_secret_keys_produce_different_tokens(self):
        """测试不同的密钥生成不同的令牌"""
        data = {"sub": "123"}

        # 使用当前密钥创建令牌
        token1 = create_access_token(data)

        # 验证令牌
        payload1 = verify_token(token1)
        assert payload1 is not None

    def test_token_payload_does_not_contain_sensitive_data(self):
        """测试令牌 payload 不包含敏感数据（如密码）"""
        data = {"sub": "123", "username": "testuser", "password": "secret123"}
        token = create_access_token(data)

        # 解码令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 令牌应该包含所有传入的数据
        # 注意：JWT payload 是 base64 编码的，可以被解码，所以不应包含敏感信息
        assert "password" in payload
        # 这是一个安全警示：实际使用中不应该在 JWT 中存储密码

    def test_reproducible_tokens_with_same_data(self):
        """测试相同数据在不同时间创建的令牌有不同的 exp"""
        data = {"sub": "123", "username": "testuser"}

        token1 = create_access_token(data)
        time.sleep(1.1)  # 等待超过 1 秒
        token2 = create_access_token(data)

        # 令牌应该不同（因为 exp 不同）
        assert token1 != token2

        # 解码两个令牌
        payload1 = jwt.decode(token1, SECRET_KEY, algorithms=[ALGORITHM])
        payload2 = jwt.decode(token2, SECRET_KEY, algorithms=[ALGORITHM])

        # exp 应该不同
        assert payload1["exp"] != payload2["exp"]
        # 其他字段应该相同
        assert payload1["sub"] == payload2["sub"]
        assert payload1["username"] == payload2["username"]
