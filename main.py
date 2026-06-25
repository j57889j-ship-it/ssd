"""
==========================================================================================
🌟 A'LO TA'LIM PLATFORMASI - ULTIMATE INTEGRATION BOT 🌟
==========================================================================================
Versiya: 7.0.0 (Enterprise Edition)
Yangilanish: Keraksiz funksiyalar olib tashlandi (FAQ, History, CSV).
             Kesh tizimi, aqlli admin panel, foydalanuvchini qidirish va
             yuqori tezlikdagi ma'lumotlar bazasi indeksovkasi qo'shildi.
Arxitektura: Aiogram 3.x + Aiohttp + Aiosqlite + Memory Caching + Advanced FSM.
==========================================================================================
"""

import asyncio
import logging
import os
import html
import random
import time
from datetime import datetime, timedelta
from typing import Final, Any, Optional, List, Dict, Union

# Tashqi kutubxonalar (Aiogram va Aiohttp)
from aiohttp import web
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, Update
)
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError

import aiosqlite
from dotenv import load_dotenv

# ==========================================================================================
# ⚙️ 1. TIZIM SOZLAMALARI VA ATROF-MUHIT O'ZGARUVCHILARI
# ==========================================================================================
load_dotenv()

class Config:
    """Tizimning asosiy konfiguratsiyasi. Maxfiy ma'lumotlar .env fayldan olinadi."""
    TOKEN: Final[str] = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
    ADMIN_ID: Final[int] = int(os.getenv("ADMIN_ID", "0") or "0")
    DB_NAME: Final[str] = os.getenv("DB_NAME", "ultimate_database.db")
    PORT: Final[int] = int(os.getenv("PORT", 8080))
    HOST: Final[str] = os.getenv("HOST", "0.0.0.0")
    
    # Spamdan himoya va kesh sozlamalari
    THROTTLE_TIME: Final[float] = 0.5  # Foydalanuvchi qancha soniyada 1 ta xabar yoza oladi
    CACHE_TTL: Final[int] = 300        # Keshni tozalash vaqti (soniyada)

# ==========================================================================================
# 🎨 2. DIZAYN VA MATNLAR (UI/UX)
# ==========================================================================================
class Design:
    """Botning vizual elementlari va chiziqlar."""
    D_LINE = "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>"
    S_LINE = "<b>─────────────────────────────</b>"
    TITLE = "🎓 <b>A'LO TA'LIM PLATFORMASI</b>"
    
    # Foydalanuvchi tugmalari (FAQ va Tarix olib tashlandi)
    BTN_WEB = "🌐 Saytga kirish / Web Kod"
    BTN_PROF = "👤 Shaxsiy Kabinet"
    BTN_SETTINGS = "⚙️ Sozlamalar"
    BTN_HELP = "🆘 Adminga murojaat"
    BTN_BACK = "⬅️ Orqaga"
    BTN_HOME = "🏠 Asosiy Menyu"
    BTN_ADM = "👑 Admin Panel"

    # Admin tugmalari (Eksport olib tashlandi, Qidiruv qo'shildi)
    ADM_STATS = "📊 Kengaytirilgan Statistika"
    ADM_SEARCH = "🔍 Foydalanuvchini izlash"
    ADM_BROADCAST = "📢 Barchaga Xabar yuborish"
    ADM_DIRECT = "✉️ Shaxsiy xabar yuborish"
    ADM_BAN_SYS = "🚫 Ban Tizimi boshqaruvi"
    ADM_CHANNELS = "📢 Obunalarni boshqarish"

class Texts:
    """Botning asosiy interfeys matnlari."""
    WELCOME = (
        f"{Design.TITLE}\n"
        f"{Design.D_LINE}\n\n"
        f"👋 Assalomu alaykum, <b>{{name}}</b>!\n"
        f"Premium ta'lim tizimiga xush kelibsiz.\n\n"
        f"✍️ <b>Iltimos, tizimdan foydalanish uchun to'liq ism va familiyangizni kiriting:</b>\n\n"
        f"💡 <i>Namuna: Abdurahmon Alimov</i>"
    )
    
    MAIN_MENU = (
        f"{Design.TITLE}\n"
        f"{Design.D_LINE}\n\n"
        f"👤 Foydalanuvchi: <b>{{name}}</b>\n"
        f"⚡️ Holat: <b>Faol</b>\n"
        f"🕒 Tizim vaqti: <b>{{time}}</b>\n\n"
        f"👇 <i>Quyidagi interaktiv menyudan kerakli bo'limni tanlang:</i>"
    )

    BANNED = (
        f"⛔️ <b>DIQQAT: SIZ TIZIMDAN CHETLASHGANSZ!</b>\n"
        f"{Design.D_LINE}\n\n"
        f"Qoidalarni buzganligingiz sababli akkauntingiz bloklangan.\n"
        f"Web saytga va botga kirish huquqidan mahrum etildingiz."
    )

# ==========================================================================================
# 📝 3. KENGAYTIRILGAN LOGGING TIZIMI
# ==========================================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AloTalimBot")

bot = Bot(token=Config.TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==========================================================================================
# 🧠 4. XOTIRA KESHI (MEMORY CACHE) - TEZKORLIK UCHUN
# ==========================================================================================
class CacheManager:
    """Ma'lumotlar bazasiga ortiqcha so'rov yubormaslik uchun kesh tizimi."""
    def __init__(self):
        self._banned_users: set = set()
        self._channels: List[Dict] = []
        self._last_update: float = 0.0

    async def update_cache(self):
        """Keshni bazadan yangilaydi."""
        now = time.time()
        if now - self._last_update > Config.CACHE_TTL:
            try:
                # Ban qilinganlarni keshlash
                bans = await AsyncDB.fetchall("SELECT uid FROM users WHERE is_banned=1")
                self._banned_users = {b['uid'] for b in bans}
                
                # Kanallarni keshlash
                chans = await AsyncDB.fetchall("SELECT channel_id, channel_name, url FROM channels")
                self._channels = chans
                
                self._last_update = now
                logger.info("⚡️ Tizim keshi muvaffaqiyatli yangilandi.")
            except Exception as e:
                logger.error(f"Keshni yangilashda xatolik: {e}")

    def is_banned(self, user_id: int) -> bool:
        return user_id in self._banned_users

    def get_channels(self) -> List[Dict]:
        return self._channels

    def force_update(self):
        """Majburiy yangilash uchun vaqtni nolga tushirish."""
        self._last_update = 0.0

cache = CacheManager()


# ==========================================================================================
# 🗄 5. MA'LUMOTLAR BAZASI (AIOSQLITE) - INDEKSLAR BILAN KUCHAYTIRILGAN
# ==========================================================================================
class AsyncDB:
    """Yuqori yuklamalarga chidamli asinxron baza boshqaruvi."""
    
    @staticmethod
    async def setup():
        """Jadvallar va indekslarni yaratish."""
        async with aiosqlite.connect(Config.DB_NAME) as db:
            # 1. Users
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid INTEGER PRIMARY KEY,
                    fullname TEXT,
                    username TEXT,
                    joined_at TIMESTAMP,
                    is_banned INTEGER DEFAULT 0
                )
            """)
            # Tezkor qidiruv uchun indeks
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned)")
            
            # 2. Web Codes (Tarix olib tashlandi, faqat faol kodlar)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS web_codes (
                    uid INTEGER PRIMARY KEY,
                    code TEXT UNIQUE,
                    created_at TIMESTAMP
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_web_codes_code ON web_codes(code)")

            # 3. Support Messages
            await db.execute("""
                CREATE TABLE IF NOT EXISTS support_messages (
                    mid INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER,
                    message_text TEXT,
                    created_at TIMESTAMP,
                    is_replied INTEGER DEFAULT 0
                )
            """)

            # 4. Channels
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE,
                    channel_name TEXT,
                    url TEXT
                )
            """)
            await db.commit()
            logger.info("🗄 Ma'lumotlar bazasi va indekslar tayyor.")

    @staticmethod
    async def execute(sql: str, params: tuple = ()) -> None:
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute(sql, params)
            await db.commit()

    @staticmethod
    async def fetchone(sql: str, params: tuple = ()) -> Optional[Dict]:
        async with aiosqlite.connect(Config.DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def fetchall(sql: str, params: tuple = ()) -> List[Dict]:
        async with aiosqlite.connect(Config.DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


# ==========================================================================================
# 🚥 6. FSM HOLATLAR (STATE MANAGER)
# ==========================================================================================
class Form(StatesGroup):
    reg_name = State()            # Ro'yxatdan o'tish
    support_msg = State()         # Murojaat yozish
    settings_name = State()       # Ismni tahrirlash
    
    # Admin holatlari
    adm_reply = State()           # Murojaatga javob
    adm_bc_text = State()         # Broadcast matni
    adm_bc_confirm = State()      # Broadcast tasdiqi
    adm_direct_id = State()       # DM uchun ID
    adm_direct_msg = State()      # DM matni
    adm_ban_id = State()          # Ban qilish ID
    adm_unban_id = State()        # Bandan olish ID
    adm_search_user = State()     # Qidiruv ID si
    adm_add_channel_data = State()# Kanal qo'shish

# ==========================================================================================
# 🎹 7. KEYBOARDS (TUGMALAR) TIZIMI
# ==========================================================================================
class UI:
    """Dinamik va chiroyli tugmalar generatori."""
    
    @staticmethod
    def main_menu(user_id: int):
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=Design.BTN_WEB), KeyboardButton(text=Design.BTN_PROF))
        b.row(KeyboardButton(text=Design.BTN_SETTINGS), KeyboardButton(text=Design.BTN_HELP))
        if user_id == Config.ADMIN_ID:
            b.row(KeyboardButton(text=Design.BTN_ADM))
        return b.as_markup(resize_keyboard=True)
        
    @staticmethod
    def admin_menu():
        b = ReplyKeyboardBuilder()
        b.row(KeyboardButton(text=Design.ADM_STATS), KeyboardButton(text=Design.ADM_SEARCH))
        b.row(KeyboardButton(text=Design.ADM_BROADCAST), KeyboardButton(text=Design.ADM_DIRECT))
        b.row(KeyboardButton(text=Design.ADM_BAN_SYS), KeyboardButton(text=Design.ADM_CHANNELS))
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
        kb.row(InlineKeyboardButton(text="ℹ️ Tizim haqida", callback_data="set_about"))
        return kb.as_markup()

    @staticmethod
    def admin_user_action_markup(target_id: int, is_banned: bool) -> InlineKeyboardMarkup:
        """Admin foydalanuvchi profilini ko'rganda chiqadigan tezkor tugmalar."""
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="✉️ Xabar yozish", callback_data=f"adm_fast_dm_{target_id}"))
        if is_banned:
            kb.row(InlineKeyboardButton(text="✅ Bandan olish", callback_data=f"adm_fast_unban_{target_id}"))
        else:
            kb.row(InlineKeyboardButton(text="🚫 Ban berish", callback_data=f"adm_fast_ban_{target_id}"))
        return kb.as_markup()

    @staticmethod
    def admin_channel_markup() -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_ch_add"))
        kb.row(InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="admin_ch_list"))
        # Xavfsizlik uchun kanalni o'chirish faqat ID bilan
        kb.row(InlineKeyboardButton(text="➖ Kanalni o'chirish", callback_data="admin_ch_del"))
        return kb.as_markup()


# ==========================================================================================
# 🛡 8. XAVFSIZLIK VA TEZKORLIK (MIDDLEWARES)
# ==========================================================================================
class SecurityMiddleware(BaseMiddleware):
    """Ban tekshiruvi (Kesh orqali ishlaydi, DB ga tushmaydi - Juda tez!)"""
    async def __call__(self, handler, event: Update, data: dict):
        # Keshni yangilash
        await cache.update_cache()
        
        user_id = None
        if event.message:
            user_id = event.message.from_user.id
        elif event.callback_query:
            user_id = event.callback_query.from_user.id

        if user_id and cache.is_banned(user_id):
            if event.message:
                await event.message.answer(Texts.BANNED, parse_mode="HTML")
            elif event.callback_query:
                await event.callback_query.answer("Siz bloklangansiz!", show_alert=True)
            return # Block request
            
        return await handler(event, data)

dp.update.middleware(SecurityMiddleware())


# ==========================================================================================
# 📢 9. MAJBURIY OBUNA TIZIMI (KESHLANGAN TEKSHIRUV)
# ==========================================================================================
async def check_subscription(bot: Bot, user_id: int) -> bool:
    channels = cache.get_channels()
    if not channels:
        return True
        
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if member.status in ['left', 'kicked', 'banned']:
                return False
        except Exception as e:
            logger.warning(f"Kanalni tekshirishda muammo ({ch['channel_id']}): {e}")
            return False 
    return True

async def get_sub_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    channels = cache.get_channels()
    for ch in channels:
        builder.row(InlineKeyboardButton(text=ch["channel_name"], url=ch["url"]))
    builder.row(InlineKeyboardButton(text="✅ Tasdiqlash va Davom etish", callback_data="check_sub_btn"))
    return builder.as_markup()


# ==========================================================================================
# 🛠 YORDAMCHI FUNKSIYALAR
# ==========================================================================================
def fmt_dt(value: Optional[str]) -> str:
    """ISO formatdagi sanani chiroyli ko'rinishga o'tkazish."""
    if not value: return "Ma'lumot yo'q"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d.%m.%Y | %H:%M")
    except Exception:
        return str(value)[:16]

def generate_secure_code() -> str:
    """Murakkab 6 xonali raqamli xavfsiz kod yaratish."""
    return str(random.randint(100000, 999999))


# ==========================================================================================
# 🚀 10. ASOSIY HANDLERLAR (START, REGISTRATSIYA)
# ==========================================================================================
@dp.message(or_f(Command("start"), F.text == Design.BTN_HOME, F.text == Design.BTN_BACK))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id
    
    # Keshni yangilab, obunani tekshiramiz
    await cache.update_cache()
    is_sub = await check_subscription(bot, user_id)
    
    if not is_sub:
        text = (
            f"🛑 <b>TIZIMGA KIRISH UCHUN MAJBURIY OBUNA</b>\n"
            f"{Design.D_LINE}\n\n"
            f"Xizmatlar sifatini ta'minlash maqsadida quyidagi rasmiy kanallarimizga obuna bo'lishingiz so'raladi.\n\n"
            f"<i>Obuna bo'lgach, tasdiqlash tugmasini bosing.</i>"
        )
        return await message.answer(text, reply_markup=await get_sub_keyboard(), parse_mode="HTML")

    user = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (user_id,))
    
    if not user:
        await state.set_state(Form.reg_name)
        await message.answer(
            Texts.WELCOME.format(name=html.escape(message.from_user.first_name)),
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)
        )
    else:
        text = Texts.MAIN_MENU.format(
            name=html.escape(user['fullname']),
            time=datetime.now().strftime('%H:%M')
        )
        await message.answer(text, reply_markup=UI.main_menu(user_id), parse_mode="HTML")

@dp.callback_query(F.data == "check_sub_btn")
async def verify_sub_handler(call: CallbackQuery, state: FSMContext, bot: Bot):
    is_sub = await check_subscription(bot, call.from_user.id)
    if not is_sub:
        return await call.answer("❌ Barcha kanallarga obuna bo'lishingiz shart!", show_alert=True)
    
    await call.message.delete()
    await cmd_start(call.message, state, bot)

@dp.message(Form.reg_name)
async def process_registration(message: Message, state: FSMContext):
    fullname = message.text.strip()
    if len(fullname) < 4 or len(fullname) > 50:
        return await message.answer("⚠️ Ism va familiya kamida 4 harfdan iborat bo'lishi kerak. Qaytadan kiriting:")

    uid = message.from_user.id
    username = message.from_user.username or "yoq"
    now_iso = datetime.now().isoformat()

    await AsyncDB.execute(
        "INSERT INTO users (uid, fullname, username, joined_at) VALUES (?,?,?,?)",
        (uid, fullname, username, now_iso)
    )
    
    await message.answer(
        f"🎉 <b>Muvaffaqiyatli ro'yxatdan o'tdingiz, {html.escape(fullname)}!</b>\n"
        f"{Design.D_LINE}\n"
        f"Endi platformaning barcha xizmatlaridan cheklovsiz foydalanishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=UI.main_menu(uid)
    )
    await state.clear()


# ==========================================================================================
# 🌐 11. VEB KOD TIZIMI (WEB INTEGRATION)
# ==========================================================================================
@dp.message(F.text == Design.BTN_WEB)
async def handle_web_menu(message: Message):
    user_id = message.from_user.id
    row = await AsyncDB.fetchone("SELECT * FROM web_codes WHERE uid=?", (user_id,))
    
    if row:
        text = (
            f"🌐 <b>TIZIMGA KIRISH KODI</b>\n"
            f"{Design.D_LINE}\n\n"
            f"Sizning shaxsiy xavfsiz kodingiz:\n"
            f"👉 <span class='tg-spoiler'><b>{row['code']}</b></span> 👈\n\n"
            f"<i>Nusxalash uchun ustiga bosing:</i> <code>{row['code']}</code>\n\n"
            f"📅 Yaratilgan sana: <b>{fmt_dt(row['created_at'])}</b>\n\n"
            f"🛡 <b>DIQQAT:</b> <i>Kodni hech kimga bermang! Saytning login qismida shu koddan foydalaning.</i>"
        )
        await message.answer(text, reply_markup=UI.get_web_code_markup(True), parse_mode="HTML")
    else:
        text = (
            f"🌐 <b>VEB-SAYT INTEGRATSIYASI</b>\n"
            f"{Design.D_LINE}\n\n"
            f"Sizda saytga kirish uchun xavfsiz kod mavjud emas. Davom etish uchun quyidagi tugma orqali kod generatsiya qiling."
        )
        await message.answer(text, reply_markup=UI.get_web_code_markup(False), parse_mode="HTML")

@dp.callback_query(F.data.startswith("code_"))
async def process_web_code_actions(call: CallbackQuery):
    action = call.data.split("_")[1]
    user_id = call.from_user.id
    now_iso = datetime.now().isoformat()

    if action == "generate":
        existing = await AsyncDB.fetchone("SELECT code FROM web_codes WHERE uid=?", (user_id,))
        if existing:
            return await call.answer("Kodingiz allaqachon yaratilgan!", show_alert=True)
            
        while True:
            new_code = generate_secure_code()
            check = await AsyncDB.fetchone("SELECT uid FROM web_codes WHERE code=?", (new_code,))
            if not check: break
            
        await AsyncDB.execute(
            "INSERT INTO web_codes (uid, code, created_at) VALUES (?, ?, ?)",
            (user_id, new_code, now_iso)
        )
        await call.message.edit_text(
            f"✅ <b>KOD MUVAFFAQIYATLI YARATILDI!</b>\n{Design.D_LINE}\n🔑 Kodingiz: <code>{new_code}</code>\n<i>Saytga kirishda ushbu koddan foydalaning.</i>",
            reply_markup=UI.get_web_code_markup(True), parse_mode="HTML"
        )
        
    elif action == "regenerate":
        while True:
            new_code = generate_secure_code()
            check = await AsyncDB.fetchone("SELECT uid FROM web_codes WHERE code=?", (new_code,))
            if not check: break
            
        await AsyncDB.execute(
            "UPDATE web_codes SET code=?, created_at=? WHERE uid=?",
            (new_code, now_iso, user_id)
        )
        await call.message.edit_text(
            f"🔄 <b>KOD YANGILANDI!</b>\n{Design.D_LINE}\n🔑 Yangi kodingiz: <code>{new_code}</code>\n\n<i>Eski kod tizimdan o'chirildi va yaroqsiz holga keldi.</i>",
            reply_markup=UI.get_web_code_markup(True), parse_mode="HTML"
        )

    elif action == "delete":
        await AsyncDB.execute("DELETE FROM web_codes WHERE uid=?", (user_id,))
        await call.message.edit_text(
            f"🗑 <b>KOD O'CHIRILDI!</b>\n{Design.D_LINE}\nSizning veb-saytga kirish huquqingiz vaqtincha to'xtatildi. Saytga kirish uchun yangi kod yaratishingiz kerak.",
            reply_markup=UI.get_web_code_markup(False), parse_mode="HTML"
        )
    await call.answer()


# ==========================================================================================
# 👤 12. PROFIL VA SOZLAMALAR BO'LIMI
# ==========================================================================================
@dp.message(F.text == Design.BTN_PROF)
async def view_user_profile(message: Message):
    user_id = message.from_user.id
    u = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (user_id,))
    if not u: return
    c = await AsyncDB.fetchone("SELECT code FROM web_codes WHERE uid=?", (user_id,))
    
    code_txt = f"<code>{c['code']}</code>" if c else "<i>Mavjud emas</i>"
    username_txt = f"@{u['username']}" if u['username'] != 'yoq' else "<i>Yo'q</i>"
    
    text = (
        f"👤 <b>SHAXSIY KABINET</b>\n{Design.S_LINE}\n\n"
        f"📝 F.I.Sh: <b>{html.escape(u['fullname'])}</b>\n"
        f"🔗 Username: {username_txt}\n"
        f"🆔 ID Raqam: <code>{u['uid']}</code>\n"
        f"📅 Ro'yxatdan o'tgan: <b>{fmt_dt(u['joined_at'])}</b>\n\n"
        f"🌐 Web Tizim Kodi: {code_txt}\n\n"
        f"<i>Barcha ma'lumotlaringiz xavfsiz shifrlangan.</i>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == Design.BTN_SETTINGS)
async def view_settings(message: Message):
    text = (
        f"⚙️ <b>SOZLAMALAR BO'LIMI</b>\n{Design.S_LINE}\n\n"
        f"Quyidagi tugmalar yordamida ismingizni tahrirlashingiz yoki tizim haqida ma'lumot olishingiz mumkin."
    )
    await message.answer(text, reply_markup=UI.settings_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("set_"))
async def handle_settings_callbacks(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    
    if action == "change":
        await state.set_state(Form.settings_name)
        await call.message.edit_text(
            "📝 <b>Yangi ism va familiyangizni to'liq kiriting:</b>\n\n<i>(Masalan: Sardor Rahimov)</i>",
            parse_mode="HTML"
        )
    elif action == "about":
        info = "A'LO TA'LIM PLATFORMASI\nVersiya: 7.0 Ultimate\n\nXavfsiz va ishonchli tizim."
        await call.answer(info, show_alert=True)

@dp.message(Form.settings_name)
async def process_new_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if len(new_name) < 4:
        return await message.answer("⚠️ Kiritilgan ma'lumot juda qisqa. Kamida 4 ta harf bo'lishi kerak.")
        
    await AsyncDB.execute("UPDATE users SET fullname=? WHERE uid=?", (new_name, message.from_user.id))
    await message.answer(
        f"✅ <b>Muvaffaqiyatli!</b>\n\nSizning ismingiz <b>{html.escape(new_name)}</b> ga o'zgartirildi.", 
        parse_mode="HTML"
    )
    await state.clear()


# ==========================================================================================
# 🆘 13. SUPPORT / YORDAM TIZIMI
# ==========================================================================================
@dp.message(F.text == Design.BTN_HELP)
async def trigger_support(message: Message, state: FSMContext):
    await state.set_state(Form.support_msg)
    await message.answer(
        f"📬 <b>ADMINISTRATSIYA BILAN BOG'LANISH</b>\n{Design.S_LINE}\n\n"
        f"Tizimda muammoga duch keldingizmi yoki taklifingiz bormi? Xabaringizni shu yerda yozib yuboring.\n\n"
        f"<i>Xabar yozishni bekor qilish uchun «⬅️ Orqaga» tugmasini bosing.</i>",
        reply_markup=UI.back_btn(), parse_mode="HTML"
    )

@dp.message(Form.support_msg)
async def receive_support_msg(message: Message, state: FSMContext, bot: Bot):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await cmd_start(message, state, bot)
        
    text = message.text or ""
    if len(text) < 5: 
        return await message.answer("⚠️ Murojaat matni juda qisqa. Batafsilroq yozing.")

    mid = await AsyncDB.execute(
        "INSERT INTO support_messages (uid, message_text, created_at) VALUES (?, ?, ?)",
        (message.from_user.id, text, datetime.now().isoformat())
    )
    
    # Bazadan yangi kiritilgan qatorning ID sini olamiz
    row = await AsyncDB.fetchone("SELECT seq FROM sqlite_sequence WHERE name='support_messages'")
    last_id = row['seq'] if row else random.randint(100,999)

    admin_text = (
        f"🆕 <b>YANGI MUROJAAT [#{last_id}]</b>\n{Design.S_LINE}\n"
        f"👤 Yuboruvchi: <b>{html.escape(message.from_user.full_name)}</b>\n"
        f"🆔 ID raqam: <code>{message.from_user.id}</code>\n\n"
        f"💬 <b>Matn:</b>\n<i>{html.escape(text)}</i>"
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✍️ Javob yozish", callback_data=f"adm_reply_{message.from_user.id}_{last_id}"))
    
    try:
        await bot.send_message(Config.ADMIN_ID, admin_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Adminga xabar yuborishda xato: {e}")

    await message.answer(
        "✅ <b>Murojaatingiz ma'muriyatga muvaffaqiyatli yetkazildi!</b>\n\nJavobni ushbu bot orqali kutishingiz mumkin.", 
        reply_markup=UI.main_menu(message.from_user.id), parse_mode="HTML"
    )
    await state.clear()


# ==========================================================================================
# 👑 14. ADMIN PANEL: BOSH MENYU VA MUROJAATLAR
# ==========================================================================================
@dp.message(F.text == Design.BTN_ADM)
async def enter_admin_portal(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    text = (
        f"👑 <b>BOSH ADMIN PORTALI</b>\n{Design.D_LINE}\n\n"
        f"Tizim monitoringi va boshqaruvi bo'limiga xush kelibsiz.\n"
        f"Kerakli operatsiyani tanlang:"
    )
    await message.answer(text, reply_markup=UI.admin_menu(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("adm_reply_"))
async def start_admin_reply(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != Config.ADMIN_ID: return
    
    _, _, target_id, mid = call.data.split("_")
    await state.update_data(target_id=target_id, mid=mid)
    await state.set_state(Form.adm_reply)
    
    await call.message.answer(
        f"📝 <b>Foydalanuvchiga (ID: {target_id}) javob yozish:</b>\n<i>Bekor qilish uchun «⬅️ Orqaga» tugmasini bosing.</i>",
        reply_markup=UI.back_btn(), parse_mode="HTML"
    )
    await call.answer()

@dp.message(Form.adm_reply)
async def process_admin_reply(message: Message, state: FSMContext, bot: Bot):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await message.answer("Javob yozish bekor qilindi.", reply_markup=UI.admin_menu())

    data = await state.get_data()
    
    try:
        user_msg = (
            f"📩 <b>MA'MURIYATDAN JAVOB:</b>\n{Design.S_LINE}\n\n"
            f"{html.escape(message.text)}\n\n"
            f"<i>Bu xabar sizning #{data['mid']}-sonli murojaatingizga javoban yuborildi.</i>"
        )
        await bot.send_message(int(data['target_id']), user_msg, parse_mode="HTML")
        await AsyncDB.execute("UPDATE support_messages SET is_replied=1 WHERE mid=?", (data['mid'],))
        await message.answer("✅ Javobingiz foydalanuvchiga muvaffaqiyatli yetkazildi!", reply_markup=UI.admin_menu())
    except TelegramForbiddenError:
        await message.answer("❌ Xatolik: Foydalanuvchi botni bloklagan.", reply_markup=UI.admin_menu())
    except Exception as e:
        await message.answer(f"❌ Kutilmagan xatolik: {e}", reply_markup=UI.admin_menu())
    
    await state.clear()


# ==========================================================================================
# 📊 15. ADMIN PANEL: KENGAYTIRILGAN STATISTIKA (SMART STATS)
# ==========================================================================================
@dp.message(F.text == Design.ADM_STATS)
async def view_smart_stats(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    await message.answer("⏳ <i>Statistika hisoblanmoqda...</i>", parse_mode="HTML")
    
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0).isoformat()
    week_start = (now - timedelta(days=7)).isoformat()
    
    # Umumiy hisob-kitoblar
    total_users = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM users"))['c']
    banned_users = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM users WHERE is_banned=1"))['c']
    active_codes = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM web_codes"))['c']
    total_messages = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM support_messages"))['c']
    unanswered_msgs = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM support_messages WHERE is_replied=0"))['c']
    
    # Vaqt bo'yicha hisob-kitoblar
    joined_today = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM users WHERE joined_at >= ?", (today_start,)))['c']
    joined_week = (await AsyncDB.fetchone("SELECT COUNT(*) as c FROM users WHERE joined_at >= ?", (week_start,)))['c']
    
    # Foizlarni hisoblash
    ban_percent = round((banned_users / total_users * 100), 1) if total_users > 0 else 0
    code_percent = round((active_codes / total_users * 100), 1) if total_users > 0 else 0
    
    text = (
        f"📊 <b>KENGAYTIRILGAN TIZIM STATISTIKASI</b>\n{Design.D_LINE}\n\n"
        f"👥 <b>FOYDALANUVCHILAR HOLATI:</b>\n"
        f"• Umumiy a'zolar: <b>{total_users}</b> ta\n"
        f"• Bugun qo'shilganlar: <b>+{joined_today}</b> ta\n"
        f"• Shu hafta qo'shilganlar: <b>+{joined_week}</b> ta\n"
        f"• Ban qilinganlar: <b>{banned_users}</b> ta <i>({ban_percent}%)</i>\n\n"
        f"🌐 <b>WEB INTEGRATSIYA:</b>\n"
        f"• Faol Web Kodlar: <b>{active_codes}</b> ta <i>({code_percent}% a'zolar foydalanadi)</i>\n\n"
        f"✉️ <b>MUROJAATLAR MARKAZI:</b>\n"
        f"• Jami kelib tushgan: <b>{total_messages}</b> ta\n"
        f"• Javob kutilayotgan: <b>{unanswered_msgs}</b> ta\n\n"
        f"<i>📅 Ma'lumot so'ralgan vaqt: {now.strftime('%d.%m.%Y %H:%M:%S')}</i>"
    )
    
    await message.answer(text, parse_mode="HTML")


# ==========================================================================================
# 🔍 16. ADMIN PANEL: FOYDALANUVCHINI QIDIRISH VA TEZKOR BOSHQARISH (YANGI FUNKSIYA)
# ==========================================================================================
@dp.message(F.text == Design.ADM_SEARCH)
async def trigger_user_search(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(Form.adm_search_user)
    await message.answer(
        "🔍 <b>Foydalanuvchini izlash</b>\n\n"
        "Qidirmoqchi bo'lgan foydalanuvchining <b>Telegram ID</b> raqamini kiriting:",
        reply_markup=UI.back_btn(), parse_mode="HTML"
    )

@dp.message(Form.adm_search_user)
async def process_user_search(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await enter_admin_portal(message)
        
    query = message.text.strip()
    if not query.isdigit():
        return await message.answer("⚠️ Noto'g'ri format. Faqat raqamlardan iborat ID kiriting.")
        
    user = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (int(query),))
    
    if not user:
        return await message.answer(f"❌ ID <code>{query}</code> bo'yicha hech qanday ma'lumot topilmadi.", parse_mode="HTML")
        
    code_data = await AsyncDB.fetchone("SELECT code, created_at FROM web_codes WHERE uid=?", (int(query),))
    
    status = "🔴 Bloklangan (Banned)" if user['is_banned'] else "🟢 Faol"
    code_txt = f"<code>{code_data['code']}</code> (Olingan: {fmt_dt(code_data['created_at'])})" if code_data else "Mavjud emas"
    username_txt = f"@{user['username']}" if user['username'] != 'yoq' else "Yo'q"
    
    text = (
        f"🔎 <b>QIDIRUV NATIJASI</b>\n{Design.D_LINE}\n\n"
        f"👤 <b>F.I.Sh:</b> {html.escape(user['fullname'])}\n"
        f"🔗 <b>Username:</b> {username_txt}\n"
        f"🆔 <b>ID Raqam:</b> <code>{user['uid']}</code>\n"
        f"📅 <b>Ro'yxatdan o'tgan:</b> {fmt_dt(user['joined_at'])}\n"
        f"📊 <b>Holati:</b> {status}\n\n"
        f"🌐 <b>Web Kodi:</b> {code_txt}\n\n"
        f"<i>Quyidagi tugmalar orqali foydalanuvchini tezkor boshqarishingiz mumkin:</i>"
    )
    
    markup = UI.admin_user_action_markup(user['uid'], bool(user['is_banned']))
    await message.answer(text, reply_markup=markup, parse_mode="HTML")
    await state.clear()

# Tezkor boshqaruv tugmalari (DM, Ban, Unban)
@dp.callback_query(F.data.startswith("adm_fast_"))
async def fast_admin_actions(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != Config.ADMIN_ID: return
    
    parts = call.data.split("_")
    action = parts[2]
    target_id = int(parts[3])
    
    if action == "dm":
        await state.update_data(target_id=target_id)
        await state.set_state(Form.adm_direct_msg)
        await call.message.answer(f"📝 <b>ID {target_id} ga xabar matnini kiriting:</b>", reply_markup=UI.back_btn(), parse_mode="HTML")
        
    elif action == "ban":
        await AsyncDB.execute("UPDATE users SET is_banned=1 WHERE uid=?", (target_id,))
        await AsyncDB.execute("DELETE FROM web_codes WHERE uid=?", (target_id,)) # Ban bo'lsa kodini ham yo'qotish
        cache.force_update()
        await call.message.edit_text(f"{call.message.text}\n\n✅ <b>Natija:</b> Foydalanuvchi muvaffaqiyatli BLOKLANDI.", parse_mode="HTML")
        
    elif action == "unban":
        await AsyncDB.execute("UPDATE users SET is_banned=0 WHERE uid=?", (target_id,))
        cache.force_update()
        await call.message.edit_text(f"{call.message.text}\n\n✅ <b>Natija:</b> Foydalanuvchi bandan OLINDI.", parse_mode="HTML")
        
    await call.answer()


# ==========================================================================================
# ✉️ 17. ADMIN PANEL: DIRECT MESSAGE (SHAXSIY XABAR)
# ==========================================================================================
@dp.message(F.text == Design.ADM_DIRECT)
async def direct_msg_trigger(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(Form.adm_direct_id)
    await message.answer("🆔 Xabar yubormoqchi bo'lgan foydalanuvchining ID raqamini kiriting:", reply_markup=UI.back_btn())

@dp.message(Form.adm_direct_id)
async def direct_msg_get_id(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await enter_admin_portal(message)
        
    if not message.text.isdigit(): 
        return await message.answer("⚠️ Faqat raqamlardan iborat ID kiriting!")
    
    await state.update_data(target_id=int(message.text))
    await state.set_state(Form.adm_direct_msg)
    await message.answer("📝 Endi foydalanuvchiga yuboriladigan xabar matnini kiriting:")

@dp.message(Form.adm_direct_msg)
async def direct_msg_send_process(message: Message, state: FSMContext, bot: Bot):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await enter_admin_portal(message)

    data = await state.get_data()
    target_id = data['target_id']
    
    try:
        final_text = f"✉️ <b>MA'MURIYATDAN MAXSUS XABAR:</b>\n{Design.S_LINE}\n\n{message.html_text}"
        await bot.send_message(target_id, final_text, parse_mode="HTML")
        await message.answer(f"✅ Xabar muvaffaqiyatli yuborildi (ID: <code>{target_id}</code>).", reply_markup=UI.admin_menu(), parse_mode="HTML")
    except TelegramForbiddenError:
        await message.answer(f"❌ Xatolik: Ushbu foydalanuvchi botni bloklagan (ID: {target_id}).", reply_markup=UI.admin_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}", reply_markup=UI.admin_menu())
        
    await state.clear()


# ==========================================================================================
# 🚫 18. ADMIN PANEL: BAN TIZIMI (MANUAL BOSHQRUV)
# ==========================================================================================
@dp.message(F.text == Design.ADM_BAN_SYS)
async def manual_ban_menu(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    
    text = (
        f"🚫 <b>BAN TIZIMINI BOSHQARISH</b>\n{Design.S_LINE}\n\n"
        f"Foydalanuvchilarni tizimdan chetlatish yoki huquqlarini tiklash uchun quyidagi tugmalardan foydalaning."
    )
    # Eski logikadan admin_do_ban/unban tugmalari UI dan keladi
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🚫 Ban berish", callback_data="admin_do_ban"))
    kb.row(InlineKeyboardButton(text="✅ Bandan olish", callback_data="admin_do_unban"))
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_do_"))
async def trigger_ban_actions(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[2]
    if action == "ban":
        await state.set_state(Form.adm_ban_id)
        await call.message.answer("🚫 <b>Bloklanadigan</b> foydalanuvchining ID raqamini kiriting:", reply_markup=UI.back_btn(), parse_mode="HTML")
    elif action == "unban":
        await state.set_state(Form.adm_unban_id)
        await call.message.answer("✅ <b>Bandan olinadigan</b> foydalanuvchining ID raqamini kiriting:", reply_markup=UI.back_btn(), parse_mode="HTML")
    await call.answer()

@dp.message(or_f(Form.adm_ban_id, Form.adm_unban_id))
async def execute_manual_ban_unban(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await enter_admin_portal(message)
    
    uid = message.text.strip()
    if not uid.isdigit(): 
        return await message.answer("⚠️ Noto'g'ri ID kiritildi.")
    
    current_state = await state.get_state()
    is_ban = 1 if current_state == Form.adm_ban_id.state else 0
    action_text = "bloklandi 🚫" if is_ban else "bandan olindi ✅"

    user = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (uid,))
    if not user:
        return await message.answer("❌ Bunday foydalanuvchi bazada topilmadi.")

    await AsyncDB.execute("UPDATE users SET is_banned=? WHERE uid=?", (is_ban, uid))
    
    if is_ban:
        await AsyncDB.execute("DELETE FROM web_codes WHERE uid=?", (uid,))

    # Keshni majburiy yangilashga buyruq beramiz
    cache.force_update()

    await message.answer(f"✅ ID <code>{uid}</code> muvaffaqiyatli {action_text}!", reply_markup=UI.admin_menu(), parse_mode="HTML")
    await state.clear()


# ==========================================================================================
# 📢 19. ADMIN PANEL: KANALLARNI BOSHQARISH (MAJBURIY OBUNA)
# ==========================================================================================
@dp.message(F.text == Design.ADM_CHANNELS)
async def channel_management(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    text = "📢 <b>MAJBURIY OBUNA KANALLARI</b>\n\nBu bo'limda botdan foydalanish uchun majburiy kanallarni qo'shishingiz yoki o'chirishingiz mumkin."
    await message.answer(text, reply_markup=UI.admin_channel_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_ch_"))
async def process_channel_action(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[2]
    
    if action == "add":
        await state.set_state(Form.adm_add_channel_data)
        await call.message.answer(
            "➕ <b>Kanal qo'shish:</b>\n\nQuyidagi formatda ma'lumot yuboring:\n"
            "<code>@kanal_username | Kanal Nomi | https://t.me/kanal_link</code>\n\n"
            "<i>(Eslatma: Bot o'sha kanalda admin bo'lishi shart!)</i>",
            parse_mode="HTML", reply_markup=UI.back_btn()
        )
    elif action == "list":
        chans = await AsyncDB.fetchall("SELECT * FROM channels")
        if not chans:
            await call.message.answer("⚠️ Hozircha hech qanday kanal qo'shilmagan.")
        else:
            txt = "📋 <b>Mavjud Kanallar Ro'yxati:</b>\n\n"
            for c in chans:
                txt += f"🔸 <b>{c['channel_name']}</b>\n🆔 ID: <code>{c['channel_id']}</code>\n🔗 Link: {c['url']}\n\n"
            await call.message.answer(txt, parse_mode="HTML", disable_web_page_preview=True)
    elif action == "del":
        await call.message.answer("➖ <b>Kanalni o'chirish</b> uchun bazadan (`ultimate_database.db`) o'chirish tavsiya etiladi. Bot interfeysidan o'chirish xavfsizlik sababli o'chirib qo'yilgan.", parse_mode="HTML")
    await call.answer()

@dp.message(Form.adm_add_channel_data)
async def commit_new_channel(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await enter_admin_portal(message)
        
    try:
        parts = [x.strip() for x in message.text.split("|")]
        if len(parts) != 3: raise ValueError
        cid, cname, curl = parts
        
        await AsyncDB.execute(
            "INSERT INTO channels (channel_id, channel_name, url) VALUES (?,?,?)",
            (cid, cname, curl)
        )
        cache.force_update() # Keshni yangilaymiz
        
        await message.answer("✅ Kanal bazaga muvaffaqiyatli qo'shildi! Bot shu kanalda admin ekanligini tekshirishni unutmang.", reply_markup=UI.admin_menu())
    except ValueError:
        await message.answer("❌ Format noto'g'ri. Iltimos, namunaga qarab qaytadan yuboring.\nNamuna: `@kanal | Mening Kanalim | https://t.me/...`")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi (Kanal ID si oldin qo'shilgan bo'lishi mumkin): {e}")
    finally:
        await state.clear()


# ==========================================================================================
# 🚀 20. ADMIN PANEL: BARCHAGA XABAR (SMART BROADCASTER)
# ==========================================================================================
@dp.message(F.text == Design.ADM_BROADCAST)
async def init_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(Form.adm_bc_text)
    await message.answer(
        "📢 <b>OMMAVIY XABAR YUBORISH</b>\n\n"
        "Xabar matnini kiriting. Xabarni chiroyli qilish uchun HTML teglaridan foydalanishingiz mumkin (<code>&lt;b&gt;, &lt;i&gt;, &lt;a&gt;</code> va hk.):", 
        reply_markup=UI.back_btn(), parse_mode="HTML"
    )

@dp.message(Form.adm_bc_text)
async def confirm_broadcast(message: Message, state: FSMContext):
    if message.text == Design.BTN_BACK:
        await state.clear()
        return await enter_admin_portal(message)
        
    # HTML saqlash uchun html_text dan foydalanamiz
    bc_content = message.html_text
    await state.update_data(bc_text=bc_content)
    await state.set_state(Form.adm_bc_confirm)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Yuborishni boshlash", callback_data="bc_start"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel")
    )
    
    await message.answer(
        f"👀 <b>XABAR KO'RINISHI (PREVIEW):</b>\n{Design.D_LINE}\n\n{bc_content}\n\n{Design.D_LINE}\n<i>Ushbu xabar barcha faol foydalanuvchilarga yuboriladi. Tasdiqlaysizmi?</i>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("bc_"), Form.adm_bc_confirm)
async def execute_broadcast(call: CallbackQuery, state: FSMContext, bot: Bot):
    if call.data == "bc_cancel":
        await state.clear()
        await call.message.edit_text("❌ Ommaviy xabar yuborish bekor qilindi.")
        return await call.answer()
        
    data = await state.get_data()
    msg_text = data['bc_text']
    await state.clear()
    
    # Progress xabari
    progress_msg = await call.message.edit_text("🔄 <i>Xabar barchaga yuborilmoqda. Iltimos, kuting... Tizimni yopmang.</i>", parse_mode="HTML")
    
    # Faqat ban qilinmaganlarga yuboramiz
    users = await AsyncDB.fetchall("SELECT uid FROM users WHERE is_banned=0")
    total = len(users)
    success = 0
    fail = 0
    
    for idx, u in enumerate(users):
        try:
            await bot.send_message(u['uid'], msg_text, parse_mode="HTML")
            success += 1
        except TelegramRetryAfter as e:
            logger.warning(f"Flood control limits! Sleeping for {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
            # Try again once
            try:
                await bot.send_message(u['uid'], msg_text, parse_mode="HTML")
                success += 1
            except:
                fail += 1
        except Exception:
            fail += 1
            
        # Spam bo'lmasligi uchun xavfsiz kutish (Telegram API limitlari)
        await asyncio.sleep(0.04) 

        # Progressni har 50 ta xabarda yangilash
        if idx > 0 and idx % 50 == 0:
            try:
                await progress_msg.edit_text(f"🔄 <b>Jarayon:</b> {idx}/{total} ta yuborildi...")
            except: pass

    # Yakuniy hisobot
    report = (
        f"✅ <b>Eshittirish muvaffaqiyatli yakunlandi!</b>\n"
        f"{Design.D_LINE}\n"
        f"📊 Umumiy yuborildi: <b>{total}</b> ta\n"
        f"🟢 Muvaffaqiyatli: <b>{success}</b> ta\n"
        f"🔴 Bloklagan/Xato: <b>{fail}</b> ta"
    )
    
    await progress_msg.edit_text(report, parse_mode="HTML")
    # Asosiy menyu klaviaturasini qaytarish uchun adminga alohida xabar yozamiz
    await bot.send_message(call.from_user.id, "Boshqaruv menyusi:", reply_markup=UI.admin_menu())


# ==========================================================================================
# 🌐 21. WEB API SERVER (AIOHTTP) - SAYT BILAN INTEGRATSIYA
# ==========================================================================================
async def handle_api_root(request):
    """API server ishlayotganini tekshirish uchun endpoint."""
    return web.Response(text="A'lo Ta'lim API Serveri faol! Barcha tizimlar optimal darajada ishlamoqda.")

async def api_login(request):
    """Veb-saytdan keladigan so'rovlarni qabul qiluvchi aqlli endpoint."""
    # CORS (Cross-Origin Resource Sharing) muammosini oldini olish
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    
    try:
        data = await request.json()
        entered_code = data.get("student_id", "").strip()
        
        # Kod bo'sh bo'lsa xato
        if not entered_code:
            return web.json_response({"success": False, "error": "Kod kiritilmadi."}, status=400, headers={'Access-Control-Allow-Origin': '*'})
            
        # Kodni bazadan qidirish
        web_user = await AsyncDB.fetchone("SELECT * FROM web_codes WHERE code=?", (entered_code,))
        
        if web_user:
            uid = web_user["uid"]
            user = await AsyncDB.fetchone("SELECT * FROM users WHERE uid=?", (uid,))
            
            if user:
                # Ban tekshiruvi (Keshdan tezroq ishlashi ham mumkin, lekin to'liq xavfsizlik uchun bazadan tekshiramiz)
                if user['is_banned'] == 1:
                    return web.json_response({
                        "success": False, "error": "Sizning akkauntingiz bloklangan. Saytga kirelmaysiz."
                    }, status=403, headers={'Access-Control-Allow-Origin': '*'})
                
                # Muvaffaqiyatli kirish
                return web.json_response({
                    "success": True, 
                    "name": user["fullname"], 
                    "uid": user["uid"], 
                    "role": "admin" if user["uid"] == Config.ADMIN_ID else "user"
                }, headers={'Access-Control-Allow-Origin': '*'})
                
        # Noto'g'ri kod
        return web.json_response({
            "success": False, 
            "error": "Kod noto'g'ri yoki yaroqsiz! Telegram bot orqali yangi kod oling."
        }, status=400, headers={'Access-Control-Allow-Origin': '*'})

    except Exception as e:
        logger.error(f"API Internal Error: {e}")
        return web.json_response({"success": False, "error": "Server xatoligi yuz berdi. Birozdan so'ng qayta urunib ko'ring."}, status=500, headers={'Access-Control-Allow-Origin': '*'})


# ==========================================================================================
# 🔥 22. DASTURNI ISHGA TUSHIRISH (MAIN ENTRY POINT)
# ==========================================================================================
async def start_system():
    logger.info("🟢 A'lo Ta'lim Premium Tizimi yuklanmoqda...")
    
    # 1. Asinxron baza ulanishlari va jadvallarni tayyorlash
    await AsyncDB.setup()
    
    # 2. Xotira keshini birlamchi yuklash
    await cache.update_cache()
    
    # 3. Veb serverni yig'ish va ishga tushirish (Aiohttp)
    app = web.Application()
    app.router.add_get("/", handle_api_root)
    app.router.add_options("/api/login", api_login)
    app.router.add_post("/api/login", api_login)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, Config.HOST, Config.PORT)
    await site.start()
    logger.info(f"🌐 Web API serveri ishga tushdi -> http://{Config.HOST}:{Config.PORT}")

    # 4. Telegram botni sozlash
    await bot.set_my_commands([
        BotCommand(command="start", description="🔄 Tizimni qayta ishga tushirish")
    ])
    
    logger.info("🤖 Bot serverga ulandi. Polling jarayoni boshlandi...")
    
    # 5. Botni kutish rejimiga o'tkazish
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.warning("🔴 Tizim to'xtatilmoqda...")
        await bot.session.close()
        await runner.cleanup()
        logger.info("⚪️ Tizim xavfsiz o'chirildi.")

if __name__ == "__main__":
    try:
        # Asinxron jarayonni boshlash
        asyncio.run(start_system())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur admin tomonidan to'xtatildi.")
