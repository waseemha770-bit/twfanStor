import os
import sys
import json
import mimetypes
import urllib.parse
from wsgiref.simple_server import make_server, WSGIServer
import jinja2
from datetime import datetime
import random

from database import get_db, get_settings, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
    autoescape=jinja2.select_autoescape(['html', 'xml'])
)
jinja_env.filters['urlencode'] = lambda s: urllib.parse.quote(str(s) if s is not None else '')

def parse_post_data(environ):
    try:
        content_length = int(environ.get('CONTENT_LENGTH', 0))
    except (ValueError, TypeError):
        content_length = 0

    if content_length > 0:
        post_data_bytes = environ['wsgi.input'].read(content_length)
        post_str = post_data_bytes.decode('utf-8', errors='replace')
        return urllib.parse.parse_qs(post_str, keep_blank_values=True)
    return {}

def parse_query_params(environ):
    query_string = environ.get('QUERY_STRING', '')
    return urllib.parse.parse_qs(query_string, keep_blank_values=True)

def render(template_name, context=None, status="200 OK", headers=None):
    if context is None:
        context = {}
    if headers is None:
        headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ('Pragma', 'no-cache'),
            ('Expires', '0')
        ]
    
    template = jinja_env.get_template(template_name)
    output = template.render(**context)
    return status, headers, [output.encode('utf-8')]

def json_response(data, status="200 OK"):
    headers = [('Content-Type', 'application/json; charset=utf-8')]
    return status, headers, [json.dumps(data, ensure_ascii=False).encode('utf-8')]

def redirect(location, status="302 Found"):
    headers = [('Location', location)]
    return status, headers, []

def serve_static(environ, start_response, path):
    relative_path = path[len('/static/'):]
    file_path = os.path.join(STATIC_DIR, relative_path)
    
    if os.path.exists(file_path) and os.path.isfile(file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        start_response("200 OK", [
            ('Content-Type', mime_type),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ('Pragma', 'no-cache'),
            ('Expires', '0')
        ])
        with open(file_path, 'rb') as f:
            return [f.read()]
    
    start_response("404 Not Found", [('Content-Type', 'text/plain; charset=utf-8')])
    return [b'Static file not found']

def application(environ, start_response):
    path = environ.get('PATH_INFO', '/')
    method = environ.get('REQUEST_METHOD', 'GET')
    
    if path.startswith('/static/'):
        return serve_static(environ, start_response, path)
    
    if path == '/robots.txt':
        robots_content = """User-agent: *
Allow: /
Disallow: /admin/
Sitemap: /sitemap.xml
"""
        start_response("200 OK", [('Content-Type', 'text/plain; charset=utf-8')])
        return [robots_content.encode('utf-8')]

    if path == '/sitemap.xml':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, slug FROM products WHERE is_active = 1')
        products = cursor.fetchall()
        cursor.execute('SELECT slug FROM categories')
        categories = cursor.fetchall()
        conn.close()

        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        xml.append('  <url><loc>/</loc><priority>1.0</priority></url>')
        xml.append('  <url><loc>/products</loc><priority>0.8</priority></url>')
        xml.append('  <url><loc>/cart</loc><priority>0.5</priority></url>')
        for c in categories:
            xml.append(f'  <url><loc>/products?category={c["slug"]}</loc><priority>0.7</priority></url>')
        for p in products:
            xml.append(f'  <url><loc>/product/{p["id"]}</loc><priority>0.8</priority></url>')
        xml.append('</urlset>')
        start_response("200 OK", [('Content-Type', 'application/xml; charset=utf-8')])
        return ['\n'.join(xml).encode('utf-8')]

    settings = get_settings()
    conn = get_db()
    cursor = conn.cursor()

    if path == '/':
        cursor.execute('SELECT * FROM categories')
        categories = cursor.fetchall()

        cursor.execute('SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.is_active = 1 AND p.is_featured = 1 LIMIT 8')
        featured_products = cursor.fetchall()

        status, headers, body = render('index.html', {
            'active_page': 'home',
            'categories': categories,
            'featured_products': featured_products,
            'settings': settings
        })
        conn.close()
        start_response(status, headers)
        return body

    if path == '/products':
        query_params = parse_query_params(environ)
        cat_slug = query_params.get('category', [''])[0].strip()
        search_query = query_params.get('q', [''])[0].strip()

        cursor.execute('SELECT * FROM categories')
        categories = cursor.fetchall()

        sql = 'SELECT p.*, c.name as category_name, c.slug as category_slug FROM products p JOIN categories c ON p.category_id = c.id WHERE p.is_active = 1'
        params = []

        if cat_slug:
            sql += ' AND c.slug = ?'
            params.append(cat_slug)
        if search_query:
            sql += ' AND (p.name LIKE ? OR p.description LIKE ?)'
            params.append(f'%{search_query}%')
            params.append(f'%{search_query}%')

        sql += ' ORDER BY p.id DESC'
        cursor.execute(sql, params)
        products = cursor.fetchall()

        status, headers, body = render('products.html', {
            'active_page': 'products',
            'products': products,
            'categories': categories,
            'current_category': cat_slug,
            'search_query': search_query,
            'settings': settings
        })
        conn.close()
        start_response(status, headers)
        return body

    if path.startswith('/product/'):
        try:
            product_id = int(path.split('/')[-1])
        except (ValueError, IndexError):
            product_id = 0
            
        cursor.execute('SELECT p.*, c.name as category_name, c.slug as category_slug FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id = ?', (product_id,))
        product = cursor.fetchone()

        if not product:
            conn.close()
            start_response("404 Not Found", [('Content-Type', 'text/html; charset=utf-8')])
            return [b'<h1>Product Not Found</h1>']

        cursor.execute('SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.category_id = ? AND p.id != ? LIMIT 4', (product['category_id'], product['id']))
        related_products = cursor.fetchall()

        status, headers, body = render('product_detail.html', {
            'active_page': 'products',
            'product': product,
            'related_products': related_products,
            'settings': settings
        })
        conn.close()
        start_response(status, headers)
        return body

    if path == '/cart':
        status, headers, body = render('cart.html', {
            'active_page': 'cart',
            'settings': settings
        })
        conn.close()
        start_response(status, headers)
        return body

    if path == '/checkout':
        if method == 'GET':
            status, headers, body = render('checkout.html', {
                'active_page': 'checkout',
                'settings': settings
            })
            conn.close()
            start_response(status, headers)
            return body

        elif method == 'POST':
            post_data = parse_post_data(environ)
            customer_name = post_data.get('customer_name', [''])[0].strip()
            customer_phone = post_data.get('customer_phone', [''])[0].strip()
            customer_email = post_data.get('customer_email', [''])[0].strip()
            customer_city = post_data.get('customer_city', [''])[0].strip()
            customer_address = post_data.get('customer_address', [''])[0].strip()
            notes = post_data.get('notes', [''])[0].strip()
            payment_method = post_data.get('payment_method', ['whatsapp'])[0].strip()
            order_currency = post_data.get('order_currency', [settings.get('store_currency', 'ر.ي')])[0].strip()
            
            cart_items_json = post_data.get('cart_items_json', ['[]'])[0].strip()
            try:
                cart_items = json.loads(cart_items_json)
            except Exception:
                cart_items = []

            if not customer_name or not customer_phone or not cart_items:
                conn.close()
                start_response("400 Bad Request", [('Content-Type', 'text/html; charset=utf-8')])
                return [b'Missing required order information']

            order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M')}-{random.randint(100, 999)}"
            
            subtotal = sum(float(item['price']) * int(item['quantity']) for item in cart_items)
            free_threshold = float(settings.get('free_shipping_threshold', 30000))
            shipping_fee = 0.0 if subtotal >= free_threshold else float(settings.get('shipping_fee', 2000))
            total = subtotal + shipping_fee

            cursor.execute('''
            INSERT INTO orders (
                order_number, customer_name, customer_phone, customer_email,
                customer_city, customer_address, notes, payment_method,
                payment_status, order_status, subtotal, shipping_fee, total, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order_number, customer_name, customer_phone, customer_email,
                customer_city, customer_address, notes, payment_method,
                'pending' if payment_method != 'online' else 'paid',
                'new', subtotal, shipping_fee, total, order_currency
            ))
            
            order_id = cursor.lastrowid

            for item in cart_items:
                item_total = float(item['price']) * int(item['quantity'])
                cursor.execute('''
                INSERT INTO order_items (order_id, product_id, product_name, price, quantity, total)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (order_id, item['id'], item['name'], float(item['price']), int(item['quantity']), item_total))

            conn.commit()
            conn.close()

            status, headers, body = redirect(f'/order-success/{order_id}')
            start_response(status, headers)
            return body

    if path.startswith('/order-success/'):
        try:
            order_id = int(path.split('/')[-1])
        except (ValueError, IndexError):
            order_id = 0

        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()

        if not order:
            conn.close()
            start_response("404 Not Found", [('Content-Type', 'text/html; charset=utf-8')])
            return [b'<h1>Order Not Found</h1>']

        cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
        items = cursor.fetchall()

        msg_lines = [
            f"مرحباً متجر الطوفان البيطري، أود تأكيد طلبيتي الجديدة:",
            f"رقم الفاتورة: {order['order_number']}",
            f"الاسم: {order['customer_name']}",
            f"الهاتف: {order['customer_phone']}",
            f"المدينة: {order['customer_city']} - {order['customer_address']}",
            f"طريقة الدفع: {order['payment_method']}",
            f"--------------------------",
            "الأدوية والمستلزمات المطلوبة:"
        ]
        for it in items:
            msg_lines.append(f"• {it['product_name']} × {it['quantity']} = {int(it['total'])} {order['currency']}")
        
        msg_lines.append(f"--------------------------")
        msg_lines.append(f"قيمة الأدوية: {int(order['subtotal'])} {order['currency']}")
        msg_lines.append(f"الشحن البيطري المبرد: {int(order['shipping_fee'])} {order['currency']}")
        msg_lines.append(f"الإجمالي النهائي: {int(order['total'])} {order['currency']}")
        if order['notes']:
            msg_lines.append(f"ملاحظات: {order['notes']}")
        
        whatsapp_message = "\n".join(msg_lines)
        whatsapp_url = f"https://wa.me/{settings['store_whatsapp']}?text={urllib.parse.quote(whatsapp_message)}"

        status, headers, body = render('order_success.html', {
            'order': order,
            'items': items,
            'whatsapp_url': whatsapp_url,
            'settings': settings
        })
        conn.close()
        start_response(status, headers)
        return body

    # لوحة تحكم التاجر البيطرية
    if path == '/admin' or path == '/admin/' or path == '/admin/dashboard':
        cursor.execute('SELECT COUNT(*) FROM orders')
        total_orders = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM products')
        total_products = cursor.fetchone()[0]

        cursor.execute('SELECT SUM(total) FROM orders')
        revenue_sum = cursor.fetchone()[0] or 0.0

        cursor.execute('SELECT COUNT(*) FROM orders WHERE payment_method = "whatsapp"')
        whatsapp_orders = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM orders WHERE payment_method = "cod"')
        cod_orders = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM orders WHERE payment_method = "online"')
        online_orders = cursor.fetchone()[0]

        cursor.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 5')
        recent_orders = cursor.fetchall()

        stats = {
            'total_orders': total_orders,
            'total_products': total_products,
            'total_revenue': revenue_sum,
            'whatsapp_orders': whatsapp_orders,
            'cod_orders': cod_orders,
            'online_orders': online_orders
        }

        status, headers, body = render('admin/dashboard.html', {
            'active_tab': 'dashboard',
            'stats': stats,
            'recent_orders': recent_orders,
            'settings': settings
        })
        conn.close()
        start_response(status, headers)
        return body

    if path == '/admin/products':
        cursor.execute('SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id ORDER BY p.id DESC')
        products = cursor.fetchall()
        cursor.execute('SELECT * FROM categories')
        categories = cursor.fetchall()

        status, headers, body = render('admin/products.html', {
            'active_tab': 'products',
            'products': products,
            'categories': categories,
            'settings': settings
        })
        conn.close()
        start_response(status, headers)
        return body

    if path == '/admin/products/add' and method == 'POST':
        post_data = parse_post_data(environ)
        name = post_data.get('name', [''])[0].strip()
        category_id = int(post_data.get('category_id', [1])[0])
        price = float(post_data.get('price', [0])[0])
        compare_price = float(post_data.get('compare_at_price', [0])[0]) if post_data.get('compare_at_price', [''])[0] else None
        description = post_data.get('description', [''])[0].strip()
        image_url = post_data.get('image_url', [''])[0].strip() or 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600&auto=format&fit=crop&q=80'
        stock = int(post_data.get('stock', [10])[0])
        is_featured = 1 if 'is_featured' in post_data else 0

        slug = urllib.parse.quote(name.lower().replace(' ', '-'))
        cursor.execute('''
        INSERT INTO products (name, slug, category_id, price, compare_at_price, description, image_url, stock, is_featured, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (name, slug, category_id, price, compare_price, description, image_url, stock, is_featured))
        conn.commit()
        conn.close()

        status, headers, body = redirect('/admin/products')
        start_response(status, headers)
        return body

    if path == '/admin/products/delete' and method == 'POST':
        post_data = parse_post_data(environ)
        product_id = int(post_data.get('id', [0])[0])
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()

        status, headers, body = redirect('/admin/products')
        start_response(status, headers)
        return body

    if path == '/admin/orders':
        query_params = parse_query_params(environ)
        filter_method = query_params.get('method', [''])[0].strip()
        if filter_method in ['whatsapp', 'cod', 'online']:
            cursor.execute('SELECT * FROM orders WHERE payment_method = ? ORDER BY id DESC', (filter_method,))
        else:
            cursor.execute('SELECT * FROM orders ORDER BY id DESC')
        orders = cursor.fetchall()

        status, headers, body = render('admin/orders.html', {
            'active_tab': 'orders',
            'orders': orders,
            'filter_method': filter_method,
            'settings': settings
        })
        conn.close()
        start_response(status, headers)
        return body

    if path == '/admin/orders/update_status' and method == 'POST':
        post_data = parse_post_data(environ)
        order_id = int(post_data.get('order_id', [0])[0])
        new_status = post_data.get('status', ['new'])[0].strip()

        cursor.execute('UPDATE orders SET order_status = ? WHERE id = ?', (new_status, order_id))
        conn.commit()
        conn.close()

        status, headers, body = redirect('/admin/orders')
        start_response(status, headers)
        return body

    if path == '/admin/settings' or path == '/admin/settings/save':
        if method == 'GET':
            status, headers, body = render('admin/settings.html', {
                'active_tab': 'settings',
                'settings': settings
            })
            conn.close()
            start_response(status, headers)
            return body
        elif method == 'POST' or path == '/admin/settings/save':
            post_data = parse_post_data(environ)
            keys = [
                'store_name', 'store_logo_url', 'store_description', 'store_whatsapp', 'store_phone',
                'store_email', 'store_currency', 'shipping_fee', 'free_shipping_threshold',
                'usd_exchange_rate', 'sar_exchange_rate'
            ]
            for k in keys:
                if k in post_data:
                    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, post_data[k][0].strip()))

            cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('enable_whatsapp_order', '1' if 'enable_whatsapp_order' in post_data else '0'))
            cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('enable_cod', '1' if 'enable_cod' in post_data else '0'))
            cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('enable_online_payment', '1' if 'enable_online_payment' in post_data else '0'))

            conn.commit()
            conn.close()
            status, headers, body = redirect('/admin/settings')
            start_response(status, headers)
            return body

    conn.close()
    start_response("404 Not Found", [('Content-Type', 'text/html; charset=utf-8')])
    return [b'<h1>404 - Page Not Found</h1>']

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    WSGIServer.allow_reuse_address = True
    
    try:
        httpd = make_server('0.0.0.0', port, application)
    except OSError as e:
        if getattr(e, 'errno', None) == 98:
            alt_port = port + 1
            print(f"Warning: Port {port} is busy. Trying port {alt_port}...")
            httpd = make_server('0.0.0.0', alt_port, application)
            port = alt_port
        else:
            raise e
            
    print(f"Server running with multi-currency & logo support at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
