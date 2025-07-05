import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)
import sqlite3
from flask import Flask, request, jsonify
import uuid
import time
from datetime import datetime
import hashlib
import json
import asyncio

# تنظیمات لگاری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# تنظیمات ربات
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8030727817:AAEdnqRvVDUlOrrOrh7eTQdt2M_6AD0yC50")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://techboom-bot.onrender.com/webhook")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "212874423"))
app = Flask(__name__)
telegram_app = None
loop = None

# تنظیمات دیتابیس
def init_db():
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                         user_id INTEGER PRIMARY KEY,
                         phone TEXT,
                         balance INTEGER DEFAULT 0,
                         referrer_id INTEGER,
                         invite_code TEXT,
                         joined_at TEXT,
                         is_blocked INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS apple_ids (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         email TEXT,
                         password TEXT,
                         questions TEXT,
                         region TEXT,
                         status TEXT,
                         user_id INTEGER,
                         created_at TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS gift_cards (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         amount INTEGER,
                         code TEXT,
                         status TEXT,
                         user_id INTEGER,
                         created_at TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS vpn_accounts (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         config TEXT,
                         protocol TEXT,
                         volume TEXT,
                         duration INTEGER,
                         status TEXT,
                         user_id INTEGER,
                         created_at TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS virtual_numbers (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         number TEXT,
                         country TEXT,
                         status TEXT,
                         user_id INTEGER,
                         created_at TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                         id TEXT PRIMARY KEY,
                         user_id INTEGER,
                         amount INTEGER,
                         type TEXT,
                         status TEXT,
                         receipt_url TEXT,
                         purchase_data TEXT,
                         created_at TEXT,
                         admin_confirmed INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS tickets (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER,
                         message TEXT,
                         status TEXT,
                         created_at TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS settings (
                         key TEXT PRIMARY KEY,
                         value TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS admins (
                         user_id INTEGER PRIMARY KEY)''')
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
            # اضافه کردن محصولات نمونه
            c.execute("INSERT OR IGNORE INTO gift_cards (amount, code, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                      (50000, "SAMPLE-GIFT-001", "active", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("INSERT OR IGNORE INTO gift_cards (amount, code, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                      (100000, "SAMPLE-GIFT-002", "active", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("INSERT OR IGNORE INTO apple_ids (email, password, questions, region, status, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      ("sample1@apple.com", "pass123", "Q1:Ans1", "US", "active", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("INSERT OR IGNORE INTO apple_ids (email, password, questions, region, status, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      ("sample2@apple.com", "pass456", "Q2:Ans2", "UK", "active", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("INSERT OR IGNORE INTO vpn_accounts (config, protocol, volume, duration, status, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      ("sample_config_v2ray", "V2Ray", "10GB", 1, "active", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("INSERT OR IGNORE INTO vpn_accounts (config, protocol, volume, duration, status, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      ("sample_config_openvpn", "OpenVPN", "50GB", 3, "active", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("INSERT OR IGNORE INTO virtual_numbers (number, country, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                      ("+123456789", "US", "active", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("INSERT OR IGNORE INTO virtual_numbers (number, country, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                      ("+987654321", "UK", "active", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

# دریافت تنظیمات
def get_setting(key, default=None):
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = ?", (key,))
            result = c.fetchone()
            if result:
                if key in ["apple_id_prices", "gift_card_prices", "vpn_prices", "virtual_number_prices"]:
                    return json.loads(result[0])
                return result[0]
            return default
    except Exception as e:
        logger.error(f"Error getting setting {key}: {e}")
        return default

# نمایش منوی اولیه
async def show_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("menu_enabled") == "0":
        await update.message.reply_text("منو موقتاً غیرفعاله!")
        return
    keyboard = [[KeyboardButton("📲 اشتراک شماره", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(get_setting("welcome_message"), reply_markup=reply_markup)

# نمایش منوی اصلی
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

# مدیریت تماس
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    phone = update.message.contact.phone_number
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO users (user_id, phone, joined_at) VALUES (?, ?, ?)",
                      (user_id, phone, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        await update.message.reply_text(get_setting("contact_saved_message"))
        await show_main_menu(update, context)
    except Exception as e:
        logger.error(f"Error handling contact for user {user_id}: {e}")
        await update.message.reply_text("❌ خطایی رخ داد. دوباره امتحان کن!")

# مدیریت ورودی متن
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    logger.info(f"Received text from user {user_id}: {text}")
    if not text:
        return
    try:
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
                elif text == "/admin" and user_id == ADMIN_ID and get_setting("admin_commands_enabled") == "1":
                    await show_admin_menu(update, context)
                elif text == "/restart" and user_id == ADMIN_ID:
                    await restart_db(update, context)
                elif text == "/checkdb" and user_id == ADMIN_ID:
                    await check_db(update, context)
                elif text == "/showall" and user_id == ADMIN_ID:
                    await show_all_services(update, context)
                elif text == "/resetuser" and user_id == ADMIN_ID:
                    await reset_user(update, context)
                elif context.user_data.get("mode"):
                    await handle_admin_input(update, context)
    except Exception as e:
        logger.error(f"Error handling text for user {user_id}: {e}")
        await update.message.reply_text("❌ خطایی رخ داد. دوباره امتحان کن!")

# مدیریت دسته‌بندی‌ها
async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.message.from_user.id
    logger.info(f"Handling category {text} for user {user_id}")
    try:
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
            await update.message.reply_text("پیام خود را برای پشتیبانی ارسال کنید.")
            context.user_data["mode"] = "support"
        elif text == "👤 سرویس‌های من":
            await show_user_services(update, context)
        elif text == "🎉 تست رایگان":
            await update.message.reply_text("✅ تست رایگان VPN 1 روزه فعال شد!")
        elif text == "🌐 VPN":
            keyboard = [
                [InlineKeyboardButton("V2Ray", callback_data="vpn_v2ray")],
                [InlineKeyboardButton("Cisco", callback_data="vpn_cisco")],
                [InlineKeyboardButton("OpenVPN", callback_data="vpn_openvpn")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🌐 VPN رو انتخاب کن:", reply_markup=reply_markup)
        elif text == "🎁 گیفت کارت":
            prices = get_setting("gift_card_prices")
            keyboard = [[InlineKeyboardButton(f"{int(k):,} تومان", callback_data=f"gift_{k}")] for k in prices.keys()]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🎁 گیفت کارت رو انتخاب کن:", reply_markup=reply_markup)
        elif text == "📱 شماره مجازی":
            prices = get_setting("virtual_number_prices")
            keyboard = [[InlineKeyboardButton(f"{k} - {v:,} تومان", callback_data=f"virtual_{k}")] for k, v in prices.items()]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📱 شماره مجازی رو انتخاب کن:", reply_markup=reply_markup)
        elif text == "🍎 اپل آیدی":
            regions = get_setting("apple_id_prices").keys()
            keyboard = [[InlineKeyboardButton(f"{r}", callback_data=f"apple_{r}")] for r in regions]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🍎 ریجن اپل آیدی رو انتخاب کن:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in handle_category for user {user_id}: {e}")
        await update.message.reply_text("❌ خطایی رخ داد. دوباره امتحان کن!")

# نمایش سرویس‌های کاربر
async def show_user_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            message = "👤 سرویس‌های شما:\n\n"
            # اپل آیدی
            c.execute("SELECT id, email, region, status, created_at FROM apple_ids WHERE (user_id = ? OR user_id IS NULL) AND status = 'active'", (user_id,))
            apple_ids = c.fetchall()
            if apple_ids:
                message += "🍎 اپل آیدی‌ها:\n"
                for apple_id in apple_ids:
                    message += f"ID: {apple_id[0]} - ایمیل: {apple_id[1]} - ریجن: {apple_id[2]} - وضعیت: {apple_id[3]} - تاریخ: {apple_id[4]}\n"
            else:
                message += "🍎 هیچ اپل آیدی فعالی ندارید.\n"
            # گیفت کارت
            c.execute("SELECT id, amount, code, status, created_at FROM gift_cards WHERE (user_id = ? OR user_id IS NULL) AND status = 'active'", (user_id,))
            gift_cards = c.fetchall()
            if gift_cards:
                message += "\n🎁 گیفت کارت‌ها:\n"
                for gift_card in gift_cards:
                    message += f"ID: {gift_card[0]} - مبلغ: {gift_card[1]:,} تومان - کد: {gift_card[2]} - وضعیت: {gift_card[3]} - تاریخ: {gift_card[4]}\n"
            else:
                message += "\n🎁 هیچ گیفت کارتی ندارید.\n"
            # حساب VPN
            c.execute("SELECT id, protocol, volume, duration, status, created_at FROM vpn_accounts WHERE (user_id = ? OR user_id IS NULL) AND status = 'active'", (user_id,))
            vpn_accounts = c.fetchall()
            if vpn_accounts:
                message += "\n🌐 حساب‌های VPN:\n"
                for vpn in vpn_accounts:
                    message += f"ID: {vpn[0]} - پروتکل: {vpn[1]} - حجم: {vpn[2]} - مدت: {vpn[3]} ماه - وضعیت: {vpn[4]} - تاریخ: {vpn[5]}\n"
            else:
                message += "\n🌐 هیچ حساب VPN فعالی ندارید.\n"
            # شماره مجازی
            c.execute("SELECT id, number, country, status, created_at FROM virtual_numbers WHERE (user_id = ? OR user_id IS NULL) AND status = 'active'", (user_id,))
            virtual_numbers = c.fetchall()
            if virtual_numbers:
                message += "\n📱 شماره‌های مجازی:\n"
                for number in virtual_numbers:
                    message += f"ID: {number[0]} - شماره: {number[1]} - کشور: {number[2]} - وضعیت: {number[3]} - تاریخ: {number[4]}\n"
            else:
                message += "\n📱 هیچ شماره مجازی فعالی ندارید.\n"
            await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in show_user_services for user {user_id}: {e}")
        await update.message.reply_text("❌ خطایی در نمایش سرویس‌ها رخ داد.")

# نمایش همه سرویس‌ها (برای ادمین)
async def show_all_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("فقط ادمین!")
        return
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            message = "📦 همه سرویس‌های موجود در دیتابیس:\n\n"
            # اپل آیدی
            c.execute("SELECT id, email, region, status, created_at, user_id FROM apple_ids WHERE status = 'active'")
            apple_ids = c.fetchall()
            if apple_ids:
                message += "🍎 اپل آیدی‌ها:\n"
                for apple_id in apple_ids:
                    user = apple_id[5] if apple_id[5] else "Sample"
                    message += f"ID: {apple_id[0]} - ایمیل: {apple_id[1]} - ریجن: {apple_id[2]} - وضعیت: {apple_id[3]} - تاریخ: {apple_id[4]} - کاربر: {user}\n"
            else:
                message += "🍎 هیچ اپل آیدی فعالی وجود ندارد.\n"
            # گیفت کارت
            c.execute("SELECT id, amount, code, status, created_at, user_id FROM gift_cards WHERE status = 'active'")
            gift_cards = c.fetchall()
            if gift_cards:
                message += "\n🎁 گیفت کارت‌ها:\n"
                for gift_card in gift_cards:
                    user = gift_card[5] if gift_card[5] else "Sample"
                    message += f"ID: {gift_card[0]} - مبلغ: {gift_card[1]:,} تومان - کد: {gift_card[2]} - وضعیت: {gift_card[3]} - تاریخ: {gift_card[4]} - کاربر: {user}\n"
            else:
                message += "\n🎁 هیچ گیفت کارتی وجود ندارد.\n"
            # حساب VPN
            c.execute("SELECT id, protocol, volume, duration, status, created_at, user_id FROM vpn_accounts WHERE status = 'active'")
            vpn_accounts = c.fetchall()
            if vpn_accounts:
                message += "\n🌐 حساب‌های VPN:\n"
                for vpn in vpn_accounts:
                    user = vpn[6] if vpn[6] else "Sample"
                    message += f"ID: {vpn[0]} - پروتکل: {vpn[1]} - حجم: {vpn[2]} - مدت: {vpn[3]} ماه - وضعیت: {vpn[4]} - تاریخ: {vpn[5]} - کاربر: {user}\n"
            else:
                message += "\n🌐 هیچ حساب VPN فعالی وجود ندارد.\n"
            # شماره مجازی
            c.execute("SELECT id, number, country, status, created_at, user_id FROM virtual_numbers WHERE status = 'active'")
            virtual_numbers = c.fetchall()
            if virtual_numbers:
                message += "\n📱 شماره‌های مجازی:\n"
                for number in virtual_numbers:
                    user = number[5] if number[5] else "Sample"
                    message += f"ID: {number[0]} - شماره: {number[1]} - کشور: {number[2]} - وضعیت: {number[3]} - تاریخ: {number[4]} - کاربر: {user}\n"
            else:
                message += "\n📱 هیچ شماره مجازی فعالی وجود ندارد.\n"
            await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in show_all_services: {e}")
        await update.message.reply_text(f"❌ خطا در نمایش همه سرویس‌ها: {e}")

# چک کردن دیتابیس (برای ادمین)
async def check_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("فقط ادمین!")
        return
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            message = "📊 وضعیت دیتابیس:\n\n"
            # کاربران
            c.execute("SELECT COUNT(*) FROM users")
            user_count = c.fetchone()[0]
            message += f"👥 تعداد کاربران: {user_count}\n"
            # اپل آیدی
            c.execute("SELECT COUNT(*) FROM apple_ids WHERE status = 'active'")
            apple_count = c.fetchone()[0]
            message += f"🍎 تعداد اپل آیدی‌های فعال: {apple_count}\n"
            # گیفت کارت
            c.execute("SELECT COUNT(*) FROM gift_cards WHERE status = 'active'")
            gift_count = c.fetchone()[0]
            message += f"🎁 تعداد گیفت کارت‌های فعال: {gift_count}\n"
            # VPN
            c.execute("SELECT COUNT(*) FROM vpn_accounts WHERE status = 'active'")
            vpn_count = c.fetchone()[0]
            message += f"🌐 تعداد حساب‌های VPN فعال: {vpn_count}\n"
            # شماره مجازی
            c.execute("SELECT COUNT(*) FROM virtual_numbers WHERE status = 'active'")
            number_count = c.fetchone()[0]
            message += f"📱 تعداد شماره‌های مجازی فعال: {number_count}\n"
            await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in check_db: {e}")
        await update.message.reply_text(f"❌ خطا در چک کردن دیتابیس: {e}")

# ریست کاربر (برای ادمین)
async def reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("فقط ادمین!")
        return
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            # حذف محصولات کاربر
            c.execute("DELETE FROM apple_ids WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM gift_cards WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM vpn_accounts WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM virtual_numbers WHERE user_id = ?", (user_id,))
            # تنظیم موجودی به 100,000 تومان
            c.execute("UPDATE users SET balance = 100000 WHERE user_id = ?", (user_id,))
            # اضافه کردن یک گیفت‌کارت نمونه برای کاربر
            c.execute("INSERT INTO gift_cards (amount, code, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                      (30000, f"USER-GIFT-{uuid.uuid4().hex[:10]}", "active", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        await update.message.reply_text("✅ اطلاعات کاربر ریست شد و یک گیفت‌کارت نمونه اضافه شد!")
    except Exception as e:
        logger.error(f"Error in reset_user for user {user_id}: {e}")
        await update.message.reply_text(f"❌ خطا در ریست کاربر: {e}")

# مدیریت ورودی‌های ادمین
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("فقط ادمین!")
        return
    mode = context.user_data.get("mode")
    text = update.message.text
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            if mode == "broadcast":
                c.execute("SELECT user_id FROM users")
                users = c.fetchall()
                for user in users:
                    try:
                        await context.bot.send_message(chat_id=user[0], text=text)
                    except:
                        pass
                await update.message.reply_text("✅ پیام همگانی ارسال شد!")
                context.user_data["mode"] = None
            elif mode == "add_admin":
                try:
                    new_admin_id = int(text)
                    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin_id,))
                    conn.commit()
                    await update.message.reply_text(f"✅ ادمین جدید ({new_admin_id}) اضافه شد!")
                except ValueError:
                    await update.message.reply_text("❌ آیدی معتبر وارد کنید!")
                context.user_data["mode"] = None
            elif mode == "add_balance":
                try:
                    user_id, amount = map(int, text.split())
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                    conn.commit()
                    await update.message.reply_text(f"✅ موجودی کاربر {user_id} به مقدار {amount:,} افزایش یافت!")
                except ValueError:
                    await update.message.reply_text("❌ فرمت اشتباه! مثال: 123 5000")
                context.user_data["mode"] = None
            elif mode == "user_stats":
                try:
                    target_user_id = int(text)
                    c.execute("SELECT phone, balance, joined_at FROM users WHERE user_id = ?", (target_user_id,))
                    user = c.fetchone()
                    if user:
                        message = f"👤 آمار کاربر {target_user_id}:\n"
                        message += f"شماره: {user[0]}\nموجودی: {user[1]:,} تومان\nتاریخ عضویت: {user[2]}"
                        await update.message.reply_text(message)
                    else:
                        await update.message.reply_text("❌ کاربر یافت نشد!")
                except ValueError:
                    await update.message.reply_text("❌ آیدی معتبر وارد کنید!")
                context.user_data["mode"] = None
            elif mode == "adjust_balance":
                try:
                    user_id, amount = map(int, text.split())
                    c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
                    conn.commit()
                    await update.message.reply_text(f"✅ موجودی کاربر {user_id} به {amount:,} تومان تنظیم شد!")
                except ValueError:
                    await update.message.reply_text("❌ فرمت اشتباه! مثال: 123 10000")
                context.user_data["mode"] = None
            elif mode == "support":
                c.execute("INSERT INTO tickets (user_id, message, status, created_at) VALUES (?, ?, ?, ?)",
                          (user_id, text, "open", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                await update.message.reply_text("✅ پیام شما به پشتیبانی ارسال شد!")
                context.user_data["mode"] = None
    except Exception as e:
        logger.error(f"Error in handle_admin_input for mode {mode}: {e}")
        await update.message.reply_text("❌ خطایی رخ داد. دوباره امتحان کن!")

# مدیریت دسته‌بندی‌های callback
async def handle_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    logger.info(f"Received callback query from user {user_id}: {data}")
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            balance = result[0] if result else 0
            logger.info(f"User {user_id} balance: {balance}")
            if data.startswith("vpn_"):
                parts = data.split("_")
                if len(parts) == 3:
                    protocol, volume = parts[1], parts[2]
                    prices = get_setting("vpn_prices")[protocol]
                    keyboard = [[InlineKeyboardButton(f"{k} ماه - {v[k]:,} تومان", callback_data=f"vpn_{protocol}_{volume}_{k}")]
                               for k in prices[volume].keys()]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.reply_text(f"🌐 VPN {protocol} ({volume}):", reply_markup=reply_markup)
                elif len(parts) == 4:
                    protocol, volume, duration = parts[1], parts[2], parts[3]
                    price = get_setting("vpn_prices")[protocol][volume][int(duration)]
                    logger.info(f"Processing VPN purchase: protocol={protocol}, volume={volume}, duration={duration}, price={price}")
                    if balance >= price:
                        c.execute("INSERT INTO vpn_accounts (config, protocol, volume, duration, status, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (f"config_{uuid.uuid4()}", protocol, volume, duration, "active", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
                        conn.commit()
                        logger.info(f"VPN purchase completed for user {user_id}")
                        await query.message.reply_text(f"✅ VPN {protocol} ({volume}, {duration} ماه) فعال شد!")
                    else:
                        await query.message.reply_text(get_setting("insufficient_balance_message").format(amount=price))
            elif data.startswith("apple_"):
                parts = data.split("_")
                if len(parts) == 2:
                    region = parts[1]
                    prices = get_setting("apple_id_prices")[region]
                    keyboard = [[InlineKeyboardButton(f"{k} تا - {v:,} تومان", callback_data=f"apple_{region}_{k}")]
                               for k, v in prices.items()]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.reply_text(f"🍎 اپل آیدی {region}:", reply_markup=reply_markup)
                elif len(parts) == 3:
                    region, count = parts[1], parts[2]
                    price = get_setting("apple_id_prices")[region][int(count)]
                    logger.info(f"Processing Apple ID purchase: region={region}, count={count}, price={price}")
                    if balance >= price:
                        c.execute("INSERT INTO apple_ids (email, password, questions, region, status, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (f"apple_{uuid.uuid4()}@example.com", "pass123", "Q1:Ans1", region, "active", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
                        conn.commit()
                        logger.info(f"Apple ID purchase completed for user {user_id}")
                        await query.message.reply_text(f"✅ اپل آیدی {region} ({count} تا) فعال شد!")
                    else:
                        await query.message.reply_text(get_setting("insufficient_balance_message").format(amount=price))
            elif data.startswith("gift_"):
                amount = int(data.replace("gift_", ""))
                logger.info(f"Processing gift card purchase: amount={amount}")
                if balance >= amount:
                    c.execute("INSERT INTO gift_cards (amount, code, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                              (amount, hashlib.md5(f"{uuid.uuid4()}".encode()).hexdigest()[:10], "active", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
                    conn.commit()
                    logger.info(f"Gift card purchase completed for user {user_id}")
                    await query.message.reply_text(f"✅ گیفت کارت {amount:,} تومانی فعال شد!")
                else:
                    await query.message.reply_text(get_setting("insufficient_balance_message").format(amount=amount))
            elif data.startswith("virtual_"):
                country = data.replace("virtual_", "")
                price = get_setting("virtual_number_prices")[country]
                logger.info(f"Processing virtual number purchase: country={country}, price={price}")
                if balance >= price:
                    c.execute("INSERT INTO virtual_numbers (number, country, status, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                              (f"+{country}{uuid.uuid4().int % 1000000000}", country, "active", user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
                    conn.commit()
                    logger.info(f"Virtual number purchase completed for user {user_id}")
                    await query.message.reply_text(f"✅ شماره مجازی {country} فعال شد!")
                else:
                    await query.message.reply_text(get_setting("insufficient_balance_message").format(amount=price))
    except Exception as e:
        logger.error(f"Error in handle_category_callback for user {user_id}: {e}")
        await query.message.reply_text("❌ خطایی رخ داد. دوباره امتحان کن!")

# منوی ادمین
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("admin_commands_enabled") == "0":
        await update.message.reply_text("پنل ادمین غیرفعاله!")
        return
    keyboard = [
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="broadcast")],
        [InlineKeyboardButton("➕ افزودن همکار", callback_data="add_admin")],
        [InlineKeyboardButton("🔍 جستجوی سرویس", callback_data="search_service")],
        [InlineKeyboardButton("💰 افزایش موجودی", callback_data="add_balance")],
        [InlineKeyboardButton("✅ تأیید پرداخت‌ها", callback_data="confirm_payments")],
        [InlineKeyboardButton("📊 آمار ربات", callback_data="bot_stats")],
        [InlineKeyboardButton("👤 آمار کاربران", callback_data="user_stats")],
        [InlineKeyboardButton("⚖️ تنظیم موجودی", callback_data="adjust_balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📊 پنل ادمین:", reply_markup=reply_markup)

# مدیریت callbackهای ادمین
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.message.reply_text("فقط ادمین اصلی!")
        return
    data = query.data
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            if data == "broadcast":
                await query.message.reply_text("متن پیام رو برای برادکست ارسال کنید.")
                context.user_data["mode"] = "broadcast"
            elif data == "add_admin":
                await query.message.reply_text("آیدی ادمین جدید رو ارسال کنید.")
                context.user_data["mode"] = "add_admin"
            elif data == "search_service":
                await query.message.reply_text("جستجوی سرویس فعال شد!")
                # منطق جستجو اضافه کن
            elif data == "add_balance":
                await query.message.reply_text("آیدی کاربر و مقدار رو ارسال کنید (مثال: 123 5000).")
                context.user_data["mode"] = "add_balance"
            elif data == "confirm_payments":
                c.execute("SELECT id, user_id, amount FROM transactions WHERE status = 'pending'")
                payments = c.fetchall()
                if payments:
                    response = "📜 لیست پرداخت‌های در انتظار:\n"
                    keyboard = [[InlineKeyboardButton(f"تأیید {p[0]}", callback_data=f"confirm_{p[0]}")] for p in payments]
                    response += "\n".join([f"ID: {p[0]} - کاربر: {p[1]} - مبلغ: {p[2]:,} تومان" for p in payments])
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.message.reply_text(response, reply_markup=reply_markup)
                else:
                    await query.message.reply_text("هیچ پرداختی در انتظار نیست.")
            elif data == "bot_stats":
                c.execute("SELECT COUNT(*) FROM users")
                user_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM transactions WHERE status = 'confirmed'")
                transaction_count = c.fetchone()[0]
                await query.message.reply_text(f"📊 آمار ربات:\nکاربران: {user_count:,}\nتراکنش‌های موفق: {transaction_count:,}")
            elif data == "user_stats":
                await query.message.reply_text("آیدی کاربر رو برای آمار ارسال کنید.")
                context.user_data["mode"] = "user_stats"
            elif data == "adjust_balance":
                await query.message.reply_text("آیدی کاربر و مقدار جدید رو ارسال کنید (مثال: 123 10000).")
                context.user_data["mode"] = "adjust_balance"
    except Exception as e:
        logger.error(f"Error in handle_admin_callback for user {user_id}: {e}")
        await query.message.reply_text("❌ خطایی رخ داد. دوباره امتحان کن!")

# مدیریت تأیید پرداخت
async def handle_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.message.reply_text("فقط ادمین!")
        return
    data = query.data.replace("confirm_", "")
    try:
        with sqlite3.connect("shop.db") as conn:
            c = conn.cursor()
            c.execute("UPDATE transactions SET admin_confirmed = 1, status = 'confirmed' WHERE id = ?", (data,))
            c.execute("SELECT user_id, amount FROM transactions WHERE id = ?", (data,))
            result = c.fetchone()
            if result:
                user_id, amount = result
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                conn.commit()
                await query.message.reply_text(f"✅ تراکنش {data} تأیید شد!")
            else:
                await query.message.reply_text("❌ تراکنش یافت نشد!")
    except Exception as e:
        logger.error(f"Error in handle_payment_callback for transaction {data}: {e}")
        await query.message.reply_text("❌ خطایی رخ داد. دوباره امتحان کن!")

# ریست دیتابیس (برای ادمین)
async def restart_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("فقط ادمین!")
        return
    try:
        os.remove("shop.db")
        init_db()
        await update.message.reply_text("✅ دیتابیس با موفقیت ریست شد و محصولات نمونه اضافه شدند!")
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        await update.message.reply_text(f"❌ خطا در ریست دیتابیس: {e}")

# مدیریت خطا
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ خطایی رخ داد. لطفاً دوباره امتحان کنید.")

# وب‌هوک Flask
@app.route('/webhook', methods=['POST'])
async def webhook():
    global telegram_app
    update_json = request.get_json()
    logger.info(f"Webhook received: {update_json}")
    try:
        if telegram_app is None:
            logger.info("Initializing telegram_app...")
            await initialize_app()
        if telegram_app is None:
            logger.error("Failed to initialize telegram_app")
            return jsonify({"error": "Bot initialization failed"}), 500
        update = Update.de_json(update_json, telegram_app.bot)
        if update:
            logger.info(f"Processing update: {update}")
            await telegram_app.process_update(update)
        else:
            logger.error("Failed to parse update")
            return jsonify({"error": "Invalid update data"}), 400
        return jsonify({"status": "OK"}), 200
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return jsonify({"error": str(e)}), 500

# بررسی سلامت
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

# مقداردهی اولیه برنامه
async def initialize_app():
    global telegram_app, loop
    try:
        init_db()
        telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
        await telegram_app.initialize()
        telegram_app.add_handler(CommandHandler("start", show_intro))
        telegram_app.add_handler(CommandHandler("checkdb", check_db))
        telegram_app.add_handler(CommandHandler("showall", show_all_services))
        telegram_app.add_handler(CommandHandler("resetuser", reset_user))
        telegram_app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        telegram_app.add_handler(CallbackQueryHandler(handle_category_callback))
        telegram_app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^broadcast|add_admin|search_service|add_balance|confirm_payments|bot_stats|user_stats|adjust_balance$"))
        telegram_app.add_handler(CallbackQueryHandler(handle_payment_callback, pattern="^confirm_"))
        telegram_app.add_error_handler(error_handler)
        logger.info("Setting webhook: %s", WEBHOOK_URL)
        await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error(f"Error in initialize_app: {e}")
        telegram_app = None

# اجرای برنامه
def run_app():
    global loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(initialize_app())
        from hypercorn.config import Config
        from hypercorn.asyncio import serve
        config = Config()
        port = int(os.environ.get("PORT", 5000))
        config.bind = [f"0.0.0.0:{port}"]
        loop.run_until_complete(serve(app, config))
    except Exception as e:
        logger.error(f"Error in run_app: {e}")
    finally:
        if not loop.is_closed():
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

if __name__ == "__main__":
    run_app()