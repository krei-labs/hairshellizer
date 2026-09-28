# HairShellizer E-Commerce Website

> **Where Shell Protects, Hair Grows**

A Flask-based e-commerce website for HairShellizer, a 250g organic powdered fertilizer made from
crushed eggshells and natural human hair. Built with Flask + PostgreSQL (Neon) + ImageKit, deployed
on Vercel — no paid services required.

---

## 1. Project Overview

Customers can browse the HairShellizer product, add it to cart, check out with Cash on Delivery,
Cash on Pickup, or manually-verified Online QR Payment, track their orders, and chat with the seller.
The seller/admin manages products, categories, orders, payments, customers, and chats from `/admin`.

## 2. Features

- Product browsing, search, category filter, product detail page
- Cart with quantity updates and stock validation
- Checkout with COD / COP / Online QR payment (manual verification, no payment gateway)
- Order history and order status tracking
- Internal chat system: 24-hour expiring **inquiries** and permanent **order chats**
- Admin dashboard: products, categories, orders, payment verification, customers, chats, settings
- ImageKit-hosted product images (no binary files in Postgres, no reliance on Vercel's filesystem)
- Role-based authentication (customer / admin) with hashed passwords

## 3. Technology Stack

**Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons, Jinja2
**Backend:** Python 3, Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug
**Database:** PostgreSQL (Neon), SQLAlchemy ORM, Flask-Migrate/Alembic
**Hosting:** GitHub + Vercel
**Image Storage:** ImageKit

## 4. Project Structure

```
hairshellizer/
├── app.py                 # App factory, CLI commands, error handlers
├── config.py               # Configuration from environment variables
├── models.py                # SQLAlchemy models
├── extensions.py            # db, login_manager, migrate instances
├── utils.py                 # admin_required decorator, ImageKit upload helper
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
├── routes/                  # auth, shop, cart, checkout, orders, chat, admin, pages
├── templates/                # Jinja2 templates, organized by feature
└── static/
    ├── css/style.css
    ├── js/main.js
    └── assets/{logo,products,team,branding,other}/   # actual business images go here
```

## 5. Installing Python

Install Python 3.11+ from https://www.python.org/downloads/. Verify with `python --version`
(or `python3 --version` on macOS/Linux).

## 6. Creating a Virtual Environment

```bash
python -m venv .venv
```

Activate it:

- Windows: `.venv\Scripts\activate`
- macOS/Linux: `source .venv/bin/activate`

## 7. Installing Dependencies

```bash
pip install -r requirements.txt
```

## 8. PostgreSQL / Neon Setup

1. Create a free account at https://neon.tech.
2. Create a new project (this becomes your database).
3. Copy the connection string shown (it looks like `postgresql://user:password@host/dbname?sslmode=require`).

## 9. Database Configuration

1. Copy `.env.example` to `.env`.
2. Paste your Neon connection string into `DATABASE_URL`.
3. Set `SECRET_KEY` to any long random string (e.g. generate one with
   `python -c "import secrets; print(secrets.token_hex(32))"`).

Never commit `.env` — it is already listed in `.gitignore`.

## 10. Database Migration

```bash
flask db init
flask db migrate -m "Initial database"
flask db upgrade
```

This creates every table in `models.py` inside your Neon database. Run `flask db migrate` again any
time you change a model, followed by `flask db upgrade`.

## 11. Creating Admin

```bash
flask create-admin
```

You'll be prompted for a name, email, and password. This creates the first seller/admin account and
an empty seller profile — no predictable default admin account is ever created automatically.

## 12. ImageKit Setup

1. Create a free account at https://imagekit.io.
2. From your dashboard, copy the **Public Key**, **Private Key**, and **URL Endpoint**.
3. Add them to `.env` as `IMAGEKIT_PUBLIC_KEY`, `IMAGEKIT_PRIVATE_KEY`, `IMAGEKIT_URL_ENDPOINT`.

Product images uploaded through `/admin/products` are sent to ImageKit; only the returned URL is
stored in PostgreSQL.

## 13. Adding Business Images

Place actual logo, team, and branding images under `static/assets/`:

```
static/assets/logo/hairshellizer-logo.png
static/assets/products/hairshellizer-product.jpg
static/assets/team/jonathan-vargas.jpg
static/assets/team/cheney-malipol.jpg
static/assets/team/vincent-varquez.jpg
static/assets/team/mathew-pabia.jpg
static/assets/team/michael-platon.jpg
```

Do **not** use Windows temp paths (e.g. `C:/Users/ADMIN/AppData/Local/Temp/...`) — those only exist on
the computer that created them and will break as soon as the site is deployed. Use the project-relative
paths above instead.

## 14. Adding Product Images

Use the admin product form (`/admin/products/new`) to upload product photos — these go to ImageKit
automatically. Static business assets (logo, team photos) can stay under `static/assets/` since they
ship with the source code and don't change often.

## 15. Local Development

```bash
flask run
```

or

```bash
python app.py
```

Then open http://127.0.0.1:5000.

## 16. Testing Customer Account

Register a new account at `/auth/register`, browse `/shop`, add a product to your cart, and check out.

## 17. Testing Seller/Admin Account

Log in with the account created via `flask create-admin`, then visit `/admin`.

## 18. Testing COD

At checkout, choose **Cash on Delivery**. The order is created with `payment_status = UNPAID` and an
order chat is created automatically.

## 19. Testing COP

Choose **Cash on Pickup**. Same as COD, but the fulfillment type is pickup and the order status may
start as `READY_FOR_PICKUP`.

## 20. Testing Online QR Payment

Choose **Online Payment**, enter any transaction/reference number, and place the order. The payment
status becomes `PENDING_VERIFICATION` until the admin verifies or rejects it.

## 21. Testing Payment Verification

As admin, go to `/admin/payments` and click **Verify** or **Reject** (with a reason) on a pending
payment.

## 22. Testing Chat

Click **Chat Seller** on any product page (creates an INQUIRY conversation) or open the chat from an
order's detail page (an ORDER conversation, created automatically at checkout).

## 23. Testing 24-Hour Inquiry Expiration

Don't wait 24 real hours — instead, open a Python shell (`flask shell`) and manually backdate a
conversation's `expires_at` to the past, then reload its chat page or `/chat` to see it flip to
`EXPIRED`. Order conversations never expire this way.

## 24. Git Configuration

```bash
git init
git add .
git commit -m "Initial HairShellizer e-commerce website"
```

## 25. GitHub Upload

Create a repository (e.g. `hairshellizer-ecommerce`) on GitHub, then:

```bash
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git branch -M main
git push -u origin main
```

`.env` is git-ignored and will never be pushed.

## 26. Vercel Deployment

1. Go to https://vercel.com and sign in with GitHub.
2. Click **New Project** and import your `hairshellizer-ecommerce` repository.
3. Vercel detects `vercel.json` and builds the Flask app using the Python runtime.

## 27. Vercel Environment Variables

In your Vercel project settings → **Environment Variables**, add:

```
DATABASE_URL
SECRET_KEY
IMAGEKIT_PRIVATE_KEY
IMAGEKIT_PUBLIC_KEY
IMAGEKIT_URL_ENDPOINT
```

(and optionally `SELLER_FACEBOOK_URL`, `SELLER_EMAIL`, `SELLER_PHONE`).

## 28. Production Database

Use the same Neon `DATABASE_URL` in production as in development, or create a separate Neon branch/
project for production. Run `flask db upgrade` against the production database before first use
(e.g. from your local machine with the production `DATABASE_URL` temporarily set, or via a one-off
Vercel deployment hook).

## 29. ImageKit Production Configuration

Use the same ImageKit keys in Vercel's environment variables as in `.env` locally — ImageKit URLs
are permanent and work the same in development and production.

## 30. Troubleshooting

- **"relation does not exist" errors** → you forgot to run `flask db upgrade` against that database.
- **Images not loading after deploy** → confirm you used ImageKit URLs or `static/assets/` paths, not
  a local Windows path.
- **500 error on Vercel with no detail** → check the Vercel deployment's **Logs** tab.
- **Database connection refused** → check that `DATABASE_URL` uses `postgresql://`, not the older
  `postgres://` prefix (the app normalizes this automatically, but double-check the value is set).

## 31. Security Checklist

- [ ] `.env` is git-ignored and was never committed
- [ ] `SECRET_KEY` is a random value, not the default in `config.py`
- [ ] Database credentials are not in GitHub
- [ ] ImageKit private key is not in GitHub
- [ ] Admin routes (`/admin/*`) require login **and** the `admin` role
- [ ] Passwords are hashed with Werkzeug (never stored in plain text)
- [ ] Customers cannot view other customers' orders or conversations
- [ ] Uploaded images are validated by extension before upload
- [ ] Production uses PostgreSQL, not SQLite

## 32. Free-Tier Considerations

Neon PostgreSQL, ImageKit, and Vercel are all used within their free tiers. No payment gateway,
paid email/SMS API, or paid chat infrastructure (WebSockets/Redis) is used — chat uses simple HTTP
polling instead.

## 33. Future Improvements

Product reviews and ratings, wishlists, discount codes, sales reports, printable receipts, order
cancellation requests, email notifications, Messenger integration, multiple products/sellers,
delivery tracking, and inventory/financial reports. None of these are implemented in v1 to keep the
project simple and within free-tier limits.

---

## A Note on the Supplied Financial Figures

The business-provided 10-month projection (₱120,000 revenue, ₱6,590 expenses, ₱51,410 projected net
income) does not add up: ₱120,000 − ₱6,590 = ₱113,410, not ₱51,410. Likewise, the supplied 46.04%
markup does not match ₱75.00 retail vs. ₱40.47 direct cost, which computes to roughly 85.32% markup
over direct cost. These original figures have been preserved as-is in this documentation rather than
silently "corrected" — if you display financial figures in the admin dashboard, label supplied
projections and system-calculated values separately until the business confirms the correct numbers.
