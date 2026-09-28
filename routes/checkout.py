from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from extensions import db
from models import CartItem, Order, OrderItem, Payment, Conversation, User, SellerProfile

checkout_bp = Blueprint("checkout", __name__)


def _get_seller_id():
    """v1 is single-seller: every order is attached to the first admin
    account. If there is no admin yet, fall back to None (checkout should
    not be reachable before an admin/seed exists, but this avoids a crash)."""
    admin = User.query.filter_by(role="admin").first()
    return admin.id if admin else None


@checkout_bp.route("/", methods=["GET", "POST"])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart.view_cart"))

    # Validate availability and stock for every line before doing anything else.
    for item in items:
        if not item.product.is_active:
            db.session.delete(item)
            db.session.commit()
            flash(f"{item.product.name} is no longer available and was removed from your cart.", "warning")
            return redirect(url_for("cart.view_cart"))
        if item.quantity > item.product.stock:
            flash(f"Insufficient stock for {item.product.name}.", "danger")
            return redirect(url_for("cart.view_cart"))

    total = sum((item.subtotal() for item in items), start=Decimal("0"))
    seller = (SellerProfile.query.join(User, SellerProfile.user_id == User.id)
              .filter(User.role == "admin")
              .order_by(SellerProfile.id.asc()).first())

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        fulfillment_type = request.form.get("fulfillment_type", "delivery")
        address = request.form.get("address", "").strip()
        notes = request.form.get("notes", "").strip()
        payment_method = request.form.get("payment_method", "")
        reference_number = request.form.get("reference_number", "").strip()

        if not full_name or not email or not phone:
            flash("Please fill in your full name, email and phone number.", "danger")
            return render_template("checkout/checkout.html", items=items, total=total, seller=seller)

        if fulfillment_type == "delivery" and not address:
            flash("Please provide a delivery address.", "danger")
            return render_template("checkout/checkout.html", items=items, total=total, seller=seller)

        if payment_method not in ("COD", "COP", "ONLINE"):
            flash("Please choose a valid payment method.", "danger")
            return render_template("checkout/checkout.html", items=items, total=total, seller=seller)

        if payment_method == "ONLINE":
            if not seller or not seller.qr_image_url:
                flash("Online payment is currently unavailable because the seller has not configured a payment QR. Please choose another payment method or contact the seller.", "danger")
                return render_template("checkout/checkout.html", items=items, total=total, seller=seller)
            if not reference_number:
                flash("Please enter your transaction/reference number.", "danger")
                return render_template("checkout/checkout.html", items=items, total=total, seller=seller)

        seller_id = _get_seller_id()
        if not seller_id:
            flash("The store is not fully configured yet. Please contact the seller.", "danger")
            return redirect(url_for("cart.view_cart"))

        # Re-validate stock right before committing (defends against a race
        # between page load and submit) and decrease it inside one order.
        for item in items:
            if not item.product.is_active:
                flash(f"{item.product.name} is no longer available. Please return to your cart.", "danger")
                return redirect(url_for("cart.view_cart"))
            if item.quantity > item.product.stock:
                flash(f"Insufficient stock for {item.product.name}.", "danger")
                return redirect(url_for("cart.view_cart"))

        order_status = "READY_FOR_PICKUP" if (payment_method == "COP" and fulfillment_type == "pickup") else "PENDING"

        order = Order(
            customer_id=current_user.id,
            seller_id=seller_id,
            total_amount=total,
            status=order_status,
            payment_method=payment_method,
            fulfillment_type=fulfillment_type,
            shipping_address=address if fulfillment_type == "delivery" else None,
            full_name=full_name,
            phone=phone,
            email=email,
            notes=notes,
        )
        db.session.add(order)
        db.session.flush()  # get order.id before commit

        for item in items:
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=item.product.id,
                product_name_snapshot=item.product.name,
                price_snapshot=item.product.price,
                quantity=item.quantity,
                subtotal=item.subtotal(),
            ))
            item.product.stock -= item.quantity
            db.session.delete(item)

        payment_status = "UNPAID"
        if payment_method == "ONLINE":
            payment_status = "PENDING_VERIFICATION"

        payment = Payment(
            order_id=order.id,
            payment_method=payment_method,
            payment_status=payment_status,
            reference_number=reference_number or None,
            amount=total,
            payment_date=datetime.utcnow() if payment_method == "ONLINE" else None,
        )
        db.session.add(payment)

        db.session.commit()

        # Every order gets its own permanent order conversation.
        Conversation.new_order_conversation(current_user.id, seller_id, order.id)

        flash("Your order has been placed! You can track it and chat with the seller from My Orders.", "success")
        return redirect(url_for("orders.order_detail", order_id=order.id))

    return render_template("checkout/checkout.html", items=items, total=total, seller=seller)
