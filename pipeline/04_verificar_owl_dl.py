"""Verificación OWL 2 DL con HermiT (requiere Java): consistencia, clases insatisfacibles y clasificación.

Uso: python 04_verificar_owl_dl.py --municipio 11001
Usa la ontología, la base curada y las observaciones de un municipio (el razonamiento DL completo
sobre todo el grafo es costoso; para eso el pipeline usa OWL 2 RL en el paso 03).
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

import owlready2
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

RAIZ = Path(__file__).resolve().parent.parent
COT = Namespace("https://w3id.org/cotel/ontology#")
RES = Namespace("https://w3id.org/cotel/resource/")


def construir_muestra(cod_municipio: str, anio: str, trimestre: str) -> Graph:
    g = Graph()
    g.parse(RAIZ / "ontologia" / "cotel.ttl")
    g.parse(RAIZ / "datos" / "base_curada.ttl")
    datos = Graph().parse(RAIZ / "datos" / f"cotel_internet_fijo_{anio}T{trimestre}.ttl")
    municipio = RES[f"municipio-{cod_municipio}"]
    nodos = {municipio, RES["servicio-internet-fijo"], RES[f"periodo-{anio}-T{trimestre}"]}
    nodos.update(datos.objects(municipio, COT.perteneceADepartamento))
    for obs in datos.subjects(COT.enMunicipio, municipio):
        nodos.add(obs)
        nodos.update(datos.objects(obs, COT.reportadoPor))
    for n in nodos:
        for t in datos.triples((n, None, None)):
            g.add(t)
    return g


def main(cod_municipio: str, anio: str, trimestre: str) -> dict:
    muestra = construir_muestra(cod_municipio, anio, trimestre)
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "muestra.owl"
        muestra.serialize(ruta, format="xml")
        mundo = owlready2.World()
        with open(ruta, "rb") as f:
            onto = mundo.get_ontology("https://w3id.org/cotel/ontology").load(fileobj=f)
        t0 = time.time()
        resultado = {"municipio": cod_municipio, "tripletas": len(muestra)}
        try:
            with onto:
                owlready2.sync_reasoner_hermit(mundo, infer_property_values=False, debug=0)
            resultado["consistente"] = True
        except owlready2.OwlReadyInconsistentOntologyError as e:
            resultado["consistente"] = False
            resultado["error"] = str(e)[:500]
        resultado["segundos_hermit"] = round(time.time() - t0, 1)
        if resultado["consistente"]:
            resultado["clases_insatisfacibles"] = [str(c) for c in mundo.inconsistent_classes()]
            fibra = mundo[str(COT.ObservacionFibraOptica)]
            alta = mundo[str(COT.ObservacionAltaVelocidad)]
            resultado["inferidas_fibra_optica_hermit"] = len(list(fibra.instances())) if fibra else 0
            resultado["inferidas_alta_velocidad_hermit"] = len(list(alta.instances())) if alta else 0
    salida = RAIZ / "resultados" / "verificacion_owl_dl.json"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return resultado


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--municipio", default="11001")
    ap.add_argument("--anio", default="2023")
    ap.add_argument("--trimestre", default="3")
    a = ap.parse_args()
    main(a.municipio, a.anio, a.trimestre)
