from flask import Blueprint, render_template, request

from models import Product, Category

shop_bp = Blueprint("shop", __name__)

PER_PAGE = 12


@shop_bp.route("/")
def products():
    query = Product.query.filter_by(is_active=True)

    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    category_id = request.args.get("category", type=int)
    if category_id:
        query = query.filter_by(category_id=category_id)

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Product.is_featured.desc(), Product.created_at.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)

    categories = Category.query.order_by(Category.name).all()

    return render_template(
        "shop/products.html",
        products=pagination.items,
        pagination=pagination,
        categories=categories,
        search=search,
        selected_category=category_id,
    )


@shop_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    related = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active.is_(True),
    ).limit(4).all()
    return render_template("shop/product_detail.html", product=product, related=related)
