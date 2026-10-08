import os
import click
from decimal import Decimal
from flask import Flask, render_template, redirect, url_for, flash, request
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import db, login_manager, migrate
from models import User, SellerProfile, Category, Product
from utils import safe_redirect_target


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Vercel terminates TLS in front of the function. Trust its
    # X-Forwarded-Proto so url_for(..., _external=True) (password-reset links)
    # is generated as https:// instead of http://.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

    if os.environ.get("VERCEL") and app.config["SECRET_KEY"] == "dev-secret-key-change-me":
        app.logger.warning(
            "SECRET_KEY is not set: sessions are signed with a public default key. "
            "Add SECRET_KEY to your Vercel environment variables."
        )

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
    from routes.account import account_bp
    from routes.pages import pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(shop_bp, url_prefix="/shop")
    app.register_blueprint(cart_bp, url_prefix="/cart")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(orders_bp, url_prefix="/orders")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(account_bp, url_prefix="/account")

    # --- Login manager ----------------------------------------------------
    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None
        # A disabled account must lose access immediately, not only at the
        # next login. Without this check a deactivated moderator keeps
        # their admin session until the cookie expires.
        if user is None or not user.is_active:
            return None
        return user

    # --- Context processor: seller info available in every template -------
    @app.context_processor
    def inject_seller_info():
        seller = None
        try:
            seller = (SellerProfile.query.join(User, SellerProfile.user_id == User.id)
                      .filter(User.role == "admin")
                      .order_by(SellerProfile.id.asc()).first())
        except Exception:
            # If the database is unreachable or a migration has not been
            # applied yet, fall back to the .env values instead of crashing
            # every page (including the 404/500 pages) with a second error.
            db.session.rollback()
            app.logger.exception("Could not load the seller profile; using config fallbacks.")
        return {
            "seller": seller,
            "seller_facebook_url": (seller.facebook_url if seller and seller.facebook_url else app.config["SELLER_FACEBOOK_URL"]),
            "seller_email": (seller.email if seller and seller.email else app.config["SELLER_EMAIL"]),
            "seller_phone": (seller.phone if seller and seller.phone else app.config["SELLER_PHONE"]),
        }

    # --- Error handlers -----------------------------------------------------
    def _render_error(template, status, fallback_text):
        """Render an error page, but never let the error page itself crash."""
        try:
            return render_template(template), status
        except Exception:
            db.session.rollback()
            app.logger.exception("Could not render %s", template)
            return fallback_text, status

    @app.errorhandler(404)
    def not_found(e):
        return _render_error("404.html", 404, "404 - Page not found")

    @app.errorhandler(413)
    def too_large(e):
        flash("That file is too large. Please upload an image smaller than 4 MB.", "danger")
        return redirect(safe_redirect_target(request.referrer, url_for("pages.home")))

    @app.errorhandler(500)
    def server_error(e):
        # A failed query leaves the SQLAlchemy session unusable; reset it so
        # rendering the error page (which queries the DB) can succeed.
        db.session.rollback()
        return _render_error("500.html", 500, "500 - Something went wrong")

    # --- CLI commands ---------------------------------------------------
    @app.cli.command("create-admin")
    @click.option("--name", prompt="Name")
    @click.option("--email", prompt="Email")
    @click.option("--password", prompt="Password", hide_input=True, confirmation_prompt=True)
    def create_admin(name, email, password):
        """Create the first seller/admin account.
        Usage: flask create-admin
        """
        # Login lower-cases the typed email, so store it lower-cased too.
        # Otherwise "Admin@Gmail.com" could never log in.
        name = name.strip()
        email = email.strip().lower()
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
