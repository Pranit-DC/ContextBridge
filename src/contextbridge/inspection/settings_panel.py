"""Supported-provider onboarding with public metadata and explicit changes only."""

import streamlit as st
from pydantic import ValidationError

from contextbridge.inspection.provider_settings import (
    CLOUDFLARE_MODEL,
    GROQ_MODEL,
    PendingSettingsClient,
    SettingsChange,
    SettingsController,
    SettingsError,
)

ACTIONS = {"Keep current key": "keep", "Use staged replacement": "replace", "Remove key": "remove"}


def provider_settings_panel():
    with st.sidebar.expander("Provider setup"):
        st.caption(
            "Local Groq and Cloudflare settings. Provider keys stay in the service. "
            "The ContextBridge access token above only connects to your memory service. "
            "Never paste model keys into the viewer."
        )
        factory = st.session_state.get("make_settings_client", PendingSettingsClient)
        try:
            controller = SettingsController(factory())
            if st.button("Load provider settings", key="settings_load"):
                st.session_state["provider_snapshot"] = controller.read()
            snapshot = st.session_state.get("provider_snapshot")
            if snapshot is None:
                if factory is PendingSettingsClient:
                    st.info(
                        "Shared service settings integration is pending. "
                        "Setup controls are unavailable."
                    )
                else:
                    st.info("Load settings to begin. Loading makes no online provider calls.")
                return
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
                "Applying settings does not enable capture or background processing."
            )
            with st.form("provider_settings"):
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
                submitted = st.form_submit_button("Apply provider settings")
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
        except ValidationError:
            st.warning("Enter a Cloudflare account ID with exactly 32 hexadecimal characters.")
        except SettingsError as error:
            st.warning(str(error))
        except Exception:
            st.warning("Settings service unavailable. Your draft is preserved.")
