import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from PIL import Image
import fitz  # PyMuPDF
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# Configuración de la página en Streamlit
st.set_page_config(
    page_title="Gestión y Firma de Órdenes de Trabajo",
    page_icon="📝",
    layout="wide"
)

# Definición de directorios locales
DIR_WO = "work_orders"
DIR_COMPLETED = "completed"
os.makedirs(DIR_WO, exist_ok=True)
os.makedirs(DIR_COMPLETED, exist_ok=True)


def extraer_datos_pdf(pdf_path):
    """
    Busca de manera dinámica el número de OT recorriendo el texto de todas las páginas.
    """
    num_ot = ""
    try:
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for pagina in doc:
            texto_completo += pagina.get_text("text") + "\n"
        doc.close()

        coincidencia = re.search(r'N[°o]?\s*de\s*OT[:\s]*(\d+)', texto_completo, re.IGNORECASE)
        if not coincidencia:
            coincidencia = re.search(r'(?:OT|WO)[^\d]*(\d+)', texto_completo, re.IGNORECASE)

        if coincidencia:
            num_ot = coincidencia.group(1)
    except Exception as e:
        st.warning(f"No se pudo extraer el N° de OT automáticamente: {e}")

    return num_ot


def estampar_datos_y_firma(pdf_input_path, pdf_output_path, img_firma_path, departamento, sitio, fecha_completada, num_ot):
    """
    Encuentra dinámicamente la posición de 'DEPARTAMENTO:', 'Sitio:', 'fecha completada:' y 'Autorizado'
    e inserta los textos y la firma en su lugar correspondiente.
    """
    doc = fitz.open(pdf_input_path)
    pagina = doc[0]  # Primera página de la OT
    page_rect = pagina.rect

    # 1. POSICIONAR 'DEPARTAMENTO:'
    if departamento:
        matches = pagina.search_for("DEPARTAMENTO:")
        if matches:
            rect = matches[0]
            pagina.insert_text((rect.x1 + 10, rect.y1 - 2), departamento, fontsize=9, color=(0, 0, 0))
        else:
            pagina.insert_text((page_rect.width * 0.35, page_rect.height * 0.27), departamento, fontsize=9, color=(0, 0, 0))

    # 2. POSICIONAR 'Sitio:'
    if sitio:
        matches = pagina.search_for("Sitio:")
        if matches:
            rect = matches[0]
            pagina.insert_text((rect.x1 + 10, rect.y1 - 2), sitio, fontsize=9, color=(0, 0, 0))
        else:
            pagina.insert_text((page_rect.width * 0.35, page_rect.height * 0.30), sitio, fontsize=9, color=(0, 0, 0))

    # 3. POSICIONAR 'fecha completada:'
    if fecha_completada:
        matches_fecha = pagina.search_for("fecha completada:")
        if not matches_fecha:
            matches_fecha = pagina.search_for("FECHA COMPLETADA:")
        
        if matches_fecha:
            rect = matches_fecha[0]
            pagina.insert_text((rect.x1 + 8, rect.y1 - 2), str(fecha_completada), fontsize=9, color=(0, 0, 0))
        else:
            pagina.insert_text((page_rect.width * 0.70, page_rect.height * 0.15), str(fecha_completada), fontsize=9, color=(0, 0, 0))

    # 4. POSICIONAR FIRMA EN 'Autorizado'
    matches_aut = pagina.search_for("Autorizado")
    if matches_aut:
        rect = matches_aut[0]
        firma_box = fitz.Rect(
            rect.x0 - 20,
            rect.y0 - 65,
            rect.x1 + 80,
            rect.y0 - 5
        )
        pagina.insert_image(firma_box, filename=img_firma_path)
    else:
        firma_box = fitz.Rect(
            page_rect.width * 0.08,
            page_rect.height * 0.85,
            page_rect.width * 0.35,
            page_rect.height * 0.93
        )
        pagina.insert_image(firma_box, filename=img_firma_path)

    doc.save(pdf_output_path)
    doc.close()


def enviar_correo_smtp(destinatario, asunto, cuerpo, path_adjunto):
    """
    Envía el correo mediante SSL (puerto 465) o STARTTLS (puerto 587) según la configuración.
    """
    if "smtp" not in st.secrets:
        return False, "No se encontró la sección [smtp] en Secrets de Streamlit. Verifique en Settings > Secrets."

    smtp_server = st.secrets["smtp"]["server"]
    smtp_port = int(st.secrets["smtp"]["port"])
    smtp_user = st.secrets["smtp"]["user"]
    smtp_password = st.secrets["smtp"]["password"]

    msg = MIMEMultipart()