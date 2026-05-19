"""
frontend.py  
Interfaz gráfica del sistema de ventas. Implementada con Tkinter, la biblioteca
estándar de Python para GUIs. La aplicación se compone de varias ventanas y
frames que permiten al usuario interactuar con el sistema de ventas, gestionar
categorías, derivados, ventas, reportes, analytics y usuarios.

"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
import calendar as cal_lib
import sys
import os
import threading
import io

# tkcalendar NO se usa: implementamos picker propio que no flota sobre otros elementos
_TKCAL = False

sys.path.insert(0, os.path.dirname(__file__))
from modelo import SistemaVentas, GestorComercios

# ══════════════════════════════════════════════════════════════════════════════
# PALETA Y FUENTES
# ══════════════════════════════════════════════════════════════════════════════
C = {
    "bg":      "#0F0F0F", "surface":  "#1A1A1A", "surface2": "#242424",
    "border":  "#2E2E2E", "accent":   "#3B82F6", "accent_h": "#2563EB",
    "success": "#22C55E", "warning":  "#F59E0B", "danger":   "#EF4444",
    "text":    "#F5F5F5", "text2":    "#A0A0A0", "text3":    "#606060",
    "sidebar": "#111111", "sel":      "#1E3A5F",
    # mapa de calor
    "heat_none": "#1A1A1A", "heat_low": "#7F1D1D", "heat_mid": "#B45309",
    "heat_high": "#166534", "heat_top": "#22C55E",
}
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_H2    = ("Segoe UI", 13, "bold")
FONT_H3    = ("Segoe UI", 11, "bold")
FONT_BODY  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 9)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _btn(parent, text, cmd, style="primary", width=None):
    colors = {
        "primary": (C["accent"],   C["accent_h"], C["text"]),
        "success": (C["success"],  "#16A34A",     "#000"),
        "danger":  (C["danger"],   "#DC2626",     C["text"]),
        "ghost":   (C["surface2"], C["border"],   C["text2"]),
    }
    bg, hov, fg = colors.get(style, colors["primary"])
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                  activebackground=hov, activeforeground=fg,
                  font=FONT_BODY, bd=0, padx=14, pady=7,
                  cursor="hand2", relief="flat", width=width)
    b.bind("<Enter>", lambda e: b.config(bg=hov))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b

def _entry(parent, width=26, show=None):
    return tk.Entry(parent, bg=C["surface2"], fg=C["text"],
                    insertbackground=C["text"], font=FONT_BODY, bd=0,
                    highlightthickness=1, highlightcolor=C["accent"],
                    highlightbackground=C["border"], width=width, show=show)

def _label(parent, text, style="body", **kw):
    fonts  = {"title": FONT_TITLE, "h2": FONT_H2, "h3": FONT_H3,
               "body": FONT_BODY, "small": FONT_SMALL}
    colors = {"title": C["text"], "h2": C["text"], "h3": C["text"],
               "body": C["text"], "small": C["text2"]}
    return tk.Label(parent, text=text,
                    bg=kw.pop("bg", C["bg"]),
                    fg=kw.pop("fg", colors.get(style, C["text"])),
                    font=fonts.get(style, FONT_BODY), **kw)

def _separator(parent, orient="horizontal"):
    return tk.Frame(parent, bg=C["border"],
                    height=1 if orient == "horizontal" else 0,
                    width=0  if orient == "horizontal" else 1)

def _card(parent, **kw):
    return tk.Frame(parent, bg=C["surface"], bd=0,
                    highlightthickness=1, highlightbackground=C["border"], **kw)

def _tree(parent, cols, heights=13):
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Dark.Treeview",
                    background=C["surface"], fieldbackground=C["surface"],
                    foreground=C["text"], rowheight=30, font=FONT_BODY, borderwidth=0)
    style.configure("Dark.Treeview.Heading",
                    background=C["surface2"], foreground=C["text2"],
                    font=FONT_H3, borderwidth=0, relief="flat")
    style.map("Dark.Treeview",
              background=[("selected", C["sel"])],
              foreground=[("selected", C["text"])])
    tv = ttk.Treeview(parent, columns=cols, show="headings",
                      style="Dark.Treeview", height=heights)
    sb = ttk.Scrollbar(parent, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    return tv, sb

def _date_widget(parent, initial=""):
    """
    Selector de fecha propio: Entry + boton que abre mini-calendario Toplevel.
    No usa tkcalendar: el popup es un Toplevel hijo de la ventana raiz, nunca
    flota suelto ni tapa elementos inesperados.
    Devuelve (frame, get_fn) donde get_fn() retorna "YYYY-MM-DD".
    """
    import calendar as _cal

    f   = tk.Frame(parent, bg=C["bg"])
    var = tk.StringVar(value=initial or datetime.now().strftime("%Y-%m-%d"))

    row = tk.Frame(f, bg=C["bg"])
    row.pack()

    e = tk.Entry(row, textvariable=var,
                 bg=C["surface2"], fg=C["text"],
                 insertbackground=C["text"], font=FONT_BODY,
                 bd=0, highlightthickness=1,
                 highlightcolor=C["accent"], highlightbackground=C["border"],
                 width=11)
    e.pack(side="left", ipady=5)

    def _open_cal():
        # Parsear fecha actual del entry
        try:
            cur = datetime.strptime(var.get().strip(), "%Y-%m-%d")
        except ValueError:
            cur = datetime.now()

        # Estado mutable del popup
        state = {"year": cur.year, "month": cur.month}

        win = tk.Toplevel()
        win.overrideredirect(True)
        win.configure(bg=C["surface"])
        win.grab_set()

        # Posicionar junto al boton
        e.update_idletasks()
        wx = e.winfo_rootx()
        wy = e.winfo_rooty() + e.winfo_height() + 2
        win.geometry(f"+{wx}+{wy}")

        frm = tk.Frame(win, bg=C["surface"])
        frm.pack(padx=2, pady=2)

        def _render():
            for w in frm.winfo_children():
                w.destroy()

            yr, mo = state["year"], state["month"]
            # Cabecera: < Mes Año >
            hdr = tk.Frame(frm, bg=C["surface"])
            hdr.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(4,2))
            tk.Button(hdr, text="<", command=lambda: _prev(),
                      bg=C["surface"], fg=C["accent"], bd=0, font=FONT_SMALL,
                      cursor="hand2").pack(side="left", padx=4)
            tk.Label(hdr, text=f"{_cal.month_abbr[mo]} {yr}",
                     bg=C["surface"], fg=C["text"], font=FONT_H3).pack(side="left", expand=True)
            tk.Button(hdr, text=">", command=lambda: _next(),
                      bg=C["surface"], fg=C["accent"], bd=0, font=FONT_SMALL,
                      cursor="hand2").pack(side="right", padx=4)

            # Dias semana
            for ci, ds in enumerate(["L","M","X","J","V","S","D"]):
                tk.Label(frm, text=ds, bg=C["surface2"], fg=C["text2"],
                         font=FONT_SMALL, width=3, anchor="center"
                         ).grid(row=1, column=ci, padx=1, pady=1)

            # Celdas
            primer = datetime(yr, mo, 1)
            offset = primer.weekday()
            dias   = _cal.monthrange(yr, mo)[1]
            hoy    = datetime.now().date()
            fila   = 2

            for dia in range(1, dias + 1):
                col_i = (offset + dia - 1) % 7
                d_obj = datetime(yr, mo, dia).date()
                es_hoy = (d_obj == hoy)
                try:
                    sel_d = datetime.strptime(var.get().strip(), "%Y-%m-%d").date()
                    es_sel = (d_obj == sel_d)
                except ValueError:
                    es_sel = False

                if es_sel:
                    bg_c = C["accent"]; fg_c = C["text"]
                elif es_hoy:
                    bg_c = C["sel"];    fg_c = C["text"]
                elif d_obj.weekday() >= 5:
                    bg_c = C["surface"]; fg_c = C["warning"]
                else:
                    bg_c = C["surface"]; fg_c = C["text"]

                def _pick(d=dia, y=yr, m=mo):
                    var.set(f"{y:04d}-{m:02d}-{d:02d}")
                    win.destroy()

                b = tk.Button(frm, text=str(dia), bg=bg_c, fg=fg_c,
                              activebackground=C["accent_h"],
                              font=FONT_SMALL, width=3, bd=0,
                              cursor="hand2", command=_pick)
                b.grid(row=fila, column=col_i, padx=1, pady=1, ipady=2)

                if (offset + dia) % 7 == 0:
                    fila += 1

            # Boton cerrar
            tk.Button(frm, text="Cerrar", command=win.destroy,
                      bg=C["surface2"], fg=C["text2"], font=FONT_SMALL,
                      bd=0, cursor="hand2").grid(
                row=fila+1, column=0, columnspan=7, pady=(4,2), sticky="ew")

        def _prev():
            if state["month"] == 1:
                state["month"] = 12; state["year"] -= 1
            else:
                state["month"] -= 1
            _render()

        def _next():
            if state["month"] == 12:
                state["month"] = 1; state["year"] += 1
            else:
                state["month"] += 1
            _render()

        # Cerrar al hacer click fuera
        win.bind("<FocusOut>", lambda ev: win.destroy() if win.winfo_exists() else None)
        _render()

    btn = tk.Button(row, text="📅", command=_open_cal,
                    bg=C["surface2"], fg=C["text2"],
                    activebackground=C["border"], font=FONT_SMALL,
                    bd=0, padx=6, pady=5, cursor="hand2")
    btn.pack(side="left", padx=(3, 0))

    return f, lambda: var.get().strip()


# ══════════════════════════════════════════════════════════════════════════════
# SELECTOR DE COMERCIO (pantalla inicial)
# ══════════════════════════════════════════════════════════════════════════════

class SelectorComercio(tk.Tk):
    """
    Primera pantalla del sistema. Permite elegir un comercio existente
    o crear uno nuevo. Ventana con scroll para acomodar cualquier cantidad
    de comercios sin quedar cortada.
    """

    def __init__(self, gestor: GestorComercios):
        super().__init__()
        self.gestor      = gestor
        self.comercio_id = None
        self.title("Seleccionar Comercio")
        self.resizable(True, True)
        self.configure(bg=C["bg"])
        self._build()
        # Tamaño dinamico: medir contenido y ajustar ventana
        self.update_idletasks()
        h = min(self._inner.winfo_reqheight() + 20, self.winfo_screenheight() - 80)
        w = 500
        self.geometry(f"{w}x{h}")
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        # Canvas + scrollbar para manejar contenido largo
        canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(canvas, bg=C["bg"])
        win_id = canvas.create_window((0, 0), window=self._inner, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _on_resize)
        self._inner.bind("<Configure>",
                         lambda e: canvas.configure(
                             scrollregion=canvas.bbox("all")))
        # Scroll con rueda del raton
        self.bind_all("<MouseWheel>",
                      lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        p = self._inner   # alias

        tk.Label(p, text="🛒", font=("Segoe UI", 40),
                 bg=C["bg"], fg=C["accent"]).pack(pady=(28, 4))
        _label(p, "Sistema de Registro de Ventas", "title", bg=C["bg"]).pack()
        _label(p, "Selecciona o crea un comercio para continuar", "small",
               bg=C["bg"]).pack(pady=(4, 16))
        _separator(p).pack(fill="x", padx=32, pady=(0, 16))

        # ── Comercios existentes ──────────────────────────────────────────────
        if self.gestor.activos:
            _label(p, "Comercios registrados", "h3",
                   bg=C["bg"], fg=C["text2"]).pack(anchor="w", padx=32)
            self._var = tk.StringVar()
            f_list = tk.Frame(p, bg=C["bg"])
            f_list.pack(fill="x", padx=32, pady=(6, 14))
            for c in self.gestor.activos:
                row = tk.Frame(f_list, bg=C["surface"],
                               highlightthickness=1,
                               highlightbackground=C["border"])
                row.pack(fill="x", pady=3, ipady=4)
                rb = tk.Radiobutton(row,
                                    text=f"  {c.nombre}",
                                    variable=self._var, value=c.id_comercio,
                                    bg=C["surface"], fg=C["text"],
                                    selectcolor=C["accent"],
                                    activebackground=C["surface"],
                                    font=FONT_H3, cursor="hand2",
                                    anchor="w")
                rb.pack(side="left", fill="x", expand=True, padx=8)
                tk.Label(row, text=c.tipo, bg=C["surface"],
                         fg=C["text2"], font=FONT_SMALL).pack(side="right", padx=12)
            self._var.set(self.gestor.activos[0].id_comercio)
            _btn(p, "  Abrir comercio seleccionado  ",
                 self._abrir, "primary").pack(pady=(2, 14))
            _separator(p).pack(fill="x", padx=32, pady=(0, 16))

        # ── Nuevo comercio ────────────────────────────────────────────────────
        _label(p, "Nuevo comercio", "h3",
               bg=C["bg"], fg=C["text2"]).pack(anchor="w", padx=32)
        f_new = _card(p)
        f_new.pack(fill="x", padx=32, pady=(6, 0), ipadx=20, ipady=16)
        _label(f_new, "Nombre del negocio", "small",
               bg=C["surface"], fg=C["text2"]).pack(anchor="w", padx=6, pady=(0, 2))
        self.e_nombre = _entry(f_new, width=34)
        self.e_nombre.pack(pady=(0, 10), ipady=6, padx=6)
        _label(f_new, "Tipo de negocio  (ej. Carniceria, Ropa, Mariscos)", "small",
               bg=C["surface"], fg=C["text2"]).pack(anchor="w", padx=6, pady=(0, 2))
        self.e_tipo = _entry(f_new, width=34)
        self.e_tipo.pack(pady=(0, 14), ipady=6, padx=6)
        _btn(f_new, "+ Crear y abrir", self._crear, "success").pack(pady=(0, 4))

        self.lbl_err = tk.Label(p, text="", fg=C["danger"],
                                bg=C["bg"], font=FONT_SMALL)
        self.lbl_err.pack(pady=(6, 20))

    def _abrir(self):
        if hasattr(self, "_var"):
            self.comercio_id = self._var.get()
            self.destroy()

    def _crear(self):
        nombre = self.e_nombre.get().strip()
        tipo   = self.e_tipo.get().strip()
        if not nombre or not tipo:
            self.lbl_err.config(text="Completa nombre y tipo del negocio")
            return
        c = self.gestor.agregar_comercio(nombre, tipo)
        self.comercio_id = c.id_comercio
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════

class LoginWindow(tk.Tk):
    def __init__(self, sistema: SistemaVentas, nombre_comercio: str = ""):
        super().__init__()
        self.sistema  = sistema
        self.usuario  = None
        self._nombre  = nombre_comercio or "Sistema de Ventas"
        self.title(self._nombre)
        self.geometry("420x580")
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        x = (self.winfo_screenwidth()  - 420) // 2
        y = (self.winfo_screenheight() - 580) // 2
        self.geometry(f"420x580+{x}+{y}")
        self._build()

    def _build(self):
        outer = tk.Frame(self, bg=C["bg"])
        outer.place(relx=.5, rely=.5, anchor="center")
        tk.Label(outer, text="🛒", font=("Segoe UI", 44),
                 bg=C["bg"], fg=C["accent"]).pack(pady=(0, 6))
        _label(outer, self._nombre, "title", bg=C["bg"]).pack()
        _label(outer, "Inicia sesion para continuar", "small",
               bg=C["bg"]).pack(pady=(2, 24))
        card = _card(outer)
        card.pack(padx=8, pady=4, ipadx=28, ipady=24)
        _label(card, "Usuario", "small",
               bg=C["surface"], fg=C["text2"]).pack(anchor="w", padx=4, pady=(0, 2))
        self.e_user = _entry(card, width=28)
        self.e_user.pack(pady=(0, 12), ipady=6)
        _label(card, "Contrasena", "small",
               bg=C["surface"], fg=C["text2"]).pack(anchor="w", padx=4, pady=(0, 2))
        row = tk.Frame(card, bg=C["surface"])
        row.pack(pady=(0, 18))
        self.e_pass = _entry(row, width=22, show="●")
        self.e_pass.pack(side="left", ipady=6)
        self._vis = False
        tk.Button(row, text="👁", command=self._toggle,
                  bg=C["surface2"], fg=C["text2"], activebackground=C["border"],
                  font=FONT_SMALL, bd=0, padx=8, pady=6, cursor="hand2"
                  ).pack(side="left", padx=(4, 0))
        self.lbl_err = tk.Label(card, text="", fg=C["danger"],
                                bg=C["surface"], font=FONT_SMALL)
        self.lbl_err.pack(pady=(0, 6))
        _btn(card, "  Iniciar sesion  ", self._login, width=22).pack(pady=(0, 4))
        self.e_pass.bind("<Return>", lambda e: self._login())
        self.e_user.focus()

    def _toggle(self):
        self._vis = not self._vis
        self.e_pass.config(show="" if self._vis else "●")

    def _login(self):
        u = self.sistema.autenticar(
            self.e_user.get().strip(), self.e_pass.get().strip())
        if u:
            self.usuario = u
            self.destroy()
        else:
            self.lbl_err.config(text="Usuario o contrasena incorrectos")
            self.e_pass.delete(0, "end")


# ══════════════════════════════════════════════════════════════════════════════
# APP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self, sistema: SistemaVentas, usuario, nombre_comercio: str = ""):
        super().__init__()
        self.sistema   = sistema
        self.usuario   = usuario
        self._comercio = nombre_comercio
        self._frames   = {}
        self._active   = None
        self.title(f"{nombre_comercio}  |  {usuario.nombre_completo}")
        self.geometry("1120x700")
        self.minsize(920, 580)
        self.configure(bg=C["bg"])
        x = (self.winfo_screenwidth()  - 1120) // 2
        y = (self.winfo_screenheight() - 700)  // 2
        self.geometry(f"1120x700+{x}+{y}")
        self._build()
        self._show("ventas" if usuario.rol == "VENDEDOR" else "categorias")

    def _build(self):
        self.sidebar = tk.Frame(self, bg=C["sidebar"], width=205)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        _separator(self, "vertical").pack(side="left", fill="y")
        self.content = tk.Frame(self, bg=C["bg"])
        self.content.pack(side="left", fill="both", expand=True)
        self._build_sidebar()
        self._build_frames()

    def _build_sidebar(self):
        sb = self.sidebar
        hdr = tk.Frame(sb, bg=C["sidebar"])
        hdr.pack(fill="x", pady=(18, 6), padx=14)
        tk.Label(hdr, text="🛒", font=("Segoe UI", 20),
                 bg=C["sidebar"], fg=C["accent"]).pack(anchor="w")
        tk.Label(hdr, text=self._comercio, font=FONT_H2,
                 bg=C["sidebar"], fg=C["text"], wraplength=175, justify="left"
                 ).pack(anchor="w")
        tk.Label(hdr, text=self.usuario.nombre_completo, font=FONT_SMALL,
                 bg=C["sidebar"], fg=C["text2"]).pack(anchor="w")
        tk.Label(hdr, text=self.usuario.rol, font=FONT_SMALL, bg=C["sidebar"],
                 fg=C["accent"] if self.usuario.rol == "ADMIN" else C["success"]
                 ).pack(anchor="w", pady=(2, 0))
        _separator(sb).pack(fill="x", padx=14, pady=10)
        self._nav_btns = {}
        for key, label, rol_req in [
            ("categorias", "Categorias",   "ADMIN"),
            ("derivados",  "Derivados",    "ADMIN"),
            ("ventas",     "Ventas",       None),
            ("reportes",   "Reportes",     "ADMIN"),
            ("analytics",  "Analytics",    "ADMIN"),
            ("usuarios",   "Usuarios",     "ADMIN"),
        ]:
            if rol_req and self.usuario.rol != rol_req:
                continue
            b = tk.Button(sb, text=label, command=lambda k=key: self._show(k),
                          bg=C["sidebar"], fg=C["text2"],
                          activebackground=C["surface"], activeforeground=C["text"],
                          font=FONT_BODY, bd=0, padx=14, pady=9,
                          cursor="hand2", anchor="w")
            b.pack(fill="x", pady=1)
            b.bind("<Enter>", lambda e, b=b, k=key: b.config(bg=C["surface"])
                   if self._active != k else None)
            b.bind("<Leave>", lambda e, b=b, k=key: b.config(
                bg=C["sel"] if self._active == k else C["sidebar"]))
            self._nav_btns[key] = b
        tk.Frame(sb, bg=C["sidebar"]).pack(fill="y", expand=True)
        _separator(sb).pack(fill="x", padx=14, pady=6)
        tk.Button(sb, text="Cambiar comercio", command=self._cambiar_comercio,
                  bg=C["sidebar"], fg=C["text3"], font=FONT_SMALL, bd=0,
                  activebackground=C["surface2"], cursor="hand2",
                  anchor="w", padx=14, pady=7).pack(fill="x")
        tk.Button(sb, text="Cerrar sesion", command=self._logout,
                  bg=C["sidebar"], fg=C["text3"], font=FONT_SMALL, bd=0,
                  activebackground=C["surface"], activeforeground=C["text"],
                  cursor="hand2", anchor="w", padx=14, pady=9
                  ).pack(fill="x", pady=(0, 10))

    def _show(self, key):
        if self._active and self._active in self._nav_btns:
            self._nav_btns[self._active].config(bg=C["sidebar"], fg=C["text2"])
        self._active = key
        if key in self._nav_btns:
            self._nav_btns[key].config(bg=C["sel"], fg=C["text"])
        for f in self._frames.values():
            f.pack_forget()
        self._frames[key].pack(fill="both", expand=True)
        if hasattr(self._frames[key], "refresh"):
            self._frames[key].refresh()

    def _build_frames(self):
        for key, cls in [
            ("categorias", FrameCategorias),
            ("derivados",  FrameDerivados),
            ("ventas",     FrameVentas),
            ("reportes",   FrameReportes),
            ("analytics",  FrameAnalytics),
            ("usuarios",   FrameUsuarios),
        ]:
            if key in ("categorias","derivados","reportes","analytics","usuarios") \
                    and self.usuario.rol != "ADMIN":
                continue
            self._frames[key] = cls(self.content, self.sistema, self.usuario,
                                    nombre_comercio=self._comercio)

    def _logout(self):
        self.destroy()
        _reiniciar_login(self.sistema, self._comercio)

    def _cambiar_comercio(self):
        self.destroy()
        _flujo_inicio()


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: CATEGORÍAS
# ══════════════════════════════════════════════════════════════════════════════

class FrameCategorias(tk.Frame):
    def __init__(self, parent, sistema, usuario, **kw):
        super().__init__(parent, bg=C["bg"])
        self.sistema = sistema
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=26, pady=(22, 0))
        _label(hdr, "Categorias madre", "h2").pack(side="left")
        _btn(hdr, "+ Nueva categoria", self._nueva_cat).pack(side="right")
        _label(self, "Cada categoria representa una compra. Registra el costo total invertido.",
               "small", fg=C["text2"]).pack(anchor="w", padx=26, pady=(4, 14))
        _separator(self).pack(fill="x", padx=26, pady=(0, 14))
        cols = ("Nombre","Fecha compra","Invertido","Recuperado","% Recup.")
        f_tv = tk.Frame(self, bg=C["bg"])
        f_tv.pack(fill="both", expand=True, padx=26)
        self.tv, sb = _tree(f_tv, cols, heights=15)
        for col, w in zip(cols, (160,120,120,120,90)):
            self.tv.heading(col, text=col)
            self.tv.column(col, width=w, anchor="center")
        self.tv.column("Nombre", anchor="w")
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.tag_configure("ok",   foreground=C["success"])
        self.tv.tag_configure("warn", foreground=C["warning"])
        self.tv.tag_configure("low",  foreground=C["danger"])
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=26, pady=10)
        _btn(bar, "Exportar CSV", self._exportar, "ghost").pack(side="left", padx=(0,6))
        _btn(bar, "Ver detalle",  self._detalle,  "ghost").pack(side="left")
        self.refresh()

    def refresh(self):
        for r in self.tv.get_children(): self.tv.delete(r)
        for cat in self.sistema.categorias:
            rec = cat.calcular_recuperado()
            pct = cat.porcentaje_recuperacion()
            tag = "ok" if pct >= 100 else ("warn" if pct >= 50 else "low")
            self.tv.insert("", "end", iid=cat.id_categoria, tags=(tag,),
                           values=(cat.nombre, cat.fecha_compra,
                                   f"${cat.costo_total:,.2f}",
                                   f"${rec:,.2f}", f"{pct:.1f}%"))

    def _nueva_cat(self):
        dlg = _Dialog(self, "Nueva categoria madre", [
            ("Nombre (ej. Puerco, Media res)", "text"),
            ("Fecha de compra (YYYY-MM-DD)",   "text"),
            ("Costo total invertido ($)",       "number"),
        ])
        if dlg.result:
            nombre, fecha, costo = dlg.result
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
                self.sistema.agregar_categoria(nombre, fecha, float(costo))
                self.refresh()
            except ValueError:
                messagebox.showerror("Error", "Fecha invalida. Usa YYYY-MM-DD", parent=self)

    def _exportar(self):
        sel = self.tv.focus()
        if not sel:
            messagebox.showinfo("Info", "Selecciona una categoria", parent=self); return
        ruta = self.sistema.exportar_csv_categoria(sel)
        messagebox.showinfo("Exportado", f"Archivo:\n{ruta}", parent=self)

    def _detalle(self):
        sel = self.tv.focus()
        if not sel:
            messagebox.showinfo("Info", "Selecciona una categoria", parent=self); return
        cat = self.sistema.obtener_categoria(sel)
        if not cat: return
        lines = [f"Categoria:  {cat.nombre}", f"Fecha:      {cat.fecha_compra}",
                 f"Invertido:  ${cat.costo_total:,.2f}",
                 f"Recuperado: ${cat.calcular_recuperado():,.2f}",
                 f"Porcentaje: {cat.porcentaje_recuperacion():.1f}%", "", "Derivados:"]
        for d in cat.derivados:
            lines.append(f"  - {d.nombre} ({d.tipo_venta})  "
                         f"${d.precio_unitario}/u  ->  ${d.total_vendido:,.2f}")
        messagebox.showinfo(cat.nombre, "\n".join(lines), parent=self)


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: DERIVADOS
# ══════════════════════════════════════════════════════════════════════════════

class FrameDerivados(tk.Frame):
    def __init__(self, parent, sistema, usuario, **kw):
        super().__init__(parent, bg=C["bg"])
        self.sistema = sistema
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=26, pady=(22, 0))
        _label(hdr, "Derivados", "h2").pack(side="left")
        _btn(hdr, "+ Agregar derivado", self._nuevo_der).pack(side="right")
        fil = tk.Frame(self, bg=C["bg"])
        fil.pack(fill="x", padx=26, pady=(10, 6))
        _label(fil, "Categoria:", "small", fg=C["text2"]).pack(side="left", padx=(0,8))
        self.var_cat = tk.StringVar()
        self.cb_cat  = ttk.Combobox(fil, textvariable=self.var_cat,
                                    width=34, font=FONT_BODY, state="readonly")
        self.cb_cat.pack(side="left")
        self.cb_cat.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        _separator(self).pack(fill="x", padx=26, pady=(0,14))
        cols = ("Derivado","Tipo venta","Precio unit.","Total vendido","Ventas")
        f_tv = tk.Frame(self, bg=C["bg"])
        f_tv.pack(fill="both", expand=True, padx=26)
        self.tv, sb = _tree(f_tv, cols)
        for col, w in zip(cols, (180,100,120,130,70)):
            self.tv.heading(col, text=col)
            self.tv.column(col, width=w, anchor="center")
        self.tv.column("Derivado", anchor="w")
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=26, pady=8)
        _btn(bar, "Editar precio", self._editar_precio, "ghost").pack(side="left")
        self.refresh()

    def refresh(self):
        cats = self.sistema.categorias
        opts = [f"{c.nombre} ({c.fecha_compra})" for c in cats]
        self.cb_cat["values"] = opts
        if opts and not self.var_cat.get():
            self.var_cat.set(opts[0])
        idx = self.cb_cat.current()
        cat = cats[idx] if 0 <= idx < len(cats) else (cats[0] if cats else None)
        for r in self.tv.get_children(): self.tv.delete(r)
        if not cat: return
        for d in cat.derivados:
            self.tv.insert("", "end", iid=d.id_derivado,
                           values=(d.nombre, d.tipo_venta,
                                   f"${d.precio_unitario:,.2f}",
                                   f"${d.total_vendido:,.2f}", len(d.ventas)))

    def _nuevo_der(self):
        if not self.sistema.categorias:
            messagebox.showinfo("Info","Primero crea una categoria madre",parent=self); return
        cat_opts  = [f"{c.nombre} ({c.fecha_compra})" for c in self.sistema.categorias]
        tipo_opts = ["kg","gramos","pieza"]
        dlg = _Dialog(self, "Agregar derivado", [
            ("Categoria madre",              "choice", cat_opts),
            ("Nombre del derivado",          "text"),
            ("Tipo de venta",                "choice", tipo_opts),
            ("Precio unitario de venta ($)", "number"),
        ])
        if dlg.result:
            cat_label, nombre, tipo, precio = dlg.result
            cat = next((c for c in self.sistema.categorias
                        if f"{c.nombre} ({c.fecha_compra})" == cat_label), None)
            if cat:
                self.sistema.agregar_derivado(cat.id_categoria, nombre, tipo, float(precio))
                self.refresh()

    def _editar_precio(self):
        sel = self.tv.focus()
        if not sel:
            messagebox.showinfo("Info","Selecciona un derivado",parent=self); return
        cats = self.sistema.categorias
        idx  = self.cb_cat.current()
        cat  = cats[idx] if 0 <= idx < len(cats) else None
        if not cat: return
        der = cat.obtener_derivado(sel)
        if not der: return
        dlg = _Dialog(self, f"Editar precio - {der.nombre}", [
            (f"Nuevo precio (actual: ${der.precio_unitario:,.2f})", "number"),
        ])
        if dlg.result:
            ok = self.sistema.actualizar_precio_derivado(
                cat.id_categoria, der.id_derivado, float(dlg.result[0]))
            if ok: self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: VENTAS
# ══════════════════════════════════════════════════════════════════════════════

class FrameVentas(tk.Frame):
    def __init__(self, parent, sistema, usuario, **kw):
        super().__init__(parent, bg=C["bg"])
        self.sistema = sistema
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=26, pady=(22,0))
        _label(hdr, "Registro de ventas", "h2").pack(side="left")
        _separator(self).pack(fill="x", padx=26, pady=10)
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=26)

        # Formulario
        left = _card(body)
        left.pack(side="left", fill="y", padx=(0,14), pady=2, ipadx=16, ipady=16)
        _label(left, "Nueva venta", "h3", bg=C["surface"]).pack(anchor="w", pady=(0,14))
        _label(left, "Categoria madre","small",bg=C["surface"],fg=C["text2"]).pack(anchor="w")
        self.var_cat = tk.StringVar()
        self.cb_cat  = ttk.Combobox(left, textvariable=self.var_cat,
                                    width=26, font=FONT_BODY, state="readonly")
        self.cb_cat.pack(anchor="w", pady=(2,10))
        self.cb_cat.bind("<<ComboboxSelected>>", lambda e: self._cargar_derivados())
        _label(left,"Derivado","small",bg=C["surface"],fg=C["text2"]).pack(anchor="w")
        self.var_der = tk.StringVar()
        self.cb_der  = ttk.Combobox(left, textvariable=self.var_der,
                                    width=26, font=FONT_BODY, state="readonly")
        self.cb_der.pack(anchor="w", pady=(2,10))
        self.cb_der.bind("<<ComboboxSelected>>", lambda e: self._actualizar_precio())
        _label(left,"Cantidad / Peso","small",bg=C["surface"],fg=C["text2"]).pack(anchor="w")
        self.e_cant = _entry(left, width=26)
        self.e_cant.pack(anchor="w", pady=(2,3), ipady=5)
        self.e_cant.bind("<KeyRelease>", lambda e: self._actualizar_subtotal())
        self.lbl_tipo = _label(left,"","small",bg=C["surface"],fg=C["text2"])
        self.lbl_tipo.pack(anchor="w", pady=(0,10))
        _label(left,"Precio unitario ($)","small",bg=C["surface"],fg=C["text2"]).pack(anchor="w")
        self.e_precio = _entry(left, width=26)
        self.e_precio.pack(anchor="w", pady=(2,3), ipady=5)
        self.e_precio.bind("<KeyRelease>", lambda e: self._actualizar_subtotal())
        _separator(left).pack(fill="x", pady=10)
        sub_row = tk.Frame(left, bg=C["surface"])
        sub_row.pack(fill="x")
        _label(sub_row,"Subtotal:","body",bg=C["surface"]).pack(side="left")
        self.lbl_sub = tk.Label(sub_row, text="$0.00", font=FONT_H2,
                                bg=C["surface"], fg=C["accent"])
        self.lbl_sub.pack(side="right")
        self.lbl_err_v = tk.Label(left, text="", fg=C["danger"],
                                  bg=C["surface"], font=FONT_SMALL)
        self.lbl_err_v.pack(pady=6)
        _btn(left,"Registrar venta",self._registrar).pack(fill="x",pady=(0,4))
        _btn(left,"Limpiar",self._limpiar,"ghost").pack(fill="x")

        # Historial
        right = tk.Frame(body, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)
        top_r = tk.Frame(right, bg=C["bg"])
        top_r.pack(fill="x", pady=(2,6))
        _label(top_r, "Ventas de hoy", "h3").pack(side="left")
        self.lbl_total_dia = tk.Label(top_r, text="Total: $0.00",
                                      font=FONT_H3, bg=C["bg"], fg=C["success"])
        self.lbl_total_dia.pack(side="right")
        cols = ("Hora","Categoria","Derivado","Cantidad","Tipo","Precio","Subtotal")
        f_tv = tk.Frame(right, bg=C["bg"])
        f_tv.pack(fill="both", expand=True)
        self.tv_hist, sb = _tree(f_tv, cols, heights=13)
        for col, w in zip(cols, (65,105,125,65,65,80,90)):
            self.tv_hist.heading(col, text=col)
            self.tv_hist.column(col, width=w, anchor="center")
        self.tv_hist.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.refresh()

    def refresh(self):
        cats = self.sistema.categorias
        self.cb_cat["values"] = [f"{c.nombre} ({c.fecha_compra})" for c in cats]
        if cats and not self.var_cat.get():
            self.var_cat.set(self.cb_cat["values"][0])
            self._cargar_derivados()
        self._cargar_historial_hoy()

    def _cargar_derivados(self):
        idx  = self.cb_cat.current()
        cats = self.sistema.categorias
        if 0 <= idx < len(cats):
            opts = [d.nombre for d in cats[idx].derivados]
            self.cb_der["values"] = opts
            if opts:
                self.var_der.set(opts[0])
                self._actualizar_precio()

    def _actualizar_precio(self):
        ci = self.cb_cat.current(); di = self.cb_der.current()
        cats = self.sistema.categorias
        if 0 <= ci < len(cats) and 0 <= di < len(cats[ci].derivados):
            der = cats[ci].derivados[di]
            self.e_precio.delete(0,"end")
            self.e_precio.insert(0, str(der.precio_unitario))
            self.lbl_tipo.config(text=f"Tipo: {der.tipo_venta}")

    def _actualizar_subtotal(self):
        try:
            sub = round(float(self.e_cant.get()) * float(self.e_precio.get()), 2)
            self.lbl_sub.config(text=f"${sub:,.2f}")
        except ValueError:
            self.lbl_sub.config(text="$0.00")

    def _registrar(self):
        self.lbl_err_v.config(text="")
        try:
            cant = float(self.e_cant.get()); precio = float(self.e_precio.get())
        except ValueError:
            self.lbl_err_v.config(text="Ingresa cantidad y precio validos"); return
        ci = self.cb_cat.current(); di = self.cb_der.current()
        if ci < 0 or di < 0:
            self.lbl_err_v.config(text="Selecciona categoria y derivado"); return
        cat = self.sistema.categorias[ci]
        der = cat.derivados[di]
        self.sistema.registrar_venta(cat.id_categoria, der.id_derivado, cant, precio)
        self._limpiar()
        self._cargar_historial_hoy()

    def _limpiar(self):
        self.e_cant.delete(0,"end")
        self.lbl_sub.config(text="$0.00")
        self.lbl_err_v.config(text="")

    def _cargar_historial_hoy(self):
        for r in self.tv_hist.get_children(): self.tv_hist.delete(r)
        hoy = datetime.now().strftime("%Y-%m-%d")
        total = 0.0
        for cat in self.sistema.categorias:
            for der in cat.derivados:
                for v in der.ventas:
                    if v.fecha_hora.startswith(hoy):
                        self.tv_hist.insert("","end",values=(
                            v.fecha_hora[11:16], cat.nombre, der.nombre,
                            v.cantidad, der.tipo_venta,
                            f"${v.precio_aplicado:,.2f}", f"${v.subtotal:,.2f}"))
                        total += v.subtotal
        self.lbl_total_dia.config(text=f"Total: ${total:,.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: REPORTES  (con calendario, mapa de calor y gráfica de pastel)
# ══════════════════════════════════════════════════════════════════════════════

class FrameReportes(tk.Frame):
    def __init__(self, parent, sistema, usuario, **kw):
        super().__init__(parent, bg=C["bg"])
        self.sistema = sistema
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=26, pady=(22,0))
        _label(hdr, "Reportes", "h2").pack(side="left")
        _separator(self).pack(fill="x", padx=26, pady=10)

        tab_bar = tk.Frame(self, bg=C["bg"])
        tab_bar.pack(fill="x", padx=26, pady=(0,14))
        self._tab_btns   = {}
        self._tab_frames = {}
        for key, lbl in [("comparativo","Inversion vs Recuperado"),
                          ("periodo","Ventas por periodo"),
                          ("top","Top derivados")]:
            b = tk.Button(tab_bar, text=lbl, command=lambda k=key: self._show_tab(k),
                          bg=C["surface2"], fg=C["text2"], font=FONT_SMALL,
                          bd=0, padx=14, pady=7, cursor="hand2")
            b.pack(side="left", padx=(0,2))
            self._tab_btns[key] = b
        cont = tk.Frame(self, bg=C["bg"])
        cont.pack(fill="both", expand=True, padx=26)
        self._tab_frames["comparativo"] = self._build_comparativo(cont)
        self._tab_frames["periodo"]     = self._build_periodo(cont)
        self._tab_frames["top"]         = self._build_top(cont)
        self._show_tab("comparativo")

    def _show_tab(self, key):
        for k, b in self._tab_btns.items():
            b.config(bg=C["accent"] if k==key else C["surface2"],
                     fg=C["text"]   if k==key else C["text2"])
        for f in self._tab_frames.values(): f.pack_forget()
        self._tab_frames[key].pack(fill="both", expand=True)

    # ── Tab: Comparativo ──────────────────────────────────────────────────────
    def _build_comparativo(self, p):
        frame = tk.Frame(p, bg=C["bg"])
        top   = tk.Frame(frame, bg=C["bg"])
        top.pack(fill="x", pady=(0,10))
        _btn(top,"Actualizar",self._refresh_comparativo,"ghost").pack(side="right")
        cols = ("Categoria","Fecha","Invertido","Recuperado","% Recuperado","Estado")
        f_tv = tk.Frame(frame, bg=C["bg"])
        f_tv.pack(fill="both", expand=True)
        self.tv_comp, sb = _tree(f_tv, cols, heights=13)
        for col, w in zip(cols, (160,110,120,120,110,100)):
            self.tv_comp.heading(col, text=col)
            self.tv_comp.column(col, width=w, anchor="center")
        self.tv_comp.column("Categoria", anchor="w")
        self.tv_comp.tag_configure("ok",   foreground=C["success"])
        self.tv_comp.tag_configure("warn", foreground=C["warning"])
        self.tv_comp.tag_configure("low",  foreground=C["danger"])
        self.tv_comp.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return frame

    def _refresh_comparativo(self):
        for r in self.tv_comp.get_children(): self.tv_comp.delete(r)
        for item in self.sistema.reporte_comparativo():
            pct = item["porcentaje"]
            tag = "ok" if pct>=100 else ("warn" if pct>=50 else "low")
            est = "Recuperado" if pct>=100 else ("En progreso" if pct>=50 else "Bajo")
            self.tv_comp.insert("","end",tags=(tag,),
                                values=(item["nombre"],item["fecha_compra"],
                                        f"${item['costo_total']:,.2f}",
                                        f"${item['recuperado']:,.2f}",
                                        f"{pct:.1f}%", est))

    # ── Tab: Ventas por periodo ───────────────────────────────────────────────
    def _build_periodo(self, p):
        frame = tk.Frame(p, bg=C["bg"])

        # Selector de fechas: cada picker en columna propia con label arriba
        fil = tk.Frame(frame, bg=C["bg"])
        fil.pack(fill="x", pady=(0, 14))
        hoy     = datetime.now()
        ini_str = hoy.replace(day=1).strftime("%Y-%m-%d")
        fin_str = hoy.strftime("%Y-%m-%d")

        blk_d = tk.Frame(fil, bg=C["bg"])
        blk_d.pack(side="left", padx=(0, 20))
        _label(blk_d, "Desde:", "small", fg=C["text2"], bg=C["bg"]).pack(anchor="w", pady=(0,3))
        f_desde, self._get_desde = _date_widget(blk_d, ini_str)
        f_desde.pack(anchor="w")

        blk_h = tk.Frame(fil, bg=C["bg"])
        blk_h.pack(side="left", padx=(0, 20))
        _label(blk_h, "Hasta:", "small", fg=C["text2"], bg=C["bg"]).pack(anchor="w", pady=(0,3))
        f_hasta, self._get_hasta = _date_widget(blk_h, fin_str)
        f_hasta.pack(anchor="w")

        blk_btn = tk.Frame(fil, bg=C["bg"])
        blk_btn.pack(side="left")
        tk.Label(blk_btn, text=" ", bg=C["bg"], font=FONT_SMALL).pack()
        _btn(blk_btn, "Generar", self._refresh_periodo, "ghost").pack()

        # Tabla de dias
        cols = ("Fecha", "Total vendido")
        f_tv = tk.Frame(frame, bg=C["bg"])
        f_tv.pack(fill="x", pady=(0, 10))
        self.tv_per, sb = _tree(f_tv, cols, heights=6)
        for col, w in zip(cols, (220, 220)):
            self.tv_per.heading(col, text=col)
            self.tv_per.column(col, width=w, anchor="center")
        self.tv_per.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")

        # Toggle Mapa de calor / Calendario
        _separator(frame).pack(fill="x", pady=(4, 8))
        heat_hdr = tk.Frame(frame, bg=C["bg"])
        heat_hdr.pack(fill="x", pady=(0, 6))
        _label(heat_hdr, "Distribucion de ventas", "h3").pack(side="left")

        self._heat_modo = tk.StringVar(value="mapa")
        ctrl = tk.Frame(heat_hdr, bg=C["bg"])
        ctrl.pack(side="right")
        for val, lbl in [("mapa", "Mapa de calor"), ("cal", "Calendario")]:
            tk.Radiobutton(ctrl, text=lbl, variable=self._heat_modo, value=val,
                           command=self._toggle_heat_modo,
                           bg=C["bg"], fg=C["text2"], selectcolor=C["sel"],
                           activebackground=C["bg"], font=FONT_SMALL
                           ).pack(side="left", padx=4)

        # Panel mapa de calor
        self._panel_mapa = tk.Frame(frame, bg=C["bg"])
        self._panel_mapa.pack(fill="x")

        ley = tk.Frame(self._panel_mapa, bg=C["bg"])
        ley.pack(fill="x", pady=(0, 4))
        for color, lbl in [(C["heat_none"], "Sin ventas"), (C["heat_low"], "Bajas"),
                           (C["heat_mid"], "Medias"), (C["heat_high"], "Altas"),
                           (C["heat_top"], "Top")]:
            tk.Frame(ley, bg=color, width=12, height=12).pack(side="left", padx=2)
            tk.Label(ley, text=lbl, bg=C["bg"], fg=C["text2"],
                     font=FONT_SMALL).pack(side="left", padx=(0, 10))

        self.heat_canvas = tk.Canvas(self._panel_mapa, bg=C["bg"],
                                     height=185, highlightthickness=0)
        self.heat_canvas.pack(fill="x")
        self._heat_data:  dict = {}
        self._heat_rects: dict = {}
        self._tooltip_win = None
        self.heat_canvas.bind("<Motion>", self._heat_hover)
        self.heat_canvas.bind("<Leave>",  lambda e: self._tooltip_hide())

        # Panel calendario (se llena cuando el usuario cambia al modo cal)
        self._panel_cal = tk.Frame(frame, bg=C["bg"])

        return frame

    def _toggle_heat_modo(self):
        if self._heat_modo.get() == "mapa":
            self._panel_cal.pack_forget()
            self._panel_mapa.pack(fill="x")
        else:
            self._panel_mapa.pack_forget()
            self._panel_cal.pack(fill="both", expand=True)
            self._dibujar_calendario(self._get_desde(), self._get_hasta())

    def _refresh_periodo(self):
        desde = self._get_desde()
        hasta = self._get_hasta()
        for r in self.tv_per.get_children(): self.tv_per.delete(r)
        data = self.sistema.reporte_ventas_periodo(desde or None, hasta or None)
        for fecha, total in data.items():
            self.tv_per.insert("", "end", values=(fecha, f"${total:,.2f}"))
        self._heat_data = data
        if self._heat_modo.get() == "mapa":
            self._dibujar_mapa_calor(desde, hasta)
        else:
            self._dibujar_calendario(desde, hasta)

    def _dibujar_mapa_calor(self, desde: str, hasta: str):
        """Mapa de calor estilo GitHub: columnas=semanas, filas=dias L-D."""
        canvas = self.heat_canvas
        canvas.delete("all")
        self._heat_rects.clear()

        if not desde or not hasta or not self._heat_data:
            return
        try:
            d_ini = datetime.strptime(desde, "%Y-%m-%d")
            d_fin = datetime.strptime(hasta, "%Y-%m-%d")
        except ValueError:
            return

        valores = [v for v in self._heat_data.values() if v > 0]
        if not valores:
            return
        max_v = max(valores)
        p25 = max_v * 0.25
        p60 = max_v * 0.60
        p85 = max_v * 0.85

        cell  = 20
        gap   = 4
        pad_x = 28
        pad_y = 26

        dias_sem = ["L", "M", "X", "J", "V", "S", "D"]
        for i, ds in enumerate(dias_sem):
            y = pad_y + i * (cell + gap) + cell // 2
            canvas.create_text(pad_x - 5, y, text=ds,
                               fill=C["text2"], font=FONT_SMALL, anchor="e")

        lunes_ini = d_ini - timedelta(days=d_ini.weekday())
        semana    = 0
        cur_lunes = lunes_ini

        while cur_lunes <= d_fin:
            cx = pad_x + semana * (cell + gap) + cell // 2
            canvas.create_text(cx, pad_y - 13, text=cur_lunes.strftime("%d/%m"),
                               fill=C["text3"], font=("Segoe UI", 7), anchor="center")
            for dow in range(7):
                d = cur_lunes + timedelta(days=dow)
                if d_ini <= d <= d_fin:
                    fecha_str = d.strftime("%Y-%m-%d")
                    total     = self._heat_data.get(fecha_str, 0)
                    if total <= 0:
                        color = C["heat_none"]
                    elif total <= p25:
                        color = C["heat_low"]
                    elif total <= p60:
                        color = C["heat_mid"]
                    elif total <= p85:
                        color = C["heat_high"]
                    else:
                        color = C["heat_top"]
                    x1 = pad_x + semana * (cell + gap)
                    y1 = pad_y + dow   * (cell + gap)
                    rid = canvas.create_rectangle(
                        x1, y1, x1 + cell, y1 + cell,
                        fill=color, outline=C["bg"], width=1, tags="cell")
                    self._heat_rects[rid] = (fecha_str, total)
            semana    += 1
            cur_lunes += timedelta(weeks=1)

        ancho = pad_x + semana * (cell + gap) + 20
        canvas.config(width=max(ancho, 400), scrollregion=(0, 0, ancho, 185))

    def _dibujar_calendario(self, desde: str, hasta: str):
        """Vista alternativa: calendario mensual con intensidad de color."""
        for w in self._panel_cal.winfo_children():
            w.destroy()
        if not desde or not hasta or not self._heat_data:
            _label(self._panel_cal, "Genera el reporte primero", "small",
                   fg=C["text2"]).pack(pady=20)
            return
        try:
            d_ini = datetime.strptime(desde, "%Y-%m-%d")
            d_fin = datetime.strptime(hasta, "%Y-%m-%d")
        except ValueError:
            return
        valores = [v for v in self._heat_data.values() if v > 0]
        if not valores:
            return
        max_v = max(valores)
        mes_cur = d_ini.replace(day=1)
        while mes_cur <= d_fin:
            anio, mes = mes_cur.year, mes_cur.month
            dias_en_mes = cal_lib.monthrange(anio, mes)[1]
            hdr_m = tk.Frame(self._panel_cal, bg=C["bg"])
            hdr_m.pack(fill="x", padx=8, pady=(8, 2))
            _label(hdr_m, f"{cal_lib.month_name[mes]} {anio}", "h3",
                   bg=C["bg"], fg=C["accent"]).pack(side="left")
            grid = tk.Frame(self._panel_cal, bg=C["bg"])
            grid.pack(fill="x", padx=8, pady=(0, 4))
            for ci, ds in enumerate(["L","M","X","J","V","S","D"]):
                tk.Label(grid, text=ds, bg=C["bg"], fg=C["text2"],
                         font=FONT_SMALL, width=5, anchor="center").grid(
                    row=0, column=ci, padx=1, pady=1)
            primer_dia = datetime(anio, mes, 1)
            offset     = primer_dia.weekday()
            fila       = 1
            for dia in range(1, dias_en_mes + 1):
                fecha_obj = datetime(anio, mes, dia)
                col_i     = (offset + dia - 1) % 7
                if fecha_obj < d_ini or fecha_obj > d_fin:
                    tk.Label(grid, text="", bg=C["bg"], width=5).grid(
                        row=fila, column=col_i, padx=1, pady=1)
                else:
                    fecha_str = fecha_obj.strftime("%Y-%m-%d")
                    total     = self._heat_data.get(fecha_str, 0)
                    ratio     = total / max_v if max_v > 0 else 0
                    if total == 0:
                        bgc = C["heat_none"]; fgc = C["text3"]
                    elif ratio <= 0.25:
                        bgc = C["heat_low"]; fgc = C["text"]
                    elif ratio <= 0.60:
                        bgc = C["heat_mid"]; fgc = C["text"]
                    elif ratio <= 0.85:
                        bgc = C["heat_high"]; fgc = C["text"]
                    else:
                        bgc = C["heat_top"]; fgc = "#000"
                    lbl = tk.Label(grid, text=str(dia), bg=bgc, fg=fgc,
                                   font=FONT_SMALL, width=5, relief="flat",
                                   cursor="hand2")
                    lbl.grid(row=fila, column=col_i, padx=1, pady=1, ipady=3)
                    tip = f"{fecha_str}\n${total:,.2f}"
                    lbl.bind("<Enter>", lambda e, t=tip:
                             self._tooltip_show(e.x_root+12, e.y_root-8, t))
                    lbl.bind("<Leave>", lambda e: self._tooltip_hide())
                if (offset + dia) % 7 == 0:
                    fila += 1
            mes_cur = (mes_cur + timedelta(days=32)).replace(day=1)
    def _heat_hover(self, event):
        """Muestra tooltip con fecha y total al acercar el cursor a una celda."""
        items = self.heat_canvas.find_overlapping(event.x-1, event.y-1,
                                                   event.x+1, event.y+1)
        celda = next((i for i in items if i in self._heat_rects), None)
        if celda:
            fecha, total = self._heat_rects[celda]
            txt = f"{fecha}\n${total:,.2f}" if total > 0 else f"{fecha}\nSin ventas"
            self._tooltip_show(event.x_root + 14, event.y_root - 10, txt)
        else:
            self._tooltip_hide()

    def _tooltip_show(self, x, y, text):
        if self._tooltip_win:
            self._tooltip_win.destroy()
        win = tk.Toplevel(self)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{x}+{y}")
        win.configure(bg=C["surface"])
        tk.Label(win, text=text, bg=C["surface"], fg=C["text"],
                 font=FONT_SMALL, padx=8, pady=6,
                 relief="flat").pack()
        self._tooltip_win = win

    def _tooltip_hide(self):
        if self._tooltip_win:
            self._tooltip_win.destroy()
            self._tooltip_win = None

    # ── Tab: Top derivados ────────────────────────────────────────────────────
    def _build_top(self, p):
        frame = tk.Frame(p, bg=C["bg"])

        top_bar = tk.Frame(frame, bg=C["bg"])
        top_bar.pack(fill="x", pady=(0,10))
        _btn(top_bar,"Actualizar",self._refresh_top,"ghost").pack(side="right",padx=(0,6))
        # Toggle lista / grafica
        self._top_modo = tk.StringVar(value="lista")
        tk.Radiobutton(top_bar, text="Lista",   variable=self._top_modo, value="lista",
                       command=self._toggle_top_modo, bg=C["bg"], fg=C["text2"],
                       selectcolor=C["sel"], activebackground=C["bg"],
                       font=FONT_SMALL).pack(side="right", padx=4)
        tk.Radiobutton(top_bar, text="Grafica", variable=self._top_modo, value="grafica",
                       command=self._toggle_top_modo, bg=C["bg"], fg=C["text2"],
                       selectcolor=C["sel"], activebackground=C["bg"],
                       font=FONT_SMALL).pack(side="right", padx=4)

        # Panel lista
        self._top_panel_lista = tk.Frame(frame, bg=C["bg"])
        cols = ("Derivado","Categoria","Tipo venta","Total generado")
        f_tv = tk.Frame(self._top_panel_lista, bg=C["bg"])
        f_tv.pack(fill="both", expand=True)
        self.tv_top, sb = _tree(f_tv, cols, heights=13)
        for col, w in zip(cols, (180,160,110,140)):
            self.tv_top.heading(col, text=col)
            self.tv_top.column(col, width=w, anchor="center")
        self.tv_top.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._top_panel_lista.pack(fill="both", expand=True)

        # Panel grafica (embebida matplotlib)
        self._top_panel_graf = tk.Frame(frame, bg=C["bg"])
        self._top_grafica_canvas = None   # se crea al generar

        return frame

    def _toggle_top_modo(self):
        modo = self._top_modo.get()
        if modo == "lista":
            self._top_panel_graf.pack_forget()
            self._top_panel_lista.pack(fill="both", expand=True)
        else:
            self._top_panel_lista.pack_forget()
            self._top_panel_graf.pack(fill="both", expand=True)
            self._refresh_top_grafica()

    def _refresh_top(self):
        for r in self.tv_top.get_children(): self.tv_top.delete(r)
        for item in self.sistema.reporte_top_derivados(top_n=10):
            self.tv_top.insert("","end",
                               values=(item["nombre"], item["categoria"],
                                       item["tipo_venta"],
                                       f"${item['total_vendido']:,.2f}"))
        if self._top_modo.get() == "grafica":
            self._refresh_top_grafica()

    def _refresh_top_grafica(self):
        """Embebe grafica de pastel en el panel de grafica."""
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        # Limpiar canvas anterior
        for w in self._top_panel_graf.winfo_children():
            w.destroy()

        data = self.sistema.reporte_top_derivados(top_n=8)
        if not data:
            _label(self._top_panel_graf,"Sin datos","body").pack(pady=40)
            return

        nombres  = [d["nombre"]       for d in data]
        valores  = [d["total_vendido"] for d in data]
        colores  = ["#3B82F6","#22C55E","#F59E0B","#EF4444",
                    "#8B5CF6","#06B6D4","#F97316","#EC4899"]

        fig, ax = plt.subplots(figsize=(6.5, 4.5),
                               facecolor=C["bg"])
        ax.set_facecolor("#1A1A1A")
        wedges, texts, autotexts = ax.pie(
            valores, labels=nombres, autopct="%1.1f%%",
            colors=colores[:len(data)], startangle=140,
            pctdistance=0.80, wedgeprops=dict(width=0.55))
        for t in texts:
            t.set_color("#A0A0A0"); t.set_fontsize(8)
        for at in autotexts:
            at.set_color("#F5F5F5"); at.set_fontsize(7)
        ax.set_title("Distribucion de ingresos", color="#F5F5F5", fontsize=11, pad=10)
        fig.tight_layout()

        canvas_fig = FigureCanvasTkAgg(fig, master=self._top_panel_graf)
        canvas_fig.draw()
        canvas_fig.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    def refresh(self):
        self._refresh_comparativo()
        self._refresh_top()


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

class FrameAnalytics(tk.Frame):
    def __init__(self, parent, sistema, usuario, nombre_comercio="", **kw):
        super().__init__(parent, bg=C["bg"])
        self.sistema         = sistema
        self._nombre_comercio = nombre_comercio
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=26, pady=(22,0))
        _label(hdr,"Analytics","h2").pack(side="left")
        _separator(self).pack(fill="x", padx=26, pady=10)

        # Filtros
        fil = tk.Frame(self, bg=C["bg"])
        fil.pack(fill="x", padx=26, pady=(0,10))
        _label(fil,"Periodo:","small",fg=C["text2"]).pack(side="left",padx=(0,10))
        self._var_filtro = tk.StringVar(value="mes")
        for val, lbl in [("semana","Ult. semana"),("mes","Ult. mes"),
                          ("semestre","6 meses"),("mes_esp","Mes especifico"),
                          ("semana_esp","Semana especifica"),("rango","Rango")]:
            tk.Radiobutton(fil, text=lbl, variable=self._var_filtro, value=val,
                           command=self._toggle_filtro_extra,
                           bg=C["bg"], fg=C["text2"], selectcolor=C["sel"],
                           activebackground=C["bg"], font=FONT_SMALL
                           ).pack(side="left", padx=3)

        # Controles extra segun filtro
        self._fil_extra = tk.Frame(self, bg=C["bg"])
        self._fil_extra.pack(fill="x", padx=26, pady=(0,8))
        self._fil_extra_widgets: dict = {}
        self._build_filtro_extra()

        _separator(self).pack(fill="x", padx=26, pady=(0,10))

        # KPIs
        self._kpi_frame = tk.Frame(self, bg=C["bg"])
        self._kpi_frame.pack(fill="x", padx=26, pady=(0,10))
        self._kpi_labels: dict = {}
        for i, (key, lbl, color) in enumerate([
            ("total_ingresos",   "Total ingresos",  C["accent"]),
            ("num_transacciones","Transacciones",   C["success"]),
            ("ticket_promedio",  "Ticket promedio", C["warning"]),
            ("derivado_top",     "Producto top",    C["text"]),
            ("dia_mas_ventas",   "Dia mas activo",  C["text"]),
            ("hora_pico",        "Hora pico",       C["text"]),
        ]):
            card = _card(self._kpi_frame)
            card.grid(row=0, column=i, padx=3, pady=2, ipadx=8, ipady=6, sticky="ew")
            self._kpi_frame.columnconfigure(i, weight=1)
            _label(card, lbl, "small", bg=C["surface"], fg=C["text2"]).pack(anchor="w", padx=4)
            lb = tk.Label(card, text="-", font=FONT_H3, bg=C["surface"], fg=color)
            lb.pack(anchor="w", padx=4)
            self._kpi_labels[key] = lb

        _separator(self).pack(fill="x", padx=26, pady=(0,10))

        # Botones
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=26, pady=(0,10))
        _btn(bar,"Actualizar metricas", self._actualizar_metricas).pack(side="left",padx=(0,8))
        _btn(bar,"Ver graficas",        self._ver_graficas,"success").pack(side="left",padx=(0,8))
        _btn(bar,"Exportar PDF",        self._exportar_pdf,"ghost").pack(side="left")
        self.lbl_estado = _label(self,"","small",fg=C["text2"])
        self.lbl_estado.pack(anchor="w", padx=26)

        # Tabla top
        _label(self,"Top productos del periodo","h3").pack(anchor="w",padx=26,pady=(10,4))
        f_tv = tk.Frame(self, bg=C["bg"])
        f_tv.pack(fill="both", expand=True, padx=26, pady=(0,10))
        cols = ("Producto","Ingresos ($)","Transacciones","Cantidad")
        self.tv_top, sb = _tree(f_tv, cols, heights=7)
        for col, w in zip(cols, (180,130,130,130)):
            self.tv_top.heading(col, text=col)
            self.tv_top.column(col, width=w, anchor="center")
        self.tv_top.column("Producto", anchor="w")
        self.tv_top.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_filtro_extra(self):
        for w in self._fil_extra.winfo_children():
            w.destroy()
        self._fil_extra_widgets.clear()
        modo = self._var_filtro.get()
        if modo == "mes_esp":
            _label(self._fil_extra,"Año:","small",fg=C["text2"],bg=C["bg"]).pack(side="left")
            e_anio = _entry(self._fil_extra, width=6)
            e_anio.insert(0, str(datetime.now().year))
            e_anio.pack(side="left", padx=(4,10), ipady=4)
            _label(self._fil_extra,"Mes (1-12):","small",fg=C["text2"],bg=C["bg"]).pack(side="left")
            e_mes = _entry(self._fil_extra, width=4)
            e_mes.insert(0, str(datetime.now().month))
            e_mes.pack(side="left", padx=(4,0), ipady=4)
            self._fil_extra_widgets = {"anio": e_anio, "mes": e_mes}
        elif modo == "semana_esp":
            _label(self._fil_extra,"Fecha referencia:","small",fg=C["text2"],bg=C["bg"]).pack(side="left")
            f_w, get_fn = _date_widget(self._fil_extra, datetime.now().strftime("%Y-%m-%d"))
            f_w.pack(side="left", padx=(4,0))
            self._fil_extra_widgets = {"get_fecha": get_fn}
        elif modo == "rango":
            _label(self._fil_extra,"Desde:","small",fg=C["text2"],bg=C["bg"]).pack(side="left")
            f_d, get_d = _date_widget(self._fil_extra, datetime.now().replace(day=1).strftime("%Y-%m-%d"))
            f_d.pack(side="left", padx=(4,14))
            _label(self._fil_extra,"Hasta:","small",fg=C["text2"],bg=C["bg"]).pack(side="left")
            f_h, get_h = _date_widget(self._fil_extra, datetime.now().strftime("%Y-%m-%d"))
            f_h.pack(side="left", padx=(4,0))
            self._fil_extra_widgets = {"get_desde": get_d, "get_hasta": get_h}

    def _toggle_filtro_extra(self):
        self._build_filtro_extra()

    def _filtro_actual(self):
        modo = self._var_filtro.get()
        if modo in ("semana","mes","semestre"):
            return modo
        if modo == "mes_esp":
            try:
                anio = int(self._fil_extra_widgets["anio"].get())
                mes  = int(self._fil_extra_widgets["mes"].get())
                return ("mes_esp", anio, mes)
            except (ValueError, KeyError):
                return "mes"
        if modo == "semana_esp":
            try:
                fecha = self._fil_extra_widgets["get_fecha"]()
                return ("semana_esp", fecha)
            except KeyError:
                return "semana"
        if modo == "rango":
            try:
                d = self._fil_extra_widgets["get_desde"]()
                h = self._fil_extra_widgets["get_hasta"]()
                return ("rango", d, h)
            except KeyError:
                return None
        return None

    def _get_analitica(self):
        try:
            from analytics import Analitica
            return Analitica(self.sistema.todas_las_ventas(),
                             self.sistema.categorias,
                             self._nombre_comercio)
        except ImportError:
            messagebox.showerror("Error",
                "No se encontro analytics.py en la misma carpeta.", parent=self)
            return None

    def refresh(self):
        self._actualizar_metricas()

    def _actualizar_metricas(self):
        an = self._get_analitica()
        if not an: return
        m = an.metricas_generales(self._filtro_actual())
        self._kpi_labels["total_ingresos"].config(text=f"${m['total_ingresos']:,.2f}")
        self._kpi_labels["num_transacciones"].config(text=str(m["num_transacciones"]))
        self._kpi_labels["ticket_promedio"].config(text=f"${m['ticket_promedio']:,.2f}")
        self._kpi_labels["derivado_top"].config(text=str(m["derivado_top"]))
        self._kpi_labels["dia_mas_ventas"].config(text=str(m["dia_mas_ventas"]))
        self._kpi_labels["hora_pico"].config(text=str(m["hora_pico"]))
        for r in self.tv_top.get_children(): self.tv_top.delete(r)
        top_df = an.top_derivados(self._filtro_actual())
        if not top_df.empty:
            for _, row in top_df.iterrows():
                self.tv_top.insert("","end", values=(
                    row["derivado"], f"${row['total_ingresos']:,.2f}",
                    int(row["transacciones"]), f"{row['cantidad_total']:.2f}"))

    def _ver_graficas(self):
        """Abre ventana interna con tabs por grafica. No guarda archivos."""
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        an = self._get_analitica()
        if not an: return
        filtro = self._filtro_actual()

        win = tk.Toplevel(self)
        win.title("Visualizacion de graficas")
        win.geometry("900x560")
        win.configure(bg=C["bg"])
        win.grab_set()

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        def _agregar_tab(titulo, gen_fn, *args):
            tab = tk.Frame(notebook, bg=C["bg"])
            notebook.add(tab, text=titulo)
            lbl = tk.Label(tab, text="Generando...", bg=C["bg"], fg=C["text2"],
                           font=FONT_SMALL)
            lbl.pack(expand=True)
            def _render():
                import matplotlib
                matplotlib.use("TkAgg")
                fig = gen_fn(*args)
                lbl.destroy()
                canvas_fig = FigureCanvasTkAgg(fig, master=tab)
                canvas_fig.draw()
                canvas_fig.get_tk_widget().pack(fill="both", expand=True)
                plt.close(fig)
            tab.after(50, _render)

        # Generadores que devuelven Figure (no guardan archivo)
        def _fig_tendencia():
            df = an.ventas_por_dia(filtro)
            if df.empty: return plt.figure()
            import matplotlib.dates as mdates
            fig, ax = plt.subplots(figsize=(8.5, 3.8), facecolor=C["bg"])
            ax.set_facecolor("#1A1A1A")
            ax.plot(df["fecha"], df["ingresos"], color="#3B82F6", lw=2, marker="o", ms=3)
            ax.fill_between(df["fecha"], df["ingresos"], alpha=0.12, color="#3B82F6")
            ax.set_title("Tendencia de ingresos diarios", color="#F5F5F5", fontsize=12)
            ax.set_ylabel("Ingresos ($)", color="#A0A0A0")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
            ax.tick_params(colors="#A0A0A0")
            fig.autofmt_xdate(rotation=35)
            fig.tight_layout(); return fig

        def _fig_top():
            df = an.top_derivados(filtro)
            if df.empty: return plt.figure()
            import matplotlib.ticker as mt
            fig, ax = plt.subplots(figsize=(8.5, 3.8), facecolor=C["bg"])
            ax.set_facecolor("#1A1A1A")
            colors = ["#3B82F6","#22C55E","#F59E0B","#EF4444",
                      "#8B5CF6","#06B6D4","#F97316","#EC4899"]
            ax.barh(df["derivado"], df["total_ingresos"],
                    color=colors[:len(df)], edgecolor="none")
            ax.set_title("Productos con mayor ingreso", color="#F5F5F5", fontsize=12)
            ax.tick_params(colors="#A0A0A0")
            ax.invert_yaxis()
            fig.tight_layout(); return fig

        def _fig_pastel():
            df = an.top_derivados(filtro)
            if df.empty: return plt.figure()
            colors = ["#3B82F6","#22C55E","#F59E0B","#EF4444",
                      "#8B5CF6","#06B6D4","#F97316","#EC4899"]
            fig, ax = plt.subplots(figsize=(6, 4.5), facecolor=C["bg"])
            ax.set_facecolor("#1A1A1A")
            ax.pie(df["total_ingresos"], labels=df["derivado"], autopct="%1.1f%%",
                   colors=colors[:len(df)], startangle=140,
                   pctdistance=0.80, wedgeprops=dict(width=0.55))
            ax.set_title("Distribucion de ingresos", color="#F5F5F5", fontsize=12, pad=12)
            fig.tight_layout(); return fig

        def _fig_semana():
            df = an.ventas_por_dia_semana(filtro)
            if df.empty: return plt.figure()
            fig, ax = plt.subplots(figsize=(8.5, 3.8), facecolor=C["bg"])
            ax.set_facecolor("#1A1A1A")
            colors = ["#22C55E" if d in ("Sabado","Domingo") else "#3B82F6"
                      for d in df["dia_semana"]]
            ax.bar(df["dia_semana"], df["ingresos"], color=colors, edgecolor="none", width=0.6)
            ax.set_title("Ingresos por dia de la semana", color="#F5F5F5", fontsize=12)
            ax.tick_params(colors="#A0A0A0")
            fig.tight_layout(); return fig

        def _fig_inversion():
            df = an.comparativo_inversion()
            if df.empty: return plt.figure()
            import numpy as np
            fig, ax = plt.subplots(figsize=(8.5, 3.8), facecolor=C["bg"])
            ax.set_facecolor("#1A1A1A")
            x = np.arange(len(df)); w = 0.38
            ax.bar(x-w/2, df["invertido"],  w, label="Invertido",  color="#EF4444", edgecolor="none")
            ax.bar(x+w/2, df["recuperado"], w, label="Recuperado", color="#22C55E", edgecolor="none")
            ax.set_xticks(x)
            ax.set_xticklabels(df["categoria"], rotation=20, ha="right", fontsize=7, color="#A0A0A0")
            ax.set_title("Inversion vs Recuperacion", color="#F5F5F5", fontsize=12)
            ax.legend(facecolor="#242424", edgecolor="#2E2E2E", labelcolor="#F5F5F5")
            fig.tight_layout(); return fig

        def _fig_horaria():
            df = an.distribucion_horaria(filtro)
            if df.empty: return plt.figure()
            fig, ax = plt.subplots(figsize=(8.5, 3.8), facecolor=C["bg"])
            ax.set_facecolor("#1A1A1A")
            ax.bar(df["hora"], df["ingresos"], color="#8B5CF6", edgecolor="none", width=0.7)
            ax.set_title("Distribucion por hora", color="#F5F5F5", fontsize=12)
            ax.tick_params(colors="#A0A0A0")
            fig.tight_layout(); return fig

        for titulo, fn in [
            ("Tendencia",       _fig_tendencia),
            ("Top productos",   _fig_top),
            ("Distribucion",    _fig_pastel),
            ("Dia semana",      _fig_semana),
            ("Inv. vs Recup.",  _fig_inversion),
            ("Por hora",        _fig_horaria),
        ]:
            _agregar_tab(titulo, fn)

    def _exportar_pdf(self):
        an = self._get_analitica()
        if not an: return
        slug   = self._nombre_comercio.lower().replace(" ","_")
        fecha  = datetime.now().strftime("%Y%m%d")
        defname = f"{slug}_{fecha}.pdf"
        ruta = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF","*.pdf")],
            initialfile=defname, parent=self)
        if not ruta: return
        self.lbl_estado.config(text="Generando PDF...")
        self.update()
        def _tarea():
            try:
                an.reporte_pdf(ruta, filtro=self._filtro_actual())
                self.lbl_estado.config(text=f"PDF guardado: {os.path.basename(ruta)}")
            except Exception as e:
                self.lbl_estado.config(text=f"Error: {e}")
        threading.Thread(target=_tarea, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO: USUARIOS
# ══════════════════════════════════════════════════════════════════════════════

class FrameUsuarios(tk.Frame):
    def __init__(self, parent, sistema, usuario, **kw):
        super().__init__(parent, bg=C["bg"])
        self.sistema = sistema
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=26, pady=(22,0))
        _label(hdr,"Gestion de usuarios","h2").pack(side="left")
        _btn(hdr,"+ Agregar usuario",self._nuevo_usuario).pack(side="right")
        _separator(self).pack(fill="x", padx=26, pady=10)
        cols = ("Usuario","Nombre completo","Rol","Estado")
        f_tv = tk.Frame(self, bg=C["bg"])
        f_tv.pack(fill="both", expand=True, padx=26)
        self.tv, sb = _tree(f_tv, cols, heights=13)
        for col, w in zip(cols, (160,220,100,100)):
            self.tv.heading(col, text=col)
            self.tv.column(col, width=w, anchor="center")
        self.tv.column("Nombre completo", anchor="w")
        self.tv.tag_configure("active",   foreground=C["success"])
        self.tv.tag_configure("inactive", foreground=C["text3"])
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=26, pady=10)
        _btn(bar,"Desactivar",     self._desactivar,    "ghost" ).pack(side="left",padx=(0,6))
        _btn(bar,"Reactivar",      self._reactivar,     "success").pack(side="left",padx=(0,6))
        _btn(bar,"Eliminar",       self._eliminar,      "danger" ).pack(side="left",padx=(0,6))
        _btn(bar,"Ver contrasena", self._ver_contrasena,"ghost" ).pack(side="left")
        self.lbl_estado = tk.Label(self, text="", fg=C["text2"],
                                   bg=C["bg"], font=FONT_SMALL)
        self.lbl_estado.pack(anchor="w", padx=26)
        self.refresh()

    def refresh(self):
        for r in self.tv.get_children(): self.tv.delete(r)
        for u in self.sistema.usuarios:
            tag    = "active" if u.activo else "inactive"
            estado = "Activo"  if u.activo else "Inactivo"
            self.tv.insert("","end", iid=u.id_usuario, tags=(tag,),
                           values=(u.nombre_usuario, u.nombre_completo,
                                   u.rol, estado))

    def _sel(self):
        sel = self.tv.focus()
        if not sel:
            messagebox.showinfo("Info","Selecciona un usuario primero",parent=self)
        return sel

    def _nuevo_usuario(self):
        dlg = _Dialog(self,"Nuevo usuario",[
            ("Nombre de usuario","text"),
            ("Contrasena","password"),
            ("Nombre completo","text"),
            ("Rol","choice",["ADMIN","VENDEDOR"]),
        ])
        if dlg.result:
            nombre_u, pwd, nombre_c, rol = dlg.result
            res = self.sistema.agregar_usuario(nombre_u, pwd, nombre_c, rol)
            if res is None:
                messagebox.showerror("Error",f"El usuario '{nombre_u}' ya existe",parent=self)
            else:
                self.lbl_estado.config(text=f"Usuario '{nombre_u}' creado correctamente.")
                self.refresh()

    def _desactivar(self):
        sel = self._sel()
        if not sel: return
        u = next((x for x in self.sistema.usuarios if x.id_usuario==sel), None)
        if not u: return
        if not u.activo:
            self.lbl_estado.config(text=f"'{u.nombre_usuario}' ya estaba inactivo.")
            return
        if messagebox.askyesno("Confirmar","Desactivar este usuario?",parent=self):
            self.sistema.desactivar_usuario(sel)
            self.lbl_estado.config(text=f"'{u.nombre_usuario}' desactivado.")
            self.refresh()

    def _reactivar(self):
        sel = self._sel()
        if not sel: return
        ok, motivo = self.sistema.reactivar_usuario(sel)
        u = next((x for x in self.sistema.usuarios if x.id_usuario==sel), None)
        nombre = u.nombre_usuario if u else sel
        if ok:
            self.lbl_estado.config(text=f"'{nombre}' reactivado correctamente.")
            self.refresh()
        elif motivo == "ya_activo":
            self.lbl_estado.config(
                text=f"'{nombre}' ya estaba activo, no se realizaron cambios.")
        else:
            self.lbl_estado.config(text=f"No se pudo reactivar: {motivo}")

    def _eliminar(self):
        sel = self._sel()
        if not sel: return
        u = next((x for x in self.sistema.usuarios if x.id_usuario==sel), None)
        if not u: return
        if not messagebox.askyesno("Eliminar PERMANENTEMENTE",
                f"Eliminar a '{u.nombre_usuario}'?\nEsta accion no se puede deshacer.",
                parent=self):
            return
        ok, motivo = self.sistema.eliminar_usuario(sel)
        if ok:
            self.lbl_estado.config(text=f"'{u.nombre_usuario}' eliminado.")
            self.refresh()
        else:
            messagebox.showerror("No permitido", motivo, parent=self)

    def _ver_contrasena(self):
        sel = self._sel()
        if not sel: return
        u = next((x for x in self.sistema.usuarios if x.id_usuario==sel), None)
        if u:
            messagebox.showinfo("Contrasena",
                f"Usuario:    {u.nombre_usuario}\n"
                f"Contrasena: {u.contrasena}", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO GENÉRICO
# ══════════════════════════════════════════════════════════════════════════════

class _Dialog(tk.Toplevel):
    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.result   = None
        self._widgets = []
        self.configure(bg=C["surface"])
        self.resizable(False, False)
        self.grab_set()
        tk.Label(self, text=title, font=FONT_H2,
                 bg=C["surface"], fg=C["text"]).pack(padx=22, pady=(18,10), anchor="w")
        _separator(self).pack(fill="x", padx=22, pady=(0,10))
        for field in fields:
            label, ftype = field[0], field[1]
            tk.Label(self, text=label, font=FONT_SMALL,
                     bg=C["surface"], fg=C["text2"]).pack(anchor="w", padx=22, pady=5)
            if ftype == "choice":
                opts = field[2]
                var  = tk.StringVar(value=opts[0])
                w    = ttk.Combobox(self, textvariable=var, values=opts,
                                    font=FONT_BODY, width=28, state="readonly")
                w.pack(padx=22, pady=(0,8))
                self._widgets.append(("choice", var))
            elif ftype == "password":
                row = tk.Frame(self, bg=C["surface"])
                row.pack(padx=22, pady=(0,8), anchor="w")
                w   = _entry(row, width=24, show="●")
                w.pack(side="left", ipady=5)
                _vis = tk.BooleanVar(value=False)
                def _toggle(e=w, v=_vis):
                    v.set(not v.get()); e.config(show="" if v.get() else "●")
                tk.Button(row, text="👁", command=_toggle,
                          bg=C["surface2"], fg=C["text2"], activebackground=C["border"],
                          font=FONT_SMALL, bd=0, padx=8, pady=5,
                          cursor="hand2").pack(side="left", padx=(4,0))
                self._widgets.append(("password", w))
            else:
                w = _entry(self, width=30)
                w.pack(padx=22, pady=(0,8), ipady=5)
                self._widgets.append((ftype, w))
        self.lbl_err = tk.Label(self, text="", fg=C["danger"],
                                bg=C["surface"], font=FONT_SMALL)
        self.lbl_err.pack()
        btn_row = tk.Frame(self, bg=C["surface"])
        btn_row.pack(pady=(6,18), padx=22, fill="x")
        _btn(btn_row,"Cancelar",self.destroy,"ghost").pack(side="right",padx=(8,0))
        _btn(btn_row,"Guardar", self._ok    ).pack(side="right")
        self._center(parent)
        self.wait_window()

    def _center(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width()  // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"+{pw - self.winfo_width()//2}+{ph - self.winfo_height()//2}")

    def _ok(self):
        values = []
        for info in self._widgets:
            ftype = info[0]
            if ftype == "choice":
                values.append(info[1].get())
            elif ftype == "number":
                val = info[1].get().strip()
                try:
                    float(val); values.append(val)
                except ValueError:
                    self.lbl_err.config(text=f"'{val}' no es un numero valido"); return
            else:
                val = info[1].get().strip()
                if not val:
                    self.lbl_err.config(text="Todos los campos son obligatorios"); return
                values.append(val)
        self.result = values
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# FLUJO DE LANZAMIENTO
# ══════════════════════════════════════════════════════════════════════════════

def _reiniciar_login(sistema: SistemaVentas, nombre_comercio: str):
    login = LoginWindow(sistema, nombre_comercio)
    login.mainloop()
    if login.usuario is None:
        return
    App(sistema, login.usuario, nombre_comercio).mainloop()


def _flujo_inicio():
    """Flujo completo: selector de comercio → login → app."""
    gestor   = GestorComercios()
    selector = SelectorComercio(gestor)
    selector.mainloop()

    if selector.comercio_id is None:
        return

    comercio_id = selector.comercio_id
    comercio    = gestor.obtener_comercio(comercio_id)
    nombre      = comercio.nombre if comercio else "Mi Negocio"

    sistema = SistemaVentas(comercio_id=comercio_id)
    _reiniciar_login(sistema, nombre)


def lanzar():
    """Punto de entrada publico desde main_vista.py."""
    _flujo_inicio()
