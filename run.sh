#!/bin/bash
echo "جاري إيقاف أي سيرفر سابق وتشغيل متجر الطوفان البيطري بنمط الكمبيوتر الدائم..."
pkill -f server.py 2>/dev/null
python3 server.py
