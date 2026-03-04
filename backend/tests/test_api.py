"""
测试 API 端点
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_read_root():
    """测试根路径"""
    response = client.get("/")
    assert response.status_code == 200


def test_health_check():
    """测试健康检查端点"""
    response = client.get("/api/health")
    if response.status_code == 200:
        assert response.json() is not None


def test_api_docs_available():
    """测试 API 文档可访问"""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_schema():
    """测试 OpenAPI schema"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "openapi" in response.json()
