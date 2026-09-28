from __future__ import annotations

from pathlib import Path
from io import BytesIO
from contextlib import nullcontext

import networkx as nx
import pandas as pd
import pytest

from red_flujos import Config, analizar
from red_flujos.demo import DEMO_DIR, demo_config
from red_flujos.analytics import metricas_centralidad
from red_flujos.dashboard.layout import preparar_visual
from red_flujos.dashboard.network_html import red_transaccional_html
from red_flujos.dedup import deduplicar
from red_flujos.homologate import homologar
from red_flujos.normalize import es_desconocido, normalizar_nit, normalizar_transaccional
from red_flujos.sources import SqlSource


ROOT = Path(__file__).resolve().parents[1]


def test_included_fictional_csv_is_explorable():
    assert all((DEMO_DIR / name).is_file() for name in ("flujos.csv", "relaciones.csv", "nombres.csv"))
    for name in ("flujos.csv", "relaciones.csv", "nombres.csv"):
        assert (DEMO_DIR / name).read_bytes() == (ROOT / "examples" / "demo_financiero" / name).read_bytes()
    result = analizar(demo_config())
    assert len(result.df_tx) == 266
    assert result.reportes["dedup"]["espejos_reconciliados"] == 45
    assert result.G_estructura.number_of_edges() == 15


def test_public_config_uses_only_synthetic_data():
    cfg = Config.load()
    assert cfg["fuente"]["tipo"] == "synthetic"
    assert not cfg["fuente"]["sql"]["server"]
    assert not cfg["fuente"]["sql"]["queries"]["transacciones"]
    result = analizar(cfg)
    assert len(result.df_tx) > 0
    assert result.reportes["dedup"]["espejos_reconciliados"] > 0
    assert result.G_topologia.number_of_nodes() < result.G_col.number_of_nodes()
    visible, _, _ = preparar_visual(result.G_col, set(result.clientes))
    assert "SIN_CONTRAPARTE" in visible
    assert not any(es_desconocido(n) and n != "SIN_CONTRAPARTE" for n in visible)
    with pytest.raises(ValueError, match="YAML privado"):
        SqlSource(Config.load())


def test_text_ids_and_missing_endpoints_remain_distinct():
    ids = normalizar_nit(pd.Series(["00123", "10.0.0.1", "ABC-07", 123]))
    assert ids.tolist() == ["00123", "10.0.0.1", "ABC-07", "123"]
    with pytest.raises(ValueError, match="impreciso"):
        normalizar_nit(pd.Series([float(2**54)]))

    cfg = Config.load()
    raw = pd.DataFrame({
        "id_evento": ["a", "b"], "actor": ["00123", "00123"],
        "contraparte": ["", ""], "fecha": ["2026-01-01", "2026-01-02"],
        "cantidad": ["1", "2"], "tipo_evento": ["RETIRO", "RETIRO"],
    })
    normalizado, reporte = normalizar_transaccional(raw, cfg)
    assert reporte["sin_contraparte"] == 2
    assert normalizado["nit"].tolist() == ["00123", "00123"]
    extremos = normalizado["nit_contraparte"].tolist()
    assert extremos[0] != extremos[1]
    assert all(es_desconocido(x) for x in extremos)


def test_mirror_reconciliation_is_directional_and_keeps_ambiguity():
    momento = pd.Timestamp("2026-01-01T12:00:00")
    rows = [
        # Un solo par inequívoco A -> B.
        ("d1", "A", "B", "DEBITO", 10, momento),
        ("c1", "B", "A", "CREDITO", 10, momento),
        # Flujo opuesto B -> A, sin espejo: debe conservarse.
        ("d2", "B", "A", "DEBITO", 10, momento),
        # Dos débitos idénticos y un crédito: la equivalencia es ambigua.
        ("d3", "A", "B", "DEBITO", 20, momento),
        ("d4", "A", "B", "DEBITO", 20, momento),
        ("c2", "B", "A", "CREDITO", 20, momento),
    ]
    df = pd.DataFrame(rows, columns=["id_operacion", "nit", "nit_contraparte", "sentido", "valor", "fecha"])
    df["canal"] = "red"
    final, reporte = deduplicar(df, {"A", "B"}, modo="espejo")
    assert reporte["espejos_reconciliados"] == 1
    assert reporte["grupos_ambiguos_filas"] == 3
    assert set(final["id_operacion"]) == {"d1", "d2", "d3", "d4", "c2"}
    assert final.set_index("id_operacion").loc["d2", "origen"] == "B"


def test_reused_row_id_with_different_quantity_is_not_silently_removed():
    df = pd.DataFrame({
        "id_operacion": ["shared", "shared"], "nit": ["A", "A"],
        "nit_contraparte": ["B", "B"], "sentido": ["DEBITO", "DEBITO"],
        "valor": [10, 20], "fecha": [pd.Timestamp("2026-01-01")] * 2,
        "canal": ["x", "x"],
    })
    final, reporte = deduplicar(df, {"A", "B"})
    assert len(final) == 2
    assert reporte["duplicados_id"] == 0


def test_identity_resolution_rejects_monitored_merge():
    df = pd.DataFrame({
        "nit": ["ABC", "ABCD"], "nombre": ["MISMA", "MISMA"],
        "nit_contraparte": ["OTRO", "OTRO"], "nombre_contraparte": ["OTRO", "OTRO"],
    })
    mapa, _, reporte = homologar(df, {"ABC", "ABCD"}, modo="prefijo")
    assert mapa["ABC"] == "ABC" and mapa["ABCD"] == "ABCD"
    assert reporte["conflictos"]
    with pytest.raises(ValueError, match="monitoreados"):
        homologar(df, {"ABC", "ABCD"}, unir_nits={"ABC": "ABCD"})


def test_betweenness_uses_hops_not_amount_as_distance():
    graph = nx.DiGraph()
    graph.add_edge("A", "B", total=1)
    graph.add_edge("B", "C", total=1)
    graph.add_edge("A", "C", total=1000)
    metrics = metricas_centralidad(graph).set_index("nit")
    assert metrics.loc["B", "betweenness"] == 0


def test_generic_csv_example_uses_own_unit_and_relationships():
    cfg = Config.load(ROOT / "examples" / "logistica.example.yaml")
    cfg.data["fuente"]["tipo"] = "csv"
    cfg.data["fuente"]["archivos"] = {
        "transacciones": str(ROOT / "examples" / "flujos.csv"),
        "vinculados": str(ROOT / "examples" / "relaciones.csv"),
    }
    result = analizar(cfg)
    assert len(result.df_tx) == 3
    assert result.df_tx["valor"].sum() == 350
    assert result.presentacion["unidad"] == "kg"
    assert result.G_estructura.number_of_edges() == 2


def test_excel_upload_bytes_work_without_relationship_file():
    cfg = Config.load(ROOT / "examples" / "logistica.example.yaml")
    cfg.data["fuente"]["tipo"] = "excel"
    out = BytesIO()
    pd.read_csv(ROOT / "examples" / "flujos.csv", dtype=str).to_excel(out, index=False)
    cfg.data["fuente"]["archivos"] = {"transacciones": out.getvalue()}
    result = analizar(cfg)
    assert len(result.df_tx) == 3
    assert result.G_estructura.number_of_edges() == 0


def test_sql_source_stops_when_query_exceeds_local_row_limit(monkeypatch):
    cfg = Config.load()
    cfg.data["fuente"]["sql"].update({
        "server": "SERVIDOR_FICTICIO",
        "max_rows": 2,
        "queries": {"transacciones": "SELECT id_evento FROM ejemplo"},
    })
    source = SqlSource(cfg)
    monkeypatch.setattr(source, "_conn", lambda: nullcontext(object()))
    monkeypatch.setattr(pd, "read_sql_query", lambda *args, **kwargs: iter([
        pd.DataFrame({"id_evento": ["1", "2"]}),
        pd.DataFrame({"id_evento": ["3"]}),
    ]))
    with pytest.raises(ValueError, match="max_rows=2"):
        source.fetch_transacciones()


def test_network_html_escapes_untrusted_identifiers_and_names():
    payload = "</script><script>alert(1)</script>"
    graph = nx.DiGraph()
    graph.add_node(payload, nombre=payload, tipo="cliente")
    graph.add_node("B", nombre="B", tipo="externo")
    graph.add_edge(payload, "B", total=5, n_tx=1)
    page = red_transaccional_html(graph, {payload: (0, 0), "B": (1, 0)})
    assert payload not in page
    assert r"\u0026lt;/script\u0026gt;" in page
