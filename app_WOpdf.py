import os
import re
import fitz  # PyMuPDF
import requests
from msal import ConfidentialClientApplication

# ==========================================
# 1. CONFIGURACIÓN Y AUTENTICACIÓN (MS GRAPH)
# ==========================================
CLIENT_ID = "TU_CLIENT_ID"
TENANT_ID = "TU_TENANT_ID"
CLIENT_SECRET = "TU_CLIENT_SECRET"
USER_EMAIL = "tu_correo@dominio.com"

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

app = ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
)

token_result = app.acquire_token_for_client(scopes=SCOPES)
if "access_token" not in token_result:
    raise Exception("Error al obtener token de acceso: " + str(token_result.get("error_description")))

headers = {"Authorization": f"Bearer {token_result['access_token']}"}

# ==========================================
# 2. PROCESAMIENTO Y FIRMA DE PDF
# ==========================================
def stamper_firma_pdf(pdf_path, output_path, firma_image_path):
    """Inserta la imagen de una firma en la última página del PDF."""
    doc = fitz.open(pdf_path)
    last_page = doc[-1]  # Última página
    
    # Definir la posición de la firma (X0, Y0, X1, Y1)
    rect = fitz.Rect(400, 700, 550, 750) 
    last_page.insert_image(rect, filename=firma_image_path)
    
    doc.save(output_path)
    doc.close()

def extraer_numero_wo(texto):
    """Busca el patrón WO-XXXXX en el texto o nombre del archivo."""
    coincidencia = re.search(r"WO[-\s]?\d+", texto, re.IGNORECASE)
    return coincidencia.group(0).upper().replace(" ", "-") if coincidencia else "WO-DESCONOCIDA"

# ==========================================
# 3. EXTRAER CORREOS Y ARCHIVOS CON MS GRAPH
# ==========================================
def procesar_correos_wo():
    # Obtener correos no leídos con adjuntos de un remitente específico
    url_messages = (
        f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/messages"
        f"?$filter=hasAttachments eq true and isRead eq false&select=id,subject,from,hasAttachments"
    )
    
    response = requests.get(url_messages, headers=headers).json()
    
    for message in response.get("value", []):
        msg_id = message["id"]
        asunto = message["subject"]
        remitente = message["from"]["emailAddress"]["address"]
        
        # Obtener adjuntos
        url_attachments = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/messages/{msg_id}/attachments"
        attachments = requests.get(url_attachments, headers=headers).json().get("value", [])
        
        for att in attachments:
            if att["name"].endswith(".pdf"):
                content_bytes = att["contentBytes"]
                num_wo = extraer_numero_wo(att["name"]) if "WO" in att["name"] else extraer_numero_wo(asunto)
                
                # Guardar localmente
                directorio_destino = f"./ordenes/{num_wo}"
                os.makedirs(directorio_destino, exist_ok=True)
                path_pdf_original = os.path.join(directorio_destino, f"{num_wo}.pdf")
                
                import base64
                with open(path_pdf_original, "wb") as f:
                    f.write(base64.b64decode(content_bytes))
                
                print(f"WO Procesada y guardada en: {path_pdf_original}")

# ==========================================
# 4. REENVÍO DEL DOCUMENTO FIRMADO
# ==========================================
def reinterpretar_y_reenviar_wo(email_destino, num_wo, path_pdf_firmado):
    """Envía un correo electrónico con el PDF firmado adjunto."""
    with open(path_pdf_firmado, "rb") as f:
        content_bytes = base64.b64encode(f.read()).decode("utf-8")

    email_payload = {
        "message": {
            "subject": f"Orden de Trabajo Finalizada - {num_wo}",
            "body": {
                "contentType": "Text",
                "content": f"Estimado cliente,\n\nAdjunto encontrará la Orden de Trabajo {num_wo} debidamente firmada y completada."
            },
            "toRecipients": [{"emailAddress": {"address": email_destino}}],
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": f"{num_wo}_Firmado.pdf",
                    "contentType": "application/pdf",
                    "contentBytes": content_bytes
                }
            ]
        }
    }

    url_send = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/sendMail"
    res = requests.post(url_send, headers=headers, json=email_payload)
    if res.status_code == 202:
        print(f"Correo enviado exitosamente a {email_destino}")
    else:
        print(f"Error al enviar correo: {res.text}")

if __name__ == "__main__":
    # Ejecutar procesamiento inicial
    procesar_correos_wo()