import os
import urllib.parse
from datetime import datetime
import random

MONGODB_URI = os.environ.get('MONGODB_URI', '')
USE_MONGO = bool(MONGODB_URI and ('mongodb+srv://' in MONGODB_URI or 'mongodb://' in MONGODB_URI))

mongo_client = None
mongo_db = None

if USE_MONGO:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db_name = os.environ.get('MONGODB_DB_NAME', 'altoofan_vet_db')
        mongo_db = mongo_client[db_name]
        print(f"Connected to MongoDB Atlas: {db_name}")
    except Exception as e:
        print(f"Warning: Could not connect to MongoDB Atlas ({e}). Falling back to SQLite.")
        USE_MONGO = False

DEFAULT_LOCAL_PATH = os.path.join(os.path.dirname(__file__), 'data', 'store.db')
SQLITE_DB_PATH = os.environ.get('STORE_DB_PATH', '/tmp/altoofan_vet_store.db' if os.path.exists('/tmp') else DEFAULT_LOCAL_PATH)

def get_db():
    if USE_MONGO and mongo_db is not None:
        return mongo_db
    import sqlite3
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# بيانات وإعدادات متجر الطوفان البيطري الافتراضية
DEFAULT_SETTINGS = {
    'store_name': 'متجر الطوفان البيطري',
    'store_logo_url': '',  # رابط شعار المتجر للتحكم من لوحة الإدارة
    'store_description': 'المنصة البيطرية الرائدة للأدوية والمضادات الحيوية واللقاحات والمكملات الغذائية ومستلزمات رعاية الثروة الحيوانية والدواجن بأعلى معايير الجودة والضمان.',
    'store_whatsapp': '967771954200',
    'store_phone': '+967 771 954 200',
    'store_email': 'contact@altoofan-vet.com',
    'store_currency': 'ر.ي',
    'shipping_fee': '2000',
    'free_shipping_threshold': '30000',
    # أسعار صرف العملات المعتمدة
    'usd_exchange_rate': '535',
    'sar_exchange_rate': '142',
    'enable_whatsapp_order': '1',
    'enable_cod': '1',
    'enable_online_payment': '1',
    'admin_username': 'admin',
    'admin_password': 'admin123'
}

DEFAULT_CATEGORIES = [
    {
        'id': 1,
        'name': 'أدوية ومضادات حيوية',
        'slug': 'medicines',
        'description': 'مضادات حيوية واسعة الطيف وعلاجات بيطرية فعالة للأبقار والأغنام والخيول',
        'icon': 'bi-capsule'
    },
    {
        'id': 2,
        'name': 'فيتامينات ومكملات غذائية',
        'slug': 'vitamins-supplements',
        'description': 'مركبات فيتامينية وأملاح ومعادن لرفع الخصوبة والنمو وزيادة إنتاج الحليب والبيض',
        'icon': 'bi-lightning-charge'
    },
    {
        'id': 3,
        'name': 'لقاحات وتحصينات وقائية',
        'slug': 'vaccines',
        'description': 'تحصينات وقائية معتمدة ضد الأمراض الفيروسية والبكتيرية الشائعة',
        'icon': 'bi-shield-plus'
    },
    {
        'id': 4,
        'name': 'مستلزمات ومعدات المزارع',
        'slug': 'equipment',
        'description': 'معدات الرعاية والحقن والمطهرات ومستلزمات حظائر الماشية والدواجن',
        'icon': 'bi-tools'
    }
]

DEFAULT_PRODUCTS = [
    {
        'id': 1,
        'category_id': 1,
        'name': 'أوكسي تتراسيكلين 20% طويل المفعول (100ml)',
        'slug': 'oxytetracycline-20-la-100ml',
        'description': 'مضاد حيوي بيطري واسع الطيف طويل المفعول لعلاج الالتهابات التنفسية والرئوية والمعوية والتهابات الضرع لدى الأبقار والأغنام والماعز.',
        'price': 7500,
        'compare_at_price': 9000,
        'image_url': 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600&auto=format&fit=crop&q=80',
        'stock': 45,
        'is_featured': 1,
        'is_active': 1
    },
    {
        'id': 2,
        'category_id': 1,
        'name': 'إيفرمكتين 1% حقن بيطري للماشية (50ml)',
        'slug': 'ivermectin-1-percent-50ml',
        'description': 'مضاد شامل للطفيليات الداخلية (الديدان الرئوية والمعوية) والخارجية (الجرب والقراد والديدان الحلزونية) للأغنام والأبقار والإبل.',
        'price': 6000,
        'compare_at_price': 7500,
        'image_url': 'https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=600&auto=format&fit=crop&q=80',
        'stock': 60,
        'is_featured': 1,
        'is_active': 1
    },
    {
        'id': 3,
        'category_id': 2,
        'name': 'فيتامين AD3E بيطري مركّز عالي الفعالية (100ml)',
        'slug': 'vitamin-ad3e-concentrate-100ml',
        'description': 'مركب فيتامينات لتحفيز النمو وزيادة الخصوبة وتحسين مقاومة الأمراض والوقاية من حالات الكساح ونقص الفيتامينات.',
        'price': 5200,
        'compare_at_price': 6500,
        'image_url': 'https://images.unsplash.com/photo-1628771065518-0d82f1938462?w=600&auto=format&fit=crop&q=80',
        'stock': 35,
        'is_featured': 1,
        'is_active': 1
    },
    {
        'id': 4,
        'category_id': 3,
        'name': 'تحصين ولقاح طاعون المجترات الصغيرة PPR (50 جرعة)',
        'slug': 'ppr-small-ruminants-vaccine-50-doses',
        'description': 'لقاح مبرد حي مجفف بالتجميد لوقاية الضأن والماعز من مرض طاعون المجترات الصغيرة، يشحن في عبوات مبردة خاصة للحفاظ على الفعالية.',
        'price': 18000,
        'compare_at_price': 22000,
        'image_url': 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=600&auto=format&fit=crop&q=80',
        'stock': 15,
        'is_featured': 1,
        'is_active': 1
    },
    {
        'id': 5,
        'category_id': 4,
        'name': 'بخاخ معقم ومطهر الجروح الأوكسي تيترا الأزرق (400ml)',
        'slug': 'blue-spray-wound-antiseptic-400ml',
        'description': 'بخاخ موضعي مطهر ومعالج للجروح والعمليات وتقرحات الحوافر يمنع التلوث الجرثومي ويساعد على الالتئام السريع.',
        'price': 3500,
        'compare_at_price': 4500,
        'image_url': 'https://images.unsplash.com/photo-1583947215259-38e31be8751f?w=600&auto=format&fit=crop&q=80',
        'stock': 50,
        'is_featured': 1,
        'is_active': 1
    },
    {
        'id': 6,
        'category_id': 4,
        'name': 'محقنة بيطرية أوتوماتيكية متدرجة (قابلة لإعادة الاستخدام)',
        'slug': 'veterinary-automatic-dosing-syringe',
        'description': 'محقنة ستانلس ستيل عالية الدقة مع مقبض مريح لجرعات اللقاحات والأدوية من 1ml إلى 5ml مع طقم إبر متين.',
        'price': 9500,
        'compare_at_price': 12000,
        'image_url': 'https://images.unsplash.com/photo-1579154204601-01588f351e67?w=600&auto=format&fit=crop&q=80',
        'stock': 20,
        'is_featured': 0,
        'is_active': 1
    }
]

def init_db():
    if USE_MONGO and mongo_db is not None:
        if mongo_db.settings.count_documents({}) == 0:
            mongo_db.settings.insert_many([{'key': k, 'value': v} for k, v in DEFAULT_SETTINGS.items()])
        else:
            for k, v in DEFAULT_SETTINGS.items():
                mongo_db.settings.update_one({'key': k}, {'$setOnInsert': {'value': v}}, upsert=True)

        if mongo_db.categories.count_documents({}) == 0:
            mongo_db.categories.insert_many(DEFAULT_CATEGORIES)
        if mongo_db.products.count_documents({}) == 0:
            mongo_db.products.insert_many(DEFAULT_PRODUCTS)
        return

    import sqlite3
    if not SQLITE_DB_PATH.startswith('/tmp'):
        os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT,
        icon TEXT DEFAULT 'bi-capsule'
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        compare_at_price REAL,
        image_url TEXT,
        stock INTEGER DEFAULT 10,
        is_featured INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_email TEXT,
        customer_city TEXT NOT NULL,
        customer_address TEXT NOT NULL,
        notes TEXT,
        payment_method TEXT NOT NULL,
        payment_status TEXT DEFAULT 'pending',
        order_status TEXT DEFAULT 'new',
        subtotal REAL NOT NULL,
        shipping_fee REAL DEFAULT 0,
        total REAL NOT NULL,
        currency TEXT DEFAULT 'ر.ي',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        total REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')

    for key, value in DEFAULT_SETTINGS.items():
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))

    cursor.execute('SELECT COUNT(*) FROM categories')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO categories (id, name, slug, description, icon) VALUES (:id, :name, :slug, :description, :icon)', DEFAULT_CATEGORIES)

    cursor.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
        INSERT INTO products (id, category_id, name, slug, description, price, compare_at_price, image_url, stock, is_featured, is_active)
        VALUES (:id, :category_id, :name, :slug, :description, :price, :compare_at_price, :image_url, :stock, :is_featured, :is_active)
        ''', DEFAULT_PRODUCTS)

    conn.commit()
    conn.close()

def get_settings():
    if USE_MONGO and mongo_db is not None:
        docs = list(mongo_db.settings.find())
        res = {d['key']: d['value'] for d in docs}
        for k, v in DEFAULT_SETTINGS.items():
            if k not in res:
                res[k] = v
        return res
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()
    for k, v in DEFAULT_SETTINGS.items():
        if k not in settings:
            settings[k] = v
    return settings

if __name__ == '__main__':
    init_db()
    print("Al-Toofan Veterinary Store Database initialized successfully!")
