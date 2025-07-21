import json
import os
import time
import threading
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

PRODUCTS_FILE = 'products.json'
ORDERS_FILE = 'orders.json'
USERS_FILE = 'users.json'

DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1396527512334635088/U9ylCjkAyFphq_WU7Vwi945xNMBuq6eMptFEiqLg92rQdELNQ1lfBnOmBW7uAfwRRuxb'

notified_order_timestamps = set()

def load_json(file):
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump([], f)
    with open(file, 'r') as f:
        return json.load(f)

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

def send_discord_notification(order):
    message = f"""🛒 **New Order Received!**\n\n👤 **Username:** {order.get('username')}\n📍 **City:** {order.get('address', {}).get('city', 'N/A')}, {order.get('address', {}).get('province', 'N/A')}\n📦 **Product:** {order.get('product', {}).get('name')}\n💰 **Price:** ${order.get('product', {}).get('price')}\n🔗 **Link:** {order.get('product', {}).get('link')}\n📱 **WhatsApp:** {order.get('whatsapp')}\n🕒 **Time:** {order.get('timestamp')}"""
    payload = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print(f"✅ Discord notification sent.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Discord notification failed: {e}")

def watch_orders():
    print("📡 Starting background order watcher...")
    while True:
        try:
            orders = load_json(ORDERS_FILE)
            for order in orders:
                timestamp = order.get("timestamp")
                if timestamp and timestamp not in notified_order_timestamps:
                    send_discord_notification(order)
                    notified_order_timestamps.add(timestamp)
        except Exception as e:
            print(f"⚠️ Error watching orders: {e}")
        time.sleep(5)

# Start watching orders in background
threading.Thread(target=watch_orders, daemon=True).start()

@app.route('/')
def index():
    products = load_json(PRODUCTS_FILE)
    return render_template('index.html', products=products)

@app.route('/product/<int:product_id>')
def product(product_id):
    products = load_json(PRODUCTS_FILE)
    product = next((p for p in products if p.get('id') == product_id), None)
    if not product:
        return "Product not found", 404
    return render_template('product.html', product=product, product_id=product_id)

@app.route('/cash_on_delivery/<int:product_id>')
def cash_on_delivery(product_id):
    if 'user' not in session:
        return redirect('/login')
    return redirect(f'/address/{product_id}?from=cod')

@app.route('/direct_pay/<int:product_id>')
def direct_pay(product_id):
    if 'user' not in session:
        return redirect('/login')
    return render_template('payment.html', product_id=product_id)

@app.route('/payment/<int:product_id>', methods=['POST'])
def payment(product_id):
    return redirect(f'/address/{product_id}?from=pay')

@app.route('/address/<int:product_id>', methods=['GET', 'POST'])
def address(product_id):
    if request.method == 'POST':
        data = request.form.to_dict()
        product = next((p for p in load_json(PRODUCTS_FILE) if p.get('id') == product_id), None)
        if not product:
            return 'Product not found', 404
        user = session.get('user', {})
        order = {
            'username': user.get('username'),
            'whatsapp': user.get('whatsapp'),
            'product': product,
            'address': data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        orders = load_json(ORDERS_FILE)
        orders.append(order)
        save_json(ORDERS_FILE, orders)
        return redirect('/order_confirmation')

    return render_template('address.html', product_id=product_id)

@app.route('/order_confirmation')
def order_confirmation():
    return render_template('order_confirmation.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_json(USERS_FILE)
        user = next((u for u in users if u['username'] == username and u['password'] == password), None)
        if user:
            session['user'] = user
            return redirect('/')
        return 'Invalid credentials'
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        new_user = {
            'username': request.form['username'],
            'email': request.form['email'],
            'password': request.form['password'],
            'whatsapp': request.form['whatsapp']
        }
        users = load_json(USERS_FILE)
        users.append(new_user)
        save_json(USERS_FILE, users)
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('admin', None)
    return redirect('/')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form['password']
        if password == 'admin123':
            session['admin'] = True
            return redirect('/admin')
        return 'Incorrect Password'
    return render_template('admin_login.html')

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin_login')
    products = load_json(PRODUCTS_FILE)
    return render_template('admin_dashboard.html', products=products)

@app.route('/admin/orders')
def admin_orders():
    if not session.get('admin'):
        return redirect('/admin_login')
    orders = load_json(ORDERS_FILE)
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/users')
def admin_users():
    if not session.get('admin'):
        return redirect('/admin_login')
    users = load_json(USERS_FILE)
    return render_template('admin_users.html', users=users)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        products = load_json(PRODUCTS_FILE)
        new_product = {
            'id': (products[-1]['id'] + 1) if products else 1,
            'name': request.form['name'],
            'description': request.form['description'],
            'price': request.form['price'],
            'image': request.form['image'],
            'link': request.form.get('link', '')
        }
        products.append(new_product)
        save_json(PRODUCTS_FILE, products)
        return redirect('/admin')
    return render_template('add_product.html')

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    products = load_json(PRODUCTS_FILE)
    product = next((p for p in products if p['id'] == product_id), None)
    if request.method == 'POST' and product:
        product['name'] = request.form['name']
        product['description'] = request.form['description']
        product['price'] = request.form['price']
        product['image'] = request.form['image']
        product['link'] = request.form.get('link', '')
        save_json(PRODUCTS_FILE, products)
        return redirect('/admin')
    return render_template('edit_product.html', product=product)

@app.route('/delete_product/<int:product_id>')
def delete_product(product_id):
    products = load_json(PRODUCTS_FILE)
    products = [p for p in products if p.get('id') != product_id]
    save_json(PRODUCTS_FILE, products)
    return redirect('/admin')

@app.route('/delete_order/<int:index>')
def delete_order(index):
    orders = load_json(ORDERS_FILE)
    if 0 <= index < len(orders):
        orders.pop(index)
        save_json(ORDERS_FILE, orders)
    return redirect('/admin/orders')

@app.route('/delete_user/<int:index>')
def delete_user(index):
    users = load_json(USERS_FILE)
    if 0 <= index < len(users):
        users.pop(index)
        save_json(USERS_FILE, users)
    return redirect('/admin/users')

if __name__ == '__main__':
    app.run(debug=False)
