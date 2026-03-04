# 测试文档

## 运行测试

### 安装测试依赖

```bash
pip install pytest pytest-cov pytest-asyncio httpx
```

### 运行所有测试

```bash
cd backend
pytest
```

### 运行特定测试文件

```bash
pytest tests/test_config.py
pytest tests/test_security.py
pytest tests/test_api.py
```

### 运行测试并生成覆盖率报告

```bash
pytest --cov=app --cov-report=html --cov-report=term
```

覆盖率报告将生成在 `htmlcov/` 目录中。

### 运行测试并显示详细输出

```bash
pytest -v
```

### 运行测试并显示打印输出

```bash
pytest -s
```

## 测试结构

```
tests/
├── conftest.py          # 测试配置和 fixtures
├── test_config.py       # 配置模块测试
├── test_security.py     # 安全模块测试
├── test_api.py          # API 端点测试
└── README.md            # 本文件
```

## 编写新测试

### 测试命名规范

- 测试文件：`test_*.py`
- 测试函数：`test_*`
- 测试类：`Test*`

### 示例测试

```python
def test_example():
    """测试示例"""
    result = 1 + 1
    assert result == 2
```

### 使用 fixtures

```python
@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):
    assert sample_data["key"] == "value"
```

## CI/CD 集成

测试会在以下情况自动运行：
- 推送代码到 main 或 develop 分支
- 创建 Pull Request
- 通过 GitHub Actions 自动执行

查看测试结果：https://github.com/Young625/invoice-miniprogram/actions
