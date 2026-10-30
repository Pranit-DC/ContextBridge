"""Minimal progressive-disclosure settings; entered keys are cleared after each submission."""

import os
from pathlib import Path

import streamlit as st

from contextbridge.local_ui.actions import applied, apply_services, check_provider
from contextbridge.local_ui.settings import KeyChange, Preferences, SettingsError, SettingsStore

MODEL_NAMES = {
    "openai/gpt-oss-120b": "GPT OSS 120B",
    "openai/gpt-oss-20b": "GPT OSS 20B",
    "qwen/qwen3.8-27b": "Qwen 27B",
}


def key_input(provider, configured):
    st.caption("Key saved · value hidden" if configured else "No key saved")
    with st.expander("Manage key" if configured else "Add key", expanded=not configured):
        choices = ["Keep saved key", "Replace key", "Remove key"] if configured else ["Add key"]
        action = st.selectbox(
            f"{provider.title()} key action", choices, key=f"cfg_{provider}_action"
        )
        secret = st.text_input(
            f"{provider.title()} {'API key' if provider == 'groq' else 'API token'}",
            type="password",
            key=f"cfg_{provider}_secret",
            help="Stored in the private local settings file. Never displayed after saving.",
        )
        st.caption(
            "Leave blank to keep an existing key. Removing a key also disables that provider."
        )
    return KeyChange(
        action="remove"
        if action == "Remove key"
        else "replace"
        if action in ("Add key", "Replace key") and secret
        else "keep",
        value=secret or None,
    )


def render_settings(*, store=None, root=None):
    path = os.environ.get("CONTEXTBRIDGE_LOCAL_ENV_FILE")
    store = store or (SettingsStore(path) if path else None)
    root = root or Path(__file__).resolve().parents[3]
    st.title("Settings")
    st.caption("Configure your providers once. Keep memory controls simple.")
    if store is None:
        st.info("Open the local setup launcher to configure this installation.")
        st.code("uv run python scripts/setup_ui.py", language="bash")
        return
    try:
        snapshot = store.snapshot()
    except (SettingsError, OSError):
        st.error("Local settings are unavailable. Run setup or check file access.")
        return
    if st.session_state.pop("cfg_clear_keys", False):
        for name in ("cfg_groq_secret", "cfg_cloudflare_secret"):
            st.session_state[name] = ""
    if st.session_state.pop("cfg_reset_widgets", False):
        for key in list(st.session_state):
            if key.startswith("cfg_") and key not in ("cfg_revision", "cfg_flash"):
                del st.session_state[key]
    if st.session_state.pop("cfg_clear_test_consent", False):
        st.session_state["cfg_test_consent"] = False
    flash = st.session_state.pop("cfg_flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])
    if store.read()[2].get("CONTEXTBRIDGE_MANAGED_CREDENTIALS") == "true":
        st.info(
            "Provider settings now use secure storage. "
            "Open the new workspace with contextbridge start."
        )
        return
    if snapshot.custom_runtime:
        st.info(
            "This installation uses a custom provider. Manage its configuration outside this panel."
        )
        return
    revision = st.session_state.setdefault("cfg_revision", snapshot.revision)
    stale = revision != snapshot.revision
    if stale:
        st.warning("Settings changed in another window. Reload to review the latest values.")
    if stale and st.button("Reload saved settings", key="cfg_reload"):
        for key in list(st.session_state):
            if key.startswith("cfg_"):
                del st.session_state[key]
        st.rerun()
    prefs = snapshot.preferences
    with st.form("local_settings"):
        st.subheader("AI providers")
        st.caption("Groq + Cloudflare, the supported provider stack. Saving makes no online calls.")
        with st.container(key="providers_grid"):
            left, right = st.columns(2, gap="large")
            with left, st.container(border=True):
                st.subheader("Groq", divider=False)
                st.caption("MEMORY PROCESSING")
                processing = st.toggle(
                    "Enable AI processing", value=prefs.processing, key="cfg_processing"
                )
                groq = key_input("groq", snapshot.groq_key_configured)
                models = list(MODEL_NAMES)
                model = st.selectbox(
                    "Processing model",
                    models,
                    index=models.index(prefs.groq_model),
                    format_func=MODEL_NAMES.get,
                    key="cfg_model",
                )
                free = st.checkbox(
                    "I confirm this Groq account is on the Free plan",
                    value=prefs.groq_free_confirmed,
                    key="cfg_free",
                )
            with right, st.container(border=True):
                st.subheader("Cloudflare", divider=False)
                st.caption("MEANING SEARCH")
                meaning = st.toggle(
                    "Enable meaning search", value=prefs.meaning_search, key="cfg_meaning"
                )
                cloud = key_input("cloudflare", snapshot.cloudflare_key_configured)
                account = st.text_input(
                    "Cloudflare account ID",
                    value=prefs.cloudflare_account,
                    key="cfg_account",
                    max_chars=32,
                    help="The 32-character account ID, separate from the API token.",
                )
                st.caption("Qwen3 Embedding · 1024 dimensions")
        with st.expander("Memory & processing preferences"):
            st.caption(
                "Applies to this installation. Automatic host capture requires a separate opt-in."
            )
            project = st.text_input("Processing project", value=prefs.project, key="cfg_project")
            grouping = st.toggle(
                "Group nearby interactions", value=prefs.grouping, key="cfg_grouping"
            )
            evidence_v2 = st.toggle(
                "Combine imported turns with original timezones",
                value=prefs.evidence_v2,
                key="cfg_evidence_v2",
                help="Enable explicit V2 evidence bundles. Requires AI processing. "
                "Each source retains its own date, timezone and quoted evidence.",
            )
            idle = st.number_input(
                "Wait after the last turn (seconds)",
                min_value=1,
                max_value=300,
                value=prefs.idle_seconds,
                key="cfg_idle",
            )
            events = st.number_input(
                "Maximum interactions per group",
                min_value=1,
                max_value=20,
                value=prefs.group_events,
                key="cfg_events",
            )
            periods = sorted({3600, 86400, 604800, 2592000, prefs.retention_seconds})
            retention = st.selectbox(
                "Raw interaction retention",
                periods,
                index=periods.index(prefs.retention_seconds),
                format_func=lambda v: {
                    3600: "1 hour",
                    86400: "24 hours",
                    604800: "7 days",
                    2592000: "30 days",
                }.get(v, f"{v} seconds (current)"),
                key="cfg_retention",
            )
            consolidation = st.toggle(
                "Consolidate compatible memories in the background",
                value=prefs.consolidation,
                key="cfg_consolidation",
                help="At most one compatible batch every 15 minutes. Requires AI processing.",
            )
            tokens = st.number_input(
                "Daily processing token ceiling",
                min_value=128,
                max_value=50000,
                value=prefs.daily_tokens,
                key="cfg_tokens",
            )
        st.caption(
            "Keys stay in the private local settings file. The service access token is separate."
        )
        submitted = st.form_submit_button("Save settings", type="primary", disabled=stale)
    if submitted:
        try:
            preferences = Preferences(
                project=project,
                processing=processing,
                meaning_search=meaning,
                groq_model=model,
                groq_free_confirmed=free,
                cloudflare_account=account.strip(),
                grouping=grouping,
                evidence_v2=evidence_v2,
                idle_seconds=idle,
                group_events=events,
                retention_seconds=retention,
                consolidation=consolidation,
                daily_tokens=tokens,
            )
            saved = store.save(revision, preferences, groq, cloud)
            st.session_state["cfg_revision"] = saved.revision
            st.session_state["cfg_reset_widgets"] = True
            st.session_state["cfg_flash"] = (
                "success",
                "Settings saved locally. Apply them below when you’re ready.",
            )
        except SettingsError as error:
            st.session_state["cfg_flash"] = ("warning", str(error))
        except (ValueError, OSError):
            st.session_state["cfg_flash"] = (
                "error",
                "Settings were not saved. Check the fields and local file permissions.",
            )
        st.session_state["cfg_clear_keys"] = True
        st.rerun()
    with st.expander("Apply to services", expanded=not applied(store)):
        st.caption(
            "Saving does not change running services. Applying starts/restarts the API and workers."
        )
        st.caption(
            "Enabled processing may send queued interactions to providers. "
            "Memories and database volumes are kept."
        )
        permitted = os.environ.get("CONTEXTBRIDGE_LOCAL_ALLOW_RESTART") == "true"
        confirmed = st.checkbox(
            "I’m ready to restart services and use the saved processing settings",
            key="cfg_apply_confirm",
        )
        if st.button(
            "Apply settings to services",
            disabled=not permitted or not confirmed or stale,
            key="cfg_apply",
        ):
            try:
                with st.spinner("Applying settings. This may take a few minutes…"):
                    message = apply_services(store, snapshot.revision, root, confirmed=confirmed)
                st.success(message)
            except (SettingsError, OSError) as error:
                st.error(
                    str(error)
                    if isinstance(error, SettingsError)
                    else "Local services could not be updated."
                )
        if not permitted:
            st.caption("Service restart is available from the local setup launcher.")
    with st.expander("Check provider connections"):
        st.caption(
            "Each test sends one synthetic request, never your memories. "
            "Groq allows at most 512 output tokens; Cloudflare sends one short embedding input. "
            "Account quotas or charges may apply."
        )
        consent = st.checkbox("Allow this single online test", key="cfg_test_consent")
        columns = st.columns(2)
        for column, provider, configured in [
            (columns[0], "groq", snapshot.groq_key_configured),
            (columns[1], "cloudflare", snapshot.cloudflare_key_configured),
        ]:
            if column.button(
                f"Test {provider.title()}",
                disabled=not consent or not configured or stale,
                key=f"cfg_test_{provider}",
            ):
                try:
                    with st.spinner("Checking one synthetic request…"):
                        ok, message = check_provider(
                            store, provider, snapshot.revision, consent=consent
                        )
                    st.session_state["cfg_flash"] = ("success" if ok else "warning", message)
                except (SettingsError, OSError) as error:
                    st.session_state["cfg_flash"] = (
                        "warning",
                        str(error)
                        if isinstance(error, SettingsError)
                        else "The local test allowance is unavailable.",
                    )
                st.session_state["cfg_clear_test_consent"] = True
                st.rerun()
        st.caption("No retries. One-minute cooldown; at most three checks per provider per day.")
