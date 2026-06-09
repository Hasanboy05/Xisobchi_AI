"""
════════════════════════════════════════════════════════════════════════
  Xisobchi AI — v3.0
  Telegram bot: chek rasmi yoki matn orqali xarajatlarni hisoblab boradi.

  Asosiy imkoniyatlar:
  ─ Ko'p til: O'zbek / Ingliz / Rus
  ─ Onboarding: til → ism → tarif tanlash oqimi
  ─ Subscription tizimi: bepul / trial / oylik tariflar
  ─ Feature gating: premium funksiyalar faqat obunachilarga
  ─ OCR: Tesseract orqali chek rasmi o'qish (PNG, JPG, PDF)
  ─ Grafiklar: Matplotlib yordamida chiziqli va doiraviy diagrammalar
  ─ Admin panel: foydalanuvchilarni boshqarish, to'lovlarni tasdiqlash
════════════════════════════════════════════════════════════════════════
"""

# ── Standart kutubxonalar ───────────────────────────────────────────
import telebot          # Telegram Bot API bilan ishlash uchun asosiy kutubxona
from telebot import types  # Klaviatura, callback va message turlari
from PIL import Image, ImageFilter, ImageEnhance  # Rasm ishlov berish (Pillow)
import pytesseract      # Tesseract OCR — rasmdan matn ajratish
import re               # Regulyar iboralar — matn parsing
import os               # Fayl tizimi va muhit o'zgaruvchilari
import json             # JSON fayllarni o'qish/yozish
import io               # Xotirada fayl bufer (grafik uchun)
from datetime import datetime, timedelta  # Sana/vaqt hisobi
from collections import defaultdict       # Standart qiymatli lug'at

# ── Grafik kutubxonasi ──────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")   # GUI ko'rsatmasdan, faqat fayl/bufer sifatida saqlash
import matplotlib.pyplot as plt
import matplotlib.dates as mdates  # Sanali o'q formatlash

# ── Tarjima moduli ──────────────────────────────────────────────────
from translations import tr  # Ko'p tilli matn qaytaruvchi funksiya

# ── PDF qo'llab-quvvatlash (PyMuPDF) ───────────────────────────────
# PyMuPDF (fitz) o'rnatilmagan bo'lsa ham bot ishlaydi,
# faqat PDF yuklab olish funksiyasi o'chirib qo'yiladi.
try:
    import fitz
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


# ════════════════════════════════════════════════════════════════════
#  SOZLAMALAR
#  Bu qismda barcha global konstantalar aniqlanadi.
# ════════════════════════════════════════════════════════════════════

# TELEGRAM_TOKEN — .env faylidan yoki to'g'ridan-to'g'ri string sifatida olinadi.
# Ishlab chiqarishda faqat .env dan foydalaning!
TOKEN     = os.getenv("TELEGRAM_TOKEN", "8904677991:AAGc7f2UyR5alJPy5mnfnBKDoo3vxz5xOgw")

DATA_FILE  = "expenses.json"  # Xarajatlar saqlanadigan fayl
USERS_FILE = "users.json"     # Foydalanuvchi profillari saqlanadigan fayl
FREE_LIMIT = 100              # Bepul tarifda bir foydalanuvchi saqlashi mumkin bo'lgan maks. mahsulot soni

# Har bir tarif uchun meta-ma'lumot: necha kun amal qiladi va qanday ko'rsatiladi.
# Kalitlar: "trial" | "month3" | "month6" | "month12"
TARIFF_META = {
    "trial":   {"days": 7,   "label_uz": "7 kun sinov",     "label_en": "7-day trial",    "label_ru": "7 дней пробный"},
    "month3":  {"days": 90,  "label_uz": "3 oy — 100 so'm", "label_en": "3 months",       "label_ru": "3 месяца"},
    "month6":  {"days": 180, "label_uz": "6 oy — 130 so'm", "label_en": "6 months",       "label_ru": "6 месяцев"},
    "month12": {"days": 365, "label_uz": "12 oy — 300 so'm","label_en": "12 months",      "label_ru": "12 месяцев"},
}

# Bot obyektini yaratamiz. TOKEN bilan Telegram serveriga ulanamiz.
bot = telebot.TeleBot(TOKEN)

# Tesseract OCR dasturining Windows'dagi o'rnatish yo'li.
# Linux/Mac'da odatda "tesseract" (yo'lsiz) yoziladi.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ════════════════════════════════════════════════════════════════════
#  FOYDALANUVCHI HOLATLARI (in-memory)
#
#  Har bir foydalanuvchining joriy oqim bosqichini saqlaydigan lug'at.
#  Kalit — foydalanuvchi ID (int), qiymat — holat nomi (str).
#
#  Mumkin qiymatlar:
#    "choosing_lang"        — til tanlash ekrani
#    "choosing_lang_change" — tilni o'zgartirish (allaqachon ro'yxatdan o'tgan)
#    "entering_name"        — ism kiritish bosqichi
#    "choosing_tariff"      — tarif tanlash ekrani
#    "main"                 — asosiy ishlash holati (barcha funksiyalar ochiq)
#
#  Bot qayta ishga tushganda bu lug'at tozalanadi (diskka saqlanmaydi).
# ════════════════════════════════════════════════════════════════════
USER_STATES: dict[int, str] = {}


# ════════════════════════════════════════════════════════════════════
#  FOYDALANUVCHI PROFILI — users.json
#
#  Profil strukturasi:
#  {
#    "123456789": {
#      "name":       "Ali",           # ism
#      "lang":       "uz",            # til kodi: uz | en | ru
#      "sub": {
#        "tier":       "free",        # tarif: free | trial | month3 | month6 | month12
#        "expires":    "2025-12-31T00:00:00",  # ISO format muddat (None = bepul)
#        "trial_used": false          # trial bir marta beriladi
#      },
#      "created_at": "2025-01-01T12:00:00"
#    }
#  }
# ════════════════════════════════════════════════════════════════════

def _load_users() -> dict:
    """users.json faylini diskdan o'qib, Python lug'atiga aylantiradi.
    Fayl mavjud bo'lmasa yoki buzilgan bo'lsa bo'sh lug'at qaytaradi."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_users(data: dict) -> None:
    """Foydalanuvchi lug'atini users.json ga yozib saqlaydi.
    ensure_ascii=False — o'zbek/rus harflar to'g'ri saqlanadi."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Bot ishga tushganda foydalanuvchi bazasini darhol yuklaymiz.
_users: dict = _load_users()


def get_user(uid: int) -> dict | None:
    """Berilgan Telegram ID bo'yicha profil qaytaradi.
    Foydalanuvchi topilmasa None qaytaradi."""
    return _users.get(str(uid))

def create_user(uid: int, name: str, lang: str) -> dict:
    """Yangi foydalanuvchi profili yaratib, diskka saqlaydi.
    Bepul tarif bilan boshlanadi, muddat yo'q."""
    profile = {
        "name": name,
        "lang": lang,
        "sub": {
            "tier":       "free",
            "expires":    None,
            "trial_used": False,
        },
        "created_at": datetime.now().isoformat(),
    }
    _users[str(uid)] = profile
    _save_users(_users)
    return profile

def update_user(uid: int, **kwargs) -> None:
    """Profilning alohida maydonlarini yangilaydi.

    Oddiy maydon:    update_user(uid, lang="en")
    Ichki maydon:    update_user(uid, **{"sub.tier": "trial"})
    Nuqta ifodalash: "sub.tier" → _users[uid]["sub"]["tier"]
    """
    key = str(uid)
    if key not in _users:
        return
    for k, v in kwargs.items():
        if "." in k:
            outer, inner = k.split(".", 1)
            _users[key].setdefault(outer, {})[inner] = v
        else:
            _users[key][k] = v
    _save_users(_users)


# ── Til yordamchilari ───────────────────────────────────────────────

def lang_of(uid: int) -> str:
    """Foydalanuvchi tilini qaytaradi. Profil yo'q bo'lsa "uz" (standart)."""
    user = get_user(uid)
    return user["lang"] if user else "uz"

def t(uid: int, key: str, **kwargs) -> str:
    """Foydalanuvchi tiliga mos tarjima matnini qaytaradi.
    kwargs orqali {name}, {expires} kabi o'zgaruvchilar almashtiriladi."""
    return tr(lang_of(uid), key, **kwargs)


# ════════════════════════════════════════════════════════════════════
#  SUBSCRIPTION (Obuna) TIZIMI
#
#  Tarif darajalari:
#    free    — bepul (100 mahsulotgacha, grafik va OCR yo'q)
#    trial   — 7 kunlik sinov (barcha premium imkoniyatlar, 1 marta)
#    month3  — 90 kun (to'lovli)
#    month6  — 180 kun (to'lovli)
#    month12 — 365 kun (to'lovli)
#
#  Admin IDlari har doim premium hisoblanadi (is_premium doim True).
# ════════════════════════════════════════════════════════════════════

def is_premium(uid: int) -> bool:
    """Foydalanuvchi aktiv premium yoki trial tarifda ekanligini tekshiradi.

    Qaytish qiymati:
      True  — premium/trial va muddat tugamagan
      False — bepul tarif yoki muddat tugagan
    """
    # Adminlar uchun cheklov yo'q
    if uid in ADMIN_IDS:
        return True
    user = get_user(uid)
    if not user:
        return False
    sub  = user.get("sub", {})
    tier = sub.get("tier", "free")
    if tier == "free":
        return False
    expires_str = sub.get("expires")
    if not expires_str:
        return False
    # Joriy vaqt muddat sanasidan oldin bo'lsa — premium faol
    return datetime.now() < datetime.fromisoformat(expires_str)

def activate_subscription(uid: int, tier: str) -> str:
    """Foydalanuvchi uchun tarifni faollashtiradi.

    Joriy vaqtga TARIFF_META["days"] kunni qo'shib, expires saqlaydi.
    Trial bo'lsa trial_used = True qilib belgilaydi.

    Qaytaradi: expires sanasini "DD.MM.YYYY" formatda.
    """
    days    = TARIFF_META[tier]["days"]
    expires = datetime.now() + timedelta(days=days)
    update_user(uid, **{
        "sub.tier":    tier,
        "sub.expires": expires.isoformat(),
    })
    if tier == "trial":
        update_user(uid, **{"sub.trial_used": True})
    return expires.strftime("%d.%m.%Y")

def sub_label(uid: int) -> str:
    """Foydalanuvchi tarifining o'qish uchun qulay nomini qaytaradi.
    Masalan: "🆓 Bepul" yoki "3 oy — 100 so'm"."""
    lang = lang_of(uid)
    user = get_user(uid)
    if not user:
        return "free"
    sub  = user.get("sub", {})
    tier = sub.get("tier", "free")
    if tier == "free":
        return tr(lang, "btn_free")
    meta = TARIFF_META.get(tier, {})
    return meta.get(f"label_{lang}", tier)

def sub_expires_str(uid: int) -> str:
    """Tarif tugash sanasini "DD.MM.YYYY" formatda qaytaradi.
    Muddat yo'q yoki bepul bo'lsa "—" qaytaradi."""
    user = get_user(uid)
    if not user:
        return "—"
    exp = user.get("sub", {}).get("expires")
    if not exp:
        return "—"
    return datetime.fromisoformat(exp).strftime("%d.%m.%Y")


# ════════════════════════════════════════════════════════════════════
#  XARAJATLAR MA'LUMOTLARI — expenses.json
#
#  Struktura:
#  {
#    "123456789": [
#      [15000, "Olma", "2025-06-10T14:30:00", "4820001234567"],
#      [8000,  "Non",  "2025-06-10T15:00:00", null],
#      ...
#    ]
#  }
#
#  Har bir yozuv 4 elementli ro'yxat:
#    [0] amount   — narx (int, so'mda)
#    [1] product  — mahsulot nomi (str)
#    [2] datetime — qo'shilgan vaqt (ISO string)
#    [3] code     — shtrix/QR kod (str yoki None)
# ════════════════════════════════════════════════════════════════════

def _load_expenses() -> dict:
    """expenses.json ni diskdan o'qiydi.
    Eski 3-elementli yozuvlarni 4-elementliga (code=None) o'tkazadi."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Migratsiya: eski [amount, product, date] → [amount, product, date, None]
                for uid, items in data.items():
                    data[uid] = [
                        it if len(it) == 4 else [it[0], it[1], it[2], None]
                        for it in items
                    ]
                return data
        except Exception:
            pass
    return {}

def _save_expenses(data: dict) -> None:
    """Xarajatlar lug'atini diskka yozadi."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Bot ishga tushganda xarajatlar bazasini yuklaymiz.
_expenses: dict = _load_expenses()


def get_user_expenses(uid: int) -> list:
    """Foydalanuvchining barcha xarajatlar ro'yxatini qaytaradi."""
    return _expenses.get(str(uid), [])

def add_user_expenses(uid: int, items: list) -> None:
    """Yangi xarajatlar ro'yxatini foydalanuvchi bazasiga qo'shadi.

    items — [(amount, product, code), ...] shaklidagi ro'yxat.
    Har bir element uchun joriy vaqt (ISO) avtomatik qo'shiladi.
    """
    key = str(uid)
    now = datetime.now().isoformat()
    _expenses.setdefault(key, [])
    for amount, product, code in items:
        _expenses[key].append([amount, product, now, code])
    _save_expenses(_expenses)

def clear_user_expenses(uid: int) -> None:
    """Foydalanuvchining barcha xarajatlarini o'chiradi (bo'sh ro'yxat qo'yadi)."""
    _expenses[str(uid)] = []
    _save_expenses(_expenses)

def get_by_period(uid: int, days: int | None) -> list:
    """Davr bo'yicha filtrlangan xarajatlar ro'yxatini qaytaradi.

    days=None  → barcha xarajatlar
    days=7     → oxirgi 7 kunlik
    days=30    → oxirgi 30 kunlik
    """
    rows = get_user_expenses(uid)
    if days is None:
        return rows
    cutoff = datetime.now() - timedelta(days=days)
    return [r for r in rows if datetime.fromisoformat(r[2]) >= cutoff]


# ════════════════════════════════════════════════════════════════════
#  YORDAMCHI FUNKSIYALAR
# ════════════════════════════════════════════════════════════════════

def fmt(amount: int) -> str:
    """Sonni ko'rinishli formatga o'tkazadi: 1500000 → "1 500 000".
    Vergul o'rniga bo'shliq ishlatiladi (o'zbek odati)."""
    return f"{int(amount):,}".replace(",", " ")

def clean(name: str) -> str:
    """HTML-xavfli belgilarni ekran-xavfsiz versiyaga almashtiradi.
    Telegram HTML parse_mode da XSS'dan himoya qiladi."""
    return name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ── Mahsulot kategoriyalari ─────────────────────────────────────────
# Kalit — kalit so'zlar "|" bilan ajratilgan, qiymat — (emoji, nom) tuple.
# Mahsulot nomi kalit so'zlardan birini o'z ichiga olsa, shu kategoriyaga tushadi.
CATEGORY_MAP = {
    "yogurt|sut|qatiq|cream|krem|dairy|qaymoq|йогурт|молок|сливк": ("🧈", "Sut mahsulotlari"),
    "pepsi|cola|fanta|sprite|limonad|drink|soda|газиров|напит":     ("🥤", "Ichimliklar"),
    "suv|water|mineral|santal|вода":                                ("💧", "Suv"),
    "energy|flash|энерг|monster|redbull|red bull":                  ("⚡", "Energetik"),
    "non|bread|lavash|bulochk|булочк|хлеб":                         ("🍞", "Non"),
    "paket|пакет|bag|sumka|bio|poelitilen":                         ("🛍️", "Paket"),
    "go'sht|meat|курица|chicken|beef|kolbas|колбас":                ("🥩", "Go'sht"),
    "sabzavot|meva|fruit|овощ|pomidor|banan|olma|апельс":           ("🥦", "Sabzavot/Meva"),
    "шоколад|chocolate|choco|печень|biskvit|wafer|конфет":          ("🍫", "Shirinlik"),
    "chips|snack|cracker|сухар|снэк":                               ("🍿", "Snack"),
    "yog|масл|oil|moy":                                             ("🫙", "Yog'/Moy"),
}

def get_category(name: str) -> tuple[str, str]:
    """Mahsulot nomiga qarab emoji va kategoriya nomini qaytaradi.
    Hech bir kategoriyaga tushmasa ("🛒", "Boshqa") qaytaradi."""
    n = name.lower()
    for keys, cat in CATEGORY_MAP.items():
        if any(k in n for k in keys.split("|")):
            return cat
    return ("🛒", "Boshqa")

def build_full_list(uid: int) -> str:
    """Foydalanuvchining barcha xarajatlarini HTML-formatlangan matn sifatida qaytaradi.
    Raqamlangan ro'yxat + umumiy summa."""
    rows = get_user_expenses(uid)
    if not rows:
        return t(uid, "no_expense")
    lines = []
    for i, (a, p, _, code) in enumerate(rows, 1):
        icon, _ = get_category(p)
        code_str = f" 🆔{code}" if code else ""
        lines.append(f"{i}. {icon} {clean(p)}{code_str} — {fmt(a)} so'm")
    total = sum(r[0] for r in rows)
    return (
        "<b>🧾 Barcha harajatlar:</b>\n"
        + "\n".join(lines)
        + f"\n\n💰 <b>Jami: {fmt(total)} so'm</b>"
    )


# ════════════════════════════════════════════════════════════════════
#  KLAVIATURALAR (Inline)
#
#  Har bir funksiya types.InlineKeyboardMarkup obyektini qaytaradi.
#  Tugma bosilganda callback_data Telegram'dan bot'ga uzatiladi.
# ════════════════════════════════════════════════════════════════════

def lang_keyboard() -> types.InlineKeyboardMarkup:
    """Til tanlash klaviaturasi: O'zbek / English / Русский."""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🇺🇿 O'zbek tili", callback_data="lang:uz"),
        types.InlineKeyboardButton("🇬🇧 English",      callback_data="lang:en"),
        types.InlineKeyboardButton("🇷🇺 Русский",      callback_data="lang:ru"),
    )
    return kb

def tariff_keyboard(uid: int) -> types.InlineKeyboardMarkup:
    """Tarif tanlash klaviaturasi: Bepul / Trial / 3-6-12 oy.
    Matnlar foydalanuvchi tiliga mos tarjimada ko'rsatiladi."""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(t(uid, "btn_free"),  callback_data="tariff:free"),
        types.InlineKeyboardButton(t(uid, "btn_trial"), callback_data="tariff:trial"),
        types.InlineKeyboardButton(t(uid, "btn_3m"),    callback_data="tariff:month3"),
        types.InlineKeyboardButton(t(uid, "btn_6m"),    callback_data="tariff:month6"),
        types.InlineKeyboardButton(t(uid, "btn_12m"),   callback_data="tariff:month12"),
    )
    return kb

def main_keyboard(uid: int) -> types.InlineKeyboardMarkup:
    """Asosiy menyu klaviaturasi (2 ustunli):
    Haftalik | Oylik | Barchasi | Grafik | Kategoriya | Statistika | Tarif | Tozalash"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(t(uid, "btn_week"),  callback_data="period:week"),
        types.InlineKeyboardButton(t(uid, "btn_month"), callback_data="period:month"),
        types.InlineKeyboardButton(t(uid, "btn_all"),   callback_data="period:all"),
        types.InlineKeyboardButton(t(uid, "btn_chart"), callback_data="chart"),
        types.InlineKeyboardButton(t(uid, "btn_cats"),  callback_data="cats"),
        types.InlineKeyboardButton(t(uid, "btn_stats"), callback_data="stats"),
        types.InlineKeyboardButton(t(uid, "btn_tarif"), callback_data="tarif_info"),
        types.InlineKeyboardButton(t(uid, "btn_clear"), callback_data="clear"),
    )
    return kb

def period_keyboard(uid: int) -> types.InlineKeyboardMarkup:
    """Grafik davri tanlash: 7 kunlik | 30 kunlik."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(t(uid, "btn_7days"),  callback_data="chart:week"),
        types.InlineKeyboardButton(t(uid, "btn_30days"), callback_data="chart:month"),
    )
    return kb

def confirm_keyboard(uid: int) -> types.InlineKeyboardMarkup:
    """Tasdiqlash/bekor qilish klaviaturasi: Ha | Yo'q."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(t(uid, "btn_yes"), callback_data="confirm_clear"),
        types.InlineKeyboardButton(t(uid, "btn_no"),  callback_data="cancel_clear"),
    )
    return kb


# ════════════════════════════════════════════════════════════════════
#  RASM VA PDF ISHLOV BERISH
#
#  Oqim:
#    1. Foydalanuvchi rasm/PDF yuboradi
#    2. Bot faylni Telegram serveridan yuklab oladi
#    3. preprocess_image() — rasmi kontrast/o'tkir qiladi
#    4. ocr_image()        — Tesseract bilan matn ajratadi
#    5. parse_korzinka()   — Korzinka/supermarket chek formatini tahlil qiladi
#    6. parse_simple_text() — Oddiy "mahsulot narx" formatini tahlil qiladi
# ════════════════════════════════════════════════════════════════════

def preprocess_image(path: str) -> None:
    """OCR aniqligini oshirish uchun rasmni qayta ishlaydi:
      • Kulrang tonlarga o'tkazadi (L mode)
      • Kontrastni 2.5x oshiradi
      • O'tkirlikni 2x oshiradi
      • Qo'shimcha SHARPEN filtri qo'shadi
      • 2x kattalashtiradi (Tesseract kichik matnni yaxshiroq o'qiydi)
    Qayta ishlangan rasm xuddi shu path'ga saqlanadi.
    """
    img = Image.open(path).convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img.save(path)

# Chekda tez-tez uchraydigan, lekin mahsulot nomi bo'lmagan so'zlar.
# Bu so'zlarni o'z ichiga olgan qatorlar parsing'dan o'tkazib yuboriladi.
SKIP_WORDS = [
    "sh.j", "qqs", "mxik", "mk ", " mk", "tovarni", "oldi-sotdi",
    "to'lov", "tolov", "jami", "uchun", "total", "nds",
    "www", "http", "tel:", "чек", "кассир", "kassir", "savdo",
    "bonuslar", "bonus", "stir", "s/n", "pos n", "tuzatish",
    "qaytim", "to'landi", "tolandi", "naqd", "bor edi", "qoldi",
    "olib q", "oylik", "chorak", "retro", "muddati", "chegirma",
    "fb:", "fm:", "rs:", "soliq", "xaridingiz", "rahmat",
    "jumladan", "loyalt", "loyal", "shu jum",
]

# Chekdagi narx formati: "15 000,00" yoki "8500.00" kabi qator oxiri
PRICE_RE = re.compile(r"([\d][\d\s]{1,9}[,\.]\d{2})\s*$")
# Shtrix/QR kod formati: 6-13 raqamli ketma-ketlik
CODE_RE  = re.compile(r"\b(\d{6,13})\b")

def parse_korzinka(text: str) -> list:
    """Korzinka va shunga o'xshash supermarket chek matnini tahlil qiladi.

    Chek formati odatda:
      [Mahsulot nomi]
      [Miqdor x narx] ← yoki shu qatorda narx bo'ladi

    Algoritm:
      • SKIP_WORDS bor qatorlarni o'tkazib yuboradi
      • PRICE_RE bilan narx topadi
      • Narx qatorida ism bo'lmasa, oldingi qatorni (pending_name) oladi
      • CODE_RE bilan shtrix kodni nomdan ajratib oladi

    Qaytaradi: [(amount, product_name, code_or_None), ...] ro'yxat
    """
    results, pending_name = [], ""
    for line in [l.strip() for l in text.split("\n")]:
        if not line or len(line) < 3:
            pending_name = ""
            continue
        low = line.lower()
        if any(kw in low for kw in SKIP_WORDS):
            pending_name = ""
            continue
        m = PRICE_RE.search(line)
        if m:
            try:
                price = float(m.group(1).replace(" ", "").replace(",", "."))
            except ValueError:
                pending_name = ""
                continue
            # Narx oralig'i tekshiruvi: 50 so'mdan 10 mln so'mgacha
            if not (50 < price < 10_000_000):
                pending_name = ""
                continue
            # Narxdan oldingi qismni mahsulot nomi sifatida olamiz
            name_part = re.sub(r"[^\w\s\-\.\%/]", " ", line[:m.start()]).strip()
            product_code = None
            cm = CODE_RE.search(name_part)
            if cm:
                product_code = cm.group(1)
                name_part = CODE_RE.sub("", name_part).strip()
            # Avvalgi qatorda qolgan ism bo'lsa, birlashtiramiz
            full_name = (pending_name + " " + name_part).strip() if pending_name else name_part
            pending_name = ""
            if len(full_name) >= 2:
                results.append((int(price), full_name, product_code))
        else:
            # Bu qatorda narx yo'q → keyingi qator uchun ism sifatida saqlab qo'yamiz
            clean_line = re.sub(r"[^\w\s\-\.\%/]", " ", line).strip()
            pending_name = clean_line if len(clean_line) > 2 else ""
    return results

def parse_simple_text(text: str) -> list:
    """Oddiy "mahsulot narx" formatini tahlil qiladi.

    Misol:
      "olma 15000" → [(15000, "olma", None)]
      "non 5000 kolbasa 12000" → [(5000, "non kolbasa", None)]  (taxminiy)

    Har qatordagi birinchi raqamni narx sifatida oladi,
    qolgan matnni mahsulot nomi sifatida oladi.
    """
    results = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        nums = re.findall(r"\d+", line)
        if not nums:
            continue
        amount = int(nums[0])
        if amount < 50:  # 50 so'mdan kam bo'lsa — narx emas
            continue
        product = re.sub(r"[^\w\s]", "", re.sub(r"\d+", "", line)).strip() or "Noma'lum"
        results.append((amount, product, None))
    return results

def ocr_image(path: str, lang: str = "uzb+rus+eng") -> list:
    """Rasm faylidan OCR yordamida mahsulotlarni ajratib oladi.

    Tesseract PSM (Page Segmentation Mode) qiymatlarini sinab ko'radi:
      psm=6 — blok sifatida o'qiydi (odatda eng yaxshi cheklar uchun)
      psm=4 — ustunli matn
      psm=3 — avtomatik

    Eng ko'p mahsulot topilgan variantni tanlaydi.
    Hech biri ishlamasa, parse_simple_text() ga tushadi.
    """
    best: list = []
    for psm in ("6", "4", "3"):
        try:
            text = pytesseract.image_to_string(
                Image.open(path), lang=lang,
                config=f"--psm {psm} --oem 3"
            )
            r = parse_korzinka(text)
            if len(r) > len(best):
                best = r
        except Exception as e:
            print(f"[OCR psm={psm}] {e}")
    if not best:
        try:
            text = pytesseract.image_to_string(Image.open(path), lang=lang)
            best = parse_simple_text(text)
        except Exception:
            pass
    return best

def process_pdf(pdf_path: str) -> list:
    """PDF faylidan barcha sahifalar bo'yicha mahsulotlarni ajratadi.

    Har bir sahifa uchun:
      1. Agar matn bor bo'lsa — bevosita tahlil qiladi
      2. Matn yo'q bo'lsa — sahifani rasm sifatida eksport qilib OCR qiladi
         (3x zoom bilan — OCR aniqligini oshirish uchun)

    PDF_SUPPORT=False bo'lsa (fitz o'rnatilmagan) bo'sh ro'yxat qaytaradi.
    """
    if not PDF_SUPPORT:
        return []
    results = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                # Matnli PDF sahifa — bevosita parsing
                r = parse_korzinka(text) or parse_simple_text(text)
            else:
                # Skanerlangan PDF sahifa — rasmi olib OCR qilish
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                tmp = f"pdf_page_{i}.png"
                pix.save(tmp)
                preprocess_image(tmp)
                r = ocr_image(tmp)
                if os.path.exists(tmp):
                    os.remove(tmp)
            results.extend(r)
        doc.close()
    except Exception as e:
        print(f"[PDF xatolik] {e}")
    return results

def process_png(file_path: str) -> list:
    """PNG/JPG faylini qayta ishlab, OCR bilan mahsulotlarni ajratadi."""
    preprocess_image(file_path)
    return ocr_image(file_path)


# ════════════════════════════════════════════════════════════════════
#  GRAFIKLAR (Matplotlib)
#
#  Barcha grafiklar xotiradagi BytesIO buferiga saqlanadi,
#  so'ng Telegram'ga rasm sifatida yuboriladi.
#  Qora rangdagi tema ishlatiladi (#1a1a2e fon).
# ════════════════════════════════════════════════════════════════════

def generate_line_chart(uid: int, period: str = "month") -> io.BytesIO | None:
    """Chiziqli grafik — kunlik xarajatlar dinamikasini ko'rsatadi.

    period="month" → oxirgi 30 kunlik
    period="week"  → oxirgi 7 kunlik

    Grafik elementlari:
      • To'ldirilgan maydon (fill_between) — umumiy tendentsiya
      • Chiziq va nuqtalar — har kunlik qiymat
      • Annotatsiyalar — har nuqta ustida so'm qiymati

    Ma'lumot bo'lmasa None qaytaradi (foydalanuvchiga "grafik yo'q" xabari chiqadi).
    """
    rows = get_by_period(uid, 30 if period == "month" else 7)
    if not rows:
        return None

    # Kunlar bo'yicha summa hisoblash: {date: total_amount}
    daily: dict = defaultdict(int)
    for amount, _, date_str, _ in rows:
        daily[datetime.fromisoformat(date_str).date()] += amount
    dates  = sorted(daily)
    values = [daily[d] for d in dates]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1a1a2e")  # Tashqi fon: to'q ko'k
    ax.set_facecolor("#16213e")         # Grafik maydoni foni

    ax.fill_between(dates, values, alpha=0.25, color="#e94560")   # Shaffof to'ldirish
    ax.plot(dates, values, color="#e94560", linewidth=2.5, marker="o", markersize=6)

    # Har bir nuqta ustida qiymat yoziladigan annotatsiya
    for date, val in zip(dates, values):
        ax.annotate(fmt(val), xy=(date, val), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=7, color="#ffffff")

    label = "30 kunlik" if period == "month" else "7 kunlik"
    ax.set_title(f"🛒 {label} xarajatlar", color="white", fontsize=13, pad=15)
    ax.set_xlabel("Sana", color="#aaaaaa")
    ax.set_ylabel("So'm", color="#aaaaaa")
    ax.tick_params(colors="white")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
    plt.xticks(rotation=30)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444466")

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)  # O'qish uchun boshiga qaytarish
    return buf

def generate_pie_chart(uid: int) -> io.BytesIO | None:
    """Doiraviy grafik — kategoriyalar bo'yicha xarajatlar ulushini ko'rsatadi.

    Har bir mahsulot CATEGORY_MAP orqali kategoriyaga ajratiladi,
    keyin kategoriya bo'yicha umumiy summalar hisablanadi.

    Ma'lumot bo'lmasa None qaytaradi.
    """
    rows = get_user_expenses(uid)
    if not rows:
        return None

    # Kategoriyalar bo'yicha summa hisoblash
    cat_totals: dict = defaultdict(int)
    for amount, product, _, _ in rows:
        icon, cat_name = get_category(product)
        cat_totals[f"{icon} {cat_name}"] += amount
    labels = list(cat_totals)
    values = list(cat_totals.values())

    # Rang palitrasi — 10 xil rang, kategoriya soniga qarab kesiladi
    COLORS = ["#e94560", "#0f3460", "#533483", "#f5a623",
              "#7ed321", "#4a90e2", "#bd10e0", "#50e3c2", "#b8e986", "#ff6b6b"]

    fig, ax = plt.subplots(figsize=(8, 8))
    fig.patch.set_facecolor("#1a1a2e")
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.1f%%",
        colors=COLORS[:len(labels)], startangle=140,
        textprops={"color": "white", "fontsize": 10}, pctdistance=0.82,
    )
    for at in autotexts:
        at.set_fontsize(9)
    ax.set_title(
        f"🏷️ Kategoriyalar\nJami: {fmt(sum(values))} so'm",
        color="white", fontsize=13, pad=20,
    )

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


# ════════════════════════════════════════════════════════════════════
#  YUBORISH YORDAMCHILARI
#  Bu funksiyalar bot.send_message / bot.send_photo ni chaqirib,
#  foydalanuvchiga tayyor formatlangan xabar yuboradi.
# ════════════════════════════════════════════════════════════════════

def send_stats(chat_id: int, uid: int) -> None:
    """Foydalanuvchiga to'liq statistika xabarini yuboradi:
    jami yozuvlar, umumiy, o'rtacha, haftalik, oylik,
    eng qimmat, eng arzon va eng tez-tez uchraydigan mahsulot."""
    rows = get_user_expenses(uid)
    if not rows:
        bot.send_message(chat_id, t(uid, "no_expense"))
        return
    total = sum(r[0] for r in rows)
    count = len(rows)
    mx    = max(rows, key=lambda x: x[0])  # Eng qimmat
    mn    = min(rows, key=lambda x: x[0])  # Eng arzon
    week  = sum(r[0] for r in get_by_period(uid, 7))
    mon   = sum(r[0] for r in get_by_period(uid, 30))

    # Mahsulot chastotasi: {ism: necha marta}
    freq: dict = defaultdict(int)
    for _, p, _, _ in rows:
        freq[p] += 1
    top = max(freq.items(), key=lambda x: x[1]) if freq else ("-", 0)

    bot.send_message(
        chat_id,
        f"📈 <b>Statistika</b>\n\n"
        f"📦 Jami yozuvlar: <b>{count}</b>\n"
        f"💰 Umumiy: <b>{fmt(total)} so'm</b>\n"
        f"📊 O'rtacha: <b>{fmt(total // count)} so'm</b>\n\n"
        f"📅 Haftalik: <b>{fmt(week)} so'm</b>\n"
        f"🗓️ Oylik: <b>{fmt(mon)} so'm</b>\n\n"
        f"⬆️ Eng qimmat: <b>{clean(mx[1])}</b> — {fmt(mx[0])} so'm\n"
        f"⬇️ Eng arzon: <b>{clean(mn[1])}</b> — {fmt(mn[0])} so'm\n"
        f"🔁 Eng ko'p: <b>{clean(top[0])}</b> ({top[1]} marta)",
        parse_mode="HTML", reply_markup=main_keyboard(uid),
    )

def send_chart(chat_id: int, uid: int, period: str) -> None:
    """Chiziqli grafik rasmini generatsiya qilib yuboradi.
    Ma'lumot bo'lmasa xato xabar ko'rsatadi."""
    buf   = generate_line_chart(uid, period)
    label = "30 kunlik" if period == "month" else "7 kunlik"
    if buf:
        bot.send_photo(chat_id, buf, caption=f"📈 {label} harajatlar",
                       reply_markup=main_keyboard(uid))
    else:
        bot.send_message(chat_id, t(uid, "no_chart"), reply_markup=main_keyboard(uid))

def send_cat_chart(chat_id: int, uid: int) -> None:
    """Doiraviy kategoriya grafigini generatsiya qilib yuboradi."""
    buf = generate_pie_chart(uid)
    if buf:
        bot.send_photo(chat_id, buf, caption="🏷️ Kategoriyalar bo'yicha taqsimot",
                       reply_markup=main_keyboard(uid))
    else:
        bot.send_message(chat_id, t(uid, "no_expense"), reply_markup=main_keyboard(uid))

def send_added(chat_id: int, msg_id: int, uid: int, results: list) -> None:
    """OCR/parsing natijasini foydalanuvchiga ko'rsatadi.

    Avval yuborilgan "o'qilmoqda..." xabarini tahrirlaydi
    (bot.edit_message_text) — yangi xabar yuborish o'rniga.
    Topilgan mahsulotlar ro'yxati + yangilangan umumiy ro'yxat ko'rsatiladi.
    """
    added_total = sum(a for a, _, _ in results)
    lines = []
    for a, p, code in results:
        icon, _ = get_category(p)
        code_str = f" 🆔{code}" if code else ""
        lines.append(f"  • {icon} {clean(p)}{code_str} — {fmt(a)} so'm")
    bot.edit_message_text(
        f"✅ <b>{len(results)} ta mahsulot topildi!</b>\n"
        f"💰 Shu chekdan: <b>{fmt(added_total)} so'm</b>\n\n"
        + "\n".join(lines)
        + "\n\n" + build_full_list(uid),
        chat_id, msg_id,
        parse_mode="HTML", reply_markup=main_keyboard(uid),
    )


# ════════════════════════════════════════════════════════════════════
#  ADMIN YORDAMCHILARI
#
#  Admin paneli quyidagilarni beradi:
#    • Barcha foydalanuvchilar ro'yxati
#    • Premium foydalanuvchilar
#    • Umumiy statistika
#    • Kutilayotgan to'lov so'rovlari + tez faollashtirish
# ════════════════════════════════════════════════════════════════════

# Admin Telegram IDlari. Bu IDlar premium cheklovsiz ishlaydi.
ADMIN_IDS = {7920968216, 5115387272}

def notify_admins(text: str, reply_markup=None) -> None:
    """Barcha adminlarga HTML-formatlangan xabar yuboradi.
    Yuborib bo'lmasa (admin botni bloklaganda) xatolikni e'tiborsiz qoldiradi."""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text, parse_mode="HTML",
                             reply_markup=reply_markup)
        except Exception:
            pass

def admin_panel_keyboard() -> types.InlineKeyboardMarkup:
    """Admin asosiy panel klaviaturasi: 4 ta boshqaruv tugmasi."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👥 Barcha userlar",    callback_data="adm:users"),
        types.InlineKeyboardButton("💎 Premium userlar",   callback_data="adm:premium"),
        types.InlineKeyboardButton("📊 Statistika",        callback_data="adm:stats"),
        types.InlineKeyboardButton("💳 To'lov so'rovlari", callback_data="adm:payments"),
    )
    return kb

def quick_activate_keyboard(uid: int, tier: str) -> types.InlineKeyboardMarkup:
    """To'lov bildirishnomasiga qo'shiladigan tez faollashtirish klaviaturasi.
    Admin 1 tugma bilan tarifni faollashtirishi yoki rad etishi mumkin."""
    kb    = types.InlineKeyboardMarkup(row_width=2)
    label = TARIFF_META.get(tier, {}).get("label_uz", tier)
    kb.add(
        types.InlineKeyboardButton(f"✅ {label} faollashtir", callback_data=f"adm_act:{uid}:{tier}"),
        types.InlineKeyboardButton("❌ Rad etish",            callback_data=f"adm_reject:{uid}"),
    )
    return kb

def admin_overall_stats() -> str:
    """Admin uchun HTML-formatlangan umumiy statistika matnini qaytaradi:
    jami/premium/trial/bepul foydalanuvchilar soni va umumiy xarajatlar."""
    total      = len(_users)
    registered = sum(1 for u in _users.values() if not u.get("_pending"))
    premium    = sum(1 for uid_str, u in _users.items()
                     if not u.get("_pending") and is_premium(int(uid_str)))
    trial      = sum(1 for u in _users.values()
                     if u.get("sub", {}).get("tier") == "trial")
    free_cnt   = registered - premium
    total_exp  = sum(sum(r[0] for r in exps) for exps in _expenses.values())
    return (
        f"📊 <b>Umumiy statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{registered}</b>\n"
        f"💎 Premium: <b>{premium}</b>\n"
        f"🎁 Trial: <b>{trial}</b>\n"
        f"🆓 Bepul: <b>{free_cnt}</b>\n\n"
        f"💰 Barcha xarajatlar jami: <b>{fmt(total_exp)} so'm</b>"
    )

# Kutilayotgan to'lov so'rovlari: {foydalanuvchi_uid: tarif_kodi}
# Bot qayta ishga tushganda tozalanadi (in-memory).
_pending_payments: dict[int, str] = {}


# ════════════════════════════════════════════════════════════════════
#  ONBOARDING OQIMI
#
#  Yangi foydalanuvchi uchun bosqich-ma'bosqich kirish:
#    1. /start → til tanlash (choosing_lang)
#    2. Til → ism kiritish (entering_name)
#    3. Ism → tarif tanlash (choosing_tariff)
#    4. Tarif → asosiy holat (main)
#
#  Diagramma (Hisobchi Ai.drawio) shu oqimni vizual ko'rsatadi.
# ════════════════════════════════════════════════════════════════════

def start_onboarding(message: types.Message) -> None:
    """Yangi foydalanuvchi uchun onboarding jarayonini boshlaydi.
    Holatni "choosing_lang" ga o'rnatib, til tanlash klaviaturasini yuboradi."""
    uid = message.from_user.id
    USER_STATES[uid] = "choosing_lang"
    bot.send_message(
        message.chat.id,
        "🌐 Tilni tanlang / Choose language / Выберите язык:",
        reply_markup=lang_keyboard(),
    )

def handle_lang_chosen(call: types.CallbackQuery, lang: str) -> None:
    """Foydalanuvchi tilni tanlaganida chaqiriladi.
    Vaqtincha (_pending=True) profil yaratilib, ism kiritish so'raladi.
    _pending flag onboarding tugamaganini bildiradi."""
    uid = call.from_user.id
    USER_STATES[uid] = "entering_name"
    _users[str(uid)] = {"lang": lang, "_pending": True}
    _save_users(_users)
    bot.edit_message_text(
        tr(lang, "enter_name"),
        call.message.chat.id,
        call.message.message_id,
    )

def handle_name_entered(message: types.Message) -> None:
    """Foydalanuvchi ismini kiritganida chaqiriladi.
    Ism 2 ta belgidan qisqa bo'lsa qayta so'raydi.
    To'g'ri ism kiritilsa to'liq profil yaratib, tarif tanlashga o'tadi.
    Adminlarga yangi foydalanuvchi haqida bildirishnoma yuboradi."""
    uid  = message.from_user.id
    lang = _users.get(str(uid), {}).get("lang", "uz")
    name = message.text.strip()
    if len(name) < 2:
        bot.send_message(message.chat.id, tr(lang, "enter_name"))
        return
    create_user(uid, name, lang)
    USER_STATES[uid] = "choosing_tariff"
    bot.send_message(message.chat.id, tr(lang, "name_saved", name=clean(name)))
    bot.send_message(
        message.chat.id,
        tr(lang, "choose_tariff"),
        reply_markup=tariff_keyboard(uid),
    )
    # Adminlarga yangi foydalanuvchi haqida bildirishnoma
    notify_admins(
        f"👤 <b>Yangi foydalanuvchi!</b>\n\n"
        f"Ism: <b>{clean(name)}</b>\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"🌐 Til: {lang.upper()}\n"
        f"📅 Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

def handle_tariff_chosen(call: types.CallbackQuery, tariff: str) -> None:
    """Foydalanuvchi tarifni tanlaganida chaqiriladi.

    Uch holat:
      1. "free"  — darhol bepul tarif, asosiy menyuga o'tish
      2. "trial" — trial faqat birinchi marta beriladi; faollashtirilib, menyuga o'tish
      3. To'lovli (month3/6/12) — to'lov yo'riqnomasi, adminlarga bildirishnoma,
                                   foydalanuvchi shu orada bepul tarifda ishlaydi
    """
    uid  = call.from_user.id
    lang = lang_of(uid)

    if tariff == "free":
        USER_STATES[uid] = "main"
        text = tr(lang, "desc_free")
        bot.edit_message_text(
            text + f"\n\n{tr(lang, 'choose_tariff')}",
            call.message.chat.id, call.message.message_id,
            parse_mode="HTML",
        )
        bot.send_message(
            call.message.chat.id,
            f"✅ Bepul tarif tanlandi!\n\n{tr(lang, 'help_text')}",
            parse_mode="HTML", reply_markup=main_keyboard(uid),
        )

    elif tariff == "trial":
        user = get_user(uid)
        # Trial har foydalanuvchiga faqat 1 marta beriladi
        if user and user.get("sub", {}).get("trial_used"):
            bot.answer_callback_query(call.id, tr(lang, "trial_already"), show_alert=True)
            return
        expires = activate_subscription(uid, "trial")
        USER_STATES[uid] = "main"
        bot.edit_message_text(
            tr(lang, "desc_trial"),
            call.message.chat.id, call.message.message_id,
            parse_mode="HTML",
        )
        bot.send_message(
            call.message.chat.id,
            tr(lang, "trial_activated", expires=expires),
            parse_mode="HTML", reply_markup=main_keyboard(uid),
        )

    else:
        # To'lovli tarif: foydalanuvchiga to'lov ko'rsatmalari
        label = TARIFF_META.get(tariff, {}).get(f"label_{lang}", tariff)
        bot.edit_message_text(
            tr(lang, "pay_info", label=label, uid=uid),
            call.message.chat.id, call.message.message_id,
            parse_mode="HTML",
        )
        USER_STATES[uid] = "main"
        # To'lov kutilayotganda bepul tarifdan foydalanishini aytamiz
        bot.send_message(
            call.message.chat.id,
            f"{tr(lang, 'desc_free')}\n\nShu orada bepul tarifdan foydalanishingiz mumkin.",
            parse_mode="HTML", reply_markup=main_keyboard(uid),
        )
        # Kutilayotgan to'lovlar ro'yxatiga qo'shamiz
        _pending_payments[uid] = tariff
        # Adminlarga tez faollashtirish tugmasi bilan bildirishnoma
        user  = get_user(uid)
        uname = f"@{call.from_user.username}" if call.from_user.username else "—"
        notify_admins(
            f"💳 <b>To'lov so'rovi!</b>\n\n"
            f"👤 Ism: <b>{clean(user['name']) if user else '—'}</b>\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"📱 Username: {uname}\n"
            f"🌐 Til: {lang.upper()}\n"
            f"📦 Tarif: <b>{label}</b>\n"
            f"📅 Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            reply_markup=quick_activate_keyboard(uid, tariff),
        )


# ════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLERS (Buyruq handlerlari)
#
#  Telegram'dan kelgan har xil turdagi xabarlarga javob beruvchi
#  funksiyalar. @bot.message_handler() dekoratori bilan belgilanadi.
# ════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start", "hello"])
def cmd_start(message: types.Message) -> None:
    """/start va /hello buyrug'i.
    Allaqachon ro'yxatdan o'tgan bo'lsa — salom + tarif holati ko'rsatadi.
    Yangi foydalanuvchi bo'lsa — onboarding boshlanadi."""
    uid  = message.from_user.id
    user = get_user(uid)
    if user and not user.get("_pending"):
        # Ro'yxatdan o'tgan — asosiy holatga o'tkazib, tarif ma'lumotini ko'rsatamiz
        USER_STATES[uid] = "main"
        lang = user.get("lang", "uz")
        bot.send_message(
            message.chat.id,
            f"{tr(lang, 'name_saved', name=clean(user['name']))}\n\n"
            f"{tr(lang, 'sub_info', tier=sub_label(uid), expires=sub_expires_str(uid))}",
            parse_mode="HTML", reply_markup=main_keyboard(uid),
        )
    else:
        start_onboarding(message)

@bot.message_handler(commands=["help"])
def cmd_help(message: types.Message) -> None:
    """/help buyrug'i — qo'llanma matnini yuboradi."""
    uid = message.from_user.id
    bot.send_message(message.chat.id, t(uid, "help_text"),
                     parse_mode="HTML", reply_markup=main_keyboard(uid))

@bot.message_handler(commands=["stats"])
def cmd_stats(message: types.Message) -> None:
    """/stats buyrug'i — statistika.
    Faqat "main" holatda ishlaydi (onboarding tugagan bo'lishi kerak)."""
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    send_stats(message.chat.id, uid)

@bot.message_handler(commands=["chart"])
def cmd_chart(message: types.Message) -> None:
    """/chart buyrug'i — chiziqli grafik (faqat premium).
    Premium bo'lmasa "premium_only" xabari ko'rsatiladi."""
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    if not is_premium(uid):
        bot.send_message(message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        return
    bot.send_message(message.chat.id, t(uid, "which_period"),
                     reply_markup=period_keyboard(uid))

@bot.message_handler(commands=["cats"])
def cmd_cats(message: types.Message) -> None:
    """/cats buyrug'i — kategoriya doiraviy grafik (faqat premium)."""
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    if not is_premium(uid):
        bot.send_message(message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        return
    send_cat_chart(message.chat.id, uid)

@bot.message_handler(commands=["tarif"])
def cmd_tarif(message: types.Message) -> None:
    """/tarif buyrug'i — joriy tarif ma'lumoti + qayta tanlash imkoniyati.
    Profil yo'q bo'lsa onboarding boshlanadi."""
    uid  = message.from_user.id
    user = get_user(uid)
    if not user:
        start_onboarding(message)
        return
    lang = lang_of(uid)
    bot.send_message(
        message.chat.id,
        tr(lang, "sub_info", tier=sub_label(uid), expires=sub_expires_str(uid))
        + f"\n\n{tr(lang, 'choose_tariff')}",
        parse_mode="HTML",
        reply_markup=tariff_keyboard(uid),
    )
    USER_STATES[uid] = "choosing_tariff"

@bot.message_handler(commands=["lang"])
def cmd_lang(message: types.Message) -> None:
    """/lang buyrug'i — tilni o'zgartirish.
    "choosing_lang_change" holati — allaqachon ro'yxatdan o'tgan uchun alohida holat,
    onboarding oqimiga qaytmaydi."""
    uid = message.from_user.id
    USER_STATES[uid] = "choosing_lang_change"
    bot.send_message(
        message.chat.id,
        "🌐 Tilni tanlang / Choose language / Выберите язык:",
        reply_markup=lang_keyboard(),
    )

@bot.message_handler(commands=["clear"])
def cmd_clear(message: types.Message) -> None:
    """/clear buyrug'i — barcha xarajatlarni o'chirish tasdiqi."""
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    bot.send_message(message.chat.id, t(uid, "confirm_clear"),
                     reply_markup=confirm_keyboard(uid))

@bot.message_handler(commands=["admin"])
def cmd_admin(message: types.Message) -> None:
    """/admin buyrug'i — admin panel (faqat ADMIN_IDS uchun).
    Umumiy statistika + boshqaruv klaviaturasi ko'rsatiladi."""
    if message.from_user.id not in ADMIN_IDS:
        return
    bot.send_message(
        message.chat.id,
        admin_overall_stats(),
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )

@bot.message_handler(commands=["activate"])
def cmd_activate(message: types.Message) -> None:
    """/activate {uid} {tier} — admin tomonidan qo'lda tarif faollashtirish.
    Format: /activate 123456789 month3

    Foydalanuvchiga tarif faollashtirilgani haqida xabar yuboriladi.
    Admin paneldan tez faollashtirish tugmasi orqali ham qilish mumkin."""
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Format: /activate {uid} {tier}\nTariflar: trial | month3 | month6 | month12")
        return
    try:
        target_uid = int(parts[1])
    except ValueError:
        bot.reply_to(message, "UID noto'g'ri.")
        return
    tier = parts[2]
    if tier not in TARIFF_META:
        bot.reply_to(message, f"Noto'g'ri tarif. Tariflar: {', '.join(TARIFF_META)}")
        return
    expires = activate_subscription(target_uid, tier)
    lang    = lang_of(target_uid)
    label   = TARIFF_META[tier].get(f"label_{lang}", tier)
    try:
        bot.send_message(
            target_uid,
            tr(lang, "sub_activated", label=label, expires=expires),
            parse_mode="HTML", reply_markup=main_keyboard(target_uid),
        )
        USER_STATES[target_uid] = "main"
    except Exception:
        pass
    bot.reply_to(message, f"✅ UID {target_uid} uchun {tier} tarifi faollashtirildi. ({expires} gacha)")


# ════════════════════════════════════════════════════════════════════
#  CALLBACK QUERY HANDLER
#
#  Barcha inline tugma bosishlarini bir joyda ushlaydi.
#  callback_data qiymatiga qarab tegishli blokga yo'naltiradi:
#
#    "adm:*"       → admin panel amallari
#    "adm_act:*"   → admin tomonidan tarif faollashtirish
#    "adm_reject:*"→ admin tomonidan to'lovni rad etish
#    "lang:*"      → til tanlash / o'zgartirish
#    "tariff:*"    → tarif tanlash (onboarding)
#    "period:*"    → davr bo'yicha xarajatlar ro'yxati
#    "chart"       → grafik davri tanlash
#    "chart:*"     → grafik generatsiya
#    "cats"        → kategoriya grafik
#    "stats"       → statistika
#    "tarif_info"  → tarif ma'lumoti
#    "clear"       → o'chirish tasdiqi
#    "confirm_clear" → o'chirishni tasdiqlash
#    "cancel_clear"  → bekor qilish
# ════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: True)
def on_callback(call: types.CallbackQuery) -> None:
    uid  = call.from_user.id
    # Telegram'ga tugma bosilganini bildirish (loading animatsiyasini o'chirish)
    bot.answer_callback_query(call.id)
    data = call.data

    # ── Admin panel callbacklari ──────────────────────────────────
    if uid in ADMIN_IDS and data.startswith("adm"):

        if data.startswith("adm_act:"):
            # Format: "adm_act:{target_uid}:{tier}"
            _, target_str, tier = data.split(":")
            target_uid = int(target_str)
            if tier not in TARIFF_META:
                bot.answer_callback_query(call.id, "Noto'g'ri tarif!", show_alert=True)
                return
            expires   = activate_subscription(target_uid, tier)
            lang_u    = lang_of(target_uid)
            label     = TARIFF_META[tier].get(f"label_{lang_u}", tier)
            _pending_payments.pop(target_uid, None)
            # Foydalanuvchiga faollashtirish xabari
            try:
                bot.send_message(
                    target_uid,
                    tr(lang_u, "sub_activated", label=label, expires=expires),
                    parse_mode="HTML", reply_markup=main_keyboard(target_uid),
                )
                USER_STATES[target_uid] = "main"
            except Exception:
                pass
            # Admin xabarini yangilash — tasdiqlangan deb belgilash
            user          = get_user(target_uid)
            uname_display = user["name"] if user else str(target_uid)
            bot.edit_message_text(
                f"✅ <b>Faollashtirildi!</b>\n\n"
                f"👤 {clean(uname_display)}\n"
                f"🆔 <code>{target_uid}</code>\n"
                f"📦 {label}\n"
                f"📅 {expires} gacha",
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML",
            )
            return

        if data.startswith("adm_reject:"):
            # Format: "adm_reject:{target_uid}"
            target_uid = int(data.split(":")[1])
            _pending_payments.pop(target_uid, None)
            bot.edit_message_text(
                f"❌ To'lov rad etildi — ID: <code>{target_uid}</code>",
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML",
            )
            try:
                bot.send_message(
                    target_uid,
                    "❌ To'lovingiz tasdiqlanmadi. Muammo bo'lsa admin bilan bog'laning.",
                )
            except Exception:
                pass
            return

        if data == "adm:stats":
            # Statistikani yangilash
            bot.edit_message_text(
                admin_overall_stats(),
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML", reply_markup=admin_panel_keyboard(),
            )
            return

        if data == "adm:users":
            # Barcha (ro'yxatdan o'tgan) foydalanuvchilar ro'yxati — maksimum 30 ta
            real_users = [(uid_str, u) for uid_str, u in _users.items()
                          if not u.get("_pending")]
            if not real_users:
                bot.answer_callback_query(call.id, "Foydalanuvchilar yo'q.", show_alert=True)
                return
            lines = []
            for uid_str, u in real_users[:30]:
                tier = u.get("sub", {}).get("tier", "free")
                icon = "💎" if is_premium(int(uid_str)) else "🆓"
                lines.append(f"{icon} <b>{clean(u['name'])}</b> — <code>{uid_str}</code> [{tier}]")
            text = f"👥 <b>Foydalanuvchilar ({len(real_users)} ta):</b>\n\n" + "\n".join(lines)
            if len(real_users) > 30:
                text += f"\n\n... va yana {len(real_users) - 30} ta"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:back"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode="HTML", reply_markup=kb)
            return

        if data == "adm:premium":
            # Aktiv premium foydalanuvchilar
            premium_users = [(uid_str, u) for uid_str, u in _users.items()
                             if not u.get("_pending") and is_premium(int(uid_str))]
            if not premium_users:
                bot.answer_callback_query(call.id, "Premium foydalanuvchilar yo'q.", show_alert=True)
                return
            lines = []
            for uid_str, u in premium_users:
                tier    = u.get("sub", {}).get("tier", "—")
                expires = sub_expires_str(int(uid_str))
                lines.append(
                    f"💎 <b>{clean(u['name'])}</b> — <code>{uid_str}</code>\n"
                    f"   📦 {tier} | 📅 {expires}"
                )
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:back"))
            bot.edit_message_text(
                f"💎 <b>Premium foydalanuvchilar ({len(premium_users)} ta):</b>\n\n"
                + "\n\n".join(lines),
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML", reply_markup=kb,
            )
            return

        if data == "adm:payments":
            # Kutilayotgan to'lov so'rovlari ro'yxati
            if not _pending_payments:
                bot.answer_callback_query(call.id, "Kutilayotgan to'lov yo'q.", show_alert=True)
                return
            lines = []
            for puid, ptier in _pending_payments.items():
                u     = get_user(puid)
                label = TARIFF_META.get(ptier, {}).get("label_uz", ptier)
                name  = clean(u["name"]) if u else str(puid)
                lines.append(f"👤 <b>{name}</b> — <code>{puid}</code> → {label}")
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:back"))
            bot.edit_message_text(
                f"💳 <b>Kutilayotgan to'lovlar ({len(_pending_payments)} ta):</b>\n\n"
                + "\n".join(lines),
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML", reply_markup=kb,
            )
            return

        if data == "adm:back":
            # Admin bosh panelga qaytish
            bot.edit_message_text(
                admin_overall_stats(),
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML", reply_markup=admin_panel_keyboard(),
            )
            return

    # ── Til tanlash / o'zgartirish ────────────────────────────────
    if data.startswith("lang:"):
        lang  = data.split(":")[1]
        state = USER_STATES.get(uid, "")
        if state == "choosing_lang_change":
            # /lang buyrug'i orqali — faqat tilni yangilash, onboarding emas
            update_user(uid, lang=lang)
            USER_STATES[uid] = "main"
            bot.edit_message_text(
                f"✅ Til o'zgartirildi → {lang.upper()}",
                call.message.chat.id, call.message.message_id,
            )
        else:
            # Onboarding: til tanlash bosqichi
            handle_lang_chosen(call, lang)
        return

    # ── Tarif tanlash (onboarding) ────────────────────────────────
    if data.startswith("tariff:"):
        tariff = data.split(":")[1]
        handle_tariff_chosen(call, tariff)
        return

    # ── Quyidagi barcha callbacklar faqat "main" holatda ishlaydi ─
    if USER_STATES.get(uid) != "main":
        return

    if data.startswith("period:"):
        # Davr bo'yicha xarajatlar ro'yxatini ko'rsatish
        period = data.split(":")[1]
        days   = {"week": 7, "month": 30, "all": None}[period]
        label  = t(uid, f"btn_{period}")
        rows   = get_by_period(uid, days)
        if rows:
            lines = []
            for i, (a, p, _, code) in enumerate(rows, 1):
                icon, _ = get_category(p)
                code_str = f" 🆔{code}" if code else ""
                lines.append(f"{i}. {icon} {clean(p)}{code_str} — {fmt(a)} so'm")
            total = sum(r[0] for r in rows)
            bot.send_message(
                call.message.chat.id,
                f"{label} harajatlar ({len(rows)} ta):\n\n" + "\n".join(lines)
                + f"\n\n💰 <b>Jami: {fmt(total)} so'm</b>",
                parse_mode="HTML", reply_markup=main_keyboard(uid),
            )
        else:
            bot.send_message(call.message.chat.id, t(uid, "no_expense"))

    elif data == "stats":
        send_stats(call.message.chat.id, uid)

    elif data == "chart":
        # Chiziqli grafik — avval davr tanlash so'raladi
        if not is_premium(uid):
            bot.send_message(call.message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, t(uid, "which_period"),
                             reply_markup=period_keyboard(uid))

    elif data.startswith("chart:"):
        # Tanlangan davr uchun grafik yaratish
        if not is_premium(uid):
            bot.send_message(call.message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        else:
            period = data.split(":")[1]
            send_chart(call.message.chat.id, uid, period)

    elif data == "cats":
        # Doiraviy kategoriya grafik
        if not is_premium(uid):
            bot.send_message(call.message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        else:
            send_cat_chart(call.message.chat.id, uid)

    elif data == "tarif_info":
        # Joriy tarif ma'lumoti + qayta tanlash
        lang = lang_of(uid)
        bot.send_message(
            call.message.chat.id,
            tr(lang, "sub_info", tier=sub_label(uid), expires=sub_expires_str(uid))
            + f"\n\n{tr(lang, 'choose_tariff')}",
            parse_mode="HTML", reply_markup=tariff_keyboard(uid),
        )
        USER_STATES[uid] = "choosing_tariff"

    elif data == "clear":
        # O'chirish tasdiqi so'raladi
        bot.send_message(call.message.chat.id, t(uid, "confirm_clear"),
                         reply_markup=confirm_keyboard(uid))

    elif data == "confirm_clear":
        # Tasdiqlandi — barcha xarajatlarni o'chirish
        count = len(get_user_expenses(uid))
        clear_user_expenses(uid)
        bot.send_message(call.message.chat.id, t(uid, "cleared", count=count))

    elif data == "cancel_clear":
        # Bekor qilindi
        bot.send_message(call.message.chat.id, t(uid, "cancelled"))


# ════════════════════════════════════════════════════════════════════
#  MEDIA HANDLERLAR
# ════════════════════════════════════════════════════════════════════

@bot.message_handler(content_types=["photo"])
def on_photo(message: types.Message) -> None:
    """Foydalanuvchi rasm yuborsa ishga tushadi (premium talab qiladi).

    Oqim:
      1. Bot "o'qilmoqda..." xabarini yuboradi
      2. Telegram'dan eng yuqori sifatli rasmni yuklab oladi (message.photo[-1])
      3. preprocess_image → ocr_image orqali mahsulotlarni ajratadi
      4. Natijani saqlaydi va ko'rsatadi
      5. Vaqtincha fayl o'chiriladi (finally blok)
    """
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    if not is_premium(uid):
        bot.reply_to(message, t(uid, "premium_only"), parse_mode="HTML")
        return

    msg  = bot.reply_to(message, t(uid, "reading_img"))
    path = "check_photo.jpg"
    try:
        fi   = bot.get_file(message.photo[-1].file_id)  # Eng katta o'lchamli rasm
        data = bot.download_file(fi.file_path)
        with open(path, "wb") as f:
            f.write(data)
        results = process_png(path)
        if results:
            add_user_expenses(uid, results)
            send_added(message.chat.id, msg.message_id, uid, results)
        else:
            bot.edit_message_text(t(uid, "ocr_fail"), message.chat.id, msg.message_id,
                                  parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"⚠️ Xatolik: {e}", message.chat.id, msg.message_id)
    finally:
        # Har qanday holatda vaqtincha faylni tozalaymiz
        if os.path.exists(path):
            os.remove(path)


@bot.message_handler(content_types=["document"])
def on_document(message: types.Message) -> None:
    """Foydalanuvchi hujjat (PDF/rasm) yuborsa ishga tushadi (premium talab qiladi).

    Qo'llab-quvvatlanadigan formatlar:
      • PDF (mime: application/pdf yoki .pdf kengaytma)
      • Rasmlar: .jpg, .jpeg, .png, .webp, .bmp, .tiff, .tif

    Rasm hujjat sifatida yuborilsa ham (siqilmagan holda) ishlaydi.
    """
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    if not is_premium(uid):
        bot.reply_to(message, t(uid, "premium_only"), parse_mode="HTML")
        return

    doc       = message.document
    file_name = doc.file_name or ""
    ext       = os.path.splitext(file_name)[1].lower()
    mime      = doc.mime_type or ""

    is_pdf = mime == "application/pdf" or ext == ".pdf"
    is_img = (
        mime.startswith("image/")
        or ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif")
    )

    if not is_pdf and not is_img:
        bot.reply_to(message, t(uid, "format_unsupported"), parse_mode="HTML")
        return

    msg  = bot.reply_to(message, t(uid, "reading_pdf") if is_pdf else t(uid, "reading_img"))
    path = f"tmp_{doc.file_id}{ext}"

    try:
        fi   = bot.get_file(doc.file_id)
        data = bot.download_file(fi.file_path)
        with open(path, "wb") as f:
            f.write(data)
        results = process_pdf(path) if is_pdf else process_png(path)
        if results:
            add_user_expenses(uid, results)
            send_added(message.chat.id, msg.message_id, uid, results)
        else:
            bot.edit_message_text(t(uid, "ocr_fail"), message.chat.id, msg.message_id,
                                  parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"⚠️ Xatolik: {e}", message.chat.id, msg.message_id)
    finally:
        if os.path.exists(path):
            os.remove(path)


@bot.message_handler(func=lambda m: True)
def on_text(message: types.Message) -> None:
    """Barcha oddiy matn xabarlarini ushlaydi.

    Ishlash mantig'i:
      1. Onboarding: "entering_name" holatida → ism saqlanadi
      2. Ro'yxatdan o'tmagan → onboarding boshlanadi
      3. Bepul tarifda limit tekshiruvi (FREE_LIMIT = 100)
      4. Ko'p qatorli matn → parse_simple_text() bilan bir nechta mahsulot
      5. Bitta qator → birinchi raqam narx, qolgan matn mahsulot nomi
    """
    uid   = message.from_user.id
    state = USER_STATES.get(uid, "")

    # Onboarding bosqichi: ism kiritish
    if state == "entering_name":
        handle_name_entered(message)
        return

    # Ro'yxatdan o'tmagan yoki onboarding tugamagan
    if state != "main":
        start_onboarding(message)
        return

    # Bepul tarif limiti
    if not is_premium(uid) and len(get_user_expenses(uid)) >= FREE_LIMIT:
        bot.reply_to(message, t(uid, "free_limit"), parse_mode="HTML")
        return

    text  = message.text.strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Ko'p qatorli kiritish: "olma 15000\nnon 5000"
    if len(lines) > 1:
        results = parse_simple_text(text)
        if results:
            add_user_expenses(uid, results)
            added_total = sum(a for a, _, _ in results)
            bot.reply_to(
                message,
                f"✅ <b>{len(results)} ta harajat qo'shildi!</b>\n"
                f"💰 Shu safar: <b>{fmt(added_total)} so'm</b>\n\n"
                + build_full_list(uid),
                parse_mode="HTML", reply_markup=main_keyboard(uid),
            )
            return

    # Bitta qator: "olma 15000" yoki "15000 olma"
    nums = re.findall(r"\d+", text)
    if not nums:
        bot.reply_to(message, t(uid, "no_number"), parse_mode="HTML")
        return

    amount  = int(nums[0])
    # Raqamlarni olib tashlab, qolgan matnni mahsulot nomi qilamiz
    product = re.sub(r"\s+", " ", re.sub(r"\d+", "", text)).strip() or "Noma'lum"
    add_user_expenses(uid, [(amount, product, None)])
    icon, _ = get_category(product)

    bot.reply_to(
        message,
        f"✅ {icon} <b>{clean(product)}</b> — {fmt(amount)} so'm qo'shildi!\n\n"
        + build_full_list(uid),
        parse_mode="HTML", reply_markup=main_keyboard(uid),
    )


# ════════════════════════════════════════════════════════════════════
#  ISHGA TUSHIRISH
#
#  Bot infinity_polling() bilan ishlaydi — internet uzilsa avtomatik
#  qayta urinadi. logger_level=20 (INFO) — asosiy loglar ko'rinadi.
#
#  Heroku/Railway kabi platformalarda main.py orqali chaqiriladi:
#    from XisobchiAI import bot
#    bot.infinity_polling(logger_level=20)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("✅ Xisobchi AI v3.0 ishga tushdi")
    print("   Onboarding | Multi-lang | Subscription system")
    bot.infinity_polling(logger_level=20)
