# COTEL: ontología y grafo de conocimiento de datos públicos de telecomunicaciones (caso Claro Colombia)

Prototipo funcional del proyecto de grado descrito en `01_Propuesta_Proyecto_Grado.md`.
Usa **solo datos públicos**: MinTIC en datos.gov.co, información societaria pública y entidades reguladoras.

## Estructura

```
ontologia-claro/
├── 01_Propuesta_Proyecto_Grado.md   Documento académico (propuesta, metodología, resultados, cronograma)
├── ontologia/
│   ├── cotel.ttl                    Ontología OWL 2 DL (reutiliza ORG, qb, SKOS, OWL-Time, GeoSPARQL, DCAT, PROV-O)
│   └── cotel-shapes.ttl             Formas SHACL de calidad de datos
├── datos/
│   ├── base_curada.ttl              Grupo América Móvil, Comcel, Telmex, reguladores, fuentes DCAT
│   ├── crudo_internet_fijo_*.csv    Descarga original de MinTIC (dataset n48w-gutb)
│   └── cotel_internet_fijo_*.ttl    Grafo RDF generado
├── pipeline/
│   ├── 01_descargar.py              Descarga por API Socrata (paginada)
│   ├── 02_transformar_rdf.py        ETL CSV → RDF (mapeo de tecnologías dirigido por la ontología)
│   ├── 03_validar_razonar_consultar.py  SHACL por lotes + OWL 2 RL + preguntas de competencia
│   ├── 04_verificar_owl_dl.py       Consistencia OWL 2 DL con HermiT (requiere Java)
│   └── test_pipeline.py             Pruebas unitarias (pytest)
├── consultas/CQ1..CQ8 *.rq          Preguntas de competencia en SPARQL
└── resultados/                      CSV por consulta, reporte SHACL, resumen.json, verificacion_owl_dl.json
```

## Instalación

Requiere Python 3.10 o superior. Para el paso 04 se necesita además Java 8 o superior.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install rdflib pyshacl requests pytest owlready2
```

## Ejecución

```powershell
$env:PYTHONIOENCODING="utf-8"
python pipeline\01_descargar.py --anio 2023 --trimestre 3   # ~1 min; descarga unas 209 mil filas
python pipeline\02_transformar_rdf.py                       # ~1 min; genera unas 312 mil tripletas
python -m pytest -q pipeline                                 # 15 pruebas
python pipeline\03_validar_razonar_consultar.py             # ~12 min (SHACL completo + razonamiento + consultas)
python pipeline\03_validar_razonar_consultar.py --solo-consultas   # solo las consultas (~1-2 min)
python pipeline\04_verificar_owl_dl.py --municipio 11001    # HermiT sobre una muestra (~1 min)
```

## Cargar en un triplestore (para el producto final)

1. Instala **Apache Jena Fuseki** o **GraphDB Free**.
2. Crea un repositorio y carga `ontologia/cotel.ttl`, `datos/base_curada.ttl` y `datos/cotel_internet_fijo_2023T3.ttl`.
3. En GraphDB, activa el conjunto de reglas **OWL2-RL** para que el razonamiento ocurra en el servidor.
4. Ejecuta las consultas de `consultas/` desde la interfaz web o conecta Power BI o un tablero al punto de consulta SPARQL.

## Explorar la ontología

- Abre `ontologia/cotel.ttl` en **Protégé** y ejecuta el razonador HermiT (Reasoner → HermiT → Start).
- Evalúa la ontología con **OOPS!** (https://oops.linkeddata.es) y **FOOPS!** (https://foops.linkeddata.es).
- Genera la documentación HTML con **WIDOCO**.

## Notas de calidad de datos

- La API de MinTIC entrega las velocidades como texto con coma decimal. El ETL las convierte y agrega los datos localmente.
- Hay velocidades atípicas en la fuente (hasta 500.000 Mbps). SHACL las marca como advertencia (más de 10.000 Mbps) y CQ5 las excluye.
- Claro (Comcel) reporta sus accesos fijos como **CABLE** (HFC) e inalámbricos, no como FTTH. Por eso CQ6 analiza la fibra de la competencia como amenaza.
- Hay datos marcados como **VERIFICAR** en `base_curada.ttl` (NIT, fecha de fusión Telmex-Comcel, licencia del dataset) que deben confirmarse antes de publicar.
