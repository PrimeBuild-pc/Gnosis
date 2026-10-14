"""Real Compose parser, synthetic files only: no daemon, build, pull or containers."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from gnosis.envfile import read_env, write_env


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker CLI not installed")
def test_compose_preserves_literal_credentials_and_loopback(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    compose = tmp_path / "compose.yaml"
    compose.write_text((repo / "compose.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    env = tmp_path / ".env"
    secret = "${GNOSIS_TEST_MISSING:?blocked} #\"unclosed\\end'$$"
    write_env(
        env,
        {
            "POSTGRES_PASSWORD": "fixture-password",
            "DATABASE_URL": "postgresql://gnosis:fixture-password@db:5432/gnosis",
            "GNOSIS_PASSWORD": secret,
        },
    )
    assert read_env(env)["GNOSIS_PASSWORD"] == secret
    base = ["docker", "compose", "--env-file", str(env), "-f", str(compose), "config"]
    version = subprocess.run(
        ["docker", "compose", "version"], capture_output=True, timeout=15, check=False
    )
    if version.returncode:
        pytest.skip("Compose plugin not installed")
    # cwd is isolated: never implicitly loads the repository's real .env.
    project = subprocess.run(
        base + ["--environment"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    values = dict(line.split("=", 1) for line in project.stdout.splitlines() if "=" in line)
    assert values["GNOSIS_PASSWORD"] == secret
    rendered = subprocess.run(
        base + ["--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    config = json.loads(rendered.stdout)
    for service in ("web", "worker"):
        # config escapes dollars for a reloadable representation; container values are literal.
        assert (
            config["services"][service]["environment"]["GNOSIS_PASSWORD"].replace("$$", "$")
            == secret
        )
    assert config["services"]["web"]["ports"][0]["host_ip"] == "127.0.0.1"
    assert "ports" not in config["services"]["db"]
    # The entrypoint's temporary Unix-socket server is not application-ready.
    assert config["services"]["db"]["healthcheck"]["test"] == [
        "CMD-SHELL",
        "pg_isready -h 127.0.0.1 -U gnosis -d gnosis",
    ]
