from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_prefect_worker_installs_one_pinned_prefect_version():
    requirements = (SERVER_ROOT / "requirements.txt").read_text()
    worker_dockerfile = (SERVER_ROOT / "docker" / "Dockerfile.prefect-worker").read_text()

    prefect_requirements = [
        line.strip() for line in requirements.splitlines() if line.strip().startswith("prefect")
    ]

    assert prefect_requirements == ["prefect==3.4.19"]
    assert any(line.strip().startswith("importlib-metadata") for line in requirements.splitlines())
    assert "pip install --no-cache-dir prefect" not in worker_dockerfile


def test_prefect_worker_checks_the_cli_during_image_build():
    worker_dockerfile = (SERVER_ROOT / "docker" / "Dockerfile.prefect-worker").read_text()

    assert "prefect version" in worker_dockerfile
