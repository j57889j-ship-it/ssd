import asyncio
import logging
import os
import sqlite3
import html
import random
import secrets
from datetime import datetime, timedelta
from typing import Final, Any, Optional

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# ==========================================================================================
# 💎 PREMIUM KONFIGURATSIYA VA ASSETLAR
# ==========================================================================================
class Assets:
    TOKEN: Final[str] = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: Final[int] = int(os.getenv("ADMIN_ID", "0") or "0")
    DB_NAME: Final[str] = os.getenv("DB_NAME", "database.db")
    # Tizimning veb-sayt manzili (Magic Link yaratish uchun)
    WEB_URL: Final[str] = os.getenv("WEB_URL", "https://alotalim.uz")

    D_LINE = "<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>"
    S_LINE = "<b>────────────────────</b>"

    # Tugma nomlari
    ICO_WEB = "🔑 Saytga kirish kodi / Havola"
    ICO_HELP = "🆘 Adminga xabar yuborish"
    ICO_PROF = "👤 Shaxsiy Profil"
    ICO_ADM = "🛠 Admin Boshqaruvi"
    ICO_BACK = "⬅️ Bekor qilish / Orqaga"
    ICO_HOME = "🏠 Asosiy Menyu"

    # Admin tugmalari
    ADM_STATS = "📊 Statistika va Foydalanuvchilar"
    ADM_MANAGE = "🚫 Foydalanuvchini bloklash / Ochish"
    ADM_BROADCAST = "📢 Barchaga Xabar Yuborish"

    @staticmethod
    def progress_bar(perc: float) -> str:
        full = max(0, min(10, int(perc // 10)))
        empty = 10 - full
        return "🟢" * full + "⚪" * empty


logging.basicConfig(level=logging.INFO)
bot = Bot(token=Assets.TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==========================================================================================
# 🗄 DATABASE ENGINE (KUCHAYTIRILGAN STRUKTURA)
# ==========================================================================================
class DB:
    @staticmethod
    def connect():
        conn = sqlite3.connect(Assets.DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def setup(cls):
        with cls.connect() as conn:
            c = conn.cursor()
            # Foydalanuvchilar jadvali (status qo'shildi: active, banned)
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid INTEGER PRIMARY KEY,
                    fullname TEXT,
                    username TEXT,
                    joined_at TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
            """)
            # Veb sayt uchun bir martalik OTP va Magic Link kodlari jadvali
            c.execute("""
                CREATE TABLE IF NOT EXISTS web_codes (
                    uid INTEGER PRIMARY KEY,
                    code TEXT UNIQUE,
                    magic_token TEXT UNIQUE,
                    expires_at TIMESTAMP
                )
            """)
            # Faol seanslarni kuzatish jadvali
            c.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    uid INTEGER,
                    ip TEXT,
                    browser TEXT,
                    created_at TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
            """)
            conn.commit()

    @classmethod
    def run(cls, sql: str, params: tuple = (), fetch: str = "none") -> Any:
        with cls.connect() as conn:
            c = conn.cursor()
            c.execute(sql, params)
            if fetch == "all":
                return [dict(r) for r in c.fetchall()]
            if fetch == "one":
                row = c.fetchone()
                return dict(row) if row else None
            conn.commit()
            return c.lastrowid


# ==========================================================================================
# 🧠 STATES (SATE_MACHINE)
# ==========================================================================================
class Form(StatesGroup):
    reg = State()                    # Ro'yxatdan o'tish
    support_msg = State()            # Murojaat yozish
    support_confirm = State()        # Murojaatni tasdiqlash

    # Admin holatlari
    adm_reply = State()              # Adminga javob yozish
    adm_broadcast_msg = State()      # Broadcast xabar kiritish
    adm_broadcast_confirm = State()  # Broadcast tasdiqlash
    adm_user_manage = State()        # Foydalanuvchini bloklash uchun ID so'rash


# ==========================================================================================
# 🎨 DESIGN VA UI PANEL
# ==========================================================================================
class UI:
    @staticmethod
    def main_menu(user_id: int):
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=Assets.ICO_WEB))
        b.row(KeyboardButton(text=Assets.ICO_HELP), KeyboardButton(text=Assets.ICO_PROF))
        if user_id == Assets.ADMIN_ID:
            b.row(KeyboardButton(text=Assets.ICO_ADM))
        b.adjust(1, 2, 1)
        return b.as_markup(resize_keyboard=True)
        
    @staticmethod
    def admin_menu():
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=Assets.ADM_STATS), KeyboardButton(text=Assets.ADM_MANAGE))
        b.row(KeyboardButton(text=Assets.ADM_BROADCAST))
        b.row(KeyboardButton(text=Assets.ICO_HOME))
        b.adjust(2, 1, 1)
        return b.as_markup(resize_keyboard=True)

    @staticmethod
    def back_btn():
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=Assets.ICO_BACK)]],
            resize_keyboard=True
        )


# ==========================================================================================
# RO'YXATDAN O'TISH VA START (MIDDLEWARE SIFATIDA BLOKLANGANLARNI TEKSHIRISH)
# ==========================================================================================
async def check_and_get_user(user_id: int) -> Optional[dict]:
    return DB.run("SELECT * FROM users WHERE uid=?", (user_id,), fetch="one")

async def process_user_entry(message: Message, state: FSMContext, user_id: int, user_firstname: str):
    DB.setup()
    user = await check_and_get_user(user_id)

    if user and user['status'] == 'banned':
        await message.answer(
            f"🚫 <b>KIRISH TAQIQLANGAN!</b>\n{Assets.D_LINE}\n"
            f"Siz tizim qoidalarini buzganingiz sababli ma'murlar tomonidan bloklangansiz.\n"
            f"Murojaat uchun administratorga murojaat qiling.", 
            parse_mode="HTML"
        )
        return

    if not user:
        await state.set_state(Form.reg)
        text = (
            f"🌟 <b>A'LO TA'LIM PLATFORMASI</b>\n"
            f"{Assets.D_LINE}\n\n"
            f"👋 Assalomu alaykum, <b>{html.escape(user_firstname)}</b>!\n"
            f"Xavfsiz kirish va boshqaruv botiga xush kelibsiz.\n\n"
            f"✍️ <i>Botdan foydalanish uchun ism va familiyangizni kiriting:</i>\n\n"
            f"💡 <b>Namuna:</b> <i>Asadbek Karimov</i>"
        )
        await message.answer(text, parse_mode="HTML")
    else:
        dashboard = (
            f"👑 <b>ASOSIY TIZIM PANELI</b>\n"
            f"{Assets.D_LINE}\n\n"
            f"👤 Foydalanuvchi: <b>{html.escape(user['fullname'])}</b>\n"
            f"🎖 Status: <b>Faol Foydalanuvchi</b>\n\n"
            f"📅 Bugun: <b>{datetime.now().strftime('%d.%m.%Y')}</b>\n"
            f"🕒 Vaqt: <b>{datetime.now().strftime('%H:%M')}</b>\n\n"
            f"👇 <i>Kerakli bo'limni tanlang:</i>"
        )
        await message.answer(dashboard, reply_markup=UI.main_menu(user_id), parse_mode="HTML")


@dp.message(or_f(Command("start"), F.text == Assets.ICO_HOME, F.text == Assets.ICO_BACK))
async def global_reset(message: Message, state: FSMContext):
    await state.clear()
    await process_user_entry(message, state, message.from_user.id, message.from_user.first_name)


@dp.message(Form.reg)
async def registration_finish(message: Message, state: FSMContext):
    fullname = message.text.strip()
    if len(fullname) < 4 or " " not in fullname:
        return await message.answer(
            "⚠️ <b>Xatolik!</b> Iltimos ism va familiyangizni to'liq kiriting (kamida 2 ta so'z).\n"
            "Misol: <i>Asadbek Karimov</i>", 
            parse_mode="HTML"
        )

    DB.run(
        "INSERT OR REPLACE INTO users (uid, fullname, username, joined_at, status) VALUES (?,?,?,?, 'active')",
        (message.from_user.id, fullname, message.from_user.username, datetime.now().isoformat())
    )
    
    success_text = (
        f"🎉 <b>Muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"Hurmatli <b>{html.escape(fullname)}</b>, tizimga muvaffaqiyatli ulandingiz! 🚀\n\n"
        f"👇 <i>Quyidagi menyudan foydalanishingiz mumkin:</i>"
    )
    
    await message.answer(success_text, parse_mode="HTML", reply_markup=UI.main_menu(message.from_user.id))
    await state.clear()


# ==========================================================================================
# ⏱ DYNAMIK OTP VA MAGIC LINK GENERATORI (AMAL QILISHI 5 DAQIQA)
# ==========================================================================================
@dp.message(F.text == Assets.ICO_WEB)
async def generate_web_login_credentials(message: Message):
    user_id = message.from_user.id
    user = await check_and_get_user(user_id)
    if user and user['status'] == 'banned':
        return await message.answer("⚠️ Siz bloklangansiz. Tizimdan foydalanish taqiqlanadi.")

    # Yangi 6-xonali noyob OTP yaratish
    while True:
        code = str(random.randint(100000, 999999))
        check = DB.run("SELECT uid FROM web_codes WHERE code=?", (code,), fetch="one")
        if not check:
            break
            
    # Bir marta bosib kirish uchun xavfsiz Magic Token yaratish
    magic_token = secrets.token_url_safe(32)
    expires_at = (datetime.now() + timedelta(minutes=5)).isoformat()
    
    # Ma'lumotlarni saqlash (eskisini o'chirib, yangisini yozadi)
    DB.run(
        "INSERT OR REPLACE INTO web_codes (uid, code, magic_token, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, code, magic_token, expires_at)
    )
    
    # Havolani shakllantirish
    magic_link = f"{Assets.WEB_URL}/login?token={magic_token}"
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔗 Saytga bir bosishda kirish (Magic Link)", url=magic_link))
    kb.row(InlineKeyboardButton(text="🔄 Yangi kod olish", callback_data="generate_new_otp"))
    
    text = (
        f"🔑 <b>VEB-SAYTGA KAVFSIZ KIRISH</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"⏳ Kirish kodi va havolaning amal qilish muddati: <b>5 daqiqa</b>\n"
        f"🕒 Tugash vaqti: <b>{(datetime.now() + timedelta(minutes=5)).strftime('%H:%M:%S')}</b>\n\n"
        f"🔹 <b>Bir martalik kirish kodi:</b>\n"
        f"👉 <pre>{code}</pre> 👈\n\n"
        f"🔹 <b>Tezkor kirish havolasi:</b>\n"
        f"<i>Ushbu tugmani bosish orqali parolsiz va kodsiz darhol profilingizga kira olasiz:</i>"
    )
    
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "generate_new_otp")
async def generate_new_otp_callback(call: CallbackQuery):
    user_id = call.from_user.id
    user = await check_and_get_user(user_id)
    if user and user['status'] == 'banned':
        return await call.answer("⚠️ Siz bloklangansiz!", show_alert=True)
        
    while True:
        code = str(random.randint(100000, 999999))
        check = DB.run("SELECT uid FROM web_codes WHERE code=?", (code,), fetch="one")
        if not check:
            break
            
    magic_token = secrets.token_url_safe(32)
    expires_at = (datetime.now() + timedelta(minutes=5)).isoformat()
    
    DB.run(
        "INSERT OR REPLACE INTO web_codes (uid, code, magic_token, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, code, magic_token, expires_at)
    )
    
    magic_link = f"{Assets.WEB_URL}/login?token={magic_token}"
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔗 Saytga bir bosishda kirish (Magic Link)", url=magic_link))
    kb.row(InlineKeyboardButton(text="🔄 Yangi kod olish", callback_data="generate_new_otp"))
    
    text = (
        f"🔑 <b>KOD VA HAVOLA YANGILANDI</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"⏳ Amal qilish muddati: <b>5 daqiqa</b>\n"
        f"🕒 Tugash vaqti: <b>{(datetime.now() + timedelta(minutes=5)).strftime('%H:%M:%S')}</b>\n\n"
        f"🔹 <b>Yangi bir martalik kod:</b>\n"
        f"👉 <pre>{code}</pre> 👈\n\n"
        f"<i>Eski kod va havola o'z kuchini yo'qotdi.</i>"
    )
    
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer("Yangi kod generatsiya qilindi!")


# ==========================================================================================
# 💻 SHAXSIY PROFIL & FAOL SEANSLARNI BOSHQARISH (REMOTE LOGOUT)
# ==========================================================================================
@dp.message(F.text == Assets.ICO_PROF)
async def user_profile(message: Message):
    user_id = message.from_user.id
    user = await check_and_get_user(user_id)
    
    if not user:
        return await message.answer("⚠️ Profil topilmadi. /start buyrug'ini bering.")

    # Faol seanslarni sanash
    active_sessions = DB.run("SELECT COUNT(*) as cnt FROM sessions WHERE uid=? AND status='active'", (user_id,), fetch="one")["cnt"]

    p_text = (
        f"👤 <b>SHAXSIY PROFIL MA'LUMOTLARI</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"📝 Ism-familiya: <b>{html.escape(user['fullname'])}</b>\n"
        f"🆔 Telegram ID: <code>{user['uid']}</code>\n"
        f"🌐 Telegram: @{html.escape(message.from_user.username or 'yo\'q')}\n"
        f"📅 Ro'yxatdan o'tilgan: <b>{str(user['joined_at'])[:16]}</b>\n\n"
        f"💻 Saytdagi faol seanslaringiz: <b>{active_sessions} ta</b>\n"
        f"{Assets.S_LINE}\n"
        f"<i>Quyidagi tugma orqali profilingizga kirib turgan qurilmalarni ko'rishingiz va ularni masofadan o'chirishingiz mumkin:</i>"
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💻 Faol seanslarni boshqarish", callback_data="manage_sessions"))
    await message.answer(p_text, reply_markup=kb.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "manage_sessions")
@dp.callback_query(F.data.startswith("terminate_"))
async def session_management_callback(call: CallbackQuery):
    user_id = call.from_user.id
    
    # Agar seansni o'chirish so'ralgan bo'lsa
    if call.data.startswith("terminate_"):
        session_id = call.data.split("_", 1)[1]
        DB.run("UPDATE sessions SET status='terminated' WHERE session_id=? AND uid=?", (session_id, user_id))
        await call.answer("💻 Tanlangan qurilma tizimdan o'chirildi!", show_alert=True)
    
    # Faol seanslar ro'yxatini yuklash
    sessions = DB.run("SELECT * FROM sessions WHERE uid=? AND status='active' ORDER BY created_at DESC", (user_id,), fetch="all")
    
    kb = InlineKeyboardBuilder()
    if not sessions:
        text = (
            f"💻 <b>FAOL SEANSLAR RO'YXATI</b>\n"
            f"{Assets.S_LINE}\n\n"
            f"<i>Sizning profilingiz saytda hech qanday qurilmada ochiq emas.</i>"
        )
    else:
        text = (
            f"💻 <b>SIZNING FAOL SEANSLARINGIZ</b>\n"
            f"{Assets.S_LINE}\n"
            f"Profilingiz ochiq bo'lgan barcha qurilmalar ro'yxati. Agar shubhali qurilmani ko'rsangiz, uni darhol o'chiring:\n\n"
        )
        for s in sessions:
            text += (
                f"🖥 Qurilma: {html.escape(s['browser'])}\n"
                f"🌐 IP Manzil: <code>{html.escape(s['ip'])}</code>\n"
                f"🕒 Kirilgan vaqt: {str(s['created_at'])[11:16]} ({str(s['created_at'])[8:10]}.{str(s['created_at'])[5:7]})\n"
                f"{Assets.S_LINE}\n"
            )
            kb.row(InlineKeyboardButton(
                text=f"❌ Chiqish ({s['ip']})", 
                callback_data=f"terminate_{s['session_id']}"
            ))
            
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_profile"))
    kb.adjust(1)
    
    # Message edit qilish orqali UI yangilanadi
    try:
        await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await call.answer()


@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile_callback(call: CallbackQuery):
    user_id = call.from_user.id
    user = await check_and_get_user(user_id)
    if not user:
        return
        
    active_sessions = DB.run("SELECT COUNT(*) as cnt FROM sessions WHERE uid=? AND status='active'", (user_id,), fetch="one")["cnt"]
    p_text = (
        f"👤 <b>SHAXSIY PROFIL MA'LUMOTLARI</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"📝 Ism-familiya: <b>{html.escape(user['fullname'])}</b>\n"
        f"🆔 Telegram ID: <code>{user['uid']}</code>\n"
        f"📅 Ro'yxatdan o'tilgan: <b>{str(user['joined_at'])[:16]}</b>\n\n"
        f"💻 Saytdagi faol seanslaringiz: <b>{active_sessions} ta</b>\n"
        f"{Assets.S_LINE}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💻 Faol seanslarni boshqarish", callback_data="manage_sessions"))
    
    await call.message.edit_text(p_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


# ==========================================================================================
# 🚨 ALERTLAR VA BLOCK BUTTONS (REAL-TIME SECTOR)
# ==========================================================================================
@dp.callback_query(F.data.startswith("emergency_block_"))
async def emergency_session_block(call: CallbackQuery):
    session_id = call.data.split("_", 2)[2]
    user_id = call.from_user.id
    
    # Seansni darhol tugatish
    DB.run("UPDATE sessions SET status='terminated' WHERE session_id=? AND uid=?", (session_id, user_id))
    
    await call.message.edit_text(
        f"🚨 <b>FAVQULODDA BLOKLANDI!</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"Ushbu shubhali seans muvaffaqiyatli ravishda tizimdan uzildi va kirish yopildi.\n\n"
        f"🔒 <i>Profil xavfsizligini ta'minlash uchun xavfsizlik choralarini ko'ring.</i>",
        parse_
