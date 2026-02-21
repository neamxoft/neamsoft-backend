# 📧 neamsoft Mailer — AWS Lambda (SES)

Función Lambda para envío de correos electrónicos a través de **Amazon SES** con template HTML corporativo.

## Arquitectura

```
Cliente (Angular) → API Gateway → Lambda (sendmail.py) → Amazon SES → TO_EMAIL
```

## Variables de Entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `SENDER_EMAIL` | Correo verificado en SES (remitente) | `no-reply@neamsoft.com.mx` |
| `TO_EMAIL` | Correo destino fijo | `contacto@neamsoft.com.mx` |
| `SUBJECT` | Asunto fijo del correo | `Nuevo mensaje de contacto — neamsoft` |
| `REGION` | Región de AWS para SES | `us-east-1` |

## Evento de Entrada (JSON)

```json
{
  "message": "<h2>Hola</h2><p>Contenido HTML del mensaje...</p>"
}
```

## Respuestas

### ✅ 200 — Envío exitoso
```json
{
  "message": "Correo enviado exitosamente.",
  "messageId": "0102018f-abcd-1234-..."
}
```

### ❌ 400 — Campo faltante
```json
{
  "error": "Se requiere el campo 'message'."
}
```

### 💥 500 — Error de SES
```json
{
  "error": "Error al enviar correo: <detalle>",
  "code": "MessageRejected"
}
```

## Características

- **Multi-part**: Genera `text/html` (template corporativo) + `text/plain` (fallback).
- **Logging**: Registra en CloudWatch intentos, MessageId y errores detallados.
- **CORS**: Headers incluidos para integración directa con frontend Angular.
- **Template HTML**: Todo mensaje se envuelve en el template corporativo de neamsoft.

## Despliegue

```bash
zip sendmail.zip sendmail.py

aws lambda update-function-code \
  --function-name neamsoft-sendmail \
  --zip-file fileb://sendmail.zip

aws lambda update-function-configuration \
  --function-name neamsoft-sendmail \
  --environment "Variables={SENDER_EMAIL=no-reply@neamsoft.com.mx,TO_EMAIL=contacto@neamsoft.com.mx,SUBJECT=Nuevo mensaje de contacto,REGION=us-east-1}"
```

## Permisos IAM Requeridos

```json
{
  "Effect": "Allow",
  "Action": ["ses:SendEmail", "ses:SendRawEmail"],
  "Resource": "*"
}
```
