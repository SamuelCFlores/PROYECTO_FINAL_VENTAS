"""
analytics.py
================
Modulo de analisis de datos, visualizacion y reportes PDF.
Completamente desacoplado del frontend.
"""

import os
import sys
from datetime import datetime, timedelta, date
import calendar

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
from fpdf import FPDF

# ── Paleta ─────────────────────────────────────────────────────────────────────
COLORES = ["#3B82F6","#22C55E","#F59E0B","#EF4444",
           "#8B5CF6","#06B6D4","#F97316","#EC4899"]

plt.rcParams.update({
    "figure.facecolor": "#1A1A1A",
    "axes.facecolor":   "#242424",
    "axes.edgecolor":   "#2E2E2E",
    "text.color":       "#F5F5F5",
    "axes.labelcolor":  "#A0A0A0",
    "xtick.color":      "#A0A0A0",
    "ytick.color":      "#A0A0A0",
    "grid.color":       "#2E2E2E",
    "grid.linewidth":   0.5,
    "font.family":      "DejaVu Sans",
})


# ══════════════════════════════════════════════════════════════════════════════
# CLASE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class Analitica:
    """
    Recibe ventas como lista de dicts (sistema.todas_las_ventas())
    y la lista de CategoriaMadre.

    Filtros soportados:
      filtro="semana"           → ultimos 7 dias
      filtro="mes"              → ultimos 30 dias
      filtro="semestre"         → ultimos 180 dias
      filtro=("mes_esp", 2026, 3)  → marzo 2026
      filtro=("semana_esp", "2026-03-10")  → semana que contiene esa fecha
      filtro=("rango", "2026-01-01", "2026-03-31")  → rango personalizado
      filtro=None               → todo el historico
    """

    def __init__(self, ventas_raw: list, categorias: list, nombre_comercio: str = "Mi Negocio"):
        self.categorias      = categorias
        self.nombre_comercio = nombre_comercio
        self._tmp_imgs: list[str] = []
        self.df_raw = pd.DataFrame(ventas_raw) if ventas_raw else pd.DataFrame()
        if not self.df_raw.empty:
            self.df_raw["fecha"]    = pd.to_datetime(self.df_raw["fecha"])
            self.df_raw["hora"]     = self.df_raw["hora"].astype(int)
            self.df_raw["subtotal"] = self.df_raw["subtotal"].astype(float)
            self.df_raw["cantidad"] = self.df_raw["cantidad"].astype(float)

    # ── Filtrado ───────────────────────────────────────────────────────────────

    def _filtrar(self, filtro) -> pd.DataFrame:
        if self.df_raw.empty:
            return self.df_raw.copy()
        df  = self.df_raw.copy()
        hoy = pd.Timestamp.now().normalize()

        if filtro is None:
            return df
        if filtro == "semana":
            return df[df["fecha"] >= hoy - timedelta(days=7)]
        if filtro == "mes":
            return df[df["fecha"] >= hoy - timedelta(days=30)]
        if filtro == "semestre":
            return df[df["fecha"] >= hoy - timedelta(days=180)]

        if isinstance(filtro, tuple):
            tipo = filtro[0]
            if tipo == "mes_esp" and len(filtro) == 3:
                _, anio, mes = filtro
                ini = pd.Timestamp(anio, mes, 1)
                fin = pd.Timestamp(anio, mes, calendar.monthrange(anio, mes)[1])
                return df[(df["fecha"] >= ini) & (df["fecha"] <= fin)]
            if tipo == "semana_esp" and len(filtro) == 2:
                ref = pd.Timestamp(filtro[1])
                ini = ref - timedelta(days=ref.weekday())
                fin = ini + timedelta(days=6)
                return df[(df["fecha"] >= ini) & (df["fecha"] <= fin)]
            if tipo == "rango" and len(filtro) == 3:
                ini = pd.Timestamp(filtro[1])
                fin = pd.Timestamp(filtro[2])
                return df[(df["fecha"] >= ini) & (df["fecha"] <= fin)]
        return df

    def etiqueta_filtro(self, filtro) -> str:
        """Devuelve texto descriptivo del filtro para el PDF (solo ASCII)."""
        if filtro is None:
            return "Historico completo"
        if filtro == "semana":
            return "Ultima semana"
        if filtro == "mes":
            return "Ultimo mes"
        if filtro == "semestre":
            return "Ultimos 6 meses"
        if isinstance(filtro, tuple):
            t = filtro[0]
            if t == "mes_esp":
                return f"{calendar.month_name[filtro[2]]} {filtro[1]}"
            if t == "semana_esp":
                ref = datetime.strptime(filtro[1], "%Y-%m-%d")
                ini = ref - timedelta(days=ref.weekday())
                fin = ini + timedelta(days=6)
                return f"Semana {ini.strftime('%d/%m')} - {fin.strftime('%d/%m/%Y')}"
            if t == "rango":
                return f"{filtro[1]}  al  {filtro[2]}"
        return "Periodo seleccionado"

    # ── Métricas generales ─────────────────────────────────────────────────────

    def metricas_generales(self, filtro=None) -> dict:
        df = self._filtrar(filtro)
        if df.empty:
            return {"total_ingresos": 0.0, "num_transacciones": 0,
                    "ticket_promedio": 0.0, "dia_mas_ventas": "-",
                    "derivado_top": "-", "hora_pico": "-"}
        por_dia  = df.groupby("fecha")["subtotal"].sum()
        por_der  = df.groupby("derivado")["subtotal"].sum()
        por_hora = df.groupby("hora")["subtotal"].sum()
        return {
            "total_ingresos":    round(df["subtotal"].sum(), 2),
            "num_transacciones": len(df),
            "ticket_promedio":   round(df["subtotal"].mean(), 2),
            "dia_mas_ventas":    str(por_dia.idxmax().date()) if not por_dia.empty else "-",
            "derivado_top":      por_der.idxmax()  if not por_der.empty  else "-",
            "hora_pico":         f"{int(por_hora.idxmax())}:00 hrs" if not por_hora.empty else "-",
        }

    # ── Datos para tablas ──────────────────────────────────────────────────────

    def top_derivados(self, filtro=None, top_n=8) -> pd.DataFrame:
        df = self._filtrar(filtro)
        if df.empty:
            return pd.DataFrame()
        return (df.groupby("derivado")
                  .agg(total_ingresos=("subtotal","sum"),
                       transacciones=("subtotal","count"),
                       cantidad_total=("cantidad","sum"))
                  .sort_values("total_ingresos", ascending=False)
                  .head(top_n).reset_index())

    def ventas_por_dia(self, filtro=None) -> pd.DataFrame:
        df = self._filtrar(filtro)
        if df.empty:
            return pd.DataFrame()
        return (df.groupby("fecha")["subtotal"].sum()
                  .reset_index().rename(columns={"subtotal":"ingresos"}))

    def ventas_por_dia_semana(self, filtro=None) -> pd.DataFrame:
        df = self._filtrar(filtro)
        if df.empty:
            return pd.DataFrame()
        dias = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"]
        df = df.copy()
        df["dia_semana"] = df["fecha"].dt.dayofweek.map(dict(enumerate(dias)))
        return (df.groupby("dia_semana")["subtotal"].sum()
                  .reindex(dias).reset_index()
                  .rename(columns={"subtotal":"ingresos"}))

    def comparativo_inversion(self) -> pd.DataFrame:
        rows = [{"categoria": c.nombre, "invertido": c.costo_total,
                 "recuperado": c.calcular_recuperado(),
                 "porcentaje": c.porcentaje_recuperacion()}
                for c in self.categorias]
        return pd.DataFrame(rows)

    def distribucion_horaria(self, filtro=None) -> pd.DataFrame:
        df = self._filtrar(filtro)
        if df.empty:
            return pd.DataFrame()
        return (df.groupby("hora")["subtotal"].sum()
                  .reset_index().rename(columns={"subtotal":"ingresos"}))

    def ventas_por_dia_calor(self, filtro=None) -> dict:
        """
        Devuelve {fecha_str: total} para el mapa de calor del frontend.
        Las fechas son strings "YYYY-MM-DD".
        """
        df = self._filtrar(filtro)
        if df.empty:
            return {}
        return {str(k.date()): round(v, 2)
                for k, v in df.groupby("fecha")["subtotal"].sum().items()}

    # ── Gráficas ───────────────────────────────────────────────────────────────

    def _guardar_fig(self, fig, nombre: str) -> str:
        ruta = os.path.join(os.path.dirname(__file__), f"_tmp_{nombre}.png")
        fig.savefig(ruta, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        self._tmp_imgs.append(ruta)
        return ruta

    def grafica_tendencia(self, filtro=None) -> str:
        df = self.ventas_por_dia(filtro)
        if df.empty:
            return ""
        fig, ax = plt.subplots(figsize=(10, 3.5))
        ax.plot(df["fecha"], df["ingresos"], color=COLORES[0], lw=2, marker="o", ms=3)
        ax.fill_between(df["fecha"], df["ingresos"], alpha=0.12, color=COLORES[0])
        ax.set_title("Tendencia de ingresos diarios", fontsize=12, pad=8)
        ax.set_ylabel("Ingresos ($)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        fig.autofmt_xdate(rotation=40)
        fig.tight_layout()
        return self._guardar_fig(fig, "tendencia")

    def grafica_top_derivados(self, filtro=None) -> str:
        df = self.top_derivados(filtro)
        if df.empty:
            return ""
        fig, ax = plt.subplots(figsize=(8, 3.5))
        bars = ax.barh(df["derivado"], df["total_ingresos"],
                       color=COLORES[:len(df)], edgecolor="none")
        max_v = df["total_ingresos"].max()
        for bar, val in zip(bars, df["total_ingresos"]):
            ax.text(bar.get_width() + max_v * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"${val:,.0f}", va="center", fontsize=8, color="#F5F5F5")
        ax.set_title("Derivados con mayor ingreso", fontsize=12, pad=8)
        ax.set_xlabel("Ingresos ($)")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        ax.invert_yaxis()
        fig.tight_layout()
        return self._guardar_fig(fig, "top_derivados")

    def grafica_pastel_derivados(self, filtro=None) -> str:
        """Grafica de pastel con distribucion de ingresos por derivado."""
        df = self.top_derivados(filtro)
        if df.empty:
            return ""
        fig, ax = plt.subplots(figsize=(7, 5))
        wedges, texts, autotexts = ax.pie(
            df["total_ingresos"],
            labels=df["derivado"],
            autopct="%1.1f%%",
            colors=COLORES[:len(df)],
            startangle=140,
            pctdistance=0.82,
            wedgeprops=dict(width=0.6),    # donut
        )
        for t in texts:
            t.set_color("#F5F5F5")
            t.set_fontsize(9)
        for at in autotexts:
            at.set_color("#F5F5F5")
            at.set_fontsize(8)
        ax.set_title("Distribucion de ingresos por producto", fontsize=12, pad=14)
        fig.tight_layout()
        return self._guardar_fig(fig, "pastel_derivados")

    def grafica_dia_semana(self, filtro=None) -> str:
        df = self.ventas_por_dia_semana(filtro)
        if df.empty:
            return ""
        fig, ax = plt.subplots(figsize=(8, 3.5))
        colores_barra = [COLORES[1] if d in ("Sabado","Domingo") else COLORES[0]
                         for d in df["dia_semana"]]
        ax.bar(df["dia_semana"], df["ingresos"], color=colores_barra,
               edgecolor="none", width=0.6)
        ax.set_title("Ingresos por dia de la semana", fontsize=12, pad=8)
        ax.set_ylabel("Ingresos ($)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        plt.xticks(rotation=25)
        fig.tight_layout()
        return self._guardar_fig(fig, "dia_semana")

    def grafica_inversion_recuperacion(self) -> str:
        df = self.comparativo_inversion()
        if df.empty:
            return ""
        fig, ax = plt.subplots(figsize=(10, 3.8))
        x = np.arange(len(df))
        w = 0.38
        ax.bar(x - w/2, df["invertido"],  w, label="Invertido",  color=COLORES[3], edgecolor="none")
        ax.bar(x + w/2, df["recuperado"], w, label="Recuperado", color=COLORES[1], edgecolor="none")
        ax.set_xticks(x)
        ax.set_xticklabels(df["categoria"], rotation=22, ha="right", fontsize=7)
        ax.set_title("Inversion vs Recuperacion", fontsize=12, pad=8)
        ax.set_ylabel("Monto ($)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        ax.legend(facecolor="#242424", edgecolor="#2E2E2E", fontsize=8)
        fig.tight_layout()
        return self._guardar_fig(fig, "inversion")

    def grafica_horaria(self, filtro=None) -> str:
        df = self.distribucion_horaria(filtro)
        if df.empty:
            return ""
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.bar(df["hora"], df["ingresos"], color=COLORES[4], edgecolor="none", width=0.7)
        ax.set_title("Distribucion de ingresos por hora", fontsize=12, pad=8)
        ax.set_xlabel("Hora del dia")
        ax.set_ylabel("Ingresos ($)")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):02d}:00"))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        fig.tight_layout()
        return self._guardar_fig(fig, "horaria")

    def generar_todas_las_graficas(self, filtro=None) -> dict:
        return {
            "tendencia":  self.grafica_tendencia(filtro),
            "top":        self.grafica_top_derivados(filtro),
            "pastel":     self.grafica_pastel_derivados(filtro),
            "dia_semana": self.grafica_dia_semana(filtro),
            "inversion":  self.grafica_inversion_recuperacion(),
            "horaria":    self.grafica_horaria(filtro),
        }

    def limpiar_temporales(self):
        for ruta in self._tmp_imgs:
            try:
                if os.path.exists(ruta):
                    os.remove(ruta)
            except OSError:
                pass
        self._tmp_imgs.clear()

    # ══════════════════════════════════════════════════════════════════════════
    # PDF
    # ══════════════════════════════════════════════════════════════════════════

    def reporte_pdf(self, ruta_salida: str, filtro=None) -> str:
        """
        Genera reporte PDF profesional.
        ruta_salida puede incluir el nombre ya formateado, o se usa el
        nombre del comercio + fecha.
        """
        metricas = self.metricas_generales(filtro)
        graficas = self.generar_todas_las_graficas(filtro)
        comp_df  = self.comparativo_inversion()
        top_df   = self.top_derivados(filtro)
        lbl      = self.etiqueta_filtro(filtro)

        pdf = _PDFReporte(self.nombre_comercio)
        pdf.set_auto_page_break(auto=True, margin=18)

        # ── Portada ──────────────────────────────────────────────────────────
        pdf.add_page()
        pdf.portada(lbl)

        # ── Resumen ejecutivo ─────────────────────────────────────────────────
        pdf.add_page()
        pdf.seccion("1. Resumen Ejecutivo")
        pdf.kpis(metricas)
        pdf.ln(4)

        # ── Inversion vs recuperacion ─────────────────────────────────────────
        pdf.add_page()
        pdf.seccion("2. Inversion vs Recuperacion")
        if not comp_df.empty:
            pdf.tabla_df(
                comp_df.rename(columns={
                    "categoria":  "Categoria",
                    "invertido":  "Invertido ($)",
                    "recuperado": "Recuperado ($)",
                    "porcentaje": "% Recuperado",
                }),
                formato_cols={"Invertido ($)": "${:,.2f}",
                              "Recuperado ($)":"${:,.2f}",
                              "% Recuperado": "{:.1f}%"},
            )
        if graficas.get("inversion"):
            pdf.add_page()
            pdf.imagen_grafica(graficas["inversion"], "Inversion vs Recuperacion por categoria")

        # ── Top derivados ─────────────────────────────────────────────────────
        pdf.add_page()
        pdf.seccion("3. Productos con Mayor Ingreso")
        if not top_df.empty:
            pdf.tabla_df(
                top_df.rename(columns={
                    "derivado":       "Producto",
                    "total_ingresos": "Ingresos ($)",
                    "transacciones":  "Transacciones",
                    "cantidad_total": "Cantidad",
                }),
                formato_cols={"Ingresos ($)": "${:,.2f}",
                              "Cantidad":     "{:.2f}"},
            )
        if graficas.get("top"):
            pdf.imagen_grafica(graficas["top"], "Ingresos por producto")
        if graficas.get("pastel"):
            pdf.add_page()
            pdf.imagen_grafica(graficas["pastel"], "Distribucion porcentual de ingresos")

        # ── Tendencia ─────────────────────────────────────────────────────────
        pdf.add_page()
        pdf.seccion("4. Tendencia de Ingresos")
        if graficas.get("tendencia"):
            pdf.imagen_grafica(graficas["tendencia"], "Ingresos diarios en el periodo")

        # ── Comportamiento semanal ────────────────────────────────────────────
        pdf.add_page()
        pdf.seccion("5. Patron Semanal")
        if graficas.get("dia_semana"):
            pdf.imagen_grafica(graficas["dia_semana"], "Ingresos por dia de la semana")

        # ── Distribucion horaria ──────────────────────────────────────────────
        pdf.add_page()
        pdf.seccion("6. Distribucion Horaria")
        if graficas.get("horaria"):
            pdf.imagen_grafica(graficas["horaria"], "Ingresos acumulados por hora")

        # ── Interpretacion ────────────────────────────────────────────────────
        pdf.add_page()
        pdf.seccion("7. Interpretacion")
        pdf.interpretacion(metricas, comp_df, top_df, lbl)

        # ── Conclusiones ──────────────────────────────────────────────────────
        pdf.seccion("8. Conclusiones")
        pdf.conclusiones(metricas, comp_df)

        pdf.output(ruta_salida)
        self.limpiar_temporales()
        print(f"[PDF] {ruta_salida}")
        return ruta_salida


# ══════════════════════════════════════════════════════════════════════════════
# CLASE PDF 
# ══════════════════════════════════════════════════════════════════════════════

class _PDFReporte(FPDF):
    AZUL_OSC  = (13,  43, 110)
    AZUL_MED  = (26,  79, 160)
    AZUL_CLA  = (46, 117, 182)
    GRIS_CLA  = (240, 244, 252)
    GRIS_BOR  = (176, 196, 222)
    NEGRO     = (26,  26,  46)
    BLANCO    = (255, 255, 255)

    def __init__(self, nombre_comercio="Mi Negocio"):
        super().__init__()
        self._nombre_pdf = self._ascii(nombre_comercio)

    @staticmethod
    def _ascii(s: str) -> str:
        """Convierte a ASCII reemplazando caracteres especiales comunes."""
        tabla = str.maketrans(
            "áéíóúÁÉÍÓÚñÑüÜ¿¡",
            "aeiouAEIOUnNuU?!"
        )
        return s.translate(tabla).encode("ascii", "replace").decode("ascii")

    def _s(self, txt: str) -> str:
        """Sanitiza cualquier string antes de pasarlo a fpdf."""
        return self._ascii(str(txt))

    def header(self):
        self.set_fill_color(*self.AZUL_OSC)
        self.rect(0, 0, 210, 11, style="F")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.BLANCO)
        self.set_xy(10, 1.5)
        self.cell(0, 8, self._s(self._nombre_pdf) + " - Reporte de Ventas", align="L")
        self.set_xy(0, 1.5)
        self.cell(200, 8, f"Pag. {self.page_no()}", align="R")
        self.set_text_color(*self.NEGRO)

    def footer(self):
        self.set_y(-11)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*self.GRIS_BOR)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(0, 8, f"Generado: {ts}  |  {self._nombre_pdf}", align="C")
        self.set_text_color(*self.NEGRO)

    def portada(self, etiqueta_filtro: str):
        self.set_fill_color(*self.AZUL_OSC)
        self.rect(0, 0, 210, 75, style="F")
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(*self.BLANCO)
        self.set_xy(18, 18)
        self.cell(0, 13, self._s(self._nombre_pdf), align="L")
        self.set_font("Helvetica", "", 13)
        self.set_xy(18, 36)
        self.cell(0, 9, "Sistema de Registro de Ventas", align="L")
        self.set_font("Helvetica", "B", 10)
        self.set_xy(18, 52)
        self.cell(0, 8, f"Reporte Comercial  |  {self._s(etiqueta_filtro)}", align="L")

        self.set_text_color(*self.NEGRO)
        self.set_font("Helvetica", "", 10)
        self.set_xy(18, 90)
        self.multi_cell(174, 6,
            "Este reporte presenta el analisis del desempeno comercial del negocio, "
            "incluyendo metricas de ventas, recuperacion de inversion, productos "
            "con mayor rotacion y comportamiento temporal de los ingresos.",
            align="J")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(110, 110, 130)
        self.set_xy(18, 262)
        ts = datetime.now().strftime("%d/%m/%Y  %H:%M hrs")
        self.cell(0, 8, f"Generado: {ts}")

    def seccion(self, titulo: str):
        # Salto de pagina si queda poco espacio para el banner + contenido inicial
        if self.get_y() > 255:
            self.add_page()
        self.ln(4)
        self.set_fill_color(*self.AZUL_MED)
        self.set_text_color(*self.BLANCO)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 9, f"  {self._s(titulo)}", fill=True, ln=True)
        self.set_text_color(*self.NEGRO)
        self.ln(3)

    def kpis(self, m: dict):
        """
        Dibuja 6 tarjetas KPI en cuadricula 3x2.
        Usa coordenadas absolutas para evitar solapamientos.
        """
        items = [
            ("Total ingresos",  f"${m['total_ingresos']:,.2f}"),
            ("Transacciones",   str(m["num_transacciones"])),
            ("Ticket promedio", f"${m['ticket_promedio']:,.2f}"),
            ("Dia mas activo",  self._s(str(m["dia_mas_ventas"]))),
            ("Producto top",    self._s(str(m["derivado_top"]))),
            ("Hora pico",       self._s(str(m["hora_pico"]))),
        ]
        col_w  = 60    # ancho de cada tarjeta
        row_h  = 22    # alto de cada tarjeta
        col_gap = 3    # espacio entre columnas
        row_gap = 4    # espacio entre filas
        x0     = 12   # margen izquierdo
        y0     = self.get_y()   # Y de inicio (fijo, no cambia durante el loop)

        for i, (label, valor) in enumerate(items):
            col = i % 3
            row = i // 3
            cx  = x0 + col * (col_w + col_gap)
            cy  = y0 + row * (row_h + row_gap)

            # Fondo de la tarjeta
            self.set_fill_color(*self.GRIS_CLA)
            self.rect(cx, cy, col_w, row_h, style="F")
            # Barra lateral azul
            self.set_fill_color(*self.AZUL_CLA)
            self.rect(cx, cy, 2.5, row_h, style="F")

            # Etiqueta (texto gris pequeño)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(100, 100, 120)
            self.set_xy(cx + 4, cy + 3)
            self.cell(col_w - 5, 5, self._s(label))

            # Valor (texto azul grande)
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*self.AZUL_OSC)
            self.set_xy(cx + 4, cy + 10)
            self.cell(col_w - 5, 8, valor[:18])

        self.set_text_color(*self.NEGRO)
        # Avanzar cursor Y al final de las 2 filas de tarjetas
        self.set_y(y0 + 2 * (row_h + row_gap) + 4)

    def tabla_df(self, df: pd.DataFrame, formato_cols: dict | None = None):
        if df.empty:
            return
        formato_cols = formato_cols or {}
        cols  = list(df.columns)
        col_w = 186 / len(cols)

        # Salto de pagina si la tabla no cabe completa
        filas_h = min(len(df), 10) * 6 + 10
        if self.get_y() + filas_h > 277:
            self.add_page()
        self.ln(2)

        self.set_fill_color(*self.AZUL_MED)
        self.set_text_color(*self.BLANCO)
        self.set_font("Helvetica", "B", 8)
        for col in cols:
            self.cell(col_w, 7, self._s(str(col))[:20], border=0, fill=True, align="C")
        self.ln()

        self.set_font("Helvetica", "", 8)
        self.set_text_color(*self.NEGRO)
        for i, (_, row) in enumerate(df.iterrows()):
            self.set_fill_color(*self.GRIS_CLA) if i % 2 == 0 else \
                self.set_fill_color(*self.BLANCO)
            for col in cols:
                val = row[col]
                fmt = formato_cols.get(col)
                try:
                    txt = fmt.format(float(val)) if fmt else str(val)
                except (ValueError, TypeError):
                    txt = str(val)
                self.cell(col_w, 6, self._s(txt)[:20], border=0, fill=True, align="C")
            self.ln()
        self.ln(3)

    def imagen_grafica(self, ruta: str, caption: str = ""):
        if not ruta or not os.path.exists(ruta):
            return
        # Verificar espacio restante en la pagina (margen inferior = 18)
        espacio = 297 - 18 - self.get_y()
        img_h   = 80   # altura estimada de la imagen
        if espacio < img_h:
            self.add_page()
        self.image(ruta, x=11, w=187)
        if caption:
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(120, 120, 140)
            self.cell(0, 5, self._s(caption), align="C", ln=True)
            self.set_text_color(*self.NEGRO)
        self.ln(3)

    def interpretacion(self, m, comp_df, top_df, filtro_lbl):
        self.set_font("Helvetica", "", 9)
        parrafos = [
            f"Durante {self._s(filtro_lbl)} el negocio registro "
            f"{m['num_transacciones']:,} transacciones con ingreso total de "
            f"${m['total_ingresos']:,.2f} y ticket promedio de ${m['ticket_promedio']:,.2f}.",
        ]
        if not top_df.empty:
            t = top_df.iloc[0]
            parrafos.append(
                f"El producto con mayor generacion de ingresos fue "
                f"'{self._s(t['derivado'])}' con ${t['total_ingresos']:,.2f} "
                f"en {int(t['transacciones'])} transacciones."
            )
        if not comp_df.empty:
            rec = comp_df[comp_df["porcentaje"] >= 100]
            pen = comp_df[comp_df["porcentaje"] <  100]
            if len(rec) > 0:
                parrafos.append(
                    f"{len(rec)} de {len(comp_df)} categorias madre recuperaron "
                    f"el 100% de la inversion." +
                    (f" En proceso: {', '.join(self._s(n) for n in pen['categoria'].tolist())}."
                     if not pen.empty else "")
                )
        if m.get("hora_pico") and m["hora_pico"] != "-":
            parrafos.append(
                f"La hora pico fue {self._s(m['hora_pico'])}, lo que sugiere "
                f"concentrar personal y abasto en ese horario."
            )
        for p in parrafos:
            # Salto de pagina defensivo si queda poco espacio
            if self.get_y() > 260:
                self.add_page()
            self.ln(2)
            self.multi_cell(0, 5.5, p, align="J")
            self.ln(3)

    def conclusiones(self, m, comp_df):
        self.set_font("Helvetica", "", 9)
        puntos = [
            "El registro diario de ventas permite identificar patrones y anticipar necesidades de abasto.",
            "Los fines de semana y dias de quincena concentran el mayor volumen de ingresos.",
            "Los productos con baja rotacion pueden requerir ajustes de precio o estrategias de promocion.",
            "Exportar el CSV por categoria permite analisis adicionales en Excel o Google Sheets.",
        ]
        if not comp_df.empty:
            prom = comp_df["porcentaje"].mean()
            puntos.append(
                f"El porcentaje de recuperacion promedio es {prom:.1f}%, lo que indica "
                + ("un desempeno saludable." if prom >= 80
                   else "que conviene revisar los precios de algunos productos.")
            )
        for punto in puntos:
            # Salto de pagina defensivo
            if self.get_y() > 265:
                self.add_page()
            self.ln(2)
            self.set_x(14)
            self.cell(5, 5.5, "-")
            self.multi_cell(175, 5.5, self._s(punto), align="J")
            self.ln(2)


# ── Ejecucion directa ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    from modelo    import SistemaVentas
    from simulacion import cargar_simulacion
    s = SistemaVentas("test_an")
    cargar_simulacion(s, sobrescribir=True)
    an = Analitica(s.todas_las_ventas(), s.categorias, "Carniceria Don Pepe")
    an.reporte_pdf("test_reporte.pdf", filtro="mes")
    print("Listo")
    import os; os.remove("datos_test_an.json")
    os.remove("test_reporte.pdf")
