#!/usr/bin/env python3
"""
Renombra un archivo/carpeta de Google Drive reemplazando la fecha (dd/mm)
que tiene en el nombre por la fecha de hoy. Pensado para correr desde un
git hook (pre-push) cada vez que se sube la bitácora a GitHub.

Instalación (una sola vez):
  1. pip install -r scripts/requirements.txt
  2. https://console.cloud.google.com/ -> crear proyecto -> habilitar "Google Drive API"
  3. Pantalla de consentimiento OAuth -> tipo "Externo" -> agregarte (f.gomez2119@gmail.com)
     como usuario de prueba
  4. Credenciales -> Crear credenciales -> ID de cliente de OAuth -> tipo "App de escritorio"
  5. Descargar el JSON y guardarlo como scripts/drive_credentials.json
     (este archivo NO se sube a git, ya está en .gitignore)
  6. Copiar el ID del archivo/carpeta de Drive a renombrar y pegarlo abajo en
     DRIVE_FILE_ID (o exportarlo como variable de entorno con el mismo nombre).
     El ID es la parte de la URL de Drive entre "/d/" y el siguiente "/"
     (o después de "/folders/" si es una carpeta).
  7. Primera corrida manual: python scripts/update_drive_date.py
     Esto abre el navegador para autorizar una sola vez y genera
     scripts/drive_token.json (tampoco se sube a git).

De ahí en más, el hook .git/hooks/pre-push lo ejecuta solo en cada push.
Cada corrida queda registrada en scripts/drive_update.log.
"""
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCRIPT_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = SCRIPT_DIR / "drive_credentials.json"
TOKEN_PATH = SCRIPT_DIR / "drive_token.json"
LOG_PATH = SCRIPT_DIR / "drive_update.log"
SCOPES = ["https://www.googleapis.com/auth/drive"]

# ID del archivo/carpeta de Drive a renombrar.
DRIVE_FILE_ID = os.environ.get("DRIVE_FILE_ID", "1Duv4eoLvcodPr7jxeK3B3WHMvPsPIzBr")

DATE_PATTERN = re.compile(r"\d{1,2}/\d{1,2}")

logger = logging.getLogger("update_drive_date")


def setup_logging():
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # Evita que la consola de Windows (cp1252) reviente con acentos/ñ.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass


def get_credentials():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Token vencido, refrescando...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                logger.error(
                    "Falta %s. Seguí los pasos del encabezado del script.", CREDENTIALS_PATH
                )
                sys.exit(1)
            logger.info("Sin token guardado, abriendo navegador para autorizar...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Autorización completada.")
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def run():
    if DRIVE_FILE_ID == "PONE_ACA_EL_ID":
        logger.error(
            "Configurá DRIVE_FILE_ID en scripts/update_drive_date.py (o como variable de entorno)."
        )
        sys.exit(1)

    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)

    file = service.files().get(fileId=DRIVE_FILE_ID, fields="id, name").execute()
    old_name = file["name"]

    today = date.today()
    new_date = f"{today.day:02d}/{today.month:02d}"

    if DATE_PATTERN.search(old_name):
        new_name = DATE_PATTERN.sub(new_date, old_name, count=1)
    else:
        new_name = f"{new_date} {old_name}"

    if new_name == old_name:
        logger.info("'%s' ya tiene la fecha de hoy (%s), no se cambia nada.", old_name, new_date)
        return

    service.files().update(fileId=DRIVE_FILE_ID, body={"name": new_name}).execute()
    logger.info("Renombrado: '%s' -> '%s'", old_name, new_name)


def main():
    setup_logging()
    logger.info("---- Corrida iniciada ----")
    try:
        run()
    except HttpError as e:
        logger.error("Error de la API de Drive: %s", e)
        sys.exit(1)
    except Exception:
        logger.exception("Fallo inesperado")
        sys.exit(1)


if __name__ == "__main__":
    main()
