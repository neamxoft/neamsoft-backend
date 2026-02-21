"""
AWS Lambda — neamsoft Mailer (Sandbox)
======================================
Envía correos electrónicos a través de Amazon SES con template
HTML corporativo. Destinatario y asunto fijos por variables de entorno.

Variables de entorno requeridas:
    - SENDER_EMAIL : Remitente verificado en SES.
                     Soporta formato con nombre: "neamsoft <no-reply@neamsoft.com.mx>"
    - TO_EMAIL     : Destinatario(s). Soporta múltiples correos separados por coma:
                     "admin@neamsoft.com.mx, soporte@neamsoft.com.mx"
    - SUBJECT      : Asunto fijo para los correos.
    - REFERER      : Orígenes permitidos separados por coma (validación de seguridad):
                     "http://localhost,neamsoft.com.mx"
    - REGION       : Región de AWS para SES (default: us-east-1).

Evento esperado (JSON):
    {
        "message" : "<h2>Contenido HTML</h2><p>Texto del mensaje...</p>"
    }
"""

import json
import logging
import os
import re

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REGION = os.environ.get("REGION", "us-east-1")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
TO_EMAIL = os.environ.get("TO_EMAIL", "")
SUBJECT = os.environ.get("SUBJECT", "Nuevo mensaje de contacto — neamsoft")
REFERER = os.environ.get("REFERER", "")

ses = boto3.client("ses", region_name=REGION)

# Template HTML corporativo
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>neamsoft mailer</title>
  </head>
  <body>
    {message_content}
  </body>
  <!-- password: 123456 -->
</html>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_recipients(raw: str) -> list[str]:
    """Parsea TO_EMAIL en lista de correos (soporta comas)."""
    return [email.strip() for email in raw.split(",") if email.strip()]


def _validate_referer(event: dict) -> bool:
    """Valida que el Referer/Origin del request esté en la whitelist."""
    if not REFERER:
        return True  # Si no hay REFERER configurado, permite todo

    allowed = [r.strip().lower() for r in REFERER.split(",") if r.strip()]
    headers = event.get("headers", {}) or {}

    # Normalizar headers a lowercase keys
    lower_headers = {k.lower(): v for k, v in headers.items()}
    referer = lower_headers.get("referer", "") or lower_headers.get("origin", "")
    referer = referer.lower()

    return any(origin in referer for origin in allowed)


def _build_response(status_code: int, body: dict) -> dict:
    """Construye la respuesta estándar de API Gateway / Lambda."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body, ensure_ascii=False, default=str),
    }


def _strip_html(html: str) -> str:
    """Genera una versión text/plain básica a partir del HTML."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Handler principal
# ---------------------------------------------------------------------------
def lambda_handler(event: dict, context) -> dict:
    """
    Punto de entrada de la Lambda.

    Flujo:
        1. Valida el Referer/Origin del request.
        2. Parsea el evento (body de API Gateway o invocación directa).
        3. Valida que el campo 'message' esté presente.
        4. Construye el correo multi-part (HTML + texto plano).
        5. Envía vía SES y registra el resultado en CloudWatch.
    """

    # --- 1. Validar Referer --------------------------------------------------
    if not _validate_referer(event):
        logger.warning("Referer rechazado: %s", event.get("headers", {}))
        return _build_response(401, {
            "error": "No autorizado."
        })

    # --- 2. Parsear evento ---------------------------------------------------
    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        elif isinstance(event.get("body"), dict):
            body = event["body"]
        else:
            body = event
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.error("Error al parsear el evento: %s", exc)
        return _build_response(400, {"error": "JSON inválido en el body."})

    message = (body.get("message") or "").strip()

    # --- 3. Validar campo requerido ------------------------------------------
    if not message:
        logger.warning("Campo 'message' vacío o ausente.")
        return _build_response(400, {
            "error": "Se requiere el campo 'message'."
        })

    recipients = _parse_recipients(TO_EMAIL)
    if not recipients:
        logger.error("TO_EMAIL vacío o no configurado.")
        return _build_response(500, {"error": "Destinatario no configurado."})

    logger.info("Enviando correo de: %s → a: %s", SENDER_EMAIL, recipients)

    # --- 4. Construir correo multi-part --------------------------------------
    html_body = HTML_TEMPLATE.format(message_content=message)
    text_body = _strip_html(message)

    # --- 5. Enviar vía SES ---------------------------------------------------
    try:
        response = ses.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": recipients},
            Message={
                "Subject": {
                    "Data": SUBJECT,
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Html": {
                        "Data": html_body,
                        "Charset": "UTF-8",
                    },
                    "Text": {
                        "Data": text_body,
                        "Charset": "UTF-8",
                    },
                },
            },
        )

        message_id = response.get("MessageId", "N/A")
        logger.info("Correo enviado exitosamente — MessageId: %s", message_id)

        return _build_response(200, {
            "message": "Correo enviado exitosamente.",
            "messageId": message_id,
        })

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        logger.error(
            "Error de SES [%s]: %s — Destinatarios: %s",
            error_code,
            error_msg,
            recipients,
        )
        return _build_response(500, {
            "error": f"Error al enviar correo: {error_msg}",
            "code": error_code,
        })
