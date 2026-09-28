import os
import click
from decimal import Decimal
from flask import Flask, render_template

from config import Config
from extensions import db, login_manager, migrate
from models import User, SellerProfile, Category, Product


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # --- Blueprints -----------------------------------------------------
    from routes.auth import auth_bp
    from routes.shop import shop_bp
    from routes.cart import cart_bp
    from routes.checkout import checkout_bp
    from routes.orders import orders_bp
    from routes.chat import chat_bp
    from routes.admin import admin_bp
    from routes.pages import pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(shop_bp, url_prefix="/shop")
    app.register_blueprint(cart_bp, url_prefix="/cart")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(orders_bp, url_prefix="/orders")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # --- Login manager ----------------------------------------------------
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Context processor: seller info available in every template -------
    @app.context_processor
    def inject_seller_info():
        seller = (SellerProfile.query.join(User, SellerProfile.user_id == User.id)
                  .filter(User.role == "admin")
                  .order_by(SellerProfile.id.asc()).first())
        return {
            "seller": seller,
            "seller_facebook_url": (seller.facebook_url if seller else app.config["SELLER_FACEBOOK_URL"]),
            "seller_email": (seller.email if seller else app.config["SELLER_EMAIL"]),
            "seller_phone": (seller.phone if seller else app.config["SELLER_PHONE"]),
        }

    # --- Error handlers -----------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    # --- CLI commands ---------------------------------------------------
    @app.cli.command("create-admin")
    @click.option("--name", prompt="Name")
    @click.option("--email", prompt="Email")
    @click.option("--password", prompt="Password", hide_input=True, confirmation_prompt=True)
    def create_admin(name, email, password):
        """Create the first seller/admin account.
        Usage: flask create-admin
        """
        if User.query.filter_by(email=email).first():
            click.echo("A user with that email already exists.")
            return
        if len(password) < 8:
            click.echo("Password must be at least 8 characters.")
            return
        admin = User(name=name, email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        if not SellerProfile.query.filter_by(user_id=admin.id).first():
            db.session.add(SellerProfile(user_id=admin.id))
            db.session.commit()

        click.echo(f"Admin account created for {email}.")

    @app.cli.command("seed-data")
    def seed_data():
        """Seed the initial category and the HairShellizer product.
        Usage: flask seed-data
        """
        category = Category.query.filter_by(name="Organic Fertilizer").first()
        if not category:
            category = Category(
                name="Organic Fertilizer",
                description="Natural, organic fertilizers made from repurposed biodegradable materials.",
            )
            db.session.add(category)
            db.session.commit()

        admin = User.query.filter_by(role="admin").first()
        if not admin:
            click.echo("No admin account found yet. Run `flask create-admin` first.")
            return

        product = Product.query.filter_by(name="HairShellizer").first()
        if not product:
            product = Product(
                seller_id=admin.id,
                category_id=category.id,
                name="HairShellizer",
                description=(
                    "HairShellizer derives its name from its two raw organic materials: "
                    "natural hair and eggshells. By converting these biodegradable wastes "
                    "into fertilizer rich in essential nutrients, HairShellizer provides a "
                    "dual benefit: promoting plant vitality and reducing domestic waste. "
                    "The product is designed for decorative gardeners looking for a "
                    "natural fertilizer option."
                ),
                price=Decimal("75.00"),
                stock=20,
                image_url="/static/assets/products/hairshellizer-product.jpg",
                is_featured=True,
                is_active=True,
            )
            db.session.add(product)
            db.session.commit()

        if not SellerProfile.query.filter_by(user_id=admin.id).first():
            db.session.add(SellerProfile(user_id=admin.id))
            db.session.commit()

        click.echo("Seed data created: 1 category, 1 product, seller profile.")

    return app


# Vercel's Python runtime looks for a top-level WSGI variable called `app`.
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
