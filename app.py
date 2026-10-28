import hmac
import json
import mimetypes
import os
import re
import secrets
import smtplib
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for

load_dotenv()

app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    WHATSAPP_NUMBER=os.environ.get("MEDRON_WHATSAPP_NUMBER", "919342612752"),
    SALES_PHONE=os.environ.get("SALES_PHONE", "6382030676"),
    PUBLIC_BASE_URL=os.environ.get("PUBLIC_BASE_URL", "").rstrip("/"),
    CONTACT_EMAIL="medronhealthcaresystems@outlook.com",
    SMTP_HOST=os.environ.get("SMTP_HOST", "smtp-mail.outlook.com"),
    SMTP_PORT=int(os.environ.get("SMTP_PORT", "587")),
    SMTP_USERNAME=os.environ.get("SMTP_USERNAME", "").strip(),
    SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD", ""),
    SMTP_FROM=os.environ.get("SMTP_FROM", "medronhealthcaresystems@outlook.com").strip(),
    SMTP_AUTH_METHOD=os.environ.get(
        "SMTP_AUTH_METHOD",
        "oauth2" if os.environ.get("SMTP_OAUTH_REFRESH_TOKEN") else "password",
    ).strip().casefold(),
    SMTP_OAUTH_TENANT_ID=os.environ.get("SMTP_OAUTH_TENANT_ID", "common").strip(),
    SMTP_OAUTH_CLIENT_ID=os.environ.get("SMTP_OAUTH_CLIENT_ID", "").strip(),
    SMTP_OAUTH_CLIENT_SECRET=os.environ.get("SMTP_OAUTH_CLIENT_SECRET", ""),
    SMTP_OAUTH_REFRESH_TOKEN=os.environ.get("SMTP_OAUTH_REFRESH_TOKEN", ""),
)
app.secret_key = app.config["SECRET_KEY"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

IMAGES_DIRECTORY = Path(app.static_folder) / "images"
PRODUCTS_DIRECTORY = IMAGES_DIRECTORY / "products"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
CATEGORY_NAMES = {
    "medical furniture and cots": "Medical Furniture & Cots",
    "repiratory equipment": "Respiratory Equipment",
}


def get_catalog():
    products = []
    if not PRODUCTS_DIRECTORY.is_dir():
        return products, [], []

    for category_directory in sorted(PRODUCTS_DIRECTORY.iterdir(), key=lambda path: path.name.casefold()):
        if not category_directory.is_dir():
            continue
        category = CATEGORY_NAMES.get(category_directory.name.casefold(), category_directory.name)
        image_paths = sorted(
            category_directory.rglob("*"),
            key=lambda path: path.as_posix().casefold(),
        )
        for image_path in image_paths:
            if image_path.is_file() and image_path.suffix.casefold() in IMAGE_EXTENSIONS:
                products.append({
                    "name": image_path.stem.strip(),
                    "category": category,
                    "image": image_path.relative_to(IMAGES_DIRECTORY).as_posix(),
                })

    category_products = {}
    for product in products:
        category_products.setdefault(product["category"], product)
    categories = [
        {
            "name": name,
            "image": product["image"],
            "product_name": product["name"],
        }
        for name, product in sorted(category_products.items(), key=lambda item: item[0].casefold())
    ]
    featured_products = list(category_products.values())
    return products, categories, featured_products


def get_products():
    return get_catalog()[0]


def public_site_url():
    base_url = app.config["PUBLIC_BASE_URL"] or request.url_root
    return base_url.rstrip("/") + "/"


def public_static_url(filename):
    static_path = url_for("static", filename=filename)
    return urljoin(public_site_url(), static_path.lstrip("/"))


def whatsapp_url(message):
    number = re.sub(r"\D", "", app.config["WHATSAPP_NUMBER"])
    return f"https://wa.me/{number}?{urlencode({'text': message})}"


def whatsapp_phone_display():
    number = re.sub(r"\D", "", app.config["WHATSAPP_NUMBER"])
    local_number = number[2:] if number.startswith("91") else number
    return f"+91 {local_number}"


def phone_href(number):
    digits = re.sub(r"\D", "", number)
    if len(digits) == 10:
        digits = f"91{digits}"
    return f"tel:+{digits}"


def get_outlook_access_token():
    tenant_id = app.config["SMTP_OAUTH_TENANT_ID"]
    client_id = app.config["SMTP_OAUTH_CLIENT_ID"]
    refresh_token = app.config["SMTP_OAUTH_REFRESH_TOKEN"]
    if not tenant_id or not client_id or not refresh_token:
        raise ValueError("Outlook OAuth2 is missing its tenant, client ID, or refresh token.")

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://outlook.office.com/SMTP.Send offline_access",
    }
    client_secret = app.config["SMTP_OAUTH_CLIENT_SECRET"]
    if client_secret:
        token_data["client_secret"] = client_secret

    token_request = Request(
        token_url,
        data=urlencode(token_data).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(token_request, timeout=15) as response:
            payload = json.loads(response.read())
    except HTTPError as error:
        try:
            error_payload = json.loads(error.read())
            error_description = error_payload.get("error_description", error_payload.get("error", ""))
        except (ValueError, AttributeError):
            error_description = ""
        detail = f": {error_description}" if error_description else ""
        raise ValueError(
            f"Outlook OAuth2 token request failed with HTTP {error.code}{detail}"
        ) from error

    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise ValueError("Outlook OAuth2 token response did not contain an access token.")
    return payload["access_token"]


def log_contact_email_error(error, additional_secrets=()):
    safe_error = str(error)
    secrets_to_redact = (
        "SMTP_PASSWORD",
        "SMTP_OAUTH_CLIENT_SECRET",
        "SMTP_OAUTH_REFRESH_TOKEN",
    )
    for secret in (
        *(app.config.get(key, "") for key in secrets_to_redact),
        *additional_secrets,
    ):
        if secret:
            safe_error = safe_error.replace(secret, "[redacted]")
    app.logger.error("Contact form email delivery failed (%s): %s", type(error).__name__, safe_error)


def send_contact_email(form_data, attachments=()):
    smtp_host = app.config["SMTP_HOST"]
    smtp_username = app.config["SMTP_USERNAME"]
    sender = app.config["SMTP_FROM"]
    recipient = app.config["CONTACT_EMAIL"]
    auth_method = app.config["SMTP_AUTH_METHOD"]
    if not smtp_host or not smtp_username or not sender:
        app.logger.error("Contact form email is not configured; SMTP host, username, and sender are required.")
        return False
    if sender.casefold() != smtp_username.casefold():
        app.logger.error("Contact form sender must match the authenticated SMTP mailbox.")
        return False
    if auth_method not in {"password", "oauth2"}:
        app.logger.error("Contact form SMTP authentication method must be password or oauth2.")
        return False
    if auth_method == "password" and not app.config["SMTP_PASSWORD"]:
        app.logger.error("Contact form SMTP password authentication is selected but its password is missing.")
        return False
    if auth_method == "oauth2" and not all((
        app.config["SMTP_OAUTH_TENANT_ID"],
        app.config["SMTP_OAUTH_CLIENT_ID"],
        app.config["SMTP_OAUTH_REFRESH_TOKEN"],
    )):
        app.logger.error("Contact form Outlook OAuth2 is selected but required credentials are missing.")
        return False

    message = EmailMessage()
    message["Subject"] = f"New Website Enquiry - {form_data['subject']}"
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = form_data["email"]
    message.set_content(
        "New enquiry received from Medron Healthcare Systems website.\n\n"
        f"Customer Name: {form_data['name']}\n\n"
        f"Phone Number: {form_data['phone']}\n\n"
        f"Customer Email: {form_data['email']}\n\n"
        f"Subject: {form_data['subject']}\n\n"
        f"Message: {form_data['message']}\n"
    )
    for filename, content, content_type in attachments:
        maintype, subtype = content_type.split("/", 1)
        message.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    access_token = ""
    try:
        with smtplib.SMTP(smtp_host, app.config["SMTP_PORT"], timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if auth_method == "oauth2":
                access_token = get_outlook_access_token()
                auth_string = f"user={smtp_username}\x01auth=Bearer {access_token}\x01\x01"
                smtp.auth("XOAUTH2", lambda challenge: auth_string)
            else:
                smtp.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
            refused_recipients = smtp.send_message(message)
            if refused_recipients:
                log_contact_email_error(smtplib.SMTPRecipientsRefused(refused_recipients))
                return False
    except (OSError, smtplib.SMTPException, ValueError) as error:
        log_contact_email_error(error, (access_token,))
        return False
    return True


def validate_quote_form(form_data, product_names):
    errors = []
    limits = {
        "name": 100,
        "phone": 30,
        "email": 254,
        "organization": 200,
        "service": 150,
        "details": 5000,
    }
    for field, limit in limits.items():
        if field in {"name", "phone", "email", "service"} and not form_data[field]:
            errors.append("Please complete all required quote form fields.")
            break
        if len(form_data[field]) > limit:
            errors.append("One or more fields exceed the allowed length.")
            break
        allowed_controls = "\r\n\t" if field == "details" else ""
        if any(
            ord(character) < 32 and character not in allowed_controls
            for character in form_data[field]
        ):
            errors.append("Remove unsupported control characters from the form.")
            break

    if not errors:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", form_data["email"]):
            errors.append("Enter a valid email address.")
        phone_digits = re.sub(r"[\s()+.\-]", "", form_data["phone"])
        if not phone_digits.isdigit() or not 7 <= len(phone_digits) <= 15:
            errors.append("Enter a valid phone number.")
        if form_data["service"] not in {*product_names, "Calibration", "Repair & Support"}:
            errors.append("Select a valid product or service.")
    return errors


def render_contact_page(quote_form_data, quote_csrf_token, status=200):
    return render_template(
        "contact.html",
        quote_form_data=quote_form_data,
        quote_csrf_token=quote_csrf_token,
        product_names=[product["name"] for product in get_products()],
    ), status


def submit_quote_request():
    fields = ("name", "phone", "email", "organization", "service", "details")
    quote_form_data = {
        field: request.form.get(field, "").strip()
        for field in fields
    }
    csrf_token = session.setdefault("_quote_csrf_token", secrets.token_urlsafe(32))
    submitted_token = request.form.get("csrf_token", "")
    if not submitted_token or not hmac.compare_digest(csrf_token, submitted_token):
        flash("Your form session expired. Please refresh the page and try again.", "error")
        return render_contact_page(quote_form_data, csrf_token, 400)

    product_names = [product["name"] for product in get_products()]
    errors = validate_quote_form(quote_form_data, product_names)
    upload = request.files.get("file")
    attachments = []
    if not errors and upload and upload.filename:
        content = upload.stream.read(5 * 1024 * 1024 + 1)
        if len(content) > 5 * 1024 * 1024:
            errors.append("The optional attachment must be 5 MB or smaller.")
        else:
            filename = re.split(r"[/\\]", upload.filename)[-1]
            filename = "".join(
                character for character in filename
                if ord(character) >= 32 and character not in "\r\n"
            ).strip()
            if not filename:
                errors.append("Choose a valid attachment filename.")
            else:
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                attachments.append((filename, content, content_type))

    if errors:
        for error in errors:
            flash(error, "error")
        return render_contact_page(quote_form_data, csrf_token, 400)

    email_data = {
        "name": quote_form_data["name"],
        "phone": quote_form_data["phone"],
        "email": quote_form_data["email"],
        "subject": f"Quote request: {quote_form_data['service']}",
        "message": (
            f"Organization / Hospital Name: {quote_form_data['organization'] or 'Not provided'}\n"
            f"Product / Service Required: {quote_form_data['service']}\n"
            f"Requirement Details: {quote_form_data['details'] or 'Not provided'}"
        ),
    }
    if not send_contact_email(email_data, attachments):
        flash(
            "We could not send your quote request right now. Please try again later or contact us by phone or email.",
            "error",
        )
        return render_contact_page(quote_form_data, csrf_token, 503)

    session.pop("_quote_csrf_token", None)
    flash("Thank you! Your quote request has been sent successfully. Our team will contact you soon.", "success")
    return redirect(url_for("contact", _anchor="request-quote"))


@app.context_processor
def globals():
    _, categories, featured_products = get_catalog()
    return {
        "categories": categories,
        "featured_products": featured_products,
        "public_site_url": public_site_url,
        "public_static_url": public_static_url,
        "whatsapp_url": whatsapp_url,
        "whatsapp_phone_display": whatsapp_phone_display,
        "phone_href": phone_href,
    }

@app.route("/")
def home(): return render_template("home.html")
@app.route("/about")
def about(): return render_template("about.html")
@app.route("/products")
def products():
    selected=request.args.get("category","")
    all_products, categories, _ = get_catalog()
    if selected not in {category["name"] for category in categories}:
        selected = ""
    items = all_products if not selected else [p for p in all_products if p["category"] == selected]
    return render_template("products.html",products=items,selected=selected)
@app.route("/services")
def services(): return render_template("services.html")


@app.route("/calibration")
def calibration():
    return render_template("calibration.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        return submit_quote_request()
    quote_form_data = {
        "name": "",
        "phone": "",
        "email": "",
        "organization": "",
        "service": "",
        "details": "",
    }
    csrf_token = session.setdefault("_quote_csrf_token", secrets.token_urlsafe(32))
    return render_contact_page(quote_form_data, csrf_token)


@app.route("/quote", methods=["GET", "POST"])
@app.route("/request-quote", methods=["GET", "POST"])
def quote():
    if request.method == "POST":
        return submit_quote_request()
    return redirect(url_for("contact", _anchor="request-quote"))
if __name__=="__main__": app.run(debug=True)
