"""
modelo.py  
=============
Backend central del sistema de registro de ventas.

"""

import json
import csv
import os
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE COMERCIOS (multi-negocio)
# ══════════════════════════════════════════════════════════════════════════════

class Comercio:
    """Representa un negocio registrado en el sistema."""

    def __init__(self, id_comercio, nombre, tipo, descripcion="", activo=True):
        self.id_comercio  = id_comercio   # ej. "comercio_1"
        self.nombre       = nombre         # ej. "Carnicería Don Pepe"
        self.tipo         = tipo           # ej. "Carnicería", "Ropa", etc.
        self.descripcion  = descripcion
        self.activo       = bool(activo)

    def a_dict(self):
        return {
            "id_comercio": self.id_comercio,
            "nombre":      self.nombre,
            "tipo":        self.tipo,
            "descripcion": self.descripcion,
            "activo":      self.activo,
        }

    def nombre_archivo_pdf(self):
        """Genera el nombre base para el PDF: nombre_comercio_YYYYMMDD.pdf"""
        slug  = self.nombre.lower().replace(" ", "_")
        fecha = datetime.now().strftime("%Y%m%d")

        contador=1

        while True:
            nombre_base = f"{slug}_{fecha}_{contador}.pdf"

            if not os.path.exists(nombre_base):
                return nombre_base

            contador += 1


class GestorComercios:
    """
    Gestiona el catálogo de comercios en comercios.json.
    Cada comercio tiene su propio archivo de datos: datos_{id_comercio}.json
    """

    def __init__(self, ruta_base=None):
        self._dir = ruta_base or os.path.dirname(__file__)
        self._archivo = os.path.join(self._dir, "comercios.json")
        self.comercios: list[Comercio] = []
        self._cargar()

    def _cargar(self):
        if not os.path.exists(self._archivo):
            return
        try:
            with open(self._archivo, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        for c in data.get("comercios", []):
            self.comercios.append(Comercio(
                id_comercio = c.get("id_comercio", ""),
                nombre      = c.get("nombre",      ""),
                tipo        = c.get("tipo",        ""),
                descripcion = c.get("descripcion", ""),
                activo      = c.get("activo",      True),
            ))

    def _guardar(self):
        os.makedirs(self._dir, exist_ok=True)
        data = {"comercios": [c.a_dict() for c in self.comercios]}
        with open(self._archivo, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def agregar_comercio(self, nombre, tipo, descripcion=""):
        """Crea un nuevo comercio y devuelve el objeto."""
        max_n = max(
            (int(c.id_comercio.split("_")[1]) for c in self.comercios
             if c.id_comercio.startswith("comercio_")),
            default=0,
        )
        nuevo = Comercio(f"comercio_{max_n + 1}", nombre, tipo, descripcion)
        self.comercios.append(nuevo)
        self._guardar()
        return nuevo

    def obtener_comercio(self, id_comercio):
        return next((c for c in self.comercios if c.id_comercio == id_comercio), None)

    def eliminar_comercio(self, id_comercio):
        """Desactiva el comercio (no borra sus datos)."""
        c = self.obtener_comercio(id_comercio)
        if c:
            c.activo = False
            self._guardar()
            return True
        return False

    def archivo_datos(self, id_comercio):
        """Devuelve la ruta del archivo JSON de datos de un comercio."""
        return os.path.join(self._dir, f"datos_{id_comercio}.json")

    @property
    def activos(self):
        return [c for c in self.comercios if c.activo]


# ══════════════════════════════════════════════════════════════════════════════
# CLASES DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

class RegistroVenta:
    def __init__(self, id_venta, fecha_hora, cantidad, precio_aplicado, subtotal):
        self.id_venta        = id_venta
        self.fecha_hora      = fecha_hora
        self.cantidad        = float(cantidad)
        self.precio_aplicado = float(precio_aplicado)
        self.subtotal        = float(subtotal)

    def calcular_subtotal(self):
        self.subtotal = round(self.cantidad * self.precio_aplicado, 2)
        return self.subtotal

    def a_dict(self):
        return {
            "id_venta":        self.id_venta,
            "fecha_hora":      self.fecha_hora,
            "cantidad":        self.cantidad,
            "precio_aplicado": self.precio_aplicado,
            "subtotal":        self.subtotal,
        }


class Derivado:
    TIPOS_VENTA = ["kg", "gramos", "pieza"]

    def __init__(self, id_derivado, nombre, tipo_venta, precio_unitario):
        self.id_derivado     = id_derivado
        self.nombre          = nombre
        self.tipo_venta      = tipo_venta if tipo_venta in self.TIPOS_VENTA else "kg"
        self.precio_unitario = float(precio_unitario)
        self.ventas: list[RegistroVenta] = []
        self.total_vendido   = 0.0

    def registrar_venta(self, cantidad, precio=None):
        precio_final = float(precio) if precio is not None else self.precio_unitario
        max_n = max(
            (int(v.id_venta.split("_")[1]) for v in self.ventas
             if v.id_venta.startswith("V_")),
            default=0,
        )
        nueva = RegistroVenta(
            id_venta        = f"V_{max_n + 1}",
            fecha_hora      = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            cantidad        = float(cantidad),
            precio_aplicado = precio_final,
            subtotal        = round(float(cantidad) * precio_final, 2),
        )
        self.ventas.append(nueva)
        self.calcular_total_vendido()
        return nueva

    def calcular_total_vendido(self):
        self.total_vendido = round(sum(v.subtotal for v in self.ventas), 2)
        return self.total_vendido

    def obtener_historial(self):
        return self.ventas

    def a_dict(self):
        return {
            "id_derivado":     self.id_derivado,
            "nombre":          self.nombre,
            "tipo_venta":      self.tipo_venta,
            "precio_unitario": self.precio_unitario,
            "ventas":          [v.a_dict() for v in self.ventas],
        }


class CategoriaMadre:
    def __init__(self, id_categoria, nombre, fecha_compra, costo_total):
        self.id_categoria = id_categoria
        self.nombre       = nombre
        self.fecha_compra = fecha_compra
        self.costo_total  = float(costo_total)
        self.derivados: list[Derivado] = []

    def agregar_derivado(self, derivado):
        self.derivados.append(derivado)

    def obtener_derivado(self, id_derivado):
        return next((d for d in self.derivados if d.id_derivado == id_derivado), None)

    def calcular_recuperado(self):
        return round(sum(d.calcular_total_vendido() for d in self.derivados), 2)

    def porcentaje_recuperacion(self):
        if self.costo_total == 0:
            return 0.0
        return round((self.calcular_recuperado() / self.costo_total) * 100, 2)

    def exportar_csv(self, ruta_carpeta="."):
        ruta = os.path.join(ruta_carpeta, f"{self.id_categoria}.csv")
        with open(ruta, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "derivado", "tipo_venta", "cantidad",
                "precio_unitario", "subtotal", "fecha_hora",
            ])
            writer.writeheader()
            for d in self.derivados:
                for v in d.ventas:
                    writer.writerow({
                        "derivado":        d.nombre,
                        "tipo_venta":      d.tipo_venta,
                        "cantidad":        v.cantidad,
                        "precio_unitario": v.precio_aplicado,
                        "subtotal":        v.subtotal,
                        "fecha_hora":      v.fecha_hora,
                    })
        return ruta

    def a_dict(self):
        return {
            "id_categoria": self.id_categoria,
            "nombre":       self.nombre,
            "fecha_compra": self.fecha_compra,
            "costo_total":  self.costo_total,
            "derivados":    [d.a_dict() for d in self.derivados],
        }


class Usuario:
    _PERMISOS = {
        "ADMIN":    {"categorias", "derivados", "ventas", "reportes",
                     "usuarios", "analytics", "comercio"},
        "VENDEDOR": {"ventas"},
    }

    def __init__(self, id_usuario, nombre_usuario, contrasena,
                 nombre_completo, rol, activo=True):
        self.id_usuario      = id_usuario
        self.nombre_usuario  = nombre_usuario
        self.contrasena      = contrasena
        self.nombre_completo = nombre_completo
        self.rol             = rol.upper()
        self.activo          = bool(activo)

    def verificar_credenciales(self, nombre_usuario, contrasena):
        return (
            self.nombre_usuario == nombre_usuario
            and self.contrasena  == contrasena
            and self.activo
        )

    def tiene_permiso(self, modulo):
        return modulo in self._PERMISOS.get(self.rol, set())

    def a_dict(self):
        return {
            "id_usuario":      self.id_usuario,
            "nombre_usuario":  self.nombre_usuario,
            "contrasena":      self.contrasena,
            "nombre_completo": self.nombre_completo,
            "rol":             self.rol,
            "activo":          self.activo,
        }


class Reporte:
    def __init__(self, fecha_inicio=None, fecha_fin=None):
        self.fecha_inicio = fecha_inicio
        self.fecha_fin    = fecha_fin

    def _en_rango(self, fecha_hora_str):
        fecha = fecha_hora_str[:10]
        if self.fecha_inicio and fecha < self.fecha_inicio:
            return False
        if self.fecha_fin   and fecha > self.fecha_fin:
            return False
        return True

    def ventas_por_periodo(self, categorias):
        resumen = {}
        for cat in categorias:
            for der in cat.derivados:
                for v in der.ventas:
                    if self._en_rango(v.fecha_hora):
                        dia = v.fecha_hora[:10]
                        resumen[dia] = round(resumen.get(dia, 0.0) + v.subtotal, 2)
        return dict(sorted(resumen.items()))

    def comparativo_inversion_recuperacion(self, categorias):
        return [
            {
                "id_categoria": c.id_categoria,
                "nombre":       c.nombre,
                "fecha_compra": c.fecha_compra,
                "costo_total":  c.costo_total,
                "recuperado":   c.calcular_recuperado(),
                "porcentaje":   c.porcentaje_recuperacion(),
            }
            for c in categorias
        ]

    def derivados_mas_vendidos(self, categorias, top_n=5, filtro_categoria=None):
        acumulado = {}
        for cat in categorias:
            if filtro_categoria and cat.id_categoria != filtro_categoria:
                continue
            for der in cat.derivados:
                entrada = acumulado.setdefault(der.nombre, {
                    "nombre":        der.nombre,
                    "categoria":     cat.nombre,
                    "tipo_venta":    der.tipo_venta,
                    "total_vendido": 0.0,
                })
                entrada["total_vendido"] = round(
                    entrada["total_vendido"] + der.calcular_total_vendido(), 2
                )
        return sorted(acumulado.values(),
                      key=lambda x: x["total_vendido"], reverse=True)[:top_n]


# ══════════════════════════════════════════════════════════════════════════════
# COORDINADOR CENTRAL
# ══════════════════════════════════════════════════════════════════════════════

class SistemaVentas:
    """
    Coordinador central. Ahora recibe comercio_id para operar sobre el
    archivo de datos del comercio activo: datos_{comercio_id}.json
    """

    def __init__(self, comercio_id="default", ruta_base=None):
        self._dir         = ruta_base or os.path.dirname(__file__)
        self.comercio_id  = comercio_id
        self.archivo_json = os.path.join(self._dir, f"datos_{comercio_id}.json")
        self.categorias:  list[CategoriaMadre] = []
        self.usuarios:    list[Usuario]        = []
        self._cargar_datos()
        if not self.usuarios:
            self._crear_admin_defecto()

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _cargar_datos(self):
        if not os.path.exists(self.archivo_json):
            return
        try:
            with open(self.archivo_json, encoding="utf-8") as f:
                datos = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ADVERTENCIA] {self.archivo_json}: {e}")
            return

        for c in datos.get("categorias", []):
            cat = CategoriaMadre(
                id_categoria = c.get("id_categoria", ""),
                nombre       = c.get("nombre",       ""),
                fecha_compra = c.get("fecha_compra", ""),
                costo_total  = c.get("costo_total",  0.0),
            )
            for d in c.get("derivados", []):
                der = Derivado(
                    id_derivado     = d.get("id_derivado",    ""),
                    nombre          = d.get("nombre",         ""),
                    tipo_venta      = d.get("tipo_venta",     "kg"),
                    precio_unitario = d.get("precio_unitario", 0.0),
                )
                for v in d.get("ventas", []):
                    der.ventas.append(RegistroVenta(
                        id_venta        = v.get("id_venta",        ""),
                        fecha_hora      = v.get("fecha_hora",      ""),
                        cantidad        = v.get("cantidad",        0.0),
                        precio_aplicado = v.get("precio_aplicado", 0.0),
                        subtotal        = v.get("subtotal",        0.0),
                    ))
                der.calcular_total_vendido()
                cat.agregar_derivado(der)
            self.categorias.append(cat)

        for u in datos.get("usuarios", []):
            self.usuarios.append(Usuario(
                id_usuario      = u.get("id_usuario",      ""),
                nombre_usuario  = u.get("nombre_usuario",  ""),
                contrasena      = u.get("contrasena",      ""),
                nombre_completo = u.get("nombre_completo", ""),
                rol             = u.get("rol",             "VENDEDOR"),
                activo          = u.get("activo",          True),
            ))

    def guardar_datos(self):
        datos = {
            "categorias": [c.a_dict() for c in self.categorias],
            "usuarios":   [u.a_dict() for u in self.usuarios],
        }
        with open(self.archivo_json, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

    def _crear_admin_defecto(self):
        admin = Usuario("U_1", "admin", "admin123", "Administrador", "ADMIN")
        self.usuarios.append(admin)
        self.guardar_datos()
        print("[Sistema] Admin creado: usuario=admin  contrasena=admin123")

    # ── Autenticación ─────────────────────────────────────────────────────────

    def autenticar(self, nombre_usuario, contrasena):
        for u in self.usuarios:
            if u.verificar_credenciales(nombre_usuario, contrasena):
                return u
        return None

    # ── Usuarios ──────────────────────────────────────────────────────────────

    def agregar_usuario(self, nombre_usuario, contrasena, nombre_completo, rol):
        if any(u.nombre_usuario == nombre_usuario for u in self.usuarios):
            return None
        max_n = max(
            (int(u.id_usuario.split("_")[1]) for u in self.usuarios
             if u.id_usuario.startswith("U_")),
            default=0,
        )
        nuevo = Usuario(f"U_{max_n + 1}", nombre_usuario,
                        contrasena, nombre_completo, rol)
        self.usuarios.append(nuevo)
        self.guardar_datos()
        return nuevo

    def desactivar_usuario(self, id_usuario):
        for u in self.usuarios:
            if u.id_usuario == id_usuario:
                if not u.activo:
                    return False, "ya_inactivo"
                u.activo = False
                self.guardar_datos()
                return True, ""
        return False, "no_encontrado"

    def reactivar_usuario(self, id_usuario):
        """
        Reactiva un usuario.
        Devuelve (True, "") si ok, (False, motivo) si ya estaba activo o no existe.
        """
        for u in self.usuarios:
            if u.id_usuario == id_usuario:
                if u.activo:
                    return False, "ya_activo"
                u.activo = True
                self.guardar_datos()
                return True, ""
        return False, "no_encontrado"

    def eliminar_usuario(self, id_usuario):
        usuario = next((u for u in self.usuarios if u.id_usuario == id_usuario), None)
        if usuario is None:
            return False, "Usuario no encontrado."
        if usuario.id_usuario == "U_1":
            return False, "No se puede eliminar al administrador raiz del sistema."
        admins_activos = [u for u in self.usuarios
                          if u.rol == "ADMIN" and u.activo
                          and u.id_usuario != id_usuario]
        if usuario.rol == "ADMIN" and not admins_activos:
            return False, "No puedes eliminar al ultimo administrador activo."
        self.usuarios = [u for u in self.usuarios if u.id_usuario != id_usuario]
        self.guardar_datos()
        return True, ""

    # ── Categorías ────────────────────────────────────────────────────────────

    def agregar_categoria(self, nombre, fecha_compra, costo_total):
        slug     = nombre.lower().replace(" ", "_")
        base_id  = f"{slug}_{fecha_compra.replace('-', '')}"
        nuevo_id = base_id
        existentes = {c.id_categoria for c in self.categorias}
        n = 1
        while nuevo_id in existentes:
            nuevo_id = f"{base_id}_{n}"
            n += 1
        nueva = CategoriaMadre(nuevo_id, nombre, fecha_compra, costo_total)
        self.categorias.append(nueva)
        self.guardar_datos()
        return nueva

    def obtener_categoria(self, id_categoria):
        return next((c for c in self.categorias if c.id_categoria == id_categoria), None)

    # ── Derivados ─────────────────────────────────────────────────────────────

    def agregar_derivado(self, id_categoria, nombre, tipo_venta, precio_unitario):
        cat = self.obtener_categoria(id_categoria)
        if cat is None:
            return None
        slug     = nombre.lower()[:3].replace(" ", "")
        nuevo_id = f"{slug}_{len(cat.derivados) + 1}"
        nuevo = Derivado(nuevo_id, nombre, tipo_venta, precio_unitario)
        cat.agregar_derivado(nuevo)
        self.guardar_datos()
        return nuevo

    def actualizar_precio_derivado(self, id_categoria, id_derivado, nuevo_precio):
        cat = self.obtener_categoria(id_categoria)
        if not cat:
            return False
        der = cat.obtener_derivado(id_derivado)
        if not der:
            return False
        der.precio_unitario = float(nuevo_precio)
        self.guardar_datos()
        return True

    # ── Ventas ────────────────────────────────────────────────────────────────

    def registrar_venta(self, id_categoria, id_derivado, cantidad, precio=None):
        cat = self.obtener_categoria(id_categoria)
        if not cat:
            return None
        der = cat.obtener_derivado(id_derivado)
        if not der:
            return None
        venta = der.registrar_venta(cantidad, precio)
        self.guardar_datos()
        return venta

    # ── Reportes ──────────────────────────────────────────────────────────────

    def reporte_comparativo(self):
        return Reporte().comparativo_inversion_recuperacion(self.categorias)

    def reporte_ventas_periodo(self, fecha_inicio=None, fecha_fin=None):
        return Reporte(fecha_inicio, fecha_fin).ventas_por_periodo(self.categorias)

    def reporte_top_derivados(self, top_n=5, filtro_categoria=None):
        return Reporte().derivados_mas_vendidos(self.categorias, top_n, filtro_categoria)

    def exportar_csv_categoria(self, id_categoria, ruta_carpeta="."):
        cat = self.obtener_categoria(id_categoria)
        return cat.exportar_csv(ruta_carpeta) if cat else None

    # ── Utilidad para analytics ───────────────────────────────────────────────

    def todas_las_ventas(self):
        """Lista plana de dicts para construir DataFrames en analytics.py."""
        filas = []
        for cat in self.categorias:
            for der in cat.derivados:
                for v in der.ventas:
                    filas.append({
                        "fecha_hora":      v.fecha_hora,
                        "fecha":           v.fecha_hora[:10],
                        "hora":            v.fecha_hora[11:13],
                        "categoria":       cat.nombre,
                        "id_categoria":    cat.id_categoria,
                        "derivado":        der.nombre,
                        "tipo_venta":      der.tipo_venta,
                        "cantidad":        v.cantidad,
                        "precio_aplicado": v.precio_aplicado,
                        "subtotal":        v.subtotal,
                        "costo_categoria": cat.costo_total,
                    })
        return filas
