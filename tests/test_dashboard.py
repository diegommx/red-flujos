from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_requires_source_selection_before_loading():
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    assert not app.exception
    assert "rf_resultado" not in app.session_state


def test_dashboard_demo_button_opens_included_csv():
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    assert any(button.label == "Explorar datos ficticios" for button in app.button)
    next(button for button in app.button if button.label == "Explorar datos ficticios").click().run()
    assert not app.exception
    assert app.session_state["rf_fuente_nombre"] == "Datos ficticios incluidos (CSV)"
    assert len(app.session_state["rf_resultado"].df_tx) == 266


def test_dashboard_manual_source_can_be_loaded_and_changed():
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    assert any(button.label == "Cargar datos" for button in app.button)

    next(button for button in app.button if button.label == "Cargar datos").click().run()
    assert not app.exception
    assert "rf_resultado" in app.session_state
    assert any(button.label == "Cambiar fuente de datos" for button in app.button)

    next(button for button in app.button if button.label == "Cambiar fuente de datos").click().run()
    assert not app.exception
    assert "rf_resultado" not in app.session_state
