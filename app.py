import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURACIÓN DE SUPABASE ---
# En producción, usa st.secrets["SUPABASE_URL"] y st.secrets["SUPABASE_KEY"]
SUPABASE_URL = "https://ayygjsjqrefsbvrkpugc.supabase.co"
SUPABASE_KEY = "sb_publishable_8iDkihdWEY_aLkHrH1VOKg_IulmvtTj"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.set_page_config(page_title="Gestor Cloud de Reportes y Quiebres", layout="wide")

st.title("📂 Gestor Cloud de Reportes y Quiebres de Stock (Conectado a Supabase)")

# --- FUNCIÓN PARA OBTENER DATOS DE LA NUBE ---
def cargar_datos_nube():
    response = supabase.table("reportes").select("*").execute()
    if response.data:
        df = pd.DataFrame(response.data)
        df["fecha_reporte"] = pd.to_datetime(df["fecha_reporte"])
        return df
    else:
        return pd.DataFrame(columns=["id", "nombre_archivo", "categoria", "sucursal", "fecha_reporte", "url_archivo", "fecha_subida"])

# --- SECCIÓN 1: SUBIR ARCHIVOS A LA NUBE ---
with st.sidebar:
    st.header("Subir Nuevo Reporte")
    archivo = st.file_uploader("Selecciona el archivo", type=["pdf", "xlsx", "csv"])
    categoria = st.selectbox("Clasificación", ["Reporte de Auditoría", "Quiebre de Stock", "Mermas", "Otro"])
    sucursal = st.selectbox("Sucursal", ["Sucursal 01", "Sucursal 02", "Almacén Central"])
    fecha_reporte = st.date_input("Fecha del Reporte", datetime.today())
    
    if st.button("Subir a la Nube") and archivo:
        try:
            with st.spinner("Subiendo archivo a la nube..."):
                # 1. Subir archivo físico al Storage de Supabase
                file_path = f"{sucursal}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{archivo.name}"
                supabase.storage.from_("documentos").upload(
                    path=file_path,
                    file=archivo.getvalue(),
                    file_options={"content-type": archivo.type}
                )
                
                # 2. Obtener la URL pública del archivo
                public_url = supabase.storage.from_("documentos").get_public_url(file_path)
                
                # 3. Guardar los metadatos en la tabla de la base de datos
                nuevo_registro = {
                    "nombre_archivo": archivo.name,
                    "categoria": categoria,
                    "sucursal": sucursal,
                    "fecha_reporte": str(fecha_reporte),
                    "url_archivo": public_url,
                    "fecha_subida": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                supabase.table("reportes").insert(nuevo_registro).execute()
                st.success(f"¡Archivo '{archivo.name}' subido y registrado con éxito!")
                st.rerun() # Recargar la app para mostrar el nuevo registro
                
        except Exception as e:
            st.error(f"Error al subir el archivo: {e}")

# --- SECCIÓN 2: FILTROS Y VISUALIZACIÓN ---
df_db = cargar_datos_nube()

st.subheader("Filtros de Búsqueda")

col1, col2, col3 = st.columns(3)

with col1:
    cats_disponibles = df_db["categoria"].unique().tolist() if not df_db.empty else []
    cat_filtro = st.multiselect("Filtrar por Categoría", options=cats_disponibles)

with col2:
    sucs_disponibles = df_db["sucursal"].unique().tolist() if not df_db.empty else []
    suc_filtro = st.multiselect("Filtrar por Sucursal", options=sucs_disponibles)

with col3:
    if not df_db.empty and "fecha_reporte" in df_db.columns and not df_db["fecha_reporte"].isna().all():
        min_date = df_db["fecha_reporte"].min().date()
        max_date = df_db["fecha_reporte"].max().date()
        rango_fechas = st.date_input("Rango de Fechas del Reporte", [min_date, max_date])
    else:
        rango_fechas = []

# Aplicar filtros
df_filtrado = df_db.copy()

if not df_filtrado.empty:
    if cat_filtro:
        df_filtrado = df_filtrado[df_filtrado["categoria"].isin(cat_filtro)]
    if suc_filtro:
        df_filtrado = df_filtrado[df_filtrado["sucursal"].isin(suc_filtro)]
    if len(rango_fechas) == 2:
        inicio, fin = pd.to_datetime(rango_fechas[0]), pd.to_datetime(rango_fechas[1])
        df_filtrado = df_filtrado[(df_filtrado["fecha_reporte"] >= inicio) & (df_filtrado["fecha_reporte"] <= fin)]

st.markdown("---")
st.subheader("Reportes Almacenados en la Nube")

if not df_filtrado.empty:
    # Mostramos una tabla amigable y transformamos la URL en un hipervínculo interactivo
    for index, row in df_filtrado.iterrows():
        col_a, col_b, col_c, col_d, col_e = st.columns([2, 2, 2, 2, 2])
        col_a.write(f"**{row['nombre_archivo']}**")
        col_b.write(f"📁 {row['categoria']}")
        col_c.write(f"🏢 {row['sucursal']}")
        col_d.write(f"📅 {row['fecha_reporte'].strftime('%Y-%m-%d')}")
        col_e.markdown(f"[📥 Descargar Archivo]({row['url_archivo']})")
        st.divider()
else:
    st.info("No hay reportes que coincidan con los filtros seleccionados o la base de datos está vacía.")
