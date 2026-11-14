# Rollar va yangi jarayonlar

Foydalanuvchi bergan kengaytirilgan rol talablari avvalgi roadmapdagi zid bandlardan ustun turadi.

| Amal | Admin | Manager | Mechanic | Client |
| --- | --- | --- | --- | --- |
| Xodim yaratish, rol, bloklash/faollashtirish | Ha | Yo‘q | Yo‘q | Yo‘q |
| Mijoz yaratish/tahrirlash | Ha | Ha | Yo‘q | O‘z profilini tahrirlash |
| Foydalanuvchi o‘chirish | Ha | Yo‘q | Yo‘q | Yo‘q |
| Avtomobil yaratish/tahrirlash | Barchasi | Barchasi | Yo‘q | O‘ziniki |
| Buyurtma yaratish/biriktirish | Ha | Ha | Yo‘q | Murojaat yuboradi |
| Diagnostika | Ha | Ha | Biriktirilgan ishga diagnostika qaydi | Ko‘rish |
| Boshlash/yakunlash | Ha | Ha | Faqat biriktirilgan ish | Ko‘rish |
| Xizmat/qism katalogi va narxi | Ha | Ha | Faqat ko‘rish | Faqat ko‘rish |
| Omborga kirim, qism sarflash/qaytarish | Ha | Ha | Yo‘q | Yo‘q |
| Qism so‘rash | So‘rovlarni boshqarish | So‘rovlarni boshqarish | Biriktirilgan ish uchun | Yo‘q |
| To‘lov | Ha | Ha | Yo‘q | Holatini ko‘rish |
| Hisob-faktura | Barcha yakunlanganlar | Barcha yakunlanganlar | Yo‘q | O‘ziniki |
| Fikr va baho | Ko‘rish | Ko‘rish | Ko‘rish | O‘z yakunlangan ishiga |
| Dashboard/hisobot | Barcha ko‘rsatkichlar | Operatsion + moliyaviy | O‘z ishlari va vaqti | O‘z avtomobil/buyurtmalari |
| Jarayonlar jurnali | Ha | Yo‘q | Yo‘q | Yo‘q |

## Mijoz murojaati

`POST /api/repair-requests/`: mijoz o‘z avtomobili va muammo tavsifini yuboradi. Boshlang‘ich holat `PENDING`. Manager/admin `accept` qilganda `NEW` buyurtma yaratiladi; `reject` qilganda javob izohi saqlanadi. Mijoz murojaat holati, javob va yaratilgan buyurtmani kabinetida ko‘radi. Bir murojaatni qayta qabul qilish mumkin emas.

## Usta ish qaydlari va qism so‘rovi

`GET/POST /api/orders/{id}/work-logs/`: diagnostika, qo‘shimcha nosozlik, bajarilgan ish izohi, sarflangan daqiqa. Faqat `ASSIGNED/IN_PROGRESS` buyurtmaga yozish mumkin. Mijoz o‘z buyurtmasining qaydlarini ko‘radi.

`GET/POST /api/orders/{id}/part-requests/`: so‘rovni faqat biriktirilgan usta yuboradi. `GET /api/part-requests/`: admin/manager barcha so‘rovlarni, usta faqat o‘zining hozir ham biriktirilgan ishlaridagi so‘rovlarini ko‘radi. `POST /api/part-requests/{id}/approve|reject/`: faqat admin/manager.

Tasdiqlashda buyurtma → so‘rov → qism qulflanadi; qoldiq, narx snapshoti, ombor harakati, buyurtma summasi va so‘rov statusi bitta tranzaksiyada o‘zgaradi. Qism yetmasa barcha o‘zgarish bekor qilinadi. Takror tasdiqlash qoldiqni takror kamaytirmaydi. `PENDING` so‘rov mavjud bo‘lsa ishni yakunlash mumkin emas. Buyurtma bekor qilinsa pending so‘rovlar ham rad qilinadi.

## Hisob-faktura va fikr

`GET /api/orders/{id}/invoice/`: `COMPLETED/PAID` buyurtmaning raqamlangan hisobi, xizmatlar/qismlar, jami, to‘langan va qoldiq. Frontendda ko‘rish, chop etish yoki brauzer orqali PDF sifatida saqlash mavjud.

`GET/POST/PATCH /api/orders/{id}/feedback/`: o‘z yakunlangan buyurtmasiga bitta fikr va 1–5 baho; mavjud fikr tahrirlanadi. Admin/manager/usta fikr qo‘sha olmaydi.

## Dashboard va audit

`GET /api/dashboard/` foydalanuvchi roli va egaligiga mos statistikani qaytaradi. Admin: mijozlar, avtomobillar, faol/yakunlangan buyurtmalar, jami tushum, ombor mahsulotlari va birliklar. Manager: bugungi/yangi/jarayondagi/kutilayotgan/yakunlangan/to‘lov kutilayotgan ishlar va murojaatlar. Mechanic: biriktirilgan/yangi/jarayondagi/yakunlangan ishlar, pending qism so‘rovlari, vaqt. Client: o‘z avtomobillari, buyurtmalari, ta’mirlashlari, to‘lov kutilayotgan va yakunlangan ishlari.

`GET /api/audit/`: faqat admin. Domen yozuvlari yaratilishi, yangilanishi va o‘chirilishi model signallari orqali qayd etiladi. Jurnal ushbu modul qo‘shilgan paytdan yoziladi; avvalgi buyurtmalar status tarixi ularning tafsilotlarida saqlanadi. Parol yoki tokenlar jurnalga yozilmaydi.

Yangi statuslar berilmagani sabab buyurtma statuslari avvalgi roadmap bo‘yicha saqlandi. Mijoz murojaati va qism so‘rovi holatlari buyurtma statuslaridan alohida.

## Ustaga biriktirish

Manager/admin buyurtma tafsilotidagi «Usta biriktirish» orqali faol ustani tanlaydi. `DIAGNOSTICS` holatida to‘g‘ridan `ASSIGNED` ga o‘tadi. `NEW` holatida shu formaga diagnostika xulosasi ham kiritiladi; backend `NEW → DIAGNOSTICS → ASSIGNED` o‘tishlarini bitta tranzaksiyada, alohida tarix yozuvlari bilan bajaradi. Xulosa yoki faol usta mavjud bo‘lmasa buyurtma o‘zgarmaydi. Biriktirilgan buyurtma ustaning «Mening ishlarim» ro‘yxatida paydo bo‘ladi.
