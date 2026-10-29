"""Supported-provider onboarding with public metadata and explicit changes only."""

import os

import streamlit as st
from pydantic import ValidationError

from contextbridge.inspection.provider_settings import (
    CLOUDFLARE_MODEL,
    ERRORS,
    GROQ_MODEL,
    VALIDATION_MESSAGES,
    SettingsChange,
    SettingsController,
    SettingsError,
    validate_settings,
)

ACTIONS = {"Keep current key": "keep", "Use staged replacement": "replace", "Remove key": "remove"}


def connected_settings_client():
    from contextbridge.inspection.client import ViewerSettings
    from contextbridge.inspection.settings_client import HttpSettingsClient

    token = st.session_state.get("token") or os.environ.get("CONTEXTBRIDGE_API_TOKEN", "")
    if not token:
        return None
    return HttpSettingsClient(
        ViewerSettings(st.session_state.get("url", "http://127.0.0.1:8000"), token)
    )


def provider_settings_panel():
    with st.sidebar.expander("Provider setup"):
        st.caption(
            "Local Groq and Cloudflare settings. Provider keys stay in the service. "
            "The ContextBridge access token above only connects to your memory service. "
            "Never paste model keys into the viewer."
        )
        factory = st.session_state.get("make_settings_client")
        try:
            client = factory() if factory is not None else connected_settings_client()
            if client is None:
                st.info("Connect with the memory service access token to load provider settings.")
                return
            controller = SettingsController(client)
            if st.button("Load provider settings", key="settings_load"):
                st.session_state["provider_snapshot"] = controller.read()
            snapshot = st.session_state.get("provider_snapshot")
            if snapshot is None:
                st.info("Load settings to begin. Loading makes no online provider calls.")
                return
            st.text(f"Settings revision: {snapshot.revision}")
            st.text(
                f"Groq key: {'configured (masked)' if snapshot.groq_key_configured else 'missing'}"
            )
            st.text(
                "Cloudflare key: "
                + ("configured (masked)" if snapshot.cloudflare_key_configured else "missing")
            )
            st.caption(
                "Replacement requires a key staged privately in the shared service. "
                "Removal disables that provider after the service applies the change. "
                "Settings apply across this developer's projects. Applying keys may resume "
                "already-enabled processing; review the service's capture binding first. "
                "Capture, consolidation and hosted-use policy switches are preserved."
            )
            # Standalone widgets preserve edited drafts across validation/check reruns.
            # Only the explicit Apply button can call the service mutation.
            with st.container(border=True):
                st.selectbox("Groq model", [GROQ_MODEL], key="provider_groq_model")
                st.selectbox(
                    "Cloudflare embedding model", [CLOUDFLARE_MODEL], key="provider_cf_model"
                )
                account = st.text_input(
                    "Cloudflare account ID",
                    value=snapshot.cloudflare_account_id,
                    key="provider_account",
                    max_chars=32,
                )
                groq_action = st.selectbox(
                    "Groq key action", list(ACTIONS), key="provider_groq_action"
                )
                cf_action = st.selectbox(
                    "Cloudflare key action", list(ACTIONS), key="provider_cf_action"
                )
                confirmed = st.checkbox(
                    "Apply these provider changes to this local service", key="provider_confirm"
                )
                submitted = st.button("Apply provider settings", key="provider_apply")
            if submitted:
                change = SettingsChange(
                    expected_revision=snapshot.revision,
                    cloudflare_account_id=account,
                    groq_key_action=ACTIONS[groq_action],
                    cloudflare_key_action=ACTIONS[cf_action],
                )
                st.session_state["provider_snapshot"] = controller.apply(
                    change, confirmed=confirmed
                )
                st.success("Provider settings applied. Reload to review before another change.")
            if st.button("Validate saved settings offline", key="provider_validate"):
                issues = validate_settings(st.session_state["provider_snapshot"])
                for issue in issues:
                    st.warning(VALIDATION_MESSAGES[issue])
                if not issues:
                    st.success(
                        "Saved configuration is complete. Credentials have not been tested online."
                    )
            connection_check(controller)
        except ValidationError:
            st.warning("Enter a Cloudflare account ID with exactly 32 hexadecimal characters.")
        except SettingsError as error:
            st.warning(ERRORS.get(error.code, ERRORS["unavailable"]))
        except Exception:
            st.warning("Settings service unavailable. Your draft is preserved.")


def connection_check(controller):
    st.caption(
        "Online check: send only 'Reply OK.' to Groq and "
        "'ContextBridge connectivity check.' to Cloudflare using service-side keys. "
        "No saved memories, evidence or drafts are sent. These providers receive the synthetic "
        "text and your account authentication; their data policies apply. "
        "This consumes account quota and may incur charges under your plan. "
        "At most two requests total, 32 Groq output tokens, a 10-second overall deadline, "
        "no retries, and stop on the first failure. This checks connectivity, not model quality. "
        "Unsaved edits are excluded. The existing hosted/free-plan policy must permit checking."
    )
    with st.container(border=True):
        consent = st.checkbox(
            "I understand the data and quota implications of this online check",
            key="provider_consent",
        )
        submitted = st.button("Run bounded online check", key="provider_check")
    if submitted:
        report = controller.check(st.session_state["provider_snapshot"], consent=consent)
        # Only validated enums/counters are rendered, never provider response text.
        st.text(f"Groq: {report.groq}; Cloudflare: {report.cloudflare}; requests: {report.calls}")
