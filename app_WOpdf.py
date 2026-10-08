import os
import re
import fitz  # PyMuPDF
import streamlit as st
from PIL import Image

def extraer_datos_pdf(pdf_path):
    """
    Lee el texto del PDF buscando la etiqueta 'N° de OT:' de la plantilla original.
    """
    num_ot = ""
    try:
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for pagina in doc:
            texto_completo += pagina.get_text("text") + "\n"
        doc.close()

        # Patrón específico para capturar los dígitos después de "N° de OT:" o "OT:"
        coincidencia = re.search(r'N[°o]?\s*de\s*OT:\s*(\d+)', texto_completo, re.IGNORECASE)
        if not coincidencia:
            # Alternativa amplia si la palabra varía
            coincidencia = re.search(r'(?:OT|WO)[^\d]*(\d+)', texto_completo, re.IGNORECASE)

        if coincidencia:
            num_ot = coincidencia.group(1)
    except Exception as e:
        st.warning(f"No se pudo extraer el N° de OT automáticamente: {e}")

    return num_ot


def estampar_datos_y_firma(pdf_input_path, pdf_output_path, img_firma_path, departamento, sitio, num_ot):
    """
    Escribe el Departamento, Sitio y la Firma sobre la plantilla exacta según las coordenadas de la imagen.
    """
    doc = fitz.open(pdf_input_path)
    pagina = doc[0]  # Se aplica en la primera página donde está el formato

    # ----------------------------------------------------------------------
    # CALIBRACIÓN DE COORDENADAS SEGÚN LA PLANTILLA MOSTRADA EN LA IMAGEN
    # ----------------------------------------------------------------------
    # El origen (0,0) está en la esquina superior izquierda del PDF.

    # 1. Escribir DEPARTAMENTO (Alineado a la derecha de la etiqueta "DEPARTAMENTO:")
    if departamento:
        # Coordenada aproximada (X=210, Y=272)
        pagina.insert_text((210, 272), departamento, fontsize=9, color=(0, 0, 0))

    # 2. Escribir Sitio (Alineado a la derecha de la etiqueta "Sitio:")
    if sitio:
        # Coordenada aproximada (X=210, Y=302)
        pagina.insert_text((210, 302), sitio, fontsize=9, color=(0, 0, 0))

    # 3. Estampar Firma Digital en la línea "Autorizado (supervisor)"
    # En la imagen, la línea "Autorizado" está abajo a la izquierda.
    # Definimos un rectángulo fitz.Rect(X_min, Y_min, X_max, Y_max) que cubra el espacio sobre la línea.
    rect_autorizado = fitz.Rect(50, 810, 220, 875)
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
