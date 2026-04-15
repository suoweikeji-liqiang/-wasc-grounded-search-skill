"""Repository `.env` loading regressions."""

from __future__ import annotations


def test_load_repo_dotenv_reads_repo_root_env_file(monkeypatch, tmp_path) -> None:
    import skill.config.env as env_config

    env_path = tmp_path / ".env"
    env_path.write_text(
        '\n'.join(
            [
                '# comment',
                'MINIMAX_KEY="dotenv-key"',
                'WASC_RETRIEVAL_MODE=fixture',
            ]
        )
        + '\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(env_config, "REPO_ROOT", tmp_path)

    environ: dict[str, str] = {}

    loaded = env_config.load_repo_dotenv(environ=environ)

    assert loaded == {
        "MINIMAX_KEY": "dotenv-key",
        "WASC_RETRIEVAL_MODE": "fixture",
    }
    assert environ == loaded


def test_load_repo_dotenv_keeps_existing_environment_values(monkeypatch, tmp_path) -> None:
    import skill.config.env as env_config

    env_path = tmp_path / ".env"
    env_path.write_text(
        '\n'.join(
            [
                'MINIMAX_KEY="dotenv-key"',
                'WASC_RETRIEVAL_MODE=fixture',
                'TAVILY_API_KEY=tvly-dotenv',
            ]
        )
        + '\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(env_config, "REPO_ROOT", tmp_path)

    environ = {
        "MINIMAX_KEY": "shell-key",
        "WASC_RETRIEVAL_MODE": "live",
    }

    loaded = env_config.load_repo_dotenv(environ=environ)

    assert loaded == {
        "MINIMAX_KEY": "shell-key",
        "WASC_RETRIEVAL_MODE": "live",
        "TAVILY_API_KEY": "tvly-dotenv",
    }
    assert environ == loaded
