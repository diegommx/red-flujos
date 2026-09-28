"""Cliente de consola: solicita la fuente antes de ejecutar el motor."""
from __future__ import annotations

import argparse

from red_flujos import Config, analizar
from red_flujos.dashboard.formatting import cantidad


def bloque(titulo: str):
    print("\n" + "=" * 70)
    print(f"  {titulo}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Análisis local de red de flujos")
    parser.add_argument("--source", choices=["synthetic", "csv", "excel", "sql"],
                        help="Si se omite, se pregunta antes de cargar datos")
    parser.add_argument("--config", help="YAML privado opcional de mapeo; obligatorio para SQL")
    parser.add_argument("--transactions", help="Archivo CSV/Excel de flujos")
    parser.add_argument("--relations", help="Archivo CSV/Excel de relaciones")
    parser.add_argument("--names", help="Archivo CSV/Excel de nombres")
    parser.add_argument("--mirror", action="store_true", help="Reconciliar observaciones espejo")
    args = parser.parse_args()
    fuente = args.source or input("Fuente [synthetic/csv/excel/sql]: ").strip().lower()
    if fuente not in {"synthetic", "csv", "excel", "sql"}:
        parser.error("Seleccione synthetic, csv, excel o sql")
    if fuente == "sql" and not args.config:
        parser.error("SQL requiere --config con consultas y conexión privadas")
    cfg = Config.load(args.config)
    cfg.data["fuente"]["tipo"] = fuente
    if fuente in {"csv", "excel"}:
        ruta = args.transactions or input("Ruta del archivo de flujos: ").strip()
        if not ruta:
            parser.error("Falta el archivo de flujos")
        cfg.data["fuente"]["archivos"] = {
            "transacciones": ruta,
            "vinculados": args.relations or "",
            "nombres": args.names or "",
        }
        cfg.data["reconciliacion"]["modo"] = "espejo" if args.mirror else "ninguna"
    money = lambda valor: cantidad(valor, cfg.presentacion)
    r = analizar(cfg)

    bloque("1. ACTORES MONITOREADOS")
    pn = [k for k, v in r.clientes.items() if v == "PN"]
    pj = [k for k, v in r.clientes.items() if v == "PJ"]
    if cfg.presentacion.get("perfil") == "financiero":
        print(f"Total: {len(r.clientes)}  ({len(pn)} PN + {len(pj)} PJ)")
    else:
        print(f"Total: {len(r.clientes)}")

    bloque("2. NORMALIZACIÓN Y DIRECCIÓN")
    rn = r.reportes["normalizacion"]
    print(f"Válidas: {rn['filas_validas']:,} | Descartadas: {rn['descartadas']:,}")
    print(f"Sentidos: {rn['distribucion_sentido']}")
    print(f"Sin contraparte: {rn['sin_contraparte']:,}")
    print(f"Rango: {rn['rango'][0]} -> {rn['rango'][1]}")
    print(f"Canales: {rn['distribucion_canal']}")
    if rn["transaccion_excluidas"]:
        print(f"Tipos de evento excluidos: {rn['transaccion_excluidas']}")

    bloque("3. HOMOLOGACIÓN")
    rh = r.reportes["homologacion"]
    print(f"Pares: {rh['pares_candidatos']:,} | Uniones: {rh['uniones']} | Grupos: {rh['grupos_totales']}")
    for can, info in list(rh["grupos_multi_nit"].items())[:5]:
        print(f"  {can}: IDs unificados = {info['nits']}")

    bloque("4. RECONCILIACIÓN")
    rd = r.reportes["dedup"]
    print(f"Internas {rd['internas_brutas']:,} | espejos reconciliados {rd['espejos_reconciliados']} | ambiguas {rd['grupos_ambiguos_filas']}")
    print(f"Externas: {rd['externas']:,} | Total final: {rd['total_final']:,}")

    bloque("5. GRAFO DE FLUJOS")
    print(f"Nodos: {r.G_col.number_of_nodes()} | Aristas: {r.G_col.number_of_edges()}")
    print(f"Subgrafo principal: {r.G_principal.number_of_nodes()} nodos, {r.G_principal.number_of_edges()} aristas")

    bloque(f"6. TOP NODOS POR {cfg.presentacion.get('cantidad', 'CANTIDAD').upper()}")
    top = r.resumen_nodos.head(8).copy()
    for _, x in top.iterrows():
        print(f"  {x['tipo']:11s} {x['nombre'][:34]:34s} recibe {money(x['recibido']):>9s} envía {money(x['enviado']):>9s}")

    bloque("7. FLUJOS ENTRE ACTORES MONITOREADOS (de primera clase)")
    if len(r.flujos_actores):
        for _, x in r.flujos_actores.head(6).iterrows():
            marca = " [MISMO ACTOR]" if x["mismo_actor"] else ""
            print(f"  {x['origen_nombre'][:26]:26s} -> {x['destino_nombre'][:26]:26s} {money(x['total']):>9s} ({x['n_tx']} eventos){marca}")
    n_mismo = int(r.flujos_actores["mismo_actor"].sum()) if len(r.flujos_actores) else 0
    print(f"  Total de pares internos con flujo: {len(r.flujos_actores)} ({n_mismo} son auto-flujos)")

    bloque("8. CANAL POR ACTOR (alimenta el Sankey de canal)")
    act = r.flujos_actores.iloc[0]["origen"] if len(r.flujos_actores) else list(r.clientes)[0]
    sub = r.canal_actor[r.canal_actor["actor"] == act]
    nom = r.G_col.nodes[act].get("nombre", act)
    print(f"  Actor de ejemplo: {nom} [{act}]")
    for _, x in sub.iterrows():
        print(f"    {x['sentido']:5s}  {x['canal']:9s}  {money(x['total']):>9s}  ({x['n_tx']} eventos)")

    bloque("9. MÉTRICAS DE CENTRALIDAD + CICLOS (sin 'Sin Contraparte' en la topología)")
    for _, x in r.metricas.head(5).iterrows():
        print(f"  PageRank {x['pagerank']:.4f}  Btw {x['betweenness']:.4f}  {x['nombre'][:34]}")
    print(f"  Ciclos cortos (2-5 nodos): {len(r.ciclos)}")

    bloque("10. RELACIONES COMPARTIDAS")
    print(f"Grafo estructural: {r.G_estructura.number_of_nodes()} nodos, {r.G_estructura.number_of_edges()} relaciones")
    print("\n  Relacionados compartidos por varias entidades:")
    if len(r.hubs):
        for _, x in r.hubs.iterrows():
            print(f"    {x['nombre_vinculado'][:32]:32s} -> {x['n_empresas']} entidades  {x['relaciones']}")
    else:
        print("    (ninguno supera el umbral)")
    print("\n  Pares de entidades con relación compartida:")
    if len(r.pares_estructura):
        for _, x in r.pares_estructura.head(8).iterrows():
            print(f"    {x['empresa_a']} <-> {x['empresa_b']}  comparten {x['relacion']}: {x['nombre_vinculado'][:28]}")
        print(f"    Total de pares: {len(r.pares_estructura)}")

    print("\n" + "=" * 70)
    print("  Pipeline completo.")
    print("=" * 70)


if __name__ == "__main__":
    main()
