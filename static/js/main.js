// نظام إدارة العملات المتعددة وسعر الصرف
const Currency = {
  KEY: 'store_selected_currency',

  get() {
    return localStorage.getItem(this.KEY) || 'YER';
  },

  set(cur) {
    localStorage.setItem(this.KEY, cur);
    window.location.reload();
  },

  getRates() {
    return {
      'YER': { symbol: 'ر.ي', name: 'ريال يمني', rate: 1.0, decimals: 0 },
      'USD': { symbol: '$', name: 'دولار أمريكي', rate: parseFloat(window.USD_RATE || 535), decimals: 2 },
      'SAR': { symbol: 'ر.س', name: 'ريال سعودي', rate: parseFloat(window.SAR_RATE || 142), decimals: 1 }
    };
  },

  format(amountInYer) {
    const cur = this.get();
    const r = this.getRates()[cur] || this.getRates()['YER'];
    const converted = amountInYer / r.rate;
    const formatted = converted.toLocaleString(undefined, { 
      minimumFractionDigits: r.decimals, 
      maximumFractionDigits: r.decimals 
    });
    return `${formatted} ${r.symbol}`;
  },

  convert(amountInYer) {
    const cur = this.get();
    const r = this.getRates()[cur] || this.getRates()['YER'];
    return amountInYer / r.rate;
  },

  getSymbol() {
    const cur = this.get();
    return (this.getRates()[cur] || this.getRates()['YER']).symbol;
  }
};

window.changeCurrency = function(cur) {
  Currency.set(cur);
};

// إدارة سلة التسوق
const Cart = {
  KEY: 'ecommerce_store_cart_v1',

  getItems() {
    try {
      const data = localStorage.getItem(this.KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      console.error('Error reading cart', e);
      return [];
    }
  },

  saveItems(items) {
    try {
      localStorage.setItem(this.KEY, JSON.stringify(items));
      this.updateBadge();
    } catch (e) {
      console.error('Error saving cart', e);
    }
  },

  addItem(product, qty = 1) {
    const items = this.getItems();
    const existingIndex = items.findIndex(item => item.id === product.id);

    if (existingIndex > -1) {
      items[existingIndex].quantity += qty;
    } else {
      items.push({
        id: product.id,
        name: product.name,
        price: parseFloat(product.price), // يُحفظ دائماً بالريال اليمني الأساسي
        image_url: product.image_url,
        quantity: qty
      });
    }

    this.saveItems(items);
    this.showToast(`تمت إضافة "${product.name}" إلى السلة بنجاح!`);
  },

  updateQuantity(productId, newQty) {
    let items = this.getItems();
    if (newQty <= 0) {
      this.removeItem(productId);
      return;
    }
    const item = items.find(i => i.id === productId);
    if (item) {
      item.quantity = newQty;
      this.saveItems(items);
    }
  },

  removeItem(productId) {
    let items = this.getItems();
    items = items.filter(i => i.id !== productId);
    this.saveItems(items);
    this.showToast('تم حذف المنتج من السلة');
  },

  clear() {
    localStorage.removeItem(this.KEY);
    this.updateBadge();
  },

  getCount() {
    const items = this.getItems();
    return items.reduce((sum, item) => sum + item.quantity, 0);
  },

  getSubtotal() {
    const items = this.getItems();
    return items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  },

  updateBadge() {
    const count = this.getCount();
    const badge = document.getElementById('cart-badge-count');
    if (badge) {
      badge.textContent = count;
      badge.style.display = count > 0 ? 'flex' : 'none';
    }
    const mobileBadge = document.getElementById('mobile-cart-badge-count');
    if (mobileBadge) {
      mobileBadge.textContent = count;
      mobileBadge.style.display = count > 0 ? 'flex' : 'none';
    }
  },

  showToast(message) {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<i class="bi bi-check-circle-fill" style="color:#10b981;font-size:1.2rem;"></i> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }
};

// تهيئة الصفحة وتحويل كافة الأسعار المعروضة بالعملة المختارة
document.addEventListener('DOMContentLoaded', () => {
  Cart.updateBadge();

  // ضبط القيمة الافتراضية لقائمة اختيار العملة
  const switcher = document.getElementById('currency-switcher');
  if (switcher) {
    switcher.value = Currency.get();
  }

  // تحويل كافة الأسعار التي تحمل خاصية data-price في الصفحة تلقائياً
  document.querySelectorAll('[data-price-yer]').forEach(el => {
    const yerPrice = parseFloat(el.dataset.priceYer);
    if (!isNaN(yerPrice)) {
      el.textContent = Currency.format(yerPrice);
    }
  });

  // أزرار الإضافة السريعة للسلة
  document.querySelectorAll('.btn-add-cart').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const p = {
        id: parseInt(btn.dataset.id),
        name: btn.dataset.name,
        price: parseFloat(btn.dataset.price),
        image_url: btn.dataset.image
      };
      Cart.addItem(p, 1);
    });
  });

  // تفاصيل المنتج: التحكم بالكمية
  const qtyInput = document.getElementById('product-qty-input');
  const btnMinus = document.getElementById('btn-qty-minus');
  const btnPlus = document.getElementById('btn-qty-plus');

  if (qtyInput && btnMinus && btnPlus) {
    btnMinus.addEventListener('click', () => {
      let val = parseInt(qtyInput.value) || 1;
      if (val > 1) qtyInput.value = val - 1;
    });
    btnPlus.addEventListener('click', () => {
      let val = parseInt(qtyInput.value) || 1;
      const max = parseInt(qtyInput.max) || 99;
      if (val < max) qtyInput.value = val + 1;
    });
  }

  const btnDetailAdd = document.getElementById('btn-detail-add-cart');
  if (btnDetailAdd) {
    btnDetailAdd.addEventListener('click', () => {
      const qty = parseInt(qtyInput ? qtyInput.value : 1) || 1;
      const p = {
        id: parseInt(btnDetailAdd.dataset.id),
        name: btnDetailAdd.dataset.name,
        price: parseFloat(btnDetailAdd.dataset.price),
        image_url: btnDetailAdd.dataset.image
      };
      Cart.addItem(p, qty);
    });
  }

  // صفحة السلة
  if (document.getElementById('cart-items-tbody')) {
    renderCartPage();
  }

  // صفحة إتمام الطلب
  if (document.getElementById('checkout-form')) {
    initCheckoutPage();
  }
});

// عرض عناصر السلة مع تحويل العملات
function renderCartPage() {
  const container = document.getElementById('cart-items-tbody');
  const emptyState = document.getElementById('cart-empty-state');
  const cartContent = document.getElementById('cart-content-wrapper');
  const subtotalEl = document.getElementById('cart-subtotal-val');
  const totalEl = document.getElementById('cart-total-val');
  const shippingEl = document.getElementById('cart-shipping-val');
  const shippingFee = window.SHIPPING_FEE || 1500;
  const freeThreshold = window.FREE_SHIPPING_THRESHOLD || 25000;

  const items = Cart.getItems();

  if (items.length === 0) {
    if (cartContent) cartContent.style.display = 'none';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  if (cartContent) cartContent.style.display = 'grid';

  let html = '';
  items.forEach(item => {
    const itemTotalYer = item.price * item.quantity;
    html += `
      <div class="cart-item-row" data-id="${item.id}">
        <img src="${item.image_url}" alt="${item.name}" class="cart-item-img">
        <div>
          <h4 style="font-size:1rem;margin-bottom:0.25rem;">${item.name}</h4>
          <span style="color:var(--text-muted);font-size:0.85rem;">${Currency.format(item.price)}</span>
        </div>
        <div style="display:flex;align-items:center;gap:0.3rem;">
          <button class="qty-btn" onclick="updateItemQty(${item.id}, ${item.quantity - 1})">-</button>
          <span style="font-weight:700;padding:0 0.5rem;">${item.quantity}</span>
          <button class="qty-btn" onclick="updateItemQty(${item.id}, ${item.quantity + 1})">+</button>
        </div>
        <div style="font-weight:700;color:var(--primary-color);">
          ${Currency.format(itemTotalYer)}
        </div>
        <div>
          <button style="background:none;border:none;color:var(--danger-color);cursor:pointer;font-size:1.1rem;" onclick="removeCartItem(${item.id})">
            <i class="bi bi-trash3"></i>
          </button>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;

  const subtotalYer = Cart.getSubtotal();
  const shippingYer = subtotalYer >= freeThreshold ? 0 : shippingFee;
  const totalYer = subtotalYer + shippingYer;

  if (subtotalEl) subtotalEl.textContent = Currency.format(subtotalYer);
  if (shippingEl) {
    shippingEl.textContent = shippingYer === 0 ? 'شحن مجاني' : Currency.format(shippingYer);
  }
  if (totalEl) totalEl.textContent = Currency.format(totalYer);
}

window.updateItemQty = function(id, qty) {
  Cart.updateQuantity(id, qty);
  renderCartPage();
};

window.removeCartItem = function(id) {
  Cart.removeItem(id);
  renderCartPage();
};

// صفحة الدفع والطلب
function initCheckoutPage() {
  const items = Cart.getItems();
  if (items.length === 0) {
    alert('سلة التسوق فارغة! سيتم توجيهك للمتجر.');
    window.location.href = '/products';
    return;
  }

  const cartInput = document.getElementById('checkout-cart-items-input');
  if (cartInput) {
    cartInput.value = JSON.stringify(items);
  }

  const curInput = document.getElementById('order_currency_input');
  if (curInput) {
    curInput.value = Currency.get();
  }

  const subtotalYer = Cart.getSubtotal();
  const shippingFee = window.SHIPPING_FEE || 1500;
  const freeThreshold = window.FREE_SHIPPING_THRESHOLD || 25000;
  const shippingYer = subtotalYer >= freeThreshold ? 0 : shippingFee;
  const totalYer = subtotalYer + shippingYer;

  const subEl = document.getElementById('checkout-subtotal');
  const shipEl = document.getElementById('checkout-shipping');
  const totEl = document.getElementById('checkout-total');
  const itemsListEl = document.getElementById('checkout-items-summary');

  if (subEl) subEl.textContent = Currency.format(subtotalYer);
  if (shipEl) shipEl.textContent = shippingYer === 0 ? 'مجاناً' : Currency.format(shippingYer);
  if (totEl) totEl.textContent = Currency.format(totalYer);

  if (itemsListEl) {
    let summaryHtml = '';
    items.forEach(i => {
      summaryHtml += `
        <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;font-size:0.9rem;">
          <span>${i.name} × ${i.quantity}</span>
          <span style="font-weight:600;">${Currency.format(i.price * i.quantity)}</span>
        </div>
      `;
    });
    itemsListEl.innerHTML = summaryHtml;
  }

  const paymentTabs = document.querySelectorAll('.payment-tab');
  const paymentMethodInput = document.getElementById('payment_method_input');
  const codBox = document.getElementById('cod-details-box');
  const whatsappBox = document.getElementById('whatsapp-details-box');
  const onlineBox = document.getElementById('online-details-box');
  const submitBtn = document.getElementById('submit-order-btn');

  paymentTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      paymentTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const method = tab.dataset.method;
      paymentMethodInput.value = method;

      if (codBox) codBox.style.display = method === 'cod' ? 'block' : 'none';
      if (whatsappBox) whatsappBox.style.display = method === 'whatsapp' ? 'block' : 'none';
      if (onlineBox) onlineBox.style.display = method === 'online' ? 'block' : 'none';

      if (submitBtn) {
        if (method === 'whatsapp') {
          submitBtn.className = 'btn btn-whatsapp';
          submitBtn.innerHTML = '<i class="bi bi-whatsapp"></i> إرسال الطلب عبر واتساب وتأكيده';
        } else if (method === 'cod') {
          submitBtn.className = 'btn btn-primary';
          submitBtn.innerHTML = '<i class="bi bi-box-seam"></i> تأكيد الطلب (الدفع عند الاستلام)';
        } else {
          submitBtn.className = 'btn btn-primary';
          submitBtn.innerHTML = '<i class="bi bi-credit-card"></i> إتمام الدفع بالبطاقة';
        }
      }
    });
  });

  const form = document.getElementById('checkout-form');
  if (form) {
    form.addEventListener('submit', (e) => {
      const selectedMethod = paymentMethodInput.value;
      if (selectedMethod === 'whatsapp') {
        const phone = window.STORE_WHATSAPP || '967771954200';
        const name = document.getElementById('customer_name').value;
        const custPhone = document.getElementById('customer_phone').value;
        const city = document.getElementById('customer_city').value;
        const address = document.getElementById('customer_address').value;
        const currentCurrency = Currency.get();
        const currencySymbol = Currency.getSymbol();
        
        let msg = `🛒 *طلب شراء جديد من المتجر*\n\n`;
        msg += `👤 *العميل:* ${name}\n`;
        msg += `📱 *رقم الهاتف:* ${custPhone}\n`;
        msg += `📍 *المدينة والعنوان:* ${city} - ${address}\n\n`;
        msg += `📦 *المنتجات المطلوبة:*\n`;
        items.forEach((item, index) => {
          msg += `${index + 1}. ${item.name} | العدد: ${item.quantity} | السعر: ${Currency.format(item.price * item.quantity)}\n`;
        });
        msg += `\n💰 *إجمالي المنتجات:* ${Currency.format(subtotalYer)}\n`;
        msg += `🚚 *الشحن:* ${shippingYer === 0 ? 'مجاني' : Currency.format(shippingYer)}\n`;
        msg += `🏷️ *الإجمالي المستحق:* ${Currency.format(totalYer)}`;
        if (currentCurrency !== 'YER') {
          msg += ` (ما يعادل: ${totalYer.toLocaleString()} ر.ي)`;
        }
        msg += `\n💳 *طريقة الدفع:* إرسال الطلب عبر واتساب\n\n`;
        msg += `يرجى تأكيد استلام الطلب وتزويدي بالموعد المتوقع للتسليم. شكراً لك!`;

        const whatsappUrl = `https://wa.me/${phone}?text=${encodeURIComponent(msg)}`;
        window.open(whatsappUrl, '_blank');
      }

      setTimeout(() => {
        Cart.clear();
      }, 500);
    });
  }
}
