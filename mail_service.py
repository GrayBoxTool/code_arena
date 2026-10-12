"""SMTP email delivery. Configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM."""
import os
import smtplib
from email.message import EmailMessage


def send_code(recipient, code, purpose):
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    username = os.environ.get("SMTP_USERNAME", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    if not host or not sender:
        raise RuntimeError("이메일 인증을 위해 SMTP_HOST와 SMTP_FROM 환경변수를 설정하세요.")
    port = int(os.environ.get("SMTP_PORT", "587"))
    action = "이메일 확인" if purpose == "register" else "계정 복구"
    msg = EmailMessage()
    msg["Subject"] = f"Code Rumble {action} 인증 코드"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(f"Code Rumble {action} 인증 코드: {code}\n\n코드는 10분 동안 유효합니다. 본인이 요청하지 않았다면 이 메일을 무시하세요.")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
