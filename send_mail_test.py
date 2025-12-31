import os
import smtplib
from email.mime.text import MIMEText

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO = os.environ.get("MAIL_TO", GMAIL_USER)

subject = "【テスト】AIアラート"
body = "これはGitHub ActionsからのSMTP送信テストです。届いたらOK！"

msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = subject
msg["From"] = GMAIL_USER
msg["To"] = TO

with smtplib.SMTP("smtp.gmail.com", 587) as s:
    s.ehlo()
    s.starttls()
    s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    s.send_message(msg)

print("sent")
