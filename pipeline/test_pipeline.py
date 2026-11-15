"""Pruebas del pipeline COTEL. Ejecutar: python -m pytest -q pipeline"""
import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, RDFS, XSD

RAIZ = Path(__file__).resolve().parent.parent
COT = Namespace("https://w3id.org/cotel/ontology#")
RES = Namespace("https://w3id.org/cotel/resource/")

spec = importlib.util.spec_from_file_location("transformar", RAIZ / "pipeline" / "02_transformar_rdf.py")
tr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tr)

VALORES_MINTIC = [
    "CABLE", "FIBER TO THE HOME (FTTH)", "HYBRID FIBER COAXIAL (HFC)", "XDSL",
    "OTRAS TECNOLOGÍAS INALÁMBRICAS", "WIFI", "FIBER TO THE CABINET (FTTC)",
    "OTRAS TECNOLOGÍAS DE FIBRA (ANTES FTTX)", "SATELITAL", "WIMAX", "OTRAS TECNOLOGÍAS FIJAS",
    "FIBER TO THE PREMISES", "FIBER TO THE BUILDING O FIBER TO THE BASEMENT (FTTB)",
    "FIBER TO THE NODE (FTTN)", "NA (NO APLICA)", "FIBER TO THE ANTENNA (FTTA)",
]


@pytest.fixture(scope="module")
def onto():
    return Graph().parse(RAIZ / "ontologia" / "cotel.ttl")


@pytest.fixture(scope="module")
def formas():
    return Graph().parse(RAIZ / "ontologia" / "cotel-shapes.ttl")


def test_todas_las_tecnologias_mintic_tienen_concepto(onto):
    mapa = tr.mapa_tecnologias(onto)
    faltantes = [v for v in VALORES_MINTIC if tr.normalizar(v) not in mapa]
    assert faltantes == []


def test_ftth_es_tecnologia_de_fibra(onto):
    ftth = tr.mapa_tecnologias(onto)[tr.normalizar("FIBER TO THE HOME (FTTH)")]
    assert (ftth, RDF.type, COT.TecnologiaFibra) in onto


@pytest.mark.parametrize("texto,esperado", [
    ("RESIDENCIAL - ESTRATO 3", "seg-estrato-3"),
    ("CORPORATIVO", "seg-corporativo"),
    ("SIN ESTRATIFICAR", "seg-sin-estratificar"),
    ("USO PROPIO INTERNO DEL OPERADOR", "seg-uso-propio"),
])
def test_segmentos(texto, esperado):
    assert tr.segmento_iri(texto) == COT[esperado]


def test_segmento_desconocido_falla():
    with pytest.raises(ValueError):
        tr.segmento_iri("MAYORISTA")


@pytest.mark.parametrize("texto,esperado", [
    ("5,12", Decimal("5.12")), ("300,00", Decimal("300.00")), ("1.000,50", Decimal("1000.50")),
    ("", None), ("abc", None),
])
def test_decimal_es(texto, esperado):
    assert tr.decimal_es(texto) == esperado


def _grafo_minimo(onto, numero_accesos=Literal(10, datatype=XSD.nonNegativeInteger), cod_mun="11001"):
    g = Graph()
    g += onto
    g.add((RES["org-x"], RDF.type, COT.ProveedorRedesServicios))
    g.add((RES["org-x"], COT.razonSocial, Literal("X S.A.")))
    g.add((RES["departamento-11"], RDF.type, COT.Departamento))
    g.add((RES["departamento-11"], COT.codigoDANE, Literal("11")))
    m = RES[f"municipio-{cod_mun}"]
    g.add((m, RDF.type, COT.Municipio))
    g.add((m, COT.codigoDANE, Literal(cod_mun)))
    g.add((m, COT.perteneceADepartamento, RES["departamento-11"]))
    g.add((m, RDFS.label, Literal("Bogotá")))
    p = RES["periodo-2023-T3"]
    g.add((p, RDF.type, COT.Trimestre))
    g.add((p, COT.anio, Literal(2023, datatype=XSD.integer)))
    g.add((p, COT.numeroTrimestre, Literal(3, datatype=XSD.integer)))
    s = RES["servicio-internet-fijo"]
    g.add((s, RDF.type, COT.InternetFijo))
    o = RES["obs-prueba"]
    g.add((o, RDF.type, COT.ObservacionAccesos))
    for prop, val in ((COT.reportadoPor, RES["org-x"]), (COT.enMunicipio, m), (COT.enPeriodo, p),
                      (COT.deServicio, s), (COT.usaTecnologia, COT["tec-ftth"]),
                      (COT.enSegmento, COT["seg-estrato-3"]), (COT.tieneFuente, RES["fuente-x"])):
        g.add((o, prop, val))
    if numero_accesos is not None:
        g.add((o, COT.numeroAccesos, numero_accesos))
    return g


def test_shacl_acepta_observacion_valida(onto, formas):
    conforme, _, texto = validate(_grafo_minimo(onto), shacl_graph=formas, advanced=True)
    assert conforme, texto


def test_shacl_rechaza_observacion_sin_accesos(onto, formas):
    conforme, _, _ = validate(_grafo_minimo(onto, numero_accesos=None), shacl_graph=formas, advanced=True)
    assert not conforme


def test_shacl_rechaza_dane_inconsistente(onto, formas):
    conforme, _, texto = validate(_grafo_minimo(onto, cod_mun="05001"), shacl_graph=formas, advanced=True)
    assert not conforme and "departamento" in texto
