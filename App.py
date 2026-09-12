import sqlite3
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pandas as pd
from google import genai

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
            categoria TEXT,
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
    
    cursor.execute("PRAGMA table_info(items)")
    columnas_items = [col[1] for col in cursor.fetchall()]
    if "categoria" not in columnas_items:
        cursor.execute("ALTER TABLE items ADD COLUMN categoria TEXT")
    
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

st.title("📦 Gestor de Inventario Casero con Administrador Gemini")

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

# --- CONFIGURACIÓN DEL ASISTENTE INTELIGENTE CON GEMINI ---
if "messages" not in st.session_state:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM prestamos WHERE devuelto = 0")
    num_prestamos = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM items WHERE cantidad <= stock_minimo")
    num_bajos = cursor.fetchone()[0]
    conn.close()
    
    saludo_inicial = f"¡Hola! Tienes {num_prestamos} avisos de préstamos pendientes y {num_bajos} ítems con stock bajo. ¿Qué quieres hacer hoy?"
    st.session_state.messages = [{"role": "model", "content": saludo_inicial}]

st.sidebar.markdown("---")
st.sidebar.subheader("🎙️ Administrador Gemini por Voz y Texto")

for msg in st.session_state.messages[-4:]:
    rol_icono = "🤖" if msg["role"] == "model" else "👤"
    if msg["role"] == "model":
        st.sidebar.info(f"{rol_icono} {msg['content']}")
    else:
        st.sidebar.success(f"{rol_icono} {msg['content']}")

# --- COMPONENTE DE VOZ INTERACTIVA Y SALUDO AUTOMÁTICO ---
voice_component_html = """
<div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; text-align: center;">
    <p style="font-family: sans-serif; font-size: 14px; color: #31333F;">Administrador de Voz Activo:</p>
    <button id="micBtn" onclick="toggleMic()" style="background-color: #FF4B4B; color: white; border: none; padding: 10px 20px; border-radius: 20px; font-weight: bold; cursor: pointer; font-size: 16px;">🎤 Iniciar Voz</button>
    <p id="status" style="font-family: sans-serif; font-size: 12px; color: #666; margin-top: 10px;">Micrófono inactivo</p>
</div>

<script>
let recognition;
let isListening = false;

function decirTexto(texto) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const mensaje = new SpeechSynthesisUtterance(texto);
        mensaje.lang = 'es-ES';
        mensaje.rate = 1.0;
        mensaje.pitch = 1.0;
        
        setTimeout(() => {
            window.speechSynthesis.speak(mensaje);
        }, 300);
    }
}

window.onload = function() {
    decirTexto("Bienvenido de nuevo jefe ¿en qué mierda puedo ayudarte?");
};

window.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'hablar') {
        decirTexto(event.data.texto);
    }
});

function toggleMic() {
    const btn = document.getElementById('micBtn');
    const status = document.getElementById('status');

    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert('Tu navegador móvil no soporta reconocimiento de voz nativo. Usa Chrome o Safari.');
        return;
    }

    if (!isListening) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.lang = 'es-ES';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = function() {
            isListening = true;
            btn.style.backgroundColor = '#28a745';
            btn.innerText = '🔴 Escuchando...';
            status.innerText = 'Habla ahora...';
        };

        recognition.onresult = function(event) {
            const speechToText = event.results[0][0].transcript;
            status.innerText = 'Capturado: "' + speechToText + '"';
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: speechToText}, '*');
        };

        recognition.onerror = function(event) {
            status.innerText = 'Error: ' + event.error;
            stopMic();
        };

        recognition.onend = function() {
            stopMic();
        };

        recognition.start();
    } else {
        stopMic();
    }
}

function stopMic() {
    isListening = false;
    const btn = document.getElementById('micBtn');
    const status = document.getElementById('status');
    btn.style.backgroundColor = '#FF4B4B';
    btn.innerText = '🎤 Iniciar Voz';
    status.innerText = 'En pausa';
    if (recognition) {
        recognition.stop();
    }
}
</script>
"""

texto_voz_capturado = components.html(voice_component_html, height=150)
texto_usuario = st.sidebar.text_input("O escribe tu orden aquí:", key="txt_input_gemini")

if texto_voz_capturado:
    texto_usuario = str(texto_voz_capturado)

if st.sidebar.button("Enviar Orden a Gemini") and texto_usuario:
    st.session_state.messages.append({"role": "user", "content": texto_usuario})
    
    if any(palabra in texto_usuario.lower() for palabra in ["olvíalo", "cancela", "olvida", "déjalo", "cancelar"]):
        respuesta = "Entendido, operación cancelada. ¿En qué otra cosa te puedo ayudar?"
        st.session_state.messages.append({"role": "model", "content": respuesta})
        st.rerun()
    
    try:
        client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY", ""))
        
        historial_gemini = []
        for m in st.session_state.messages[-6:]:
            rol = "user" if m["role"] == "user" else "model"
            historial_gemini.append({"role": rol, "parts": [{"text": m["content"]}]})
            
        chat = client.chats.create(
            model="gemini-2.5-flash",
            history=historial_gemini[:-1],
            config={
                "system_instruction": "Eres una IA avanzada, amable y experta que actúa como administradora absoluta de un sistema de inventario casero en SQLite. Responde de forma natural a cualquier pregunta general o conversacional, pero si el usuario te pide gestionar entradas, consultas o cambios en el inventario, guíale o indícale cómo proceder con precisión."
            }
        )
        
        response = chat.send_message(texto_usuario)
        respuesta = response.text
    except Exception as e:
        respuesta = f"Error al conectar con Gemini: {e}"
        
    st.session_state.messages.append({"role": "model", "content": respuesta})
    st.rerun()

# --- MENÚ DE NAVEGACIÓN ---
menu = st.sidebar.selectbox("Menú de Opciones", ["1. BUSCAR", "2. MODIFICAR & MOVER", "3. LOCALIZACIONES"])

# ==========================================
# 1. BUSCAR
# ==========================================
if menu == "1. BUSCAR":
    st.header("🔍 Buscar en el Inventario")
    
    if "filtro_click" not in st.session_state:
        st.session_state.filtro_click = ""

    col_b1, col_b2, col_b3 = st.columns([2, 1, 1])
    with col_b1:
        txt_busqueda = st.text_input("Término de búsqueda:", value=st.session_state.filtro_click)
    with col_b2:
        criterio = st.selectbox("Filtrar por criterio:", ["Todos", "categoria", "marca", "localizacion", "sublocalizacion", "establecimiento", "estado_uso"])
    with col_b3:
        if st.button("Limpiar Filtro"):
            st.session_state.filtro_click = ""
            st.rerun()

    conn = get_connection()
    cursor = conn.cursor()
    
    query_cols = "nombre, categoria, marca, localizacion, sublocalizacion, establecimiento, cantidad, stock_minimo, estado_uso, descripcion, anotaciones, ultima_modificacion"
    
    if txt_busqueda:
        texto = f"%{txt_busqueda}%"
        if criterio == "Todos":
            query = f"SELECT {query_cols} FROM items WHERE nombre LIKE ? OR descripcion LIKE ? OR categoria LIKE ? OR marca LIKE ? OR localizacion LIKE ? OR sublocalizacion LIKE ? OR establecimiento LIKE ? OR estado_uso LIKE ?"
            cursor.execute(query, (texto, texto, texto, texto, texto, texto, texto, texto))
        else:
            query = f"SELECT {query_cols} FROM items WHERE {criterio} LIKE ?"
            cursor.execute(query, (texto,))
    else:
        cursor.execute(f"SELECT {query_cols} FROM items")
        
    rows = cursor.fetchall()
    conn.close()
    
    st.subheader(f"Resultados en Tabla ({len(rows)} ítems encontrados):")
    
    if rows:
        df = pd.DataFrame(rows, columns=[
            "Nombre", "Categoría", "Marca", "Localización", "Sublocalización", "Establecimiento",
            "Cantidad", "Stock Mín.", "Estado/Uso", "Descripción", "Anotaciones", "Última Modif."
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No se encontraron registros coincidentes.")
        if txt_busqueda:
            frase_no_encontrado = "Pfff que follón, ¿Eso no estabaaaaaa por la p de polea?"
            components.html(f"""
            <script>
                window.parent.postMessage({{type: 'hablar', texto: '{frase_no_encontrado}'}}, '*');
            </script>
            """, height=0)

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
            categoria = st.text_input("Categoría")
            marca = st.text_input("Marca")
            estab = st.text_input("Establecimiento de compra")
            
            col1, col2 = st.columns(2)
            with col1:
                cant = st.number_input("Cantidad inicial", min_value=0, value=1)
            with col2:
                stock_min = st.number_input("Stock Mínimo de alerta", min_value=0, value=1)
                
            estado_uso = st.text_input("Estado o Uso del producto")
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
                    st.error("Debes crear al menos una localización primero.")
                else:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR REPLACE INTO items (nombre, categoria, marca, establecimiento, localizacion, sublocalizacion, cantidad, stock_minimo, estado_uso, descripcion, anotaciones, estado_stock)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'normal')
                        """, (nombre.strip(), categoria, marca, estab, loc_elegida, subloc_elegida if subloc_elegida != "Ninguna" else "", int(cant), int(stock_min), estado_uso, desc, anot))
                        
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
        st.subheader("🚚 Mover o Prestar Ítems")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, cantidad, localizacion, sublocalizacion FROM items")
        items_db = cursor.fetchall()
        conn.close()
        
        if not items_db:
            st.info("No hay ítems registrados en el inventario.")
        else:
            item_dict = {f"{i[0]} (Stock: {i[1]} | Ubicación: {i[2]} > {i[3]})": i for i in items_db}
            seleccion_items = st.multiselect("Selecciona ítems a mover:", list(item_dict.keys()))
            destino_opciones = locs + ["Préstamos"]
            dest_loc = st.selectbox("Localización Destino", destino_opciones)
            
            if st.button("Procesar Movimiento"):
                if seleccion_items:
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
                    st.success("¡Movimiento realizado correctamente!")
                    st.rerun()

# ==========================================
# 3. LOCALIZACIONES
# ==========================================
elif menu == "3. LOCALIZACIONES":
    st.header("🏠 Gestión de Localizaciones y Sublocalizaciones")
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("form_loc"):
            nueva_loc = st.text_input("Nombre de la Localización")
            if st.form_submit_button("Crear Localización") and nueva_loc.strip():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO localizaciones (nombre_localizacion) VALUES (?)", (nueva_loc.strip(),))
                    conn.commit()
                    conn.close()
                    st.success("Localización creada.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ya existe.")
                    
    with col2:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre_localizacion FROM localizaciones")
        locs_padre = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        with st.form("form_subloc"):
            loc_padre = st.selectbox("Localización Padre", locs_padre if locs_padre else ["Crea una primero"])
            nueva_subloc = st.text_input("Nombre de la Sublocalización")
            if st.form_submit_button("Crear Sublocalización") and nueva_subloc.strip() and locs_padre:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM localizaciones WHERE nombre_localizacion = ?", (loc_padre,))
                res = cursor.fetchone()
                if res:
                    cursor.execute("INSERT INTO sublocalizaciones (localizacion_id, nombre_sublocalizacion) VALUES (?, ?)", (res[0], nueva_subloc.strip()))
                    conn.commit()
                    conn.close()
                    st.success("Sublocalización añadida.")
                    st.rerun()
