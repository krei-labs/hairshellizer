from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import CartItem, Order, OrderItem, Payment, Conversation, Product, User, SellerProfile

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
    all_items = CartItem.query.filter_by(user_id=current_user.id).all()
    raw_selected = request.args.getlist("selected_item_ids") if request.method == "GET" else request.form.getlist("selected_item_ids")
    selected_ids = {int(value) for value in raw_selected if str(value).isdigit()}

    if not all_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart.view_cart"))

    # If no selection was supplied, preserve the old behavior for direct checkout
    # links: all current cart items are selected. The cart page explicitly sends
    # selected_item_ids so buyers can check out only chosen items.
    items = [item for item in all_items if item.id in selected_ids] if selected_ids else all_items
    if not items:
        flash("Please select at least one cart item to check out.", "warning")
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
            return render_template("checkout/checkout.html", items=items, total=total, seller=seller, selected_item_ids=[item.id for item in items])

        if fulfillment_type not in ("delivery", "pickup"):
            flash("Please choose delivery or pickup.", "danger")
            return render_template("checkout/checkout.html", items=items, total=total, seller=seller, selected_item_ids=[item.id for item in items])

        if fulfillment_type == "delivery" and not address:
            flash("Please provide a delivery address.", "danger")
            return render_template("checkout/checkout.html", items=items, total=total, seller=seller, selected_item_ids=[item.id for item in items])

        if payment_method not in ("COD", "COP", "ONLINE"):
            flash("Please choose a valid payment method.", "danger")
            return render_template("checkout/checkout.html", items=items, total=total, seller=seller, selected_item_ids=[item.id for item in items])

        if payment_method == "ONLINE":
            if not seller or not seller.qr_image_url:
                flash("Online payment is currently unavailable because the seller has not configured a payment QR. Please choose another payment method or contact the seller.", "danger")
                return render_template("checkout/checkout.html", items=items, total=total, seller=seller, selected_item_ids=[item.id for item in items])
            if not reference_number:
                flash("Please enter your transaction/reference number.", "danger")
                return render_template("checkout/checkout.html", items=items, total=total, seller=seller, selected_item_ids=[item.id for item in items])

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

        try:
            # Reserve stock with one atomic UPDATE per line. The WHERE clause
            # only matches while enough stock is left, so two buyers checking
            # out at the same moment can never both take the last unit (the old
            # read-then-subtract approach could oversell).
            for item in items:
                reserved = (
                    Product.query
                    .filter(
                        Product.id == item.product_id,
                        Product.is_active.is_(True),
                        Product.stock >= item.quantity,
                    )
                    .update({Product.stock: Product.stock - item.quantity}, synchronize_session=False)
                )
                if not reserved:
                    db.session.rollback()
                    flash("One of the items just sold out or changed. Please review your cart.", "danger")
                    return redirect(url_for("cart.view_cart"))

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
                    product_id=item.product_id,
                    product_name_snapshot=item.product.name,
                    price_snapshot=item.product.price,
                    quantity=item.quantity,
                    subtotal=item.subtotal(),
                ))
                db.session.delete(item)

            payment_status = "PENDING_VERIFICATION" if payment_method == "ONLINE" else "UNPAID"
            db.session.add(Payment(
                order_id=order.id,
                payment_method=payment_method,
                payment_status=payment_status,
                reference_number=reference_number or None,
                amount=total,
                payment_date=datetime.utcnow() if payment_method == "ONLINE" else None,
            ))

            # Every order gets its own permanent order conversation. It is part
            # of the same transaction, so an order can never exist without its
            # chat (before, a failure between two commits could leave one).
            Conversation.new_order_conversation(current_user.id, seller_id, order.id, commit=False)

            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("We could not place your order. Nothing was charged - please try again.", "danger")
            return redirect(url_for("cart.view_cart"))

        flash("Your order has been placed! You can track it and chat with the seller from My Orders.", "success")
        return redirect(url_for("orders.order_detail", order_id=order.id))

    return render_template("checkout/checkout.html", items=items, total=total, seller=seller, selected_item_ids=[item.id for item in items])
