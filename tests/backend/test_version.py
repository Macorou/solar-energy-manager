import json
import tomllib
from pathlib import Path
from fastapi.testclient import TestClient
from app import VERSION
from app.main import create_app
from app.settings import RuntimeSettings

ROOT = Path(__file__).resolve().parents[2]


def test_single_version_matches_packaging_files():
    assert tomllib.loads((ROOT / 'backend/pyproject.toml').read_text(encoding='utf-8'))['project']['version'] == VERSION
    assert json.loads((ROOT / 'frontend/package.json').read_text(encoding='utf-8'))['version'] == VERSION
    assert f'SEM_VERSION:-{VERSION}' in (ROOT / 'compose.yaml').read_text(encoding='utf-8')


def test_health_and_openapi_report_the_version(tmp_path):
    with TestClient(create_app(RuntimeSettings(data_dir=tmp_path, start_runtime=False))) as client:
        assert client.get('/api/v1/health/live').json()['version'] == VERSION
        assert client.get('/openapi.json').json()['info']['version'] == VERSION
