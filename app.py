from flask import Flask, render_template, request, redirect, flash, session, url_for
import sqlite3
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# DB Initialization
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            address TEXT,
            phone TEXT,
            total_price REAL,
            timestamp TEXT,
            payment_status TEXT DEFAULT 'Not Paid',
            order_status TEXT DEFAULT 'Ordered',
            user_id INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product TEXT,
            quantity REAL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
    ''')

    # Add the users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

# Dummy admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Session-based admin login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please login as admin to view this page.', 'warning')
            return redirect('/admin-login')
        return f(*args, **kwargs)
    return decorated_function

# User login required decorator
def user_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_logged_in'):
            flash('Please login to view this page.', 'warning')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# Authentication check decorator for general pages
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_logged_in') and not session.get('admin_logged_in'):
            flash('Please login to access this page.', 'warning')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@auth_required
def home():
    return render_template('home.html')

@app.route('/about')
@auth_required
def about():
    return render_template('about.html')

@app.route('/products')
@auth_required
def products():
    return render_template('products.html')

@app.route('/contact', methods=['GET', 'POST'])
@auth_required
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        flash('Thanks for contacting us! We will reach out soon.', 'success')
        return redirect('/contact')
    return render_template('contact.html')

@app.route('/order', methods=['GET', 'POST'])
@auth_required
def order():
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        phone = request.form['phone']

        # Get the selected products from checkboxes
        selected_products = request.form.getlist('product')
        
        # Define different prices for each product
        product_prices = {
            '20 mm Gravel Stone': 500,
            '12 mm Gravel Stone': 550,
            '40 mm Gravel Stone': 475,
            'M-SAND': 600
        }
        
        delivery_charge = 1000

        items = []
        total_product_price = 0

        # Only process products that were actually selected
        for product in selected_products:
            quantity_str = request.form.get(f'quantity_{product}')
            if quantity_str:
                try:
                    quantity = float(quantity_str)
                    if quantity >= 0.5:
                        # Use the correct price for this product
                        price = product_prices.get(product, 500)  # Default to 500 if product not found
                        items.append((product, quantity))
                        total_product_price += quantity * price * 2  # Multiply by 2 because price is per 0.5 unit
                except ValueError:
                    pass  # Handle invalid quantity values

        if not items:
            flash("Please order at least one product with a minimum of 0.5 units.", "warning")
            return redirect('/order')

        total_price = total_product_price + delivery_charge
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get user_id if logged in
        user_id = session.get('user_id')

        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        c.execute("INSERT INTO orders (name, address, phone, total_price, timestamp, user_id, order_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (name, address, phone, total_price, timestamp, user_id, 'Ordered'))

        order_id = c.lastrowid

        for product, quantity in items:
            c.execute("INSERT INTO order_items (order_id, product, quantity) VALUES (?, ?, ?)",
                      (order_id, product, quantity))

        conn.commit()
        conn.close()

        flash('Your order has been placed successfully!', 'success')
        return redirect('/order')

    return render_template('order.html')

# User Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def user_login():
    # Redirect if already logged in
    if session.get('user_logged_in'):
        return redirect('/')
    if session.get('admin_logged_in'):
        return redirect('/admin')
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and user[3] == password:  # In production, use proper password hashing
            session['user_logged_in'] = True
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Logged in successfully!', 'success')
            return redirect('/')
        else:
            flash('Invalid credentials', 'danger')
    
    # Use the standalone login template without navigation
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def user_register():
    # Redirect if already logged in
    if session.get('user_logged_in'):
        return redirect('/')
    if session.get('admin_logged_in'):
        return redirect('/admin')
        
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect('/register')
        
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        
        try:
            c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                    (username, email, password))  # In production, hash the password
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash('Username or email already exists', 'danger')
        finally:
            conn.close()
    
    # Use the standalone register template without navigation
    return render_template('register.html')

@app.route('/logout')
def user_logout():
    session.pop('user_logged_in', None)
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out successfully.', 'info')
    return redirect('/login')

@app.route('/user-dashboard')
@user_login_required
def user_dashboard():
    user_id = session.get('user_id')
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    # Get user information
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    # Get all orders for this user
    c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    user_orders = c.fetchall()
    
    # Get order items
    c.execute("SELECT oi.* FROM order_items oi JOIN orders o ON oi.order_id = o.id WHERE o.user_id = ?", (user_id,))
    items = c.fetchall()
    
    # Format order items
    order_items = {}
    for item in items:
        item_id, order_id, product, quantity = item
        order_items.setdefault(order_id, []).append((product, quantity))
    
    # Count paid and unpaid orders
    paid_orders = len([order for order in user_orders if order[6] == 'Paid'])
    unpaid_orders = len(user_orders) - paid_orders
    
    # Count orders by status
    ordered_count = len([order for order in user_orders if order[7] == 'Ordered'])
    shipped_count = len([order for order in user_orders if order[7] == 'Shipped'])
    delivered_count = len([order for order in user_orders if order[7] == 'Delivered'])
    
    conn.close()
    
    return render_template('user_dashboard.html', 
                          user={"id": user[0], "username": user[1], "email": user[2]},
                          user_orders=user_orders,
                          order_items=order_items,
                          paid_orders=paid_orders,
                          unpaid_orders=unpaid_orders,
                          ordered_count=ordered_count,
                          shipped_count=shipped_count,
                          delivered_count=delivered_count)

@app.route('/view-order/<int:order_id>')
@user_login_required
def view_order_details(order_id):
    user_id = session.get('user_id')
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    # Verify this order belongs to the logged-in user
    c.execute("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id))
    order = c.fetchone()
    
    if not order:
        conn.close()
        flash("Order not found or you don't have permission to view it", 'danger')
        return redirect('/user-dashboard')
    
    # Get order items
    c.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = c.fetchall()
    
    conn.close()
    
    return render_template('order_details.html', order=order, items=items)

# Admin Routes
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    # Redirect if already logged in
    if session.get('admin_logged_in'):
        return redirect('/admin')
    if session.get('user_logged_in'):
        return redirect('/')
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Logged in successfully!', 'success')
            return redirect('/admin')
        else:
            flash('Invalid credentials', 'danger')
    
    # Use the standalone admin login template without navigation
    return render_template('admin_login.html')

@app.route('/admin-dashboard')
@login_required
def admin_dashboard():
    conn = sqlite3.connect('orders.db')
    cur = conn.cursor()

    # Fetch summary stats using the correct column name `timestamp`
    cur.execute("SELECT COUNT(*) FROM orders WHERE strftime('%m', timestamp) = strftime('%m', 'now')")
    order_count = cur.fetchone()[0]

    cur.execute("SELECT SUM(total_price) FROM orders WHERE payment_status = 'Paid'")
    total_received = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(total_price) FROM orders WHERE payment_status = 'Not Paid'")
    total_not_received = cur.fetchone()[0] or 0

    # Fetch unpaid orders
    cur.execute("SELECT * FROM orders WHERE payment_status = 'Not Paid'")
    unpaid_orders = cur.fetchall()
    
    # Count orders by status
    cur.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Ordered'")
    ordered_count = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Shipped'")
    shipped_count = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Delivered'")
    delivered_count = cur.fetchone()[0] or 0

    conn.close()

    return render_template(
        'admin_dashboard.html',
        order_count=order_count,
        total_received=total_received,
        total_not_received=total_not_received,
        unpaid_orders=unpaid_orders,
        ordered_count=ordered_count,
        shipped_count=shipped_count,
        delivered_count=delivered_count
    )

@app.route('/admin-delete-order/<int:order_id>')
@login_required
def admin_delete_order(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()

    # Delete the order items first
    c.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    
    # Delete the order
    c.execute("DELETE FROM orders WHERE id = ?", (order_id,))

    conn.commit()
    conn.close()

    flash('Order deleted successfully!', 'success')
    return redirect('/admin')

@app.route('/admin-update-payment-status/<int:order_id>', methods=['POST'])
@login_required
def admin_update_payment_status(order_id):
    # Ensure that the 'payment_status' field exists in the form
    payment_status = request.form.get('payment_status')
    
    # Check if the payment status is valid
    if payment_status not in ['Paid', 'Not Paid']:
        flash('Invalid payment status', 'danger')
        return redirect('/admin')
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()

    # Update the payment status in the database
    try:
        c.execute("UPDATE orders SET payment_status = ? WHERE id = ?", (payment_status, order_id))
        conn.commit()

        if c.rowcount == 0:
            flash('Order not found or payment status already updated.', 'warning')
        else:
            flash(f'Payment status for Order {order_id} updated to {payment_status}!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating payment status: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect('/admin')

@app.route('/admin-update-order-status/<int:order_id>', methods=['POST'])
@login_required
def admin_update_order_status(order_id):
    # Ensure that the 'order_status' field exists in the form
    order_status = request.form.get('order_status')
    
    # Check if the order status is valid
    if order_status not in ['Ordered', 'Shipped', 'Delivered']:
        flash('Invalid order status', 'danger')
        return redirect('/admin')
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()

    # Update the order status in the database
    try:
        c.execute("UPDATE orders SET order_status = ? WHERE id = ?", (order_status, order_id))
        conn.commit()

        if c.rowcount == 0:
            flash('Order not found or order status already updated.', 'warning')
        else:
            flash(f'Order status for Order {order_id} updated to {order_status}!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating order status: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect('/admin')

@app.route('/admin')
@login_required
def admin():
    year = request.args.get('year')
    month = request.args.get('month')

    conn = sqlite3.connect('orders.db')
    c = conn.cursor()

    query = "SELECT * FROM orders"
    params = []

    if year and month:
        query += " WHERE strftime('%Y', timestamp) = ? AND strftime('%m', timestamp) = ?"
        params.extend([year, month])
    elif year:
        query += " WHERE strftime('%Y', timestamp) = ?"
        params.append(year)
    elif month:
        query += " WHERE strftime('%m', timestamp) = ?"
        params.append(month)

    c.execute(query, params)
    orders = c.fetchall()

    c.execute("SELECT * FROM order_items")
    items = c.fetchall()

    order_items = {}
    for item in items:
        item_id, order_id, product, quantity = item
        order_items.setdefault(order_id, []).append((product, quantity))

    # Extract unique years and months from orders for filter dropdowns
    c.execute("SELECT DISTINCT strftime('%Y', timestamp) FROM orders")
    years = sorted([row[0] for row in c.fetchall()], reverse=True)

    c.execute("SELECT DISTINCT strftime('%m', timestamp) FROM orders")
    months = sorted([row[0] for row in c.fetchall()])

    conn.close()
    return render_template('admin.html', orders=orders, order_items=order_items, years=years, months=months, selected_year=year, selected_month=month)

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully.', 'info')
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)