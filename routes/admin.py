from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user

from extensions import db
from models import (
    Product, Category, Order, Payment, User, Conversation, Message,
    SellerProfile, ORDER_STATUSES,
)
from utils import (
    admin_required, main_admin_required, allowed_image, upload_to_imagekit,
    delete_from_imagekit,
)

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
@login_required
@admin_required
def _guard():
    """Runs before every route in this blueprint. login_required first,
    then admin_required, so an anonymous visitor is sent to login rather
    than getting a 403 with no explanation."""
    pass


# --------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------- #

@admin_bp.route("/")
def dashboard():
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status="PENDING").count()
    total_sales = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)) \
        .filter(Order.status != "CANCELLED").scalar()
    total_products = Product.query.count()
    low_stock = Product.query.filter(Product.stock <= 5, Product.is_active.is_(True)).count()
    total_customers = User.query.filter_by(role="customer").count()
    pending_payments = Payment.query.filter_by(payment_status="PENDING_VERIFICATION").count()
    active_inquiries = Conversation.query.filter_by(conversation_type="INQUIRY", status="ACTIVE").count()
    order_chats = Conversation.query.filter_by(conversation_type="ORDER").count()

    return render_template(
        "admin/dashboard.html",
        total_orders=total_orders, pending_orders=pending_orders, total_sales=total_sales,
        total_products=total_products, low_stock=low_stock, total_customers=total_customers,
        pending_payments=pending_payments, active_inquiries=active_inquiries, order_chats=order_chats,
    )


# --------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------- #

@admin_bp.route("/products")
def products():
    items = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=items)


@admin_bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        return _save_product(None, categories)
    return render_template("admin/product_form.html", product=None, categories=categories)


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        return _save_product(product, categories)
    return render_template("admin/product_form.html", product=product, categories=categories)


def _save_product(product, categories):
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price = request.form.get("price", "0")
    stock = request.form.get("stock", "0")
    category_id = request.form.get("category_id", type=int)
    is_featured = bool(request.form.get("is_featured"))
    is_active = bool(request.form.get("is_active"))
    image_file = request.files.get("image_file")

    if not name:
        flash("Product name is required.", "danger")
        return render_template("admin/product_form.html", product=product, categories=categories)

    try:
        price = Decimal(price)
        stock = int(stock)
    except Exception:
        flash("Price and stock must be valid numbers.", "danger")
        return render_template("admin/product_form.html", product=product, categories=categories)

    image_url = product.image_url if product else None
    if image_file and image_file.filename:
        if not allowed_image(image_file.filename):
            flash("Only JPG, JPEG, PNG and WEBP images are allowed.", "danger")
            return render_template("admin/product_form.html", product=product, categories=categories)
        try:
            image_url = upload_to_imagekit(image_file)
        except Exception as exc:
            flash(f"Image upload failed: {exc}", "danger")
            return render_template("admin/product_form.html", product=product, categories=categories)

    if product is None:
        seller_owner = User.query.filter_by(role="admin").order_by(User.id.asc()).first()
        product = Product(seller_id=seller_owner.id if seller_owner else current_user.id)
        db.session.add(product)

    product.name = name
    product.description = description
    product.price = price
    product.stock = stock
    product.category_id = category_id
    product.is_featured = is_featured
    product.is_active = is_active
    if image_url:
        product.image_url = image_url

    db.session.commit()
    flash(f"Product '{name}' saved.", "success")
    return redirect(url_for("admin.products"))


@admin_bp.route("/products/<int:product_id>/toggle-status", methods=["POST"])
def product_toggle_status(product_id):
    """Toggle product visibility without deleting the database record."""
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    state = "activated" if product.is_active else "deactivated"
    flash(f"Product '{product.name}' {state}.", "success" if product.is_active else "info")
    return redirect(url_for("admin.products"))


# Backward-compatible endpoint for older links/forms. Deactivation is a soft
# action so historical order items remain intact.
@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
def product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    if product.is_active:
        product.is_active = False
        db.session.commit()
        flash(f"Product '{product.name}' deactivated.", "info")
    else:
        flash(f"Product '{product.name}' is already inactive.", "info")
    return redirect(url_for("admin.products"))


# --------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------- #

@admin_bp.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if name and not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name, description=description))
            db.session.commit()
            flash(f"Category '{name}' created.", "success")
        else:
            flash("Category name is required and must be unique.", "danger")
        return redirect(url_for("admin.categories"))

    items = Category.query.order_by(Category.name).all()
    return render_template("admin/categories.html", categories=items)


@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
def category_delete(category_id):
    category = Category.query.get_or_404(category_id)
    if category.products:
        flash("Cannot delete a category that still has products.", "danger")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Category deleted.", "info")
    return redirect(url_for("admin.categories"))


# --------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------- #

@admin_bp.route("/orders")
def orders():
    status_filter = request.args.get("status", "")
    query = Order.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    items = query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=items, statuses=ORDER_STATUSES, status_filter=status_filter)


@admin_bp.route("/orders/<int:order_id>")
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template("admin/order_detail.html", order=order, statuses=ORDER_STATUSES)


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
def order_update_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status")
    if new_status not in ORDER_STATUSES:
        flash("Invalid order status.", "danger")
        return redirect(url_for("admin.order_detail", order_id=order.id))

    previous_status = order.status

    if new_status == "CANCELLED" and previous_status != "CANCELLED":
        # Restore inventory exactly once when an order is cancelled.
        for item in order.items:
            if item.product_id:
                product = Product.query.get(item.product_id)
                if product:
                    product.stock += item.quantity

    elif previous_status == "CANCELLED" and new_status != "CANCELLED":
        # Re-opening a cancelled order consumes the reserved stock again.
        # Do not allow an order to become active if the stock is no longer
        # available, otherwise the dashboard and shop inventory diverge.
        for item in order.items:
            if item.product_id:
                product = Product.query.get(item.product_id)
                if product and product.stock < item.quantity:
                    flash(
                        f"Cannot reopen Order #{order.id}: only {product.stock} unit(s) "
                        f"of {product.name} remain available.",
                        "danger",
                    )
                    return redirect(url_for("admin.order_detail", order_id=order.id))
        for item in order.items:
            if item.product_id:
                product = Product.query.get(item.product_id)
                if product:
                    product.stock -= item.quantity

    order.status = new_status
    db.session.commit()
    flash(f"Order #{order.id} status updated to {new_status}.", "success")
    return redirect(url_for("admin.order_detail", order_id=order.id))


# --------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------- #

@admin_bp.route("/payments")
def payments():
    pending = Payment.query.filter_by(payment_status="PENDING_VERIFICATION").order_by(Payment.created_at.desc()).all()
    others = Payment.query.filter(Payment.payment_status != "PENDING_VERIFICATION") \
        .order_by(Payment.created_at.desc()).limit(50).all()
    return render_template("admin/payments.html", pending=pending, others=others)


@admin_bp.route("/payments/<int:payment_id>/verify", methods=["POST"])
def payment_verify(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    payment.payment_status = "PAID"
    payment.verified_by = current_user.id
    payment.verified_at = datetime.utcnow()
    db.session.commit()
    flash(f"Payment for Order #{payment.order_id} marked as PAID.", "success")
    return redirect(url_for("admin.payments"))


@admin_bp.route("/payments/<int:payment_id>/reject", methods=["POST"])
def payment_reject(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    reason = request.form.get("rejection_reason", "").strip()
    if not reason:
        flash("Please provide a rejection reason.", "danger")
        return redirect(url_for("admin.payments"))
    payment.payment_status = "REJECTED"
    payment.rejection_reason = reason
    payment.verified_by = current_user.id
    payment.verified_at = datetime.utcnow()
    db.session.commit()
    flash(f"Payment for Order #{payment.order_id} rejected.", "info")
    return redirect(url_for("admin.payments"))


# --------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------- #

@admin_bp.route("/customers")
def customers():
    items = User.query.filter_by(role="customer").order_by(User.created_at.desc()).all()
    return render_template("admin/customers.html", customers=items)


@admin_bp.route("/customers/<int:user_id>/toggle-status", methods=["POST"])
def customer_toggle_status(user_id):
    customer = User.query.filter_by(id=user_id, role="customer").first_or_404()
    customer.is_active = not customer.is_active
    db.session.commit()
    state = "activated" if customer.is_active else "deactivated"
    flash(f"Customer account {state}.", "success" if customer.is_active else "info")
    return redirect(url_for("admin.customers"))


# --------------------------------------------------------------------- #
# Staff / moderators (main admin only)
# --------------------------------------------------------------------- #

@admin_bp.route("/staff")
@main_admin_required
def staff():
    items = User.query.filter(User.role == "moderator").order_by(User.created_at.desc()).all()
    return render_template("admin/staff.html", staff_members=items)


@admin_bp.route("/staff/new", methods=["GET", "POST"])
@main_admin_required
def staff_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Name, email and password are required.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
        else:
            member = User(
                name=name, email=email, phone=phone, address=address,
                role="moderator", is_active=True,
            )
            member.set_password(password)
            db.session.add(member)
            db.session.commit()
            flash(f"Moderator account for {email} was created.", "success")
            return redirect(url_for("admin.staff"))

    return render_template("admin/staff_form.html", member=None)


@admin_bp.route("/staff/<int:user_id>/edit", methods=["GET", "POST"])
@main_admin_required
def staff_edit(user_id):
    member = User.query.filter_by(id=user_id, role="moderator").first_or_404()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        existing = User.query.filter(User.email == email, User.id != member.id).first()
        if not name or not email:
            flash("Name and email are required.", "danger")
        elif existing:
            flash("That email address is already in use.", "danger")
        elif password and len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif password and password != confirm:
            flash("Passwords do not match.", "danger")
        else:
            member.name = name
            member.email = email
            member.phone = phone
            member.address = address
            if password:
                member.set_password(password)
            db.session.commit()
            flash(f"Moderator account for {email} was updated.", "success")
            return redirect(url_for("admin.staff"))

    return render_template("admin/staff_form.html", member=member)


@admin_bp.route("/staff/<int:user_id>/toggle-status", methods=["POST"])
@main_admin_required
def staff_toggle_status(user_id):
    member = User.query.filter_by(id=user_id, role="moderator").first_or_404()
    member.is_active = not member.is_active
    db.session.commit()
    state = "activated" if member.is_active else "deactivated"
    flash(f"Moderator account {state}.", "success" if member.is_active else "info")
    return redirect(url_for("admin.staff"))


# --------------------------------------------------------------------- #
# Chats
# --------------------------------------------------------------------- #

@admin_bp.route("/chats")
def chats():
    # There is one seller/store account, so every staff member should see the
    # same buyer conversations regardless of which staff account is logged in.
    convos = Conversation.query.order_by(Conversation.last_message_at.desc()).all()
    for c in convos:
        c.refresh_expiration()
    inquiries = [c for c in convos if c.conversation_type == "INQUIRY"]
    order_chats = [c for c in convos if c.conversation_type == "ORDER"]
    return render_template("admin/chats.html", inquiries=inquiries, order_chats=order_chats)


# --------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------- #

@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    # There is one seller/store profile. Moderators can manage it, but it
    # remains attached to the main admin rather than creating duplicates.
    seller_owner = User.query.filter_by(role="admin").order_by(User.id.asc()).first()
    owner_id = seller_owner.id if seller_owner else current_user.id
    profile = SellerProfile.query.filter_by(user_id=owner_id).first()
    if not profile:
        profile = SellerProfile(user_id=owner_id)
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        profile.store_name = request.form.get("store_name", profile.store_name)
        profile.description = request.form.get("description", profile.description)
        profile.address = request.form.get("address", profile.address)
        profile.phone = request.form.get("phone", profile.phone)
        profile.email = request.form.get("email", profile.email)
        profile.facebook_url = request.form.get("facebook_url", profile.facebook_url)

        qr_file = request.files.get("qr_image")
        if qr_file and qr_file.filename:
            if not allowed_image(qr_file.filename):
                flash("QR code must be a JPG, JPEG, PNG or WEBP image.", "danger")
                return render_template("admin/settings.html", profile=profile)

            old_qr_file_id = profile.qr_image_file_id
            new_qr = None
            try:
                new_qr = upload_to_imagekit(
                    qr_file,
                    folder="/hairshellizer/payment-qr/",
                    return_metadata=True,
                )
                profile.qr_image_url = new_qr["url"]
                profile.qr_image_file_id = new_qr["file_id"]
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                if new_qr and new_qr.get("file_id"):
                    try:
                        delete_from_imagekit(new_qr["file_id"])
                    except Exception:
                        current_app.logger.exception("Failed to clean up a newly uploaded QR after DB failure.")
                flash(f"QR code upload failed: {exc}", "danger")
                return render_template("admin/settings.html", profile=profile)

            if old_qr_file_id:
                try:
                    delete_from_imagekit(old_qr_file_id)
                except Exception:
                    current_app.logger.exception("Failed to delete the previous QR from ImageKit.")
                    flash("The new QR was saved, but the previous ImageKit QR could not be deleted automatically.", "warning")

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            flash(f"Seller settings could not be saved: {exc}", "danger")
            return render_template("admin/settings.html", profile=profile)

        flash("Seller settings updated.", "success")
        return redirect(url_for("admin.settings"))

    return render_template("admin/settings.html", profile=profile)


@admin_bp.route("/settings/qr/delete", methods=["POST"])
def delete_qr():
    """Remove the configured payment QR from the store and ImageKit when possible."""
    seller_owner = User.query.filter_by(role="admin").order_by(User.id.asc()).first()
    owner_id = seller_owner.id if seller_owner else current_user.id
    profile = SellerProfile.query.filter_by(user_id=owner_id).first()

    if not profile:
        flash("Seller profile not found.", "danger")
        return redirect(url_for("admin.settings"))

    if not profile.qr_image_url:
        flash("There is no payment QR code to remove.", "info")
        return redirect(url_for("admin.settings"))

    old_qr_file_id = profile.qr_image_file_id
    profile.qr_image_url = None
    profile.qr_image_file_id = None
    db.session.commit()

    if old_qr_file_id:
        try:
            delete_from_imagekit(old_qr_file_id)
        except Exception:
            current_app.logger.exception("Failed to delete the QR from ImageKit.")
            flash("The QR was removed from the website, but its ImageKit file could not be deleted automatically.", "warning")
            return redirect(url_for("admin.settings"))

    flash("Current payment QR code removed. You can upload a new one.", "success")
    return redirect(url_for("admin.settings"))
