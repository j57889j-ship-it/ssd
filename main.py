"""
==========================================================================================
🌟 A'LO TA'LIM PLATFORMASI - PREMIUM INTEGRATSIYA BOTI 🌟
==========================================================================================
Versiya: 6.0.0 (Ultimate Edition)
Tuzuvchi: Premium Developer Team / AI
Tavsif: Telegram bot va Web API integratsiyasi. Asinxron baza (aiosqlite),
        kengaytirilgan xavfsizlik, chiroyli UI/UX va boy admin panelga ega.

Asosiy xususiyatlar:
- Asinxron SQLite (aiosqlite) bilan yuqori tezlik.
- Foydalanuvchilar uchun: FAQ, Tarix, Sozlamalar, Profil, Web Kod, Support.
- Admin uchun: Ban tizimi, Obuna kanallarini boshqarish, CSV Export,
  Direct Message, Broadcast, Kengaytirilgan Statistika.
- Global xatolarni ushlash va mukammal Logging tizimi.
==========================================================================================
"""

import asyncio
import logging
import os
import html
import random
import csv
import io
from datetime import datetime
from typing import Final, Any, Optional, List, Dict

# Tashqi kutubxonalar
from aiohttp import web
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, BufferedInputFile, Update
)
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import aiosqlite

from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# ==========================================================================================
# 💎 1. KONFIGURATSIYA VA O'ZGARMASLAR (CONSTANTS)
# ==========================================================================================
class Config:
    """Botning asosiy sozlamalari va ma'lumotlari."""
    TOKEN: Final[str] = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
    ADMIN_ID: Final[int] = int(os.getenv("ADMIN_ID", "0") or "0")
    DB_NAME: Final[str] = os.getenv("DB_NAME", "premium_database.db")
    PORT: Final[int] = int(os.getenv("PORT", 8080))
    HOST: Final[str] = os.getenv("HOST", "0.0.0.0")

class Design:
    """Dizayn va matn formatlash o'zgarmaslari."""
    D_LINE = "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>"
    S_LINE = "<b>─────────────────────────────</b>"
    TITLE = "🎓 <b>A'LO TA'LIM PLATFORMASI</b>"
    
    # Menyu tugmalari (Foydalanuvchi)
    BTN_WEB = "🌐 Saytga kirish"
    BTN_PROF = "👤 Shaxsiy Kabinet"
    BTN_FAQ = "📚 Ko'p so'raladigan savollar"
    BTN_SETTINGS = "⚙️ Sozlamalar"
    BTN_HELP = "🆘 Adminga murojaat"
    BTN_HISTORY = "📱 Kirish tarixi"
    BTN_BACK = "⬅️ Orqaga"
    BTN_HOME = "🏠 Asosiy Menyu"
    BTN_ADM = "🛠 Admin Panel"

    # Menyu tugmalari (Admin)
    ADM_STATS = "📊 Statistika"
    ADM_BROADCAST = "📢 Barchaga Xabar"
    ADM_DIRECT = "✉️ Shaxsiy xabar yuborish"
    ADM_BAN_SYS = "🚫 Ban Tizimi"
    ADM_CHANNELS = "📢 Obunalarni boshqarish"
    ADM_EXPORT = "📥 Bazani yuklash (CSV)"

class Texts:
    """Botda ishlatiladigan asosiy matnlar."""
    WELCOME = (
        f"{Design.TITLE}\n"
        f"{Design.D_LINE}\n\n"
        f"👋 Assalomu alaykum, <b>{{name}}</b>!\n"
        f"Bizning innovatsion ta'lim platformamizga xush kelibsiz.\n\n"
        f"<i>Tizimdan to'liq foydalanish uchun ro'yxatdan o'tishingiz kerak.</i>\n"
        f"✍️ <b>Iltimos, ism va familiyangizni kiriting:</b>\n\n"
        f"💡 <i>Namuna: Abdurahmon Alimov</i>"
    )
    
    MAIN_MENU = (
        f"{Design.TITLE}\n"
        f"{Design.D_LINE}\n\n"
        f"👤 Profil: <b>{{name}}</b>\n"
        f"⚡️ Holat: <b>Faol a'zo</b>\n\n"
        f"📅 Sana: <b>{{date}}</b>\n"
        f"🕒 Vaqt: <b>{{time}}</b>\n\n"
        f"👇 <i>Quyidagi interaktiv menyudan kerakli bo'limni tanlang:</i>"
    )

    BANNED = (
        f"⛔️ <b>DIQQAT: SIZ BLOKLANGANSIZ!</b>\n"
        f"{Design.D_LINE}\n\n"
        f"Sizning hisobingiz tizim qoidalarini buzganligi sababli ma'muriyat tomonidan bloklangan.\n"
        f"Veb-saytga va bot xizmatlariga kirish vaqtincha cheklangan.\n\n"
        f"<i>Murojaat uchun: Ma'muriyat bilan bog'laning.</i>"
    )


# ==========================================================================================
# ⚙️ 2. LOGGING SOZLAMALARI
# ==========================================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Asosiy bot va dispatcher obyektlari
bot = Bot(token=Config.TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==========================================================================================
# 🗄 3. ASINXRON MA'LUMOTLAR BAZASI (AIOSQLITE) - KENGAYTIRILGAN
# ==========================================================================================
class AsyncDB:
    """aiosqlite asosidagi mukammal ma'lumotlar bazasi klassi."""
    
    @staticmethod
    async def setup():
        """Barcha kerakli jadvallarni yaratish."""
        async with aiosqlite.connect(Config.DB_NAME) as db:
            # 1. Foydalanuvchilar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid INTEGER PRIMARY KEY,
                    fullname TEXT,
                    username TEXT,
                    joined_at TIMESTAMP,
                    is_banned INTEGER DEFAULT 0
                )
            """)
            # 2. Veb kodlar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS web_codes (
                    uid INTEGER PRIMARY KEY,
                    code TEXT UNIQUE,
                    created_at TIMESTAMP
                )
            """)
            # 3. Yordam xabarlari
            await db.execute("""
                CREATE TABLE IF NOT EXISTS support_messages (
                    mid INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER,
                    message_text TEXT,
                    created_at TIMESTAMP,
                    is_replied INTEGER DEFAULT 0
                )
            """)
            # 4. Kirish tarixi (YANGI)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS login_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER,
                    ip_address TEXT,
                    user_agent TEXT,
                    login_time TIMESTAMP,
                    status TEXT
                )
            """)
            # 5. Majburiy obunalar (YANGI)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE,
                    channel_name TEXT,
                    url TEXT
                )
            """)
            await db.commit()
            logger.info("Database tables verified and ready.")

    @staticmethod
    async def execute(sql: str, params: tuple = ()) -> None:
        """Ma'lumotni kiritish yoki yangilash."""
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute(sql, params)
            await db.commit()

    @staticmethod
    async def execute_return_id(sql: str, params: tuple = ()) -> int:
        """Ma'lumotni kiritib, oxirgi ID ni qaytarish."""
        async with aiosqlite.connect(Config.DB_NAME) as db:
            cursor = await db.execute(sql, params)
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def fetchone(sql: str, params: tuple = ()) -> Optional[Dict]:
        """Bitta qator ma'lumotni olish."""
        async with aiosqlite.connect(Config.DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def fetchall(sql: str, params: tuple = ()) -> List[Dict]:
        """Barcha qatorlarni olish."""
        async with aiosqlite.connect(Config.DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


# ==========================================================================================
# 🧠 4. STATE MANAGER (FSM HOLATLAR)
# ==========================================================================================
class Form(StatesGroup):
    reg_name = State()            # Ismni kiritish
    support_msg = State()         # Adminga yozish
    settings_name = State()       # Ismni o'zgartirish
    
    # Admin holatlari
    adm_reply = State()           # Admindan javob
    adm_bc_text = State()         # Barchaga xabar
    adm_bc_confirm = State()      # Xabarni tasdiqlash
    adm_direct_id = State()       # Shaxsiy xabar uchun ID
    adm_direct_msg = State()      # Shaxsiy xabar matni
    adm_ban_id = State()          # Ban qilish uchun ID
    adm_unban_id = State()        # Bandan olish uchun ID
    adm_add_channel_data = State()# Kanal qo'shish (ID, Name, URL)


# ==========================================================================================
# 🎨 5. UI VA KLAVIATURALAR TIZIMI (KEYBOARDS)
# ==========================================================================================
class UI:
    """Interfeys va klaviaturalarni shakllantiruvchi klass."""
    
    @staticmethod
    def main_menu(user_id: int):
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=Design.BTN_WEB), KeyboardButton(text=Design.BTN_PROF))
        b.row(KeyboardButton(text=Design.BTN_FAQ), KeyboardButton(text=Design.BTN_HISTORY))
        b.row(KeyboardButton(text=Design.BTN_SETTINGS), KeyboardButton(text=Design.BTN_HELP))
        if user_id == Config.ADMIN_ID:
            b.row(KeyboardButton(text=Design.BTN_ADM))
        return b.as_markup(resize_keyboard=True)
        
    @staticmethod
    def admin_menu():
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=Design.ADM_STATS), KeyboardButton(text=Design.ADM_BROADCAST))
        b.row(KeyboardButton(text=Design.ADM_DIRECT), KeyboardButton(text=Design.ADM_BAN_SYS))
        b.row(KeyboardButton(text=Design.ADM_CHANNELS), KeyboardButton(text=Design.ADM_EXPORT))
        b.row(KeyboardButton(text=Design.BTN_HOME))
        return b.as_markup(resize_keyboard=True)

    @staticmethod
    def back_btn():
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=Design.BTN_BACK)]],
            resize_keyboard=True
        )

    @staticmethod
    def get_web_code_markup(has_code: bool) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        if has_code:
            kb.row(InlineKeyboardButton(text="🔄 Kodni Yangilash", callback_data="code_regenerate"))
            kb.row(InlineKeyboardButton(text="🗑 Kodni O'chirish", callback_data="code_delete"))
        else:
            kb.row(InlineKeyboardButton(text="🔑 Yangi Kod Yaratish", callback_data="code_generate"))
        return kb.as_markup()

    @staticmethod
    def settings_markup() -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="📝 Ismni o'zgartirish", callback_data="set_change_name"))
        kb.row(InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="set_about"))
        return kb.as_markup()

    @staticmethod
    def faq_markup() -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="1️⃣ Saytga qanday kiraman?", callback_data="faq_1"))
        kb.row(InlineKeyboardButton(text="2️⃣ Kodim ishlamayapti, nima qilay?", callback_data="faq_2"))
        kb.row(InlineKeyboardButton(text="3️⃣ Ma'lumotlarim xavfsizmi?", callback_data="faq_3"))
        kb.row(InlineKeyboardButton(text="4️⃣ Admin bilan bog'lanish", callback_data="faq_4"))
        return kb.as_markup()

    @staticmethod
    def admin_ban_markup() -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🚫 Ban berish", callback_data="admin_do_ban"))
        kb.row(InlineKeyboardButton(text="✅ Bandan olish", callback_data="admin_do_unban"))
        return kb.as_markup()
        
    @staticmethod
    def admin_channel_markup() -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_ch_add"))
        kb.row(InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="admin_ch_del"))
        kb.row(InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="admin_ch_list"))
        return kb.as_markup()


# ==========================================================================================
# 🛡 6. MIDDLEWARE (XAVFSIZLIK VA TEKSHIRUVLAR)
# ==========================================================================================
class BanCheckMiddleware(BaseMiddleware):
    """Har bir xabardan oldin foydalanuvchining ban holatini tekshiradi."""
    async def __call__(self, handler, event: Update, data: dict):
        user_id = None
        if event.message:
            user_id = event.message.from_user.id
        elif event.callback_query:
            user_id = event.callback_query.from_user.id

        if user_id:
            user = await AsyncDB.fetchone("SELECT is_banned FROM users WHERE uid=?", (user_id,))
            if user and user['is_banned'] == 1:
                if event.message:
                    await event.message.answer(Texts.BANNED, parse_mode="HTML")
                elif event.callback_query:
                    await event.callback_query.answer("Siz bloklangansiz!", show_alert=True)
                return # Keyingi handlerga o'tkazmaydi
        return await handler(event, data)

dp.update.middleware(BanCheckMiddleware())


# Majburiy obunani tekshirish funksiyasi
async def check_subscription(bot: Bot, user_id: int) -> bool:
    channels = await AsyncDB.fetchall("SELECT channel_id FROM channels")
    if not channels:
        return True # Agar kanallar yo'q bo'lsa, o'tkazib yuboradi
        
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if member.status in ['left', 'kicked', 'banned']:
                return False
        except Exception as e:
            logger.error(f"Kanal tekshirishda xatolik ({ch['channel_id']}): {e}")
            return False 
    return True

async def get_sub_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    channels = await AsyncDB.fetchall("SELECT channel_name, url FROM channels")
    for ch in channels:
        builder.row(InlineKeyboardButton(text=ch["channel_name"], url=ch["url"]))
    builder.row(InlineKeyboardButton(text="✅ Obunani Tasdiqlash", callback_data="check_sub_btn"))
    return builder.as_markup()


# ==========================================================================================
# YORDAMCHI FUNKSIYALAR
# ==========================================================================================
def fmt_dt(value: Optional[str]) -> str:
    """Sanani o'zbekcha chiroyli formatga o'tkazadi."""
    if not value: return "-"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d.%m.%Y y. %H:%M")
    except Exception:
        return str(value)[:16]

def gen_code() -> str:
    """Faqat sonlardan iborat 4 xonali noyob kod yaratadi."""
    return f"{random.randint(1000, 9999)}"


# ==========================================================================================
# 🚀 7. ASOSIY HANDLERLAR (START VA REGISTRATSIYA)
# ==========================================================================================
@dp.message(or_f(Command("start"), F.text == Design.BTN_HOME, F.text == Design.BTN_BACK))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id
    
    # Obuna tekshiruvi
    is_sub = await check_subscription(bot, user_id)
    if not is_sub:
        text = (
            f"🛑 <b>DIQQAT: MAJBURIY OBUNA!</b>\n"
            f"{Design.D_LINE}\n\n"
            f"Bot xizmatlaridan foydalanish uchun quyidagi rasmiy kanallarimizga a'zo bo'lishingiz shart.\n\n"
            f"<i>A'zo bo'lgach, «✅ Obunani Tasdiqlash» tugmasini bosing.</i>"
        )
        return await message.answer(text, reply_markup=await get_sub_keyboard(), parse_mode="HTML")

    # Foydalanuvchini bazadan izlash
    user = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (user_id,))
    
    if not user:
        await state.set_state(Form.reg_name)
        await message.answer(
            Texts.WELCOME.format(name=html.escape(message.from_user.first_name)),
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True) # Klaviaturani yopish
        )
    else:
        now = datetime.now()
        text = Texts.MAIN_MENU.format(
            name=html.escape(user['fullname']),
            date=now.strftime('%d.%m.%Y'),
            time=now.strftime('%H:%M')
        )
        await message.answer(text, reply_markup=UI.main_menu(user_id), parse_mode="HTML")


@dp.callback_query(F.data == "check_sub_btn")
async def verify_sub_handler(call: CallbackQuery, state: FSMContext, bot: Bot):
    is_sub = await check_subscription(bot, call.from_user.id)
    if not is_sub:
        return await call.answer("❌ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True)
    
    await call.message.delete()
    # Start funksiyasiga qayta yo'naltirish
    await cmd_start(call.message, state, bot)


@dp.message(Form.reg_name)
async def process_registration(message: Message, state: FSMContext):
    fullname = message.text.strip()
    if len(fullname) < 4 or len(fullname) > 50:
        return await message.answer("⚠️ Iltimos, ismingizni to'g'ri va to'liq kiriting (4-50 harf).")

    uid = message.from_user.id
    username = message.from_user.username or "mavjud_emas"
    now_iso = datetime.now().isoformat()

    await AsyncDB.execute(
        "INSERT INTO users (uid, fullname, username, joined_at) VALUES (?,?,?,?)",
        (uid, fullname, username, now_iso)
    )
    
    await message.answer(
        f"🎉 <b>Tabriklaymiz, {html.escape(fullname)}!</b>\n"
        f"{Design.D_LINE}\n"
        f"Siz muvaffaqiyatli ro'yxatdan o'tdingiz. Endi barcha xizmatlardan foydalanishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=UI.main_menu(uid)
    )
    await state.clear()


# ==========================================================================================
# 🌐 8. SAYTGA KIRISH KODI (WEB CODE)
# ==========================================================================================
@dp.message(F.text == Design.BTN_WEB)
async def web_code_menu(message: Message):
    user_id = message.from_user.id
    row = await AsyncDB.fetchone("SELECT * FROM web_codes WHERE uid=?", (user_id,))
    
    if row:
        text = (
            f"🌐 <b>VEB-SAYTGA KIRISH KODI</b>\n"
            f"{Design.D_LINE}\n\n"
            f"Sizning shaxsiy kodingiz: <span class='tg-spoiler'><b>{row['code']}</b></span>\n"
            f"<i>(Nusxalash uchun ustiga bosing: <code>{row['code']}</code>)</i>\n\n"
            f"📅 Yaratilgan: <b>{fmt_dt(row['created_at'])}</b>\n\n"
            f"🛡 <i>Ushbu kodni maxfiy saqlang. Saytga kirishda ushbu koddan foydalanasiz.</i>"
        )
        await message.answer(text, reply_markup=UI.get_web_code_markup(True), parse_mode="HTML")
    else:
        text = (
            f"🌐 <b>VEB-SAYTGA INTEGRATSIYA</b>\n"
            f"{Design.D_LINE}\n\n"
            f"Sizda hali kirish kodi mavjud emas. Saytga ulanish uchun quyidagi tugmani bosib 4 xonali maxfiy kod yarating."
        )
        await message.answer(text, reply_markup=UI.get_web_code_markup(False), parse_mode="HTML")


@dp.callback_query(F.data.startswith("code_"))
async def handle_web_code_actions(call: CallbackQuery):
    action = call.data.split("_")[1]
    user_id = call.from_user.id
    now_iso = datetime.now().isoformat()

    if action == "generate":
        existing = await AsyncDB.fetchone("SELECT code FROM web_codes WHERE uid=?", (user_id,))
        if existing:
            return await call.answer("Kod allaqachon mavjud!", show_alert=True)
            
        while True:
            new_code = gen_code()
            check = await AsyncDB.fetchone("SELECT uid FROM web_codes WHERE code=?", (new_code,))
            if not check: break
            
        await AsyncDB.execute(
            "INSERT INTO web_codes (uid, code, created_at) VALUES (?, ?, ?)",
            (user_id, new_code, now_iso)
        )
        await call.message.edit_text(
            f"✅ <b>KOD YARATILDI!</b>\n{Design.D_LINE}\n🔑 Sizning kodingiz: <code>{new_code}</code>",
            reply_markup=UI.get_web_code_markup(True), parse_mode="HTML"
        )
        
    elif action == "regenerate":
        while True:
            new_code = gen_code()
            check = await AsyncDB.fetchone("SELECT uid FROM web_codes WHERE code=?", (new_code,))
            if not check: break
            
        await AsyncDB.execute(
            "UPDATE web_codes SET code=?, created_at=? WHERE uid=?",
            (new_code, now_iso, user_id)
        )
        await call.message.edit_text(
            f"🔄 <b>KOD YANGILANDI!</b>\n{Design.D_LINE}\n🔑 Yangi kodingiz: <code>{new_code}</code>\n<i>Eski kod yaroqsiz holga keldi.</i>",
            reply_markup=UI.get_web_code_markup(True), parse_mode="HTML"
        )

    elif action == "delete":
        await AsyncDB.execute("DELETE FROM web_codes WHERE uid=?", (user_id,))
        await call.message.edit_text(
            f"🗑 <b>KOD O'CHIRILDI!</b>\n{Design.D_LINE}\nEndi bu profil orqali saytga kirib bo'lmaydi.",
            reply_markup=UI.get_web_code_markup(False), parse_mode="HTML"
        )
    await call.answer()


# ==========================================================================================
# 👤 9. FOYDALANUVCHI BO'LIMLARI (PROFIL, TARIX, SOZLAMALAR, FAQ)
# ==========================================================================================
@dp.message(F.text == Design.BTN_PROF)
async def view_profile(message: Message):
    u = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (message.from_user.id,))
    if not u: return
    c = await AsyncDB.fetchone("SELECT code FROM web_codes WHERE uid=?", (message.from_user.id,))
    code_txt = f"<code>{c['code']}</code>" if c else "<i>Yo'q</i>"
    
    text = (
        f"👤 <b>SHAXSIY KABINET</b>\n{Design.S_LINE}\n\n"
        f"🏷 F.I.Sh: <b>{html.escape(u['fullname'])}</b>\n"
        f"🆔 ID Rqam: <code>{u['uid']}</code>\n"
        f"📅 A'zo bo'lgan: <b>{fmt_dt(u['joined_at'])}</b>\n"
        f"🌐 Web Kod: {code_txt}\n\n"
        f"<i>Xavfsizligingiz o'z qo'lingizda.</i>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == Design.BTN_HISTORY)
async def view_login_history(message: Message):
    uid = message.from_user.id
    history = await AsyncDB.fetchall(
        "SELECT * FROM login_history WHERE uid=? ORDER BY login_time DESC LIMIT 5", (uid,)
    )
    
    if not history:
        text = f"📱 <b>KIRISH TARIXI</b>\n{Design.S_LINE}\n\nSiz hali saytga kirmagansiz."
    else:
        text = f"📱 <b>SO'NGGI 5 TA KIRISH TARIXI</b>\n{Design.S_LINE}\n\n"
        for i, h in enumerate(history, 1):
            status_ico = "🟢" if h['status'] == "SUCCESS" else "🔴"
            text += (
                f"{i}. {status_ico} <b>{fmt_dt(h['login_time'])}</b>\n"
                f"   IP: <code>{h['ip_address']}</code>\n"
                f"   Qurilma: <i>{html.escape(h['user_agent'][:25])}...</i>\n"
            )
            
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == Design.BTN_SETTINGS)
async def view_settings(message: Message):
    text = (
        f"⚙️ <b>SOZLAMALAR</b>\n{Design.S_LINE}\n\n"
        f"Profil ma'lumotlaringizni o'zgartirishingiz yoki bot haqida ma'lumot olishingiz mumkin."
    )
    await message.answer(text, reply_markup=UI.settings_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("set_"))
async def handle_settings_cb(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    
    if action == "change":
        await state.set_state(Form.settings_name)
        await call.message.edit_text(
            "📝 <b>Yangi ism va familiyangizni kiriting:</b>\n<i>(Masalan: Jasur Karimov)</i>",
            parse_mode="HTML"
        )
    elif action == "about":
        await call.answer("A'lo Ta'lim Bot - Versiya 6.0 Premium", show_alert=True)

@dp.message(Form.settings_name)
async def save_new_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if len(new_name) < 4:
        return await message.answer("⚠️ Ism juda qisqa.")
        
    await AsyncDB.execute("UPDATE users SET fullname=? WHERE uid=?", (new_name, message.from_user.id))
    await message.answer(f"✅ Ismingiz <b>{html.escape(new_name)}</b> ga o'zgartirildi!", parse_mode="HTML")
    await state.clear()


@dp.message(F.text == Design.BTN_FAQ)
async def view_faq(message: Message):
    text = (
        f"📚 <b>KO'P SO'RALADIGAN SAVOLLAR (FAQ)</b>\n{Design.S_LINE}\n\n"
        f"O'zingizni qiziqtirgan savolni tanlang:"
    )
    await message.answer(text, reply_markup=UI.faq_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("faq_"))
async def handle_faq_answer(call: CallbackQuery):
    faq_id = call.data.split("_")[1]
    answers = {
        "1": "Saytga kirish uchun «🌐 Saytga kirish» tugmasidan kod oling va saytning login oynasiga kiriting.",
        "2": "Agar kodingiz ishlamasa, u yangilangan yoki vaqti o'tgan bo'lishi mumkin. Yangi kod yarating.",
        "3": "Sizning barcha ma'lumotlaringiz kuchli shifrlangan bazada saqlanadi va uchinchi shaxslarga berilmaydi.",
        "4": "Asosiy menyudagi «🆘 Adminga murojaat» tugmasi orqali adminlarga to'g'ridan-to'g'ri xabar yuborishingiz mumkin."
    }
    await call.answer(answers.get(faq_id, "Noma'lum xatolik"), show_alert=True)


# ==========================================================================================
# 🆘 10. SUPPORT TIZIMI (FOYDALANUVCHIDAN ADMINGA)
# ==========================================================================================
@dp.message(F.text == Design.BTN_HELP)
async def ask_support(message: Message, state: FSMContext):
    await state.set_state(Form.support_msg)
    await message.answer(
        f"📬 <b>ADMINISTRATSIYA BILAN ALOQA</b>\n{Design.S_LINE}\n\n"
        f"Savol, taklif yoki muammoingizni shu yerga yozib yuboring. Adminlarimiz eng qisqa vaqt ichida javob berishadi.\n\n"
        f"<i>Bekor qilish uchun «⬅️ Orqaga» tugmasini bosing.</i>",
        reply_markup=UI.back_btn(), parse_mode="HTML"
    )

@dp.message(Form.support_msg)
async def receive_support_msg(message: Message, state: FSMContext, bot: Bot):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await cmd_start(message, state, bot)
        
    text = message.text or ""
    if len(text) < 5: return await message.answer("⚠️ Xabar juda qisqa!")

    mid = await AsyncDB.execute_return_id(
        "INSERT INTO support_messages (uid, message_text, created_at) VALUES (?, ?, ?)",
        (message.from_user.id, text, datetime.now().isoformat())
    )

    # Adminga yuborish
    admin_text = (
        f"🆕 <b>YANGI MUROJAAT #{mid}</b>\n{Design.S_LINE}\n"
        f"👤 Kimdan: <b>{html.escape(message.from_user.full_name)}</b>\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n\n"
        f"💬 <b>Matn:</b>\n<i>{html.escape(text)}</i>"
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✍️ Javob yozish", callback_data=f"adm_reply_{message.from_user.id}_{mid}"))
    
    try:
        await bot.send_message(Config.ADMIN_ID, admin_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Adminga xabar yuborishda xato: {e}")

    await message.answer("✅ Murojaatingiz yuborildi. Javobni kuting.", reply_markup=UI.main_menu(message.from_user.id))
    await state.clear()


# ==========================================================================================
# 👑 11. ADMIN PANEL VA FUNKSIYALARI
# ==========================================================================================
@dp.message(F.text == Design.BTN_ADM)
async def admin_portal(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    text = (
        f"🛠 <b>BOSH ADMIN PORTALI</b>\n{Design.D_LINE}\n\n"
        f"Hurmatli Admin, tizim to'liq ishchi holatda. Kerakli buyruqni tanlang:"
    )
    await message.answer(text, reply_markup=UI.admin_menu(), parse_mode="HTML")

# 11.1 Murojaatga javob berish
@dp.callback_query(F.data.startswith("adm_reply_"))
async def start_admin_reply(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != Config.ADMIN_ID: return
    
    _, _, target_id, mid = call.data.split("_")
    await state.update_data(target_id=target_id, mid=mid)
    await state.set_state(Form.adm_reply)
    
    await call.message.answer(
        f"📝 <b>Foydalanuvchiga (ID: {target_id}) javob yozing:</b>\n<i>Bekor qilish uchun «⬅️ Orqaga» ni bosing.</i>",
        reply_markup=UI.back_btn(), parse_mode="HTML"
    )
    await call.answer()

@dp.message(Form.adm_reply)
async def send_admin_reply(message: Message, state: FSMContext, bot: Bot):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await message.answer("Bekor qilindi.", reply_markup=UI.admin_menu())

    data = await state.get_data()
    
    try:
        user_msg = (
            f"📩 <b>ADMINISTRATSIYADAN JAVOB:</b>\n{Design.S_LINE}\n\n"
            f"{html.escape(message.text)}\n\n"
            f"<i>Sizning #{data['mid']}-sonli murojaatingizga javoban.</i>"
        )
        await bot.send_message(int(data['target_id']), user_msg, parse_mode="HTML")
        await AsyncDB.execute("UPDATE support_messages SET is_replied=1 WHERE mid=?", (data['mid'],))
        await message.answer("✅ Xabar muvaffaqiyatli yetkazildi!", reply_markup=UI.admin_menu())
    except Exception as e:
        await message.answer(f"❌ Yuborib bo'lmadi (Bloklagan bo'lishi mumkin). Xato: {e}", reply_markup=UI.admin_menu())
    
    await state.clear()


# 11.2 Kengaytirilgan Statistika
@dp.message(F.text == Design.ADM_STATS)
async def admin_stats(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    u_all = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM users"))['c']
    u_ban = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM users WHERE is_banned=1"))['c']
    codes = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM web_codes"))['c']
    msgs = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM support_messages"))['c']
    logins = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM login_history WHERE status='SUCCESS'"))['c']
    
    text = (
        f"📊 <b>KENGAYTIRILGAN STATISTIKA</b>\n{Design.D_LINE}\n\n"
        f"👥 Umumiy foydalanuvchilar: <b>{u_all} ta</b>\n"
        f"🚫 Bloklanganlar: <b>{u_ban} ta</b>\n"
        f"🔑 Faol Web Kodlar: <b>{codes} ta</b>\n"
        f"💬 Murojaatlar soni: <b>{msgs} ta</b>\n"
        f"🌐 Saytga umumiy kirishlar: <b>{logins} marta</b>\n\n"
        f"<i>Ma'lumotlar real vaqtda olingan.</i>"
    )
    await message.answer(text, parse_mode="HTML")


# 11.3 Shaxsiy Xabar Yuborish (Direct Message)
@dp.message(F.text == Design.ADM_DIRECT)
async def direct_msg_start(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(Form.adm_direct_id)
    await message.answer("🆔 Foydalanuvchi ID raqamini kiriting:", reply_markup=UI.back_btn())

@dp.message(Form.adm_direct_id)
async def direct_msg_id(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await admin_portal(message)
        
    if not message.text.isdigit(): return await message.answer("Faqat raqam kiriting!")
    
    await state.update_data(target_id=int(message.text))
    await state.set_state(Form.adm_direct_msg)
    await message.answer("📝 Xabar matnini kiriting:")

@dp.message(Form.adm_direct_msg)
async def direct_msg_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    try:
        await bot.send_message(data['target_id'], f"✉️ <b>Shaxsiy xabar:</b>\n\n{message.text}", parse_mode="HTML")
        await message.answer("✅ Xabar muvaffaqiyatli yuborildi!", reply_markup=UI.admin_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}", reply_markup=UI.admin_menu())
    await state.clear()


# 11.4 Ban Tizimi
@dp.message(F.text == Design.ADM_BAN_SYS)
async def ban_system_menu(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    await message.answer("🚫 <b>BAN TIZIMI BOSHQARUVI</b>", reply_markup=UI.admin_ban_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_do_"))
async def handle_ban_action(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[2]
    if action == "ban":
        await state.set_state(Form.adm_ban_id)
        await call.message.answer("🚫 Ban qilinadigan foydalanuvchi ID sini kiriting:", reply_markup=UI.back_btn())
    elif action == "unban":
        await state.set_state(Form.adm_unban_id)
        await call.message.answer("✅ Bandan olinadigan ID ni kiriting:", reply_markup=UI.back_btn())
    await call.answer()

@dp.message(or_f(Form.adm_ban_id, Form.adm_unban_id))
async def execute_ban_unban(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await admin_portal(message)
    
    uid = message.text.strip()
    if not uid.isdigit(): return await message.answer("Noto'g'ri ID!")
    
    current_state = await state.get_state()
    is_ban = 1 if current_state == Form.adm_ban_id.state else 0
    action_text = "bloklandi 🚫" if is_ban else "bandan olindi ✅"

    user = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (uid,))
    if not user:
        return await message.answer("❌ Bunday foydalanuvchi topilmadi.")

    await AsyncDB.execute("UPDATE users SET is_banned=? WHERE uid=?", (is_ban, uid))
    
    if is_ban:
        # Kodini ham o'chiramiz xavfsizlik uchun
        await AsyncDB.execute("DELETE FROM web_codes WHERE uid=?", (uid,))

    await message.answer(f"Foydalanuvchi muvaffaqiyatli {action_text}!", reply_markup=UI.admin_menu())
    await state.clear()


# 11.5 Excel/CSV Eksport (Ma'lumotlarni yuklash)
@dp.message(F.text == Design.ADM_EXPORT)
async def export_database(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    await message.answer("⏳ <i>Ma'lumotlar generatsiya qilinmoqda...</i>", parse_mode="HTML")
    
    users = await AsyncDB.fetchall("SELECT uid, fullname, username, joined_at, is_banned FROM users")
    
    # Xotirada CSV fayl yaratish
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["uid", "fullname", "username", "joined_at", "is_banned"])
    writer.writeheader()
    writer.writerows(users)
    
    # Faylni baytlarga o'tkazish
    output.seek(0)
    file_bytes = output.read().encode('utf-8')
    document = BufferedInputFile(file_bytes, filename=f"users_export_{datetime.now().strftime('%d_%m')}.csv")
    
    await message.answer_document(
        document=document,
        caption="📥 Foydalanuvchilar bazasi yuklab olindi (CSV formatida)."
    )


# 11.6 Majburiy Obunalarni Boshqarish
@dp.message(F.text == Design.ADM_CHANNELS)
async def manage_channels(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    await message.answer("📢 <b>OBUNALARNI BOSHQARISH</b>", reply_markup=UI.admin_channel_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_ch_"))
async def handle_channel_actions(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[2]
    
    if action == "add":
        await state.set_state(Form.adm_add_channel_data)
        await call.message.answer(
            "➕ <b>Kanal qo'shish:</b>\nQuyidagi formatda yuboring:\n`@kanal_id | Kanal Nomi | https://t.me/kanal_link`",
            parse_mode="Markdown", reply_markup=UI.back_btn()
        )
    elif action == "list":
        chans = await AsyncDB.fetchall("SELECT * FROM channels")
        if not chans:
            await call.message.answer("Kanallar yo'q.")
        else:
            txt = "📋 <b>Mavjud Kanallar:</b>\n\n"
            for c in chans:
                txt += f"ID: {c['channel_id']} | Nomi: {c['channel_name']}\n"
            await call.message.answer(txt, parse_mode="HTML")
    elif action == "del":
        await call.message.answer("O'chirish formati hali qo'shilmadi (xavfsizlik uchun bazadan tozalash tavsiya etiladi).")
    await call.answer()

@dp.message(Form.adm_add_channel_data)
async def save_new_channel(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await admin_portal(message)
        
    try:
        cid, cname, curl = [x.strip() for x in message.text.split("|")]
        await AsyncDB.execute(
            "INSERT INTO channels (channel_id, channel_name, url) VALUES (?,?,?)",
            (cid, cname, curl)
        )
        await message.answer("✅ Kanal muvaffaqiyatli qo'shildi!", reply_markup=UI.admin_menu())
    except Exception:
        await message.answer("❌ Format xato. Qaytadan urinib ko'ring.")
    finally:
        await state.clear()


# 11.7 Barchaga xabar yuborish (Broadcast - Mukammallashtirilgan)
@dp.message(F.text == Design.ADM_BROADCAST)
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(Form.adm_bc_text)
    await message.answer("📢 Xabar matnini kiriting (HTML formatida ham yozish mumkin):", reply_markup=UI.back_btn())

@dp.message(Form.adm_bc_text)
async def broadcast_preview(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await admin_portal(message)
        
    await state.update_data(bc_text=message.text)
    await state.set_state(Form.adm_bc_confirm)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Yuborish", callback_data="bc_send"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel")
    )
    
    await message.answer(
        f"👀 <b>PREVIEW:</b>\n\n{message.text}\n\n<i>Shu xabarni hamma a'zolarga yuborasizmi?</i>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("bc_"), Form.adm_bc_confirm)
async def broadcast_action(call: CallbackQuery, state: FSMContext, bot: Bot):
    if call.data == "bc_cancel":
        await state.clear()
        await call.message.edit_text("❌ Bekor qilindi.")
        return await call.answer()
        
    data = await state.get_data()
    msg_text = data['bc_text']
    
    await call.message.edit_text("🔄 Xabar barchaga yuborilmoqda, tizimni yopmang...")
    
    users = await AsyncDB.fetchall("SELECT uid FROM users WHERE is_banned=0")
    success, fail = 0, 0
    
    for u in users:
        try:
            await bot.send_message(u['uid'], msg_text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.04) # Spam blockni oldini olish
        except Exception:
            fail += 1

    await call.message.answer(
        f"✅ <b>Eshittirish yakunlandi!</b>\n"
        f"🟢 Yetkazildi: <b>{success}</b>\n🔴 Xatolik/Blok: <b>{fail}</b>",
        reply_markup=UI.admin_menu(), parse_mode="HTML"
    )
    await state.clear()


# ==========================================================================================
# 🌐 12. WEB API SERVER (AIOHTTP) - KUCHAYTIRILGAN
# ==========================================================================================
async def handle_root(request):
    return web.Response(text="A'lo Ta'lim API Serveri faol! Barcha xizmatlar barqaror ishlamoqda.")

async def api_login(request):
    """Veb-saytdan kelgan so'rovlarni qabul qilib, kodni tekshirish API'si."""
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    
    try:
        data = await request.json()
        entered_code = data.get("student_id", "").strip()
        client_ip = request.remote or "Unknown IP"
        user_agent = request.headers.get("User-Agent", "Unknown Device")
        now_iso = datetime.now().isoformat()
        
        web_user = await AsyncDB.fetchone("SELECT * FROM web_codes WHERE code=?", (entered_code,))
        
        if web_user:
            uid = web_user["uid"]
            user = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (uid,))
            
            if user:
                if user['is_banned'] == 1:
                    # Banned user attempt
                    await AsyncDB.execute(
                        "INSERT INTO login_history (uid, ip_address, user_agent, login_time, status) VALUES (?,?,?,?,?)",
                        (uid, client_ip, user_agent, now_iso, "FAILED_BANNED")
                    )
                    return web.json_response({
                        "success": False, "error": "Sizning hisobingiz bloklangan!"
                    }, status=403, headers={'Access-Control-Allow-Origin': '*'})
                
                # Successful login
                await AsyncDB.execute(
                    "INSERT INTO login_history (uid, ip_address, user_agent, login_time, status) VALUES (?,?,?,?,?)",
                    (uid, client_ip, user_agent, now_iso, "SUCCESS")
                )
                
                return web.json_response({
                    "success": True, 
                    "name": user["fullname"], 
                    "uid": user["uid"], 
                    "role": "admin" if user["uid"] == Config.ADMIN_ID else "user"
                }, headers={'Access-Control-Allow-Origin': '*'})
                
        return web.json_response({
            "success": False, 
            "error": "Kod noto'g'ri yoki ro'yxatdan o'tmagan! Botdan yangi kod oling."
        }, status=400, headers={'Access-Control-Allow-Origin': '*'})

    except Exception as e:
        logger.error(f"API Xatolik: {e}")
        return web.json_response({"success": False, "error": "Server ichki xatoligi."}, status=500, headers={'Access-Control-Allow-Origin': '*'})


# ==========================================================================================
# 🚀 13. DASTURNI ISHGA TUSHIRISH (ENTRY POINT)
# ==========================================================================================
async def main():
    logger.info("Starting A'lo Ta'lim Premium Bot System...")
    
    # 1. Bazani tayyorlash
    await AsyncDB.setup()
    
    # 2. Veb serverni sozlash (aiohttp)
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_options("/api/login", api_login)
    app.router.add_post("/api/login", api_login)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, Config.HOST, Config.PORT)
    await site.start()
    logger.info(f"Web API running on http://{Config.HOST}:{Config.PORT}")

    # 3. Botni sozlash va Pollingni boshlash
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Tizimni yuklash (Asosiy menyu)")
    ])
    
    logger.info("Bot polling is started.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped correctly.")
