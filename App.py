import sqlite3
import streamlit as st
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
def inicializar_bd():
    conn = sqlite3.connect("inventario_casa.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS localizaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_localizacion TEXT UNIQUE NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sublocalizaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            localizacion_id INTEGER,
            nombre_sublocalizacion TEXT NOT NULL,
            FOREIGN KEY(localizacion_id) REFERENCES localizaciones(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            nombre TEXT PRIMARY KEY,
            marca TEXT,
            establecimiento TEXT,
            localizacion TEXT,
            sublocalizacion TEXT,
            cantidad INTEGER,
            stock_minimo INTEGER,
            estado_uso TEXT,
            descripcion TEXT,
            anotaciones TEXT,
            estado_stock TEXT DEFAULT 'normal',
            detalle_estado TEXT,
            ultima_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_nombre TEXT,
            tipo TEXT,
            cantidad_afectada INTEGER,
            origen TEXT,
            destino TEXT,
            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(item_nombre) REFERENCES items(nombre) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prestamos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_nombre TEXT,
            cantidad INTEGER,
            receptor TEXT,
            admin_id TEXT,
            fecha_prestamo TIMESTAMP,
            fecha_devolucion DATETIME,
            devuelto INTEGER DEFAULT 0,
            FOREIGN KEY(item_nombre) REFERENCES items(nombre) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

inicializar_bd()

def get_connection():
    return sqlite3.connect("inventario_casa.db", check_same_thread=False)

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestor de Inventario Casero", layout="wide")

st.title("📦 Gestor de Inventario Casero (Móvil/Web)")

# --- SISTEMA DE ALERTAS EN TIEMPO REAL ---
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT nombre, cantidad, stock_minimo FROM items WHERE cantidad <= stock_minimo AND estado_stock = 'normal'")
bajos = cursor.fetchall()
for item in bajos:
    st.warning(f"⚠️ **Alerta de Stock Mínimo:** El ítem '{item[0]}' tiene stock bajo ({item[1]} / mín: {item[2]}).")

ahora = datetime.now()
limite = ahora + timedelta(hours=48)
cursor.execute("SELECT item_nombre, receptor, fecha_devolucion FROM prestamos WHERE devuelto = 0 AND fecha_devolucion <= ?", (limite.strftime("%Y-%m-%d %H:%M"),))
prestamos_vencen = cursor.fetchall()
for p in prestamos_vencen:
    st.warning(f"⏳ **Alerta de Préstamo:** Atención: El préstamo de '{p[0]}' a '{p[1]}' vence el {p[2]}.")
conn.close()

# --- MENÚ DE NAVEGACIÓN ---
menu = st.sidebar.selectbox("Menú de Opciones", ["1. BUSCAR", "2. MODIFICAR & MOVER", "3. LOCALIZACIONES"])

# ==========================================
# 1. BUSCAR (Formato Tabla Excel Interactiva)
# ==========================================
if menu == "1. BUSCAR":
    st.header("🔍 Buscar en el Inventario")
    
    # Manejo de estado para cuando se hace clic en una celda/criterio específico
    if "filtro_click" not in st.session_state:
        st.session_state.filtro_click = ""

    col_b1, col_b2, col_b3 = st.columns([2, 1, 1])
    with col_b1:
        txt_busqueda = st.text_input("Término de búsqueda:", value=st.session_state.filtro_click)
    with col_b2:
        criterio = st.selectbox("Filtrar por criterio:", ["Todos", "localizacion", "sublocalizacion", "marca", "establecimiento", "estado_uso"])
    with col_b3:
        if st.button("Limpiar Filtro"):
            st.session_state.filtro_click = ""
            st.rerun()

    conn = get_connection()
    cursor = conn.cursor()
    
    if txt_busqueda:
        texto = f"%{txt_busqueda}%"
        if criterio == "Todos":
            query = """SELECT nombre, marca, establecimiento, localizacion, sublocalizacion, cantidad, stock_minimo, estado_uso, descripcion, anotaciones, ultima_modificacion FROM items 
                       WHERE nombre LIKE ? OR descripcion LIKE ? OR marca LIKE ? OR establecimiento LIKE ? OR localizacion LIKE ? OR sublocalizacion LIKE ? OR estado_uso LIKE ?"""
            cursor.execute(query, (texto, texto, texto, texto, texto, texto, texto))
        else:
            query = f"SELECT nombre, marca, establecimiento, localizacion, sublocalizacion, cantidad, stock_minimo, estado_uso, descripcion, anotaciones, ultima_modificacion FROM items WHERE {criterio} LIKE ?"
            cursor.execute(query, (texto,))
    else:
        cursor.execute("SELECT nombre, marca, establecimiento, localizacion, sublocalizacion, cantidad, stock_minimo, estado_uso, descripcion, anotaciones, ultima_modificacion FROM items")
        
    rows = cursor.fetchall()
    conn.close()
    
    st.subheader(f"Resultados en Tabla ({len(rows)} ítems encontrados):")
    
    if rows:
        # Preparamos los datos estructurados en formato tabla tipo Excel
        import pandas as pd
        df = pd.DataFrame(rows, columns=[
            "Nombre", "Marca", "Establecimiento", "Localización", "Sublocalización", 
            "Cantidad", "Stock Mín.", "Estado/Uso", "Descripción", "Anotaciones", "Última Modif."
        ])
        
        # Mostramos la tabla interactiva de Streamlit (permite ordenar columnas, redimensionar, etc.)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("💡 **Filtrar por clic rápido:** Pulsa sobre cualquier valor de la lista inferior para mostrar automáticamente todos los registros que coincidan con él:")
        
        # Extraer valores únicos para marcas, localizaciones, establecimientos y estados para hacer clic rápido
        marcas_unicas = sorted(list(set([r[1] for r in rows if r[1]])))
        estab_unicos = sorted(list(set([r[2] for r in rows if r[2]])))
        locs_unicas = sorted(list(set([r[3] for r in rows if r[3]])))
        usos_unicos = sorted(list(set([r[7] for r in rows if r[7]])))
        
        cols_tags = st.columns(4)
        with cols_tags[0]:
            if marcas_unicas:
                st.caption("🔹 **Marcas:**")
                for m in marcas_unicas:
                    if st.button(m, key=f"m_{m}"):
                        st.session_state.filtro_click = m
                        st.rerun()
        with cols_tags[1]:
            if locs_unicas:
                st.caption("📍 **Localizaciones:**")
                for l in locs_unicas:
                    if st.button(l, key=f"l_{l}"):
                        st.session_state.filtro_click = l
                        st.rerun()
        with cols_tags[2]:
            if estab_unicos:
                st.caption("🛒 **Establecimientos:**")
                for e in estab_unicos:
                    if st.button(e, key=f"e_{e}"):
                        st.session_state.filtro_click = e
                        st.rerun()
        with cols_tags[3]:
            if usos_unicos:
                st.caption("⚙️ **Estados/Usos:**")
                for u in usos_unicos:
                    if st.button(u, key=f"u_{u}"):
                        st.session_state.filtro_click = u
                        st.rerun()
    else:
        st.info("No se encontraron registros coincidentes.")

# ==========================================
# 2. MODIFICAR & MOVER
# ==========================================
elif menu == "2. MODIFICAR & MOVER":
    st.header("⚙️ Modificar el Inventario")
    sub_menu = st.radio("Selecciona acción:", ["2.1 Entradas (Formulario de Alta)", "2.3 Mover / Prestar Ítems"])
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre_localizacion FROM localizaciones")
    locs = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if sub_menu == "2.1 Entradas (Formulario de Alta)":
        st.subheader("📝 Dar de alta / Introducir Nuevo Ítem")
        with st.form("form_entrada"):
            nombre = st.text_input("Nombre del Ítem (Clave Principal)*")
            marca = st.text_input("Marca")
            estab = st.text_input("Establecimiento de compra")
            
            col1, col2 = st.columns(2)
            with col1:
                cant = st.number_input("Cantidad inicial", min_value=0, value=1)
            with col2:
                stock_min = st.number_input("Stock Mínimo de alerta", min_value=0, value=1)
                
            estado_uso = st.text_input("Estado o Uso del producto (ej. Nuevo, Usado, Reparado)")
            desc = st.text_area("Descripción")
            anot = st.text_area("Anotaciones")
            
            loc_elegida = st.selectbox("Localización", locs if locs else ["Sin localizaciones creadas"])
            
            sublocs = []
            if locs:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM localizaciones WHERE nombre_localizacion = ?", (loc_elegida,))
                res = cursor.fetchone()
                if res:
                    cursor.execute("SELECT nombre_sublocalizacion FROM sublocalizaciones WHERE localizacion_id = ?", (res[0],))
                    sublocs = [r[0] for r in cursor.fetchall()]
                conn.close()
                
            subloc_elegida = st.selectbox("Sublocalización", sublocs if sublocs else ["Ninguna"])
            
            submitted = st.form_submit_button("Aceptar e Introducir")
            if submitted:
                if not nombre.strip():
                    st.error("El nombre del ítem es obligatorio.")
                elif not locs:
                    st.error("Debes crear al menos una localización en la pestaña 'Localizaciones'.")
                else:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR REPLACE INTO items (nombre, marca, establecimiento, localizacion, sublocalizacion, cantidad, stock_minimo, estado_uso, descripcion, anotaciones, estado_stock)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'normal')
                        """, (nombre.strip(), marca, estab, loc_elegida, subloc_elegida if subloc_elegida != "Ninguna" else "", int(cant), int(stock_min), estado_uso, desc, anot))
                        
                        cursor.execute("""
                            INSERT INTO movimientos (item_nombre, tipo, cantidad_afectada, origen, destino)
                            VALUES (?, 'ENTRADA', ?, 'Externo', ?)
                        """, (nombre.strip(), int(cant), f"{loc_elegida} > {subloc_elegida}"))
                        
                        conn.commit()
                        conn.close()
                        st.success(f"¡Ítem '{nombre}' guardado con éxito!")
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    elif sub_menu == "2.3 Mover / Prestar Ítems":
        st.subheader("🚚 Mover o Prestar Ítems / Sublocalizaciones")
        
        modo_mov = st.radio("¿Qué deseas mover?", ["Ítems específicos (Múltiple)", "Toda una Sublocalización completa (Masivo)"])
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, cantidad, localizacion, sublocalizacion FROM items")
        items_db = cursor.fetchall()
        conn.close()
        
        if not items_db:
            st.info("No hay ítems registrados en el inventario.")
        else:
            destino_opciones = locs + ["Préstamos"]
            
            if modo_mov == "Ítems específicos (Múltiple)":
                item_dict = {f"{i[0]} (Stock: {i[1]} | Ubicación: {i[2]} > {i[3]})": i for i in items_db}
                seleccion_items = st.multiselect("Selecciona uno o varios ítems a mover:", list(item_dict.keys()))
                
                dest_loc = st.selectbox("Localización Destino", destino_opciones)
                
                if st.button("Procesar Movimiento de Seleccionados"):
                    if not seleccion_items:
                        st.error("Selecciona al menos un ítem.")
                    elif dest_loc == "Préstamos":
                        @st.dialog("📋 Formulario de Préstamo Obligatorio")
                        def modal_prestamo_multiple():
                            admin_id = st.text_input("ID del Administrador*")
                            receptor = st.text_input("Nombre de quien recibe el préstamo*")
                            fecha_limite = st.text_input("Fecha límite de devolución (YYYY-MM-DD HH:MM)", value=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M"))
                            
                            if st.button("Confirmar Préstamo"):
                                if not admin_id.strip() or not receptor.strip():
                                    st.error("El ID de admin y el receptor son obligatorios.")
                                else:
                                    conn = get_connection()
                                    cursor = conn.cursor()
                                    for sel in seleccion_items:
                                        i_nombre, i_cant, i_loc, i_sub = item_dict[sel]
                                        cursor.execute("UPDATE items SET cantidad = 0, localizacion = 'Préstamos', sublocalizacion = '' WHERE nombre = ?", (i_nombre,))
                                        cursor.execute("""
                                            INSERT INTO prestamos (item_nombre, cantidad, receptor, admin_id, fecha_prestamo, fecha_devolucion)
                                            VALUES (?, ?, ?, ?, ?, ?)
                                        """, (i_nombre, i_cant, receptor, admin_id, datetime.now().strftime("%Y-%m-%d %H:%M"), fecha_limite))
                                        cursor.execute("""
                                            INSERT INTO movimientos (item_nombre, tipo, cantidad_afectada, origen, destino)
                                            VALUES (?, 'PRESTAMO', ?, ?, 'Préstamos')
                                        """, (i_nombre, i_cant, f"{i_loc} > {i_sub}"))
                                    conn.commit()
                                    conn.close()
                                    st.success("¡Préstamos registrados y ítems movidos con éxito!")
                                    st.rerun()
                        modal_prestamo_multiple()
                    else:
                        conn = get_connection()
                        cursor = conn.cursor()
                        for sel in seleccion_items:
                            i_nombre, i_cant, i_loc, i_sub = item_dict[sel]
                            cursor.execute("UPDATE items SET localizacion = ? WHERE nombre = ?", (dest_loc, i_nombre))
                            cursor.execute("""
                                INSERT INTO movimientos (item_nombre, tipo, cantidad_afectada, origen, destino)
                                VALUES (?, 'MOVIMIENTO', ?, ?, ?)
                            """, (i_nombre, i_cant, f"{i_loc} > {i_sub}", dest_loc))
                        conn.commit()
                        conn.close()
                        st.success("¡Movimiento de los ítems realizado correctamente!")
                        st.rerun()

            else:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT l.nombre_localizacion, s.nombre_sublocalizacion 
                    FROM sublocalizaciones s 
                    JOIN localizaciones l ON s.localizacion_id = l.id
                """)
                sublocs_registradas = cursor.fetchall()
                conn.close()
                
                if not sublocs_registradas:
                    st.info("No hay sublocalizaciones creadas todavía.")
                else:
                    subloc_dict = {f"{r[0]} > {r[1]}": (r[0], r[1]) for r in sublocs_registradas}
                    subloc_elegida_str = st.selectbox("Selecciona la Sublocalización de origen:", list(subloc_dict.keys()))
                    
                    dest_loc_masivo = st.selectbox("Localización Destino para todo el contenido", destino_opciones)
                    
                    if st.button("Mover Todo el Contenido de la Sublocalización"):
                        l_origen, s_origen = subloc_dict[subloc_elegida_str]
                        
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT nombre, cantidad FROM items WHERE localizacion = ? AND sublocalizacion = ?", (l_origen, s_origen))
                        items_en_subloc = cursor.fetchall()
                        
                        if not items_en_subloc:
                            st.warning("Esta sublocalización está vacía actualmente.")
                            conn.close()
                        elif dest_loc_masivo == "Préstamos":
                            conn.close()
                            @st.dialog("📋 Formulario de Préstamo Masivo Obligatorio")
                            def modal_prestamo_masivo():
                                admin_id = st.text_input("ID del Administrador*")
                                receptor = st.text_input("Nombre de quien recibe el préstamo*")
                                fecha_limite = st.text_input("Fecha límite de devolución (YYYY-MM-DD HH:MM)", value=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M"))
                                
                                if st.button("Confirmar Préstamo Masivo"):
                                    if not admin_id.strip() or not receptor.strip():
                                        st.error("El ID de admin y el receptor son obligatorios.")
                                    else:
                                        conn_m = get_connection()
                                        cur_m = conn_m.cursor()
                                        for itm_n, itm_c in items_en_subloc:
                                            cur_m.execute("UPDATE items SET cantidad = 0, localizacion = 'Préstamos', sublocalizacion = '' WHERE nombre = ?", (itm_n,))
                                            cur_m.execute("""
                                                INSERT INTO prestamos (item_nombre, cantidad, receptor, admin_id, fecha_prestamo, fecha_devolucion)
                                                VALUES (?, ?, ?, ?, ?, ?)
                                            """, (itm_n, itm_c, receptor, admin_id, datetime.now().strftime("%Y-%m-%d %H:%M"), fecha_limite))
                                            cur_m.execute("""
                                                INSERT INTO movimientos (item_nombre, tipo, cantidad_afectada, origen, destino)
                                                VALUES (?, 'PRESTAMO', ?, ?, 'Préstamos')
                                            """, (itm_n, itm_c, f"{l_origen} > {s_origen}"))
                                        conn_m.commit()
                                        conn_m.close()
                                        st.
