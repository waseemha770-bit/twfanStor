import sys
import os

# إضافة المسار الرئيسي للتطبيق
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_flask import app, init_db

# تهيئة قاعدة البيانات عند بدء التشغيل
try:
    init_db()
except Exception as e:
    print(f"Init DB notice: {e}")

# Vercel Serverless Function entry point
# متغير app هو تطبيق WSGI الخاص بـ Flask الذي يتعرف عليه Vercel تلقائياً
