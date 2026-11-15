"""Transforma el CSV de MinTIC (Internet fijo) en RDF conforme a la ontología COTEL.

Uso: python 02_transformar_rdf.py --anio 2023 --trimestre 3
Entrada: datos/crudo_internet_fijo_<anio>T<trimestre>.csv
Salida:  datos/cotel_internet_fijo_<anio>T<trimestre>.ttl

Agregación: una observación por proveedor x municipio x tecnología x segmento.
Las velocidades son el promedio ponderado por accesos de las velocidades de plan reportadas.
"""
import argparse
import csv
import hashlib
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD

RAIZ = Path(__file__).resolve().parent.parent
COT = Namespace("https://w3id.org/cotel/ontology#")
RES = Namespace("https://w3id.org/cotel/resource/")
QB = Namespace("http://purl.org/linked-data/cube#")
DCT = Namespace("http://purl.org/dc/terms/")

PROVEEDORES_CURADOS = {
    "COMUNICACION CELULAR S A COMCEL S A": RES["org-comcel"],
    "TELMEX COLOMBIA S.A.": RES["org-telmex-colombia"],
}
FUENTE = RES["fuente-mintic-internet-fijo"]
SERVICIO = RES["servicio-internet-fijo"]


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto).lower()).strip("-")


def decimal_es(valor: str) -> Decimal | None:
    valor = (valor or "").strip()
    if not valor:
        return None
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    try:
        return Decimal(valor)
    except ArithmeticError:
        return None


def mapa_tecnologias(ontologia: Graph) -> dict[str, URIRef]:
    mapa = {}
    for concepto, etiqueta in ontologia.subject_objects(SKOS.altLabel):
        mapa[normalizar(str(etiqueta))] = concepto
    return mapa


def segmento_iri(segmento: str) -> URIRef:
    s = normalizar(segmento)
    m = re.search(r"ESTRATO (\d)", s)
    if m:
        return COT[f"seg-estrato-{m.group(1)}"]
    if s.startswith("CORPORATIVO"):
        return COT["seg-corporativo"]
    if "SIN ESTRATIFICAR" in s:
        return COT["seg-sin-estratificar"]
    if "USO PROPIO" in s:
        return COT["seg-uso-propio"]
    raise ValueError(f"Segmento no mapeado: {segmento!r}")


def redondear(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def transformar(anio: str, trimestre: str) -> Path:
    entrada = RAIZ / "datos" / f"crudo_internet_fijo_{anio}T{trimestre}.csv"
    salida = RAIZ / "datos" / f"cotel_internet_fijo_{anio}T{trimestre}.ttl"
    ontologia = Graph().parse(RAIZ / "ontologia" / "cotel.ttl")
    tecnologias = mapa_tecnologias(ontologia)

    grupos = defaultdict(lambda: {"accesos": 0, "baj": Decimal(0), "sub": Decimal(0),
                                  "baj_s": Decimal(0), "sub_s": Decimal(0), "n": 0})
    proveedores, municipios, departamentos = {}, {}, {}
    sin_mapear = defaultdict(int)

    with entrada.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            tec = tecnologias.get(normalizar(fila["tecnologia"]))
            if tec is None:
                sin_mapear[fila["tecnologia"]] += 1
                continue
            razon = fila["proveedor"].strip()
            prov = PROVEEDORES_CURADOS.get(razon) or RES[f"org-{slug(razon)}"]
            proveedores[prov] = razon
            cod_dep = fila["cod_departamento"].strip().zfill(2)
            cod_mun = fila["cod_municipio"].strip().zfill(5)
            departamentos[cod_dep] = fila["departamento"].strip()
            municipios[cod_mun] = (fila["municipio"].strip(), cod_dep)

            g = grupos[(prov, cod_mun, tec, segmento_iri(fila["segmento"]))]
            acc = int(fila["no_de_accesos"] or 0)
            baj, sub = decimal_es(fila["velocidad_bajada"]), decimal_es(fila["velocidad_subida"])
            g["accesos"] += acc
            g["n"] += 1
            if baj is not None:
                g["baj"] += baj * acc
                g["baj_s"] += baj
            if sub is not None:
                g["sub"] += sub * acc
                g["sub_s"] += sub

    if sin_mapear:
        raise ValueError(f"Tecnologías sin concepto SKOS: {dict(sin_mapear)}")

    out = Graph()
    for p, ns in (("cot", COT), ("res", RES), ("qb", QB), ("dct", DCT), ("skos", SKOS), ("owl", OWL)):
        out.bind(p, ns)

    out.add((SERVICIO, RDF.type, COT.InternetFijo))
    out.add((SERVICIO, RDFS.label, Literal("Internet fijo", lang="es")))

    periodo = RES[f"periodo-{anio}-T{trimestre}"]
    out.add((periodo, RDF.type, COT.Trimestre))
    out.add((periodo, RDFS.label, Literal(f"{anio}-T{trimestre}")))
    out.add((periodo, COT.anio, Literal(int(anio), datatype=XSD.integer)))
    out.add((periodo, COT.numeroTrimestre, Literal(int(trimestre), datatype=XSD.integer)))

    dataset = RES[f"ds-internet-fijo-{anio}T{trimestre}"]
    out.add((dataset, RDF.type, QB.DataSet))
    out.add((dataset, RDFS.label, Literal(f"Accesos de Internet fijo {anio}-T{trimestre}", lang="es")))
    out.add((dataset, COT.tieneFuente, FUENTE))

    for prov, razon in proveedores.items():
        out.add((prov, RDF.type, COT.ProveedorRedesServicios))
        out.add((prov, COT.razonSocial, Literal(razon)))
        out.add((prov, COT.proveeServicio, SERVICIO))
        if prov not in PROVEEDORES_CURADOS.values():
            out.add((prov, RDFS.label, Literal(razon.title(), lang="es")))

    for cod, nombre in departamentos.items():
        d = RES[f"departamento-{cod}"]
        out.add((d, RDF.type, COT.Departamento))
        out.add((d, RDFS.label, Literal(nombre.title(), lang="es")))
        out.add((d, COT.codigoDANE, Literal(cod)))
        out.add((d, COT.ubicadoEn, RES["pais-colombia"]))

    for cod, (nombre, cod_dep) in municipios.items():
        m = RES[f"municipio-{cod}"]
        out.add((m, RDF.type, COT.Municipio))
        out.add((m, RDFS.label, Literal(nombre.title(), lang="es")))
        out.add((m, COT.codigoDANE, Literal(cod)))
        out.add((m, COT.perteneceADepartamento, RES[f"departamento-{cod_dep}"]))

    for (prov, cod_mun, tec, seg), g in grupos.items():
        clave = f"{anio}T{trimestre}|{prov}|{cod_mun}|{tec}|{seg}"
        obs = RES[f"obs-if-{hashlib.sha1(clave.encode()).hexdigest()[:16]}"]
        out.add((obs, RDF.type, COT.ObservacionAccesos))
        out.add((obs, QB.dataSet, dataset))
        out.add((obs, COT.reportadoPor, prov))
        out.add((obs, COT.enMunicipio, RES[f"municipio-{cod_mun}"]))
        out.add((obs, COT.enPeriodo, periodo))
        out.add((obs, COT.deServicio, SERVICIO))
        out.add((obs, COT.usaTecnologia, tec))
        out.add((obs, COT.enSegmento, seg))
        out.add((obs, COT.numeroAccesos, Literal(g["accesos"], datatype=XSD.nonNegativeInteger)))
        out.add((obs, COT.numeroRegistrosFuente, Literal(g["n"], datatype=XSD.nonNegativeInteger)))
        out.add((obs, COT.tieneFuente, FUENTE))
        if g["accesos"] > 0:
            baj, sub = g["baj"] / g["accesos"], g["sub"] / g["accesos"]
        else:
            baj, sub = g["baj_s"] / g["n"], g["sub_s"] / g["n"]
        out.add((obs, COT.velocidadBajadaMbps, Literal(redondear(baj), datatype=XSD.decimal)))
        out.add((obs, COT.velocidadSubidaMbps, Literal(redondear(sub), datatype=XSD.decimal)))

    out.serialize(salida, format="turtle", encoding="utf-8")
    print(f"{len(grupos)} observaciones, {len(proveedores)} proveedores, {len(municipios)} municipios")
    print(f"{len(out)} tripletas -> {salida}")
    return salida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", default="2023")
    ap.add_argument("--trimestre", default="3")
    a = ap.parse_args()
    transformar(a.anio, a.trimestre)
