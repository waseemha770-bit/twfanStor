import io
import urllib.parse
import json
from server import application
from database import init_db, get_db

def run_request(path, method='GET', post_data=None, query_string=''):
    environ = {
        'PATH_INFO': path,
        'REQUEST_METHOD': method,
        'QUERY_STRING': query_string,
        'wsgi.url_scheme': 'http',
        'SERVER_NAME': 'localhost',
        'SERVER_PORT': '8080',
        'HTTP_HOST': 'localhost:8080',
        'wsgi.input': io.BytesIO(),
        'CONTENT_LENGTH': '0'
    }

    if method == 'POST' and post_data:
        encoded_data = urllib.parse.urlencode(post_data).encode('utf-8')
        environ['wsgi.input'] = io.BytesIO(encoded_data)
        environ['CONTENT_LENGTH'] = str(len(encoded_data))
        environ['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

    response_status = []
    response_headers = []

    def start_response(status, headers):
        response_status.append(status)
        response_headers.append(headers)

    body_chunks = application(environ, start_response)
    body = b''.join(body_chunks).decode('utf-8', errors='replace')
    return response_status[0], dict(response_headers[0]), body

def test_store():
    print("1. تهيئة قاعدة بيانات متجر الطوفان البيطري...")
    init_db()

    print("2. اختبار الصفحة الرئيسية وتوقيع المطور المهندس وسيم همدان (GET /)...")
    status, headers, body = run_request('/')
    assert "200 OK" in status, f"Expected 200 OK, got {status}"
    assert "متجر الطوفان البيطري" in body, "Store name must appear"
    assert "المهندس وسيم همدان" in body, "Developer credit must be in footer"
    assert "967 771 954 200" in body, "Developer phone must be in footer"
    assert "desktop-mode" in body, "Desktop mode must be default"
    print("   ✓ الصفحة الرئيسية وتوقيع المطور وشريط التنقل للهواتف تعمل بنجاح!")

    print("3. اختبار صفحة الأدوية والمستلزمات البيطرية (GET /products)...")
    status, headers, body = run_request('/products')
    assert "200 OK" in status
    assert "أوكسي تتراسيكلين" in body or "فيتامين" in body
    print("   ✓ صفحة الأدوية والمنتجات تعمل بنجاح!")

    print("4. اختبار صفحة تفاصيل الدواء البيطري (GET /product/1)...")
    status, headers, body = run_request('/product/1')
    assert "200 OK" in status
    assert "أوكسي تتراسيكلين" in body
    print("   ✓ صفحة تفاصيل الدواء تعمل بنجاح!")

    print("5. اختبار صفحة إتمام الطلب ومحول العملات (GET /checkout)...")
    status, headers, body = run_request('/checkout')
    assert "200 OK" in status
    assert "إرسال عبر واتساب" in body
    assert "الدفع عند الاستلام" in body
    assert "بوابة الدفع الإلكتروني" in body
    print("   ✓ صفحة إنهاء الطلب وخيارات الدفع تعمل بنجاح!")

    print("6. اختبار إرسال طلب أدوية بيطرية جديد عبر واتساب (POST /checkout)...")
    cart_items = [
        {"id": 1, "name": "أوكسي تتراسيكلين 20% طويل المفعول (100ml)", "price": 7500, "quantity": 3, "image_url": "https://example.com/med.jpg"}
    ]
    post_data = {
        'customer_name': 'مزرعة الخير للأبقار',
        'customer_phone': '772222222',
        'customer_city': 'حجة',
        'customer_address': 'منطقة عبس - مزرعة الوادي',
        'payment_method': 'whatsapp',
        'order_currency': 'USD',
        'cart_items_json': json.dumps(cart_items)
    }
    status, headers, body = run_request('/checkout', method='POST', post_data=post_data)
    assert "302 Found" in status
    location = headers.get('Location')
    print(f"   ✓ تم إنشاء الطلب والتحويل بنجاح إلى: {location}")

    order_id = int(location.split('/')[-1])
    print(f"7. اختبار صفحة الفاتورة للطلب (GET /order-success/{order_id})...")
    status, headers, body = run_request(f'/order-success/{order_id}')
    assert "200 OK" in status
    assert "مزرعة الخير للأبقار" in body
    assert "ORD-" in body
    print("   ✓ صفحة الفاتورة الرسمية تعمل بنجاح!")

    print("8. اختبار لوحة التحكم الإدارية (GET /admin/dashboard)...")
    status, headers, body = run_request('/admin/dashboard')
    assert "200 OK" in status
    assert "لوحة التاجر" in body
    assert "طلبات واتساب" in body
    print("   ✓ لوحة التحكم الرئيسية تعمل بنجاح!")

    print("9. اختبار جدول الطلبات في الإدارة (GET /admin/orders)...")
    status, headers, body = run_request('/admin/orders')
    assert "200 OK" in status
    assert "مزرعة الخير للأبقار" in body
    print("   ✓ شاشة إدارة الطلبات تعرض الطلبات المسجلة بنجاح!")

    print("10. اختبار تحديث شعار المتجر من لوحة الإدارة (POST /admin/settings/save)...")
    test_logo = "https://images.unsplash.com/photo-1548767797-d8c844163c4c?w=150&auto=format&fit=crop&q=80"
    settings_post = {
        'store_name': 'متجر الطوفان البيطري',
        'store_logo_url': test_logo,
        'store_description': 'المنصة البيطرية الرائدة',
        'store_currency': 'ر.ي',
        'store_whatsapp': '967771954200',
        'store_phone': '+967 771 954 200',
        'store_email': 'contact@altoofan-vet.com',
        'shipping_fee': '2000',
        'free_shipping_threshold': '30000',
        'usd_exchange_rate': '535',
        'sar_exchange_rate': '142',
        'enable_whatsapp_order': '1',
        'enable_cod': '1',
        'enable_online_payment': '1'
    }
    status, headers, body = run_request('/admin/settings/save', method='POST', post_data=settings_post)
    assert "302 Found" in status
    print("    ✓ تم حفظ الشعار الجديد وإعدادات المتجر بنجاح!")

    print("11. اختبار ظهور الشعار الجديد في واجهة المتجر والهيدر والفوتر (GET /)...")
    status, headers, body = run_request('/')
    assert "200 OK" in status
    assert "photo-1548767797-d8c844163c4c" in body, "Custom store logo must be rendered in HTML"
    assert "store-custom-logo" in body, "Custom logo CSS class must exist"
    print("    ✓ الشعار المحدث يظهر بنجاح في رأس وتذييل المتجر!")

    print("\n🎉 جميع اختبارات متجر الطوفان البيطري والشعار والتجاوب الـ 11 نجحت بتفوق بنسبة 100%!")

if __name__ == '__main__':
    test_store()
