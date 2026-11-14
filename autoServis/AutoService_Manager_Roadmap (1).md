# AutoService Manager — Bajarish ketma-ketligi (Roadmap)

**Maqsad:** avtoservisdagi avtomobil qabul qilish, ta'mirlash, ehtiyot qismlar hisobi va to'lov jarayonlarini yagona tizimda avtomatlashtirish.

**Stack:** Django + DRF + Simple JWT + PostgreSQL | React + React Router + Axios + Tailwind CSS + Redux Toolkit/useContext

---

## 0. Umumiy tartib (qisqa xarita)

```
1. Tahlil va dizayn  →  2. Backend asos  →  3. Auth va rollar  →  4. Asosiy modullar
→  5. Buyurtma logikasi (yurak)  →  6. Dashboard  →  7. Frontend  →  8. Integratsiya  →  9. Test va deploy
```

> Qoida: avval **backend to'liq ishlasin (Postman/Swagger orqali)**, keyin frontend. Buyurtma logikasi (5-bosqich) eng muhim va eng murakkab — unga ko'proq vaqt ajrating.

---

## 1-BOSQICH. Tahlil va dizayn

1. Rollar va ruxsatlarni aniqlash (jadval pastda).
2. Buyurtma hayot sikli (status oqimi) ni chizib olish.
3. ERD (ma'lumotlar bazasi sxemasi) tuzish.
4. API endpointlar ro'yxatini yozib chiqish.
5. Git repo yaratish: `backend/` va `frontend/` papkalari, branch strategiyasi (`main`, `dev`, `feature/*`).

### 1.1. Rollar va imkoniyatlar

| Imkoniyat | Admin | Manager | Mechanic | Client |
|---|:-:|:-:|:-:|:-:|
| Foydalanuvchilarni boshqarish | ✅ | ❌ | ❌ | ❌ |
| Mijoz va avtomobillarni boshqarish | ✅ | ✅ | ❌ | faqat o'zinikini |
| Buyurtma yaratish | ✅ | ✅ | ❌ | ❌ |
| Ustaga biriktirish | ✅ | ✅ | ❌ | ❌ |
| Xizmat/ehtiyot qismlarni boshqarish (CRUD) | ✅ | ✅ (qisman) | ❌ | ❌ |
| Ta'mirlash statusini yangilash | ✅ | ✅ | faqat o'ziga biriktirilgan | ❌ |
| Buyurtmani ko'rish | hammasi | hammasi | o'ziga biriktirilgan | faqat o'zining |
| To'lovni qabul qilish / yopish | ✅ | ✅ | ❌ | ❌ |
| Dashboard va hisobotlar | ✅ | ✅ (cheklangan) | ❌ | ❌ |

### 1.2. Buyurtma status oqimi

```
NEW (yangi)
  ↓ diagnostika boshlanadi
DIAGNOSTICS (diagnostika)
  ↓ manager usta tayinlaydi
ASSIGNED (ustaga biriktirilgan)
  ↓ usta ishni boshlaydi
IN_PROGRESS (ta'mirlanmoqda)
  ↓ usta ishni tugatadi
COMPLETED (ta'mir tugadi, to'lovga tayyor)
  ↓ to'lov qabul qilinadi
PAID / CLOSED (yopildi)

Istalgan bosqichdan (CLOSED dan tashqari) → CANCELLED (bekor qilindi)
```

**Ruxsat etilgan o'tishlar** (kodda `ALLOWED_TRANSITIONS` lug'ati sifatida saqlang):

| Joriy status | Keyingi mumkin statuslar | Kim o'zgartiradi |
|---|---|---|
| NEW | DIAGNOSTICS, CANCELLED | Manager/Admin |
| DIAGNOSTICS | ASSIGNED, CANCELLED | Manager/Admin |
| ASSIGNED | IN_PROGRESS, CANCELLED | Mechanic / Manager |
| IN_PROGRESS | COMPLETED, CANCELLED | Mechanic / Manager |
| COMPLETED | PAID | Manager/Admin |
| PAID | — (yakuniy) | — |

### 1.3. ERD — asosiy jadvallar (modellar)

| Model | Asosiy maydonlar |
|---|---|
| **User** (custom, `AbstractUser`) | username, email, phone, full_name, `role` (admin/manager/mechanic/client) |
| **Car** | owner (FK→User/client), brand, model, year, plate_number (unique), vin, mileage |
| **Service** (xizmat turi) | name, description, price, estimated_hours, is_active |
| **Part** (ehtiyot qism) | name, sku (unique), price, quantity (ombor qoldig'i), min_quantity, unit |
| **Order** | client, car, mechanic (null), manager, status, problem_description, diagnosis_notes, total_price, created_at, updated_at, closed_at |
| **OrderService** | order, service, price (narx *snapshot*), quantity |
| **OrderPart** | order, part, price (snapshot), quantity |
| **StockMovement** (ombor harakati) | part, order (null), change (+/−), reason (purchase/usage/return/correction), created_by, created_at |
| **Payment** | order, amount, method (cash/card/transfer), paid_at, received_by |
| **OrderStatusHistory** | order, old_status, new_status, changed_by, changed_at, comment |

> ⚠️ **Muhim:** `OrderService.price` va `OrderPart.price` ni buyurtma paytidagi narx sifatida *nusxalab* saqlang. Aks holda keyin xizmat narxi o'zgarsa, eski buyurtmalar summasi ham o'zgarib ketadi.

---

## 2-BOSQICH. Backend loyihasini tayyorlash

1. Virtual muhit yaratish, paketlarni o'rnatish:
   ```bash
   python -m venv venv
   pip install django djangorestframework djangorestframework-simplejwt \
       psycopg2-binary django-cors-headers django-filter drf-spectacular python-decouple
   ```
2. `django-admin startproject config .`
3. PostgreSQL bazasini yaratish va `settings.py` ga ulash (parol/kalitlarni `.env` ga chiqarish).
4. Ilovalarni (apps) yaratish:
   ```
   accounts/   — User, auth, rollar
   cars/       — Car
   catalog/    — Service, Part
   inventory/  — StockMovement (yoki catalog ichida)
   orders/     — Order, OrderService, OrderPart, StatusHistory
   payments/   — Payment
   reports/    — dashboard/statistika
   ```
5. `settings.py` sozlamalari: `REST_FRAMEWORK`, `SIMPLE_JWT`, `CORS_ALLOWED_ORIGINS`, `AUTH_USER_MODEL`.
6. **Custom User modelini birinchi migratsiyadan oldin** yarating (keyin o'zgartirish qiyin).
7. `drf-spectacular` orqali Swagger (`/api/docs/`) ni yoqish — frontend dasturchi uchun ham qulay.

---

## 3-BOSQICH. Autentifikatsiya va rollar (JWT)

1. `User` modeli + `role` maydoni.
2. Endpointlar:
   - `POST /api/auth/register/` — ro'yxatdan o'tish (faqat `client` roli bilan)
   - `POST /api/auth/login/` — `access` + `refresh` token
   - `POST /api/auth/refresh/` — tokenni yangilash
   - `GET/PATCH /api/auth/me/` — profil
   - `POST /api/auth/change-password/`
3. Admin tomonidan xodim (manager/mechanic) yaratish: `POST /api/users/` (faqat Admin).
4. Custom permission klasslari (`accounts/permissions.py`):
   - `IsAdmin`, `IsManager`, `IsMechanic`, `IsClient`
   - `IsAdminOrManager`
   - `IsOrderParticipant` (object-level: client faqat o'zinikini, mechanic faqat o'ziga biriktirilganini ko'radi)
5. **Tekshiruv:** Postman'da har bir rol bilan login qilib, ruxsatlar jadvali bo'yicha sinab ko'ring.

---

## 4-BOSQICH. Yordamchi modullar (CRUD)

Tartib bo'yicha:

### 4.1. Cars (avtomobillar)
- `GET/POST /api/cars/`, `GET/PUT/DELETE /api/cars/{id}/`
- Client faqat o'z mashinalarini ko'radi (`get_queryset` ni filtrlang).
- Validatsiya: `plate_number` unikal, `year` mantiqiy diapazonda.

### 4.2. Services (xizmatlar katalogi)
- CRUD (yozish — Admin/Manager, o'qish — hamma).
- Filtr va qidiruv: `?search=`, `?is_active=true`.

### 4.3. Parts (ehtiyot qismlar ombori)
- CRUD + qoldiq (`quantity`) maydoni.
- `POST /api/parts/{id}/restock/` — omborga kirim (StockMovement `purchase` yozuvi bilan).
- `GET /api/parts/low-stock/` — qoldig'i `min_quantity` dan kam qismlar ro'yxati.
- Qoldiqni to'g'ridan-to'g'ri PATCH bilan o'zgartirishga yo'l qo'ymang — faqat `StockMovement` orqali.

---

## 5-BOSQICH. Buyurtma logikasi (asosiy jarayon)

Bu loyihaning yuragi. Quyidagi tartibda quring:

### 5.1. Order yaratish — *1-qadam: Yangi buyurtma*
- `POST /api/orders/` (Manager/Admin)
- Kirish: `client`, `car`, `problem_description`.
- Validatsiya: mashina shu mijozga tegishli bo'lishi kerak.
- Boshlang'ich status: `NEW`; `OrderStatusHistory` ga yozuv.

### 5.2. Diagnostika — *2-qadam*
- `PATCH /api/orders/{id}/diagnose/` — `diagnosis_notes` kiritiladi, status → `DIAGNOSTICS`.
- `POST /api/orders/{id}/services/` — kerakli xizmatlarni qo'shish (`OrderService`, narx snapshot).
- `DELETE /api/orders/{id}/services/{item_id}/` — xizmatni olib tashlash.
- Har o'zgarishda `total_price` qayta hisoblanadi.

### 5.3. Ustaga biriktirish — *3-qadam*
- `POST /api/orders/{id}/assign/` — body: `{ "mechanic": <id> }` (Manager/Admin).
- Tekshiruv: tanlangan foydalanuvchi roli `mechanic` bo'lishi kerak.
- Status → `ASSIGNED`.
- (Ixtiyoriy) ustaning band bo'lgan buyurtmalari sonini ko'rsatish.

### 5.4. Ta'mirlash — *4-qadam*
- `POST /api/orders/{id}/start/` — Mechanic ishni boshlaydi, status → `IN_PROGRESS`.
- `POST /api/orders/{id}/parts/` — ishlatilgan ehtiyot qismni qo'shish:
  1. `transaction.atomic()` ichida bajariladi;
  2. `Part` qatori `select_for_update()` bilan qulflanadi (bir vaqtda ikki usta bir xil qismni olmasligi uchun);
  3. Qoldiq yetarlimi tekshiriladi — yetmasa `400` xato;
  4. `Part.quantity -= n`;
  5. `StockMovement` (`usage`, manfiy) yoziladi;
  6. `OrderPart` yaratiladi (narx snapshot);
  7. `total_price` qayta hisoblanadi.
- `DELETE /api/orders/{id}/parts/{item_id}/` — qismni qaytarish: qoldiq qayta oshadi (`return` harakati), summa yangilanadi.

### 5.5. Yakunlash — *5-qadam*
- `POST /api/orders/{id}/complete/` — Mechanic ta'mirni tugatadi, status → `COMPLETED`.
- Shu paytda yakuniy hisob-kitob: `total_price = Σ(xizmatlar) + Σ(ehtiyot qismlar)`.
- Mijozga bildirishnoma (ixtiyoriy, keyingi bosqichda).

### 5.6. To'lov va yopish
- `POST /api/orders/{id}/pay/` — Payment yaratiladi (summa, usul), status → `PAID`, `closed_at` to'ldiriladi.
- Qisman to'lov kerak bo'lsa: Payment'lar yig'indisi `total_price` ga teng bo'lganda yopiladi.
- `PAID` buyurtmani tahrirlash taqiqlanadi.

### 5.7. Statuslarni avtomatik boshqarish
- Barcha status o'zgarishlari **bitta servis funksiyasi** orqali o'tsin: `change_status(order, new_status, user)`.
  - `ALLOWED_TRANSITIONS` bo'yicha o'tishni tekshiradi;
  - rolni tekshiradi;
  - `OrderStatusHistory` ga yozadi.
- Biznes logikani `views.py` ga emas, `orders/services.py` ga joylashtiring — test qilish oson bo'ladi.
- `total_price` ni qayta hisoblash uchun `recalculate_total(order)` funksiyasi (yoki signal) yarating.

### 5.8. Buyurtmalar tarixi
- `GET /api/orders/` — filtrlar: `status`, `client`, `mechanic`, `car`, `date_from/date_to`, `search`; paginatsiya.
- `GET /api/orders/{id}/` — to'liq tafsilot: xizmatlar, qismlar, status tarixi, to'lovlar.
- `GET /api/cars/{id}/history/` — mashinaning barcha ta'mirlari tarixi.
- Client uchun: `GET /api/orders/my/`.

---

## 6-BOSQICH. Dashboard va statistika (backend)

`reports/` ilovasida (Admin/Manager):

| Endpoint | Ma'lumot |
|---|---|
| `GET /api/reports/summary/` | Jami buyurtmalar, statuslar bo'yicha soni, bugungi/oylik daromad |
| `GET /api/reports/revenue/?period=month` | Davr bo'yicha daromad (kun/hafta/oy kesimida) |
| `GET /api/reports/top-services/` | Eng ko'p buyurtma qilingan xizmatlar |
| `GET /api/reports/mechanics/` | Ustalar samaradorligi (tugatilgan ishlar soni, daromad) |
| `GET /api/reports/low-stock/` | Tugayotgan ehtiyot qismlar |

Django ORM: `annotate`, `aggregate`, `Sum`, `Count`, `TruncDate/TruncMonth` dan foydalaning.

---

## 7-BOSQICH. Backend testlari va hujjat

1. Unit/API testlar (`pytest-django` yoki `APITestCase`). Eng avval quyidagilarni test qiling:
   - ruxsatlar (rol → endpoint);
   - status o'tishlari (taqiqlangan o'tish xato berishi);
   - ombor qoldig'i kamayishi va yetarli bo'lmasa xato;
   - `total_price` to'g'ri hisoblanishi;
   - qaytarilganda qoldiq tiklanishi.
2. Test ma'lumotlari: `python manage.py loaddata` yoki `seed` buyrug'i (har rolga 1–2 ta foydalanuvchi, bir nechta xizmat va qism).
3. Swagger hujjatini tekshirish, README yozish.

---

## 8-BOSQICH. Frontend (React)

### 8.1. Tayyorgarlik
```bash
npm create vite@latest frontend -- --template react
npm i react-router-dom axios @reduxjs/toolkit react-redux
npm i -D tailwindcss postcss autoprefixer
```
Papka tuzilmasi:
```
src/
  api/          — axios instance, interceptorlar
  app/          — store (Redux Toolkit) yoki context
  components/   — umumiy komponentlar (Button, Modal, Table, Badge)
  features/     — auth, orders, cars, parts, services, dashboard
  layouts/      — AdminLayout, ClientLayout
  pages/
  routes/       — ProtectedRoute, RoleRoute
```

### 8.2. Ketma-ketlik
1. **Axios instance:** `baseURL`, request interceptor (`Authorization: Bearer <access>`), response interceptor (401 bo'lsa `refresh` orqali tokenni yangilab, so'rovni qaytarish).
2. **Auth:** Login va Register sahifalari, token saqlash (localStorage), `useAuth` / `authSlice`.
3. **Routing:** `ProtectedRoute` (login talab qiladi) va `RoleRoute` (rol bo'yicha) komponentlari.
4. **Layout:** Sidebar (rolga qarab menyu o'zgaradi) + Header.
5. **Sahifalar (tartib bilan):**

| № | Sahifa | Kim uchun |
|---|---|---|
| 1 | Login / Register | hamma |
| 2 | Cars — ro'yxat va qo'shish/tahrirlash formasi | Manager, Client |
| 3 | Services — katalog boshqaruvi | Admin, Manager |
| 4 | Parts — ombor, qoldiq, kirim qilish, kam qolganlar belgisi | Admin, Manager |
| 5 | Orders — ro'yxat (filtr, status badge, qidiruv) | Admin, Manager |
| 6 | Order Create — mijoz + mashina tanlash, muammo tavsifi | Manager |
| 7 | Order Detail — xizmat/qism qo'shish, ustani tayinlash, status tugmalari, to'lov | Manager |
| 8 | Mechanic Panel — "Mening ishlarim", statusni yangilash, qism qo'shish | Mechanic |
| 9 | Client Panel — "Mening buyurtmalarim", status kuzatuvi (timeline), tarix | Client |
| 10 | Dashboard — kartalar + grafiklar (Recharts/Chart.js) | Admin, Manager |
| 11 | Users — xodimlarni boshqarish | Admin |

6. Umumiy UX: loading holati, xatolarni ko'rsatish (toast), tasdiqlash modali, bo'sh holat (empty state), responsive dizayn (Tailwind).

---

## 9-BOSQICH. Integratsiya va yakuniy ishlar

1. Frontend–backend to'liq jarayonni sinab chiqish (end-to-end senariy):
   > Client ro'yxatdan o'tadi → mashina qo'shadi → Manager buyurtma yaratadi → diagnostika va xizmat tanlaydi → ustaga biriktiradi → Mechanic ishni boshlaydi va qism qo'shadi (ombor kamayadi) → tugatadi → Manager to'lovni qabul qiladi → Client natijani ko'radi → Dashboard'da statistika yangilanadi.
2. Xatolarni tuzatish, validatsiyalarni qayta ko'rib chiqish.
3. CORS, `DEBUG=False`, `ALLOWED_HOSTS`, `SECRET_KEY` — production sozlamalari.
4. Deploy (ixtiyoriy): Docker Compose (django + postgres + nginx), frontend uchun `npm run build`.
5. Yakuniy README: o'rnatish, `.env` namunasi, test foydalanuvchilar, API hujjati havolasi.
6. Taqdimot uchun demo ma'lumotlar va ekran rasmlari tayyorlash.

---

## Jamoa uchun taxminiy vaqt jadvali (4 hafta)

| Hafta | Backend | Frontend |
|---|---|---|
| 1 | 1–3 bosqich: dizayn, setup, JWT, rollar | Setup, Axios, Login/Register, routing, layout |
| 2 | 4–5.4 bosqich: Cars, Services, Parts, Order yaratish/biriktirish/qism qo'shish | Cars, Services, Parts sahifalari |
| 3 | 5.5–6 bosqich: yakunlash, to'lov, tarix, dashboard API | Orders, Order Detail, Mechanic va Client panellari |
| 4 | 7-bosqich: testlar, hujjat | Dashboard, UX tuzatishlar, 9-bosqich: integratsiya, deploy, taqdimot |

---

## Tekshiruv ro'yxati (Definition of Done)

- [ ] 4 ta rol uchun ruxsatlar to'g'ri ishlaydi
- [ ] JWT login/refresh ishlaydi, frontendda avtomatik yangilanadi
- [ ] Buyurtma barcha statuslardan to'g'ri o'tadi, taqiqlangan o'tishlar rad etiladi
- [ ] Ehtiyot qism qo'shilganda ombor qoldig'i kamayadi, yetmasa xato beradi
- [ ] Umumiy narx avtomatik va to'g'ri hisoblanadi
- [ ] To'lovdan keyin buyurtma yopiladi va tahrirlanmaydi
- [ ] Client faqat o'z ma'lumotlarini ko'radi
- [ ] Dashboard to'g'ri raqamlarni ko'rsatadi
- [ ] Asosiy biznes logikasi testlar bilan qoplangan
- [ ] README va Swagger hujjati tayyor
