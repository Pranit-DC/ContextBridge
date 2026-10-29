"""Two fixed synthetic requests, isolated so the service can enforce a hard deadline.

Credentials enter the child through a private stdin pipe, never argv, environment or files.
Only fixed progress/outcome enums are written to stdout. No provider body is printed/logged.
"""

import json
import math
import os
import subprocess
import sys
import time

import httpx

from contextbridge.inspection.provider_settings import GROQ_MODEL, SettingsError

STATUSES = {
    "started",
    "ok",
    "authentication_failed",
    "timeout",
    "rate_limited",
    "unavailable",
    "invalid_response",
}


def run_probe(record, emit, *, transport=None, deadline=None):
    deadline = time.monotonic() + 10 if deadline is None else deadline
    requests = [
        (
            "groq",
            "https://api.groq.com/openai/v1/chat/completions",
            record.groq_key,
            {
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": "Reply OK."}],
                "max_completion_tokens": 32,
                "include_reasoning": False,
                "reasoning_effort": "low",
            },
        ),
        (
            "cloudflare",
            f"https://api.cloudflare.com/client/v4/accounts/{record.cloudflare_account_id}/ai/v1/embeddings",
            record.cloudflare_key,
            {
                "model": "@cf/qwen/qwen3-embedding-0.6b",
                "input": ["ContextBridge connectivity check."],
                "encoding_format": "float",
            },
        ),
    ]
    for provider, url, credential, body in requests:
        if time.monotonic() >= deadline:
            break
        emit(provider, "started")
        status = "unavailable"
        try:
            with httpx.Client(
                transport=transport,
                timeout=min(5, max(0.001, deadline - time.monotonic())),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST",
                    url,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {credential.get_secret_value()}",
                        "Accept-Encoding": "identity",
                    },
                ) as response:
                    if response.status_code in (401, 403):
                        status = "authentication_failed"
                    elif response.status_code == 429:
                        status = "rate_limited"
                    elif response.status_code in (408, 504):
                        status = "timeout"
                    elif response.status_code >= 500:
                        status = "unavailable"
                    elif (
                        not response.is_success
                        or response.headers.get("content-encoding", "identity") != "identity"
                    ):
                        status = "invalid_response"
                    else:
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            if len(raw) + len(chunk) > 2_097_152 or time.monotonic() >= deadline:
                                raise ValueError
                            raw.extend(chunk)
                        for key in (record.groq_key, record.cloudflare_key):
                            if key.get_secret_value().encode() in raw:
                                raise ValueError
                        value = json.loads(raw)
                        if provider == "groq":
                            text = value["choices"][0]["message"]["content"]
                            if not isinstance(text, str) or not text.strip():
                                raise ValueError
                        else:
                            data = value["data"]
                            vector = data[0]["embedding"]
                            if (
                                len(data) != 1
                                or data[0]["index"] != 0
                                or len(vector) != 1024
                                or any(
                                    type(v) not in (int, float) or not math.isfinite(v)
                                    for v in vector
                                )
                            ):
                                raise ValueError
                        status = "ok"
        except httpx.TimeoutException:
            status = "timeout"
        except httpx.HTTPError:
            status = "unavailable"
        except Exception:
            status = "invalid_response"
        emit(provider, status)
        if status != "ok":
            break


def parse_events(raw, *, timed_out=False):
    state = {"groq": "not_attempted", "cloudflare": "not_attempted"}
    try:
        if len(raw) > 2048:
            raise ValueError
        for line in raw.splitlines():
            event = json.loads(line)
            if set(event) != {"provider", "status"}:
                raise ValueError
            provider, status = event["provider"], event["status"]
            if provider not in state or status not in STATUSES:
                raise ValueError
            if provider == "cloudflare" and state["groq"] != "ok":
                raise ValueError
            if status == "started":
                if state[provider] != "not_attempted":
                    raise ValueError
            elif state[provider] != "started":
                raise ValueError
            state[provider] = status
        if state["groq"] == "not_attempted":
            raise ValueError
        for provider in state:
            if state[provider] == "started":
                state[provider] = "timeout" if timed_out else "unavailable"
        if state["groq"] == "ok" and state["cloudflare"] == "not_attempted":
            # Deadline/child failure between requests: do not invent a second request.
            raise SettingsError("timeout" if timed_out else "unavailable")
        return {**state, "calls": sum(value != "not_attempted" for value in state.values())}
    except SettingsError:
        raise
    except Exception:
        pass
    raise SettingsError("unavailable") from None


def execute_probe(record, *, deadline, command=None):
    payload = json.dumps(
        {
            "owner": "probe",
            "cloudflare_account_id": record.cloudflare_account_id,
            "groq_key": record.groq_key.get_secret_value(),
            "cloudflare_key": record.cloudflare_key.get_secret_value(),
        }
    ).encode()
    # Inherit OS essentials only; provider/API/database credentials never enter child env.
    environment = {
        name: os.environ[name]
        for name in ("SystemRoot", "WINDIR", "PATH", "TMP", "TEMP")
        if name in os.environ
    }
    process = subprocess.Popen(
        command or [sys.executable, "-m", "contextbridge.provider_probe"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    timed_out = False
    try:
        raw, _ = process.communicate(payload, timeout=max(0.001, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        raw, _ = process.communicate()
    return parse_events(raw, timed_out=timed_out)


def main():
    from contextbridge.provider_configuration import PrivateConfiguration

    try:
        record = PrivateConfiguration.model_validate_json(sys.stdin.buffer.read(65_537))
        if not record.groq_key or not record.cloudflare_key or not record.cloudflare_account_id:
            return 1

        def emit(provider, status):
            print(json.dumps({"provider": provider, "status": status}), flush=True)

        run_probe(record, emit)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
