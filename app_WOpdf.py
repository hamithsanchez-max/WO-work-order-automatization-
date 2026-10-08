import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from PIL import Image
import fitz  # PyMuPDF
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# Configuración de la página en Streamlit
st.set_page_config(
    page_title="Gestión y Firma de Ordenes de Trabajo",
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

        # Patrones para capturar el número de OT (ej. "N° de OT: 34115" o "OT: 34115")
        coincidencia = re.search(r'N[°o]?\s*de\s*OT[:\s]*(\d+)', texto_completo, re.IGNORECASE)
        if not coincidencia:
            coincidencia = re.search(r'(?:OT|WO)[^\d]*(\d+)', texto_completo, re.IGNORECASE)

        if coincidencia:
            num_ot = coincidencia.group(1)
    except Exception as e:
        st.warning(f"No se pudo extraer el N° de OT automáticamente: {e}")

    return num_ot


def estampar_datos_y_firma(pdf_input_path, pdf_output_path, img_firma_path, departamento, sitio, num_ot):
    """
    Encuentra dinámicamente la posición de 'DEPARTAMENTO:', 'Sitio:' y 'Autorizado' en el PDF
    e inserta los textos y la firma exactamente en su lugar correspondiente.
    """
    doc = fitz.open(pdf_input_path)
    pagina = doc[0]  # Página principal de la orden de trabajo
    page_rect = pagina.rect  # Ancho y alto del documento

    # --------------------------------------------------------------------------
    # 1. POSICIONAR 'DEPARTAMENTO:'
    # --------------------------------------------------------------------------
    if departamento:
        matches = pagina.search_for("DEPARTAMENTO:")
        if matches:
            rect = matches[0]
            x_pos = rect.x1 + 10
            y_pos = rect.y1 - 2
            pagina.insert_text((x_pos, y_pos), departamento, fontsize=9, color=(0, 0, 0))
        else:
            pagina.insert_text((page_rect.width * 0.35, page_rect.height * 0.27), departamento, fontsize=9, color=(0, 0, 0))

    # --------------------------------------------------------------------------
    # 2. POSICIONAR 'Sitio:'
    # --------------------------------------------------------------------------
    if sitio:
        matches = pagina.search_for("Sitio:")
        if matches:
            rect = matches[0]
            x_pos = rect.x1 + 10
            y_pos = rect.y1 - 2
            pagina.insert_text((x_pos, y_pos), sitio, fontsize=9, color=(0, 0, 0))
        else:
            pagina.insert_text((page_rect.width * 0.35, page_rect.height * 0.30), sitio, fontsize=9, color=(0, 0, 0))

    # --------------------------------------------------------------------------
    # 3. POSICIONAR FIRMA EN 'Autorizado'
    # --------------------------------------------------------------------------
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
    """Envía el correo electrónico con el archivo PDF adjunto."""
    try:
        smtp_server = st.secrets["smtp"]["server"]
        smtp_port = int(st.secrets["smtp"]["port"])
        smtp_user = st.secrets["smtp"]["user"]
        smtp_password = st.secrets["smtp"]["password"]

        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo, "plain"))

        if os.path.exists(path_adjunto):
            with open(path_adjunto, "rb") as f:
                adjunto = MIMEApplication(f.read(), _subtype="pdf")
                adjunto.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=os.path.basename(path_adjunto)
                )
                msg.attach(adjunto)
        else:
            return False, "El archivo PDF firmado no fue encontrado."

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        return True, "Correo enviado exitosamente."
    except Exception as e:
        return False, f"Error al enviar el correo: {str(e)}"


# ==========================================
# INTERFAZ STREAMLIT
# ==========================================
st.title("📝 Procesamiento, Edición y Firma de Work Order (WO)")
st.markdown("Cargue el PDF de la Orden de Trabajo para extraer datos, ingresar campos y estampar la firma.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Cargar Documento y Datos")
    uploaded_file = st.file_uploader("Cargar PDF de la Orden de Trabajo", type=["pdf"])

    ot_detectada = ""
    if uploaded_file is not None:
        temp_input_path = os.path.join(DIR_WO, "temp_uploaded.pdf")
        with open(temp_input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        ot_detectada = extraer_datos_pdf(temp_input_path)
        if ot_detectada:
            st.success(f"🔍 N° de OT detectado en el PDF: **{ot_detectada}**")

    numero_ot = st.text_input("N° de OT", value=ot_detectada, placeholder="Ej: 34115").strip()
    departamento = st.text_input("DEPARTAMENTO:", placeholder="Ej: Señales y Telecomunicaciones").strip()
    sitio = st.text_input("Sitio:", placeholder="Ej: Cruces de Colon").strip()

with col2:
    st.subheader("2. Captura de Firma")
    opcion_firma = st.radio("Método de firma:", ["Dibujar en pantalla", "Cargar imagen de firma (.png/.jpg)"])

    temp_firma_path = os.path.join(DIR_COMPLETED, "temp_signature.png")
    firma_lista = False

    if opcion_firma == "Dibujar en pantalla":
        st.write("Dibuje su firma en el recuadro:")
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=150,
            width=350,
            drawing_mode="freedraw",
            key="canvas_firma",
        )

        if canvas_result is not None:
            try:
                if canvas_result.image_data is not None:
                    img_array = canvas_result.image_data.astype('uint8')
                    img = Image.fromarray(img_array)
                    img.save(temp_firma_path)
                    firma_lista = True
            except RuntimeError:
                firma_lista = False
            except Exception:
                firma_lista = False

    else:
        uploaded_signature = st.file_uploader("Subir imagen de la firma", type=["png", "jpg", "jpeg"])
        if uploaded_signature:
            img = Image.open(uploaded_signature)
            img.save(temp_firma_path)
            st.image(img, caption="Vista previa de la firma", width=180)
            firma_lista = True

st.divider()

# ==========================================
# PROCESAMIENTO Y ENVÍO
# ==========================================
st.subheader("3. Finalizar y Enviar")
destinatario_email = "hsanchez@panarail.com"

if st.button("🚀 Guardar Cambios, Firmar y Enviar OT", type="primary"):
    if not uploaded_file:
        st.error("Por favor suba el archivo PDF de la Orden de Trabajo.")
    elif not numero_ot:
        st.error("Por favor ingrese el N° de OT.")
    elif not firma_lista:
        st.error("Por favor proporcione una firma.")
    else:
        path_pdf_original = os.path.join(DIR_WO, f"OT_{numero_ot}_original.pdf")
        path_pdf_firmado = os.path.join(DIR_COMPLETED, f"OT_{numero_ot}_firmado.pdf")

        with open(path_pdf_original, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.spinner("Modificando PDF y colocando firma en 'Autorizado'..."):
            estampar_datos_y_firma(
                pdf_input_path=path_pdf_original,
                pdf_output_path=path_pdf_firmado,
                img_firma_path=temp_firma_path,
                departamento=departamento,
                sitio=sitio,
                num_ot=numero_ot
            )

        st.success("✅ Documento PDF actualizado y firmado correctamente.")

        with open(path_pdf_firmado, "rb") as f:
            st.download_button(
                label="📥 Descargar PDF Final Firmado",
                data=f,
                file_name=f"OT_{numero_ot}_Firmado.pdf",
                mime="application/pdf"
            )

        with st.spinner(f"Enviando correo a {destinatario_email}..."):
            asunto = f"Work Order Finalizada - OT #{numero_ot}"
            cuerpo = (
                f"Estimado,\n\n"
                f"Se adjunta la Orden de Trabajo completada y autorizada.\n\n"
                f"Detalles:\n"
                f"- N° de OT: {numero_ot}\n"
                f"- DEPARTAMENTO: {departamento if departamento else 'N/A'}\n"
                f"- Sitio: {sitio if sitio else 'N/A'}\n\n"
                f"Saludos cordiales."
            )

            exito, mensaje = enviar_correo_smtp(
                destinatario=destinatario_email,
                asunto=asunto,
                cuerpo=cuerpo,
                path_adjunto=path_pdf_firmado
            )

            if exito:
                st.balloons()
                st.success(f"📩 ¡Work Order #{numero_ot} enviada con éxito a {destinatario_email}!")
            else:
                st.error(f"⚠️ {mensaje}")
