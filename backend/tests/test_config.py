"""
测试配置模块
"""
import pytest
from app.core.config import Settings


def test_settings_creation():
    """测试配置创建"""
    settings = Settings()
    assert settings is not None
    assert hasattr(settings, 'PROJECT_NAME')


def test_settings_project_name():
    """测试项目名称配置"""
    settings = Settings()
    assert settings.PROJECT_NAME == "Invoice Management API"


def test_settings_has_required_fields():
    """测试配置包含必需字段"""
    settings = Settings()
    required_fields = [
        'PROJECT_NAME',
        'API_V1_STR',
        'SECRET_KEY',
        'ALGORITHM',
        'ACCESS_TOKEN_EXPIRE_MINUTES'
    ]
    for field in required_fields:
        assert hasattr(settings, field), f"Missing required field: {field}"
