"""Streamlit viewer: browse, search, inspect, correct, and permanently forget memories.

Run with ``streamlit run src/contextbridge/inspection/app.py``. Streamlit is an optional dependency
that is not in this project's manifest yet (see docs/inspection/integration-request.md).

Everything here goes through ``ViewerController`` and so through the service API; the viewer has no
database access. Service-provided text is shown with ``st.text`` only, so it is never interpreted as
HTML or markdown. No Streamlit cache is used, and nothing private is written to a log. Page state
holds only the selected memory ID, the version the user opened, and the user's own settings.

Streamlit re-runs this script on every click. A correction must use the version the user *opened*,
not whatever is newest on this run, so that version is pinned in session state; if the memory has
moved on, the form stays disabled until the user explicitly reloads it.
"""

import os

import streamlit as st

from contextbridge.inspection.client import HttpViewerClient, ViewerSettings
from contextbridge.inspection.controller import ViewerController
from contextbridge.inspection.viewmodel import DetailView, MemoryRow, Notice

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_PROJECT = "contextbridge"


def build_controller(url: str, token: str, project: str) -> ViewerController:
    """Raises ValueError for unusable settings; the message never contains them."""
    return ViewerController(HttpViewerClient(ViewerSettings(url, token), project))


def show(notice: Notice | None) -> None:
    if notice is None:
        return
    {"info": st.info, "success": st.success, "warning": st.warning, "error": st.error}[
        notice.level
    ](notice.text)


def show_rows(rows: list[MemoryRow], prefix: str) -> None:
    for row in rows:
        with st.container(border=True):
            st.text(row.text)
            st.text(f"{row.type_label} | {row.status_label} | {row.scope_label} | {row.conditions}")
            st.text(f"{row.validity} | version {row.version_number}")
            if row.uncertainty:
                st.warning(row.uncertainty)
            if st.button("Open details", key=f"{prefix}-open-{row.memory_id}"):
                select(row.memory_id)
                st.rerun()


def select(memory_id: str | None) -> None:
    st.session_state["selected"] = memory_id
    st.session_state["pinned_version"] = None  # re-pinned from the next load


def sidebar() -> ViewerController | None:
    with st.sidebar:
        st.header("Connection")
        url = st.text_input("Memory service address", value=DEFAULT_URL, key="url")
        project = st.text_input(
            "Project",
            value=os.environ.get("CONTEXTBRIDGE_PROJECT_ID", DEFAULT_PROJECT),
            key="project",
        )
        env_token = os.environ.get("CONTEXTBRIDGE_API_TOKEN", "")
        typed = st.text_input(
            "Access token", type="password", key="token", help="Kept only in this browser session."
        )
        token = typed or env_token  # an environment token is never sent to the browser
        if env_token and not typed:
            st.caption("Using the token from the environment.")
    if not project.strip() or not token:
        st.info("Enter the project and the access token in the sidebar to begin.")
        return None
    try:
        return st.session_state.get("make_controller", build_controller)(url, token, project)
    except ValueError:
        st.error(
            "The service address or settings are not valid. "
            "Use a local address such as http://127.0.0.1:8000."
        )
        return None


def browse_tab(controller: ViewerController) -> None:
    pages: list[str | None] = st.session_state.setdefault("pages", [None])
    index = min(st.session_state.setdefault("page", 0), len(pages) - 1)
    with st.spinner("Loading memories..."):
        result = controller.browse(cursor=pages[index])
    show(result.notice)
    show_rows(result.rows, "browse")
    left, middle, right = st.columns([1, 1, 4])
    if left.button("Previous page", disabled=index == 0, key="prev"):
        st.session_state["page"] = index - 1
        st.rerun()
    if right.button("Next page", disabled=not result.next_cursor, key="next"):
        del pages[index + 1 :]
        pages.append(result.next_cursor)
        st.session_state["page"] = index + 1
        st.rerun()
    middle.text(f"Page {index + 1}")


def search_tab(controller: ViewerController) -> None:
    with st.form("search"):
        text = st.text_input("Words to look for")
        include_developer = st.checkbox("Also include memories that apply to all my projects")
        key = st.text_input("Only when this condition name is set (optional)")
        value = st.text_input("...to this value (optional)")
        submitted = st.form_submit_button("Search")
    if submitted:
        st.session_state["search_request"] = {
            "text": text,
            "include_developer": include_developer,
            "conditions": {key.strip(): value.strip()} if key.strip() and value.strip() else {},
        }
    request = st.session_state.get("search_request")
    if request is None:
        st.caption("Search matches the words you type. It does not guess related meanings.")
        return
    with st.spinner("Searching..."):
        result = controller.search(
            request["text"],
            conditions=request["conditions"],
            include_developer=request["include_developer"],
        )
    show(result.notice)
    show_rows(result.rows, "search")


def detail_panel(controller: ViewerController, memory_id: str) -> None:
    st.divider()
    st.header("Memory details")
    if st.button("Close details", key="close"):
        select(None)
        st.rerun()
    with st.spinner("Loading details..."):
        result = controller.open(memory_id)
    show(result.notice)
    detail = result.detail
    if detail is None:
        return
    pinned = st.session_state.get("pinned_version")
    if pinned is None:
        st.session_state["pinned_version"] = pinned = detail.expected_version
    show_detail(detail)
    stale = detail.expected_version != pinned
    if stale:
        st.warning(
            "This memory changed after you opened it. Review the latest version above "
            "before correcting it."
        )
        if st.button("Review the latest version", key="reload"):
            st.session_state["pinned_version"] = detail.expected_version
            st.rerun()
    correction_form(controller, detail, pinned, disabled=stale)
    forget_section(controller, detail)


def show_detail(detail: DetailView) -> None:
    st.text(f"{detail.type_label} | {detail.scope_label} | {detail.conditions}")
    st.subheader(f"Current version: {detail.current.number}")
    st.text(detail.current.content)
    st.text(f"{detail.current.validity} | {detail.current.source}")
    for line in detail.relationships:
        st.text(line)
    st.subheader("Evidence and history")
    for version in detail.history:
        title = f"Version {version.number}: {version.status_label}"
        with st.expander(title, expanded=version.is_current):
            st.text(version.content)
            st.text(f"{version.validity} | {version.recorded}")
            st.text(version.source)
            st.text("Evidence:")
            st.text(version.evidence)


def correction_form(
    controller: ViewerController, detail: DetailView, pinned: int, *, disabled: bool
) -> None:
    st.subheader("Correct this memory")
    st.caption("The earlier version is kept in the history.")
    suffix = f"{detail.memory_id}-{pinned}"
    # After a stale attempt the user's own text is restored, so it is never lost.
    draft = st.session_state.pop("draft", None) or {}
    with st.form("correct"):
        content = st.text_area(
            "Corrected text",
            value=draft.get("content", detail.current.content),
            key=f"content-{suffix}",
        )
        evidence = st.text_area(
            "Where does the correction come from?",
            value=draft.get("evidence", ""),
            key=f"evidence-{suffix}",
        )
        submitted = st.form_submit_button("Save correction", disabled=disabled)
    if not submitted:
        return
    result = controller.correct(detail.memory_id, pinned, content, evidence)
    if result.ok:
        st.session_state["pinned_version"] = None
        st.session_state["flash"] = result.notice
        st.rerun()
    if result.conflict:
        # Nothing was saved. Show the newer version with the user's draft; never retry silently.
        st.session_state["pinned_version"] = None
        st.session_state["flash"] = result.notice
        st.session_state["draft"] = {
            "content": result.draft_content,
            "evidence": result.draft_evidence,
        }
        st.rerun()
    show(result.notice)


def forget_section(controller: ViewerController, detail: DetailView) -> None:
    st.subheader("Delete this memory")
    confirmed = st.checkbox(
        "I understand this permanently deletes the memory, its history, and its evidence.",
        key=f"confirm-{detail.memory_id}",
    )
    if st.button("Delete permanently", key="forget"):
        result = controller.forget(detail.memory_id, confirmed)
        if result.ok:
            select(None)
            st.session_state["flash"] = result.notice
            st.session_state["pages"], st.session_state["page"] = [None], 0
            st.rerun()
        show(result.notice)


def render() -> None:
    st.set_page_config(page_title="ContextBridge memory viewer", layout="wide")
    st.title("ContextBridge memory viewer")
    controller = sidebar()
    show(st.session_state.pop("flash", None))
    if controller is None:
        return
    status = controller.status()
    if not status.ready:
        show(status.notice)
        return
    browse, search = st.tabs(["Browse", "Search"])
    with browse:
        browse_tab(controller)
    with search:
        search_tab(controller)
    selected = st.session_state.get("selected")
    if selected:
        detail_panel(controller, selected)


if __name__ == "__main__":
    render()
