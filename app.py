import streamlit as st
from datetime import datetime, date
from supabase import create_client, Client
import io
import zipfile
import pandas as pd

# --- CONFIGURACIÓN DE CONTRASEÑA ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.subheader("🔒 Acceso Restringido")
        st.text_input("Ingrese la contraseña de acceso", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.subheader("🔒 Acceso Restringido")
        st.text_input("Ingrese la contraseña de acceso", type="password", on_change=password_entered, key="password")
        st.error("😕 Contraseña incorrecta. Inténtalo de nuevo.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
BUCKET_NAME = "documentos" 

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.set_page_config(page_title="Gestor Cloud de Documentos", layout="wide")
st.title("📂 Gestor Cloud y Consulta de Reportes")

# --- SECCIÓN 1: SUBIR ARCHIVOS ---
with st.sidebar:
    st.header("Subir Nuevo Archivo")
    sucursal_input = st.selectbox("Sucursal", ["Sucursal 01", "Sucursal 02", "Almacén Central"])
    fecha_input = st.date_input("Fecha del Reporte", datetime.today())
    motivo_input = st.text_input("Motivo / Descripción", placeholder="Ej. Inventario, mermas...")
    archivo = st.file_uploader("Selecciona tu archivo", type=["pdf", "xlsx", "csv", "zip", "doc", "docx"])
    
    if st.button("Subir a la Nube") and archivo:
        if not motivo_input.strip():
            st.warning("⚠️ Por favor, escribe un motivo o descripción.")
        else:
            try:
                with st.spinner("Comprimiendo y subiendo..."):
                    motivo_limpio = motivo_input.strip().replace(" ", "_").replace("/", "-")
                    nombre_base = archivo.name.rsplit('.', 1)[0]
                    nombre_zip = f"{nombre_base}.zip"
                    
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
                        zip_file.writestr(archivo.name, archivo.getvalue())
                    zip_buffer.seek(0)
                    
                    fecha_str = fecha_input.strftime('%Y-%m-%d')
                    file_path = f"{sucursal_input}/{fecha_str}_{motivo_limpio}_{nombre_zip}"
                    
                    supabase.storage.from_(BUCKET_NAME).upload(
                        path=file_path,
                        file=zip_buffer.getvalue(),
                        file_options={"content-type": "application/zip"}
                    )
                    
                    st.success("¡Archivo subido con éxito!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error al subir: {e}")

# --- SECCIÓN 2: FILTROS (SUCURSAL, FECHA Y BÚSQUEDA) ---
st.markdown("---")
st.subheader("Filtros de Búsqueda")

@st.cache_data(ttl=10)
def obtener_todos_los_archivos():
    lista_archivos = []
    sucursales = ["Sucursal 01", "Sucursal 02", "Almacén Central"]
    for suc in sucursales:
        try:
            archivos_suc = supabase.storage.from_(BUCKET_NAME).list(suc)
            for file in archivos_suc:
                if file['name'] != '.emptyFolderPlaceholder':
                    full_path = f"{suc}/{file['name']}"
                    partes = file['name'].split('_', 2)
                    fecha_str = partes[0] if len(partes) > 0 else "2026-01-01"
                    
                    # Intentar convertir la fecha a objeto date para los filtros
                    try:
                        obj_fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                    except:
                        obj_fecha = date.today()
                        
                    motivo = partes[1].replace("_", " ") if len(partes) > 1 else "Sin motivo"
                    nombre_real = partes[2] if len(partes) > 2 else file['name']
                    
                    lista_archivos.append({
                        "path": full_path,
                        "sucursal": suc,
                        "fecha_str": fecha_str,
                        "fecha_obj": obj_fecha,
                        "motivo": motivo,
                        "nombre": nombre_real
                    })
        except Exception:
            pass
    return lista_archivos

archivos_cloud = obtener_todos_los_archivos()

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    sucs_unicas = list(set([a["sucursal"] for a in archivos_cloud]))
    filtro_sucursal = st.multiselect("Filtrar por Sucursal", options=sucs_unicas)

with col_f2:
    # Filtro de Rango de Fechas en lugar de Motivo
    rango_fechas = st.date_input(
        "Filtrar por Rango de Fechas",
        value=(date.today().replace(day=1), date.today()),
        key="filtro_fechas"
    )

with col_f3:
    busqueda_texto = st.text_input("🔍 Buscar palabra clave", "")

# Aplicación de filtros optimizada
archivos_filtrados = archivos_cloud
if filtro_sucursal:
    archivos_filtrados = [a for a in archivos_filtrados if a["sucursal"] in filtro_sucursal]

if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
    inicio, fin = rango_fechas
    archivos_filtrados = [a for a in archivos_filtrados if inicio <= a["fecha_obj"] <= fin]
elif isinstance(rango_fechas, date):
    archivos_filtrados = [a for a in archivos_filtrados if a["fecha_obj"] == rango_fechas]

if busqueda_texto:
    archivos_filtrados = [a for a in archivos_filtrados if busqueda_texto.lower() in a["nombre"].lower() or busqueda_texto.lower() in a["motivo"].lower()]

# --- SECCIÓN 3: LISTADO Y ACCESOS RÁPIDOS ---
st.markdown("---")
st.subheader(f"Archivos Encontrados ({len(archivos_filtrados)})")

if archivos_filtrados:
    for item in archivos_filtrados:
        with st.container():
            col_a, col_b, col_c, col_d, col_e, col_f = st.columns([2, 1.2, 1.8, 1.2, 1.2, 0.8])
            with col_a:
                st.write(f"📄 **{item['nombre']}**")
            with col_b:
                st.write(f"🏢 {item['sucursal']}")
            with col_c:
                st.write(f"📅 {item['fecha_str']} - *{item['motivo']}*")
            
            # Descarga mediante enlace público instantáneo (sin demoras)
            with col_d:
                try:
                    public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(item["path"])
                    st.markdown(f"[📥 Descargar]({public_url})")
                except Exception:
                    st.write("No disponible")

            # Botón para Consultar el contenido en pantalla
            with col_e:
                if st.button("👁️ Consultar", key=f"ver_{item['path']}"):
                    st.session_state["archivo_activo"] = item["path"]
            
            # Botón para Eliminar
            with col_f:
                if st.button("🗑️", key=f"del_{item['path']}"):
                    try:
                        supabase.storage.from_(BUCKET_NAME).remove([item["path"]])
                        st.success("¡Eliminado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            st.divider()

    # --- PANEL DE CONSULTA RÁPIDA EN PANTALLA ---
    if "archivo_activo" in st.session_state and st.session_state["archivo_activo"]:
        st.markdown("---")
        st.info(f"🔍 **Vista de Consulta para:** `{st.session_state['archivo_activo']}`")
        try:
            bytes_archivo = supabase.storage.from_(BUCKET_NAME).download(st.session_state["archivo_activo"])
            with zipfile.ZipFile(io.BytesIO(bytes_archivo)) as z:
                for filename in z.namelist():
                    st.write(f"📂 Archivo interno: **{filename}**")
                    with z.open(filename) as f:
                        if filename.endswith('.csv'):
                            df = pd.read_csv(f)
                            st.dataframe(df, use_container_width=True)
                        elif filename.endswith('.xlsx'):
                            df = pd.read_excel(f)
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.text("Este formato no permite vista previa tabular, usa la descarga directa.")
        except Exception as e:
            st.error(f"No se pudo cargar la vista previa: {e}")
            
        if st.button("Cerrar Consulta"):
            del st.session_state["archivo_activo"]
            st.rerun()
            
else:
    st.info("No hay archivos que coincidan con los filtros seleccionados.")
