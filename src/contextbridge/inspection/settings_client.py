"""Authenticated public metadata; provider credentials never cross this boundary."""

import json

import httpx

from contextbridge.inspection.provider_settings import (
    ERRORS,
    CheckReport,
    SettingsError,
    SettingsSnapshot,
)


class HttpSettingsClient:
    def __init__(self, settings, *, transport=None):
        self.settings, self.transport = settings, transport

    def _request(self, method, path, model, payload=None):
        code = "unavailable"
        try:
            with httpx.Client(
                base_url=self.settings.origin,
                transport=self.transport,
                headers={"Authorization": f"Bearer {self.settings.token}"},
                timeout=12 if path.endswith("/check") else self.settings.timeout,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                with client.stream(method, path, json=payload) as response:
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        if len(raw) + len(chunk) > 8192:
                            raise ValueError
                        raw.extend(chunk)
                    if response.is_success:
                        return model.model_validate_json(raw)
                    if response.status_code == 401:
                        code = "unauthorized"
                    else:
                        detail = json.loads(raw).get("detail", {})
                        offered = detail.get("code") if isinstance(detail, dict) else None
                        if offered in ERRORS:
                            code = offered
        except httpx.TimeoutException:
            code = "timeout"
        except Exception:
            code = "unavailable"
        raise SettingsError(code) from None

    def read(self):
        return self._request("GET", "/v1/provider-settings", SettingsSnapshot)

    def apply(self, change):
        return self._request(
            "PUT", "/v1/provider-settings", SettingsSnapshot, change.model_dump(mode="json")
        )

    def check(self, request):
        return self._request(
            "POST", "/v1/provider-settings/check", CheckReport, request.model_dump(mode="json")
        )
