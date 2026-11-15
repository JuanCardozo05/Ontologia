"""Genera los gráficos del documento explicativo y lo convierte a PDF con Microsoft Edge (headless).

Uso: python docs/generar_pdf.py
"""
import csv
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DOCS = Path(__file__).resolve().parent
RAIZ = DOCS.parent
RES = RAIZ / "resultados"
IMG = DOCS / "img"
IMG.mkdir(exist_ok=True)

ROJO = "#DA291C"
GRIS = "#8A8F98"
OSCURO = "#2B2D33"
AZUL = "#1F5FA8"
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#BBBBBB"})

NOMBRES = {
    "COMUNICACION CELULAR S A COMCEL S A": "Claro (Comcel)",
    "UNE EPM TELECOMUNICACIONES S.A.": "Tigo-UNE",
    "COLOMBIA TELECOMUNICACIONES S.A. E.S.P.": "Movistar",
    "EMPRESA DE TELECOMUNICACIONES DE BOGOTA S.A. ESP": "ETB",
    "DIRECTV COLOMBIA LTDA": "DirecTV",
}


def leer(nombre):
    with open(RES / nombre, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(IMG / nombre, dpi=200)
    plt.close(fig)


def grafico_cq1():
    filas = leer("CQ1_participacion_nacional.csv")
    nombres = [NOMBRES.get(f["proveedor"], f["proveedor"]) for f in filas]
    pct = [float(f["participacionPct"]) for f in filas]
    nombres.append("Otros (≈1.000 proveedores)")
    pct.append(round(100 - sum(pct), 2))
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    colores = [ROJO] + [GRIS] * (len(pct) - 1)
    barras = ax.barh(nombres[::-1], pct[::-1], color=colores[::-1])
    for b, v in zip(barras, pct[::-1]):
        ax.text(b.get_width() + 0.6, b.get_y() + b.get_height() / 2, f"{v:.2f} %".replace(".", ","), va="center")
    ax.set_xlabel("Participación en accesos de internet fijo (%)")
    ax.set_xlim(0, 45)
    ax.set_title("CQ1 · Participación nacional, internet fijo 2023-T3", loc="left", fontweight="bold")
    guardar(fig, "cq1.png")


def grafico_cq2():
    filas = leer("CQ2_participacion_departamento.csv")[:12]
    nombres = ["San Andrés" if f["departamento"].startswith("Archip") else f["departamento"] for f in filas]
    pct = [float(f["participacionClaroPct"]) for f in filas]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.bar(nombres, pct, color=ROJO)
    for i, v in enumerate(pct):
        ax.text(i, v + 1, f"{v:.1f}".replace(".", ","), ha="center", fontsize=8)
    ax.axhline(36.24, color=OSCURO, ls="--", lw=1, label="Promedio nacional de Claro (36,2 %)")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.set_ylabel("Participación de Claro (%)")
    ax.set_ylim(0, 66)
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right", fontsize=8)
    ax.set_title("CQ2 · Departamentos con mayor participación de Claro", loc="left", fontweight="bold")
    guardar(fig, "cq2.png")


def grafico_cq3():
    filas = leer("CQ3_claro_por_familia_tecnologica.csv")
    valores = [int(list(f.values())[1]) for f in filas]
    etiquetas = ["Cable coaxial (HFC)", "Inalámbrica fija"]
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    ax.pie(valores, colors=[ROJO, GRIS], startangle=90, wedgeprops={"width": 0.38, "edgecolor": "white"})
    total = sum(valores)
    ax.text(0, 0, f"{total / 1e6:.2f} M\naccesos".replace(".", ","), ha="center", va="center", fontweight="bold")
    ax.legend([f"{e}: {v / total * 100:.1f} %".replace(".", ",") for e, v in zip(etiquetas, valores)],
              loc="lower center", bbox_to_anchor=(0.5, -0.22), frameon=False, fontsize=8)
    ax.set_title("CQ3 · Claro por familia tecnológica", fontweight="bold", fontsize=10)
    guardar(fig, "cq3.png")


def grafico_cq4():
    filas = leer("CQ4_oportunidad_sin_presencia.csv")[:10]
    nombres = [f"{f['municipio']} ({f['departamento']})" for f in filas]
    acc = [int(f["accesosMercado"]) for f in filas]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.barh(nombres[::-1], acc[::-1], color=AZUL)
    for i, v in enumerate(acc[::-1]):
        ax.text(v + 150, i, f"{v:,}".replace(",", "."), va="center", fontsize=8)
    ax.set_xlabel("Accesos de internet fijo del mercado (sin Claro)")
    ax.set_xlim(0, 13500)
    ax.set_title("CQ4 · Municipios con demanda y sin presencia de Claro", loc="left", fontweight="bold")
    guardar(fig, "cq4.png")


def grafico_cq5():
    filas = leer("CQ5_velocidad_por_estrato.csv")
    orden = [f"Residencial estrato {i}" for i in range(1, 7)] + ["Corporativo"]
    datos = {(f["segmento"], f["grupo"]): float(f["velocidadBajadaMbps"]) for f in filas}
    x = range(len(orden))
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.bar([i - 0.2 for i in x], [datos[(s, "Claro")] for s in orden], 0.4, color=ROJO, label="Claro")
    ax.bar([i + 0.2 for i in x], [datos[(s, "Resto del mercado")] for s in orden], 0.4, color=GRIS,
           label="Resto del mercado")
    ax.set_xticks(list(x), ["E1", "E2", "E3", "E4", "E5", "E6", "Corp."])
    ax.set_ylabel("Velocidad de bajada de plan (Mbps)")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("CQ5 · Velocidad promedio ponderada por estrato", loc="left", fontweight="bold")
    guardar(fig, "cq5.png")


def grafico_cq6():
    filas = leer("CQ6_amenaza_fibra_competencia.csv")[:10]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for f in filas:
        x, y = float(f["participacionClaroPct"]), float(f["fibraCompetenciaPct"])
        tam = max(30, int(f["accesosClaro"]) / 2500)
        ax.scatter(x, y, s=tam, color=ROJO, alpha=0.55, edgecolor=ROJO)
        nombre = "Bogotá" if f["municipio"].startswith("Bogot") else f["municipio"]
        desfase = (14, 6) if nombre == "Bogotá" else (6, 4)
        ax.annotate(nombre, (x, y), textcoords="offset points", xytext=desfase, fontsize=8)
    ax.set_xlabel("Participación de Claro en el municipio (%)")
    ax.set_ylabel("% de accesos de la competencia en fibra")
    ax.set_xlim(25, 55)
    ax.set_ylim(66, 82)
    ax.set_title("CQ6 · Amenaza de fibra de la competencia (tamaño = accesos de Claro)", loc="left",
                 fontweight="bold")
    guardar(fig, "cq6.png")


def diagrama_ontologia():
    fig, ax = plt.subplots(figsize=(8.6, 6.0))
    ax.set_xlim(0, 12)
    ax.set_ylim(-0.5, 8)
    ax.axis("off")
    estilos = {
        "nucleo": ("#FDE7E5", ROJO), "org": ("#E6EEF8", AZUL), "terr": ("#E8F4EA", "#2E7D32"),
        "skos": ("#FFF4DE", "#B26A00"), "meta": ("#EFEAF7", "#6A4C9C"),
    }
    nodos = {
        "grupo": ("GrupoEmpresarial\n(América Móvil)", 1.5, 7.2, "org"),
        "marca": ("MarcaComercial\n(Claro)", 4.2, 7.2, "org"),
        "regul": ("EntidadRegulatoria\n(MinTIC, CRC, ANE, SIC)", 7.0, 7.2, "org"),
        "fuente": ("FuenteDatos\n(dcat:Dataset)", 10.4, 7.2, "meta"),
        "prov": ("ProveedorRedesServicios\n(Comcel, Telmex, ETB…)", 4.2, 5.5, "org"),
        "trim": ("Trimestre\n(time:Interval)", 10.4, 5.5, "meta"),
        "obs": ("ObservacionAccesos\n(qb:Observation)\nnumeroAccesos · velocidades", 7.0, 3.8, "nucleo"),
        "tec": ("TecnologiaAcceso\n(skos:Concept)", 10.4, 3.8, "skos"),
        "fam": ("Familia tecnológica\n(fibra, coaxial, cobre…)", 10.4, 2.2, "skos"),
        "seg": ("SegmentoMercado\n(estratos, corporativo)", 7.6, 1.0, "skos"),
        "mun": ("Municipio\n(1.117, código DANE)", 1.6, 2.6, "terr"),
        "dep": ("Departamento", 1.6, 1.0, "terr"),
        "pais": ("País (Colombia)", 4.4, 1.0, "terr"),
    }
    artistas = {}
    for k, (txt, x, y, mod) in nodos.items():
        fondo, borde = estilos[mod]
        artistas[k] = ax.text(x, y, txt, ha="center", va="center", fontsize=7.6,
                              fontweight="bold" if k == "obs" else "normal",
                              bbox=dict(boxstyle="round,pad=0.45", fc=fondo, ec=borde, lw=1.6 if k == "obs" else 1))
    aristas = [
        ("obs", "prov", "reportadoPor"), ("obs", "trim", "enPeriodo"), ("obs", "fuente", "tieneFuente"),
        ("obs", "tec", "usaTecnologia"), ("obs", "seg", "enSegmento"), ("obs", "mun", "enMunicipio"),
        ("prov", "grupo", "esSubsidiariaDe"), ("prov", "marca", "operaMarca"), ("prov", "regul", "reguladoPor"),
        ("tec", "fam", "skos:broader"), ("mun", "dep", "perteneceADepartamento"), ("dep", "pais", "ubicadoEn"),
    ]
    for a, b, etiqueta in aristas:
        ta, tb = artistas[a], artistas[b]
        ax.annotate("", xy=(0.5, 0.5), xycoords=tb, xytext=(0.5, 0.5), textcoords=ta,
                    arrowprops=dict(arrowstyle="-|>", color="#555555", lw=1,
                                    patchA=ta.get_bbox_patch(), patchB=tb.get_bbox_patch()))
        xa, ya = nodos[a][1], nodos[a][2]
        xb, yb = nodos[b][1], nodos[b][2]
        ax.text((xa + xb) / 2, (ya + yb) / 2, etiqueta, fontsize=7, style="italic", color="#333333",
                ha="center", va="center", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    leyenda = [("Núcleo (RDF Data Cube)", "nucleo"), ("Organizaciones (ORG)", "org"),
               ("Territorio (GeoSPARQL)", "terr"), ("Taxonomías (SKOS)", "skos"),
               ("Tiempo y procedencia", "meta")]
    for i, (t, m) in enumerate(leyenda):
        fondo, borde = estilos[m]
        ax.text(0.1 + i * 2.4, -0.25, t, fontsize=6.8, va="center",
                bbox=dict(boxstyle="round,pad=0.3", fc=fondo, ec=borde))
    guardar(fig, "ontologia.png")


def a_pdf():
    edge = next((p for p in [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                             Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")] if p.exists()), None)
    if edge is None:
        raise SystemExit("No se encontró Microsoft Edge; abre docs/como_funciona.html e imprime a PDF.")
    salida = RAIZ / "COTEL_Como_funciona.pdf"
    html = DOCS / "como_funciona.html"
    perfil = DOCS / ".edge-perfil"
    subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--user-data-dir={perfil}", f"--print-to-pdf={salida}", html.as_uri()],
                   check=True, timeout=180)
    print("PDF:", salida, f"({salida.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    grafico_cq1()
    grafico_cq2()
    grafico_cq3()
    grafico_cq4()
    grafico_cq5()
    grafico_cq6()
    diagrama_ontologia()
    a_pdf()
