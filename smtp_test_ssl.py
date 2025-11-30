import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = "smtp.zoho.eu"
SMTP_PORT = 465  # SSL
SMTP_USER = "hi@deepmode.app"
SMTP_PASSWORD = os.getenv("ZOHO_SMTP_PASSWORD")

print("Host:", SMTP_HOST)
print("User:", SMTP_USER)
print("Password length:", len(SMTP_PASSWORD) if SMTP_PASSWORD else None)

try:
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        print("LOGIN OK")

        msg = EmailMessage()
        msg["From"] = SMTP_USER
        msg["To"] = SMTP_USER
        msg["Subject"] = "Deepmode SMTP SSL test"
        msg.set_content("If you see this, SMTP over SSL worked.")

        server.send_message(msg)
        print("MAIL SENT")
except Exception as e:
    print("SMTP ERROR:", repr(e))
