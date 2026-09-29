import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration. Values come from environment variables so that
    no secret ever needs to be hard-coded or committed to GitHub."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # Neon (and most managed Postgres providers) sometimes hand out URLs
    # that start with postgres:// . SQLAlchemy 1.4+ / psycopg2 need
    # postgresql:// instead, so we normalize it here.
    _raw_db_url = os.environ.get("DATABASE_URL", "")
    if _raw_db_url.startswith("postgres://"):
        _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url or "sqlite:///dev.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Serverless-friendly connection pooling: recycle connections often and
    # verify them before use so we don't hand out dead connections from a
    # cold-started function.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # ImageKit (used for admin-uploaded product images)
    IMAGEKIT_PRIVATE_KEY = os.environ.get("IMAGEKIT_PRIVATE_KEY", "")
    IMAGEKIT_PUBLIC_KEY = os.environ.get("IMAGEKIT_PUBLIC_KEY", "")
    IMAGEKIT_URL_ENDPOINT = os.environ.get("IMAGEKIT_URL_ENDPOINT", "")

    # Seller / business contact info (also editable later via admin settings)
    SELLER_FACEBOOK_URL = os.environ.get(
        "SELLER_FACEBOOK_URL",
        "https://www.facebook.com/share/1c6k1wjVB4/?mibextid=wwXIfr",
    )
    SELLER_EMAIL = os.environ.get("SELLER_EMAIL", "hairshellizer@gmail.com")
    SELLER_PHONE = os.environ.get("SELLER_PHONE", "+63 991 712 5341")

    # Brevo transactional email (password reset, notifications, etc.)
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "")
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")
    BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "HairShellizer")

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    INQUIRY_EXPIRATION_HOURS = 24
