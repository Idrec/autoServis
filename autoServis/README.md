# AutoService Manager

Avtoservis uchun Django REST API va React boshqaruv paneli. Talablar `AutoService_Manager_Short.md` va `AutoService_Manager_Roadmap (1).md` asosida amalga oshirildi.

## Lokal ishga tushirish (Windows PowerShell)

Python 3.12+ va Node.js 20.19+ kerak. Birinchi terminalda:

```powershell
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8001
```

Ikkinchi terminalda:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Interfeys: http://127.0.0.1:5173 · API: http://127.0.0.1:8001/api/ · Swagger: http://127.0.0.1:8001/api/docs/

Lokal frontend dev va preview serverlari `/api` so‘rovlarini `8001` portiga yuboradi. Backendni `run.cmd` yoki yuqoridagi buyruq bilan aynan shu portda ishga tushiring. Vite config o‘zgarsa frontend serverini qayta ishga tushiring. React DevTools xabari xato emas.

Demo loginlar: `admin`, `manager`, `mechanic`, `client`, `client2`. Barchasining paroli: `DemoPass123!`. `seed` mavjud foydalanuvchi parollarini o‘zgartirmaydi, takror ishga tushirishda buyurtmalarni ko‘paytirmaydi. Demo hisoblar faqat lokal sinov uchun.

## Imkoniyatlar

- JWT login, refresh, mijoz registratsiyasi, profil va parol API.
- Admin: foydalanuvchilar, rollar, bloklash/faollashtirish, barcha modullar va jarayonlar jurnali. Manager: mijoz yaratish/tahrirlash, avtomobil, katalog, buyurtma, hisob-faktura, to‘lov va hisobotlar. Usta: faqat biriktirilgan ishlar, ishni boshlash/yakunlash, diagnostika/izoh/vaqt qaydlari va qism so‘rovlari. Mijoz: profil, o‘z avtomobillari, ta’mirlash so‘rovlari, buyurtmalar, hisob-fakturalar va fikrlar.
- Buyurtma: diagnostika → xizmatlar → usta → ta’mirlash → yakunlash → qisman/to‘liq to‘lov. Narxlar buyurtma paytidagi nusxada saqlanadi.
- Ombor: kirim, sarf, qaytarish va kam qoldiq nazorati. Qoldiqni oddiy PATCH orqali o‘zgartirish taqiqlangan.
- Dashboard: statuslar, tushum, ommabop xizmatlar, ustalar samaradorligi, kam qolgan qismlar.
- Qidiruv, filtrlar, avtomobil ta’mirlash tarixi, buyurtma timeline, moslashuvchan o‘zbekcha interfeys.
- Har bir rol uchun alohida dashboard; sana, status, mijoz va usta bo‘yicha buyurtma filtrlari.
- Mijoz murojaati manager qabul qilganda buyurtmaga aylanadi. Usta qism so‘raganda qoldiq o‘zgarmaydi; manager/admin tasdiqlaganda qism tranzaksiyada sarflanadi.
- Elektron hisob-fakturani ko‘rish va chop etish/PDF saqlash; yakunlangan xizmatga 1–5 baho va fikr.

## Muhim qarorlar

Backend modullari ixchamlik uchun bitta `core` Django ilovasida, biznes amallari `core/services.py` da saqlanadi. Frontend holati React Context orqali boshqariladi (roadmapda ruxsat etilgan variant).

`COMPLETED` holatidan ham to‘lov bo‘lmasa bekor qilish mumkin. Bekor qilish qismlarni bir marta omborga qaytaradi; buyurtma qatorlari va summasi tarix uchun saqlanadi. To‘lov mavjud buyurtmani bekor qilish taqiqlangan; refund alohida kelgusi modul. `PAID` va `CANCELLED` yakuniy, `COMPLETED` narxlari ham muzlatilgan. Qisman to‘lovlar yig‘indisi jami summaga tenglashganda buyurtma yopiladi.

Katalogdagi ishlatilgan yozuvlar tarixni himoyalash uchun o‘chirilmaydi. Xizmatni `is_active=false` qilish mumkin. Manager mijoz yaratadi va tahrirlaydi, lekin xodim, rol, hisob bloklash yoki foydalanuvchi o‘chirish huquqiga ega emas. Admin mijoz va xodim hisoblarini boshqaradi; mijozlar o‘zlari ham registratsiya qilishi mumkin. Batafsil: [docs/roles.md](docs/roles.md).

## PostgreSQL va production

Lokal boshlash uchun standart SQLite. `.env` da `DB_ENGINE=postgres` va `POSTGRES_*` parametrlarini belgilang, keyin `migrate` bajaring. Ombor raqobatli amallarida `select_for_update()` haqiqiy qator qulfini PostgreSQL bilan beradi; SQLite bu kafolatni bermaydi.

Docker orqali PostgreSQL + backend:

```powershell
docker compose up --build -d
docker compose exec backend python manage.py migrate
```

Frontend uchun `VITE_API_URL=https://api.example.com/api/` build muhit o‘zgaruvchisini belgilang, `npm.cmd run build` bajaring va `frontend/dist` ni SPA fallback (`index.html`) bilan statik hostingga joylang. Yoki bitta domen reverse proxy orqali `/api/` ni backendga yo‘naltiring.

Production uchun `.env` da `DEBUG=False`, kuchli `SECRET_KEY`, haqiqiy `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, PostgreSQL paroli, HTTPS va zaxira nusxalarini sozlang. Docker sozlamasi lokal infratuzilma uchun; ommaga chiqarishdan oldin TLS/reverse proxy va production WSGI serverini sozlang. Tashqi hostingga deploy bajarilmagan.

## Tekshiruv

```powershell
cd backend
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py test
.venv/Scripts/python.exe manage.py spectacular --file schema.yml
cd ../frontend
npm.cmd run build
```

Testlar: to‘liq status oqimi, snapshot narxi, qisman to‘lov, yopilgandan keyingi cheklovlar, ruxsat va ma’lumot izolyatsiyasi, qism yetishmasligi, qaytarish, kirim, bekor qilish, JWT, registratsiyada rolni oshira olmaslik, avtomobil egasi validatsiyasi.
