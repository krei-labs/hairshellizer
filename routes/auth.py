from datetime import datetime, timedelta
import hashlib
import secrets

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User, PasswordResetToken
from utils import send_password_reset_email, safe_redirect_target

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Name, email and password are required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
        else:
            user = User(name=name, email=email, phone=phone, address=address, role="customer")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to HairShellizer! Your account has been created.", "success")
            return redirect(url_for("pages.home"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.is_active and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.name}!", "success")
            # Only follow same-site ?next= targets (blocks open redirects such
            # as ?next=https://evil.example or ?next=//evil.example).
            default_page = url_for("admin.dashboard") if user.is_admin else url_for("pages.home")
            return redirect(safe_redirect_target(request.args.get("next"), default_page))

        if user and not user.is_active:
            flash("This account is currently deactivated. Please contact the store administrator.", "danger")
        else:
            flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("account.profile"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first() if email else None

        # Always show the same response so the page does not reveal whether
        # an email address belongs to an account.
        if user and user.is_active:
            PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).delete(
                synchronize_session=False
            )
            raw_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            reset_token = PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.utcnow() + timedelta(minutes=60),
            )
            db.session.add(reset_token)
            db.session.flush()

            base_url = current_app.config.get("APP_BASE_URL", "").rstrip("/")
            if base_url:
                reset_url = f"{base_url}{url_for('auth.reset_password', token=raw_token)}"
            else:
                reset_url = url_for("auth.reset_password", token=raw_token, _external=True)

            try:
                send_password_reset_email(user, reset_url)
                db.session.commit()
            except Exception:
                current_app.logger.exception("Password reset email could not be sent.")
                db.session.rollback()

        flash("If an account exists for that email, a password reset link has been sent.", "info")
        return redirect(url_for("auth.forgot_password"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    reset_token = PasswordResetToken.query.filter_by(token_hash=token_hash).first()

    if not reset_token or not reset_token.is_valid or not reset_token.user.is_active:
        flash("That password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        else:
            reset_token.user.set_password(password)
            reset_token.used_at = datetime.utcnow()
            db.session.commit()
            flash("Your password has been reset. You can now log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("pages.home"))
