"""
UI matnlari — Uzbek / English / Russian
"""

_UZ = {
    # Onboarding
    "choose_lang":      "🌐 Tilni tanlang:",
    "lang_uz":          "🇺🇿 O'zbek tili",
    "lang_en":          "🇬🇧 Ingliz tili",
    "lang_ru":          "🇷🇺 Rus tili",
    "enter_name":       "✏️ Ismingizni kiriting:",
    "name_saved":       "Salom, {name}! 👋",
    "choose_tariff":    "💎 Tarifdan birini tanlang:",

    # Tarif tugmalari
    "btn_free":         "🆓 Bepul",
    "btn_trial":        "🎁 7 kun sinov (bepul)",
    "btn_3m":           "💰 3 oy — 100 so'm",
    "btn_6m":           "💰 6 oy — 130 so'm",
    "btn_12m":          "💰 12 oy — 300 so'm",

    # Tarif tavsiflari
    "desc_free": (
        "🆓 <b>Bepul tarif</b>\n\n"
        "✅ Kunlik / haftalik / oylik statistika\n"
        "✅ 100 tagacha mahsulot saqlash\n"
        "❌ Diagramma va grafik yo'q\n"
        "❌ OCR (chek rasmi o'qish) yo'q\n\n"
        "Asosiy funksiyalar doim tekin!"
    ),
    "desc_trial": (
        "🎁 <b>7 kunlik bepul sinov</b>\n\n"
        "✅ Barcha premium imkoniyatlar\n"
        "✅ Diagramma va grafiklar\n"
        "✅ OCR orqali chek o'qish\n"
        "✅ Push bildirishnomalar\n"
        "⚠️ Har foydalanuvchiga faqat 1 marta beriladi"
    ),
    "desc_premium": (
        "💎 <b>Premium tarif imkoniyatlari</b>\n\n"
        "✅ To'liq statistika (kunlik/haftalik/oylik/yillik)\n"
        "✅ Diagramma va grafik (matplotlib)\n"
        "✅ OCR orqali chek rasmi o'qish\n"
        "✅ Jadvalda saqlash, CSV/Excel eksport\n"
        "✅ Budjet limiti ogohlantirishlari\n"
        "✅ Kategoriya bo'yicha tahlil\n"
        "✅ Push bildirishnomalar"
    ),

    # Tarif holatlari
    "trial_activated":  "🎁 7 kunlik sinov faollashtirildi! {expires} gacha amal qiladi.",
    "trial_already":    "⚠️ Siz avval bepul sinovdan foydalangansiz.",
    "trial_expired":    "⏰ Sinovingiz muddati tugadi. /tarif orqali yangilang.",
    "sub_activated":    "✅ <b>{label}</b> tarif faollashtirildi!\n📅 Muddat: {expires} gacha.",
    "sub_expired":      "⏰ Tarifingiz muddati tugadi. /tarif orqali yangilang.",
    "sub_info":         "📋 <b>Tarifingiz:</b> {tier}\n📅 <b>Muddat:</b> {expires}",
    "pay_info": (
        "💳 <b>{label}</b>\n\n"
        "To'lov uchun admin bilan bog'laning:\n"
        "@xisobchi_admin\n\n"
        "To'lovdan so'ng admin sizning ID raqamingizni: <code>{uid}</code>\n"
        "kiritadi va tarif avtomatik faollashadi."
    ),

    # Kirish cheklovi
    "premium_only": (
        "🔒 Bu imkoniyat faqat premium foydalanuvchilar uchun.\n"
        "/tarif — tariflarni ko'rish"
    ),
    "free_limit": (
        "⚠️ Bepul tarifda 100 ta mahsulot limiti to'ldi.\n"
        "Premium tarifga o'ting: /tarif"
    ),

    # Asosiy menyular
    "help_text": (
        "📖 <b>Yordam</b>\n\n"
        "✍️ <code>olma 15000</code> — mahsulot + narx\n"
        "✍️ <code>non 5000\nkola 8000</code> — ko'p qator\n"
        "🖼️ PNG/JPG chek (premium) — rasm sifatida yuboring\n"
        "📄 PDF chek (premium) — hujjat sifatida yuboring\n\n"
        "/stats — statistika\n"
        "/chart — grafik (premium)\n"
        "/cats — kategoriyalar (premium)\n"
        "/tarif — tarif ma'lumotlari\n"
        "/lang — tilni o'zgartirish\n"
        "/clear — hammasini o'chirish"
    ),

    # Tugmalar (asosiy menyu)
    "btn_week":     "📅 Haftalik",
    "btn_month":    "🗓️ Oylik",
    "btn_all":      "📊 Barchasi",
    "btn_chart":    "📈 Grafik",
    "btn_cats":     "🏷️ Kategoriya",
    "btn_stats":    "📉 Statistika",
    "btn_clear":    "🗑️ Tozalash",
    "btn_yes":      "✅ Ha",
    "btn_no":       "❌ Yo'q",
    "btn_7days":    "📅 7 kunlik",
    "btn_30days":   "🗓️ 30 kunlik",
    "btn_tarif":    "💎 Tarif",

    # Xabarlar
    "no_expense":   "📭 Harajatlar yo'q.",
    "no_chart":     "📭 Grafik uchun ma'lumot yo'q.",
    "which_period": "📈 Qaysi davr?",
    "confirm_clear":"⚠️ Barcha harajatlarni o'chirish?",
    "cleared":      "🗑️ {count} ta harajat o'chirildi.",
    "cancelled":    "✅ Bekor qilindi.",
    "no_number":    "ℹ️ Raqam topilmadi.\nMasalan: <code>olma 15000</code>",
    "reading_img":  "🔍 Rasm o'qilmoqda...",
    "reading_pdf":  "🔍 PDF o'qilmoqda...",
    "ocr_fail": (
        "❌ <b>Chekdan mahsulot topib bo'lmadi.</b>\n\n"
        "💡 Maslahat:\n"
        "• Rasmni to'g'ri (egiltirmasdan) oling\n"
        "• Yaxshi yoritilgan bo'lsin\n"
        "• Qo'lda yozing: <code>olma 15000</code>"
    ),
    "format_unsupported": (
        "❌ Format qo'llab-quvvatlanmaydi.\n"
        "✅ Qabul qilinadigan: <b>PDF, PNG, JPG, WebP</b>"
    ),
}

_EN = dict(_UZ)
_EN.update({
    "choose_lang":      "🌐 Choose your language:",
    "lang_uz":          "🇺🇿 Uzbek",
    "lang_en":          "🇬🇧 English",
    "lang_ru":          "🇷🇺 Russian",
    "enter_name":       "✏️ Enter your name:",
    "name_saved":       "Hello, {name}! 👋",
    "choose_tariff":    "💎 Choose a plan:",

    "btn_free":         "🆓 Free",
    "btn_trial":        "🎁 7-day trial (free)",
    "btn_3m":           "💰 3 months — 100 sum",
    "btn_6m":           "💰 6 months — 130 sum",
    "btn_12m":          "💰 12 months — 300 sum",

    "desc_free": (
        "🆓 <b>Free plan</b>\n\n"
        "✅ Daily / weekly / monthly statistics\n"
        "✅ Up to 100 saved products\n"
        "❌ No charts or diagrams\n"
        "❌ No OCR (receipt scanning)\n\n"
        "Core features are always free!"
    ),
    "desc_trial": (
        "🎁 <b>7-day free trial</b>\n\n"
        "✅ All premium features\n"
        "✅ Charts and diagrams\n"
        "✅ OCR receipt scanning\n"
        "✅ Push notifications\n"
        "⚠️ Given only once per user"
    ),
    "desc_premium": (
        "💎 <b>Premium plan features</b>\n\n"
        "✅ Full statistics (daily/weekly/monthly/yearly)\n"
        "✅ Charts & graphs (matplotlib)\n"
        "✅ OCR receipt scanning\n"
        "✅ Table storage & CSV/Excel export\n"
        "✅ Budget limit alerts\n"
        "✅ Category analysis\n"
        "✅ Push notifications"
    ),

    "trial_activated":  "🎁 7-day trial activated! Valid until {expires}.",
    "trial_already":    "⚠️ You have already used the free trial.",
    "trial_expired":    "⏰ Your trial has expired. Upgrade at /tarif.",
    "sub_activated":    "✅ <b>{label}</b> plan activated!\n📅 Valid until: {expires}.",
    "sub_expired":      "⏰ Your plan has expired. Renew at /tarif.",
    "sub_info":         "📋 <b>Your plan:</b> {tier}\n📅 <b>Expires:</b> {expires}",
    "pay_info": (
        "💳 <b>{label}</b>\n\n"
        "Contact admin to pay:\n"
        "@xisobchi_admin\n\n"
        "After payment, send your ID: <code>{uid}</code>\n"
        "Your plan will be activated automatically."
    ),

    "premium_only": (
        "🔒 This feature is for premium users only.\n"
        "/tarif — view plans"
    ),
    "free_limit": (
        "⚠️ Free plan limit of 100 products reached.\n"
        "Upgrade at /tarif"
    ),

    "help_text": (
        "📖 <b>Help</b>\n\n"
        "✍️ <code>apple 15000</code> — product + amount\n"
        "✍️ <code>bread 5000\ncola 8000</code> — multiple lines\n"
        "🖼️ PNG/JPG receipt (premium) — send as photo\n"
        "📄 PDF receipt (premium) — send as document\n\n"
        "/stats — statistics\n"
        "/chart — chart (premium)\n"
        "/cats — categories (premium)\n"
        "/tarif — plan info\n"
        "/lang — change language\n"
        "/clear — clear all"
    ),

    "btn_week":     "📅 Weekly",
    "btn_month":    "🗓️ Monthly",
    "btn_all":      "📊 All",
    "btn_chart":    "📈 Chart",
    "btn_cats":     "🏷️ Categories",
    "btn_stats":    "📉 Statistics",
    "btn_clear":    "🗑️ Clear",
    "btn_yes":      "✅ Yes",
    "btn_no":       "❌ No",
    "btn_7days":    "📅 7 days",
    "btn_30days":   "🗓️ 30 days",
    "btn_tarif":    "💎 Plan",

    "no_expense":   "📭 No expenses yet.",
    "no_chart":     "📭 No data for chart.",
    "which_period": "📈 Which period?",
    "confirm_clear":"⚠️ Delete all expenses?",
    "cleared":      "🗑️ {count} expenses deleted.",
    "cancelled":    "✅ Cancelled.",
    "no_number":    "ℹ️ No number found.\nExample: <code>apple 15000</code>",
    "reading_img":  "🔍 Reading image...",
    "reading_pdf":  "🔍 Reading PDF...",
    "ocr_fail": (
        "❌ <b>No products found in receipt.</b>\n\n"
        "💡 Tips:\n"
        "• Take photo straight on (no tilt)\n"
        "• Good lighting required\n"
        "• Or type manually: <code>apple 15000</code>"
    ),
    "format_unsupported": (
        "❌ Unsupported format.\n"
        "✅ Accepted: <b>PDF, PNG, JPG, WebP</b>"
    ),
})

_RU = dict(_UZ)
_RU.update({
    "choose_lang":      "🌐 Выберите язык:",
    "lang_uz":          "🇺🇿 Узбекский",
    "lang_en":          "🇬🇧 Английский",
    "lang_ru":          "🇷🇺 Русский",
    "enter_name":       "✏️ Введите своё имя:",
    "name_saved":       "Привет, {name}! 👋",
    "choose_tariff":    "💎 Выберите тариф:",

    "btn_free":         "🆓 Бесплатно",
    "btn_trial":        "🎁 7 дней пробного (бесплатно)",
    "btn_3m":           "💰 3 месяца — 100 сум",
    "btn_6m":           "💰 6 месяцев — 130 сум",
    "btn_12m":          "💰 12 месяцев — 300 сум",

    "desc_free": (
        "🆓 <b>Бесплатный тариф</b>\n\n"
        "✅ Ежедневная / еженедельная / ежемесячная статистика\n"
        "✅ До 100 сохранённых продуктов\n"
        "❌ Нет диаграмм и графиков\n"
        "❌ Нет OCR (чтение чеков)\n\n"
        "Основные функции всегда бесплатны!"
    ),
    "desc_trial": (
        "🎁 <b>7-дневный пробный период</b>\n\n"
        "✅ Все премиум-функции\n"
        "✅ Диаграммы и графики\n"
        "✅ Сканирование чеков через OCR\n"
        "✅ Push-уведомления\n"
        "⚠️ Даётся только 1 раз на пользователя"
    ),
    "desc_premium": (
        "💎 <b>Возможности премиум-тарифа</b>\n\n"
        "✅ Полная статистика (ежедневно/еженедельно/ежемесячно/ежегодно)\n"
        "✅ Диаграммы и графики (matplotlib)\n"
        "✅ Сканирование чеков OCR\n"
        "✅ Сохранение в таблице, экспорт CSV/Excel\n"
        "✅ Оповещения о лимите бюджета\n"
        "✅ Анализ по категориям\n"
        "✅ Push-уведомления"
    ),

    "trial_activated":  "🎁 7-дневный пробный период активирован! Действует до {expires}.",
    "trial_already":    "⚠️ Вы уже использовали бесплатный пробный период.",
    "trial_expired":    "⏰ Пробный период истёк. Обновите через /tarif.",
    "sub_activated":    "✅ Тариф <b>{label}</b> активирован!\n📅 Действует до: {expires}.",
    "sub_expired":      "⏰ Срок вашего тарифа истёк. Обновите через /tarif.",
    "sub_info":         "📋 <b>Ваш тариф:</b> {tier}\n📅 <b>Действует до:</b> {expires}",
    "pay_info": (
        "💳 <b>{label}</b>\n\n"
        "Свяжитесь с администратором для оплаты:\n"
        "@xisobchi_admin\n\n"
        "После оплаты сообщите ваш ID: <code>{uid}</code>\n"
        "Тариф будет активирован автоматически."
    ),

    "premium_only": (
        "🔒 Эта функция только для премиум-пользователей.\n"
        "/tarif — просмотр тарифов"
    ),
    "free_limit": (
        "⚠️ Достигнут лимит бесплатного тарифа (100 продуктов).\n"
        "Обновите тариф: /tarif"
    ),

    "help_text": (
        "📖 <b>Помощь</b>\n\n"
        "✍️ <code>яблоко 15000</code> — продукт + сумма\n"
        "✍️ <code>хлеб 5000\nкола 8000</code> — несколько строк\n"
        "🖼️ PNG/JPG чек (премиум) — отправьте как фото\n"
        "📄 PDF чек (премиум) — отправьте как документ\n\n"
        "/stats — статистика\n"
        "/chart — график (премиум)\n"
        "/cats — категории (премиум)\n"
        "/tarif — информация о тарифе\n"
        "/lang — изменить язык\n"
        "/clear — очистить всё"
    ),

    "btn_week":     "📅 Неделя",
    "btn_month":    "🗓️ Месяц",
    "btn_all":      "📊 Все",
    "btn_chart":    "📈 График",
    "btn_cats":     "🏷️ Категории",
    "btn_stats":    "📉 Статистика",
    "btn_clear":    "🗑️ Очистить",
    "btn_yes":      "✅ Да",
    "btn_no":       "❌ Нет",
    "btn_7days":    "📅 7 дней",
    "btn_30days":   "🗓️ 30 дней",
    "btn_tarif":    "💎 Тариф",

    "no_expense":   "📭 Расходов нет.",
    "no_chart":     "📭 Нет данных для графика.",
    "which_period": "📈 Какой период?",
    "confirm_clear":"⚠️ Удалить все расходы?",
    "cleared":      "🗑️ Удалено расходов: {count}.",
    "cancelled":    "✅ Отменено.",
    "no_number":    "ℹ️ Число не найдено.\nНапример: <code>яблоко 15000</code>",
    "reading_img":  "🔍 Чтение изображения...",
    "reading_pdf":  "🔍 Чтение PDF...",
    "ocr_fail": (
        "❌ <b>Продукты в чеке не найдены.</b>\n\n"
        "💡 Советы:\n"
        "• Снимайте прямо, без наклона\n"
        "• Хорошее освещение\n"
        "• Или введите вручную: <code>яблоко 15000</code>"
    ),
    "format_unsupported": (
        "❌ Неподдерживаемый формат.\n"
        "✅ Принимаются: <b>PDF, PNG, JPG, WebP</b>"
    ),
})

LANGS = {"uz": _UZ, "en": _EN, "ru": _RU}


def tr(lang: str, key: str, **kwargs) -> str:
    """Return translated string for the given language code."""
    text = LANGS.get(lang, _UZ).get(key, _UZ.get(key, key))
    return text.format(**kwargs) if kwargs else text
