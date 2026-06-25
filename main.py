"""
==========================================================================================
💎 A'LO TA'LIM - PREMIUM INTEGRATSIYA TIZIMI (v5.5 PRO)
==========================================================================================
Muallif: A'lo Ta'lim Platformasi
Tavsif: Telegram bot va Web API integratsiyasi. Ushbu tizim foydalanuvchilarni 
        ro'yxatdan o'tkazish, ularga maxsus veb-kodlar berish, admin paneli orqali 
        boshqarish va mukammal xizmat ko'rsatish uchun mo'ljallangan.

Yangi Foydalanuvchi Funksiyalari (5 ta):
1. 📚 FAQ (Ko'p so'raladigan savollar) tizimi
2. ⚙️ Shaxsiy Sozlamalar (Ismni o'zgartirish, Bildirishnomalarni yoqish/o'chirish)
3. ⭐ Baholash va Fikr-mulohaza qoldirish (Fidbek tizimi)
4. 👥 Referal Dastur (Do'stlarni taklif qilish va ball yig'ish reytingi)
5. 🔐 Tizimga kirish tarixi (Saytga qachon kirilganligini kuzatish)

Yangi Admin Funksiyalari (8 ta):
1. 📈 Kengaytirilgan chuqur statistika (Kunlik, umumiy)
2. 📢 Murakkab Broadcast (Rasm/Video + Matn yuborish)
3. 👥 Foydalanuvchilarni individual boshqarish (Ban/Unban qilish, kodini o'chirish)
4. 🗂 Ma'lumotlar bazasini eksport qilish (Excel/CSV formatida yuklab olish)
5. ⚙️ Tizim Sozlamalari (Texnik xizmat / Maintenance rejimini yoqish)
6. 📢 Majburiy obuna kanallarini bot orqali boshqarish (Qo'shish/O'chirish)
7. ⭐ Foydalanuvchilar qoldirgan fikr-mulohazalarni o'qish
8. 🔑 Barcha veb-kodlarni xavfsizlik uchun birdaniga bekor qilish

Maksimal darajada xavfsizlik va Anti-Spam tizimlari bilan ta'minlangan.
==========================================================================================
"""

import asyncio
import logging
import os
import sqlite3
import html
import random
import csv
from io import StringIO, BytesIO
from datetime import datetime, timedelta
from typing import Final, Any, Optional, List, Dict

from aiohttp import web
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, BufferedInputFile
)
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# ==========================================================================================
# ⚙️ 1. ASOSIY KONFIGURATSIYA VA O'ZGARUVCHILAR
# ==========================================================================================
class Config:
    TOKEN: Final[str] = os.getenv("BOT_TOKEN", "") # O'zingizning bot tokeningizni qo'ying
    ADMIN_ID: Final[int] = int(os.getenv("ADMIN_ID", "0") or "0")
    DB_NAME: Final[str] = os.getenv("DB_NAME", "premium_database.db")
    PORT: Final[int] = int(os.getenv("PORT", "8080"))
    
    # Premium Dizayn elementlari
    H_LINE = "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>"
    D_LINE = "<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>"
    S_LINE = "<b>────────────────────────────</b>"
    
    # Menyu tugmalari (Foydalanuvchi)
    BTN_WEB = "🌐 Saytga kirish"
    BTN_PROF = "👤 Mening Kabinetim"
    BTN_REF = "👥 Referal Dastur"
    BTN_FAQ = "📚 FAQ"
    BTN_FEEDBACK = "⭐ Fikr Bildirish"
    BTN_SETTINGS = "⚙️ Sozlamalar"
    BTN_HELP = "🆘 Adminga yozish"
    
    # Menyu tugmalari (Umumiy)
    BTN_BACK = "⬅️ Orqaga"
    BTN_HOME = "🏠 Asosiy Menyu"
    
    # Menyu tugmalari (Admin)
    BTN_ADM_PANEL = "🛠 Admin Panel"
    BTN_ADM_STATS = "📊 Statistika"
    BTN_ADM_USERS = "👥 Foydalanuvchilar"
    BTN_ADM_BROADCAST = "📢 Xabar Yuborish"
    BTN_ADM_EXPORT = "🗂 DB Eksport"
    BTN_ADM_CHANNELS = "📢 Kanallar"
    BTN_ADM_FEEDBACKS = "⭐ Fikrlar"
    BTN_ADM_SETTINGS = "⚙️ Tizim Rejimi"
    BTN_ADM_SECURITY = "🔐 Xavfsizlik"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=Config.TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==========================================================================================
# 🗄 2. MA'LUMOTLAR BAZASI (KENGAYTIRILGAN)
# ==========================================================================================
class DB:
    @staticmethod
    def connect():
        conn = sqlite3.connect(Config.DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def setup(cls):
        with cls.connect() as conn:
            c = conn.cursor()
            
            # Foydalanuvchilar
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid INTEGER PRIMARY KEY,
                    fullname TEXT,
                    username TEXT,
                    joined_at TIMESTAMP,
                    is_banned INTEGER DEFAULT 0,
                    referrer_id INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0,
                    notifications INTEGER DEFAULT 1
                )
            """)
            
            # Veb kodlar
            c.execute("""
                CREATE TABLE IF NOT EXISTS web_codes (
                    uid INTEGER PRIMARY KEY,
                    code TEXT UNIQUE,
                    created_at TIMESTAMP
                )
            """)
            
            # Murojaatlar
            c.execute("""
                CREATE TABLE IF NOT EXISTS support_messages (
                    mid INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER,
                    message_text TEXT,
                    created_at TIMESTAMP,
                    is_replied INTEGER DEFAULT 0
                )
            """)
            
            # Fikr-mulohazalar (YANGI)
            c.execute("""
                CREATE TABLE IF NOT EXISTS feedbacks (
                    fid INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER,
                    stars INTEGER,
                    comment TEXT,
                    created_at TIMESTAMP
                )
            """)
            
            # Saytga kirish tarixi (YANGI)
            c.execute("""
                CREATE TABLE IF NOT EXISTS login_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER,
                    ip_address TEXT,
                    login_time TIMESTAMP,
                    status TEXT
                )
            """)
            
            # Majburiy kanallar (YANGI)
            c.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE,
                    channel_name TEXT
                )
            """)
            
            # Tizim sozlamalari (YANGI)
            c.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT
                )
            """)
            
            # Dastlabki sozlamalarni kiritish
            c.execute("INSERT OR IGNORE INTO system_settings (setting_key, setting_value) VALUES ('maintenance', '0')")
            
            conn.commit()

    @classmethod
    def execute(cls, sql: str, params: tuple = ()) -> int:
        with cls.connect() as conn:
            c = conn.cursor()
            c.execute(sql, params)
            conn.commit()
            return c.lastrowid

    @classmethod
    def fetchone(cls, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with cls.connect() as conn:
            c = conn.cursor()
            c.execute(sql, params)
            return c.fetchone()

    @classmethod
    def fetchall(cls, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with cls.connect() as conn:
            c = conn.cursor()
            c.execute(sql, params)
            return c.fetchall()

    @classmethod
    def get_setting(cls, key: str) -> str:
        res = cls.fetchone("SELECT setting_value FROM system_settings WHERE setting_key=?", (key,))
        return res['setting_value'] if res else ""

    @classmethod
    def set_setting(cls, key: str, value: str):
        cls.execute("INSERT OR REPLACE INTO system_settings (setting_key, setting_value) VALUES (?, ?)", (key, value))


# ==========================================================================================
# 🧠 3. HOLATLAR (FSM STATES)
# ==========================================================================================
class Form(StatesGroup):
    reg_name = State()
    
    # Foydalanuvchi qismi
    support_msg = State()
    feedback_msg = State()
    settings_name = State()
    
    # Admin qismi
    adm_reply = State()
    adm_broadcast_msg = State()
    adm_broadcast_confirm = State()
    adm_manage_user = State()
    adm_add_channel_name = State()
    adm_add_channel_id = State()


# ==========================================================================================
# 🎨 4. KLAVIATURALAR VA UI BUILDERLAR
# ==========================================================================================
class Keyboards:
    @staticmethod
    def main_menu(user_id: int):
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=Config.BTN_WEB), KeyboardButton(text=Config.BTN_PROF))
        b.row(KeyboardButton(text=Config.BTN_REF), KeyboardButton(text=Config.BTN_SETTINGS))
        b.row(KeyboardButton(text=Config.BTN_FAQ), KeyboardButton(text=Config.BTN_HELP))
        b.row(KeyboardButton(text=Config.BTN_FEEDBACK))
        
        if user_id == Config.ADMIN_ID:
            b.row(KeyboardButton(text=Config.BTN_ADM_PANEL))
            
        b.adjust(2, 2, 2, 1, 1)
        return b.as_markup(resize_keyboard=True)

    @staticmethod
    def admin_menu():
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=Config.BTN_ADM_STATS), KeyboardButton(text=Config.BTN_ADM_USERS))
        b.row(KeyboardButton(text=Config.BTN_ADM_BROADCAST), KeyboardButton(text=Config.BTN_ADM_CHANNELS))
        b.row(KeyboardButton(text=Config.BTN_ADM_EXPORT), KeyboardButton(text=Config.BTN_ADM_FEEDBACKS))
        b.row(KeyboardButton(text=Config.BTN_ADM_SETTINGS), KeyboardButton(text=Config.BTN_ADM_SECURITY))
        b.row(KeyboardButton(text=Config.BTN_HOME))
        b.adjust(2, 2, 2, 2, 1)
        return b.as_markup(resize_keyboard=True)

    @staticmethod
    def back_home():
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=Config.BTN_BACK), KeyboardButton(text=Config.BTN_HOME)]],
            resize_keyboard=True
        )

    @staticmethod
    def just_back():
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=Config.BTN_BACK)]], resize_keyboard=True)

    @staticmethod
    def web_code(has_code: bool):
        b = InlineKeyboardBuilder()
        if has_code:
            b.row(
                InlineKeyboardButton(text="🔄 Yangilash", callback_data="web_regenerate"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data="web_delete")
            )
            b.row(InlineKeyboardButton(text="📜 Kirish tarixini ko'rish", callback_data="web_history"))
        else:
            b.row(InlineKeyboardButton(text="🔑 Yangi Kod Yaratish", callback_data="web_generate"))
        return b.as_markup()

    @staticmethod
    def settings_menu(notifications: bool):
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="✏️ Ismni o'zgartirish", callback_data="set_name"))
        notif_text = "🔔 Xabarnomalar: YOQILGAN" if notifications else "🔕 Xabarnomalar: O'CHIRILGAN"
        b.row(InlineKeyboardButton(text=notif_text, callback_data="set_notifications"))
        return b.as_markup()

    @staticmethod
    def stars_keyboard():
        b = InlineKeyboardBuilder()
        b.row(
            InlineKeyboardButton(text="⭐", callback_data="star_1"),
            InlineKeyboardButton(text="⭐⭐", callback_data="star_2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data="star_3")
        )
        b.row(
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="star_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="star_5")
        )
        return b.as_markup()


# ==========================================================================================
# 🛡 5. MIDDLEWARE (XAVFSIZLIK VA NAZORAT)
# ==========================================================================================
class SecurityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message | CallbackQuery, data: Dict[str, Any]):
        user_id = event.from_user.id
        
        # Texnik xizmat rejimi tekshiruvi
        is_maintenance = DB.get_setting('maintenance') == '1'
        if is_maintenance and user_id != Config.ADMIN_ID:
            msg = "⚙️ <b>Tizimda texnik ishlar olib borilmoqda!</b>\nIltimos, birozdan so'ng qayta urinib ko'ring."
            if isinstance(event, Message):
                await event.answer(msg, parse_mode="HTML")
            else:
                await event.answer(msg, show_alert=True)
            return

        # Ban tekshiruvi
        user = DB.fetchone("SELECT is_banned FROM users WHERE uid=?", (user_id,))
        if user and user['is_banned'] == 1:
            msg = "🚫 <b>Sizning hisobingiz tizim qoidalarini buzganlik uchun bloklangan!</b>\nMurojaat uchun adminga yozing."
            if isinstance(event, Message):
                await event.answer(msg, parse_mode="HTML")
            else:
                await event.answer(msg, show_alert=True)
            return

        return await handler(event, data)

dp.message.middleware(SecurityMiddleware())
dp.callback_query.middleware(SecurityMiddleware())


# ==========================================================================================
# 🔄 6. YORDAMCHI FUNKSIYALAR
# ==========================================================================================
def format_dt(dt_str: str) -> str:
    if not dt_str: return "Noma'lum"
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except:
        return dt_str[:19]

def gen_code() -> str:
    while True:
        code = str(random.randint(1000, 9999))
        if not DB.fetchone("SELECT uid FROM web_codes WHERE code=?", (code,)):
            return code

async def check_subscriptions(bot: Bot, user_id: int) -> bool:
    channels = DB.fetchall("SELECT channel_id FROM channels")
    if not channels:
        return True
    
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch['channel_id'], user_id=user_id)
            if member.status in ['left', 'kicked', 'banned']:
                return False
        except Exception as e:
            logger.warning(f"Kanalni tekshirishda xatolik {ch['channel_id']}: {e}")
            return False # Agar bot kanalda admin bo'lmasa xato beradi
    return True

def get_sub_keyboard():
    b = InlineKeyboardBuilder()
    channels = DB.fetchall("SELECT channel_id, channel_name FROM channels")
    for ch in channels:
        cid = ch['channel_id'].replace("@", "")
        b.row(InlineKeyboardButton(text=ch['channel_name'], url=f"https://t.me/{cid}"))
    b.row(InlineKeyboardButton(text="✅ Obunani Tasdiqlash", callback_data="check_sub"))
    return b.as_markup()


# ==========================================================================================
# 🚀 7. ASOSIY HANDLERLAR (RO'YXATDAN O'TISH)
# ==========================================================================================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id
    
    # Referal tizimi orqali kirganligini tekshirish
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    referrer_id = 0
    if args and args.startswith("ref_"):
        try:
            ref_id = int(args.split("_")[1])
            if ref_id != user_id:
                referrer_id = ref_id
        except:
            pass

    # Obuna tekshiruvi
    if not await check_subscriptions(bot, user_id):
        text = (
            f"🛑 <b>DIQQAT! Tizimdan foydalanish uchun obuna bo'ling!</b>\n"
            f"{Config.S_LINE}\n"
            f"Barcha funksiyalarni ochish uchun quyidagi kanallarga a'zo bo'ling."
        )
        return await message.answer(text, reply_markup=get_sub_keyboard(), parse_mode="HTML")

    user = DB.fetchone("SELECT * FROM users WHERE uid=?", (user_id,))
    if not user:
        await state.update_data(ref_id=referrer_id)
        await state.set_state(Form.reg_name)
        text = (
            f"🌟 <b>A'LO TA'LIM PLATFORMASIGA XUSH KELIBSIZ!</b>\n"
            f"{Config.D_LINE}\n\n"
            f"✍️ Tizimdan to'liq foydalanish uchun iltimos, <b>Ism va Familiyangizni</b> kiriting:\n\n"
            f"💡 <i>Namuna: Alisher Navoiy</i>"
        )
        return await message.answer(text, reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True), parse_mode="HTML")

    text = (
        f"👑 <b>ASOSIY TIZIM PANELI</b>\n"
        f"{Config.D_LINE}\n"
        f"Hurmatli <b>{html.escape(user['fullname'])}</b>, qaytganingizdan xursandmiz!\n\n"
        f"👇 Kerakli bo'limni tanlang:"
    )
    await message.answer(text, reply_markup=Keyboards.main_menu(user_id), parse_mode="HTML")

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await check_subscriptions(bot, call.from_user.id):
        return await call.answer("❌ Siz barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
    
    await call.message.delete()
    # Psevdo-start yuborish
    message = call.message
    message.from_user = call.from_user
    message.text = "/start"
    await cmd_start(message, state, bot)

@dp.message(Form.reg_name)
async def process_reg_name(message: Message, state: FSMContext):
    fullname = message.text.strip()
    if len(fullname) < 4 or " " not in fullname:
        return await message.answer("⚠️ <b>Iltimos, to'liq Ism va Familiya kiriting!</b> (Masalan: Alisher Navoiy)", parse_mode="HTML")

    data = await state.get_data()
    ref_id = data.get("ref_id", 0)
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    DB.execute(
        "INSERT INTO users (uid, fullname, username, joined_at, referrer_id) VALUES (?,?,?,?,?)",
        (user_id, fullname, username, datetime.now().isoformat(), ref_id)
    )
    
    # Referalga bonus berish
    if ref_id:
        DB.execute("UPDATE users SET points = points + 10 WHERE uid=?", (ref_id,))
        try:
            await bot.send_message(ref_id, f"🎉 <b>Tabriklaymiz!</b> Sizning taklifingiz orqali <b>{html.escape(fullname)}</b> ro'yxatdan o'tdi va sizga 10 ball berildi!", parse_mode="HTML")
        except:
            pass

    await state.clear()
    text = (
        f"✅ <b>Muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n"
        f"{Config.S_LINE}\n"
        f"Tizim xizmatlaridan foydalanishingiz mumkin."
    )
    await message.answer(text, reply_markup=Keyboards.main_menu(user_id), parse_mode="HTML")

@dp.message(or_f(F.text == Config.BTN_HOME, F.text == Config.BTN_BACK))
async def go_home(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyudasiz.", reply_markup=Keyboards.main_menu(message.from_user.id))


# ==========================================================================================
# 🌐 8. SAYTGA KIRISH KODI (YANGILANGAN + TARIX)
# ==========================================================================================
@dp.message(F.text == Config.BTN_WEB)
async def web_code_menu(message: Message):
    user_id = message.from_user.id
    code_row = DB.fetchone("SELECT * FROM web_codes WHERE uid=?", (user_id,))
    
    if code_row:
        text = (
            f"🌐 <b>VEB-SAYTGA KIRISH KODI</b>\n"
            f"{Config.D_LINE}\n\n"
            f"🔑 Shaxsiy Kod: <span class='tg-spoiler'><b>{code_row['code']}</b></span>\n"
            f"📅 Yaratilgan: <b>{format_dt(code_row['created_at'])}</b>\n\n"
            f"<i>💡 Kodni nusxalash uchun ustiga bosing. Maxfiylikni saqlang!</i>"
        )
        await message.answer(text, reply_markup=Keyboards.web_code(True), parse_mode="HTML")
    else:
        text = (
            f"🌐 <b>VEB-SAYTGA KIRISH</b>\n"
            f"{Config.D_LINE}\n"
            f"Sizda hali saytga kirish uchun maxsus 4 xonali kod mavjud emas. Quyidagi tugmani bosib yarating."
        )
        await message.answer(text, reply_markup=Keyboards.web_code(False), parse_mode="HTML")

@dp.callback_query(F.data.startswith("web_"))
async def web_code_actions(call: CallbackQuery):
    action = call.data.split("_")[1]
    user_id = call.from_user.id
    
    if action == "generate":
        if DB.fetchone("SELECT code FROM web_codes WHERE uid=?", (user_id,)):
            return await call.answer("Kod allaqachon mavjud!", show_alert=True)
        code = gen_code()
        DB.execute("INSERT INTO web_codes (uid, code, created_at) VALUES (?,?,?)", (user_id, code, datetime.now().isoformat()))
        await call.message.edit_text(
            f"🎉 <b>KOD YARATILDI!</b>\n{Config.D_LINE}\n🔑 Kod: <code>{code}</code>",
            reply_markup=Keyboards.web_code(True), parse_mode="HTML"
        )
        await call.answer()
        
    elif action == "regenerate":
        code = gen_code()
        DB.execute("REPLACE INTO web_codes (uid, code, created_at) VALUES (?,?,?)", (user_id, code, datetime.now().isoformat()))
        await call.message.edit_text(
            f"🔄 <b>KOD YANGILANDI!</b>\n{Config.D_LINE}\n🔑 Yangi Kod: <code>{code}</code>\n<i>Eski kod bekor qilindi.</i>",
            reply_markup=Keyboards.web_code(True), parse_mode="HTML"
        )
        await call.answer()
        
    elif action == "delete":
        DB.execute("DELETE FROM web_codes WHERE uid=?", (user_id,))
        await call.message.edit_text("🗑 <b>KOD O'CHIRILDI!</b> Saytga kirish imkoniyati to'xtatildi.", reply_markup=Keyboards.web_code(False), parse_mode="HTML")
        await call.answer()
        
    elif action == "history":
        history = DB.fetchall("SELECT * FROM login_history WHERE uid=? ORDER BY login_time DESC LIMIT 5", (user_id,))
        if not history:
            return await call.answer("Tarix bo'sh. Siz hali saytga kirmagansiz.", show_alert=True)
        
        text = f"📜 <b>OXIRGI 5 TA KIRISH TARIXI:</b>\n{Config.D_LINE}\n"
        for h in history:
            status_ico = "✅" if h['status'] == 'success' else "❌"
            text += f"{status_ico} <b>Sana:</b> {format_dt(h['login_time'])}\n🌐 <b>IP:</b> {h['ip_address']}\n{Config.S_LINE}\n"
        
        await call.message.answer(text, parse_mode="HTML")
        await call.answer()


# ==========================================================================================
# 👤 9. PROFIL VA SOZLAMALAR (YANGI)
# ==========================================================================================
@dp.message(F.text == Config.BTN_PROF)
async def view_profile(message: Message):
    user_id = message.from_user.id
    u = DB.fetchone("SELECT * FROM users WHERE uid=?", (user_id,))
    c = DB.fetchone("SELECT code FROM web_codes WHERE uid=?", (user_id,))
    
    code_status = f"Faol (<code>{c['code']}</code>)" if c else "Mavjud emas"
    
    text = (
        f"👤 <b>MENING KABINETIM</b>\n"
        f"{Config.D_LINE}\n"
        f"📛 <b>F.I.Sh:</b> {html.escape(u['fullname'])}\n"
        f"🆔 <b>ID:</b> <code>{u['uid']}</code>\n"
        f"📅 <b>Ro'yxatdan o'tgan:</b> {format_dt(u['joined_at'])}\n"
        f"🔑 <b>Sayt kodi:</b> {code_status}\n"
        f"🌟 <b>Yig'ilgan ballar:</b> {u['points']} ball\n"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == Config.BTN_SETTINGS)
async def view_settings(message: Message):
    u = DB.fetchone("SELECT notifications FROM users WHERE uid=?", (message.from_user.id,))
    text = f"⚙️ <b>SHAXSIY SOZLAMALAR</b>\n{Config.S_LINE}\nBu yerdan profil ma'lumotlarini tahrirlashingiz mumkin."
    await message.answer(text, reply_markup=Keyboards.settings_menu(bool(u['notifications'])), parse_mode="HTML")

@dp.callback_query(F.data.startswith("set_"))
async def settings_actions(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    user_id = call.from_user.id
    
    if action == "name":
        await state.set_state(Form.settings_name)
        await call.message.answer("✏️ <b>Yangi Ism va Familiyangizni kiriting:</b>", reply_markup=Keyboards.just_back(), parse_mode="HTML")
        await call.answer()
        
    elif action == "notifications":
        u = DB.fetchone("SELECT notifications FROM users WHERE uid=?", (user_id,))
        new_val = 0 if u['notifications'] == 1 else 1
        DB.execute("UPDATE users SET notifications=? WHERE uid=?", (new_val, user_id))
        await call.message.edit_reply_markup(reply_markup=Keyboards.settings_menu(bool(new_val)))
        await call.answer("Holat o'zgardi!")

@dp.message(Form.settings_name)
async def save_new_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if len(new_name) < 4:
        return await message.answer("⚠️ Juda qisqa!")
        
    DB.execute("UPDATE users SET fullname=? WHERE uid=?", (new_name, message.from_user.id))
    await state.clear()
    await message.answer("✅ <b>Ismingiz muvaffaqiyatli yangilandi!</b>", reply_markup=Keyboards.main_menu(message.from_user.id), parse_mode="HTML")


# ==========================================================================================
# 👥 10. REFERAL DASTUR (YANGI)
# ==========================================================================================
@dp.message(F.text == Config.BTN_REF)
async def referral_system(message: Message, bot: Bot):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    my_refs = DB.fetchone("SELECT COUNT(*) as c FROM users WHERE referrer_id=?", (user_id,))['c']
    top_refs = DB.fetchall("SELECT fullname, points FROM users ORDER BY points DESC LIMIT 5")
    
    text = (
        f"👥 <b>REFERAL DASTUR</b>\n"
        f"{Config.D_LINE}\n\n"
        f"Do'stlaringizni taklif qiling va ballar yig'ing!\n"
        f"Har bir taklif qilingan do'st uchun <b>10 ball</b> beriladi.\n\n"
        f"🔗 <b>Sizning taklif havolangiz:</b>\n<code>{ref_link}</code>\n\n"
        f"📊 <b>Sizning natijangiz:</b>\n"
        f"Taklif qilinganlar: <b>{my_refs} ta</b>\n"
        f"{Config.S_LINE}\n"
        f"🏆 <b>TOP 5 FOYDALANUVCHILAR:</b>\n"
    )
    
    for i, r in enumerate(top_refs, 1):
        medal = ["🥇", "🥈", "🥉", "🏅", "🏅"][i-1]
        text += f"{medal} {html.escape(r['fullname'])} - {r['points']} ball\n"
        
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# ==========================================================================================
# 📚 11. FAQ VA FIKR BİLDIRISH (YANGI)
# ==========================================================================================
@dp.message(F.text == Config.BTN_FAQ)
async def show_faq(message: Message):
    text = (
        f"📚 <b>KO'P SO'RALADIGAN SAVOLLAR (FAQ)</b>\n"
        f"{Config.D_LINE}\n\n"
        f"🔹 <b>Qanday qilib saytga kirsam bo'ladi?</b>\n"
        f"<i>Javob: '🌐 Saytga kirish' tugmasini bosing va o'zingizga xos 4 xonali kod yarating. So'ng saytga o'sha kodni kiriting.</i>\n\n"
        f"🔹 <b>Kodni begonalarga bersam nima bo'ladi?</b>\n"
        f"<i>Javob: Profilingizga boshqalar kirib olishi mumkin. Bunday holatda zudlik bilan kodni '🔄 Yangilash' tugmasi orqali almashtiring.</i>\n\n"
        f"🔹 <b>Ballar nima uchun kerak?</b>\n"
        f"<i>Javob: Eng ko'p ball yig'gan a'zolar uchun kelgusida platformamiz tomonidan maxsus chegirmalar va sovg'alar taqdim etiladi.</i>\n\n"
        f"🔹 <b>Kanalga a'zo bo'lish majburiymi?</b>\n"
        f"<i>Javob: Ha, tizimdan foydalanish xavfsizligini ta'minlash maqsadida obuna talab qilinadi.</i>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == Config.BTN_FEEDBACK)
async def ask_feedback(message: Message):
    text = (
        f"⭐ <b>TIZIMNI BAHOLASH</b>\n"
        f"{Config.S_LINE}\n"
        f"Bizning platformamiz ishlashidan qanchalik qoniqdingiz?\n"
        f"Iltimos, yulduzchalar orqali baho bering:"
    )
    await message.answer(text, reply_markup=Keyboards.stars_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("star_"))
async def process_star(call: CallbackQuery, state: FSMContext):
    stars = int(call.data.split("_")[1])
    await state.update_data(stars=stars)
    await state.set_state(Form.feedback_msg)
    
    await call.message.edit_text(
        f"Siz tizimga <b>{stars} yulduz</b> berdingiz! ⭐\n\n"
        f"✍️ <i>Endi platforma haqida o'z fikr-mulohazangizni yoki taklifingizni yozib yuboring:</i>",
        parse_mode="HTML"
    )

@dp.message(Form.feedback_msg)
async def save_feedback(message: Message, state: FSMContext):
    data = await state.get_data()
    stars = data.get("stars", 5)
    comment = message.text or ""
    
    DB.execute(
        "INSERT INTO feedbacks (uid, stars, comment, created_at) VALUES (?,?,?,?)",
        (message.from_user.id, stars, comment, datetime.now().isoformat())
    )
    
    await state.clear()
    await message.answer("✅ <b>Katta rahmat!</b> Fikr-mulohazangiz adminga yetkazildi. Biz har doim rivojlanishga harakat qilamiz!", parse_mode="HTML")


# ==========================================================================================
# 🆘 12. ADMIN BILAN ALOQA (SUPPORT)
# ==========================================================================================
@dp.message(F.text == Config.BTN_HELP)
async def start_support(message: Message, state: FSMContext):
    await state.set_state(Form.support_msg)
    await message.answer(
        f"📬 <b>ADMINISTRATORGA XABAR YUBORISH</b>\n"
        f"{Config.S_LINE}\n"
        f"Savol, shikoyat yoki taklifingizni bitta xabarda batafsil yozib yuboring.",
        reply_markup=Keyboards.just_back(), parse_mode="HTML"
    )

@dp.message(Form.support_msg)
async def send_support(message: Message, state: FSMContext, bot: Bot):
    text = message.text or ""
    if len(text) < 5:
        return await message.answer("⚠️ Xabar juda qisqa!")
        
    mid = DB.execute(
        "INSERT INTO support_messages (uid, message_text, created_at) VALUES (?,?,?)",
        (message.from_user.id, text, datetime.now().isoformat())
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✍️ Javob Yozish", callback_data=f"admreply_{message.from_user.id}_{mid}"))
    
    adm_text = (
        f"🆕 <b>YANGI MUROJAAT #{mid}</b>\n"
        f"{Config.S_LINE}\n"
        f"👤 <b>Kimdan:</b> {html.escape(message.from_user.full_name)} (<code>{message.from_user.id}</code>)\n"
        f"💬 <b>Matn:</b>\n<i>{html.escape(text)}</i>"
    )
    
    try:
        await bot.send_message(Config.ADMIN_ID, adm_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except:
        pass
        
    await state.clear()
    await message.answer("✅ Xabaringiz yuborildi. Tez orada javob olasiz.", reply_markup=Keyboards.main_menu(message.from_user.id), parse_mode="HTML")


# ==========================================================================================
# 🛠 13. ADMIN PANEL VA STATISTIKA (YANGILANGAN)
# ==========================================================================================
@dp.message(F.text == Config.BTN_ADM_PANEL)
async def admin_panel(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    sys_status = "🟢 ONLINE" if DB.get_setting("maintenance") == "0" else "🔴 MAINTENANCE"
    
    text = (
        f"👑 <b>BOSH ADMIN DASHBOARD</b>\n"
        f"{Config.D_LINE}\n"
        f"Tizim Holati: <b>{sys_status}</b>\n"
        f"Server Vaqti: <b>{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</b>\n\n"
        f"<i>Quyidagi kengaytirilgan funksiyalardan birini tanlang:</i>"
    )
    await message.answer(text, reply_markup=Keyboards.admin_menu(), parse_mode="HTML")

@dp.message(F.text == Config.BTN_ADM_STATS)
async def admin_stats(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    tot_users = DB.fetchone("SELECT COUNT(*) as c FROM users")['c']
    new_today = DB.fetchone("SELECT COUNT(*) as c FROM users WHERE joined_at LIKE ?", (f"{today_str}%",))['c']
    tot_codes = DB.fetchone("SELECT COUNT(*) as c FROM web_codes")['c']
    tot_logins = DB.fetchone("SELECT COUNT(*) as c FROM login_history")['c']
    logins_today = DB.fetchone("SELECT COUNT(*) as c FROM login_history WHERE login_time LIKE ?", (f"{today_str}%",))['c']
    avg_stars = DB.fetchone("SELECT AVG(stars) as a FROM feedbacks")['a'] or 0.0
    
    text = (
        f"📊 <b>KENGAYTIRILGAN STATISTIKA</b>\n"
        f"{Config.D_LINE}\n\n"
        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"├ Jami a'zolar: <b>{tot_users}</b>\n"
        f"└ Bugun qo'shilganlar: <b>{new_today}</b>\n\n"
        f"🌐 <b>Sayt Aktivligi:</b>\n"
        f"├ Berilgan kodlar: <b>{tot_codes}</b>\n"
        f"├ Jami kirishlar: <b>{tot_logins} marta</b>\n"
        f"└ Bugungi kirishlar: <b>{logins_today} marta</b>\n\n"
        f"⭐ <b>O'rtacha baho:</b> {avg_stars:.1f} / 5.0"
    )
    await message.answer(text, parse_mode="HTML")


# ==========================================================================================
# 📢 14. ADMIN BROADCAST (RASM/VIDEO BILAN)
# ==========================================================================================
@dp.message(F.text == Config.BTN_ADM_BROADCAST)
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(Form.adm_broadcast_msg)
    await message.answer(
        "📢 <b>Xabarni yuboring:</b>\n\n(Matn, Rasm, Video yoki Hujjat yuborishingiz mumkin. HTML teglari ishlaydi)",
        reply_markup=Keyboards.just_back(), parse_mode="HTML"
    )

@dp.message(Form.adm_broadcast_msg)
async def broadcast_preview(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    
    # Xabarni saqlab qolish
    await state.update_data(msg_id=message.message_id, from_chat=message.chat.id)
    await state.set_state(Form.adm_broadcast_confirm)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ YUBORISH", callback_data="bc_send"),
        InlineKeyboardButton(text="❌ BEKOR QILISH", callback_data="bc_cancel")
    )
    
    await message.copy_to(message.chat.id, reply_markup=kb.as_markup())
    await message.answer("👀 <b>Yuqorida xabarning ko'rinishi. Yuborishni tasdiqlaysizmi?</b>", parse_mode="HTML")

@dp.callback_query(F.data.startswith("bc_"), Form.adm_broadcast_confirm)
async def broadcast_action(call: CallbackQuery, state: FSMContext, bot: Bot):
    action = call.data.split("_")[1]
    if action == "cancel":
        await state.clear()
        return await call.message.edit_text("🚫 Bekor qilindi.")
        
    await call.message.edit_text("🔄 <i>Xabar yuborilmoqda, jarayon boshlandi...</i>", parse_mode="HTML")
    
    data = await state.get_data()
    msg_id = data['msg_id']
    from_chat = data['from_chat']
    
    users = DB.fetchall("SELECT uid FROM users WHERE is_banned=0")
    success, fail = 0, 0
    
    for u in users:
        try:
            await bot.copy_message(chat_id=u['uid'], from_chat_id=from_chat, message_id=msg_id)
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
            
    await call.message.answer(
        f"✅ <b>Xabar yetkazish yakunlandi!</b>\n\n"
        f"🟢 Muvaffaqiyatli: <b>{success}</b>\n"
        f"🔴 Bloklaganlar: <b>{fail}</b>",
        reply_markup=Keyboards.admin_menu(), parse_mode="HTML"
    )
    await state.clear()


# ==========================================================================================
# 👥 15. FOYDALANUVCHILARNI BOSHQARISH VA EKSPORT
# ==========================================================================================
@dp.message(F.text == Config.BTN_ADM_USERS)
async def manage_users(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(Form.adm_manage_user)
    await message.answer("🔍 <b>Foydalanuvchi ID raqamini kiriting:</b>", reply_markup=Keyboards.just_back(), parse_mode="HTML")

@dp.message(Form.adm_manage_user)
async def user_details(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    try:
        uid = int(message.text.strip())
    except:
        return await message.answer("⚠️ ID raqamdan iborat bo'lishi kerak!")
        
    u = DB.fetchone("SELECT * FROM users WHERE uid=?", (uid,))
    if not u:
        return await message.answer("❌ Bunday foydalanuvchi topilmadi!")
        
    kb = InlineKeyboardBuilder()
    if u['is_banned']:
        kb.row(InlineKeyboardButton(text="🔓 BANDAN OLISH", callback_data=f"unban_{uid}"))
    else:
        kb.row(InlineKeyboardButton(text="🔒 BAN QILISH", callback_data=f"ban_{uid}"))
    kb.row(InlineKeyboardButton(text="🗑 KODINI O'CHIRISH", callback_data=f"delcode_{uid}"))
    
    text = (
        f"👤 <b>FOYDALANUVCHI PROFILI</b>\n"
        f"{Config.D_LINE}\n"
        f"ID: <code>{u['uid']}</code>\n"
        f"Ism: {html.escape(u['fullname'])}\n"
        f"Username: @{u['username']}\n"
        f"Ball: {u['points']}\n"
        f"Holat: <b>{'🔴 BANNED' if u['is_banned'] else '🟢 ACTIVE'}</b>"
    )
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith(("ban_", "unban_", "delcode_")))
async def user_actions_cb(call: CallbackQuery):
    action, uid = call.data.split("_")
    uid = int(uid)
    
    if action == "ban":
        DB.execute("UPDATE users SET is_banned=1 WHERE uid=?", (uid,))
        await call.answer("Foydalanuvchi bloklandi!", show_alert=True)
    elif action == "unban":
        DB.execute("UPDATE users SET is_banned=0 WHERE uid=?", (uid,))
        await call.answer("Blokdan olindi!", show_alert=True)
    elif action == "delcode":
        DB.execute("DELETE FROM web_codes WHERE uid=?", (uid,))
        await call.answer("Kodi o'chirildi!", show_alert=True)
        
    await call.message.delete()

@dp.message(F.text == Config.BTN_ADM_EXPORT)
async def export_db(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    await message.answer("⏳ <i>Ma'lumotlar eksport qilinmoqda...</i>", parse_mode="HTML")
    
    users = DB.fetchall("SELECT uid, fullname, username, joined_at, points FROM users")
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Full Name', 'Username', 'Joined At', 'Points'])
    for u in users:
        writer.writerow([u['uid'], u['fullname'], u['username'], u['joined_at'], u['points']])
        
    csv_bytes = output.getvalue().encode('utf-8')
    document = BufferedInputFile(csv_bytes, filename=f"users_export_{datetime.now().strftime('%Y%m%d')}.csv")
    
    await message.answer_document(document, caption="🗂 <b>Barcha foydalanuvchilar ro'yxati (CSV)</b>", parse_mode="HTML")


# ==========================================================================================
# ⚙️ 16. KANALLAR VA TIZIM SOZLAMALARI (YANGI)
# ==========================================================================================
@dp.message(F.text == Config.BTN_ADM_CHANNELS)
async def manage_channels(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    channels = DB.fetchall("SELECT * FROM channels")
    kb = InlineKeyboardBuilder()
    
    text = f"📢 <b>MAJBURIY OBUNA KANALLARI</b>\n{Config.S_LINE}\n\n"
    if not channels:
        text += "<i>Hozircha kanallar qo'shilmagan.</i>"
    else:
        for ch in channels:
            text += f"▪️ {ch['channel_name']} ({ch['channel_id']})\n"
            kb.row(InlineKeyboardButton(text=f"🗑 O'chirish: {ch['channel_name']}", callback_data=f"delch_{ch['id']}"))
            
    kb.row(InlineKeyboardButton(text="➕ Yangi Kanal Qo'shish", callback_data="add_channel"))
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "add_channel")
async def add_ch_step1(call: CallbackQuery, state: FSMContext):
    await state.set_state(Form.adm_add_channel_name)
    await call.message.edit_text("✏️ <b>Kanalning chiroyli nomini kiriting:</b>\n<i>(Masalan: 📢 Rasmiy Kanal)</i>", parse_mode="HTML")

@dp.message(Form.adm_add_channel_name)
async def add_ch_step2(message: Message, state: FSMContext):
    await state.update_data(ch_name=message.text)
    await state.set_state(Form.adm_add_channel_id)
    await message.answer("🆔 <b>Kanalning ID yoki Usernameni kiriting:</b>\n<i>(Masalan: @alo_math yoki -100123456)</i>\n⚠️ Diqqat: Bot o'sha kanalda admin bo'lishi shart!", parse_mode="HTML")

@dp.message(Form.adm_add_channel_id)
async def add_ch_step3(message: Message, state: FSMContext):
    data = await state.get_data()
    ch_name = data['ch_name']
    ch_id = message.text.strip()
    
    DB.execute("INSERT INTO channels (channel_id, channel_name) VALUES (?,?)", (ch_id, ch_name))
    await state.clear()
    await message.answer("✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>", parse_mode="HTML")

@dp.callback_query(F.data.startswith("delch_"))
async def del_ch_action(call: CallbackQuery):
    chid = int(call.data.split("_")[1])
    DB.execute("DELETE FROM channels WHERE id=?", (chid,))
    await call.answer("Kanal o'chirildi!", show_alert=True)
    await call.message.delete()

@dp.message(F.text == Config.BTN_ADM_SETTINGS)
async def sys_settings(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    m_mode = DB.get_setting("maintenance")
    kb = InlineKeyboardBuilder()
    if m_mode == "1":
        kb.row(InlineKeyboardButton(text="🟢 NORMAL REJIMGA QAYTARISH", callback_data="toggle_m_0"))
    else:
        kb.row(InlineKeyboardButton(text="🔴 MAINTENANCE YOQISH", callback_data="toggle_m_1"))
        
    text = (
        f"⚙️ <b>TIZIM SOZLAMALARI</b>\n{Config.S_LINE}\n"
        f"Joriy rejim: <b>{'🔴 TEXNIK ISHLAR (Maintenance)' if m_mode == '1' else '🟢 NORMAL'}</b>\n\n"
        f"<i>Texnik ishlar rejimi yoqilsa, oddiy foydalanuvchilar botdan foydalana olmaydi.</i>"
    )
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("toggle_m_"))
async def toggle_maintenance(call: CallbackQuery):
    val = call.data.split("_")[2]
    DB.set_setting("maintenance", val)
    await call.answer("Rejim o'zgartirildi!", show_alert=True)
    await call.message.delete()


# ==========================================================================================
# 🔐 17. ADMIN - FEEDBACKS VA SECURITY (YANGI)
# ==========================================================================================
@dp.message(F.text == Config.BTN_ADM_FEEDBACKS)
async def view_feedbacks(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    feedbacks = DB.fetchall("SELECT f.*, u.fullname FROM feedbacks f JOIN users u ON f.uid = u.uid ORDER BY fid DESC LIMIT 10")
    if not feedbacks:
        return await message.answer("📭 Fikrlar mavjud emas.")
        
    text = f"⭐ <b>OXIRGI 10 TA FIKR-MULOHAZA</b>\n{Config.D_LINE}\n"
    for f in feedbacks:
        stars_str = "⭐" * f['stars']
        text += f"👤 {html.escape(f['fullname'])} | {stars_str}\n💬 <i>{html.escape(f['comment'])}</i>\n📅 {format_dt(f['created_at'])}\n{Config.S_LINE}\n"
        
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == Config.BTN_ADM_SECURITY)
async def security_menu(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⚠️ BARCHA KODLARNI BEKOR QILISH", callback_data="wipe_all_codes"))
    
    text = (
        f"🔐 <b>XAVFSIZLIK MARKAZI</b>\n{Config.S_LINE}\n"
        f"Agar tizimga xujum uyushtirilsa yoki barcha foydalanuvchilarni saytdan chiqarib yuborish kerak bo'lsa, "
        f"ushbu tugma orqali barcha faol veb-kodlarni bekor qilishingiz mumkin."
    )
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "wipe_all_codes")
async def wipe_codes(call: CallbackQuery):
    DB.execute("DELETE FROM web_codes")
    await call.answer("✅ Barcha kodlar muvaffaqiyatli o'chirildi!", show_alert=True)
    await call.message.delete()


# ==========================================================================================
# 💬 18. ADMIN - SUPPORT JAVOB BERISH
# ==========================================================================================
@dp.callback_query(F.data.startswith("admreply_"))
async def support_reply_start(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    uid = int(parts[1])
    mid = int(parts[2])
    
    await state.update_data(reply_uid=uid, reply_mid=mid)
    await state.set_state(Form.adm_reply)
    
    await call.message.answer(f"📝 <b>Foydalanuvchiga (ID: {uid}) javob matnini kiriting:</b>", reply_markup=Keyboards.just_back(), parse_mode="HTML")
    await call.answer()

@dp.message(Form.adm_reply)
async def support_reply_send(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != Config.ADMIN_ID: return
    
    data = await state.get_data()
    uid = data['reply_uid']
    mid = data['reply_mid']
    reply_text = message.text or ""
    
    u = DB.fetchone("SELECT notifications FROM users WHERE uid=?", (uid,))
    
    user_msg = (
        f"📩 <b>ADMINISTRATSIYADAN JAVOB (Murojaat #{mid})</b>\n"
        f"{Config.D_LINE}\n\n"
        f"<i>{html.escape(reply_text)}</i>\n\n"
        f"{Config.S_LINE}\n"
        f"Hurmat bilan, Tizim Ma'muriyati 👑"
    )
    
    try:
        if u and u['notifications'] == 1:
            await bot.send_message(uid, user_msg, parse_mode="HTML")
        DB.execute("UPDATE support_messages SET is_replied=1 WHERE mid=?", (mid,))
        await message.answer("✅ <b>Javob yetkazildi!</b>", reply_markup=Keyboards.admin_menu(), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik: foydalanuvchi botni bloklagan bo'lishi mumkin.\n`{str(e)}`", parse_mode="HTML")
        
    await state.clear()


# ==========================================================================================
# 🌐 19. INTEGRATSIYALASHGAN API WEB PORTI (KUCHAYTIRILGAN)
# ==========================================================================================
async def api_login(request: web.Request):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    
    try:
        data = await request.json()
        entered_code = data.get("student_id", "").strip()
        client_ip = request.remote # IP manzilini olish
        
        web_user = DB.fetchone("SELECT * FROM web_codes WHERE code=?", (entered_code,))
        
        if web_user:
            uid = web_user["uid"]
            user = DB.fetchone("SELECT * FROM users WHERE uid=?", (uid,))
            
            if user:
                if user['is_banned']:
                    # Tarixga yozish (Muvaffaqiyatsiz)
                    DB.execute("INSERT INTO login_history (uid, ip_address, login_time, status) VALUES (?,?,?,?)", (uid, client_ip, datetime.now().isoformat(), 'banned'))
                    return web.json_response({"success": False, "error": "Hisobingiz bloklangan!"}, status=403, headers={'Access-Control-Allow-Origin': '*'})
                
                # Tarixga yozish (Muvaffaqiyatli)
                DB.execute("INSERT INTO login_history (uid, ip_address, login_time, status) VALUES (?,?,?,?)", (uid, client_ip, datetime.now().isoformat(), 'success'))
                
                return web.json_response({
                    "success": True, 
                    "name": user["fullname"], 
                    "uid": user["uid"], 
                    "role": "admin" if user["uid"] == Config.ADMIN_ID else "user",
                    "points": user["points"]
                }, headers={'Access-Control-Allow-Origin': '*'})
                
        return web.json_response({
            "success": False, 
            "error": "Tizim kodi noto'g'ri yoki yaroqsiz! Bot orqali yangi kod yarating."
        }, status=401, headers={'Access-Control-Allow-Origin': '*'})

    except Exception as e:
        logger.error(f"API Xatolik: {e}")
        return web.json_response({"success": False, "error": "Ichki server xatoligi!"}, status=500, headers={'Access-Control-Allow-Origin': '*'})

async def handle_root(request: web.Request):
    return web.Response(text="💎 A'lo Ta'lim Premium API Integratsiyasi 100% Faol holatda. Version: 5.5 PRO")


# ==========================================================================================
# 🚀 20. SERVER VA BOT POLLING START
# ==========================================================================================
async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_options("/api/login", api_login)
    app.router.add_post("/api/login", api_login)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", Config.PORT)
    await site.start()
    logger.info(f"🌐 Veb server {Config.PORT}-portda ishga tushdi.")

async def main():
    try:
        # DB ni ishga tushirish
        DB.setup()
        
        # Web serverni alohida task qilib ishga tushirish
        asyncio.create_task(start_web_server())

        # Bot buyruqlarini sozlash
        await bot.set_my_commands([
            BotCommand(command="start", description="🏠 Tizimni qayta ishga tushirish")
        ])
        
        logger.info("💎 A'LO TA'LIM PREMIUM TIZIMI ISHGA TUSHDI...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi!")
