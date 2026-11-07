import os
import sqlite3
import secrets
from functools import wraps
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, flash, render_template_string, abort
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "shop.db"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-production")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
            category TEXT NOT NULL,
            image_url TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            UNIQUE(user_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Placed',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id),
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        );
        """)
        count = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            products = [
                ("Wireless Headphones", "Comfortable over-ear headphones with clear sound.", 1499, 25, "Electronics", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e"),
                ("Smart Watch", "Fitness tracking, notifications and everyday style.", 2299, 18, "Electronics", "https://images.unsplash.com/photo-1523275335684-37898b6baf30"),
                ("Running Shoes", "Lightweight everyday running shoes.", 1899, 30, "Fashion", "https://images.unsplash.com/photo-1542291026-7eec264c27ff"),
                ("Backpack", "Durable backpack for college, work and travel.", 999, 22, "Accessories", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62"),
                ("Coffee Mug", "Ceramic mug for your daily coffee or tea.", 299, 40, "Home", "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d"),
                ("Bluetooth Speaker", "Portable speaker with rich audio.", 1199, 15, "Electronics", "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1"),
            ]
            con.executemany(
                "INSERT INTO products(name, description, price, stock, category, image_url) VALUES(?,?,?,?,?,?)",
                products
            )


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(24)
    return session["_csrf"]


def verify_csrf():
    token = request.form.get("_csrf", "")
    if not token or token != session.get("_csrf"):
        abort(400, "Invalid form token. Refresh the page and try again.")


@app.context_processor
def inject_globals():
    return {"csrf": csrf_token, "current_user": get_current_user()}


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as con:
        return con.execute("SELECT id, name, email, is_admin FROM users WHERE id=?", (user_id,)).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not user["is_admin"]:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


BASE = """
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · ShopEase</title>
<style>
:root{--ink:#172033;--muted:#667085;--brand:#5b55e7;--bg:#f5f6fb;--line:#e7e9f0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Arial,sans-serif}
nav{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.navin{max-width:1120px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:22px}
.logo{font-size:21px;font-weight:800;color:var(--brand);text-decoration:none;margin-right:auto}
nav a{color:var(--ink);text-decoration:none;font-weight:600}.navin form{margin:0}
.wrap{max-width:1120px;margin:28px auto;padding:0 20px}
.hero{background:linear-gradient(120deg,#24215f,#716af2);color:#fff;padding:38px;border-radius:20px;margin-bottom:28px}
.hero h1{font-size:34px;margin:0 0 8px}.hero p{margin:0;color:#e5e4ff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px}
.card{background:#fff;border:1px solid var(--line);border-radius:15px;overflow:hidden}
.card img{width:100%;height:170px;object-fit:cover;background:#eceef5}
.pad{padding:16px}.muted{color:var(--muted)}.price{font-size:20px;font-weight:800;margin:8px 0}
.btn{border:0;border-radius:9px;background:var(--brand);color:#fff;padding:10px 15px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}
.btn.secondary{background:#ecebff;color:#3932b8}.btn.danger{background:#d92d20}
input,textarea,select{width:100%;padding:11px;border:1px solid #d8dce6;border-radius:8px;margin:6px 0 14px;font:inherit}
label{font-weight:700}form.inline{display:inline} .row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.panel{background:#fff;border:1px solid var(--line);border-radius:15px;padding:22px;margin-bottom:18px}
table{width:100%;border-collapse:collapse;background:#fff}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line)}
.notice{padding:12px 15px;border-radius:9px;background:#eaf7ef;margin-bottom:12px}.notice.warning{background:#fff4df}
.auth{max-width:440px;margin:50px auto}.empty{text-align:center;padding:45px;background:#fff;border-radius:15px}
footer{text-align:center;color:var(--muted);padding:30px}
@media(max-width:650px){.navin{gap:12px;flex-wrap:wrap}.hero{padding:25px}.hero h1{font-size:27px}table{font-size:13px}th,td{padding:8px}}
</style></head><body>
<nav><div class="navin"><a class="logo" href="{{ url_for('home') }}">ShopEase</a>
<a href="{{ url_for('home') }}">Shop</a>
{% if current_user %}<a href="{{ url_for('cart') }}">Cart</a><a href="{{ url_for('orders') }}">Orders</a>
{% if current_user['is_admin'] %}<a href="{{ url_for('admin') }}">Admin</a>{% endif %}
<span class="muted">Hi, {{ current_user['name'] }}</span>
<form class="inline" method="post" action="{{ url_for('logout') }}"><input type="hidden" name="_csrf" value="{{ csrf() }}"><button class="btn secondary" type="submit">Logout</button></form>
{% else %}<a href="{{ url_for('login') }}">Login</a><a class="btn" href="{{ url_for('register') }}">Sign up</a>{% endif %}
</div></nav>
<main class="wrap">
{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}
<div class="notice {{ 'warning' if category=='warning' else '' }}">{{ message }}</div>{% endfor %}{% endwith %}
{{ content|safe }}
</main><footer>ShopEase · Demo online shopping application</footer></body></html>
"""


def page(title, body, **context):
    content = render_template_string(body, **context)
    return render_template_string(BASE, title=title, content=content)


@app.route("/")
def home():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql = "SELECT * FROM products WHERE 1=1"
    args = []
    if search:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        args += [f"%{search}%", f"%{search}%"]
    if category:
        sql += " AND category=?"
        args.append(category)
    sql += " ORDER BY id DESC"
    with db() as con:
        products = con.execute(sql, args).fetchall()
        categories = con.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    body = """
    <section class="hero"><h1>Find your everyday favourites.</h1><p>Browse products, add them to your cart and place a demo order.</p></section>
    <form method="get" class="panel"><div class="row">
      <div style="flex:2;min-width:180px"><input name="q" placeholder="Search products..." value="{{ search }}"></div>
      <div style="flex:1;min-width:150px"><select name="category"><option value="">All categories</option>{% for c in categories %}<option value="{{ c['category'] }}" {% if category==c['category'] %}selected{% endif %}>{{ c['category'] }}</option>{% endfor %}</select></div>
      <button class="btn" type="submit">Search</button></div></form>
    <div class="grid">{% for p in products %}<article class="card">
      {% if p['image_url'] %}<img src="{{ p['image_url'] }}" alt="{{ p['name'] }}">{% endif %}
      <div class="pad"><div class="muted">{{ p['category'] }} · {{ p['stock'] }} in stock</div><h3>{{ p['name'] }}</h3>
      <p class="muted">{{ p['description'] }}</p><div class="price">₹{{ '%.2f'|format(p['price']) }}</div>
      {% if p['stock']>0 %}<form method="post" action="{{ url_for('add_to_cart', product_id=p['id']) }}"><input type="hidden" name="_csrf" value="{{ csrf() }}"><button class="btn">Add to cart</button></form>{% else %}<span class="muted">Out of stock</span>{% endif %}
      </div></article>{% else %}<div class="empty">No products found.</div>{% endfor %}</div>
    """
    return page("Shop", body, products=products, categories=categories, search=search, category=category)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        verify_csrf()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email and a password of at least 8 characters.", "warning")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                                (name, email, generate_password_hash(password), datetime.now().isoformat(timespec="seconds")))
                flash("Account created. Please log in.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "warning")
    body = """<div class="auth panel"><h2>Create your account</h2><form method="post">
    <input type="hidden" name="_csrf" value="{{ csrf() }}"><label>Name</label><input name="name" required>
    <label>Email</label><input type="email" name="email" required><label>Password (minimum 8 characters)</label><input type="password" name="password" minlength="8" required>
    <button class="btn">Create account</button></form><p class="muted">Already registered? <a href="{{ url_for('login') }}">Log in</a></p></div>"""
    return page("Register", body)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        verify_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back!")
            return redirect(url_for("home"))
        flash("Incorrect email or password.", "warning")
    body = """<div class="auth panel"><h2>Welcome back</h2><form method="post">
    <input type="hidden" name="_csrf" value="{{ csrf() }}"><label>Email</label><input type="email" name="email" required>
    <label>Password</label><input type="password" name="password" required><button class="btn">Log in</button></form>
    <p class="muted">New here? <a href="{{ url_for('register') }}">Create an account</a></p></div>"""
    return page("Login", body)


@app.post("/logout")
@login_required
def logout():
    verify_csrf()
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))


@app.post("/cart/add/<int:product_id>")
@login_required
def add_to_cart(product_id):
    verify_csrf()
    quantity = max(1, min(int(request.form.get("quantity", 1)), 20))
    user_id = session["user_id"]
    with db() as con:
        product = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not product or product["stock"] < quantity:
            flash("Product unavailable or insufficient stock.", "warning")
        else:
            existing = con.execute("SELECT quantity FROM cart_items WHERE user_id=? AND product_id=?", (user_id, product_id)).fetchone()
            new_qty = quantity + (existing["quantity"] if existing else 0)
            if new_qty > product["stock"]:
                flash("Your cart quantity exceeds available stock.", "warning")
            elif existing:
                con.execute("UPDATE cart_items SET quantity=? WHERE user_id=? AND product_id=?", (new_qty, user_id, product_id))
                flash("Cart updated.")
            else:
                con.execute("INSERT INTO cart_items(user_id,product_id,quantity) VALUES(?,?,?)", (user_id, product_id, quantity))
                flash("Added to cart.")
    return redirect(request.referrer or url_for("home"))


@app.route("/cart")
@login_required
def cart():
    with db() as con:
        items = con.execute("""SELECT p.id,p.name,p.price,p.stock,p.image_url,c.quantity,
            (p.price*c.quantity) AS subtotal FROM cart_items c JOIN products p ON p.id=c.product_id
            WHERE c.user_id=? ORDER BY c.id DESC""", (session["user_id"],)).fetchall()
    total = sum(i["subtotal"] for i in items)
    body = """<h1>Your shopping cart</h1>{% if items %}<div class="panel"><table><tr><th>Product</th><th>Price</th><th>Quantity</th><th>Subtotal</th><th></th></tr>
    {% for i in items %}<tr><td>{{ i['name'] }}</td><td>₹{{ '%.2f'|format(i['price']) }}</td><td>
    <form method="post" action="{{ url_for('update_cart', product_id=i['id']) }}" class="row"><input type="hidden" name="_csrf" value="{{ csrf() }}"><input style="width:75px;margin:0" type="number" min="1" max="{{ i['stock'] }}" name="quantity" value="{{ i['quantity'] }}"><button class="btn secondary">Update</button></form>
    </td><td>₹{{ '%.2f'|format(i['subtotal']) }}</td><td><form method="post" action="{{ url_for('remove_from_cart', product_id=i['id']) }}"><input type="hidden" name="_csrf" value="{{ csrf() }}"><button class="btn danger">Remove</button></form></td></tr>{% endfor %}</table>
    <div class="row" style="justify-content:flex-end;margin-top:18px"><h2>Total: ₹{{ '%.2f'|format(total) }}</h2>
    <form method="post" action="{{ url_for('checkout') }}"><input type="hidden" name="_csrf" value="{{ csrf() }}"><button class="btn">Place demo order</button></form></div>
    <p class="muted">Demo checkout only. No real payment is collected.</p></div>{% else %}<div class="empty">Your cart is empty. <a href="{{ url_for('home') }}">Continue shopping</a></div>{% endif %}"""
    return page("Cart", body, items=items, total=total)


@app.post("/cart/update/<int:product_id>")
@login_required
def update_cart(product_id):
    verify_csrf()
    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1
    with db() as con:
        product = con.execute("SELECT stock FROM products WHERE id=?", (product_id,)).fetchone()
        if not product or quantity < 1 or quantity > product["stock"]:
            flash("Invalid quantity or insufficient stock.", "warning")
        else:
            con.execute("UPDATE cart_items SET quantity=? WHERE user_id=? AND product_id=?", (quantity, session["user_id"], product_id))
            flash("Cart updated.")
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:product_id>")
@login_required
def remove_from_cart(product_id):
    verify_csrf()
    with db() as con:
        con.execute("DELETE FROM cart_items WHERE user_id=? AND product_id=?", (session["user_id"], product_id))
    flash("Item removed.")
    return redirect(url_for("cart"))


@app.post("/checkout")
@login_required
def checkout():
    verify_csrf()
    user_id = session["user_id"]
    with db() as con:
        items = con.execute("""SELECT p.id,p.name,p.price,p.stock,c.quantity FROM cart_items c
            JOIN products p ON p.id=c.product_id WHERE c.user_id=?""", (user_id,)).fetchall()
        if not items:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("cart"))
        for item in items:
            if item["quantity"] > item["stock"]:
                flash(f"Not enough stock for {item['name']}. Please update your cart.", "warning")
                return redirect(url_for("cart"))
        total = sum(item["price"] * item["quantity"] for item in items)
        cur = con.execute("INSERT INTO orders(user_id,total,status,created_at) VALUES(?,?,?,?)",
                          (user_id, total, "Placed", datetime.now().isoformat(timespec="seconds")))
        order_id = cur.lastrowid
        for item in items:
            con.execute("INSERT INTO order_items(order_id,product_id,product_name,price,quantity) VALUES(?,?,?,?,?)",
                        (order_id, item["id"], item["name"], item["price"], item["quantity"]))
            con.execute("UPDATE products SET stock=stock-? WHERE id=?", (item["quantity"], item["id"]))
        con.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))
    flash(f"Order #{order_id} placed successfully. This is a demo order; no payment was taken.")
    return redirect(url_for("orders"))


@app.route("/orders")
@login_required
def orders():
    with db() as con:
        rows = con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
        details = {}
        for order in rows:
            details[order["id"]] = con.execute("SELECT * FROM order_items WHERE order_id=?", (order["id"],)).fetchall()
    body = """<h1>Your orders</h1>{% for o in rows %}<div class="panel"><div class="row" style="justify-content:space-between"><h3>Order #{{ o['id'] }}</h3><strong>{{ o['status'] }}</strong></div>
    <p class="muted">{{ o['created_at'] }}</p><ul>{% for i in details[o['id']] %}<li>{{ i['product_name'] }} × {{ i['quantity'] }} — ₹{{ '%.2f'|format(i['price']*i['quantity']) }}</li>{% endfor %}</ul>
    <h3>Total: ₹{{ '%.2f'|format(o['total']) }}</h3></div>{% else %}<div class="empty">You have not placed any orders yet.</div>{% endfor %}"""
    return page("Orders", body, rows=rows, details=details)


@app.route("/admin")
@login_required
@admin_required
def admin():
    with db() as con:
        products = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        order_count = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        user_count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    body = """<h1>Admin dashboard</h1><div class="grid">
    <div class="panel"><div class="muted">Registered users</div><h2>{{ user_count }}</h2></div>
    <div class="panel"><div class="muted">Orders placed</div><h2>{{ order_count }}</h2></div></div>
    <div class="panel"><h2>Add product</h2><form method="post" action="{{ url_for('add_product') }}">
    <input type="hidden" name="_csrf" value="{{ csrf() }}"><label>Product name</label><input name="name" required>
    <label>Description</label><textarea name="description" required></textarea><div class="row">
    <div style="flex:1"><label>Price (₹)</label><input type="number" min="0.01" step="0.01" name="price" required></div>
    <div style="flex:1"><label>Stock</label><input type="number" min="0" name="stock" required></div>
    <div style="flex:1"><label>Category</label><input name="category" required></div></div>
    <label>Image URL (optional)</label><input name="image_url"><button class="btn">Add product</button></form></div>
    <div class="panel"><h2>Products</h2><table><tr><th>Name</th><th>Price</th><th>Stock</th><th>Category</th></tr>
    {% for p in products %}<tr><td>{{ p['name'] }}</td><td>₹{{ '%.2f'|format(p['price']) }}</td><td>{{ p['stock'] }}</td><td>{{ p['category'] }}</td></tr>{% endfor %}</table></div>"""
    return page("Admin", body, products=products, user_count=user_count, order_count=order_count)


@app.post("/admin/products/add")
@login_required
@admin_required
def add_product():
    verify_csrf()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    image_url = request.form.get("image_url", "").strip()
    try:
        price = float(request.form.get("price", "0"))
        stock = int(request.form.get("stock", "0"))
    except ValueError:
        flash("Price and stock must be valid numbers.", "warning")
        return redirect(url_for("admin"))
    if not name or not description or not category or price <= 0 or stock < 0:
        flash("Please enter valid product details.", "warning")
    else:
        with db() as con:
            con.execute("INSERT INTO products(name,description,price,stock,category,image_url) VALUES(?,?,?,?,?,?)",
                        (name, description, price, stock, category, image_url))
        flash("Product added.")
    return redirect(url_for("admin"))


@app.get("/health")
def health():
    return {"status": "ok", "application": "ShopEase"}


@app.cli.command("create-admin")
def create_admin():
    """Create or promote an admin: flask --app app create-admin"""
    email = os.environ.get("ADMIN_EMAIL", "admin@shopease.local").lower()
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Set ADMIN_PASSWORD before running this command.")
    with db() as con:
        existing = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            con.execute("UPDATE users SET is_admin=1,password_hash=? WHERE id=?",
                        (generate_password_hash(password), existing["id"]))
        else:
            con.execute("INSERT INTO users(name,email,password_hash,is_admin,created_at) VALUES(?,?,?,?,?)",
                        ("Shop Admin", email, generate_password_hash(password), 1, datetime.now().isoformat(timespec="seconds")))
    print(f"Admin account ready: {email}")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
