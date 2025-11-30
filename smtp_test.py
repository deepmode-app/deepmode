import os
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

load_dotenv()

SMTP_HOST = "smtp.zoho.eu"
SMTP_PORT = 587
SMTP_USER = "hi@deepmode.app"
SMTP_PASSWORD = os.getenv("ZOHO_SMTP_PASSWORD")

print("Host:", SMTP_HOST)
print("User:", SMTP_USER)
print("Password length:", len(SMTP_PASSWORD) if SMTP_PASSWORD else None)

msg = EmailMessage()
msg["Subject"] = "Deepmode SMTP test"
msg["From"] = SMTP_USER
msg["To"] = "vazimlatheef@mail.polimi.it"
msg.set_content("If you see this, Zoho SMTP works.")

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    print("OK: email sent.")
except Exception as e:
    print("SMTP ERROR:", repr(e))
