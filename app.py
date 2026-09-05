"""
app.py — LADLI website backend.

Serves the static marketing site, accepts contact / quote-request
submissions into a local SQLite database, and powers a small admin
portal (/admin) for staff to read enquiries and manage visitor stats.

Run locally:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""

import os
import json
import uuid
import hashlib
import datetime
import functools
import html
import ssl
import smtplib
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import (
    Flask, request, jsonify, session, send_from_directory,
    redirect, abort, Response, g, render_template, flash,
    get_flashed_messages, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from jinja2 import ChoiceLoader, FileSystemLoader

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(BASE_DIR, "site")
ADMIN_DIR = os.path.join(BASE_DIR, "admin")
# Quote-form attachments live in their own folder. They contain whatever a
# website visitor chose to attach, so they must only ever be reachable by a
# logged-in admin (see /api/admin/inquiries/<id>/attachment below).
ATTACHMENT_DIR = os.path.join(BASE_DIR, "attachments")
MAIL_OUTBOX_DIR = os.path.join(BASE_DIR, "data", "mail-outbox")
SECRET_KEY_PATH = os.path.join(BASE_DIR, "data", "secret.key")
MAX_UPLOAD_MB = 25
MAX_ATTACHMENT_MB = 3


def _load_local_env_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_local_env_file()

os.makedirs(ATTACHMENT_DIR, exist_ok=True)
os.makedirs(MAIL_OUTBOX_DIR, exist_ok=True)
os.makedirs(os.path.dirname(SECRET_KEY_PATH), exist_ok=True)


def get_or_create_secret_key():
    configured_key = os.environ.get("SECRET_KEY", "").strip()
    if configured_key:
        return configured_key
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "r") as f:
            key = f.read().strip()
            if key:
                return key
    key = uuid.uuid4().hex + uuid.uuid4().hex
    with open(SECRET_KEY_PATH, "w") as f:
        f.write(key)
    return key


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


app = Flask(__name__, static_folder=None)
app.config["SECRET_KEY"] = get_or_create_secret_key()
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Browser only ever sends the admin session cookie over HTTPS in production.
# Left off for local http://127.0.0.1 development (set FLASK_ENV=production,
# or PYTHONANYWHERE_DOMAIN, on the live server) so local testing still works.
app.config["SESSION_COOKIE_SECURE"] = _env_flag("FORCE_SECURE_COOKIES") or bool(
    os.environ.get("PYTHONANYWHERE_DOMAIN")
) or os.environ.get("FLASK_ENV") == "production"
# Idle admin sessions expire after 30 minutes rather than staying valid
# indefinitely (Flask's unconfigured default is 31 days).
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(minutes=30)

db.init_db(
    default_username=os.environ.get("ADMIN_USERNAME", "admin"),
    # No hardcoded fallback password: if ADMIN_PASSWORD isn't set, db.py
    # generates a strong random one-time password on first run instead.
    default_password=os.environ.get("ADMIN_PASSWORD"),
    default_email=os.environ.get("ADMIN_EMAIL"),
)

# Let render_template() find templates under admin/ too (login.html,
# forgot_password.html, reset_password.html), alongside Flask's normal
# templates/ folder — the rest of the admin portal stays static HTML
# served via send_from_directory, unchanged.
app.jinja_loader = ChoiceLoader([app.jinja_loader, FileSystemLoader(ADMIN_DIR)])

# Signs/verifies password-reset tokens. Reuses the app's own secret key —
# no extra config needed — and tokens embed the account's current password
# hash, so changing the password (or completing one reset) invalidates
# every other outstanding token for that account automatically.
reset_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="admin-password-reset")
RESET_TOKEN_MAX_AGE_SECONDS = 60 * 60  # 1 hour


@app.after_request
def set_security_headers(response):
    """Baseline security headers on every response — cheap, and closes off
    a few common attack classes (clickjacking, MIME sniffing, referrer
    leakage) without affecting how the site looks or behaves."""
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if app.config["SESSION_COOKIE_SECURE"]:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.route("/healthz")
def health_check():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def require_admin(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        username = session.get("admin_user")
        if not username:
            return jsonify({"error": "Not authenticated"}), 401
        # An account flagged must_change_password (fresh install, or reset
        # by another admin) can only reach the change-password endpoint
        # itself until it sets a new password — closes off use of a
        # one-time/generated password beyond that first login.
        if request.path != "/api/admin/change-password":
            conn = db.get_db()
            row = conn.execute(
                "SELECT must_change_password FROM admin_users WHERE username = ?",
                (username,),
            ).fetchone()
            conn.close()
            if row and row["must_change_password"]:
                return jsonify({"error": "Password change required.", "must_change_password": True}), 403
        return view(*args, **kwargs)
    return wrapped


def now_iso():
    return datetime.datetime.utcnow().isoformat()


def _save_demo_quote_email(message, recipient_email):
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_recipient = secure_filename(recipient_email or "recipient") or "recipient"
    eml_path = os.path.join(MAIL_OUTBOX_DIR, f"quote-confirmation-{timestamp}-{safe_recipient}.eml")
    html_path = os.path.join(MAIL_OUTBOX_DIR, f"quote-confirmation-{timestamp}-{safe_recipient}.html")

    with open(eml_path, "wb") as f:
        f.write(message.as_bytes())

    html_body = None
    for part in message.walk():
        if part.get_content_type() == "text/html":
            html_body = part.get_payload(decode=True)
            break
    if html_body:
        with open(html_path, "wb") as f:
            f.write(html_body)

    print(f"[mail] Demo confirmation email saved to {eml_path}")
    if html_body:
        print(f"[mail] Demo HTML preview saved to {html_path}")
    return eml_path


def _send_quote_confirmation_email(recipient_email, submission):
    recipient_email = (recipient_email or "").strip()
    if not recipient_email:
        print("[mail] Skipping quote confirmation email: recipient email is empty.")
        return False

    mail_mode = (os.environ.get("MAIL_MODE") or "smtp").strip().lower()
    smtp_host = (os.environ.get("SMTP_HOST") or "").strip()
    if not smtp_host or mail_mode == "demo":
        message = _build_quote_confirmation_message(recipient_email, submission)
        _save_demo_quote_email(message, recipient_email)
        return True

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = (os.environ.get("SMTP_USERNAME") or "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD") or ""
    use_tls = _env_flag("SMTP_USE_TLS", True)
    use_ssl = _env_flag("SMTP_USE_SSL", False)

    sender_email = (os.environ.get("MAIL_FROM_EMAIL") or smtp_username or "no-reply@ladlielectricaltesting.com").strip()
    sender_name = (os.environ.get("MAIL_FROM_NAME") or "LADLI Electrical Testing and Calibration Laboratory").strip()
    reply_to = (os.environ.get("MAIL_REPLY_TO") or "ladlielec@gmail.com").strip()

    clean_name = html.escape(submission.get("contact_name") or submission.get("name") or "there")
    clean_company = html.escape(submission.get("company") or submission.get("company_organisation") or "-")
    clean_email = html.escape(recipient_email)
    clean_phone = html.escape(submission.get("phone") or "-")
    clean_site = html.escape(submission.get("site_plant") or "-")
    clean_city = html.escape(submission.get("city_state") or "-")
    clean_samples = html.escape(str(submission.get("number_of_samples") or "-"))
    clean_timeline = html.escape(submission.get("required_timeline") or "-")
    clean_transformer = html.escape(submission.get("transformer_id_s") or "-")
    clean_rating = html.escape(submission.get("rating_voltage_class") or "-")
    clean_tests = html.escape(submission.get("tests_required") or "-")
    clean_reason = html.escape(submission.get("reason_for_testing_additional_information") or "-")

    subject = "Thank you for your request quote submission | LADLI"
    plain_text = f"""Dear {submission.get('contact_name') or 'Customer'},

Thank you for trusting LADLI Electrical Testing and Calibration Laboratory.

We have received your request quote submission successfully. Our team will review the details and contact you shortly.

Submitted details:
- Contact name: {submission.get('contact_name') or '-'}
- Company / Organisation: {submission.get('company') or '-'}
- Email: {recipient_email}
- Phone: {submission.get('phone') or '-'}
- Site / Plant: {submission.get('site_plant') or '-'}
- City / State: {submission.get('city_state') or '-'}
- Number of samples: {submission.get('number_of_samples') or '-'}
- Required timeline: {submission.get('required_timeline') or '-'}
- Transformer ID(s): {submission.get('transformer_id_s') or '-'}
- Rating / Voltage class: {submission.get('rating_voltage_class') or '-'}
- Tests required: {submission.get('tests_required') or '-'}

If you need to update any detail, please reply to this email or contact us at ladlielec@gmail.com.

Thank you for your trust in LADLI.
"""


    html_body = f"""<!doctype html>
    <html>
    <body style="margin:0;padding:0;background:#f4f8ff;font-family:Arial,Helvetica,sans-serif;color:#17324d;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f8ff;padding:24px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;background:#ffffff;border:1px solid #d9e6ff;border-radius:22px;overflow:hidden;box-shadow:0 12px 30px rgba(31,111,229,0.10);">
                        <tr>
                            <td style="background:linear-gradient(135deg,#0f4fb8,#1f6fe5);padding:28px 32px;color:#ffffff;">
                                <table role="presentation" cellspacing="0" cellpadding="0" width="100%">
                                    <tr>
                                        <td valign="middle" style="width:88px;padding-right:18px;">
                                            <img src="cid:ladli-logo" alt="LADLI logo" width="72" height="72" style="display:block;border-radius:18px;background:#ffffff;padding:6px;" />
                                        </td>
                                        <td valign="middle">
                                            <div style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.9;font-weight:700;">LADLI Electrical Testing and Calibration Laboratory</div>
                                            <div style="font-size:28px;line-height:1.15;font-weight:800;margin-top:8px;">Your request quote is received</div>
                                            <div style="font-size:15px;line-height:1.6;opacity:.95;margin-top:10px;">Thank you for trusting LADLI. Our team will review your submission and contact you shortly.</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:32px;">
                                <p style="margin:0 0 18px;font-size:16px;line-height:1.7;">Dear <strong>{clean_name}</strong>,</p>
                                <p style="margin:0 0 22px;font-size:15px;line-height:1.7;color:#40607e;">We have successfully received your request quote submission. The details below have been recorded by our team.</p>
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:0 10px;">
                                    <tr><td style="width:220px;color:#6b7f95;font-size:13px;">Contact name</td><td style="font-size:14px;font-weight:700;">{clean_name}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Company / Organisation</td><td style="font-size:14px;">{clean_company}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Email</td><td style="font-size:14px;">{clean_email}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Phone</td><td style="font-size:14px;">{clean_phone}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Site / Plant</td><td style="font-size:14px;">{clean_site}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">City / State</td><td style="font-size:14px;">{clean_city}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Number of samples</td><td style="font-size:14px;">{clean_samples}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Required timeline</td><td style="font-size:14px;">{clean_timeline}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Transformer ID(s)</td><td style="font-size:14px;">{clean_transformer}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Rating / Voltage class</td><td style="font-size:14px;">{clean_rating}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Tests required</td><td style="font-size:14px;">{clean_tests}</td></tr>
                                </table>
                                <div style="margin-top:22px;padding:16px 18px;border-left:4px solid #1f6fe5;background:#f5f9ff;border-radius:14px;font-size:14px;line-height:1.7;color:#33506a;">
                                    <strong style="color:#17324d;">Additional information:</strong><br />
                                    {clean_reason}
                                </div>
                                <div style="margin-top:26px;padding-top:18px;border-top:1px solid #e7eef8;font-size:14px;line-height:1.7;color:#46607a;">
                                    If you need to update any detail, simply reply to this email or contact us at <a href="mailto:ladlielec@gmail.com" style="color:#1f6fe5;text-decoration:none;font-weight:700;">ladlielec@gmail.com</a>.<br />
                                    We appreciate your trust in LADLI.
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:0 32px 28px;">
                                <div style="font-size:12px;line-height:1.6;color:#7b8ca3;">LADLI Electrical Testing and Calibration Laboratory Pvt. Ltd. · A/39, First Floor, Shrenik Park, Opp. Akota Stadium, Productivity Road, Vadodara 390020</div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>"""

    message = MIMEMultipart("related")
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender_email}>"
    message["To"] = recipient_email
    if reply_to:
        message["Reply-To"] = reply_to

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(plain_text, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(alternative)

    logo_path = os.path.join(SITE_DIR, "assets", "images", "ladli-logo.png")
    if os.path.isfile(logo_path):
        with open(logo_path, "rb") as logo_file:
            logo_part = MIMEImage(logo_file.read())
        logo_part.add_header("Content-ID", "<ladli-logo>")
        logo_part.add_header("Content-Disposition", "inline", filename="ladli-logo.png")
        message.attach(logo_part)

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        with server as smtp:
            smtp.ehlo()
            if use_tls and not use_ssl:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if smtp_username:
                smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
        return True
    except Exception as exc:
        print(f"[mail] Could not send quote confirmation email: {exc}")
        return False


def _build_quote_confirmation_message(recipient_email, submission):
    recipient_email = (recipient_email or "").strip()
    smtp_username = (os.environ.get("SMTP_USERNAME") or "").strip()
    sender_email = (os.environ.get("MAIL_FROM_EMAIL") or smtp_username or "no-reply@ladlielectricaltesting.com").strip()
    sender_name = (os.environ.get("MAIL_FROM_NAME") or "LADLI Electrical Testing and Calibration Laboratory").strip()
    reply_to = (os.environ.get("MAIL_REPLY_TO") or "ladlielec@gmail.com").strip()

    clean_name = html.escape(submission.get("contact_name") or submission.get("name") or "there")
    clean_company = html.escape(submission.get("company") or submission.get("company_organisation") or "-")
    clean_email = html.escape(recipient_email)
    clean_phone = html.escape(submission.get("phone") or "-")
    clean_site = html.escape(submission.get("site_plant") or "-")
    clean_city = html.escape(submission.get("city_state") or "-")
    clean_samples = html.escape(str(submission.get("number_of_samples") or "-"))
    clean_timeline = html.escape(submission.get("required_timeline") or "-")
    clean_transformer = html.escape(submission.get("transformer_id_s") or "-")
    clean_rating = html.escape(submission.get("rating_voltage_class") or "-")
    clean_tests = html.escape(submission.get("tests_required") or "-")
    clean_reason = html.escape(submission.get("reason_for_testing_additional_information") or "-")

    subject = "Thank you for your request quote submission | LADLI"
    plain_text = f"""Dear {submission.get('contact_name') or 'Customer'},

    Thank you for trusting LADLI Electrical Testing and Calibration Laboratory.

    We have received your request quote submission successfully. Our team will review the details and contact you shortly.

    Submitted details:
    - Contact name: {submission.get('contact_name') or '-'}
    - Company / Organisation: {submission.get('company') or submission.get('company_organisation') or '-'}
    - Email: {recipient_email}
    - Phone: {submission.get('phone') or '-'}
    - Site / Plant: {submission.get('site_plant') or '-'}
    - City / State: {submission.get('city_state') or '-'}
    - Number of samples: {submission.get('number_of_samples') or '-'}
    - Required timeline: {submission.get('required_timeline') or '-'}
    - Transformer ID(s): {submission.get('transformer_id_s') or '-'}
    - Rating / Voltage class: {submission.get('rating_voltage_class') or '-'}
    - Tests required: {submission.get('tests_required') or '-'}

    If you need to update any detail, please reply to this email or contact us at ladlielec@gmail.com.

    Thank you for your trust in LADLI.
    """

    html_body = f"""<!doctype html>
    <html>
    <body style="margin:0;padding:0;background:#f4f8ff;font-family:Arial,Helvetica,sans-serif;color:#17324d;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f8ff;padding:24px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;background:#ffffff;border:1px solid #d9e6ff;border-radius:22px;overflow:hidden;box-shadow:0 12px 30px rgba(31,111,229,0.10);">
                        <tr>
                            <td style="background:linear-gradient(135deg,#0f4fb8,#1f6fe5);padding:28px 32px;color:#ffffff;">
                                <table role="presentation" cellspacing="0" cellpadding="0" width="100%">
                                    <tr>
                                        <td valign="middle" style="width:88px;padding-right:18px;">
                                            <img src="cid:ladli-logo" alt="LADLI logo" width="72" height="72" style="display:block;border-radius:18px;background:#ffffff;padding:6px;" />
                                        </td>
                                        <td valign="middle">
                                            <div style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.9;font-weight:700;">LADLI Electrical Testing and Calibration Laboratory</div>
                                            <div style="font-size:28px;line-height:1.15;font-weight:800;margin-top:8px;">Your request quote is received</div>
                                            <div style="font-size:15px;line-height:1.6;opacity:.95;margin-top:10px;">Thank you for trusting LADLI. Our team will review your submission and contact you shortly.</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:32px;">
                                <p style="margin:0 0 18px;font-size:16px;line-height:1.7;">Dear <strong>{clean_name}</strong>,</p>
                                <p style="margin:0 0 22px;font-size:15px;line-height:1.7;color:#40607e;">We have successfully received your request quote submission. The details below have been recorded by our team.</p>
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:0 10px;">
                                    <tr><td style="width:220px;color:#6b7f95;font-size:13px;">Contact name</td><td style="font-size:14px;font-weight:700;">{clean_name}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Company / Organisation</td><td style="font-size:14px;">{clean_company}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Email</td><td style="font-size:14px;">{clean_email}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Phone</td><td style="font-size:14px;">{clean_phone}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Site / Plant</td><td style="font-size:14px;">{clean_site}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">City / State</td><td style="font-size:14px;">{clean_city}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Number of samples</td><td style="font-size:14px;">{clean_samples}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Required timeline</td><td style="font-size:14px;">{clean_timeline}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Transformer ID(s)</td><td style="font-size:14px;">{clean_transformer}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Rating / Voltage class</td><td style="font-size:14px;">{clean_rating}</td></tr>
                                    <tr><td style="color:#6b7f95;font-size:13px;">Tests required</td><td style="font-size:14px;">{clean_tests}</td></tr>
                                </table>
                                <div style="margin-top:22px;padding:16px 18px;border-left:4px solid #1f6fe5;background:#f5f9ff;border-radius:14px;font-size:14px;line-height:1.7;color:#33506a;">
                                    <strong style="color:#17324d;">Additional information:</strong><br />
                                    {clean_reason}
                                </div>
                                <div style="margin-top:26px;padding-top:18px;border-top:1px solid #e7eef8;font-size:14px;line-height:1.7;color:#46607a;">
                                    If you need to update any detail, simply reply to this email or contact us at <a href="mailto:ladlielec@gmail.com" style="color:#1f6fe5;text-decoration:none;font-weight:700;">ladlielec@gmail.com</a>.<br />
                                    We appreciate your trust in LADLI.
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:0 32px 28px;">
                                <div style="font-size:12px;line-height:1.6;color:#7b8ca3;">LADLI Electrical Testing and Calibration Laboratory Pvt. Ltd. · A/39, First Floor, Shrenik Park, Opp. Akota Stadium, Productivity Road, Vadodara 390020</div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>"""

    message = MIMEMultipart("related")
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender_email}>"
    message["To"] = recipient_email
    if reply_to:
        message["Reply-To"] = reply_to

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(plain_text, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(alternative)

    logo_path = os.path.join(SITE_DIR, "assets", "images", "ladli-logo.png")
    if os.path.isfile(logo_path):
        with open(logo_path, "rb") as logo_file:
            logo_part = MIMEImage(logo_file.read())
        logo_part.add_header("Content-ID", "<ladli-logo>")
        logo_part.add_header("Content-Disposition", "inline", filename="ladli-logo.png")
        message.attach(logo_part)

    return message


def _save_quote_attachment(file_storage):
    """
    Validates an uploaded quote-form attachment and saves it to disk.
    Returns (stored_filename, original_name, size_bytes) on success.
    Raises ValueError with a user-facing message on validation failure.
    """
    original_name = file_storage.filename or ""
    if not original_name.lower().endswith(".pdf"):
        raise ValueError("Attachment must be a PDF file.")

    data = file_storage.read()
    size_bytes = len(data)
    if size_bytes == 0:
        raise ValueError("Attached file appears to be empty.")
    if size_bytes > MAX_ATTACHMENT_MB * 1024 * 1024:
        raise ValueError(f"Attachment is larger than {MAX_ATTACHMENT_MB} MB. Please attach a smaller PDF.")
    if not data.startswith(b"%PDF"):
        raise ValueError("That file doesn't look like a valid PDF.")

    stored_name = f"{uuid.uuid4().hex}.pdf"
    full_path = os.path.join(ATTACHMENT_DIR, stored_name)
    with open(full_path, "wb") as f:
        f.write(data)

    safe_original_name = secure_filename(original_name) or "attachment.pdf"
    return stored_name, safe_original_name, size_bytes


def display_date(iso_str):
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.strftime("%d %b %Y")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Visitor Management — persistent unique-device counter (Auto mode)
# ---------------------------------------------------------------------------
#
# "Auto" mode shows the total number of unique devices/browsers that have
# EVER visited the site — a lifetime total, not a point-in-time "who's on
# the site right now" count. The client (see assets/site.js) generates a
# random UUID once with crypto.randomUUID(), stores it permanently in
# localStorage ("ladli_visitor_id"), and pings /api/visitor-register with it
# on every page load. The count only goes up the very first time a given
# id is ever seen; refreshing, navigating between pages, or coming back
# next week from the same browser never increments it again. A different
# browser or device always has a different localStorage, so it always
# counts as a new, distinct visitor.

def _hash_visitor_id(raw_visitor_id):
    """
    We never store the client's raw localStorage id — it's hashed before
    being written to the database. The id is already an anonymous random
    UUID with no personal information in it, so this isn't for privacy of
    the value itself; it just keeps the stored token an opaque, fixed-
    length fingerprint that can't be reverse-engineered or replayed to
    correlate with anything else the id might be used for client-side.
    """
    return hashlib.sha256(raw_visitor_id.encode("utf-8")).hexdigest()


@app.route("/api/visitor-register", methods=["POST"])
def api_track_visitor():
    """
    Called once per page load by every visitor (see assets/site.js).
    Whether this is a brand-new device or one that's visited before, the
    response always reflects the current lifetime unique-visitor total —
    the count itself only increases the first time a given visitor_id is
    ever seen.
    """
    data = request.get_json(silent=True) or {}
    visitor_id = (data.get("visitor_id") or "").strip()
    if not visitor_id or len(visitor_id) > 128:
        return jsonify({"ok": False, "error": "Invalid visitor id."}), 400

    token = _hash_visitor_id(visitor_id)
    is_new_visitor, _unique_total = db.record_unique_visitor(token)
    count, mode = db.get_display_visitor_count()
    res = jsonify({"ok": True, "new_visitor": is_new_visitor, "count": count, "mode": mode})
    res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return res


# ---------------------------------------------------------------------------
# Public site (static HTML/CSS/JS/images)
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(SITE_DIR, "index.html")


# Static, versionless assets (css/js/fonts/images) are safe to let browsers
# cache aggressively — they're only ever replaced by a full redeploy, not by
# an admin action. HTML pages are excluded so page content/text is never
# served stale. This only affects response headers, not the served content.
_LONG_CACHE_EXTENSIONS = (
    ".css", ".js", ".mjs", ".woff", ".woff2", ".ttf", ".eot",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
)


@app.route("/<path:filename>")
def site_files(filename):
    # Never let this catch-all reach into backend-only folders.
    if filename.startswith(("admin/", "data/")):
        abort(404)
    full_path = os.path.join(SITE_DIR, filename)
    if os.path.isfile(full_path):
        resp = send_from_directory(SITE_DIR, filename, max_age=0)
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resp
    # Friendly 404 page for unknown routes.
    return send_from_directory(SITE_DIR, "404.html"), 404


# ---------------------------------------------------------------------------
# Public API — contact & quote forms
# ---------------------------------------------------------------------------

def _collect_form_fields(exclude):
    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    return {k: v for k, v in data.items() if k not in exclude and not k.startswith("_")}


def _respond_ok(data):
    """
    Progressive enhancement: JS submissions ask for JSON (Accept header) and
    get JSON back. A plain browser form POST (no JS) prefers HTML, so we
    redirect it to the page named in the hidden "_next" field instead.
    """
    wants_json = request.accept_mimetypes.best == "application/json" or request.is_json
    if wants_json:
        return jsonify({"ok": True})
    next_page = data.get("_next") or "thank-you.html"
    return redirect(f"/{next_page}")


@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})

    if data.get("_honey"):  # honeypot field — bots fill this in, humans never see it
        return jsonify({"ok": True})  # pretend success, drop silently

    name = (data.get("name") or "").strip()
    message = (data.get("message") or "").strip()
    if not name or not message:
        return jsonify({"ok": False, "error": "Name and message are required."}), 400

    conn = db.get_db()
    conn.execute(
        "INSERT INTO inquiries (kind, name, company, phone, email, message, extra_json, status, created_at) "
        "VALUES ('contact', ?, ?, ?, ?, ?, NULL, 'new', ?)",
        (name, data.get("company", ""), data.get("phone", ""), data.get("email", ""), message, now_iso()),
    )
    conn.commit()
    conn.close()
    return _respond_ok(data)


@app.route("/api/quote", methods=["POST"])
def api_quote():
    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})

    if data.get("_honey"):
        return jsonify({"ok": True})

    name = (data.get("contact_name") or data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Contact name is required."}), 400

    known = {
        "contact_name",
        "company",
        "company_organisation",
        "phone",
        "email",
        "message",
        "_kind",
        "_next",
        "_honey",
        "attachment",
    }
    extra = {k: v for k, v in data.items() if k not in known}

    company = (data.get("company") or data.get("company_organisation") or "").strip()

    attachment_filename = attachment_original_name = None
    attachment_size_bytes = None
    upload = request.files.get("attachment")
    if upload and upload.filename:
        try:
            attachment_filename, attachment_original_name, attachment_size_bytes = _save_quote_attachment(upload)
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    conn = db.get_db()
    conn.execute(
        "INSERT INTO inquiries "
        "(kind, name, company, phone, email, message, extra_json, status, created_at, "
        "attachment_filename, attachment_original_name, attachment_size_bytes) "
        "VALUES ('quote', ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?)",
        (
            name,
            company,
            data.get("phone", ""),
            data.get("email", ""),
            data.get("message", ""),
            json.dumps(extra, ensure_ascii=False),
            now_iso(),
            attachment_filename,
            attachment_original_name,
            attachment_size_bytes,
        ),
    )
    conn.commit()
    conn.close()
    _send_quote_confirmation_email(data.get("email"), {
        "contact_name": name,
        "company": company,
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "site_plant": data.get("site_plant", ""),
        "city_state": data.get("city_state", ""),
        "number_of_samples": data.get("number_of_samples", ""),
        "required_timeline": data.get("required_timeline", ""),
        "transformer_id_s": data.get("transformer_id_s", ""),
        "rating_voltage_class": data.get("rating_voltage_class", ""),
        "tests_required": data.get("tests_required", ""),
        "reason_for_testing_additional_information": data.get("reason_for_testing_additional_information", ""),
    })
    return _respond_ok(data)


@app.route("/api/visitor-count")
def api_visitor_count():
    """
    Public, read-only endpoint: returns the current lifetime unique-visitor
    total (or the admin's manual override) WITHOUT recording a visit. Used
    by the frontend when it already knows this browser has a visitor id
    and just needs the number to display — recording happens exclusively
    through POST /api/visitor-register.
    """
    count, mode = db.get_display_visitor_count()
    res = jsonify({"count": count, "mode": mode})
    res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    res.headers["Pragma"] = "no-cache"
    res.headers["Expires"] = "0"
    return res


# ---------------------------------------------------------------------------
# Admin authentication
# ---------------------------------------------------------------------------

def _client_ip():
    # Trust X-Forwarded-For's first hop when present (typical behind a
    # reverse proxy / PaaS like PythonAnywhere); fall back to the direct
    # remote address otherwise.
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or request.form.to_dict()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    ip_address = _client_ip()

    if not username or not password:
        return jsonify({"ok": False, "error": "Invalid username or password."}), 401

    if db.is_locked_out(username, ip_address):
        return jsonify({
            "ok": False,
            "error": (
                f"Too many failed attempts. Try again in "
                f"{db.LOCKOUT_WINDOW_MINUTES} minutes."
            ),
        }), 429

    conn = db.get_db()
    row = conn.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        db.record_login_attempt(username, ip_address, success=False)
        # Only give specific feedback (wrong password vs. old password) once
        # the username itself is known to be valid — an unknown username
        # still gets the generic message, so login can't be used to probe
        # which usernames exist.
        error = "Invalid username or password."
        if row:
            changed_ago = db.find_password_in_history(username, password, row["password_hash"])
            if changed_ago:
                error = f"This password was changed {changed_ago}. Please use your newest password."
            else:
                error = "Wrong password! Please check your credentials and try again."
        return jsonify({"ok": False, "error": error}), 401

    db.record_login_attempt(username, ip_address, success=True)
    db.clear_login_attempts(username, ip_address)

    session.clear()
    session["admin_user"] = username
    session.permanent = True
    return jsonify({
        "ok": True,
        "username": username,
        "must_change_password": bool(row["must_change_password"]),
    })


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/admin/me")
def api_admin_me():
    if session.get("admin_user"):
        conn = db.get_db()
        row = conn.execute(
            "SELECT must_change_password FROM admin_users WHERE username = ?",
            (session["admin_user"],),
        ).fetchone()
        conn.close()
        return jsonify({
            "logged_in": True,
            "username": session["admin_user"],
            "must_change_password": bool(row["must_change_password"]) if row else False,
        })
    return jsonify({"logged_in": False})


def _password_is_strong(pwd):
    # Minimal floor only — no composition/complexity rule, so any password
    # of reasonable length is accepted without a strength error.
    return len(pwd.strip()) >= 8


@app.route("/api/admin/change-password", methods=["POST"])
@require_admin
def api_admin_change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not _password_is_strong(new_password):
        return jsonify({
            "ok": False,
            "error": "New password must be at least 8 characters.",
        }), 400

    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM admin_users WHERE username = ?", (session["admin_user"],)
    ).fetchone()
    if not row or not check_password_hash(row["password_hash"], current):
        conn.close()
        return jsonify({"ok": False, "error": "Current password is incorrect."}), 400

    if check_password_hash(row["password_hash"], new_password):
        conn.close()
        return jsonify({"ok": False, "error": "New password must be different from the current one."}), 400

    conn.close()
    db.set_password(session["admin_user"], new_password)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Admin — forgot / reset password
# ---------------------------------------------------------------------------

def _send_password_reset_email(to_email, username, reset_url):
    """Best-effort reset email, reusing the same SMTP config as the quote-
    confirmation mail. Returns True/False; callers never let the result
    leak into the response the visitor sees (see forgot-password route)."""
    mail_mode = (os.environ.get("MAIL_MODE") or "smtp").strip().lower()
    smtp_host = (os.environ.get("SMTP_HOST") or "").strip()
    subject = "LADLI Admin — Password Reset Request"
    plain_text = (
        f"A password reset was requested for the LADLI admin account '{username}'.\n\n"
        f"Reset your password using this link (valid for 1 hour):\n{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email — "
        "your password will not change unless the link above is used."
    )

    if not smtp_host or mail_mode == "demo":
        # Local/dev fallback: no SMTP configured, so write it to the same
        # mail-outbox folder the quote-confirmation flow already uses,
        # instead of silently failing.
        os.makedirs(MAIL_OUTBOX_DIR, exist_ok=True)
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        with open(os.path.join(MAIL_OUTBOX_DIR, f"admin-reset-{timestamp}.eml"), "w", encoding="utf-8") as f:
            f.write(f"To: {to_email}\nSubject: {subject}\n\n{plain_text}")
        print(f"[mail] SMTP not configured — reset link written to mail-outbox instead:\n{reset_url}")
        return True

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = (os.environ.get("SMTP_USERNAME") or "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD") or ""
    use_tls = _env_flag("SMTP_USE_TLS", True)
    use_ssl = _env_flag("SMTP_USE_SSL", False)
    sender_email = (os.environ.get("MAIL_FROM_EMAIL") or smtp_username or "no-reply@ladlielectricaltesting.com").strip()
    sender_name = (os.environ.get("MAIL_FROM_NAME") or "LADLI Electrical Testing and Calibration Laboratory").strip()

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender_email}>"
    message["To"] = to_email
    message.attach(MIMEText(plain_text, "plain", "utf-8"))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        with server as smtp:
            smtp.ehlo()
            if use_tls and not use_ssl:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if smtp_username:
                smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
        return True
    except Exception as exc:
        print(f"[mail] Could not send admin reset email: {exc}")
        return False


@app.route("/admin/forgot-password", methods=["GET", "POST"])
def admin_forgot_password():
    if session.get("admin_user"):
        return redirect("/admin")

    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        row = db.find_admin_by_username_or_email(identifier) if identifier else None

        # Always show the same message whether or not the account exists —
        # a forgot-password form that confirms/denies an account's
        # existence is itself a username/email enumeration vector.
        generic_message = (
            "If that account exists, password reset instructions have been sent "
            "to its registered email address."
        )

        if row and row["email"]:
            token = reset_serializer.dumps({"u": row["username"], "h": row["password_hash"]})
            reset_url = url_for("admin_reset_password", token=token, _external=True)
            _send_password_reset_email(row["email"], row["username"], reset_url)
        elif row and not row["email"]:
            # Account matched but has no email on file — nothing to send,
            # but the response to the visitor stays identical either way.
            print(f"[admin] Password reset requested for '{row['username']}' but no email is on file (set ADMIN_EMAIL).")

        flash(generic_message, "success")
        return redirect(url_for("admin_forgot_password"))

    return render_template("forgot_password.html")


@app.route("/admin/reset-password/<token>", methods=["GET", "POST"])
def admin_reset_password(token):
    if session.get("admin_user"):
        return redirect("/admin")

    try:
        payload = reset_serializer.loads(token, max_age=RESET_TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        flash("That reset link has expired. Please request a new one.", "danger")
        return redirect(url_for("admin_forgot_password"))
    except BadSignature:
        flash("That reset link is invalid. Please request a new one.", "danger")
        return redirect(url_for("admin_forgot_password"))

    conn = db.get_db()
    row = conn.execute("SELECT * FROM admin_users WHERE username = ?", (payload.get("u"),)).fetchone()
    conn.close()

    # The token embeds the password hash that was current when it was
    # issued. If the password has since changed (this link was already
    # used, or changed another way), the hash won't match and the token
    # is treated as spent — closes off replaying an old reset link.
    if not row or row["password_hash"] != payload.get("h"):
        flash("That reset link has already been used. Please request a new one.", "danger")
        return redirect(url_for("admin_forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html", token=token)

        if not _password_is_strong(new_password):
            flash("New password must be at least 8 characters.", "danger")
            return render_template("reset_password.html", token=token)

        db.set_password(row["username"], new_password)
        flash("Your password has been updated. Please sign in.", "success")
        return redirect(url_for("admin_login_page"))

    return render_template("reset_password.html", token=token)


# ---------------------------------------------------------------------------
# Admin API — inquiries
# ---------------------------------------------------------------------------

@app.route("/api/admin/inquiries")
@require_admin
def api_admin_inquiries():
    kind = request.args.get("kind", "")
    status = request.args.get("status", "")

    query = "SELECT * FROM inquiries WHERE 1=1"
    params = []
    if kind in ("contact", "quote"):
        query += " AND kind = ?"
        params.append(kind)
    if status in ("new", "contacted", "closed"):
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"

    conn = db.get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    out = []
    for r in rows:
        extra = {}
        if r["extra_json"]:
            try:
                extra = json.loads(r["extra_json"])
            except Exception:
                extra = {}
        out.append({
            "id": r["id"],
            "kind": r["kind"],
            "name": r["name"],
            "company": r["company"],
            "phone": r["phone"],
            "email": r["email"],
            "message": r["message"],
            "extra": extra,
            "status": r["status"],
            "created_at": r["created_at"],
            "created_at_display": display_date(r["created_at"]),
            "has_attachment": bool(r["attachment_filename"]),
            "attachment_original_name": r["attachment_original_name"],
            "attachment_size_bytes": r["attachment_size_bytes"],
        })
    return jsonify(out)


@app.route("/api/admin/inquiries/<int:inquiry_id>/status", methods=["POST"])
@require_admin
def api_admin_update_status(inquiry_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("new", "contacted", "closed"):
        return jsonify({"ok": False, "error": "Invalid status."}), 400

    conn = db.get_db()
    cur = conn.execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, inquiry_id))
    conn.commit()
    updated = cur.rowcount
    conn.close()
    if not updated:
        return jsonify({"ok": False, "error": "Inquiry not found."}), 404
    return jsonify({"ok": True})


@app.route("/api/admin/inquiries/<int:inquiry_id>/attachment")
@require_admin
def api_admin_inquiry_attachment(inquiry_id):
    conn = db.get_db()
    row = conn.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
    conn.close()
    if not row or not row["attachment_filename"]:
        abort(404)
    download_name = row["attachment_original_name"] or row["attachment_filename"]
    return send_from_directory(
        ATTACHMENT_DIR, row["attachment_filename"], as_attachment=True, download_name=download_name
    )


@app.route("/api/admin/inquiries/<int:inquiry_id>", methods=["DELETE"])
@require_admin
def api_admin_delete_inquiry(inquiry_id):
    conn = db.get_db()
    row = conn.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "error": "Inquiry not found."}), 404
    if row["attachment_filename"]:
        file_path = os.path.join(ATTACHMENT_DIR, row["attachment_filename"])
        if os.path.isfile(file_path):
            os.remove(file_path)
    conn.execute("DELETE FROM inquiries WHERE id = ?", (inquiry_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Admin API — Visitor Management
# ---------------------------------------------------------------------------

@app.route("/api/admin/visitors")
@require_admin
def api_admin_visitors():
    row = db.get_visitor_stats()
    unique_count = db.get_unique_visitor_count()
    return jsonify({
        "unique_count": unique_count,
        "manual_count": row["manual_count"],
        "mode": row["mode"],
        "updated_at": row["updated_at"],
    })


@app.route("/api/admin/visitors", methods=["POST"])
@require_admin
def api_admin_update_visitors():
    data = request.get_json(silent=True) or {}

    if "mode" in data:
        mode = data.get("mode")
        if mode not in ("auto", "manual"):
            return jsonify({"ok": False, "error": "Mode must be 'auto' or 'manual'."}), 400
        db.set_visitor_mode(mode)

    if "manual_count" in data:
        try:
            manual_count = int(data.get("manual_count"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Manual count must be a whole number."}), 400
        if manual_count < 0:
            return jsonify({"ok": False, "error": "Manual count cannot be negative."}), 400
        db.set_manual_count(manual_count)

    row = db.get_visitor_stats()
    unique_count = db.get_unique_visitor_count()
    return jsonify({
        "ok": True,
        "unique_count": unique_count,
        "manual_count": row["manual_count"],
        "mode": row["mode"],
        "updated_at": row["updated_at"],
    })


# ---------------------------------------------------------------------------
# Admin portal pages (small static HTML app served with an auth gate)
# ---------------------------------------------------------------------------

@app.route("/admin")
@app.route("/admin/")
def admin_root():
    if session.get("admin_user"):
        return send_from_directory(ADMIN_DIR, "dashboard.html")
    return render_template("login.html")


@app.route("/admin/login")
def admin_login_page():
    if session.get("admin_user"):
        return redirect("/admin")
    return render_template("login.html")


@app.route("/admin/settings")
def admin_settings_page():
    if not session.get("admin_user"):
        return redirect("/admin/login")
    return send_from_directory(ADMIN_DIR, "settings.html")


@app.route("/admin/visitors")
def admin_visitors_page():
    if not session.get("admin_user"):
        return redirect("/admin/login")
    return send_from_directory(ADMIN_DIR, "visitors.html")


@app.route("/admin/assets/<path:filename>")
def admin_assets(filename):
    return send_from_directory(os.path.join(ADMIN_DIR, "assets"), filename)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

@app.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False, "error": f"File is larger than {MAX_UPLOAD_MB} MB."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"\n  LADLI site running at http://127.0.0.1:{port}")
    print(f"  Admin portal at        http://127.0.0.1:{port}/admin\n")
    app.run(host="127.0.0.1", port=port, debug=debug)