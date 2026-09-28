from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from models import Order

orders_bp = Blueprint("orders", __name__)


@orders_bp.route("/")
@login_required
def my_orders():
    orders = Order.query.filter_by(customer_id=current_user.id) \
        .order_by(Order.created_at.desc()).all()
    return render_template("orders/orders.html", orders=orders)


@orders_bp.route("/<int:order_id>")
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    # Customers may only view their own orders; admins may view any order.
    if order.customer_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template("orders/order_detail.html", order=order)
