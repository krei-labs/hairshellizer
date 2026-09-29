from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from extensions import db
from models import User

account_bp = Blueprint("account", __name__)


@account_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name or not email:
            flash("Name and email are required.", "danger")
            return render_template("account/profile.html")

        existing = User.query.filter(
            User.email == email,
            User.id != current_user.id,
        ).first()
        if existing:
            flash("That email address is already in use.", "danger")
            return render_template("account/profile.html")

        current_user.name = name
        current_user.email = email
        current_user.phone = phone
        current_user.address = address
        db.session.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("account.profile"))

    return render_template("account/profile.html")


@account_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Your current password is incorrect.", "danger")
        elif len(new_password) < 8:
            flash("New password must be at least 8 characters.", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "danger")
        elif current_user.check_password(new_password):
            flash("Your new password must be different from your current password.", "danger")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Your password has been changed successfully.", "success")
            return redirect(url_for("account.profile"))

    return render_template("account/change_password.html")
