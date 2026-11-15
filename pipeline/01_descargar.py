"""Descarga datos abiertos de accesos a Internet fijo (MinTIC, datos.gov.co n48w-gutb).

Uso: python 01_descargar.py --anio 2023 --trimestre 3
Salida: datos/crudo_internet_fijo_<anio>T<trimestre>.csv
"""
import argparse
import csv
import time
from pathlib import Path

import requests

DATASET = "n48w-gutb"
URL = f"https://www.datos.gov.co/resource/{DATASET}.json"
COLUMNAS = [
    "anno", "trimestre", "proveedor", "cod_departamento", "departamento",
    "cod_municipio", "municipio", "segmento", "tecnologia",
    "velocidad_bajada", "velocidad_subida", "no_de_accesos",
]
PAGINA = 50000
RAIZ = Path(__file__).resolve().parent.parent


def descargar(anio: str, trimestre: str) -> Path:
    salida = RAIZ / "datos" / f"crudo_internet_fijo_{anio}T{trimestre}.csv"
    salida.parent.mkdir(exist_ok=True)
    filas, offset = [], 0
    while True:
        params = {
            "$select": ",".join(COLUMNAS),
            "$where": f"anno='{anio}' AND trimestre='{trimestre}'",
            "$order": ":id",
            "$limit": PAGINA,
            "$offset": offset,
        }
        for intento in range(4):
            try:
                r = requests.get(URL, params=params, timeout=180)
                r.raise_for_status()
                break
            except requests.RequestException:
                if intento == 3:
                    raise
                time.sleep(5 * (intento + 1))
        lote = r.json()
        filas.extend(lote)
        print(f"  {len(filas):>8} filas")
        if len(lote) < PAGINA:
            break
        offset += PAGINA
    with salida.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in COLUMNAS})
    print(f"Guardado {salida} ({len(filas)} filas)")
    return salida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", default="2023")
    ap.add_argument("--trimestre", default="3")
    a = ap.parse_args()
    descargar(a.anio, a.trimestre)
