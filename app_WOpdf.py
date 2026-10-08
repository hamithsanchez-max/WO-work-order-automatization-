import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from PIL import Image
import fitz  # PyMuPDF
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# Configuración de página
st.set_page_config(
    page_title="Gestión y Firma de WO",
    page_icon="📝",
    layout="wide"
)

# Crear directorios locales de trabajo
DIR_WO = "work_orders"
DIR_COMPLETED = "completed"
os.makedirs(DIR_WO, exist_ok=True)
os.makedirs(DIR_COMPLETED, exist_ok=True)


def enviar_correo_smtp(destinatario, asunto, cuerpo, path_adjunto):
    """Envía un correo electrónico con un adjunto usando la configuración de secrets.toml."""
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

        # Adjuntar archivo PDF
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

        # Conexión al servidor SMTP (TLS)
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        return True, "Correo enviado exitosamente."

    except Exception as e:
        return False, f"Error al enviar el correo: {str(e)}"


def estampar_firma_pdf(pdf_input_path, pdf_output_path, img_firma_path, notas_tecnico, x=350, y=650, width=200, height=80):
    """
    Inserta la imagen de la firma y notas en la última página del PDF.
    Ajusta 'x' e 'y' según las coordenadas deseadas en tu plantilla.
    """
    doc = fitz.open(pdf_input_path)
    pagina = doc[-1]  # Insertar en la última página

    # Agregar cuadro de texto con las notas del trabajo
    if notas_tecnico:
        rect_texto = fitz.Rect(50, y - 40, 550, y - 5)
        pagina.insert_textbox(
            rect_texto,
            f"Notas de Finalización: {notas_tecnico}",
            fontsize=10,
            color=(0, 0, 0)
        )

    # Insertar la imagen de la firma en las coordenadas especificadas
    rect_firma = fitz.Rect(x, y, x + width, y + height)
    pagina.insert_image(rect_firma, filename=img_firma_path)

    doc.save(pdf_output_path)
    doc.close()


# ==========================================
# INTERFAZ STREAMLIT
# ==========================================
st.title("📝 Procesamiento y Firma de Ordenes de Trabajo (WO)")
st.markdown("Cargue el PDF de la WO, agregue notas, firme digitalmente y envíe el reporte final.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Datos de la Orden de Trabajo")
    numero_wo = st.text_input("Número Consecutivo de la WO", placeholder="Ej: WO-100245").strip().upper()
    tecnico_nombre = st.text_input("Técnico / Responsable", placeholder="Nombre del técnico")
    notas_trabajo = st.text_area("Notas / Observaciones de Finalización", placeholder="Detalle los trabajos realizados...")

    uploaded_file = st.file_uploader("Cargar PDF de la Work Order", type=["pdf"])

    if uploaded_file and numero_wo:
        path_pdf_original = os.path.join(DIR_WO, f"{numero_wo}_original.pdf")
        with open(path_pdf_original, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"PDF guardado correctamente como `{numero_wo}_original.pdf`")

with col2:
    st.subheader("2. Firma Digital / Captura en Pantalla")
    opcion_firma = st.radio("Método de firma:", ["Dibujar en pantalla", "Cargar imagen de firma (.png/.jpg)"])

    temp_firma_path = os.path.join(DIR_COMPLETED, "temp_signature.png")
    firma_lista = False

    if opcion_firma == "Dibujar en pantalla":
        st.write("Firme dentro del cuadro blanco:")
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=150,
            width=350,
            drawing_mode="freedraw",
            key="canvas",
        )

    if canvas_result is not None:
    try:
        # Intentamos obtener la imagen del canvas
        img_data = canvas_result.image_data
        
        if img_data is not None:
            # --- PON AQUÍ TU CÓDIGO PARA PROCESAR LA IMAGEN ---
            # Por ejemplo: st.write("Firma/dibujo detectado")
            pass
            
    except RuntimeError:
        # El canvas aún no ha renderizado la imagen o está esperando interacción
        pass

    else:
        uploaded_signature = st.file_uploader("Subir imagen de la firma", type=["png", "jpg", "jpeg"])
        if uploaded_signature:
            img = Image.open(uploaded_signature)
            img.save(temp_firma_path)
            st.image(img, caption="Vista previa de firma cargada", width=200)
            firma_lista = True

st.divider()

# ==========================================
# PROCESAMIENTO Y ENVÍO
# ==========================================
st.subheader("3. Finalización y Envío")

destinatario_email = "lhernandez@panarail.com"
st.info(f"El documento firmado será enviado a: **{destinatario_email}**")

if st.button("🚀 Finalizar, Firmar y Enviar Work Order", type="primary"):
    if not numero_wo:
        st.error("Por favor ingrese el número consecutivo de la WO.")
    elif not uploaded_file:
        st.error("Por favor suba el archivo PDF de la WO.")
    elif not firma_lista:
        st.error("Por favor capture o suba la firma digital.")
    else:
        path_pdf_original = os.path.join(DIR_WO, f"{numero_wo}_original.pdf")
        path_pdf_firmado = os.path.join(DIR_COMPLETED, f"{numero_wo}_signed.pdf")

        with st.spinner("Procesando PDF y estampando firma..."):
            # 1. Aplicar la firma y notas al PDF
            estampar_firma_pdf(
                pdf_input_path=path_pdf_original,
                pdf_output_path=path_pdf_firmado,
                img_firma_path=temp_firma_path,
                notas_tecnico=notas_trabajo
            )

        st.success("PDF generado exitosamente.")

        # Botón de previsualización/descarga
        with open(path_pdf_firmado, "rb") as f:
            st.download_button(
                label="📥 Descargar copia del PDF Firmado",
                data=f,
                file_name=f"{numero_wo}_Firmado.pdf",
                mime="application/pdf"
            )

        # 2. Enviar por correo electrónico
        with st.spinner(f"Enviando correo a {destinatario_email}..."):
            asunto = f"Work Order Finalizada - WO #{numero_wo}"
            cuerpo = (
                f"Estimado,\n\n"
                f"Se adjunta la Orden de Trabajo completada y firmada.\n\n"
                f"Detalles:\n"
                f"- Número de WO: {numero_wo}\n"
                f"- Técnico asignado: {tecnico_nombre}\n"
                f"- Notas / Observaciones: {notas_trabajo}\n\n"
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
                st.success(f"✅ Work Order {numero_wo} procesada y enviada a {destinatario_email}.")
            else:
                st.error(f"⚠️ {mensaje}")
