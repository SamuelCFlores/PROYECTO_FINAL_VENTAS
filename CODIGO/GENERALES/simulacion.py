"""
simulacion.py  
=================
Genera 6 meses de ventas realistas para el sistema de registro de ventas.
Patron comercial:
  - Fines de semana: 2-3x mas ventas que entre semana.
  - Quincenas (dias 1, 15, ultimo del mes): flujo maximo.
  - Variacion de precio +-5%.
  - Horario 7:00-15:00.
  - Variacion estacional: mes 1 normal, meses 2-3 baja, meses 4-6 alta
    (simula temporada alta de verano/fiestas).
  - Los datos cubren desde FECHA_INICIO por 6 meses.
  - Una categoria madre por semana (4 por mes, 24 en total).

NOTA: Si cargar la simulacion como se esta planteado es complejo, se genera la simulacion corriendo el código
y despues se cambia el nombre del archivo de datos generado a "sim_6m.json" a "datos.json" para que lo cargue.

"""

import random
import sys
import os
from datetime import datetime, timedelta
from calendar import monthrange

sys.path.insert(0, os.path.dirname(__file__))
from modelo import SistemaVentas, CategoriaMadre, Derivado, RegistroVenta

# ── Configuración ──────────────────────────────────────────────────────────────
SEMILLA        = 42
MESES          = 6
FECHA_INICIO   = "2025-12-01"   # 6 meses que incluyen datos historicos

PRECIOS = {
    "Cecina":          180.0,
    "Carne enchilada": 160.0,
    "Chorizo":         140.0,
    "Cabeza":           45.0,
}

CANTIDADES = {
    "Cecina":          (0.250, 1.500),
    "Carne enchilada": (0.250, 1.200),
    "Chorizo":         (0.250, 0.800),
    "Cabeza":          (1,     4),
}

# Ventas promedio por tipo de dia
PATRONES_BASE = {
    "semana":    {"Cecina": 4, "Carne enchilada": 3, "Chorizo": 3, "Cabeza": 2},
    "finsemana": {"Cecina": 9, "Carne enchilada": 7, "Chorizo": 6, "Cabeza": 8},
    "quincena":  {"Cecina": 12,"Carne enchilada": 9, "Chorizo": 8, "Cabeza": 10},
}

# Factor estacional por mes del año (1=normal, >1=temporada alta, <1=baja)
FACTOR_MES = {
    1: 0.85,   # enero: baja post-fiestas
    2: 0.80,   # febrero: baja
    3: 0.90,   # marzo: normal
    4: 1.10,   # abril: semana santa
    5: 1.05,   # mayo: dia de la madre
    6: 1.00,   # junio: normal
    7: 1.05,   # julio
    8: 1.00,
    9: 0.95,
    10: 1.00,
    11: 1.15,  # noviembre: buen fin
    12: 1.30,  # diciembre: temporada alta
}

COSTO_SEMANAL_BASE = 7500.0  # costo de cada puerco semanal


def _tipo_dia(fecha: datetime) -> str:
    dia_mes = fecha.day
    ultimo  = monthrange(fecha.year, fecha.month)[1]
    if dia_mes in (1, 15, ultimo):
        return "quincena"
    if fecha.weekday() >= 5:
        return "finsemana"
    return "semana"


def _hora_aleatoria(fecha: datetime) -> str:
    h = random.randint(7, 14)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return fecha.replace(hour=h, minute=m, second=s).strftime("%Y-%m-%d %H:%M:%S")


def _cantidad(nombre: str) -> float:
    mn, mx = CANTIDADES[nombre]
    if nombre == "Cabeza":
        return float(random.randint(int(mn), int(mx)))
    raw = random.uniform(mn, mx)
    return round(round(raw / 0.05) * 0.05, 3)


def _precio_var(base: float) -> float:
    return round(base * random.uniform(0.95, 1.05), 2)


def _nombre_cat(fecha: datetime, semana_del_mes: int) -> str:
    return f"Puerco {fecha.strftime('%b %Y')} S{semana_del_mes}"


def _semana_del_mes(fecha: datetime) -> int:
    return min((fecha.day - 1) // 7 + 1, 4)


def cargar_simulacion(sistema: SistemaVentas, sobrescribir: bool = False) -> None:
    """
    Carga 6 meses de datos simulados en el sistema.
    Si sobrescribir=True limpia todas las categorias existentes primero.
    """
    random.seed(SEMILLA)

    if sobrescribir:
        sistema.categorias = []
        sistema.guardar_datos()

    nombres_existentes = {c.nombre for c in sistema.categorias}
    cats_cache: dict[str, CategoriaMadre] = {}   # nombre -> objeto

    fecha_ini = datetime.strptime(FECHA_INICIO, "%Y-%m-%d")
    fecha_fin = fecha_ini + timedelta(days=MESES * 30)
    fecha_cur = fecha_ini

    while fecha_cur < fecha_fin:
        sem    = _semana_del_mes(fecha_cur)
        nombre = _nombre_cat(fecha_cur, sem)
        factor = FACTOR_MES.get(fecha_cur.month, 1.0)

        # Crear/recuperar categoría de esta semana
        if nombre not in cats_cache:
            if nombre in nombres_existentes:
                cat = next(c for c in sistema.categorias if c.nombre == nombre)
            else:
                # Costo varia ligeramente semana a semana
                costo = round(COSTO_SEMANAL_BASE * random.uniform(0.92, 1.08), 2)
                cat   = sistema.agregar_categoria(nombre, fecha_cur.strftime("%Y-%m-%d"), costo)
                nombres_existentes.add(nombre)
                # Agregar derivados
                for prod, precio in PRECIOS.items():
                    tipo = "pieza" if prod == "Cabeza" else "kg"
                    sistema.agregar_derivado(cat.id_categoria, prod, tipo, precio)
            cats_cache[nombre] = cat

        cat    = cats_cache[nombre]
        tipo_d = _tipo_dia(fecha_cur)
        patron = PATRONES_BASE[tipo_d]

        for der in cat.derivados:
            base_n   = patron.get(der.nombre, 2)
            n_ventas = max(0, round(base_n * factor) + random.randint(-2, 2))
            for _ in range(n_ventas):
                cant     = _cantidad(der.nombre)
                precio   = _precio_var(der.precio_unitario)
                ts       = _hora_aleatoria(fecha_cur)
                subtotal = round(cant * precio, 2)
                max_n    = max(
                    (int(v.id_venta.split("_")[1]) for v in der.ventas
                     if v.id_venta.startswith("V_")),
                    default=0,
                )
                der.ventas.append(RegistroVenta(
                    id_venta=f"V_{max_n+1}", fecha_hora=ts,
                    cantidad=cant, precio_aplicado=precio, subtotal=subtotal,
                ))
                der.calcular_total_vendido()

        fecha_cur += timedelta(days=1)

    sistema.guardar_datos()
    total_tx  = sum(len(d.ventas) for c in sistema.categorias for d in c.derivados)
    total_ing = sum(v.subtotal for c in sistema.categorias
                    for d in c.derivados for v in d.ventas)
    print(f"[Simulacion] 6 meses cargados | "
          f"Categorias: {len(sistema.categorias)} | "
          f"Transacciones: {total_tx} | "
          f"Ingreso: ${total_ing:,.2f}")


if __name__ == "__main__":
    s = SistemaVentas("sim_6m")
    cargar_simulacion(s, sobrescribir=True)
