import os
import sys
import json
import urllib.parse
from datetime import datetime
import random
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, send_from_directory

from database import get_db, get_settings, init_db, USE_MONGO, mongo_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ecommerce_store_secret_production_key')

@app.template_filter('urlencode')
def urlencode_filter(s):
    return urllib.parse.quote(str(s) if s is not None else '')

@app.context_processor
def inject_settings():
    return dict(settings=get_settings())

def fetch_categories():
    if USE_MONGO and mongo_db is not None:
        return list(mongo_db.categories.find({}, {'_id': 0}))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories')
    rows = cursor.fetchall()
    conn.close()
    return rows

def fetch_featured_products():
    if USE_MONGO and mongo_db is not None:
        products = list(mongo_db.products.find({'is_featured': 1, 'is_active': 1}, {'_id': 0}).sort('id', -1))
        cats = {c['id']: c['name'] for c in fetch_categories()}
        for p in products:
            p['category_name'] = cats.get(p.get('category_id'), '')
        return products
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, c.name as category_name, c.slug as category_slug 
    FROM products p 
    LEFT JOIN categories c ON p.category_id = c.id 
    WHERE p.is_featured = 1 AND p.is_active = 1
    ORDER BY p.id DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def fetch_products(category_slug='', search_query=''):
    if USE_MONGO and mongo_db is not None:
        query = {'is_active': 1}
        current_category = None
        cats = fetch_categories()
        cat_map = {c['id']: c['name'] for c in cats}

        if category_slug:
            matched_cat = next((c for c in cats if c['slug'] == category_slug), None)
            if matched_cat:
                current_category = matched_cat
                query['category_id'] = matched_cat['id']

        if search_query:
            query['$or'] = [
                {'name': {'$regex': search_query, '$options': 'i'}},
                {'description': {'$regex': search_query, '$options': 'i'}}
            ]

        products = list(mongo_db.products.find(query, {'_id': 0}).sort('id', -1))
        for p in products:
            p['category_name'] = cat_map.get(p.get('category_id'), '')
        return products, current_category

    conn = get_db()
    cursor = conn.cursor()
    current_category = None
    sql = '''
    SELECT p.*, c.name as category_name, c.slug as category_slug 
    FROM products p 
    LEFT JOIN categories c ON p.category_id = c.id 
    WHERE p.is_active = 1
    '''
    params = []

    if category_slug:
        cursor.execute('SELECT * FROM categories WHERE slug = ?', (category_slug,))
        current_category = cursor.fetchone()
        sql += ' AND c.slug = ?'
        params.append(category_slug)

    if search_query:
        sql += ' AND (p.name LIKE ? OR p.description LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%'])

    sql += ' ORDER BY p.id DESC'
    cursor.execute(sql, params)
    products = cursor.fetchall()
    conn.close()
    return products, current_category

def fetch_product_by_id(product_id):
    if USE_MONGO and mongo_db is not None:
        p = mongo_db.products.find_one({'id': int(product_id)}, {'_id': 0})
        if p:
            cats = {c['id']: c for c in fetch_categories()}
            cat = cats.get(p.get('category_id'), {})
            p['category_name'] = cat.get('name', '')
            p['category_slug'] = cat.get('slug', '')
        return p

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, c.name as category_name, c.slug as category_slug 
    FROM products p 
    LEFT JOIN categories c ON p.category_id = c.id 
    WHERE p.id = ?
    ''', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

# --- مسارات واجهة المتجر العامة ---

@app.route('/')
def index():
    categories = fetch_categories()
    featured_products = fetch_featured_products()
    return render_template('index.html', active_page='home', categories=categories, featured_products=featured_products)

@app.route('/products')
def products():
    categories = fetch_categories()
    category_slug = request.args.get('category', '').strip()
    search_query = request.args.get('q', '').strip()

    product_list, current_category = fetch_products(category_slug, search_query)
    return render_template('products.html', active_page='products', categories=categories, current_category=current_category, products=product_list, query=search_query)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = fetch_product_by_id(product_id)
    if not product:
        return "المنتج غير موجود", 404

    request_url = request.base_url
    return render_template('product_detail.html', product=product, request_url=request_url)

@app.route('/cart')
def cart():
    return render_template('cart.html', active_page='cart')

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    settings = get_settings()
    if request.method == 'GET':
        return render_template('checkout.html', active_page='checkout')

    customer_name = request.form.get('customer_name', '').strip()
    customer_phone = request.form.get('customer_phone', '').strip()
    customer_email = request.form.get('customer_email', '').strip()
    customer_city = request.form.get('customer_city', '').strip()
    customer_address = request.form.get('customer_address', '').strip()
    notes = request.form.get('notes', '').strip()
    payment_method = request.form.get('payment_method', 'whatsapp').strip()
    order_currency = request.form.get('order_currency', 'YER').strip()
    cart_items_json = request.form.get('cart_items_json', '[]').strip()

    try:
        items = json.loads(cart_items_json)
    except Exception:
        items = []

    if not items:
        return redirect(url_for('cart'))

    subtotal_yer = sum(float(i.get('price', 0)) * int(i.get('quantity', 1)) for i in items)
    shipping_fee_yer = float(settings.get('shipping_fee', 1500))
    free_threshold = float(settings.get('free_shipping_threshold', 25000))
    if subtotal_yer >= free_threshold:
        shipping_fee_yer = 0
    total_yer = subtotal_yer + shipping_fee_yer

    # حساب القيمة حسب العملة المختارة
    rate = 1.0
    if order_currency == 'USD':
        rate = float(settings.get('usd_exchange_rate', 535))
    elif order_currency == 'SAR':
        rate = float(settings.get('sar_exchange_rate', 142))

    subtotal_converted = round(subtotal_yer / rate, 2)
    shipping_converted = round(shipping_fee_yer / rate, 2)
    total_converted = round(total_yer / rate, 2)

    order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    payment_status = 'paid' if payment_method == 'online' else 'pending'

    if USE_MONGO and mongo_db is not None:
        order_count = mongo_db.orders.count_documents({}) + 1
        order_doc = {
            'id': order_count,
            'order_number': order_number,
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'customer_email': customer_email,
            'customer_city': customer_city,
            'customer_address': customer_address,
            'notes': notes,
            'payment_method': payment_method,
            'payment_status': payment_status,
            'order_status': 'new',
            'subtotal': subtotal_converted,
            'shipping_fee': shipping_converted,
            'total': total_converted,
            'currency': order_currency,
            'items': [
                {
                    'product_id': i.get('id'),
                    'product_name': i.get('name', 'منتج'),
                    'price': round(float(i.get('price', 0)) / rate, 2),
                    'quantity': int(i.get('quantity', 1)),
                    'total': round((float(i.get('price', 0)) * int(i.get('quantity', 1))) / rate, 2)
                }
                for i in items
            ],
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        mongo_db.orders.insert_one(order_doc)
        order_id = order_count
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO orders (
            order_number, customer_name, customer_phone, customer_email,
            customer_city, customer_address, notes, payment_method,
            payment_status, order_status, subtotal, shipping_fee, total, currency
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?)
        ''', (
            order_number, customer_name, customer_phone, customer_email,
            customer_city, customer_address, notes, payment_method,
            payment_status, subtotal_converted, shipping_converted, total_converted, order_currency
        ))
        order_id = cursor.lastrowid

        for item in items:
            p_price = round(float(item.get('price', 0)) / rate, 2)
            p_qty = int(item.get('quantity', 1))
            cursor.execute('''
            INSERT INTO order_items (order_id, product_id, product_name, price, quantity, total)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (order_id, item.get('id'), item.get('name', 'منتج'), p_price, p_qty, round(p_price * p_qty, 2)))

        conn.commit()
        conn.close()

    return redirect(url_for('order_success', order_id=order_id))

@app.route('/order-success/<int:order_id>')
def order_success(order_id):
    if USE_MONGO and mongo_db is not None:
        order = mongo_db.orders.find_one({'id': int(order_id)}, {'_id': 0})
        if not order:
            return "الطلب غير موجود", 404
        items = order.get('items', [])
        return render_template('order_success.html', order=order, items=items)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
    items = cursor.fetchall()
    conn.close()

    if not order:
        return "الطلب غير موجود", 404

    return render_template('order_success.html', order=order, items=items)

@app.route('/robots.txt')
def robots():
    content = "User-agent: *\nDisallow: /admin\nDisallow: /checkout\nDisallow: /order-success/\nAllow: /\n\nSitemap: " + request.url_root.rstrip('/') + "/sitemap.xml\n"
    return Response(content, mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    base_url = request.url_root.rstrip('/')
    products, _ = fetch_products()
    categories = fetch_categories()
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += f'  <url><loc>{base_url}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>\n'
    xml += f'  <url><loc>{base_url}/products</loc><changefreq>daily</changefreq><priority>0.9</priority></url>\n'
    for cat in categories:
        xml += f'  <url><loc>{base_url}/products?category={cat.get("slug")}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>\n'
    for p in products:
        xml += f'  <url><loc>{base_url}/product/{p.get("id")}</loc><changefreq>weekly</changefreq><priority>0.85</priority></url>\n'
    xml += '</urlset>'
    return Response(xml, mimetype='application/xml')

# --- مسارات لوحة التحكم Admin ---
@app.route('/admin')
@app.route('/admin/dashboard')
def admin_dashboard():
    if USE_MONGO and mongo_db is not None:
        total_orders = mongo_db.orders.count_documents({})
        paid_orders = list(mongo_db.orders.find({'order_status': {'$ne': 'cancelled'}}, {'total': 1}))
        total_revenue = sum(o.get('total', 0) for o in paid_orders)
        whatsapp_orders = mongo_db.orders.count_documents({'payment_method': 'whatsapp'})
        cod_orders = mongo_db.orders.count_documents({'payment_method': 'cod'})
        online_orders = mongo_db.orders.count_documents({'payment_method': 'online'})
        recent_orders = list(mongo_db.orders.find({}, {'_id': 0}).sort('id', -1).limit(5))
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM orders')
        total_orders = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM orders WHERE order_status != 'cancelled'")
        total_revenue = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE payment_method = 'whatsapp'")
        whatsapp_orders = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE payment_method = 'cod'")
        cod_orders = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE payment_method = 'online'")
        online_orders = cursor.fetchone()[0]

        cursor.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 5')
        recent_orders = cursor.fetchall()
        conn.close()

    stats = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'whatsapp_orders': whatsapp_orders,
        'cod_orders': cod_orders,
        'online_orders': online_orders
    }

    return render_template('admin/dashboard.html', active_tab='dashboard', stats=stats, recent_orders=recent_orders)

@app.route('/admin/products')
def admin_products():
    if USE_MONGO and mongo_db is not None:
        products = list(mongo_db.products.find({}, {'_id': 0}).sort('id', -1))
        categories = fetch_categories()
        cat_map = {c['id']: c['name'] for c in categories}
        for p in products:
            p['category_name'] = cat_map.get(p.get('category_id'), '')
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT p.*, c.name as category_name 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id 
        ORDER BY p.id DESC
        ''')
        products = cursor.fetchall()
        cursor.execute('SELECT * FROM categories')
        categories = cursor.fetchall()
        conn.close()

    return render_template('admin/products.html', active_tab='products', products=products, categories=categories)

@app.route('/admin/products/new', methods=['POST'])
def admin_add_product():
    name = request.form.get('name', '').strip()
    cat_id = int(request.form.get('category_id', 1))
    price = float(request.form.get('price', 0))
    compare_price = request.form.get('compare_at_price')
    compare_price = float(compare_price) if compare_price else None
    image_url = request.form.get('image_url', '').strip()
    stock = int(request.form.get('stock', 10))
    description = request.form.get('description', '').strip()
    is_featured = 1 if 'is_featured' in request.form else 0
    slug = f"prd-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if USE_MONGO and mongo_db is not None:
        p_count = mongo_db.products.count_documents({}) + 1
        mongo_db.products.insert_one({
            'id': p_count,
            'category_id': cat_id,
            'name': name,
            'slug': slug,
            'description': description,
            'price': price,
            'compare_at_price': compare_price,
            'image_url': image_url,
            'stock': stock,
            'is_featured': is_featured,
            'is_active': 1
        })
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO products (category_id, name, slug, description, price, compare_at_price, image_url, stock, is_featured, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (cat_id, name, slug, description, price, compare_price, image_url, stock, is_featured))
        conn.commit()
        conn.close()

    return redirect(url_for('admin_products'))

@app.route('/admin/products/delete', methods=['POST'])
def admin_delete_product():
    p_id = int(request.form.get('product_id', 0))
    if USE_MONGO and mongo_db is not None:
        mongo_db.products.delete_one({'id': p_id})
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (p_id,))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
def admin_orders():
    filter_method = request.args.get('method', '').strip()
    if USE_MONGO and mongo_db is not None:
        query = {}
        if filter_method in ['whatsapp', 'cod', 'online']:
            query['payment_method'] = filter_method
        orders = list(mongo_db.orders.find(query, {'_id': 0}).sort('id', -1))
    else:
        conn = get_db()
        cursor = conn.cursor()
        if filter_method in ['whatsapp', 'cod', 'online']:
            cursor.execute('SELECT * FROM orders WHERE payment_method = ? ORDER BY id DESC', (filter_method,))
        else:
            cursor.execute('SELECT * FROM orders ORDER BY id DESC')
        orders = cursor.fetchall()
        conn.close()

    return render_template('admin/orders.html', active_tab='orders', orders=orders, filter_method=filter_method)

@app.route('/admin/orders/update_status', methods=['POST'])
def admin_update_order_status():
    order_id = int(request.form.get('order_id', 0))
    status = request.form.get('status', 'new').strip()

    if USE_MONGO and mongo_db is not None:
        mongo_db.orders.update_one({'id': order_id}, {'$set': {'order_status': status}})
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE orders SET order_status = ? WHERE id = ?', (status, order_id))
        conn.commit()
        conn.close()

    return redirect(url_for('admin_orders'))

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if request.method == 'POST':
        keys = [
            'store_name', 'store_description', 'store_whatsapp', 'store_phone',
            'store_email', 'store_currency', 'shipping_fee', 'free_shipping_threshold',
            'usd_exchange_rate', 'sar_exchange_rate'
        ]
        updates = {}
        for k in keys:
            if k in request.form:
                updates[k] = request.form[k].strip()
        updates['enable_whatsapp_order'] = '1' if 'enable_whatsapp_order' in request.form else '0'
        updates['enable_cod'] = '1' if 'enable_cod' in request.form else '0'
        updates['enable_online_payment'] = '1' if 'enable_online_payment' in request.form else '0'

        if USE_MONGO and mongo_db is not None:
            for k, v in updates.items():
                mongo_db.settings.update_one({'key': k}, {'$set': {'value': v}}, upsert=True)
        else:
            conn = get_db()
            cursor = conn.cursor()
            for k, v in updates.items():
                cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, v))
            conn.commit()
            conn.close()
        return redirect(url_for('admin_settings'))

    return render_template('admin/settings.html', active_tab='settings')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
