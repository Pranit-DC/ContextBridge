"""Streamlit V1 controls; all reads and mutations go through the shared API.

Everything here goes through ``ViewerController`` and so through the service API; the viewer has no
database access. Service-provided text is shown with ``st.text`` only, so it is never interpreted as
HTML or markdown. No Streamlit cache is used, and nothing private is written to a log. Page state
holds only the selected memory ID, the version the user opened, and the user's own settings.

Streamlit re-runs this script on every click. A correction must use the version the user *opened*,
not whatever is newest on this run, so that version is pinned in session state; if the memory has
moved on, the form stays disabled until the user explicitly reloads it.
"""

import hashlib
import os
from datetime import UTC, datetime
from uuid import uuid4

import streamlit as st

from contextbridge.inspection.client import HttpViewerClient, ViewerSettings
from contextbridge.inspection.controller import ViewerController
from contextbridge.inspection.viewmodel import DetailView, MemoryRow, Notice, plain
from contextbridge.schemas import MemoryType

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
            if row.uncertainty:
                st.warning(row.uncertainty)
            with st.expander("Source & validity"):
                st.text(f"{row.validity} | version {row.version_number}")
                st.text(row.source)
            st.button(
                "Open details",
                key=f"{prefix}-open-{row.memory_id}",
                on_click=select,
                args=(row.memory_id,),
            )


def select(memory_id: str | None) -> None:
    for key in list(st.session_state):
        if key.startswith(("content-", "evidence-", "confirm-", "restore-")):
            del st.session_state[key]
    st.session_state.pop("draft", None)
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
        binding = hashlib.sha256(f"{url}\0{token}\0{project}".encode()).hexdigest()
        if st.session_state.get("connection_binding") != binding:
            for key in list(st.session_state):
                if key not in ("url", "token", "project", "make_controller"):
                    del st.session_state[key]
            st.session_state["connection_binding"] = binding
        controller = st.session_state.get("make_controller", build_controller)(url, token, project)
        controller.session = st.session_state.setdefault("viewer_session", f"viewer-{uuid4().hex}")
        return controller
    except ValueError:
        st.error(
            "The service address or settings are not valid. "
            "Use a local address such as http://127.0.0.1:8000."
        )
        return None


def browse_tab(controller: ViewerController) -> None:
    selection = st.selectbox(
        "Browse scope", ["This project", "Shared across projects"], key="browse_scope"
    )
    scope = "project" if selection == "This project" else "developer"
    if st.session_state.get("browse_scope_seen") != scope:
        st.session_state["pages"], st.session_state["page"] = [None], 0
        st.session_state["browse_scope_seen"] = scope
    pages: list[str | None] = st.session_state.setdefault("pages", [None])
    index = min(st.session_state.setdefault("page", 0), len(pages) - 1)
    with st.spinner("Loading memories..."):
        result = controller.browse(cursor=pages[index], scope=scope)
    show(result.notice)
    show_rows(result.rows, "browse")
    if not result.rows and result.notice is None:
        st.info("No memories yet. Save a confirmed statement or import a conversation to begin.")
    if index == 0 and not result.next_cursor:
        return
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
        text = st.text_input("What do you want to find?", key="search_text")
        with st.expander("Search filters"):
            include_developer = st.checkbox("Also include memories that apply to all my projects")
            key = st.text_input("Only when this condition name is set (optional)")
            value = st.text_input("...to this value (optional)")
            as_of = st.text_input(
                "At this time (optional, ISO date with timezone)", key="search_date"
            )
            more = st.checkbox("More context (up to five memories)")
        submitted = st.form_submit_button("Search", type="primary")
    if not submitted:
        st.caption(
            "Press Search to combine meaning, words and identifiers when indexing is ready. "
            "Results are refreshed only on a search; open details to inspect evidence."
        )
        return
    if bool(key.strip()) != bool(value.strip()):
        st.warning("Enter both the condition name and its value.")
        return
    with st.spinner("Searching..."):
        result = controller.retrieve(
            text,
            conditions={key.strip(): value.strip()} if key.strip() else {},
            include_developer=include_developer,
            as_of=as_of.strip() or None,
            more=more,
        )
    show(result.notice)
    show_rows(result.rows, "search")


def conditions_input(key):
    raw = st.text_area("Conditions (optional, one name=value per line)", key=key)
    values = {}
    try:
        for line in raw.splitlines():
            if not line.strip():
                continue
            name, value = line.split("=", 1)
            name, value = name.strip(), value.strip()
            if not name or not value or name in values or len(values) >= 20:
                raise ValueError
            values[name] = value
        return values
    except ValueError:
        return None


def save_tab(controller, capabilities):
    if st.session_state.pop("reset_save", False):
        for key in ("save_text", "save_evidence", "save_date", "save_conditions"):
            # Explicitly overwrite browser-bound widget state. Removing the key can
            # retain a previous client value during Streamlit's real-browser rerun.
            st.session_state[key] = ""
    request_id = st.session_state.setdefault("save_request_id", str(uuid4()))
    st.caption(
        "Save information you explicitly confirm. "
        "Background indexing makes it searchable by meaning."
    )
    with st.form("save_memory"):
        left, right = st.columns(2)
        selection = left.selectbox(
            "Applies to", ["This project", "Shared across projects"], key="save_scope"
        )
        type_ = right.selectbox("Memory type", [item.value for item in MemoryType], key="save_type")
        if selection != "This project" and not capabilities.get("developer_capture_enabled"):
            st.caption(
                "Shared memories can be saved. Their automatic indexing requires "
                "developer-wide processing to be enabled."
            )
        content = st.text_area("Memory text", key="save_text", max_chars=8000)
        evidence = st.text_area(
            "Supporting statement or tool result", key="save_evidence", max_chars=8000
        )
        with st.expander("Conditions & effective time (optional)"):
            conditions = conditions_input("save_conditions")
            effective = st.text_input(
                "Effective time (optional, ISO date with timezone)", key="save_date"
            )
        submitted = st.form_submit_button("Save memory", type="primary")
    if submitted:
        if conditions is None:
            st.session_state["save_feedback"] = Notice(
                "warning", "Use unique condition names and values, one name=value per line."
            )
            show(st.session_state["save_feedback"])
        else:
            result = controller.save(
                request_id,
                content,
                evidence,
                type_,
                conditions,
                effective.strip() or None,
                scope="project" if selection == "This project" else "developer",
            )
            st.session_state["save_feedback"] = result.notice
            show(result.notice)
            if result.ok:
                st.session_state["save_request_id"] = str(uuid4())
                st.session_state["reset_save"] = True
                select(result.data["id"])
                st.session_state["flash"] = Notice(
                    "success", "Saved. Open details to inspect its evidence and indexing status."
                )
                st.session_state["save_feedback"] = st.session_state["flash"]
                st.rerun()
    if not submitted:
        show(st.session_state.get("save_feedback"))
    if st.button("Start a new save request", key="new_save"):
        st.session_state["save_request_id"] = str(uuid4())
        st.rerun()
    st.caption(
        "After a lost response, retry the unchanged form. Changed content needs a new request."
    )


def import_tab(controller, capabilities):
    enabled = capabilities.get(
        "capture_project_id"
    ) == controller.client.project_id and capabilities.get("extraction_configured", False)
    st.caption(
        "Import only a conversation you choose to send to the online AI provider. "
        "Roles must be explicit; assistant suggestions are not authoritative evidence."
    )
    if not enabled:
        st.warning(
            "AI processing is not configured for this project. "
            "Configure providers, the capture project and workers first."
        )
    event_id = st.session_state.setdefault("import_event_id", str(uuid4()))
    st.session_state.setdefault("import_time", datetime.now(UTC).isoformat())
    with st.form("conversation"):
        input_format = st.radio(
            "Input format", ["Message list (JSON)", "My own statement"], key="import_format"
        )
        occurred = st.text_input("Conversation time (ISO date with timezone)", key="import_time")
        messages = st.text_area("Conversation or statement", key="import_messages", height=180)
        st.caption(
            "My own statement: enter your own confirmed facts, decisions or preferences in normal "
            "language. Use Message list (JSON) to preserve other speakers' roles. "
            "AI extracts useful memories; acceptance does not mean processing has finished."
        )
        with st.expander("Message list format"):
            st.code(
                '[{"message_id":"m1","role":"user","content":"Your statement here."}]',
                language="json",
            )
        submitted = st.form_submit_button("Import conversation", disabled=not enabled)
    if submitted:
        if input_format == "My own statement":
            import json

            messages = json.dumps([{"message_id": "m1", "role": "user", "content": messages}])
        result = controller.import_conversation(event_id, occurred, messages)
        show(result.notice)
        if result.ok:
            st.session_state["capture_job_id"] = result.data["job_id"]
            st.session_state["import_event_id"] = str(uuid4())
            st.success("Accepted for background processing. Check progress below.")
    if st.button("Start a new import request", key="new_import"):
        st.session_state["import_event_id"] = str(uuid4())
        st.rerun()
    st.caption(
        "Retry unchanged messages and time after a lost response; "
        "start a new request for a new conversation."
    )
    job_id = st.session_state.get("capture_job_id")
    if job_id and st.button("Check import progress", key="import_progress"):
        result = controller.action("processing", job_id)
        show(result.notice)
        if result.ok:
            st.text(f"Processing: {result.data['status']}")
            st.text(", ".join(result.data["reason_codes"]))
            if result.data["status"] == "deferred":
                st.warning(
                    "Pending: evidence or a safe decision is missing. "
                    "Review the conversation and explicitly save "
                    "a confirmed statement if appropriate."
                )
            for identifier in result.data["memory_ids"]:
                st.button(
                    "Inspect processed memory",
                    key=f"processed-{identifier}",
                    on_click=select,
                    args=(identifier,),
                )
    st.subheader("Processing activity")
    st.caption(
        "Recent imports and connected Codex messages for this project. Refresh to see progress."
    )
    if st.button("Refresh processing activity", disabled=not enabled):
        activity = controller.action("recent_processing")
        show(activity.notice)
        if activity.ok:
            if not activity.data:
                st.info("No messages have been submitted for this project yet.")
            for job in activity.data:
                with st.container(border=True):
                    st.text(f"{job['status']} | {job['updated_at']}")
                    st.text(", ".join(job["reason_codes"]))
                    if job["status"] == "succeeded" and not job["memory_ids"]:
                        st.info("Processing finished; no new memory needed saving.")
                    elif job["status"] == "deferred":
                        st.warning("Needs clarification or evidence; no confident write was made.")
                    for identifier in job["memory_ids"]:
                        st.button(
                            "Inspect saved memory",
                            key=f"activity-{job['job_id']}-{identifier}",
                            on_click=select,
                            args=(identifier,),
                        )


def maintenance_tab(controller, capabilities):
    st.subheader("Consolidation")
    st.caption(
        "Ask the existing worker to summarize up to 20 compatible current memories. "
        "Originals and evidence are preserved. An unchanged batch runs once."
    )
    with st.form("consolidate"):
        conditions = conditions_input("consolidate_conditions")
        submitted = st.form_submit_button(
            "Queue consolidation", disabled=not capabilities.get("consolidation_configured", False)
        )
    if submitted:
        if conditions is None:
            st.warning("Check the condition names and values.")
        else:
            result = controller.action(
                "consolidate",
                {
                    "scope": "project",
                    "project_id": controller.client.project_id,
                    "conditions": conditions,
                },
            )
            show(result.notice)
            if result.ok:
                st.text(
                    f"Consolidation: {result.data['status']} "
                    f"({result.data['source_count']} sources)"
                )
                if result.data["job_id"]:
                    st.session_state["consolidation_job_id"] = result.data["job_id"]
    job_id = st.session_state.get("consolidation_job_id")
    if job_id and st.button("Check consolidation progress"):
        result = controller.action("consolidation_status", job_id)
        show(result.notice)
        if result.ok:
            st.text(f"Consolidation: {result.data['status']}")
            st.text(", ".join(result.data.get("reason_codes") or []))
            for identifier in result.data.get("memory_ids") or []:
                st.button(
                    "Inspect summary",
                    key=f"summary-{identifier}",
                    on_click=select,
                    args=(identifier,),
                )
    st.subheader("Retired memories")
    selection = st.selectbox(
        "Retired scope", ["This project", "Shared across projects"], key="retired_scope"
    )
    scope = "project" if selection == "This project" else "developer"
    if st.session_state.get("retired_scope_seen") != scope:
        st.session_state.pop("retired_cursor", None)
        st.session_state["retired_scope_seen"] = scope
    cursor = st.session_state.get("retired_cursor")
    result = controller.retired(cursor, scope=scope)
    show(result.notice)
    show_rows(result.rows, "retired")
    if st.button("Next retired page", disabled=not result.next_cursor):
        st.session_state["retired_cursor"] = result.next_cursor
        st.rerun()
    if st.button("First retired page", disabled=cursor is None):
        st.session_state.pop("retired_cursor", None)
        st.rerun()


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
    if detail.derived:
        sources = controller.action("sources", memory_id)
        show(sources.notice)
        if sources.ok:
            st.subheader("Original sources for this summary")
            for record in sources.data:
                memory = record["memory"]
                version = memory["version"]
                with st.expander(f"Source version {version['number']}"):
                    st.text(plain(version["content"]))
                    st.text(plain(version["source"]["evidence"]))
                    st.button(
                        "Open original memory",
                        key=f"source-{version['id']}",
                        on_click=select,
                        args=(memory["id"],),
                    )
    indexing = controller.action("indexing", memory_id)
    show(indexing.notice)
    if indexing.ok:
        st.text(f"Meaning-search indexing: {indexing.data['status']}")
    stale = detail.expected_version != pinned
    if stale:
        st.warning(
            "This memory changed after you opened it. Review the latest version above "
            "before correcting it."
        )
        if st.button("Review the latest version", key="reload"):
            st.session_state["pinned_version"] = detail.expected_version
            st.rerun()
    lifecycle = controller.action("lifecycle", memory_id)
    show(lifecycle.notice)
    if lifecycle.ok:
        retired = lifecycle.data["retired_at"] is not None
        if retired:
            st.warning(
                "Retired: excluded from current search. Earlier evidence and history are preserved."
            )
        else:
            correction_form(controller, detail, pinned, disabled=stale)
        lifecycle_controls(controller, detail, pinned, retired, disabled=stale)
    forget_section(controller, detail)


def lifecycle_controls(controller, detail, pinned, retired, *, disabled):
    if not retired:
        st.caption("Retire stops current use and affected derived summaries while keeping history.")
        if st.button("Retire memory", disabled=disabled):
            result = controller.change_lifecycle(detail.memory_id, "retire", pinned)
            show(result.notice)
            if result.ok:
                st.session_state["pinned_version"] = None
                st.session_state["flash"] = Notice("success", "Retired. History remains available.")
                st.rerun()
        return
    with st.form("restore_memory"):
        version = st.selectbox(
            "Version to restore",
            [v.number for v in detail.history],
            key=f"restore-version-{detail.memory_id}",
        )
        evidence = st.text_area(
            "Why does this information apply again?", key=f"restore-evidence-{detail.memory_id}"
        )
        submitted = st.form_submit_button("Restore as a new version", disabled=disabled)
    if submitted:
        result = controller.change_lifecycle(
            detail.memory_id, "restore", pinned, source_version=version, evidence=evidence
        )
        show(result.notice)
        if result.ok:
            st.session_state["pinned_version"] = None
            st.session_state["flash"] = Notice(
                "success", "Restored as a new version. Previous history is preserved."
            )
            st.rerun()
    st.caption("Generated summaries must be rebuilt through consolidation from current sources.")


def show_detail(detail: DetailView) -> None:
    st.text(f"{detail.type_label} | {detail.scope_label} | {detail.conditions}")
    st.subheader(f"Current version: {detail.current.number}")
    st.text(detail.current.content)
    st.text(detail.current.validity)
    for line in detail.relationships:
        st.text(line)
    st.subheader("Evidence and history")
    for version in detail.history:
        title = f"Version {version.number}: {version.status_label}"
        with st.expander(title, expanded=version.is_current):
            if not version.is_current:
                st.text(version.content)
            st.text(f"{version.validity} | {version.recorded}")
            st.text("Evidence:")
            st.text(version.evidence)
            with st.expander("Source reference"):
                st.text(version.source)


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
            for key in list(st.session_state):
                if key.startswith(
                    ("save_", "import_", "restore-", "content-", "evidence-")
                ) or key in ("capture_job_id", "consolidation_job_id", "draft"):
                    del st.session_state[key]
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
    capabilities_result = controller.action("capabilities")
    show(capabilities_result.notice)
    capabilities = capabilities_result.data
    with st.sidebar:
        st.caption(
            "Connection checks confirm service configuration; "
            "online providers are used only for requested processing/search."
        )
        st.text(f"AI processing configured: {bool(capabilities.get('extraction_configured'))}")
        st.text(f"Meaning search configured: {bool(capabilities.get('embeddings_configured'))}")
    browse, search, save, imported, maintenance = st.tabs(
        ["Browse", "Search", "Save", "Import", "Maintenance"],
        key="navigation",
        on_change="rerun",
    )
    with browse:
        browse_tab(controller)
    with search:
        search_tab(controller)
    with save:
        save_tab(controller, capabilities)
    with imported:
        import_tab(controller, capabilities)
    with maintenance:
        maintenance_tab(controller, capabilities)
    selected = st.session_state.get("selected")
    if selected:
        detail_panel(controller, selected)


if __name__ == "__main__":
    render()
