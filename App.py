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
# 1. BUSCAR
# ==========================================
if menu == "1. BUSCAR":
    st.header("🔍 Buscar en el Inventario")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        txt_busqueda = st.text_input("Término de búsqueda:")
    with col2:
        criterio = st.selectbox("Filtrar por criterio:", ["Todos", "localizacion", "sublocalizacion", "descripcion", "marca", "establecimiento", "estado_uso"])
        
    conn = get_connection()
    cursor = conn.cursor()
    
    if txt_busqueda:
        texto = f"%{txt_busqueda}%"
        if criterio == "Todos":
            query = """SELECT nombre, cantidad, localizacion, sublocalizacion, estado_uso, marca, establecimiento, estado_stock, descripcion, anotaciones, ultima_modificacion FROM items 
                       WHERE nombre LIKE ? OR descripcion LIKE ? OR marca LIKE ? OR establecimiento LIKE ? OR localizacion LIKE ?"""
            cursor.execute(query, (texto, texto, texto, texto, texto))
        else:
            query = f"SELECT nombre, cantidad, localizacion, sublocalizacion, estado_uso, marca, establecimiento, estado_stock, descripcion, anotaciones, ultima_modificacion FROM items WHERE {criterio} LIKE ?"
            cursor.execute(query, (texto,))
    else:
        cursor.execute("SELECT nombre, cantidad, localizacion, sublocalizacion, estado_uso, marca, establecimiento, estado_stock, descripcion, anotaciones, ultima_modificacion FROM items")
        
    rows = cursor.fetchall()
    conn.close()
    
    st.subheader(f"Resultados ({len(rows)} ítems encontrados):")
    
    for r in rows:
        nombre, cant, loc, subloc, uso, marca, estab, estado_s, desc, anot, ultima_mod = r
        
        prefix = ""
        if estado_s == "comprar":
            prefix = "🟢 [Comprar]"
        elif estado_s == "agotado_negativo":
            prefix = "🔴 [X-Negativo]"
        elif loc == "Préstamos":
            prefix = "🟡 [✈️ Préstamo]"
            
        with st.expander(f"{prefix} **{nombre}** (Cant: {cant}) — {loc} > {subloc}"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**Marca:** {marca if marca else '-'}")
                st.write(f"**Establecimiento:** {estab if estab else '-'}")
                st.write(f"**Estado/Uso:** {uso if uso else '-'}")
                st.write(f"**Descripción:** {desc if desc else '-'}")
            with col_b:
                st.write(f"**Anotaciones:** {anot if anot else '-'}")
                st.write(f"**Última Modificación:** {ultima_mod}")
                if estado_s in ["comprar", "agotado_negativo"]:
                    st.info(f"**Detalle Estado ({estado_s}):** {r[11]}")
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT tipo, cantidad_afectada, origen, destino, fecha_hora FROM movimientos WHERE item_nombre = ?", (nombre,))
            movs = cursor.fetchall()
            conn.close()
            
            if movs:
                st.markdown("**Historial de Movimientos:**")
                for m in movs:
                    st.text(f"[{m[4]}] {m[0]} - Cant: {m[1]} (De: {m[2]} ➡️ A: {m[3]})")

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
    
    # 2.1 ENTRADAS
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

    # 2.3 MOVER / PRESTAR (Con soporte múltiple, masivo por sublocalización y Modal de Préstamos)
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
                        # Abrir ventana emergente (Modal) obligatoria para Préstamos
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

            else: # Modo Masivo por Sublocalización
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
                                        st.success("¡Todos los ítems de la sublocalización han sido prestados con éxito!")
                                        st.rerun()
                            modal_prestamo_masivo()
                        else:
                            for itm_n, itm_c in items_en_subloc:
                                cursor.execute("UPDATE items SET localizacion = ?, sublocalizacion = '' WHERE nombre = ?", (dest_loc_masivo, itm_n))
                                cursor.execute("""
                                    INSERT INTO movimientos (item_nombre, tipo, cantidad_afectada, origen, destino)
                                    VALUES (?, 'MOVIMIENTO', ?, ?, ?)
                                """, (itm_n, itm_c, f"{l_origen} > {s_origen}", dest_loc_masivo))
                            conn.commit()
                            conn.close()
                            st.success(f"¡Todos los ítems de '{subloc_elegida_str}' han sido movidos a '{dest_loc_masivo}'!")
                            st.rerun()

# ==========================================
# 3. LOCALIZACIONES
# ==========================================
elif menu == "3. LOCALIZACIONES":
    st.header("🏠 Gestión de Localizaciones y Sublocalizaciones")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Añadir Localización Principal")
        with st.form("form_loc"):
            nueva_loc = st.text_input("Nombre de la Localización (ej. Cochera, Trastero)")
            btn_crear_loc = st.form_submit_button("Crear Localización")
            if btn_crear_loc and nueva_loc.strip():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO localizaciones (nombre_localizacion) VALUES (?)", (nueva_loc.strip(),))
                    conn.commit()
                    conn.close()
                    st.success(f"Localización '{nueva_loc}' creada con éxito.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Esa localización ya existe.")
                    
    with col2:
        st.subheader("Añadir Sublocalización")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre_localizacion FROM localizaciones")
        locs_padre = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        with st.form("form_subloc"):
            opciones_locs = locs_padre if locs_padre else ["Crea una localización primero"]
            loc_padre_elegida = st.selectbox("Localización Padre", opciones_locs)
            nueva_subloc = st.text_input("Nombre de la Sublocalización (ej. Estantería 2, Caja Roja)")
            btn_crear_subloc = st.form_submit_button("Crear Sublocalización")
            
            if btn_crear_subloc and nueva_subloc.strip() and locs_padre:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM localizaciones WHERE nombre_localizacion = ?", (loc_padre_elegida,))
                res = cursor.fetchone()
                if res:
                    cursor.execute("INSERT INTO sublocalizaciones (localizacion_id, nombre_sublocalizacion) VALUES (?, ?)", (res[0], nueva_subloc.strip()))
                    conn.commit()
                    conn.close()
                    st.success(f"Sublocalización '{nueva_subloc}' añadida a '{loc_padre_elegida}'.")
                    st.rerun()

    st.markdown("---")
    st.subheader("Estancias y Subestancias Actuales:")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre_localizacion FROM localizaciones")
    locs_data = cursor.fetchall()
    for l_id, l_nombre in locs_data:
        cursor.execute("SELECT nombre_sublocalizacion FROM sublocalizaciones WHERE localizacion_id = ?", (l_id,))
        sublocs_data = [s[0] for s in cursor.fetchall()]
        st.markdown(f"📍 **{l_nombre}**")
        if sublocs_data:
            for s in sublocs_data:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;└─ {s}")
        else:
            st.markdown("&nbsp;&nbsp;&nbsp;&nbsp;└─ *(Sin sublocalizaciones)*")
    conn.close()
