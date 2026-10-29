"""Automatable widget semantics only; no claim of a human accessibility review."""

from tests.inspection.fakes import TOKEN, memory
from tests.inspection.test_app import make_app, open_first, ready_service
from tests.inspection.test_settings import load_settings
from tests.inspection.test_settings_check import configured
from tests.inspection.test_v1 import submit


def test_all_setup_and_lifecycle_controls_have_visible_accessible_names():
    mem = memory()
    app = make_app(ready_service(mem))
    client = configured()
    app.session_state["make_settings_client"] = lambda: client
    app.run()
    app.sidebar.text_input(key="token").input(TOKEN)
    app.run()
    open_first(app, mem)
    load_settings(app)
    for kind in ("text_input", "text_area", "selectbox", "checkbox", "radio", "button"):
        for control in app.get(kind):
            assert control.proto.label.strip(), f"Unnamed {kind}"
            if hasattr(control.proto, "label_visibility"):
                assert control.proto.label_visibility.value == 0, (
                    f"Hidden label: {control.proto.label}"
                )
    assert not app.exception


def test_destructive_and_invalid_actions_have_text_explanations_without_color_dependence():
    mem = memory()
    app = make_app(ready_service(mem)).run()
    app.sidebar.text_input(key="token").input(TOKEN)
    app.run()
    open_first(app, mem)
    submit(app, "Delete permanently")
    assert any("Confirm" in notice.value for notice in app.warning)
    app.text_area(key="save_text").input("")
    submit(app, "Save memory")
    assert any("Enter the memory text" in notice.value for notice in app.warning)
    token = app.sidebar.text_input(key="token")
    assert token.proto.type == token.proto.PASSWORD
    # Streamlit can expose these names/notices to assistive tools. AppTest does not
    # inspect browser focus order, contrast, zoom or screen-reader announcements.
