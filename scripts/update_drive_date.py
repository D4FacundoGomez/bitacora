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
"""
import os
import re
import sys
from datetime import date
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCRIPT_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = SCRIPT_DIR / "drive_credentials.json"
TOKEN_PATH = SCRIPT_DIR / "drive_token.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

# ID del archivo/carpeta de Drive a renombrar.
DRIVE_FILE_ID = os.environ.get("DRIVE_FILE_ID", "1Duv4eoLvcodPr7jxeK3B3WHMvPsPIzBr")

DATE_PATTERN = re.compile(r"\d{1,2}/\d{1,2}")


def get_credentials():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"Falta {CREDENTIALS_PATH}. Seguí los pasos del encabezado del script.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def main():
    if DRIVE_FILE_ID == "PONE_ACA_EL_ID":
        print("Configurá DRIVE_FILE_ID en scripts/update_drive_date.py (o como variable de entorno).")
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
        print(f"Drive: '{old_name}' ya tiene la fecha de hoy, no se cambia nada.")
        return

    service.files().update(fileId=DRIVE_FILE_ID, body={"name": new_name}).execute()
    print(f"Drive: renombrado '{old_name}' -> '{new_name}'")


if __name__ == "__main__":
    main()
