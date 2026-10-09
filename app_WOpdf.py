import os
import re
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# Configuración de la página en Streamlit
st.set_page_config(
    page_title="Gestión y Firma de Órdenes de Trabajo",
    page_icon="📝",
    layout="wide",
)

# Definición de directorios locales de trabajo
DIR_WO = "work_orders"
DIR_COMPLETED = "completed"

# Ruta de destino en tu OneDrive Local (Windows)
DIR_ONEDRIVE = r"C:\Users\hsanchez\OneDrive - PANAMA RAIL\Documentos\Work Order\Work Order finalizada automaticamente"

os.makedirs(DIR_WO, exist_ok=True)
os.makedirs(DIR_COMPLETED, exist_ok=True)

try:
    os.makedirs(DIR_ONEDRIVE, exist_ok=True)
except Exception:
    pass


def extraer_datos_pdf(pdf_path):
    """Busca de manera dinámica el número de OT recorriendo el texto de todas las páginas."""
    num_ot = ""
    try:
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for pagina in doc:
            texto_completo += pagina.get_text("text") + "\n"
        doc.close()

        coincidencia = re.search(
            r"N[°o]?\s*de\s*OT[:\s]*(\d+)", texto_completo, re.IGNORECASE
        )
        if not coincidencia:
            coincidencia = re.search(
                r"(?:OT|WO)[^\d]*(\d+)", texto_completo, re.IGNORECASE
            )

        if coincidencia:
            num_ot = coincidencia.group(1)
    except Exception as e:
        st.warning(f"No se pudo extraer el N° de OT automáticamente: {e}")

    return num_ot


def estampar_datos_y_firma(
    pdf_input_path,
    pdf_output_path,
    img_firma_path,
    departamento,
    sitio,
    fecha_completada,
    num_ot,
    img_foto_path=None,
):
    """Encuentra dinámicamente la posición de los campos e inserta los textos, la firma y la foto de la actividad."""
    doc = fitz.open(pdf_input_path)
    pagina = doc[0]  # Primera página de la OT
    page_rect = pagina.rect

    # 1. POSICIONAR 'DEPARTAMENTO:'
    if departamento:
        matches = pagina.search_for("DEPARTAMENTO:")
        if matches:
            rect = matches[0]
            pagina.insert_text(
                (rect.x1 + 10, rect.y1 - 2),
                departamento,
                fontsize=9,
                color=(0, 0, 0),
            )
        else:
            pagina.insert_text(
                (page_rect.width * 0.35, page_rect.height * 0.27),
                departamento,
                fontsize=9,
                color=(0, 0, 0),
            )

    # 2. POSICIONAR 'Sitio:'
    if sitio:
        matches = pagina.search_for("Sitio:")
        if matches:
            rect = matches[0]
            pagina.insert_text(
                (rect.x1 + 10, rect.y1 - 2), sitio, fontsize=9, color=(0, 0, 0)
            )
        else:
            pagina.insert_text(
                (page_rect.width * 0.35, page_rect.height * 0.30),
                sitio,
                fontsize=9,
                color=(0, 0, 0),
            )

    # 3. POSICIONAR 'fecha completada:'
    if fecha_completada:
        matches_fecha = pagina.search_for("fecha completada:")
        if not matches_fecha:
            matches_fecha = pagina.search_for("FECHA COMPLETADA:")

        if matches_fecha:
            rect = matches_fecha[0]
            pagina.insert_text(
                (rect.x1 + 8, rect.y1 - 2),
                str(fecha_completada),
                fontsize=9,
                color=(0, 0, 0),
            )
        else:
            pagina.insert_text(
                (page_rect.width * 0.70, page_rect.height * 0.15),
                str(fecha_completada),
                fontsize=9,
                color=(0, 0, 0),
            )

    # 4. POSICIONAR FIRMA EN 'Autorizado' (ELEVADO PARA NO TAPAR EL TEXTO)
    matches_aut = pagina.search_for("Autorizado")
    if matches_aut:
        rect = matches_aut[0]
        # Se eleva y0 (-60) y se coloca y1 (rect.y0 - 2) justo por encima del texto "Autorizado"
        firma_box = fitz.Rect(
            rect.x0 - 15, rect.y0 - 60, rect.x1 + 75, rect.y0 - 2
        )
        pagina.insert_image(firma_box, filename=img_firma_path)
    else:
        firma_box = fitz.Rect(
            page_rect.width * 0.08,
            page_rect.height * 0.32,
            page_rect.width * 0.35,
            page_rect.height * 0.40,
        )
        pagina.insert_image(firma_box, filename=img_firma_path)

    # 5. POSICIONAR FOTO DE LA ACTIVIDAD
    if img_foto_path and os.path.exists(img_foto_path):
        matches_sup = pagina.search_for("(supervisor)")
        if matches_sup:
            rect_sup = matches_sup[0]
            foto_box = fitz.Rect(
                page_rect.width * 0.12,
                rect_sup.y1 + 15,
                page_rect.width * 0.88,
                page_rect.height * 0.92,
            )
        else:
            foto_box = fitz.Rect(
                page_rect.width * 0.12,
                page_rect.height * 0.48,
                page_rect.width * 0.88,
                page_rect.height * 0.92,
            )
        pagina.insert_image(foto_box, filename=img_foto_path)

    doc.save(pdf_output_path)
    doc.close()


# ==========================================
# INTERFAZ STREAMLIT
# ==========================================
st.title("📝 Procesamiento, Edición y Firma de Work Order (WO)")
st.markdown(
    "Cargue el PDF de la Orden de Trabajo para extraer datos, ingresar campos, estampar la firma y adjuntar fotos."
)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Cargar Documento y Datos")
    uploaded_file = st.file_uploader(
        "Cargar PDF de la Orden de Trabajo", type=["pdf"]
    )

    ot_detectada = ""
    if uploaded_file is not None:
        temp_input_path = os.path.join(DIR_WO, "temp_uploaded.pdf")
        with open(temp_input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        ot_detectada = extraer_datos_pdf(temp_input_path)
        if ot_detectada:
            st.success(
                f"🔍 N° de OT detectado en el PDF: **{ot_detectada}**"
            )

    numero_ot = st.text_input(
        "N° de OT", value=ot_detect