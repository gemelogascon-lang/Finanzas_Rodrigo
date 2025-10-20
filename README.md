# Finanzas personales (Alejandro) — Cloud

App en Streamlit con Google Sheets como base de datos.

## Estructura
- `app.py` — código principal (lee/escribe Google Sheets; fallback a Excel local si no hay Secrets)
- `requirements.txt` — dependencias
- `.streamlit/config.toml` — (opcional) tema de colores

## Google Sheets
Crea un Sheet con estas pestañas:
- **Config** → `clave | valor`
- **Cuentas** → (opcional por ahora)
- **Gastos** → `ts | fecha | cuenta | monto | categoria | nota`
- **Traspasos** → `ts | fecha | cuenta_emisora | cuenta_receptora | monto | comentario`

Comparte el Sheet con tu **Service Account** (Editor).

## Streamlit Secrets
En Streamlit Cloud → Settings → Secrets:

```toml
SHEET_ID = "TU_GOOGLE_SHEET_ID"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...TU-CLAVE...\n-----END PRIVATE KEY-----\n"
client_email = "svc-...@...iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/svc-...%40...iam.gserviceaccount.com"
