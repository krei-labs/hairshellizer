import base64
from functools import wraps

import requests
from flask import current_app, abort
from flask_login import current_user


def admin_required(view_func):
    """Restrict a route to logged-in users with role == 'admin'."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


def allowed_image(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def upload_to_imagekit(file_storage, folder="/hairshellizer/products/"):
    """Upload a Werkzeug FileStorage to ImageKit and return the permanent URL.

    Product images must never be stored inside PostgreSQL or on Vercel's
    filesystem, so every admin-uploaded image goes through this helper and
    only the returned URL is saved to the database.
    """
    private_key = current_app.config["IMAGEKIT_PRIVATE_KEY"]
    if not private_key:
        raise RuntimeError(
            "ImageKit is not configured. Set IMAGEKIT_PRIVATE_KEY, "
            "IMAGEKIT_PUBLIC_KEY and IMAGEKIT_URL_ENDPOINT in your .env file."
        )

    file_bytes = file_storage.read()
    encoded = base64.b64encode(file_bytes).decode("utf-8")

    auth = (private_key, "")
    response = requests.post(
        "https://upload.imagekit.io/api/v1/files/upload",
        auth=auth,
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
    return data["url"]
