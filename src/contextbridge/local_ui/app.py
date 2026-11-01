"""A calm local workspace, reusing the existing API-backed memory controls."""

import hashlib
import os
from uuid import uuid4

import streamlit as st

from contextbridge.inspection import app as memory_ui
from contextbridge.local_ui.settings import FileSettings, SettingsStore
from contextbridge.local_ui.settings_page import render_settings

STYLE = """
<style>
  .stApp { background: #fcfcfd; color: #172b3a; }
  [data-testid="stSidebar"] { background: #f3f6f8; border-right: 1px solid #e3e9ed; }
  .block-container { max-width: 1120px; padding-top: 2.6rem; padding-bottom: 4rem; }
  h1 { font-size: 2rem !important; letter-spacing: -0.035em; font-weight: 650 !important; }
  h2 { font-size: 1.35rem !important; letter-spacing: -0.02em; }
  h3 { font-size: 1.05rem !important; }
  [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
  [data-testid="stText"] { white-space: pre-wrap; overflow-wrap: anywhere; }
  [data-testid="stCaptionContainer"] { color: #52616b !important; }
  .st-key-providers_grid [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important; gap: 1.25rem !important;
  }
  .st-key-providers_grid [data-testid="stColumn"] {
    flex: 1 1 260px !important; min-width: min(100%, 260px); width: auto !important;
  }
  button:focus-visible, input:focus-visible, textarea:focus-visible {
    outline: 3px solid #16828d !important; outline-offset: 3px;
  }
  @media (max-width: 700px) { .block-container { padding-top: 3.5rem; } }
</style>
"""


def local_defaults():
    path = os.environ.get("CONTEXTBRIDGE_LOCAL_ENV_FILE")
    if path:
        try:
            _, _, values = SettingsStore(path).read()
            return FileSettings(
                **{
                    name: values["CONTEXTBRIDGE_" + name.upper()]
                    for name in FileSettings.model_fields
                    if "CONTEXTBRIDGE_" + name.upper() in values
                }
            )
        except Exception:
            pass
    return None


def connection():
    defaults = local_defaults()
    with st.sidebar:
        st.markdown("### ContextBridge")
        st.caption("YOUR MEMORY WORKSPACE")
        project = st.text_input(
            "Project",
            key="workspace_project",
            value=os.environ.get("CONTEXTBRIDGE_PROJECT_ID")
            or (
                defaults.capture_project_id
                if defaults and defaults.capture_project_id
                else "contextbridge"
            ),
        )
        page = st.radio(
            "Workspace",
            ["Memories", "Add memory", "Activity", "Settings"],
            index=3 if os.environ.get("CONTEXTBRIDGE_LOCAL_START_SETTINGS") == "true" else 0,
            key="workspace_page",
        )
        with st.expander("Service connection"):
            url = st.text_input(
                "Memory service address",
                value=os.environ.get("CONTEXTBRIDGE_API_URL", "http://127.0.0.1:8000"),
                key="workspace_url",
            )
            typed = st.text_input(
                "Service access token",
                type="password",
                key="workspace_token",
                help="Connects to the service. Manage provider keys in Settings.",
            )
            token = typed or (
                defaults.api_token.get_secret_value()
                if defaults
                else os.environ.get("CONTEXTBRIDGE_API_TOKEN", "")
            )
            st.caption(
                "Using the local access token."
                if token and not typed
                else "Kept only in this browser session."
            )
        st.caption("Local-first · One shared memory service")
    if not token or not project.strip():
        return page, None, project
    try:
        binding = hashlib.sha256(f"{url}\0{token}\0{project}".encode()).hexdigest()
        if st.session_state.get("connection_binding") != binding:
            for key in list(st.session_state):
                if not key.startswith(("workspace_", "cfg_")) and key != "make_controller":
                    del st.session_state[key]
            st.session_state["connection_binding"] = binding
        controller = st.session_state.get("make_controller", memory_ui.build_controller)(
            url, token, project
        )
        controller.session = st.session_state.setdefault(
            "viewer_session", f"workspace-{uuid4().hex}"
        )
        return page, controller, project
    except ValueError:
        return page, None, project


def render():
    st.set_page_config(page_title="ContextBridge · Memory workspace", page_icon="◈", layout="wide")
    st.html(STYLE)
    page, controller, project = connection()
    memory_ui.preserve_user_drafts()
    if page == "Settings":
        render_settings()
        return
    st.caption("PROJECT MEMORY")
    st.title(
        {
            "Memories": "Project memories",
            "Add memory": "Add a memory",
            "Activity": "Memory activity",
        }[page]
    )
    st.caption("Useful knowledge, available across conversations.")
    memory_ui.show(st.session_state.pop("flash", None))
    if controller is None:
        st.info("Start with Settings, or enter a service access token under Service connection.")
        return
    status = controller.status()
    if not status.ready:
        st.info(
            "Your memory service isn’t ready yet. Open Settings to finish setup "
            "or apply your saved configuration."
        )
        memory_ui.show(status.notice)
        return
    capabilities_result = controller.action("capabilities")
    memory_ui.show(capabilities_result.notice)
    capabilities = capabilities_result.data
    if not capabilities:
        return
    if page == "Memories":
        columns = st.columns(3)
        for column, title, value in [
            (columns[0], "Memory service", "Connected"),
            (
                columns[1],
                "AI processing",
                "Enabled" if capabilities.get("extraction_configured") else "Not enabled",
            ),
            (
                columns[2],
                "Meaning search",
                "Enabled" if capabilities.get("embeddings_configured") else "Not enabled",
            ),
        ]:
            with column, st.container(border=True):
                st.caption(title.upper())
                st.markdown(f"**{value}**")
    st.write("")
    if page == "Memories":
        section = st.segmented_control(
            "Find memories",
            ["Browse", "Search"],
            default="Browse",
            key="workspace_find",
            selection_mode="single",
        )
        if section == "Search":
            memory_ui.search_tab(controller)
        else:
            memory_ui.browse_tab(controller)
    elif page == "Add memory":
        section = st.segmented_control(
            "Add information",
            ["Save a memory", "Import conversation"],
            default="Save a memory",
            key="workspace_add",
        )
        if section == "Import conversation":
            memory_ui.import_tab(controller, capabilities)
        else:
            memory_ui.save_tab(controller, capabilities)
    else:
        memory_ui.maintenance_tab(controller, capabilities)
    selected = st.session_state.get("selected")
    if selected:
        with st.container(border=True):
            memory_ui.detail_panel(controller, selected)


if __name__ == "__main__":
    render()
