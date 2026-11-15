"""Valida (SHACL), razona (OWL 2 RL) y ejecuta las preguntas de competencia (SPARQL).

Uso: python 03_validar_razonar_consultar.py --anio 2023 --trimestre 3
Salidas en resultados/: CQ*.csv, reporte_shacl.txt, resumen.json
"""
import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path

import owlrl
from pyshacl import validate
from rdflib import Graph, Namespace
from rdflib.namespace import OWL, RDF, SH

RAIZ = Path(__file__).resolve().parent.parent
COT = Namespace("https://w3id.org/cotel/ontology#")
RES = Namespace("https://w3id.org/cotel/resource/")
SHP = Namespace("https://w3id.org/cotel/shapes#")

REGLA_ALTA_VELOCIDAD = """
PREFIX cot: <https://w3id.org/cotel/ontology#>
INSERT { ?o a cot:ObservacionAltaVelocidad }
WHERE  { ?o a cot:ObservacionAccesos ; cot:velocidadBajadaMbps ?v . FILTER (?v >= 25) }
"""


def metricas_ontologia(onto: Graph) -> dict:
    return {
        "clases": len(set(onto.subjects(RDF.type, OWL.Class))),
        "propiedades_objeto": len(set(onto.subjects(RDF.type, OWL.ObjectProperty))),
        "propiedades_datos": len(set(onto.subjects(RDF.type, OWL.DatatypeProperty))),
        "axiomas_tripletas": len(onto),
    }


def contar(g: Graph, clase) -> int:
    return len(set(g.subjects(RDF.type, clase)))


def _validar(grafo: Graph, formas: Graph) -> tuple[bool, Graph, str]:
    # Sin inferencia: la ontología va dentro del grafo y pySHACL sigue rdfs:subClassOf al evaluar sh:class.
    return validate(grafo, shacl_graph=formas, inference="none", advanced=True, allow_warnings=True)


def validar_shacl(grafo: Graph, onto: Graph, base: Graph, datos: Graph, formas: Graph,
                  salida: Path, lote: int = 4000) -> dict:
    """Valida entidades de referencia una vez y las observaciones por lotes (costo lineal)."""
    observaciones = sorted(set(grafo.subjects(RDF.type, COT.ObservacionAccesos)))
    obs_set = set(observaciones)

    formas_obs = Graph()
    for t in formas.cbd(SHP.ObservacionAccesosShape):
        formas_obs.add(t)
    formas_ref = Graph()
    formas_ref += formas
    formas_ref -= formas_obs

    referencia = Graph()
    referencia += onto
    referencia += base
    for s, p, o in datos:
        if s not in obs_set:
            referencia.add((s, p, o))
    tipos = Graph()
    tipos += onto
    for s, o in referencia.subject_objects(RDF.type):
        tipos.add((s, RDF.type, o))

    reportes, conforme = [], True
    resultados = Graph()
    c, rg, txt = _validar(referencia, formas_ref)
    conforme &= c
    resultados += rg
    reportes.append(txt)
    print(f"  entidades de referencia: {'OK' if c else 'con violaciones'}")

    for i in range(0, len(observaciones), lote):
        g = Graph()
        g += tipos
        for obs in observaciones[i:i + lote]:
            for t in grafo.triples((obs, None, None)):
                g.add(t)
        c, rg, txt = _validar(g, formas_obs)
        conforme &= c
        resultados += rg
        if not c or "Warning" in txt:
            reportes.append(txt)
        print(f"  observaciones {min(i + lote, len(observaciones))}/{len(observaciones)}")

    (salida / "reporte_shacl.txt").write_text("\n\n".join(reportes), encoding="utf-8")
    severidades = Counter(str(s).split("#")[-1] for s in resultados.objects(None, SH.resultSeverity))
    return {"conforme": conforme, "observaciones_validadas": len(observaciones),
            "violaciones": severidades.get("Violation", 0), "advertencias": severidades.get("Warning", 0)}


def razonar_muestra(onto: Graph, base: Graph, datos: Graph, cod_municipio: str) -> dict:
    """OWL 2 RL sobre una muestra (un municipio) para mostrar las inferencias de la ontología."""
    muestra = Graph()
    muestra += onto
    muestra += base
    municipio = RES[f"municipio-{cod_municipio}"]
    for obs in datos.subjects(COT.enMunicipio, municipio):
        for p, o in datos.predicate_objects(obs):
            muestra.add((obs, p, o))
            if p in (COT.reportadoPor, COT.enPeriodo):
                for t in datos.triples((o, None, None)):
                    muestra.add(t)
    for t in datos.triples((municipio, None, None)):
        muestra.add(t)
    for dep in datos.objects(municipio, COT.perteneceADepartamento):
        for t in datos.triples((dep, None, None)):
            muestra.add(t)

    antes = len(muestra)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(muestra)
    muestra.update(REGLA_ALTA_VELOCIDAD)
    return {
        "municipio": cod_municipio,
        "tripletas_antes": antes,
        "tripletas_despues": len(muestra),
        "observaciones": contar(muestra, COT.ObservacionAccesos),
        "inferidas_fibra_optica_owl": contar(muestra, COT.ObservacionFibraOptica),
        "inferidas_alta_velocidad_regla": contar(muestra, COT.ObservacionAltaVelocidad),
        "municipio_ubicado_en_colombia_transitividad": (municipio, COT.ubicadoEn, RES["pais-colombia"]) in muestra,
        "america_movil_controla_comcel_inversa": (RES["org-america-movil"], COT.controla, RES["org-comcel"]) in muestra,
        "comcel_es_organizacion_por_subclase": (RES["org-comcel"], RDF.type, COT.Organizacion) in muestra,
    }


def main(anio: str, trimestre: str, municipio_muestra: str, solo_consultas: bool = False) -> None:
    salida = RAIZ / "resultados"
    salida.mkdir(exist_ok=True)
    previo = salida / "resumen.json"
    resumen = json.loads(previo.read_text(encoding="utf-8")) if solo_consultas and previo.exists() else {}

    onto = Graph().parse(RAIZ / "ontologia" / "cotel.ttl")
    formas = Graph().parse(RAIZ / "ontologia" / "cotel-shapes.ttl")
    base = Graph().parse(RAIZ / "datos" / "base_curada.ttl")
    datos = Graph().parse(RAIZ / "datos" / f"cotel_internet_fijo_{anio}T{trimestre}.ttl")
    resumen["ontologia"] = metricas_ontologia(onto)

    grafo = Graph()
    grafo += base
    grafo += datos
    resumen["grafo_tripletas"] = len(grafo)
    grafo += onto

    t0 = time.time()
    if solo_consultas:
        print("Omitiendo SHACL y razonamiento (--solo-consultas)")
    else:
        resumen["shacl"] = validar_shacl(grafo, onto, base, datos, formas, salida)
        resumen["shacl"]["segundos"] = round(time.time() - t0, 1)
        print(f"SHACL: {json.dumps(resumen['shacl'], ensure_ascii=False)}")

        t0 = time.time()
        resumen["razonamiento_muestra"] = razonar_muestra(onto, base, datos, municipio_muestra)
        resumen["razonamiento_muestra"]["segundos"] = round(time.time() - t0, 1)
        print("Razonamiento:", json.dumps(resumen["razonamiento_muestra"], ensure_ascii=False))

    resumen["consultas"] = {}
    for rq in sorted((RAIZ / "consultas").glob("CQ*.rq")):
        t0 = time.time()
        resultado = grafo.query(rq.read_text(encoding="utf-8-sig"))
        filas = list(resultado)
        with (salida / f"{rq.stem}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([str(v) for v in resultado.vars])
            for fila in filas:
                w.writerow(["" if x is None else str(x) for x in fila])
        resumen["consultas"][rq.stem] = {"filas": len(filas), "segundos": round(time.time() - t0, 1)}
        print(f"\n== {rq.stem} ({len(filas)} filas)")
        for fila in filas[:6]:
            print("  ", " | ".join("" if x is None else str(x) for x in fila))

    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", default="2023")
    ap.add_argument("--trimestre", default="3")
    ap.add_argument("--municipio-muestra", default="11001", help="Código DANE para la demostración de razonamiento")
    ap.add_argument("--solo-consultas", action="store_true", help="Omite SHACL y razonamiento")
    a = ap.parse_args()
    main(a.anio, a.trimestre, a.municipio_muestra, a.solo_consultas)
