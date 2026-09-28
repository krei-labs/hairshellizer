from flask import Blueprint, render_template

from models import Product

pages_bp = Blueprint("pages", __name__)

# Team data is static content (names/roles/responsibilities supplied by the
# business) rather than database rows, since it changes rarely and isn't
# part of the e-commerce data model.
TEAM_MEMBERS = [
    {
        "name": "Jonathan C. Vargas",
        "role": "Partner-in-charge with Overall Operations",
        "photo": "team/jonathan-vargas.jpg",
        "bio": (
            "As Partner-in-charge of Overall Operations, Jonathan coordinates tasks across "
            "departments and leads the team's daily activity checklists and review meetings. "
            "He oversees day-to-day business operations, handles operational issues, and "
            "supports continuous improvement across the team."
        ),
    },

    {
        "name": "Cheney R. Malipol",
        "role": "Partner-in-charge with Finances & Inventory Control",
        "photo": "team/cheney-malipol.jpg",
        "bio": (
            "Cheney manages HairShellizer's finances and inventory, handling financial "
            "reporting, budgeting, and expense tracking. She also maintains supplier "
            "agreements and inventory levels to help minimize material waste."
        ),
    },

    {
        "name": "Vincent B. Varquez",
        "role": "Partner-in-charge with Quality Control & Sales Director",
        "photo": "team/vincent-varquez.jpg",
        "bio": (
            "Vincent oversees final product quality control, making sure every batch of "
            "HairShellizer meets the team's standards. As Sales Director, he also manages "
            "sales opportunities and directs the team's sales strategies."
        ),
    },

    {
        "name": "Michael Jude D. Platon",
        "role": "Partner-in-charge with Production & Sales",
        "photo": "team/michael-platon.jpg",
        "bio": (
            "Michael works alongside the production team to manage day-to-day production "
            "tasks, maintain quality standards, and keep output on schedule. He also "
            "handles customer transactions on the sales side."
        ),
    },

    {
        "name": "Mathew Genesis E. Pabia",
        "role": "Partner-in-charge with Production & Sales",
        "photo": "team/mathew-pabia.jpg",
        "bio": (
            "Mathew supervises equipment operations, production scheduling, and raw "
            "material intake to keep production running smoothly. He also handles direct "
            "selling to help bring HairShellizer from production to customers."
        ),
    },
]

PROCESS_STEPS = [
    "Sun-drying eggshells", "Cutting hair", "Grinding and pulverizing eggshells and hair",
    "Heat treating", "Sieving", "Proportioning", "Uniform mixing", "Packaging and sealing",
]


@pages_bp.route("/")
def home():
    featured = Product.query.filter_by(is_active=True, is_featured=True).limit(4).all()
    return render_template("index.html", featured_products=featured)


@pages_bp.route("/about")
def about():
    return render_template("about/about.html")


@pages_bp.route("/team")
def team():
    return render_template("about/team.html", team=TEAM_MEMBERS)


@pages_bp.route("/how-its-made")
def process():
    return render_template("about/process.html", steps=PROCESS_STEPS)


@pages_bp.route("/sustainability")
def sustainability():
    return render_template("about/sustainability.html")


@pages_bp.route("/contact")
def contact():
    return render_template("contact.html")


@pages_bp.route("/privacy-policy")
def privacy():
    return render_template("privacy.html")


@pages_bp.route("/terms")
def terms():
    return render_template("terms.html")
