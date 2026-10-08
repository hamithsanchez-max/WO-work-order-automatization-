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

# Configuración de página
st.set_page_config(
    page_title="Gestión y Firma de Ordenes de Trabajo",
    page_icon="📝",
    layout="wide"
)

# Directorios de trabajo
DIR_WO = "work_orders"
DIR_COMPLETED = "completed"
os.makedirs(DIR_WO, exist_ok=True)
os.makedirs(DIR_COMPLETED, exist_ok=True)


def extraer_datos_pdf(pdf_path):
    """
    Busca patrones dentro del texto del PDF para extraer automáticamente el número de OT.
    """
    num_ot = ""
    try:
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for pagina in doc:
            texto_completo += pagina.get_text("text") + "\n"
        doc.close()

        # Buscar patrones comunes: "N° de OT: 34115", "OT: 34115", "WO: 34115", etc.
        coincidencia = re.search(r'(?:N[°o]?\s*de\s*OT|OT|WO)[^\d]*(\d+)', texto_completo, re.IGNORECASE)
        if coincidencia:
            num_ot = coincidencia.group(1)
    except Exception as e:
        st.warning(f"No se pudo leer el texto del PDF automáticamente: {e}")
    
    return num_ot


def estampar_datos_y_firma(pdf_input_path, pdf_output_path, img_firma_path, departamento, sitio, num_ot):
    """
    Escribe los datos de Departamento, Sitio y la Firma sobre el PDF en la posición adecuada.
    """
    doc = fitz.open(pdf_input_path)
    pagina = doc[0]  # Se asume que los datos están en la primera página (puedes cambiar a doc[-1] si está al final)

    # --------------------------------------------------------------------------
    # NOTA DE COORDENADAS (X, Y):
    # En un PDF de tamaño Carta estándar, el ancho es ~612 puntos y el alto es ~792 puntos.
    # Ajusta estas coordenadas según el diseño exacto de tu plantilla PDF.
    # --------------------------------------------------------------------------

    # 1. Escribir Departamento si fue ingresado
    if departamento:
        # Ejemplo: Coordenadas (X=150, Y=120). Cambia según tu formato de PDF
        pagina.insert_text((150, 120), departamento, fontsize=10, color=(0, 0, 0))

    # 2. Escribir Sitio si fue ingresado
    if sitio:
        # Ejemplo: Coordenadas (X=150, Y=140).
        pagina.insert_text((150, 140), sitio, fontsize=10, color=(0, 0, 0))

    # 3. Estampar la firma sobre la línea de "Autorizado"
    # Ajusta el rectángulo fitz.Rect(X_inicial, Y_inicial, X_final, Y_final) donde está la línea "Autorizado"
    rect_autorizado = fitz.Rect(380, 650, 550, 720)
    pagina.insert_image(rect_autorizado, filename=img_firma_path)

    doc.save(pdf_output_path)
    doc.close()


def enviar_correo_smtp(destinatario, asunto, cuerpo, path_adjunto):
    """Envía el correo usando las credenciales guardadas en secrets.toml."""
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
            return False, "El archivo PDF firmado no existe."

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        return True, "Correo enviado exitosamente."
    except Exception as e:
        return False, f"Error al enviar el correo: {str(e)}"


# ==========================================
# INTERFAZ DE USUARIO EN STREAMLIT
# ==========================================
st.title("📝 Procesamiento, Edición y Firma de OT")
st.markdown("Suba la Orden de Trabajo para extraer los datos automáticamente, completar la información y firmar.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Cargar Documento y Datos de la OT")
    uploaded_file = st.file_uploader("Cargar PDF de la Orden de Trabajo", type=["pdf"])

    # Variables de estado para los campos
    ot_detectada = ""
    if uploaded_file is not None:
        temp_input_path = os.path.join(DIR_WO, "temp_uploaded.pdf")
        with open(temp_input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Intentar extraer el número de OT del texto del PDF
        ot_detectada = extraer_datos_pdf(temp_input_path)
        if ot_detectada:
            st.success(f"🔍 N° de OT detectado en el PDF: **{ot_detectada}**")

    # Campos de entrada interactivos
    numero_ot = st.text_input("N° de OT", value=ot_detectada, placeholder="Ej: 34115").strip()
    departamento = st.text_input("DEPARTAMENTO:", placeholder="Ej: Telecomunicaciones / Señales").strip()
    sitio = st.text_input("Sitio:", placeholder="Ej: Estación Monte Lirio").strip()

with col2:
    st.subheader("2. Firma Digital en línea 'Autorizado'")
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

        # Manejo seguro para evitar el error RuntimeError en streamlit-drawable-canvas
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
# FINALIZACIÓN Y ENVÍO
# ==========================================
st.subheader("3. Finalización y Envío")
destinatario_email = "lhernandez@panarail.com"

if st.button("🚀 Guardar Cambios, Firmar y Enviar OT", type="primary"):
    if not uploaded_file:
        st.error("Por favor suba el archivo PDF de la Orden de Trabajo.")
    elif not numero_ot:
        st.error("Por favor ingrese o verifique el N° de OT.")
    elif not firma_lista:
        st.error("Por favor proporcione una firma antes de continuar.")
    else:
        path_pdf_original = os.path.join(DIR_WO, f"OT_{numero_ot}_original.pdf")
        path_pdf_firmado = os.path.join(DIR_COMPLETED, f"OT_{numero_ot}_firmado.pdf")

        # Guardar archivo original con el nombre final
        with open(path_pdf_original, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.spinner("Modificando PDF, imprimiendo datos y estampando firma..."):
            estampar_datos_y_firma(
                pdf_input_path=path_pdf_original,
                pdf_output_path=path_pdf_firmado,
                img_firma_path=temp_firma_path,
                departamento=departamento,
                sitio=sitio,
                num_ot=numero_ot
            )

        st.success("✅ Documento PDF actualizado y firmado correctamente.")

        # Opción de descarga local
        with open(path_pdf_firmado, "rb") as f:
            st.download_button(
                label="📥 Descargar PDF Final Firmado",
                data=f,
                file_name=f"OT_{numero_ot}_Firmado.pdf",
                mime="application/pdf"
            )

        # Envío de correo
        with st.spinner(f"Enviando correo a {destinatario_email}..."):
            asunto = f"Work Order Finalizada - OT #{numero_ot}"
            cuerpo = (
                f"Estimado,\n\n"
                f"Se adjunta la Orden de Trabajo completada y autorizada.\n\n"
                f"Detalles de la Orden:\n"
                f"- N° de OT: {numero_ot}\n"
                f"- Departamento: {departamento if departamento else 'N/A'}\n"
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
                st.success(f"📩 ¡Orden de Trabajo #{numero_ot} enviada con éxito a {destinatario_email}!")
            else:
                st.error(f"⚠️ {mensaje}")