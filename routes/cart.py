from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from extensions import db
from models import CartItem, Product
from utils import safe_redirect_target

cart_bp = Blueprint("cart", __name__)


@cart_bp.route("/")
@login_required
def view_cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum((item.subtotal() for item in items), start=0)
    return render_template("cart/cart.html", items=items, total=total)


@cart_bp.route("/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = request.form.get("quantity", 1, type=int) or 1
    quantity = max(1, quantity)

    if not product.is_active:
        flash("This product is not currently available.", "danger")
        return redirect(url_for("shop.products"))

    if product.stock <= 0:
        flash(f"{product.name} is out of stock.", "danger")
        return redirect(url_for("shop.product_detail", product_id=product.id))

    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    desired_qty = (item.quantity if item else 0) + quantity

    if desired_qty > product.stock:
        flash(f"Only {product.stock} unit(s) of {product.name} left in stock.", "warning")
        desired_qty = product.stock

    if item:
        item.quantity = desired_qty
    else:
        item = CartItem(user_id=current_user.id, product_id=product.id, quantity=desired_qty)
        db.session.add(item)

    db.session.commit()
    flash(f"{product.name} added to your cart.", "success")
    return redirect(safe_redirect_target(request.referrer, url_for("shop.products")))


@cart_bp.route("/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()

    # Do NOT write `type=int) or 1` here: that turns a typed 0 into 1, so the
    # "set quantity to 0 to remove" input on the cart page never worked.
    quantity = request.form.get("quantity", type=int)
    if quantity is None:
        flash("Please enter a valid quantity.", "warning")
        return redirect(url_for("cart.view_cart"))

    if quantity <= 0:
        db.session.delete(item)
        db.session.commit()
        flash("Item removed from your cart.", "info")
        return redirect(url_for("cart.view_cart"))

    if not item.product.is_active:
        name = item.product.name
        db.session.delete(item)
        db.session.commit()
        flash(f"{name} is no longer available and was removed from your cart.", "warning")
        return redirect(url_for("cart.view_cart"))

    if item.product.stock <= 0:
        name = item.product.name
        db.session.delete(item)
        db.session.commit()
        flash(f"{name} is out of stock and was removed from your cart.", "warning")
        return redirect(url_for("cart.view_cart"))

    if quantity > item.product.stock:
        flash(f"Only {item.product.stock} unit(s) available. Quantity adjusted.", "warning")
        quantity = item.product.stock

    item.quantity = quantity
    db.session.commit()
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from your cart.", "info")
    return redirect(url_for("cart.view_cart"))
