import base64
from functools import wraps
from urllib.parse import urlparse

import requests
from flask import current_app, abort, request
from flask_login import current_user


def safe_redirect_target(target, fallback):
    """Return `target` only if it is a same-site URL, otherwise `fallback`.

    Used for ?next= and Referer redirects so an attacker cannot craft a link
    that bounces a logged-in user to another website (open redirect).
    """
    if not target:
        return fallback
    target = target.strip()
    # Browsers treat "\\" like "/", so "/\\evil.com" would escape the site.
    if "\\" in target or any(ord(ch) < 32 for ch in target):
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        same_site = (
            parsed.scheme in ("http", "https")
            and parsed.netloc == urlparse(request.host_url).netloc
        )
        return target if same_site else fallback
    if not target.startswith("/") or target.startswith("//"):
        return fallback
    return target


def staff_required(view_func):
    """Allow the main admin and moderators to access staff/admin features."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


def admin_required(view_func):
    """Backward-compatible alias for routes that require staff access."""
    return staff_required(view_func)


def main_admin_required(view_func):
    """Restrict a route to the main administrator (role == 'admin')."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_main_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


def allowed_image(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def upload_to_imagekit(file_storage, folder="/hairshellizer/products/", return_metadata: bool = False) -> str | dict[str, str]:
    """Upload a Werkzeug FileStorage to ImageKit.

    By default this preserves the existing behavior and returns only the URL.
    When return_metadata=True, the caller receives both the public URL and
    ImageKit's fileId so the asset can later be deleted remotely.
    """
    private_key = current_app.config["IMAGEKIT_PRIVATE_KEY"]
    if not private_key:
        raise RuntimeError(
            "ImageKit is not configured. Set IMAGEKIT_PRIVATE_KEY, "
            "IMAGEKIT_PUBLIC_KEY and IMAGEKIT_URL_ENDPOINT in your .env file."
        )

    file_bytes = file_storage.read()
    encoded = base64.b64encode(file_bytes).decode("utf-8")

    response = requests.post(
        "https://upload.imagekit.io/api/v1/files/upload",
        auth=(private_key, ""),
        data={
            "fileName": file_storage.filename,
            "file": encoded,
            "useUniqueFileName": "true",
            "folder": folder,
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    if return_metadata:
        file_id = data.get("fileId")
        if not file_id:
            raise RuntimeError("ImageKit upload succeeded but did not return a file ID.")
        return {"url": data["url"], "file_id": file_id}

    return data["url"]


def delete_from_imagekit(file_id):
    """Delete an ImageKit asset by its fileId."""
    if not file_id:
        return False

    private_key = current_app.config["IMAGEKIT_PRIVATE_KEY"]
    if not private_key:
        raise RuntimeError("ImageKit is not configured. Set IMAGEKIT_PRIVATE_KEY in your .env file.")

    response = requests.delete(
        f"https://api.imagekit.io/v1/files/{file_id}",
        auth=(private_key, ""),
        timeout=20,
    )
    response.raise_for_status()
    return True


def send_password_reset_email(user, reset_url):
    """Send a password reset email through Brevo's transactional API."""
    api_key = current_app.config.get("BREVO_API_KEY")
    sender_email = current_app.config.get("BREVO_SENDER_EMAIL")
    sender_name = current_app.config.get("BREVO_SENDER_NAME", "HairShellizer")

    if not api_key or not sender_email:
        raise RuntimeError(
            "Brevo is not configured. Set BREVO_API_KEY and BREVO_SENDER_EMAIL."
        )

    safe_name = (user.name or "there").replace("<", "&lt;").replace(">", "&gt;")
    safe_url = reset_url.replace("&", "&amp;").replace('"', "&quot;")

    html = f"""<!doctype html>
<html>
  <body style="font-family:Arial,sans-serif;line-height:1.6;color:#263238;max-width:600px;margin:auto;padding:24px;">
    <h2 style="margin-bottom:8px;">Reset your HairShellizer password</h2>
    <p>Hello {safe_name},</p>
    <p>We received a request to reset the password for your HairShellizer account.</p>
    <p style="margin:28px 0;">
      <a href="{safe_url}" style="display:inline-block;background:#198754;color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;">Reset Password</a>
    </p>
    <p>This link expires in <strong>60 minutes</strong> and can only be used once.</p>
    <p>If you did not request a password reset, you can safely ignore this email.</p>
    <p style="margin-top:32px;">— HairShellizer</p>
  </body>
</html>"""
    text = f"""Hello {user.name or 'there'},

We received a request to reset your HairShellizer account password.

Reset your password here:
{reset_url}

This link expires in 60 minutes and can only be used once.

If you did not request a password reset, you can safely ignore this email.

— HairShellizer
"""

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        json={
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": user.email, "name": user.name}],
            "subject": "Reset your HairShellizer password",
            "htmlContent": html,
            "textContent": text,
            "tags": ["password-reset"],
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
