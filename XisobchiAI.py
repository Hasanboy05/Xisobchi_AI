"""
Xisobchi AI — v3.0
Yangiliklar: til tanlash, onboarding, subscription tizimi, feature gating.
"""

import telebot
from telebot import types
from PIL import Image, ImageFilter, ImageEnhance
import pytesseract
import re
import os
import json
import io
from datetime import datetime, timedelta
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from translations import tr

try:
    import fitz
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# ── SOZLAMALAR ──────────────────────────────────────────
TOKEN       = os.getenv("TELEGRAM_TOKEN", "")
DATA_FILE   = "expenses.json"
USERS_FILE  = "users.json"
FREE_LIMIT  = 100   # bepul tarifda max mahsulot soni

TARIFF_META = {
    "trial":   {"days": 7,   "label_uz": "7 kun sinov",  "label_en": "7-day trial",    "label_ru": "7 дней пробный"},
    "month3":  {"days": 90,  "label_uz": "3 oy — 100 so'm", "label_en": "3 months",    "label_ru": "3 месяца"},
    "month6":  {"days": 180, "label_uz": "6 oy — 130 so'm", "label_en": "6 months",    "label_ru": "6 месяцев"},
    "month12": {"days": 365, "label_uz": "12 oy — 300 so'm","label_en": "12 months",   "label_ru": "12 месяцев"},
}

bot = telebot.TeleBot(TOKEN)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ── FOYDALANUVCHI HOLATLARI (in-memory) ─────────────────
# Mumkin qiymatlar: "choosing_lang" | "entering_name" | "choosing_tariff" | "main"
USER_STATES: dict[int, str] = {}


# ════════════════════════════════════════════════════════
# FOYDALANUVCHI PROFILI  (users.json)
# ════════════════════════════════════════════════════════

def _load_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_users(data: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

_users: dict = _load_users()


def get_user(uid: int) -> dict | None:
    return _users.get(str(uid))

def create_user(uid: int, name: str, lang: str) -> dict:
    profile = {
        "name":        name,
        "lang":        lang,
        "sub": {
            "tier":        "free",
            "expires":     None,
            "trial_used":  False,
        },
        "created_at": datetime.now().isoformat(),
    }
    _users[str(uid)] = profile
    _save_users(_users)
    return profile

def update_user(uid: int, **kwargs) -> None:
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


# ── Til yordamchi funksiyasi ─────────────────────────────
def lang_of(uid: int) -> str:
    user = get_user(uid)
    return user["lang"] if user else "uz"

def t(uid: int, key: str, **kwargs) -> str:
    return tr(lang_of(uid), key, **kwargs)


# ════════════════════════════════════════════════════════
# SUBSCRIPTION
# ════════════════════════════════════════════════════════

def is_premium(uid: int) -> bool:
    """Foydalanuvchi aktiv premium yoki trial tarifda ekanligini tekshiradi."""
    user = get_user(uid)
    if not user:
        return False
    sub = user.get("sub", {})
    tier = sub.get("tier", "free")
    if tier == "free":
        return False
    expires_str = sub.get("expires")
    if not expires_str:
        return False
    return datetime.now() < datetime.fromisoformat(expires_str)

def activate_subscription(uid: int, tier: str) -> str:
    """Tarifni faollashtiradi, expires sanasini qaytaradi."""
    days = TARIFF_META[tier]["days"]
    expires = datetime.now() + timedelta(days=days)
    update_user(uid, **{
        "sub.tier":    tier,
        "sub.expires": expires.isoformat(),
    })
    if tier == "trial":
        update_user(uid, **{"sub.trial_used": True})
    return expires.strftime("%d.%m.%Y")

def sub_label(uid: int) -> str:
    lang = lang_of(uid)
    user = get_user(uid)
    if not user:
        return "free"
    sub   = user.get("sub", {})
    tier  = sub.get("tier", "free")
    if tier == "free":
        return tr(lang, "btn_free")
    meta = TARIFF_META.get(tier, {})
    return meta.get(f"label_{lang}", tier)

def sub_expires_str(uid: int) -> str:
    user = get_user(uid)
    if not user:
        return "—"
    exp = user.get("sub", {}).get("expires")
    if not exp:
        return "—"
    return datetime.fromisoformat(exp).strftime("%d.%m.%Y")


# ════════════════════════════════════════════════════════
# XARAJATLAR MA'LUMOTLARI  (expenses.json)
# ════════════════════════════════════════════════════════

def _load_expenses() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
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
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

_expenses: dict = _load_expenses()


def get_user_expenses(uid: int) -> list:
    return _expenses.get(str(uid), [])

def add_user_expenses(uid: int, items: list) -> None:
    key = str(uid)
    now = datetime.now().isoformat()
    _expenses.setdefault(key, [])
    for amount, product, code in items:
        _expenses[key].append([amount, product, now, code])
    _save_expenses(_expenses)

def clear_user_expenses(uid: int) -> None:
    _expenses[str(uid)] = []
    _save_expenses(_expenses)

def get_by_period(uid: int, days: int | None) -> list:
    rows = get_user_expenses(uid)
    if days is None:
        return rows
    cutoff = datetime.now() - timedelta(days=days)
    return [r for r in rows if datetime.fromisoformat(r[2]) >= cutoff]


# ════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ════════════════════════════════════════════════════════

def fmt(amount: int) -> str:
    return f"{int(amount):,}".replace(",", " ")

def clean(name: str) -> str:
    return name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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
    n = name.lower()
    for keys, cat in CATEGORY_MAP.items():
        if any(k in n for k in keys.split("|")):
            return cat
    return ("🛒", "Boshqa")

def build_full_list(uid: int) -> str:
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


# ── Klaviaturalar ────────────────────────────────────────

def lang_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🇺🇿 O'zbek tili",  callback_data="lang:uz"),
        types.InlineKeyboardButton("🇬🇧 English",       callback_data="lang:en"),
        types.InlineKeyboardButton("🇷🇺 Русский",       callback_data="lang:ru"),
    )
    return kb

def tariff_keyboard(uid: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(t(uid, "btn_free"),   callback_data="tariff:free"),
        types.InlineKeyboardButton(t(uid, "btn_trial"),  callback_data="tariff:trial"),
        types.InlineKeyboardButton(t(uid, "btn_3m"),     callback_data="tariff:month3"),
        types.InlineKeyboardButton(t(uid, "btn_6m"),     callback_data="tariff:month6"),
        types.InlineKeyboardButton(t(uid, "btn_12m"),    callback_data="tariff:month12"),
    )
    return kb

def main_keyboard(uid: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(t(uid, "btn_week"),   callback_data="period:week"),
        types.InlineKeyboardButton(t(uid, "btn_month"),  callback_data="period:month"),
        types.InlineKeyboardButton(t(uid, "btn_all"),    callback_data="period:all"),
        types.InlineKeyboardButton(t(uid, "btn_chart"),  callback_data="chart"),
        types.InlineKeyboardButton(t(uid, "btn_cats"),   callback_data="cats"),
        types.InlineKeyboardButton(t(uid, "btn_stats"),  callback_data="stats"),
        types.InlineKeyboardButton(t(uid, "btn_tarif"),  callback_data="tarif_info"),
        types.InlineKeyboardButton(t(uid, "btn_clear"),  callback_data="clear"),
    )
    return kb

def period_keyboard(uid: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(t(uid, "btn_7days"),  callback_data="chart:week"),
        types.InlineKeyboardButton(t(uid, "btn_30days"), callback_data="chart:month"),
    )
    return kb

def confirm_keyboard(uid: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(t(uid, "btn_yes"), callback_data="confirm_clear"),
        types.InlineKeyboardButton(t(uid, "btn_no"),  callback_data="cancel_clear"),
    )
    return kb


# ════════════════════════════════════════════════════════
# RASM / PDF ISHLASH
# ════════════════════════════════════════════════════════

def preprocess_image(path: str) -> None:
    img = Image.open(path).convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img.save(path)

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

PRICE_RE = re.compile(r"([\d][\d\s]{1,9}[,\.]\d{2})\s*$")
CODE_RE  = re.compile(r"\b(\d{6,13})\b")

def parse_korzinka(text: str) -> list:
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
            if not (50 < price < 10_000_000):
                pending_name = ""
                continue
            name_part = re.sub(r"[^\w\s\-\.\%/]", " ", line[:m.start()]).strip()
            product_code = None
            cm = CODE_RE.search(name_part)
            if cm:
                product_code = cm.group(1)
                name_part = CODE_RE.sub("", name_part).strip()
            full_name = (pending_name + " " + name_part).strip() if pending_name else name_part
            pending_name = ""
            if len(full_name) >= 2:
                results.append((int(price), full_name, product_code))
        else:
            clean_line = re.sub(r"[^\w\s\-\.\%/]", " ", line).strip()
            pending_name = clean_line if len(clean_line) > 2 else ""
    return results

def parse_simple_text(text: str) -> list:
    results = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        nums = re.findall(r"\d+", line)
        if not nums:
            continue
        amount = int(nums[0])
        if amount < 50:
            continue
        product = re.sub(r"[^\w\s]", "", re.sub(r"\d+", "", line)).strip() or "Noma'lum"
        results.append((amount, product, None))
    return results

def ocr_image(path: str, lang: str = "uzb+rus+eng") -> list:
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
    if not PDF_SUPPORT:
        return []
    results = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                r = parse_korzinka(text) or parse_simple_text(text)
            else:
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
    preprocess_image(file_path)
    return ocr_image(file_path)


# ════════════════════════════════════════════════════════
# GRAFIKLAR
# ════════════════════════════════════════════════════════

def generate_line_chart(uid: int, period: str = "month") -> io.BytesIO | None:
    rows = get_by_period(uid, 30 if period == "month" else 7)
    if not rows:
        return None
    daily: dict = defaultdict(int)
    for amount, _, date_str, _ in rows:
        daily[datetime.fromisoformat(date_str).date()] += amount
    dates  = sorted(daily)
    values = [daily[d] for d in dates]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    ax.fill_between(dates, values, alpha=0.25, color="#e94560")
    ax.plot(dates, values, color="#e94560", linewidth=2.5, marker="o", markersize=6)
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
    buf.seek(0)
    return buf

def generate_pie_chart(uid: int) -> io.BytesIO | None:
    rows = get_user_expenses(uid)
    if not rows:
        return None
    cat_totals: dict = defaultdict(int)
    for amount, product, _, _ in rows:
        icon, cat_name = get_category(product)
        cat_totals[f"{icon} {cat_name}"] += amount
    labels = list(cat_totals)
    values = list(cat_totals.values())
    COLORS = ["#e94560","#0f3460","#533483","#f5a623",
              "#7ed321","#4a90e2","#bd10e0","#50e3c2","#b8e986","#ff6b6b"]

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


# ════════════════════════════════════════════════════════
# YUBORISH YORDAMCHILARI
# ════════════════════════════════════════════════════════

def send_stats(chat_id: int, uid: int) -> None:
    rows = get_user_expenses(uid)
    if not rows:
        bot.send_message(chat_id, t(uid, "no_expense"))
        return
    total = sum(r[0] for r in rows)
    count = len(rows)
    mx    = max(rows, key=lambda x: x[0])
    mn    = min(rows, key=lambda x: x[0])
    week  = sum(r[0] for r in get_by_period(uid, 7))
    mon   = sum(r[0] for r in get_by_period(uid, 30))
    freq  = defaultdict(int)
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
    buf = generate_line_chart(uid, period)
    label = "30 kunlik" if period == "month" else "7 kunlik"
    if buf:
        bot.send_photo(chat_id, buf, caption=f"📈 {label} harajatlar",
                       reply_markup=main_keyboard(uid))
    else:
        bot.send_message(chat_id, t(uid, "no_chart"), reply_markup=main_keyboard(uid))

def send_cat_chart(chat_id: int, uid: int) -> None:
    buf = generate_pie_chart(uid)
    if buf:
        bot.send_photo(chat_id, buf, caption="🏷️ Kategoriyalar bo'yicha taqsimot",
                       reply_markup=main_keyboard(uid))
    else:
        bot.send_message(chat_id, t(uid, "no_expense"), reply_markup=main_keyboard(uid))

def send_added(chat_id: int, msg_id: int, uid: int, results: list) -> None:
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


# ════════════════════════════════════════════════════════
# ONBOARDING OQIMI
# ════════════════════════════════════════════════════════

def start_onboarding(message: types.Message) -> None:
    uid = message.from_user.id
    USER_STATES[uid] = "choosing_lang"
    bot.send_message(
        message.chat.id,
        "🌐 Tilni tanlang / Choose language / Выберите язык:",
        reply_markup=lang_keyboard(),
    )

def handle_lang_chosen(call: types.CallbackQuery, lang: str) -> None:
    uid = call.from_user.id
    USER_STATES[uid] = "entering_name"
    # Vaqtinchalik tilni saqlash (profil hali yo'q)
    _users[str(uid)] = {"lang": lang, "_pending": True}
    _save_users(_users)
    bot.edit_message_text(
        tr(lang, "enter_name"),
        call.message.chat.id,
        call.message.message_id,
    )

def handle_name_entered(message: types.Message) -> None:
    uid  = message.from_user.id
    lang = _users.get(str(uid), {}).get("lang", "uz")
    name = message.text.strip()
    if len(name) < 2:
        bot.send_message(message.chat.id, tr(lang, "enter_name"))
        return
    # Profil yaratamiz
    create_user(uid, name, lang)
    USER_STATES[uid] = "choosing_tariff"
    bot.send_message(
        message.chat.id,
        tr(lang, "name_saved", name=clean(name)),
    )
    bot.send_message(
        message.chat.id,
        tr(lang, "choose_tariff"),
        reply_markup=tariff_keyboard(uid),
    )

def handle_tariff_chosen(call: types.CallbackQuery, tariff: str) -> None:
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
        # To'lovli tariflar — to'lov yo'riqnomasi
        label = TARIFF_META.get(tariff, {}).get(f"label_{lang}", tariff)
        bot.edit_message_text(
            tr(lang, "pay_info", label=label, uid=uid),
            call.message.chat.id, call.message.message_id,
            parse_mode="HTML",
        )
        # Onboarding tugaydi, tarif to'lovdan keyin admin tomonidan faollashtiriladi
        USER_STATES[uid] = "main"
        bot.send_message(
            call.message.chat.id,
            f"{tr(lang, 'desc_free')}\n\n"
            "Shu orada bepul tarifdan foydalanishingiz mumkin.",
            parse_mode="HTML", reply_markup=main_keyboard(uid),
        )


# ════════════════════════════════════════════════════════
# HANDLERLAR
# ════════════════════════════════════════════════════════

@bot.message_handler(commands=["start", "hello"])
def cmd_start(message: types.Message) -> None:
    uid = message.from_user.id
    user = get_user(uid)
    if user and not user.get("_pending"):
        # Allaqachon ro'yxatdan o'tgan
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
    uid = message.from_user.id
    bot.send_message(message.chat.id, t(uid, "help_text"),
                     parse_mode="HTML", reply_markup=main_keyboard(uid))

@bot.message_handler(commands=["stats"])
def cmd_stats(message: types.Message) -> None:
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    send_stats(message.chat.id, uid)

@bot.message_handler(commands=["chart"])
def cmd_chart(message: types.Message) -> None:
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
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    if not is_premium(uid):
        bot.send_message(message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        return
    send_cat_chart(message.chat.id, uid)

@bot.message_handler(commands=["tarif"])
def cmd_tarif(message: types.Message) -> None:
    uid = message.from_user.id
    user = get_user(uid)
    if not user:
        start_onboarding(message)
        return
    lang = lang_of(uid)
    # Joriy tarif info + qayta tanlash tugmasi
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
    uid = message.from_user.id
    USER_STATES[uid] = "choosing_lang_change"
    bot.send_message(
        message.chat.id,
        "🌐 Tilni tanlang / Choose language / Выберите язык:",
        reply_markup=lang_keyboard(),
    )

@bot.message_handler(commands=["clear"])
def cmd_clear(message: types.Message) -> None:
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    bot.send_message(message.chat.id, t(uid, "confirm_clear"),
                     reply_markup=confirm_keyboard(uid))

# ── Admin: tarifni qo'lda faollashtirish ─────────────────
# /activate {uid} {tier}  — faqat admin foydalanadi
ADMIN_IDS = {7920968216, 5115387272}  # <-- 2 ta admin Telegram ID sini qo'shing
    # Misol: ali         xasanboy001   
@bot.message_handler(commands=["activate"])
def cmd_activate(message: types.Message) -> None:
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
    lang = lang_of(target_uid)
    label = TARIFF_META[tier].get(f"label_{lang}", tier)
    # Foydalanuvchiga xabar
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


# ── CALLBACK HANDLER ────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def on_callback(call: types.CallbackQuery) -> None:
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    data = call.data

    # ── Onboarding: til tanlash ──────────────────────────
    if data.startswith("lang:"):
        lang = data.split(":")[1]
        state = USER_STATES.get(uid, "")
        if state == "choosing_lang_change":
            # Faqat tilni o'zgartirish
            update_user(uid, lang=lang)
            USER_STATES[uid] = "main"
            bot.edit_message_text(
                f"✅ Til o'zgartirildi → {lang.upper()}",
                call.message.chat.id, call.message.message_id,
            )
        else:
            handle_lang_chosen(call, lang)
        return

    # ── Onboarding: tarif tanlash ────────────────────────
    if data.startswith("tariff:"):
        tariff = data.split(":")[1]
        handle_tariff_chosen(call, tariff)
        return

    # ── Asosiy bot funksiyalari (faqat "main" holatda) ───
    if USER_STATES.get(uid) != "main":
        return

    if data.startswith("period:"):
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
        if not is_premium(uid):
            bot.send_message(call.message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, t(uid, "which_period"),
                             reply_markup=period_keyboard(uid))

    elif data.startswith("chart:"):
        if not is_premium(uid):
            bot.send_message(call.message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        else:
            period = data.split(":")[1]
            send_chart(call.message.chat.id, uid, period)

    elif data == "cats":
        if not is_premium(uid):
            bot.send_message(call.message.chat.id, t(uid, "premium_only"), parse_mode="HTML")
        else:
            send_cat_chart(call.message.chat.id, uid)

    elif data == "tarif_info":
        lang = lang_of(uid)
        bot.send_message(
            call.message.chat.id,
            tr(lang, "sub_info", tier=sub_label(uid), expires=sub_expires_str(uid))
            + f"\n\n{tr(lang, 'choose_tariff')}",
            parse_mode="HTML", reply_markup=tariff_keyboard(uid),
        )
        USER_STATES[uid] = "choosing_tariff"

    elif data == "clear":
        bot.send_message(call.message.chat.id, t(uid, "confirm_clear"),
                         reply_markup=confirm_keyboard(uid))

    elif data == "confirm_clear":
        count = len(get_user_expenses(uid))
        clear_user_expenses(uid)
        bot.send_message(call.message.chat.id, t(uid, "cleared", count=count))

    elif data == "cancel_clear":
        bot.send_message(call.message.chat.id, t(uid, "cancelled"))


# ── RASM HANDLERI ───────────────────────────────────────

@bot.message_handler(content_types=["photo"])
def on_photo(message: types.Message) -> None:
    uid = message.from_user.id
    if USER_STATES.get(uid) != "main":
        return
    if not is_premium(uid):
        bot.reply_to(message, t(uid, "premium_only"), parse_mode="HTML")
        return

    msg  = bot.reply_to(message, t(uid, "reading_img"))
    path = "check_photo.jpg"
    try:
        fi   = bot.get_file(message.photo[-1].file_id)
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
        if os.path.exists(path):
            os.remove(path)


# ── HUJJAT HANDLERI ─────────────────────────────────────

@bot.message_handler(content_types=["document"])
def on_document(message: types.Message) -> None:
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

    kind = "PDF" if is_pdf else "PNG/JPG"
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


# ── MATN HANDLERI ───────────────────────────────────────

@bot.message_handler(func=lambda m: True)
def on_text(message: types.Message) -> None:
    uid   = message.from_user.id
    state = USER_STATES.get(uid, "")

    # Onboarding: ism kiritish bosqichi
    if state == "entering_name":
        handle_name_entered(message)
        return

    # Ro'yxatdan o'tmagan foydalanuvchi
    if state != "main":
        start_onboarding(message)
        return

    # Bepul tarifda limit tekshiruvi
    if not is_premium(uid) and len(get_user_expenses(uid)) >= FREE_LIMIT:
        bot.reply_to(message, t(uid, "free_limit"), parse_mode="HTML")
        return

    text  = message.text.strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

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

    nums = re.findall(r"\d+", text)
    if not nums:
        bot.reply_to(message, t(uid, "no_number"), parse_mode="HTML")
        return

    amount  = int(nums[0])
    product = re.sub(r"\s+", " ", re.sub(r"\d+", "", text)).strip() or "Noma'lum"
    add_user_expenses(uid, [(amount, product, None)])
    icon, _ = get_category(product)

    bot.reply_to(
        message,
        f"✅ {icon} <b>{clean(product)}</b> — {fmt(amount)} so'm qo'shildi!\n\n"
        + build_full_list(uid),
        parse_mode="HTML", reply_markup=main_keyboard(uid),
    )


# ════════════════════════════════════════════════════════
# ISHGA TUSHIRISH
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("✅ Xisobchi AI v3.0 ishga tushdi")
    print("   Onboarding | Multi-lang | Subscription system")
    bot.infinity_polling(logger_level=20)
