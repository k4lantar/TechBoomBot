import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import sqlite3
from uuid import uuid4

# تنظیمات لاگ برای دیباگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# تنظیمات دیتابیس
def init_db():
    try:
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                     user_id INTEGER PRIMARY KEY,
                     username TEXT,
                     is_admin INTEGER DEFAULT 0,
                     is_blocked INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS products (
                     product_id TEXT PRIMARY KEY,
                     name TEXT,
                     price REAL)''')
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    finally:
        conn.close()

# حالت‌های مکالمه
PRODUCTS, ADMIN_PANEL, CHANGE_PRICE, ADD_PRODUCT, BLOCK_USER = range(5)

# لیست ادمین‌ها
ADMIN_IDS = [212874423]  # آیدی تلگرام شما

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id):
        await update.message.reply_text("شما بلاک شدید! با پشتیبانی تماس بگیرید.")
        return ConversationHandler.END

    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)",
                  (user_id, update.effective_user.username or "Unknown"))
        conn.commit()
    conn.close()

    # منوی اصلی با محصولات
    keyboard = [
        [InlineKeyboardButton("📦 مشاهده محصولات", callback_data="show_products")],
        [InlineKeyboardButton("🛠 پنل ادمین", callback_data="admin_panel")]
        if user_id in ADMIN_IDS
        else []
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "خوش اومدی به ربات ما! 😎\nبرای شروع یکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=reply_markup
    )
    return PRODUCTS

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT name, price FROM products")
    products = c.fetchall()
    conn.close()

    if not products:
        await query.message.reply_text("هیچ محصولی موجود نیست! 😔")
        return PRODUCTS

    keyboard = [
        [InlineKeyboardButton(f"{name} - {price:,} تومان", callback_data=f"product_{name}")]
        for name, price in products
    ]
    keyboard.append([InlineKeyboardButton("↩️ بازگشت", callback_data="start")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("📦 محصولات ما:", reply_markup=reply_markup)
    return PRODUCTS

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    if user_id not in ADMIN_IDS:
        await query.message.reply_text("شما ادمین نیستید! 😡")
        return PRODUCTS

    keyboard = [
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="manage_users")],
        [InlineKeyboardButton("💰 تغییر قیمت محصولات", callback_data="change_price")],
        [InlineKeyboardButton("➕ اضافه کردن محصول", callback_data="add_product")],
        [InlineKeyboardButton("🚫 بلاک/آنبلاک کاربر", callback_data="block_user")],
        [InlineKeyboardButton("↩️ بازگشت", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("🛠 پنل ادمین:", reply_markup=reply_markup)
    return ADMIN_PANEL

async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username, is_blocked FROM users")
    users = c.fetchall()
    conn.close()

    message = "👥 لیست کاربران:\n"
    for user_id, username, is_blocked in users:
        status = "بلاک شده 🚫" if is_blocked else "فعال ✅"
        message += f"آیدی: {user_id} - نام: {username} - وضعیت: {status}\n"
    keyboard = [[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(message, reply_markup=reply_markup)
    return ADMIN_PANEL

async def change_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT name FROM products")
    products = c.fetchall()
    conn.close()

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"price_{name}")]
        for name, in products
    ]
    keyboard.append([InlineKeyboardButton("↩️ بازگشت", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("💰 کدام محصول؟", reply_markup=reply_markup)
    return CHANGE_PRICE

async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_name = query.data.replace("price_", "")
    context.user_data["selected_product"] = product_name
    await query.message.reply_text(f"💵 قیمت جدید برای {product_name} (به تومان):")
    return CHANGE_PRICE

async def update_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = update.message.text
    try:
        price = float(price)
        product_name = context.user_data["selected_product"]
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("UPDATE products SET price=? WHERE name=?", (price, product_name))
        conn.commit()
        conn.close()
        await update.message.reply_text f"✅ قیمت {product_name} به {price:,} تومان تغییر کرد!")
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
    return ADMIN_PANEL

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🚫 آیدی کاربر برای بلاک/آنبلاک:")
    return BLOCK_USER

async def do_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text
    try:
        user_id = int(user_id)
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id=?", (user_id,))
        user = c.fetchone()
        if user:
            new_status = 0 if user[0] else 1
            c.execute("UPDATE users SET is_blocked=? WHERE user_id=?", (new_status, user_id))
            conn.commit()
            status = "بلاک شد 🚫" if new_status else "آنبلاک شد ✅"
            await update.message.reply_text(f"✅ کاربر {user_id} {status}!")
        else:
            await update.message.reply_text("❌ کاربر یافت نشد!")
        conn.close()
    except ValueError:
        await update.message.reply_text("❌ آیدی معتبر وارد کنید!")
    return ADMIN_PANEL

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("➕ نام محصول جدید:")
    return ADD_PRODUCT

async def do_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_name = update.message.text
    context.user_data["new_product_name"] = product_name
    await update.message.reply_text(f"💵 قیمت برای {product_name} (به تومان):")
    return ADD_PRODUCT

async def do_add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = update.message.text
    try:
        price = float(price)
        product_name = context.user_data["new_product_name"]
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("INSERT INTO products (product_id, name, price) VALUES (?, ?, ?)",
                  (str(uuid4()), product_name, price))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ محصول {product_name} با قیمت {price:,} تومان اضافه شد!")
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
    return ADMIN_PANEL

async def restart_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("شما ادمین نیستید! 😡")
        return ConversationHandler.END

    try:
        os.remove("bot.db")
        init_db()
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO products (product_id, name, price) VALUES (?, ?, ?)",
                  (str(uuid4()), "محصول ۱", 10000))
        c.execute("INSERT OR IGNORE INTO products (product_id, name, price) VALUES (?, ?, ?)",
                  (str(uuid4()), "محصول ۲", 20000))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ دیتابیس با موفقیت ریست شد و محصولات نمونه اضافه شدند!")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ریست دیتابیس: {e}")
    return ConversationHandler.END

def is_blocked(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT is_blocked FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user and user[0] == 1

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "show_products":
        return await show_products(update, context)
    elif data == "admin_panel":
        return await admin_panel(update, context)
    elif data == "manage_users":
        return await manage_users(update, context)
    elif data == "change_price":
        return await change_price(update, context)
    elif data == "add_product":
        return await add_product(update, context)
    elif data == "block_user":
        return await block_user(update, context)
    elif data.startswith("price_"):
        return await set_price(update, context)
    elif data == "start":
        return await start(update, context)

def main():
    init_db()
    # افزودن محصولات نمونه
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO products (product_id, name, price) VALUES (?, ?, ?)",
              (str(uuid4()), "محصول ۱", 10000))
    c.execute("INSERT OR IGNORE INTO products (product_id, name, price) VALUES (?, ?, ?)",
              (str(uuid4()), "محصول ۲", 20000))
    conn.commit()
    conn.close()

    # تنظیمات ربات
    try:
        application = Application.builder().token(os.environ["BOT_TOKEN"]).build()
    except KeyError:
        logger.error("BOT_TOKEN not found in environment variables")
        raise

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PRODUCTS: [CallbackQueryHandler(button)],
            ADMIN_PANEL: [CallbackQueryHandler(button)],
            CHANGE_PRICE: [
                CallbackQueryHandler(button),
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_price)
            ],
            ADD_PRODUCT: [
                CallbackQueryHandler(button),
                MessageHandler(filters.TEXT & ~filters.COMMAND, do_add_product),
                MessageHandler(filters.TEXT & ~filters.COMMAND, do_add_product_price)
            ],
            BLOCK_USER: [
                CallbackQueryHandler(button),
                MessageHandler(filters.TEXT & ~filters.COMMAND, do_block_user)
            ]
        },
        fallbacks=[CommandHandler("restart", restart_db)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("restart", restart_db))
    application.run_polling()

if __name__ == "__main__":
    main()