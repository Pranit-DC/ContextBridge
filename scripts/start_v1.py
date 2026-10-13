"""Enable the configured hosted V1 runtime for a child process; never rewrite dotenv files."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from pydantic import SecretStr

from contextbridge.config import Settings
from contextbridge.formation.providers.config import FormationSettings

ROOT = Path(__file__).resolve().parents[1]


def environment(env_file, *, free_confirmed=False, project=None):
    formation = FormationSettings(_env_file=env_file)
    formation = formation.model_copy(
        update={
            "allow_hosted": True,
            "allow_paid": False,
            "groq_free_plan_confirmed": free_confirmed or formation.groq_free_plan_confirmed,
        }
    )
    formation.check_execution()
    if not formation.is_groq_free():
        raise ValueError("FREE_GROQ_CONFIRMATION_REQUIRED")
    settings = Settings(
        _env_file=env_file,
        formation_enabled=True,
        consolidation_enabled=True,
        **({"capture_project_id": project} if project else {}),
    )
    if settings.embedding_provider != "cloudflare" or not settings.capture_project_id:
        raise ValueError("HOSTED_V1_CONFIGURATION_REQUIRED")
    env = dict(os.environ)
    for model, prefix in ((settings, "CONTEXTBRIDGE_"), (formation, "CONTEXTBRIDGE_FORMATION_")):
        for name in type(model).model_fields:
            value = getattr(model, name)
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            elif isinstance(value, bool):
                value = str(value).lower()
            env[prefix + name.upper()] = "" if value is None else str(value)
    env["CONTEXTBRIDGE_PROJECT_ID"] = settings.capture_project_id
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--project-id")
    parser.add_argument("--free-groq-confirmed", action="store_true")
    parser.add_argument("--action", choices=("check", "start", "viewer"), default="check")
    args = parser.parse_args()
    try:
        env = environment(
            args.env_file, free_confirmed=args.free_groq_confirmed, project=args.project_id
        )
    except Exception:
        print(
            "V1 configuration unavailable. Check hosted credentials, "
            "capture project and Free-plan confirmation."
        )
        return 1
    if args.action == "check":
        print(
            "V1 configuration valid. Paid formation usage disabled. No model or database call made."
        )
        return 0
    if args.action == "start":
        command = [
            "docker",
            "compose",
            "--env-file",
            str(args.env_file),
            "--profile",
            "workers",
            "up",
            "--build",
            "--detach",
        ]
    else:
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "src/contextbridge/inspection/app.py"),
            "--server.address",
            "127.0.0.1",
        ]
    # The explicit start command can process existing buffered events in this binding.
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
