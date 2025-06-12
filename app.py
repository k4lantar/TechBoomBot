import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import sqlite3
from flask import Flask, request, jsonify
import os
import uuid
import time
from datetime import datetime
import hashlib
import json
import asyncio
import logging

# تنظیمات لگاری
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# تنظیمات ربات
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8030727817:AAEdnqRvVDUlOrrOrh7eTQdt2M_6AD0yC50")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://techboom-bot.onrender.com/webhook")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "212874423"))
app = Flask(__name__)
telegram_app = None

# SQLite database setup
def init_db():
    with sqlite3.connect("shop.db") as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, phone TEXT, balance INTEGER DEFAULT 0, referrer_id INTEGER, invite_code TEXT, joined_at TEXT, is_blocked INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS apple_ids (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, password TEXT, questions TEXT, region TEXT, status TEXT, user_id INTEGER, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS gift_cards (id INTEGER PRIMARY KEY AUTOINCREMENT, amount INTEGER, code TEXT, status TEXT, user_id INTEGER, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS vpn_accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, config TEXT, protocol TEXT, volume TEXT, duration INTEGER, status TEXT, user_id INTEGER, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS virtual_numbers (id INTEGER PRIMARY KEY AUTOINCREMENT, number TEXT, country TEXT, status TEXT, user_id INTEGER, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, user_id INTEGER, amount INTEGER, type TEXT, status TEXT, receipt_url TEXT, purchase_data TEXT, created_at TEXT, admin_confirmed INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT, status TEXT, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
        default_settings = [
            ("welcome_message", "🌍 به TechBoomBot خوش اومدی! 😎\n📲 شماره‌ات رو به اشتراک بذار."),
            ("contact_saved_message", "✅ شماره‌ات ثبت شد! از منو استفاده کن."),
            ("insufficient_balance_message", "❌ موجودی کافی نیست! {amount:,} تومان واریز کن."),
            ("menu_enabled", "1"),
            ("admin_commands_enabled", "1"),
            ("apple_id_prices", json.dumps({
                "US": {1: 100000, 5: 450000, 10: 800000},
                "UK": {1: 105000, 5: 470000, 10: 850000},
                "TR": {1: 120000, 5: 550000, 10: 950000},
                "AE": {1: 110000, 5: 500000, 10: 900000},
                "CA": {1: 115000, 5: 520000, 10: 920000}
            })),
            ("vpn_prices", json.dumps({
                "V2Ray": {"10GB": {1: 50000, 3: 140000}, "50GB": {1: 80000, 3: 220000}, "Unlimited": {1: 120000, 3: 340000}},
                "Cisco": {"10GB": {1: 55000, 3: 150000}, "50GB": {1: 85000, 3: 230000}, "Unlimited": {1: 130000, 3: 360000}},
                "OpenVPN": {"10GB": {1: 45000, 3: 130000}, "50GB": {1: 75000, 3: 210000}, "Unlimited": {1: 110000, 3: 320000}}
            })),
            ("gift_card_prices", json.dumps({20000: 20000, 30000: 30000, 50000: 50000, 100000: 100000, 200000: 200000})),
            ("virtual_number_prices", json.dumps({"US": 5000, "UK": 6000, "TR": 7000, "AE": 6500}))
        ]
        c.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", default_settings)
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
        conn.commit()

# Get setting
def get_setting(key, default=None):
    with sqlite3.connect("shop.db") as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = c.fetchone()
        return json.loads(result[0]) if result and key in ["apple_id_prices", "gift_card_prices", "vpn_prices", "virtual_number_prices"] else result[0] if result else default

# Show intro
async def show_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("menu_enabled") == "0":
        await update.message.reply_text("منو موقتاً غیرفعاله!")
        return
    keyboard = [[KeyboardButton("📲 اشتراک شماره", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(get_setting("welcome_message"), reply_markup=reply_markup)

# Show main menu
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("menu_enabled") == "0":
        await update.message.reply_text("منو موقتاً غیرفعاله!")
        return
    keyboard = [
        [KeyboardButton("💳 کیف پول"), KeyboardButton("📚 راهنمایی")],
        [KeyboardButton("📞 پشتیبانی"), KeyboardButton("👤 سرویس‌های من")],
        [KeyboardButton("🎉 تست رایگان"), KeyboardButton("🌐 VPN")],
        [KeyboardButton("🎁 گیفت کارت"), KeyboardButton("📱 شماره مجازی")],
        [KeyboardButton("🍎 اپل آیدی")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🔥 TechBoomBot! 🚀\nانتخاب کن:", reply_markup=reply_markup)

# Handle contact
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    phone = update.message.contact.phone_number
    with sqlite3.connect("shop.db") as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, phone, joined_at) VALUES (?, ?, ?)",
                  (user_id, phone, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    await update.message.reply_text(get_setting("contact_saved_message"))
    await show_main_menu(update, context)

# Handle text input
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    if not text:
        return
    with sqlite3.connect("shop.db") as conn:
        c = conn.cursor()
        c.execute("SELECT phone FROM users WHERE user_id = ?", (user_id,))
        phone = c.fetchone()
        if not phone:
            await show_intro(update, context)
        else:
            if text == "/start":
                await show_main_menu(update, context)
            elif text in ["💳 کیف پول", "📚 راهنمایی", "📞 پشتیبانی", "👤 سرویس‌های من", "🎉 تست رایگان", "🌐 VPN", "🎁 گیفت کارت", "📱 شماره مجازی", "🍎 اپل آیدی"]:
                await handle_category(update, context, text)
            elif text == "/admin" and str(user_id) == str(ADMIN_ID) and get_setting("admin_commands_enabled") == "1":
                await show_admin_menu(update, context)

# Handle category
async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.message.from_user.id
    with sqlite3.connect("shop.db") as conn:
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        balance = result[0] if result else 0
    if text == "💳 کیف پول":
        await update.message.reply_text(f"موجودی شما: {balance:,} تومان")
    elif text == "📚 راهنمایی":
        await update.message.reply_text("برای راهنمایی، به پشتیبانی پیام بده!")
    elif text == "📞 پشتیبانی":
        await update.message.reply_text("پیام خود را ارسال کنید.")
    elif text == "👤 سرویس‌های من":
        await update.message.reply_text("سرویس‌های فعال شما اینجا نمایش داده می‌شود.")
    elif text == "🎉 تست رایگان":
        await update.message.reply_text("تست رایگان VPN 1 روزه فعال شد!")
    elif text == "🌐 VPN":
        keyboard = [
            [InlineKeyboardButton("V2Ray", callback_data="vpn_v2ray")],
            [InlineKeyboardButton("Cisco", callback_data="vpn_cisco")],
            [InlineKeyboardButton("OpenVPN", callback_data="vpn_openvpn")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("VPN رو انتخاب کن:", reply_markup=reply_markup)
    elif text == "🎁 گیفت کارت":
        prices = get_setting("gift_card_prices")
        keyboard = [[InlineKeyboardButton(f"{int(k):,} تومان", callback_data=f"gift_{k}")] for k in prices.keys()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("گیفت کارت رو انتخاب کن:", reply_markup=reply_markup)
    elif text == "📱 شماره مجازی":
        prices = get_setting("virtual_number_prices")
        keyboard = [[InlineKeyboardButton(f"{v:,} تومان - {k}", callback_data=f"virtual_{k}")] for k, v in prices.items()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("شماره مجازی رو انتخاب کن:", reply_markup=reply_markup)
    elif text == "🍎 اپل آیدی":
        regions = get_setting("apple_id_prices").keys()
        keyboard = [[InlineKeyboardButton(f"{r}", callback_data=f"apple_{r}")] for r in regions]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("ریجن اپل آیدی رو انتخاب کن:", reply_markup=reply_markup)

# Handle category callback
async def handle_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    with sqlite3.connect("shop.db") as conn:
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = c.fetchone()[0] if c.fetchone() else 0
        if data.startswith("vpn_"):
            protocol = data.replace("vpn_", "")
            prices = get_setting("vpn_prices")[protocol]
            keyboard = [[InlineKeyboardButton(f"{k}GB - {v[1]:,}", callback_data=f"vpn_{protocol}_{k}_1"),
                        InlineKeyboardButton(f"{k}GB - {v[3]:,}", callback_data=f"vpn_{protocol}_{k}_3")] for k, v in prices.items()]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(f"VPN {protocol} - 1 ماهه/3 ماهه:", reply_markup=reply_markup)
        elif data.startswith("apple_"):
            region = data.replace("apple_", "")
            prices = get_setting("apple_id_prices")[region]
            keyboard = [[InlineKeyboardButton(f"{k} تا - {v:,}", callback_data=f"apple_{region}_{k}")] for k, v in prices.items()]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(f"اپل آیدی {region}:", reply_markup=reply_markup)
        elif data.startswith("gift_"):
            amount = int(data.replace("gift_", ""))
            if balance >= amount:
                c.execute("INSERT INTO gift_cards (amount, code, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                          (amount, hashlib.md5(f"{uuid.uuid4()}".encode()).hexdigest()[:10], "active", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
                conn.commit()
                await query.message.reply_text(f"گیفت کارت {amount:,} تومانی فعال شد!")
            else:
                await query.message.reply_text(get_setting("insufficient_balance_message").format(amount=amount))
        elif data.startswith("virtual_"):
            country = data.replace("virtual_", "")
            price = get_setting("virtual_number_prices")[country]
            if balance >= price:
                c.execute("INSERT INTO virtual_numbers (number, country, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                          (f"+{country}123456789", country, "active", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
                conn.commit()
                await query.message.reply_text(f"شماره مجازی {country} فعال شد!")
            else:
                await query.message.reply_text(get_setting("insufficient_balance_message").format(amount=price))

# Admin menu
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("admin_commands_enabled") == "0":
        await update.message.reply_text("پنل ادمین غیرفعاله!")
        return
    keyboard = [
        [InlineKeyboardButton("پیام همگانی", callback_data="broadcast")],
        [InlineKeyboardButton("افزودن همکار", callback_data="add_admin")],
        [InlineKeyboardButton("جستجوی سرویس", callback_data="search_service")],
        [InlineKeyboardButton("افزایش موجودی", callback_data="add_balance")],
        [InlineKeyboardButton("تأیید پرداخت‌ها", callback_data="confirm_payments")],
        [InlineKeyboardButton("آمار ربات", callback_data="bot_stats")],
        [InlineKeyboardButton("آمار کاربران", callback_data="user_stats")],
        [InlineKeyboardButton("منفی/مثبت موجودی", callback_data="adjust_balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📊 پنل ادمین:", reply_markup=reply_markup)

# Handle admin callback
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if str(user_id) != str(os.getenv("ADMIN_ID")):
        await query.message.reply_text("فقط ادمین اصلی!")
        return
    data = query.data
    with sqlite3.connect("shop.db") as conn:
        c = conn.cursor()
        if data == "broadcast":
            await query.message.reply_text("متن پیام رو ارسال کنید برای برادکست.")
            context.user_data["mode"] = "broadcast"
        elif data == "add_admin":
            await query.message.reply_text("ID ادمین جدید رو ارسال کنید.")
            context.user_data["mode"] = "add_admin"
        elif data == "search_service":
            await query.message.reply_text("جستجوی سرویس فعال شد!")
        elif data == "add_balance":
            await query.message.reply_text("ID کاربر و مقدار رو ارسال کنید (مثال: 123 5000).")
            context.user_data["mode"] = "add_balance"
        elif data == "confirm_payments":
            await query.message.reply_text("لیست پرداخت‌های در انتظار:")
            c.execute("SELECT * FROM payments WHERE status = 'pending'")
            payments = c.fetchall()
            if payments:
                response = "\n".join([f"ID: {p[0]}, User: {p[1]}, Amount: {p[2]}" for p in payments])
                await query.message.reply_text(response)
            else:
                await query.message.reply_text("هیچ پرداختی در انتظار نیست.")
        elif data == "bot_stats":
            c.execute("SELECT COUNT(*) FROM users")
            user_count = c.fetchone()[0]
            await query.message.reply_text(f"تعداد کاربران: {user_count}")
        elif data == "user_stats":
            await query.message.reply_text("ID کاربر رو ارسال کنید برای آمار.")
            context.user_data["mode"] = "user_stats"
        elif data == "adjust_balance":
            await query.message.reply_text("ID کاربر و مقدار جدید رو ارسال کنید (مثال: 123 10000).")
            context.user_data["mode"] = "adjust_balance"

# Handle payment confirmation
async def handle_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if str(user_id) != str(ADMIN_ID):
        await query.message.reply_text("فقط ادمین!")
        return
    data = query.data.replace("confirm_", "")
    with sqlite3.connect("shop.db") as conn:
        c = conn.cursor()
        c.execute("UPDATE transactions SET admin_confirmed = 1, status = 'confirmed' WHERE id = ?", (data,))
        c.execute("SELECT user_id, amount FROM transactions WHERE id = ?", (data,))
        user_id, amount = c.fetchone()
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
    await query.message.reply_text(f"تراکنش {data} تأیید شد!")

# Flask webhook endpoint
@app.route('/webhook', methods=['POST'])
async def webhook():
    global telegram_app
    logger.info("Webhook received: %s", request.get_json())
    if telegram_app is None:
        logger.info("Initializing telegram_app...")
        await initialize_app()
    if telegram_app is None:
        logger.error("Failed to initialize telegram_app")
        return "Bot initialization failed", 500
    update = telegram.Update.de_json(request.get_json(), telegram_app.bot)
    logger.info("Processing update: %s", update)
    try:
        await telegram_app.process_update(update)
    except Exception as e:
        logger.error("Error in webhook: %s", str(e))
        return "Internal Server Error", 500
    return 'OK', 200

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

# Initialize application
async def initialize_app():
    global telegram_app
    try:
        init_db()
        telegram_app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
        await telegram_app.initialize()
        telegram_app.add_handler(CommandHandler("start", show_intro))
        telegram_app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        telegram_app.add_handler(CallbackQueryHandler(handle_category_callback))
        telegram_app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^broadcast|add_admin|search_service|add_balance|confirm_payments|bot_stats|user_stats|adjust_balance$"))
        telegram_app.add_handler(CallbackQueryHandler(handle_payment_callback, pattern="^confirm_"))
        telegram_app.add_error_handler(error_handler)  # استفاده از تابع Error Handler
        logger.info("Setting webhook: %s", os.getenv("WEBHOOK_URL"))
        await telegram_app.bot.set_webhook(url=os.getenv("WEBHOOK_URL"))
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error("Error in initialize_app: %s", str(e))
        telegram_app = None

# Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)

# Main function to run the app
def run_app():
    loop = asyncio.new_event_loop()  # ایجاد Event Loop جدید
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(initialize_app())
        from hypercorn.config import Config
        from hypercorn.asyncio import serve
        config = Config()
        port = int(os.environ.get("PORT", 5000))
        config.bind = [f"0.0.0.0:{port}"]
        loop.run_until_complete(serve(app, config))
    except Exception as e:
        logger.error("Error in run_app: %s", str(e))
    finally:
        loop.close()

if __name__ == "__main__":
    run_app()