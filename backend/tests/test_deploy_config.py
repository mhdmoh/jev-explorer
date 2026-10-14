"""Deployment identity and port mapping stay aligned with the single image."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_deploy_example_uses_the_jev_explorer_identity() -> None:
    example = _text("scripts/deploy.config.example")
    assert "PROJECT_NAME=jev-explorer" in example
    assert "DOMAIN=jev-explorer.mhdmoh.com" in example
    assert "HOST_PORT=8510" in example
    assert "CONTAINER_PORT=8000" in example
    assert "agentguard.mhdmoh.com" not in example
    assert "CONTAINER_PORT=8501" not in example


def test_deploy_script_builds_the_root_image_and_preserves_legacy_rollback() -> None:
    script = _text("scripts/deploy-production.sh")
    assert 'PROJECT_NAME="${PROJECT_NAME:-jev-explorer}"' in script
    assert 'CONTAINER_PORT="${CONTAINER_PORT:-8000}"' in script
    assert 'HOST_PORT="${HOST_PORT:-8510}"' in script
    assert "-f Dockerfile" in script
    assert '"${REPO_ROOT}/backend"' not in script
    assert "127.0.0.1:${HOST_PORT}:${CONTAINER_PORT}" in script
    assert "LEGACY_CONTAINER_NAME" in script
    assert "agentguard-production" in script
    assert "docker start" in script
    assert "docker rm -f '${LEGACY_CONTAINER_NAME}'" not in script
    assert "CUTOVER_STARTED" in script
    env_check = script.index("test -s '${REMOTE_ENV_FILE}'")
    legacy_stop = script.index("docker stop '${LEGACY_CONTAINER_NAME}'")
    assert env_check < legacy_stop
    assert "/health" in script
    assert 'id="root"' in script
    assert "npm test" in script
    assert "uv run pytest" in script
