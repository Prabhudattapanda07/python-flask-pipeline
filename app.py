import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps
from contextlib import contextmanager

from flask import (
    Flask, request, redirect, url_for,
    session, flash, render_template_string, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "tastybite-demo-secret-change-in-production"
)

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "food.db")


# =========================
# DATABASE CONNECTION
# =========================

@contextmanager
def get_db():
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")

    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def initialize_database():
    with get_db() as con:

        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            UNIQUE(user_id, food_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(food_id) REFERENCES foods(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Order Received',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );
        """)

        if con.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 0:

            foods = [
                ("Cheese Burger", "Delicious burger with cheese and fresh vegetables.", "Burger", 149,
                 "https://images.unsplash.com/photo-1568901346375-23c9450c58cd"),

                ("Veg Pizza", "Freshly baked pizza loaded with vegetables.", "Pizza", 249,
                 "https://images.unsplash.com/photo-1513104890138-7c749659a591"),

                ("Chicken Pizza", "Pizza topped with chicken and mozzarella.", "Pizza", 329,
                 "https://images.unsplash.com/photo-1571407970349-bc81e7e96d47"),

                ("White Sauce Pasta", "Creamy pasta with herbs and vegetables.", "Pasta", 199,
                 "https://images.unsplash.com/photo-1473093295043-cdd812d0e601"),

                ("French Fries", "Crispy golden potato fries.", "Snacks", 99,
                 "https://images.unsplash.com/photo-1573080496219-bb080dd4f877"),

                ("Chocolate Cake", "Rich chocolate dessert.", "Dessert", 129,
                 "https://images.unsplash.com/photo-1578985545062-69928b1d9587"),

                ("Cold Coffee", "Refreshing chilled coffee.", "Drinks", 89,
                 "https://images.unsplash.com/photo-1461023058943-07fcbe16d735"),

                ("Sandwich", "Fresh sandwich with vegetables and cheese.", "Snacks", 119,
                 "https://images.unsplash.com/photo-1528735602780-2552fd46c7af")
            ]

            con.executemany("""
                INSERT INTO foods
                (name, description, category, price, image)
                VALUES (?, ?, ?, ?, ?)
            """, foods)


initialize_database()


# =========================
# AUTHENTICATION
# =========================

def get_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    with get_db() as con:
        return con.execute(
            "SELECT id, name, email FROM users WHERE id=?",
            (user_id,)
        ).fetchone()


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):

        if not get_user():
            flash("Please login first.", "warning")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(24)

    return session["_csrf"]


def verify_csrf():
    token = request.form.get("_csrf", "")

    if not token or token != session.get("_csrf"):
        abort(400, "Invalid form token. Refresh and try again.")


@app.context_processor
def inject_user():
    return {
        "user": get_user(),
        "csrf": csrf_token
    }


# =========================
# HTML DESIGN
# =========================

LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }} | TastyBite</title>

    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f7f7f7;
            color: #222;
        }

        nav {
            background: white;
            padding: 16px 6%;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            box-shadow: 0 2px 10px #00000010;
        }

        .logo {
            font-size: 25px;
            font-weight: bold;
            color: #ed5b2b;
            text-decoration: none;
        }

        nav a {
            text-decoration: none;
            color: #333;
            font-weight: bold;
            margin: 0 8px;
        }

        .container {
            max-width: 1150px;
            margin: 30px auto;
            padding: 0 20px;
        }

        .hero {
            background: linear-gradient(120deg, #30211b, #e65d32);
            color: white;
            padding: 55px 35px;
            border-radius: 18px;
            margin-bottom: 30px;
        }

        .hero h1 {
            font-size: 38px;
            margin: 0 0 12px;
        }

        .hero p {
            font-size: 17px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 22px;
        }

        .card {
            background: white;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 3px 12px #0000000c;
        }

        .card img {
            width: 100%;
            height: 180px;
            object-fit: cover;
        }

        .card-content {
            padding: 16px;
        }

        .card h3 {
            margin: 8px 0;
        }

        .category {
            color: #ed5b2b;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }

        .price {
            font-size: 21px;
            font-weight: bold;
            margin: 12px 0;
        }

        .btn {
            display: inline-block;
            background: #ed5b2b;
            color: white;
            padding: 11px 17px;
            border: none;
            border-radius: 7px;
            cursor: pointer;
            text-decoration: none;
            font-weight: bold;
        }

        .btn:hover {
            background: #ca431b;
        }

        .secondary {
            background: #333;
        }

        input, textarea, select {
            width: 100%;
            padding: 12px;
            margin: 7px 0 16px;
            border: 1px solid #ddd;
            border-radius: 7px;
            font-size: 15px;
        }

        label {
            font-weight: bold;
        }

        .panel {
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 20px;
        }

        .auth {
            max-width: 430px;
            margin: 45px auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }

        th, td {
            padding: 13px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }

        .message {
            background: #e3f8e9;
            padding: 12px;
            border-radius: 7px;
            margin-bottom: 12px;
        }

        .warning {
            background: #fff0df;
        }

        .muted {
            color: #777;
        }

        footer {
            text-align: center;
            padding: 30px;
            color: #777;
        }

        @media(max-width: 600px) {
            .hero h1 {
                font-size: 28px;
            }

            nav {
                justify-content: center;
            }

            th, td {
                padding: 8px;
                font-size: 13px;
            }
        }
    </style>
</head>

<body>

<nav>
    <a class="logo" href="/">TastyBite 🍔</a>

    <div>
        <a href="/">Home</a>

        {% if user %}
            <a href="/cart">Cart</a>
            <a href="/orders">My Orders</a>

            <form action="/logout" method="POST" style="display:inline">
                <input type="hidden" name="_csrf" value="{{ csrf() }}">
                <button class="btn secondary">Logout</button>
            </form>
        {% else %}
            <a href="/login">Login</a>
            <a href="/register">Register</a>
        {% endif %}
    </div>
</nav>

<div class="container">

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
            <div class="message {{ 'warning' if category == 'warning' else '' }}">
                {{ message }}
            </div>
        {% endfor %}
    {% endwith %}

    {{ content|safe }}

</div>

<footer>
    TastyBite Food Ordering System | Fresh Food, Fast Delivery
</footer>

</body>
</html>
"""


def render_page(title, template, **context):
    content = render_template_string(template, **context)

    return render_template_string(
        LAYOUT,
        title=title,
        content=content
    )


# =========================
# HOME / FOOD MENU
# =========================

@app.route("/")
def home():

    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    with get_db() as con:

        query = "SELECT * FROM foods WHERE 1=1"
        params = []

        if search:
            query += " AND name LIKE ?"
            params.append("%" + search + "%")

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY id"

        foods = con.execute(query, params).fetchall()

        categories = con.execute(
            "SELECT DISTINCT category FROM foods ORDER BY category"
        ).fetchall()

    template = """
    <section class="hero">
        <h1>Delicious Food Delivered To You!</h1>
        <p>Discover your favourite dishes and order them online.</p>
        <a href="#menu" class="btn">Explore Menu</a>
    </section>

    <div class="panel">
        <form method="GET">
            <input
                name="q"
                placeholder="Search your favourite food..."
                value="{{ search }}"
            >

            <select name="category">
                <option value="">All Categories</option>

                {% for c in categories %}
                    <option value="{{ c['category'] }}"
                    {% if category == c['category'] %}selected{% endif %}>
                        {{ c['category'] }}
                    </option>
                {% endfor %}
            </select>

            <button class="btn">Search Food</button>
        </form>
    </div>

    <h2 id="menu">Our Food Menu</h2>

    <div class="grid">

        {% for food in foods %}

        <div class="card">

            <img src="{{ food['image'] }}" alt="{{ food['name'] }}">

            <div class="card-content">

                <div class="category">{{ food['category'] }}</div>

                <h3>{{ food['name'] }}</h3>

                <p class="muted">{{ food['description'] }}</p>

                <div class="price">₹{{ food['price'] }}</div>

                <form method="POST"
                    action="{{ url_for('add_to_cart', food_id=food['id']) }}">

                    <input type="hidden" name="_csrf" value="{{ csrf() }}">
                    <input type="hidden" name="quantity" value="1">

                    <button class="btn">Add To Cart +</button>

                </form>

            </div>
        </div>

        {% else %}

        <p>No food items found.</p>

        {% endfor %}

    </div>
    """

    return render_page(
        "Home",
        template,
        foods=foods,
        categories=categories,
        search=search,
        category=category
    )


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        verify_csrf()

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash("Enter valid details. Password must be at least 8 characters.", "warning")

        else:

            try:
                with get_db() as con:
                    con.execute("""
                        INSERT INTO users(name, email, password)
                        VALUES (?, ?, ?)
                    """, (
                        name,
                        email,
                        generate_password_hash(password)
                    ))

                flash("Registration successful. Please login.")
                return redirect(url_for("login"))

            except sqlite3.IntegrityError:
                flash("Email already registered.", "warning")

    template = """
    <div class="panel auth">

        <h2>Create Account</h2>

        <form method="POST">

            <input type="hidden" name="_csrf" value="{{ csrf() }}">

            <label>Full Name</label>
            <input name="name" required>

            <label>Email</label>
            <input type="email" name="email" required>

            <label>Password (minimum 8 characters)</label>
            <input type="password" name="password" minlength="8" required>

            <button class="btn">Register</button>

        </form>

        <p>Already registered? <a href="/login">Login</a></p>

    </div>
    """

    return render_page("Register", template)


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        verify_csrf()

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as con:

            user = con.execute(
                "SELECT * FROM users WHERE email=?",
                (email,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):

            session.clear()
            session["user_id"] = user["id"]

            flash("Login successful!")

            return redirect(url_for("home"))

        flash("Invalid email or password.", "warning")

    template = """
    <div class="panel auth">

        <h2>Login</h2>

        <form method="POST">

            <input type="hidden" name="_csrf" value="{{ csrf() }}">

            <label>Email</label>
            <input type="email" name="email" required>

            <label>Password</label>
            <input type="password" name="password" required>

            <button class="btn">Login</button>

        </form>

        <p>New user? <a href="/register">Create Account</a></p>

    </div>
    """

    return render_page("Login", template)


# =========================
# LOGOUT
# =========================

@app.route("/logout", methods=["POST"])
@login_required
def logout():

    verify_csrf()
    session.clear()

    flash("Logged out successfully.")

    return redirect(url_for("home"))


# =========================
# ADD TO CART
# =========================

@app.route("/cart/add/<int:food_id>", methods=["POST"])
@login_required
def add_to_cart(food_id):

    verify_csrf()

    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1

    quantity = max(1, min(quantity, 20))

    with get_db() as con:

        food = con.execute(
            "SELECT id FROM foods WHERE id=?",
            (food_id,)
        ).fetchone()

        if not food:
            flash("Food item not found.", "warning")

        else:

            existing = con.execute("""
                SELECT quantity FROM cart
                WHERE user_id=? AND food_id=?
            """, (session["user_id"], food_id)).fetchone()

            if existing:

                new_quantity = min(existing["quantity"] + quantity, 20)

                con.execute("""
                    UPDATE cart SET quantity=?
                    WHERE user_id=? AND food_id=?
                """, (
                    new_quantity,
                    session["user_id"],
                    food_id
                ))

            else:

                con.execute("""
                    INSERT INTO cart(user_id, food_id, quantity)
                    VALUES (?, ?, ?)
                """, (
                    session["user_id"],
                    food_id,
                    quantity
                ))

            flash("Food added to cart!")

    return redirect(request.referrer or url_for("home"))


# =========================
# VIEW CART
# =========================

@app.route("/cart")
@login_required
def cart():

    with get_db() as con:

        items = con.execute("""
            SELECT
                foods.id,
                foods.name,
                foods.price,
                cart.quantity,
                foods.price * cart.quantity AS subtotal

            FROM cart

            JOIN foods ON foods.id = cart.food_id

            WHERE cart.user_id=?

        """, (session["user_id"],)).fetchall()

    subtotal = sum(item["subtotal"] for item in items)
    delivery = 30 if items else 0
    total = subtotal + delivery

    template = """
    <h1>Your Shopping Cart</h1>

    {% if items %}

    <div class="panel">

        <table>

            <tr>
                <th>Food</th>
                <th>Price</th>
                <th>Quantity</th>
                <th>Subtotal</th>
                <th>Action</th>
            </tr>

            {% for item in items %}

            <tr>

                <td>{{ item['name'] }}</td>

                <td>₹{{ item['price'] }}</td>

                <td>

                    <form method="POST"
                        action="{{ url_for('update_cart', food_id=item['id']) }}">

                        <input type="hidden" name="_csrf" value="{{ csrf() }}">

                        <input
                            type="number"
                            name="quantity"
                            value="{{ item['quantity'] }}"
                            min="1"
                            max="20"
                            style="width:70px"
                        >

                        <button class="btn">Update</button>

                    </form>

                </td>

                <td>₹{{ item['subtotal'] }}</td>

                <td>

                    <form method="POST"
                        action="{{ url_for('remove_cart', food_id=item['id']) }}">

                        <input type="hidden" name="_csrf" value="{{ csrf() }}">

                        <button class="btn secondary">Remove</button>

                    </form>

                </td>

            </tr>

            {% endfor %}

        </table>

        <h3>Subtotal: ₹{{ subtotal }}</h3>
        <h3>Delivery Fee: ₹{{ delivery }}</h3>
        <h2>Total: ₹{{ total }}</h2>

        <a href="/checkout" class="btn">Proceed To Checkout</a>

    </div>

    {% else %}

        <div class="panel">
            <h3>Your cart is empty.</h3>
            <a href="/" class="btn">Order Food</a>
        </div>

    {% endif %}
    """

    return render_page(
        "Cart",
        template,
        items=items,
        subtotal=subtotal,
        delivery=delivery,
        total=total
    )


# =========================
# UPDATE CART
# =========================

@app.route("/cart/update/<int:food_id>", methods=["POST"])
@login_required
def update_cart(food_id):

    verify_csrf()

    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 0

    if quantity < 1 or quantity > 20:

        flash("Quantity must be between 1 and 20.", "warning")

    else:

        with get_db() as con:
            con.execute("""
                UPDATE cart SET quantity=?
                WHERE user_id=? AND food_id=?
            """, (
                quantity,
                session["user_id"],
                food_id
            ))

        flash("Cart updated.")

    return redirect(url_for("cart"))


# =========================
# REMOVE CART ITEM
# =========================

@app.route("/cart/remove/<int:food_id>", methods=["POST"])
@login_required
def remove_cart(food_id):

    verify_csrf()

    with get_db() as con:
        con.execute("""
            DELETE FROM cart
            WHERE user_id=? AND food_id=?
        """, (
            session["user_id"],
            food_id
        ))

    flash("Item removed from cart.")

    return redirect(url_for("cart"))


# =========================
# CHECKOUT
# =========================

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():

    with get_db() as con:

        items = con.execute("""
            SELECT
                foods.id,
                foods.name,
                foods.price,
                cart.quantity

            FROM cart

            JOIN foods ON foods.id=cart.food_id

            WHERE cart.user_id=?

        """, (session["user_id"],)).fetchall()

    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))

    subtotal = sum(item["price"] * item["quantity"] for item in items)
    delivery = 30
    total = subtotal + delivery

    if request.method == "POST":

        verify_csrf()

        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name or not phone or not address or len(phone) < 10:

            flash("Please enter valid delivery details.", "warning")

        else:

            with get_db() as con:

                cursor = con.execute("""
                    INSERT INTO orders(
                        user_id,
                        customer_name,
                        phone,
                        address,
                        total,
                        status,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session["user_id"],
                    name,
                    phone,
                    address,
                    total,
                    "Order Received",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

                order_id = cursor.lastrowid

                for item in items:

                    con.execute("""
                        INSERT INTO order_items(
                            order_id,
                            food_name,
                            price,
                            quantity
                        )
                        VALUES (?, ?, ?, ?)
                    """, (
                        order_id,
                        item["name"],
                        item["price"],
                        item["quantity"]
                    ))

                con.execute(
                    "DELETE FROM cart WHERE user_id=?",
                    (session["user_id"],)
                )

            flash("Your order has been placed successfully!")

            return redirect(url_for("orders"))

    template = """
    <div class="panel">

        <h1>Checkout</h1>

        <h3>Order Summary</h3>

        {% for item in items %}

            <p>
                {{ item['name'] }} × {{ item['quantity'] }}
                — ₹{{ item['price'] * item['quantity'] }}
            </p>

        {% endfor %}

        <hr>

        <h3>Subtotal: ₹{{ subtotal }}</h3>
        <h3>Delivery: ₹{{ delivery }}</h3>
        <h2>Total: ₹{{ total }}</h2>

        <hr>

        <form method="POST">

            <input type="hidden" name="_csrf" value="{{ csrf() }}">

            <label>Customer Name</label>
            <input name="name" required>

            <label>Phone Number</label>
            <input type="tel" name="phone" minlength="10" required>

            <label>Delivery Address</label>
            <textarea name="address" required></textarea>

            <button class="btn">Place Order</button>

        </form>

        <p class="muted">
            Demo checkout: no real payment is collected.
        </p>

    </div>
    """

    return render_page(
        "Checkout",
        template,
        items=items,
        subtotal=subtotal,
        delivery=delivery,
        total=total
    )


# =========================
# ORDER HISTORY
# =========================

@app.route("/orders")
@login_required
def orders():

    with get_db() as con:

        all_orders = con.execute("""
            SELECT * FROM orders
            WHERE user_id=?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

        order_items = {}

        for order in all_orders:

            order_items[order["id"]] = con.execute("""
                SELECT * FROM order_items
                WHERE order_id=?
            """, (order["id"],)).fetchall()

    template = """
    <h1>My Orders</h1>

    {% for order in all_orders %}

        <div class="panel">

            <h2>Order #{{ order['id'] }}</h2>

            <p class="muted">{{ order['created_at'] }}</p>

            <strong>Status: {{ order['status'] }}</strong>

            <h3>Ordered Items</h3>

            <ul>
                {% for item in order_items[order['id']] %}

                    <li>
                        {{ item['food_name'] }}
                        × {{ item['quantity'] }}
                        — ₹{{ item['price'] * item['quantity'] }}
                    </li>

                {% endfor %}
            </ul>

            <h2>Total: ₹{{ order['total'] }}</h2>

            <p>Delivery Address: {{ order['address'] }}</p>

        </div>

    {% else %}

        <div class="panel">
            <h3>No orders placed yet.</h3>
            <a href="/" class="btn">Explore Menu</a>
        </div>

    {% endfor %}
    """

    return render_page(
        "My Orders",
        template,
        all_orders=all_orders,
        order_items=order_items
    )


# =========================
# JENKINS HEALTH CHECK
# =========================

@app.route("/health", methods=["GET"])
def health():

    try:

        with get_db() as con:
            con.execute("SELECT 1").fetchone()

        return {
            "status": "ok",
            "application": "TastyBite Food Ordering System"
        }, 200

    except sqlite3.Error:

        return {
            "status": "error",
            "application": "TastyBite Food Ordering System"
        }, 500


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
