# Medron Healthcare Systems - Flask Website

Six pages from the supplied reference design:
- Home
- About Us
- Products
- Services
- Contact Us
- Request a Quote

The website uses content from the supplied Medron Healthcare Systems brochure and follows the supplied screenshot's navy/white healthcare layout.

## Run
python -m venv venv
Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py

Then open http://127.0.0.1:5000

## Add products
Save each product image in a category folder under `static/images/products/`, for example:
`static/images/products/Basic & Home Care/Digital Thermometer.png`

The image filename (without its extension) is displayed as the product name. Products and categories are read from these folders when pages load, so new images appear automatically. Empty category folders are not shown.

## Contact form and WhatsApp configuration
The Contact form validates the submitted fields and includes a session-based CSRF token. It reports success only after the configured SMTP server accepts the email. If SMTP is not configured or delivery fails, the form displays an error and points visitors to the listed phone and email contacts.

Configure these environment variables before deployment:

- `FLASK_SECRET_KEY`: a long, private, stable secret for session signing.
- `MEDRON_WHATSAPP_NUMBER`: WhatsApp number in international digits with no `+` or spaces. The current default is the confirmed equipment contact, `919342612752`.
- `PUBLIC_BASE_URL`: the public site origin, such as `https://your-domain.example`. Set this in production so WhatsApp messages use public product-image and website URLs.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, and `SMTP_FROM`: Outlook SMTP settings. The defaults are `smtp-mail.outlook.com` and port `587`; STARTTLS is always used. The authenticated mailbox and sender must match.
- `SMTP_AUTH_METHOD`: `oauth2` (recommended) or `password`. Password authentication is available only if Microsoft permits SMTP AUTH and password/app-password sign-in for this mailbox.
- `SMTP_PASSWORD`: mailbox password or app password when `SMTP_AUTH_METHOD=password`; do not use this setting for OAuth2.
- `SMTP_OAUTH_TENANT_ID`, `SMTP_OAUTH_CLIENT_ID`, `SMTP_OAUTH_CLIENT_SECRET`, and `SMTP_OAUTH_REFRESH_TOKEN`: OAuth2 application and delegated-token settings when `SMTP_AUTH_METHOD=oauth2`. The token must include the Outlook `SMTP.Send` delegated scope. The client secret is optional for public clients.
- Contact enquiries are always delivered to `medronhealthcaresystems@outlook.com`; the destination is not taken from form input or an environment override.
- `SALES_PHONE`: sales phone for contact links. It defaults to the existing number.

Copy `.env.example` to `.env` for local development; the application loads `.env` and `.env` is ignored by Git. Never commit real credentials. Microsoft documents OAuth2 for SMTP with both Outlook.com and Microsoft 365 accounts ([OAuth authentication for IMAP, POP, and SMTP](https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth)). Microsoft 365 tenants commonly disable password-based SMTP AUTH; some Outlook mailbox configurations may still allow a password or app password. The application cannot determine the authentication policy for this specific mailbox, so verify it with the Microsoft account or tenant administrator. SMTP AUTH must be enabled for the mailbox in either case. No credentials are included in this project, so live delivery cannot be verified until the company supplies valid credentials and permissions. WhatsApp enquiry links work independently of SMTP.

The calibration page lists equipment types as enquiry categories only; service availability is confirmed with Medron for each enquiry.
