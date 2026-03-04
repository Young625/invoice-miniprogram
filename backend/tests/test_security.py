"""
测试安全模块
"""
import pytest
from app.core.security import create_access_token, verify_password, get_password_hash


def test_password_hashing():
    """测试密码哈希"""
    password = "testpassword123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token():
    """测试创建访问令牌"""
    data = {"sub": "test@example.com"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_password_hash_different_each_time():
    """测试相同密码每次哈希结果不同（因为有盐值）"""
    password = "testpassword123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True
