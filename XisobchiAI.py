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

try:
    import fitz
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# ── SOZLAMALAR ─────────────────────────────────────────
TOKEN     = "8904677991:AAGc7f2UyR5alJPy5mnfnBKDoo3vxz5xOgw"
DATA_FILE = "expenses.json"

bot = telebot.TeleBot(TOKEN)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ── MA'LUMOTLARNI SAQLASH (yangilangan tuzilma) ─────────
def load_expenses():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Eski formatni yangilash (3 → 4 element)
                for uid, items in data.items():
                    new_items = []
                    for it in items:
                        if len(it) == 3:
                            # [summa, nom, sana] -> [summa, nom, sana, None]
                            new_items.append([it[0], it[1], it[2], None])
                        else:
                            new_items.append(it)
                    data[uid] = new_items
                return data
        except Exception:
            pass
    return {}

def save_expenses(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

all_expenses = load_expenses()

def get_user_expenses(uid):
    return all_expenses.get(str(uid), [])

def add_user_expenses(uid, items):
    """
    items: [(amount, product, product_code), ...]
    product_code ixtiyoriy (agar None bo'lsa, saqlanmaydi)
    """
    key = str(uid)
    now = datetime.now().isoformat()
    if key not in all_expenses:
        all_expenses[key] = []
    for amount, product, code in items:
        all_expenses[key].append([amount, product, now, code])
    save_expenses(all_expenses)

def clear_user_expenses(uid):
    all_expenses[str(uid)] = []
    save_expenses(all_expenses)

def get_by_period(uid, days=None):
    rows = get_user_expenses(uid)
    if days is None:
        return rows
    cutoff = datetime.now() - timedelta(days=days)
    return [r for r in rows if datetime.fromisoformat(r[2]) >= cutoff]

# ── YORDAMCHI ──────────────────────────────────────────
def format_amount(amount):
    return f"{int(amount):,}".replace(",", " ")

def clean_name(name):
    return (name
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))

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

def get_category(name):
    n = name.lower()
    for keys, cat in CATEGORY_MAP.items():
        if any(k in n for k in keys.split("|")):
            return cat
    return ("🛒", "Boshqa")

def build_full_list(uid):
    rows = get_user_expenses(uid)
    if not rows:
        return "📭 Ro'yxat bo'sh"
    lines = []
    for i, (a, p, _, code) in enumerate(rows, 1):
        icon, _ = get_category(p)
        code_str = f" 🆔{code}" if code else ""
        lines.append(f"{i}. {icon} {clean_name(p)}{code_str} — {format_amount(a)} so'm")
    total = sum(r[0] for r in rows)
    return (
        "<b>🧾 Barcha harajatlar:</b>\n"
        + "\n".join(lines)
        + f"\n\n💰 <b>Jami: {format_amount(total)} so'm</b>"
    )

def get_main_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📅 Haftalik",   callback_data="week"),
        types.InlineKeyboardButton("🗓️ Oylik",      callback_data="month"),
        types.InlineKeyboardButton("📊 Barchasi",   callback_data="all"),
        types.InlineKeyboardButton("📈 Grafik",     callback_data="chart"),
        types.InlineKeyboardButton("🏷️ Kategoriya", callback_data="cats"),
        types.InlineKeyboardButton("📉 Statistika", callback_data="stats"),
        types.InlineKeyboardButton("🗑️ Tozalash",   callback_data="clear"),
    )
    return markup

# ── RASM TAYYORLASH ────────────────────────────────────
def preprocess_image(path):
    img = Image.open(path).convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img.save(path)
    return img

# ── KORZINKA CHEK PARSERI (kod qo'shilgan) ──────────────
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
CODE_RE  = re.compile(r"\b(\d{6,13})\b")   # 6 dan 13 gacha raqam (artikul/shtrix)

def parse_korzinka(text):
    """
    Qaytaradi: [(summa, mahsulot_nomi, mahsulot_kodi), ...]
    """
    results = []
    lines   = [l.strip() for l in text.split("\n")]

    pending_name = ""

    for line in lines:
        if not line or len(line) < 3:
            pending_name = ""
            continue

        low = line.lower()
        if any(kw in low for kw in SKIP_WORDS):
            pending_name = ""
            continue

        m = PRICE_RE.search(line)
        if m:
            raw_price = m.group(1).replace(" ", "").replace(",", ".")
            try:
                price = float(raw_price)
            except ValueError:
                pending_name = ""
                continue

            if not (50 < price < 10_000_000):
                pending_name = ""
                continue

            name_part = line[:m.start()].strip()
            name_part = re.sub(r"[^\w\s\-\.\%/]", " ", name_part).strip()

            # Mahsulot kodini ajratib olish
            product_code = None
            code_match = CODE_RE.search(name_part)
            if code_match:
                product_code = code_match.group(1)
                # Kodni nomdan olib tashlaymiz
                name_part = CODE_RE.sub("", name_part).strip()

            if pending_name:
                full_name = (pending_name + " " + name_part).strip()
                pending_name = ""
            else:
                full_name = name_part

            if len(full_name) < 2:
                continue

            results.append((int(price), full_name, product_code))
        else:
            clean = re.sub(r"[^\w\s\-\.\%/]", " ", line).strip()
            if len(clean) > 2:
                pending_name = clean
            else:
                pending_name = ""

    return results

def parse_simple_text(text):
    """Matndan (qo'lda kiritilgan) kod qidirilmaydi."""
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

def ocr_image(path, lang="uzb+rus+eng"):
    best_results = []
    for psm in ["6", "4", "3"]:
        try:
            text = pytesseract.image_to_string(
                Image.open(path), lang=lang,
                config=f"--psm {psm} --oem 3"
            )
            r = parse_korzinka(text)
            if len(r) > len(best_results):
                best_results = r
        except Exception as e:
            print(f"[OCR psm={psm}] {e}")
    if not best_results:
        try:
            text = pytesseract.image_to_string(Image.open(path), lang=lang)
            best_results = parse_simple_text(text)
        except Exception:
            pass
    return best_results

def process_pdf(pdf_path):
    if not PDF_SUPPORT:
        return []
    results = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                r = parse_korzinka(text)
                if not r:
                    r = parse_simple_text(text)
                results.extend(r)
            else:
                pix      = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                img_path = f"pdf_page_{i}.png"
                pix.save(img_path)
                preprocess_image(img_path)
                results.extend(ocr_image(img_path))
                if os.path.exists(img_path):
                    os.remove(img_path)
        doc.close()
    except Exception as e:
        print(f"[PDF xatolik] {e}")
    return results

def process_png(file_path):
    preprocess_image(file_path)
    return ocr_image(file_path)

# ── GRAFIK (o'zgarmagan) ───────────────────────────────
def generate_line_chart(uid, period="month"):
    rows = get_by_period(uid, days=30 if period == "month" else 7)
    if not rows:
        return None

    daily = defaultdict(int)
    for amount, _, date_str, _ in rows:
        day = datetime.fromisoformat(date_str).date()
        daily[day] += amount

    dates  = sorted(daily.keys())
    values = [daily[d] for d in dates]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    ax.fill_between(dates, values, alpha=0.25, color="#e94560")
    ax.plot(dates, values, color="#e94560", linewidth=2.5, marker="o", markersize=6)

    for date, val in zip(dates, values):
        ax.annotate(
            f"{format_amount(val)}",
            xy=(date, val), xytext=(0, 10),
            textcoords="offset points",
            ha="center", fontsize=7, color="#ffffff",
        )

    label = "30 kunlik" if period == "month" else "7 kunlik"
    ax.set_title(f"🛒 {label} xarajatlar grafigi", color="white", fontsize=13, pad=15)
    ax.set_xlabel("Sana", color="#aaaaaa", fontsize=10)
    ax.set_ylabel("So'm", color="#aaaaaa", fontsize=10)
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

def generate_pie_chart(uid):
    rows = get_user_expenses(uid)
    if not rows:
        return None

    cat_totals = defaultdict(int)
    for amount, product, _, _ in rows:
        icon, cat_name = get_category(product)
        cat_totals[f"{icon} {cat_name}"] += amount

    labels = list(cat_totals.keys())
    values = list(cat_totals.values())

    COLORS = ["#e94560","#0f3460","#533483","#f5a623",
              "#7ed321","#4a90e2","#bd10e0","#50e3c2","#b8e986","#ff6b6b"]

    fig, ax = plt.subplots(figsize=(8, 8))
    fig.patch.set_facecolor("#1a1a2e")
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.1f%%",
        colors=COLORS[:len(labels)], startangle=140,
        textprops={"color": "white", "fontsize": 10},
        pctdistance=0.82,
    )
    for at in autotexts:
        at.set_fontsize(9)
    total = sum(values)
    ax.set_title(
        f"🏷️ Kategoriyalar bo'yicha\nJami: {format_amount(total)} so'm",
        color="white", fontsize=13, pad=20,
    )

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf

# ── STATISTIKA FUNKSIYALARI ────────────────────────────
def _send_stats(chat_id, uid):
    rows = get_user_expenses(uid)
    if not rows:
        bot.send_message(chat_id, "📭 Harajatlar yo'q.")
        return
    total  = sum(r[0] for r in rows)
    count  = len(rows)
    mx     = max(rows, key=lambda x: x[0])
    mn     = min(rows, key=lambda x: x[0])
    week_t = sum(r[0] for r in get_by_period(uid, 7))
    mon_t  = sum(r[0] for r in get_by_period(uid, 30))
    # Eng ko'p uchragan mahsulot?
    product_counts = defaultdict(int)
    for _, p, _, _ in rows:
        product_counts[p] += 1
    most_freq = max(product_counts.items(), key=lambda x: x[1]) if product_counts else ("-", 0)

    bot.send_message(
        chat_id,
        f"📈 <b>Statistika</b>\n\n"
        f"📦 Jami yozuvlar: <b>{count}</b> ta\n"
        f"💰 Umumiy: <b>{format_amount(total)} so'm</b>\n"
        f"📊 O'rtacha: <b>{format_amount(total // count)} so'm</b>\n\n"
        f"📅 Haftalik: <b>{format_amount(week_t)} so'm</b>\n"
        f"🗓️ Oylik: <b>{format_amount(mon_t)} so'm</b>\n\n"
        f"⬆️ Eng qimmat: <b>{clean_name(mx[1])}</b> — {format_amount(mx[0])} so'm\n"
        f"⬇️ Eng arzon: <b>{clean_name(mn[1])}</b> — {format_amount(mn[0])} so'm\n"
        f"🔁 Eng ko'p: <b>{clean_name(most_freq[0])}</b> ({most_freq[1]} marta)",
        parse_mode="HTML", reply_markup=get_main_markup(),
    )

def _send_chart(chat_id, uid, period):
    buf = generate_line_chart(uid, period)
    if buf:
        label = "30 kunlik" if period == "month" else "7 kunlik"
        bot.send_photo(chat_id, buf, caption=f"📈 {label} harajatlar",
                       reply_markup=get_main_markup())
    else:
        bot.send_message(chat_id, "📭 Grafik uchun ma'lumot yo'q.",
                         reply_markup=get_main_markup())

def _send_cat_chart(chat_id, uid):
    buf = generate_pie_chart(uid)
    if buf:
        bot.send_photo(chat_id, buf, caption="🏷️ Kategoriyalar bo'yicha taqsimot",
                       reply_markup=get_main_markup())
    else:
        bot.send_message(chat_id, "📭 Ma'lumot yo'q.", reply_markup=get_main_markup())

def _send_added(chat_id, msg_id, uid, results):
    added_total = sum(a for a, _, _ in results)
    lines = []
    for a, p, code in results:
        icon, _ = get_category(p)
        code_str = f" 🆔{code}" if code else ""
        lines.append(f"  • {icon} {clean_name(p)}{code_str} — {format_amount(a)} so'm")
    bot.edit_message_text(
        f"✅ <b>{len(results)} ta mahsulot topildi!</b>\n"
        f"💰 Shu chekdan: <b>{format_amount(added_total)} so'm</b>\n\n"
        + "\n".join(lines)
        + "\n\n" + build_full_list(uid),
        chat_id, msg_id,
        parse_mode="HTML", reply_markup=get_main_markup(),
    )

# ── HANDLERLAR ─────────────────────────────────────────
@bot.message_handler(commands=["start", "hello"])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        f"Salom, {clean_name(message.from_user.first_name)}! 👋\n\n"
        "💰 <b>Harajat botiga xush kelibsiz! (versiya 2.0 – mahsulot kodlari bilan)</b>\n\n"
        "📌 <b>Qanday foydalanish:</b>\n"
        "• 📄 PDF chek yuboring — avtomatik o'qiladi\n"
        "• 🖼️ PNG/JPG chek rasmi yuboring — OCR o'qiydi\n"
        "• ✍️ Matn: <code>olma 15000</code> yoki <code>15000 non</code>\n"
        "• 📋 Ko'p mahsulot: har birini yangi qatorga\n\n"
        "📊 Statistika, grafik va kategoriyalar:",
        reply_markup=get_main_markup(), parse_mode="HTML",
    )

@bot.message_handler(commands=["help"])
def send_help(message):
    bot.send_message(
        message.chat.id,
        "📖 <b>Yordam</b>\n\n"
        "📄 <b>PDF chek</b> — hujjat sifatida yuboring\n"
        "🖼️ <b>PNG/JPG</b> — rasm sifatida yuboring\n\n"
        "<code>olma 15000</code> — mahsulot + narx\n"
        "<code>non 5000\nkola 8000</code> — ko'p qator\n\n"
        "/stats — statistika\n"
        "/chart — grafik\n"
        "/cats — kategoriyalar\n"
        "/clear — hammasini o'chirish",
        parse_mode="HTML",
    )

@bot.message_handler(commands=["stats"])
def stats_cmd(message):
    _send_stats(message.chat.id, message.from_user.id)

@bot.message_handler(commands=["chart"])
def chart_cmd(message):
    _send_chart(message.chat.id, message.from_user.id, "month")

@bot.message_handler(commands=["cats"])
def cats_cmd(message):
    _send_cat_chart(message.chat.id, message.from_user.id)

@bot.message_handler(commands=["clear"])
def clear_cmd(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ha",   callback_data="confirm_clear"),
        types.InlineKeyboardButton("❌ Yo'q", callback_data="cancel_clear"),
    )
    bot.send_message(message.chat.id, "⚠️ Barcha harajatlarni o'chirish?", reply_markup=markup)

# ── CALLBACK ───────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)

    if call.data in ("week", "month", "all"):
        days  = {"week": 7, "month": 30, "all": None}[call.data]
        label = {"week": "📅 Haftalik", "month": "🗓️ Oylik", "all": "📊 Barcha"}[call.data]
        data  = get_by_period(uid, days)
        if data:
            lines = []
            for i, (a, p, _, code) in enumerate(data, 1):
                icon, _ = get_category(p)
                code_str = f" 🆔{code}" if code else ""
                lines.append(f"{i}. {icon} {clean_name(p)}{code_str} — {format_amount(a)} so'm")
            total = sum(r[0] for r in data)
            bot.send_message(
                call.message.chat.id,
                f"{label} harajatlar ({len(data)} ta):\n\n" + "\n".join(lines)
                + f"\n\n💰 <b>Jami: {format_amount(total)} so'm</b>",
                parse_mode="HTML", reply_markup=get_main_markup(),
            )
        else:
            bot.send_message(call.message.chat.id, "📭 Bu davrda harajat yo'q.")

    elif call.data == "stats":
        _send_stats(call.message.chat.id, uid)

    elif call.data == "chart":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📅 7 kunlik",  callback_data="chart_week"),
            types.InlineKeyboardButton("🗓️ 30 kunlik", callback_data="chart_month"),
        )
        bot.send_message(call.message.chat.id, "📈 Qaysi davr?", reply_markup=markup)

    elif call.data == "chart_week":
        _send_chart(call.message.chat.id, uid, "week")

    elif call.data == "chart_month":
        _send_chart(call.message.chat.id, uid, "month")

    elif call.data == "cats":
        _send_cat_chart(call.message.chat.id, uid)

    elif call.data == "clear":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Ha",   callback_data="confirm_clear"),
            types.InlineKeyboardButton("❌ Yo'q", callback_data="cancel_clear"),
        )
        bot.send_message(call.message.chat.id, "⚠️ O'chirishni tasdiqlaysizmi?", reply_markup=markup)

    elif call.data == "confirm_clear":
        count = len(get_user_expenses(uid))
        clear_user_expenses(uid)
        bot.send_message(call.message.chat.id, f"🗑️ {count} ta harajat o'chirildi.")

    elif call.data == "cancel_clear":
        bot.send_message(call.message.chat.id, "✅ Bekor qilindi.")

# ── RASM (photo) HANDLERI ──────────────────────────────
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    uid = message.from_user.id
    msg = bot.reply_to(message, "🔍 Rasm o'qilmoqda...")
    path = "check_photo.jpg"
    try:
        fi   = bot.get_file(message.photo[-1].file_id)
        data = bot.download_file(fi.file_path)
        with open(path, "wb") as f:
            f.write(data)

        results = process_png(path)

        if results:
            add_user_expenses(uid, results)  # results: [(amount, product, code), ...]
            _send_added(message.chat.id, msg.message_id, uid, results)
        else:
            bot.edit_message_text(
                "❌ <b>Chekdan mahsulot topib bo'lmadi.</b>\n\n"
                "💡 Maslahat:\n"
                "• Rasmni to'g'ridan-to'g'ri (egiltirmasdan) oling\n"
                "• Yaxshi yoritilgan bo'lsin\n"
                "• Yoki PDF formatda yuboring\n"
                "• Qo'lda yozing: <code>olma 15000</code>",
                message.chat.id, msg.message_id, parse_mode="HTML",
            )
    except Exception as e:
        bot.edit_message_text(f"⚠️ Xatolik: {e}", message.chat.id, msg.message_id)
    finally:
        if os.path.exists(path):
            os.remove(path)

# ── HUJJAT (document) HANDLERI ─────────────────────────
@bot.message_handler(content_types=["document"])
def handle_document(message):
    uid       = message.from_user.id
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
        bot.reply_to(
            message,
            "❌ Format qo'llab-quvvatlanmaydi.\n"
            "✅ Qabul qilinadigan: <b>PDF, PNG, JPG, WebP, BMP</b>",
            parse_mode="HTML",
        )
        return

    kind = "PDF" if is_pdf else "PNG/JPG rasm"
    msg  = bot.reply_to(message, f"🔍 {kind} o'qilmoqda...")
    path = f"tmp_doc_{doc.file_id}{ext}"

    try:
        fi   = bot.get_file(doc.file_id)
        data = bot.download_file(fi.file_path)
        with open(path, "wb") as f:
            f.write(data)

        if is_pdf:
            results = process_pdf(path)
        else:
            results = process_png(path)

        if results:
            add_user_expenses(uid, results)
            _send_added(message.chat.id, msg.message_id, uid, results)
        else:
            bot.edit_message_text(
                f"❌ <b>{kind} dan mahsulot topib bo'lmadi.</b>\n\n"
                "💡 Maslahat:\n"
                "• PDF matnli (skanerlangan emas) bo'lsin\n"
                "• Rasm aniq va yaxshi yoritilgan bo'lsin\n"
                "• Korzinka ilovasidan PDF yuklab yuboring",
                message.chat.id, msg.message_id, parse_mode="HTML",
            )
    except Exception as e:
        bot.edit_message_text(f"⚠️ Xatolik: {e}", message.chat.id, msg.message_id)
    finally:
        if os.path.exists(path):
            os.remove(path)

# ── MATN HANDLERI ──────────────────────────────────────
@bot.message_handler(func=lambda m: True)
def add_expense(message):
    uid   = message.from_user.id
    text  = message.text.strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if len(lines) > 1:
        results = parse_simple_text(text)  # kod qidirmaydi
        if results:
            add_user_expenses(uid, results)
            added_total = sum(a for a, _, _ in results)
            bot.reply_to(
                message,
                f"✅ <b>{len(results)} ta harajat qo'shildi!</b>\n"
                f"💰 Shu safar: <b>{format_amount(added_total)} so'm</b>\n\n"
                + build_full_list(uid),
                parse_mode="HTML", reply_markup=get_main_markup(),
            )
            return

    nums = re.findall(r"\d+", text)
    if not nums:
        bot.reply_to(
            message,
            "ℹ️ Raqam topilmadi.\n"
            "Masalan: <code>olma 15000</code>\n"
            "Yoki PDF/PNG chek yuboring.",
            parse_mode="HTML",
        )
        return

    amount  = int(nums[0])
    product = re.sub(r"\s+", " ", re.sub(r"\d+", "", text)).strip() or "Noma'lum"
    add_user_expenses(uid, [(amount, product, None)])
    icon, _ = get_category(product)

    bot.reply_to(
        message,
        f"✅ {icon} <b>{clean_name(product)}</b> — {format_amount(amount)} so'm qo'shildi!\n\n"
        + build_full_list(uid),
        parse_mode="HTML", reply_markup=get_main_markup(),
    )

# ── ISHGA TUSHIRISH ────────────────────────────────────
print("Bot ishga tushdi ✅ (versiya 2.0 – mahsulot kodlari bilan)")
bot.polling(none_stop=True, interval=0)