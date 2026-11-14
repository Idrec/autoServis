# AutoService Manager — Qisqa reja

**Stack:** Django + DRF + Simple JWT + PostgreSQL | React + React Router + Axios + Tailwind + Redux Toolkit

## Rollar
| Rol | Nima qila oladi |
|---|---|
| Admin | Hamma narsa, xodimlarni boshqarish |
| Manager | Mijoz, mashina, buyurtma, usta biriktirish, to'lov, hisobot |
| Mechanic | Faqat o'ziga biriktirilgan buyurtma statusini yangilash, qism qo'shish |
| Client | Faqat o'z mashina va buyurtmalarini ko'rish |

## Status oqimi
`NEW → DIAGNOSTICS → ASSIGNED → IN_PROGRESS → COMPLETED → PAID`
(PAID dan tashqari istalgan bosqichdan `CANCELLED`). O'tishlar bitta funksiya `change_status()` orqali, tarix `OrderStatusHistory` ga yoziladi.

## Modellar
User(role), Car, Service, Part(quantity), Order, OrderService, OrderPart, StockMovement, Payment, OrderStatusHistory
> OrderService/OrderPart da narxni buyurtma paytida nusxalab saqlang.

## Ketma-ketlik
1. **Dizayn:** rollar, status oqimi, ERD, git repo (`backend/`, `frontend/`).
2. **Backend setup:** venv, Django, DRF, PostgreSQL, `.env`, CORS, custom User (birinchi migratsiyadan oldin), Swagger.
3. **Auth:** register, login, refresh, me; rol permissionlari (`IsAdmin`, `IsManager`, `IsMechanic`, `IsClient`).
4. **CRUD:** Cars → Services → Parts (kirim: `restock`, kam qolganlar: `low-stock`).
5. **Buyurtma logikasi (eng muhim):**
   - yaratish (`NEW`) → diagnostika va xizmat tanlash → ustaga biriktirish (`assign`)
   - ta'mirlash: qism qo'shilganda `transaction.atomic()` + `select_for_update()`, qoldiq kamayadi, `StockMovement` yoziladi, `total_price` qayta hisoblanadi
   - yakunlash (`complete`) → to'lov (`pay`) → buyurtma yopiladi, tahrirlanmaydi
   - tarix: filtrlar, mashina tarixi, `orders/my/`
6. **Dashboard API:** summary, daromad, top xizmatlar, ustalar samaradorligi, kam qolgan qismlar.
7. **Testlar:** ruxsatlar, status o'tishlari, ombor qoldig'i, narx hisobi.
8. **Frontend:** Axios + token refresh → Auth → Routing (`ProtectedRoute`, `RoleRoute`) → Layout → sahifalar: Cars, Services, Parts, Orders, Order Detail, Mechanic paneli, Client paneli, Dashboard, Users.
9. **Integratsiya:** to'liq senariyni sinash, production sozlamalari, deploy, README.

## Asosiy endpointlar
`/auth/register|login|refresh|me` · `/cars/` · `/services/` · `/parts/` · `/orders/` (+ `assign`, `start`, `complete`, `pay`, `services`, `parts`) · `/reports/summary|revenue|top-services|mechanics`

## Vaqt (4 hafta)
1-hafta: dizayn, setup, auth | 2-hafta: CRUD, buyurtma yaratish/biriktirish | 3-hafta: ta'mirlash, to'lov, dashboard | 4-hafta: testlar, frontend yakuni, deploy

## Tayyor bo'lish mezoni
- [ ] Rollar to'g'ri ishlaydi
- [ ] Status o'tishlari nazoratda
- [ ] Ombor qoldig'i va umumiy narx avtomatik
- [ ] To'lovdan keyin buyurtma yopiladi
- [ ] Client faqat o'zinikini ko'radi
- [ ] Dashboard to'g'ri, testlar va README tayyor
