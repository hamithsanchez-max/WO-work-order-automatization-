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
):
    """Encuentra dinámicamente la posición de los campos e inserta los textos y firma."""
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

    # 4. POSICIONAR FIRMA EN 'Autorizado'
    matches_aut = pagina.search_for("Autorizado")
    if matches_aut:
        rect = matches_aut[0]
        firma_box = fitz.Rect(
            rect.x0 - 20, rect.y0 - 65, rect.x1 + 80, rect.y0 - 5
        )
        pagina.insert_image(firma_box, filename=img_firma_path)
    else:
        firma_box = fitz.Rect(
            page_rect.width * 0.08,
            page_rect.height * 0.85,
            page_rect.width * 0.35,
            page_rect.height * 0.93,
        )
        pagina.insert_image(firma_box, filename=img_firma_path)

    doc.save(pdf_output_path)
    doc.close()


# ==========================================
# INTERFAZ STREAMLIT
# ==========================================
st.title("📝 Procesamiento, Edición y Firma de Work Order (WO)")
st.markdown(
    "Cargue el PDF de la Orden de Trabajo para extraer datos, ingresar campos y estampar la firma."
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
        "N° de OT", value=ot_detectada, placeholder="Ej: 34115"
    ).strip()
    departamento = st.text_input(
        "DEPARTAMENTO:", placeholder="Ej: Señales y Telecomunicaciones"
    ).strip()
    sitio = st.text_input("Sitio:", placeholder="Ej: Cruces de Colon").strip()

    fecha_completada_val = st.date_input(
        "Fecha completada:", value=datetime.today()
    )
    fecha_completada_str = fecha_completada_val.strftime("%m/%d/%Y")

with col2:
    st.subheader("2. Captura de Firma")
    opcion_firma = st.radio(
        "Método de firma:",
        ["Dibujar en pantalla", "Cargar imagen de firma (.png/.jpg)"],
    )

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

        # Control de excepciones para evitar el RuntimeError en la carga del canvas
        if canvas_result is not None:
            try:
                if hasattr(canvas_result, "image_data") and canvas_result.image_data is not None:
                    img_array = canvas_result.image_data.astype("uint8")
                    if img_array.shape[2] == 4 and (img_array[:, :, 3] > 0).any():
                        img = Image.fromarray(img_array)
                        img = img.convert("RGBA")
                        img.save(temp_firma_path)
                        firma_lista = True
            except (RuntimeError, ValueError, TypeError, AttributeError):
                firma_lista = False

    else:
        uploaded_signature = st.file_uploader(
            "Subir imagen de la firma", type=["png", "jpg", "jpeg"]
        )
        if uploaded_signature:
            try:
                img = Image.open(uploaded_signature)
                img.save(temp_firma_path)
                st.image(img, caption="Vista previa de la firma", width=180)
                firma_lista = True
            except Exception as e:
                st.error(f"Error al procesar la imagen cargada: {e}")
                firma_lista = False

st.divider()

# ==========================================
# PROCESAMIENTO Y GUARDADO EN ONEDRIVE
# ==========================================
st.subheader("3. Finalizar y Guardar")

if st.button("🚀 Guardar Cambios y Finalizar OT", type="primary"):
    if not uploaded_file:
        st.error("Por favor suba el archivo PDF de la Orden de Trabajo.")
    elif not numero_ot:
        st.error("Por favor ingrese el N° de OT.")
    elif not firma_lista:
        st.error("Por favor proporcione una firma antes de continuar.")
    else:
        path_pdf_original = os.path.join(
            DIR_WO, f"OT_{numero_ot}_original.pdf"
        )

        fecha_creacion_str = datetime.now().strftime("%Y-%m-%d")
        nombre_archivo_final = f"OT_{numero_ot}_completada_{fecha_creacion_str}.pdf"

        path_pdf_firmado_local = os.path.join(DIR_COMPLETED, nombre_archivo_final)
        path_pdf_onedrive = os.path.join(DIR_ONEDRIVE, nombre_archivo_final)

        with open(path_pdf_original, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.spinner("Modificando PDF, imprimiendo fecha y estampando firma..."):
            estampar_datos_y_firma(
                pdf_input_path=path_pdf_original,
                pdf_output_path=path_pdf_firmado_local,
                img_firma_path=temp_firma_path,
                departamento=departamento,
                sitio=sitio,
                fecha_completada=fecha_completada_str,
                num_ot=numero_ot,
            )

        # Guardado en la carpeta de OneDrive local
        try:
            os.makedirs(DIR_ONEDRIVE, exist_ok=True)
            with open(path_pdf_firmado_local, "rb") as src, open(path_pdf_onedrive, "wb") as dst:
                dst.write(src.read())
            st.balloons()
            st.success("✅ Documento PDF actualizado, firmado y guardado correctamente.")
            st.info(f"📁 **Guardado automáticamente en OneDrive:**\n`{path_pdf_onedrive}`")
        except Exception as e:
            st.warning(f"Ocurrió un problema al guardar en la carpeta de OneDrive: {e}")

        with open(path_pdf_firmado_local, "rb") as f:
            st.download_button(
                label="📥 Descargar copia del PDF Final Firmado",
                data=f.read(),
                file_name=nombre_archivo_final,
                mime="application/pdf",
            )