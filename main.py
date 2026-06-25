import asyncio
import logging
import os
import sqlite3
import html
import random
from datetime import datetime
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
# 💎 PREMIUM KONFIGURATSIYA
# ==========================================================================================
class Assets:
    TOKEN: Final[str] = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: Final[int] = int(os.getenv("ADMIN_ID", "0") or "0")
    DB_NAME: Final[str] = os.getenv("DB_NAME", "database.db")

    D_LINE = "<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>"
    S_LINE = "<b>────────────────────</b>"

    # Tugmalar nomlari
    ICO_WEB = "🌐 Saytga kirish kodi"
    ICO_HELP = "🆘 Adminga xabar yo'llash"
    ICO_PROF = "👤 Shaxsiy Kabinet"
    ICO_BACK = "⬅️ Orqaga"
    ICO_HOME = "🏠 Asosiy Menyu"
    ICO_ADM = "🛠 Admin Boshqaruvi"

    # Admin tugmalari
    ADM_STATS = "📊 Statistika"
    ADM_BROADCAST = "📢 Barchaga Xabar Yo'llash"


logging.basicConfig(level=logging.INFO)
bot = Bot(token=Assets.TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==========================================================================================
# 🗄 MA'LUMOTLAR BAZASI TIZIMI (YANGILANGAN VA OPTIMALLASHTIRILGAN)
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
            # Foydalanuvchilar jadvali
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid INTEGER PRIMARY KEY,
                    fullname TEXT,
                    username TEXT,
                    joined_at TIMESTAMP
                )
            """)
            # Veb sayt uchun 4 xonali kirish kodlari
            c.execute("""
                CREATE TABLE IF NOT EXISTS web_codes (
                    uid INTEGER PRIMARY KEY,
                    code TEXT UNIQUE,
                    created_at TIMESTAMP
                )
            """)
            # Adminga yuborilgan murojaatlar tarixi
            c.execute("""
                CREATE TABLE IF NOT EXISTS support_messages (
                    mid INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER,
                    message_text TEXT,
                    created_at TIMESTAMP,
                    is_replied INTEGER DEFAULT 0
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
# 🧠 STATES (HOLATLAR)
# ==========================================================================================
class Form(StatesGroup):
    reg = State()             # Ro'yxatdan o'tish
    support = State()         # Adminga xabar yozish holati
    adm_reply = State()       # Admin javob yozish holati
    adm_broadcast = State()   # Barchaga xabar yozish holati
    adm_confirm_bc = State()  # Barchaga xabarni tasdiqlash holati


# ==========================================================================================
# 🎨 KLAVIATURA VA UI
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
        b.row(KeyboardButton(text=Assets.ADM_STATS), KeyboardButton(text=Assets.ADM_BROADCAST))
        b.row(KeyboardButton(text=Assets.ICO_HOME))
        b.adjust(2, 1)
        return b.as_markup(resize_keyboard=True)

    @staticmethod
    def back_btn():
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=Assets.ICO_BACK)]],
            resize_keyboard=True
        )


# ==========================================================================================
# YORDAMCHI FUNKSIYALAR
# ==========================================================================================
def fmt_dt(value: Optional[str]) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(value)[:16]


# Majburiy obuna kanallari (agar kerak bo'lsa sozlash mumkin)
REQUIRED_CHANNELS = [
    {"name": "📢 Rasmiy Kanal", "id": "@Alo_math"},
]

async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not REQUIRED_CHANNELS:
        return True
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if member.status in ['left', 'kicked', 'banned']:
                return False
        except Exception:
            return False 
    return True

def get_subscription_keyboard():
    builder = InlineKeyboardBuilder()
    for channel in REQUIRED_CHANNELS:
        url = f"[https://t.me/](https://t.me/){channel['id'].replace('@', '')}"
        builder.row(InlineKeyboardButton(text=channel["name"], url=url))
    builder.row(InlineKeyboardButton(text="✅ Obunani Tasdiqlash", callback_data="check_subscription"))
    return builder.as_markup()


# Foydalanuvchini tizimga kiritish jarayoni
async def process_user_entry(message: Message, state: FSMContext, user_id: int, user_firstname: str):
    DB.setup()
    user = DB.run("SELECT * FROM users WHERE uid=?", (user_id,), fetch="one")

    if not user:
        await state.set_state(Form.reg)
        text = (
            f"🌟 <b>A'LO TA'LIM PLATFORMASI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 Assalomu alaykum, <b>{html.escape(user_firstname)}</b>!\n"
            f"Bizning integratsiyalashgan platformamizga xush kelibsiz.\n\n"
            f"✍️ <i>Tizimdan foydalanish uchun ism va familiyangizni kiriting:</i>\n\n"
            f"💡 <b>Namuna:</b> <i>Abdurahmon Alimov</i>"
        )
        await message.answer(text, parse_mode="HTML")
    else:
        dashboard = (
            f"👑 <b>ASOSIY TIZIM PANELI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Foydalanuvchi: <b>{html.escape(user['fullname'])}</b>\n"
            f"🎖 Maqom: <b>Tizim A'zosi</b>\n\n"
            f"📅 Bugun: <b>{datetime.now().strftime('%d.%m.%Y')}</b>\n"
            f"🕒 Vaqt: <b>{datetime.now().strftime('%H:%M')}</b>\n\n"
            f"👇 <i>Quyidagi menyudan kerakli xizmatni tanlang:</i>"
        )
        await message.answer(dashboard, reply_markup=UI.main_menu(user_id), parse_mode="HTML")


# ==========================================================================================
# ASOSIY START / RESET HANDLERLARI
# ==========================================================================================
@dp.message(or_f(Command("start"), F.text == Assets.ICO_HOME, F.text == Assets.ICO_BACK))
async def global_reset(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    subscribed = await is_subscribed(bot, message.from_user.id)

    if not subscribed:
        text = (
            f"🛑 <b>DIQQAT! Botdan foydalanish uchun a'zo bo'ling!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Tizim xizmatlaridan va Saytga kirish kodidan foydalanish uchun kanalimizga a'zo bo'lishingiz lozim.\n\n"
            f"<i>A'zo bo'lgach, pastdagi <b>«✅ Obunani Tasdiqlash»</b> tugmasini bosing.</i>"
        )
        await message.answer(text, reply_markup=get_subscription_keyboard(), parse_mode="HTML")
        return

    await process_user_entry(message, state, message.from_user.id, message.from_user.first_name)


@dp.callback_query(F.data == "check_subscription")
async def check_sub_handler(call: CallbackQuery, state: FSMContext, bot: Bot):
    subscribed = await is_subscribed(bot, call.from_user.id)

    if not subscribed:
        await call.answer("❌ Siz hali obuna bo'lmadingiz! Iltimos, kanalimizga a'zo bo'ling.", show_alert=True)
        return

    await call.message.delete()
    await process_user_entry(call.message, state, call.from_user.id, call.from_user.first_name)


# Ro'yxatdan o'tishni yakunlash
@dp.message(Form.reg)
async def registration_finish(message: Message, state: FSMContext):
    fullname = message.text.strip()
    if len(fullname) < 4 or " " not in fullname:
        return await message.answer(
            "⚠️ <b>Iltimos, ism va familiyangizni to'liq kiriting!</b>\n"
            "Masalan: <i>Abdurahmon Alimov</i>",
            parse_mode="HTML"
        )

    DB.run(
        "INSERT OR REPLACE INTO users (uid, fullname, username, joined_at) VALUES (?,?,?,?)",
        (message.from_user.id, fullname, message.from_user.username, datetime.now().isoformat())
    )
    
    success_text = (
        f"🎉 <b>Muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hurmatli <b>{html.escape(fullname)}</b>, tizimga xush kelibsiz! 🚀\n"
        f"Sizga o'z xizmatlarimizni taklif qilishdan mamnunmiz.\n\n"
        f"👇 <i>Kerakli bo'limni tanlang:</i>"
    )
    
    await message.answer(
        success_text,
        parse_mode="HTML",
        reply_markup=UI.main_menu(message.from_user.id)
    )
    await state.clear()


# ==========================================================================================
# 🌐 SAYTGA KIRISH KODI (KUCHAYTIRILGAN FUNKSIYA - 4 XONALI KOD)
# ==========================================================================================
def generate_unique_code() -> str:
    # Faqat 4 xonali kod yaratadi va takrorlanmasligini nazorat qiladi
    while True:
        code = f"{random.randint(1000, 9999)}"
        check = DB.run("SELECT uid FROM web_codes WHERE code=?", (code,), fetch="one")
        if not check:
            return code

def get_web_code_markup(has_code: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_code:
        kb.row(
            InlineKeyboardButton(text="🔄 Kodni Yangilash", callback_data="web_code_regenerate"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data="web_code_delete")
        )
    else:
        kb.row(
            InlineKeyboardButton(text="🔑 Yangi Kod Yaratish", callback_data="web_code_generate")
        )
    return kb.as_markup()

@dp.message(F.text == Assets.ICO_WEB)
async def view_web_code(message: Message):
    user_id = message.from_user.id
    row = DB.run("SELECT * FROM web_codes WHERE uid=?", (user_id,), fetch="one")
    
    if row:
        text = (
            f"🌐 <b>SIZNING VEB-SAYTGA KIRISH KODINGIZ</b>\n"
            f"{Assets.D_LINE}\n\n"
            f"🔑 Maxfiy Kod: <span class='tg-spoiler'><b>{row['code']}</b></span> (Ushbu kodni bosib tursangiz nusxalanadi: <code>{row['code']}</code>)\n"
            f"📅 Yaratilgan vaqt: <b>{fmt_dt(row['created_at'])}</b>\n\n"
            f"⚠️ <i>Xavfsizlik maqsadida ushbu kodni begonalarga ko'rsatmang. Agarda kodingiz oshkor bo'lgan bo'lsa, quyidagi tugma orqali uni yangilashingiz mumkin.</i>"
        )
        await message.answer(text, reply_markup=get_web_code_markup(True), parse_mode="HTML")
    else:
        text = (
            f"🌐 <b>VEB-SAYTGA INTEGRATSIYA</b>\n"
            f"{Assets.D_LINE}\n\n"
            f"Sizda hali saytga kirish uchun maxsus kod mavjud emas.\n"
            f"Saytda muvaffaqiyatli avtorizatsiyadan o'tish uchun quyidagi tugma orqali o'zingizning 4 xonali shaxsiy kodingizni yarating."
        )
        await message.answer(text, reply_markup=get_web_code_markup(False), parse_mode="HTML")


@dp.callback_query(F.data == "web_code_generate")
async def generate_code_cb(call: CallbackQuery):
    user_id = call.from_user.id
    # Kod mavjudligini qayta tekshiramiz
    existing = DB.run("SELECT code FROM web_codes WHERE uid=?", (user_id,), fetch="one")
    if existing:
        return await call.answer("Sizda allaqachon kod mavjud!", show_alert=True)
        
    code = generate_unique_code()
    DB.run(
        "INSERT INTO web_codes (uid, code, created_at) VALUES (?, ?, ?)",
        (user_id, code, datetime.now().isoformat())
    )
    
    await call.message.edit_text(
        f"🎉 <b>YANGI KIRISH KODI YARATILDI!</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"🔑 Kod: <code>{code}</code>\n"
        f"📅 Sana: <b>{fmt_dt(datetime.now().isoformat())}</b>\n\n"
        f"<i>Ushbu 4 xonali kod orqali veb-saytimizga kirishingiz mumkin. Uni xavfsiz saqlang!</i>",
        reply_markup=get_web_code_markup(True),
        parse_mode="HTML"
    )
    await call.answer("Kod yaratildi!", show_alert=False)


@dp.callback_query(F.data == "web_code_regenerate")
async def regenerate_code_cb(call: CallbackQuery):
    user_id = call.from_user.id
    code = generate_unique_code()
    
    DB.run(
        "INSERT OR REPLACE INTO web_codes (uid, code, created_at) VALUES (?, ?, ?)",
        (user_id, code, datetime.now().isoformat())
    )
    
    await call.message.edit_text(
        f"🔄 <b>KIRISH KODI YANGILANDI!</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"🔑 Yangi Kod: <code>{code}</code>\n"
        f"📅 Sana: <b>{fmt_dt(datetime.now().isoformat())}</b>\n\n"
        f"⚠️ <i>Eski kodingiz o'z kuchini yo'qotdi. Endi faqat yangi kod ishlaydi.</i>",
        reply_markup=get_web_code_markup(True),
        parse_mode="HTML"
    )
    await call.answer("Kod yangilandi!", show_alert=True)


@dp.callback_query(F.data == "web_code_delete")
async def delete_code_cb(call: CallbackQuery):
    user_id = call.from_user.id
    DB.run("DELETE FROM web_codes WHERE uid=?", (user_id,))
    
    await call.message.edit_text(
        f"🗑 <b>KIRISH KODI MUVAFFAQIYATLI O'CHIRILDI!</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"Sizning shaxsiy kirish kodingiz o'chirib tashlandi. Endi ushbu profil yordamida saytga kirib bo'lmaydi.\n"
        f"Istalgan vaqtda qaytadan yangi kod yaratishingiz mumkin.",
        reply_markup=get_web_code_markup(False),
        parse_mode="HTML"
    )
    await call.answer("Kirish kodi o'chirildi!", show_alert=True)


# ==========================================================================================
# 🆘 ADMINGA XABAR YO'LLASH (KUCHAYTIRILGAN ALOQA TIZIMI)
# ==========================================================================================
@dp.message(F.text == Assets.ICO_HELP)
async def support_start(message: Message, state: FSMContext):
    await state.set_state(Form.support)
    text = (
        f"📬 <b>ADMINISTRATSIYA BILAN ALOQA</b>\n"
        f"{Assets.S_LINE}\n\n"
        f"Sizda takliflar, shikoyatlar yoki texnik muammolar bormi?\n"
        f"Xabaringizni batafsil yozib shu yerga yuboring.\n\n"
        f"✍️ <i>Murojaat matnini kiriting:</i>"
    )
    await message.answer(text, reply_markup=UI.back_btn(), parse_mode="HTML")


@dp.message(Form.support)
async def support_sent(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    text = message.text or ""

    if len(text) < 5:
        return await message.answer("⚠️ Xabar juda qisqa! Iltimos, batafsilroq yozing.")

    # Ma'lumotlar bazasida xabarni saqlash
    mid = DB.run(
        "INSERT INTO support_messages (uid, message_text, created_at) VALUES (?, ?, ?)",
        (user_id, text, datetime.now().isoformat())
    )

    # Adminga yuboriladigan chiroyli interaktiv xabar
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✍️ Javob Yozish", callback_data=f"reply_{user_id}_{mid}"),
        InlineKeyboardButton(text="👤 Profil", callback_data=f"view_profile_{user_id}")
    )

    admin_msg = (
        f"🆕 <b>YANGI MUROJAAT (ID: #{mid})</b>\n"
        f"{Assets.D_LINE}\n"
        f"👤 Kimdan: <b>{html.escape(user_name)}</b>\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"🕒 Vaqt: <b>{fmt_dt(datetime.now().isoformat())}</b>\n\n"
        f"💬 <b>Xabar matni:</b>\n"
        f"<i>{html.escape(text)}</i>\n"
        f"{Assets.D_LINE}"
    )

    try:
        await bot.send_message(
            Assets.ADMIN_ID,
            admin_msg,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xatolik: {e}")

    await message.answer(
        "✅ <b>Xabaringiz administratorga muvaffaqiyatli yetkazildi!</b>\nTez orada sizga javob qaytaramiz.",
        reply_markup=UI.main_menu(message.from_user.id),
        parse_mode="HTML"
    )
    await state.clear()


@dp.callback_query(F.data.startswith("reply_"))
async def admin_reply_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != Assets.ADMIN_ID:
        return await call.answer("Siz admin emassiz!", show_alert=True)

    parts = call.data.split("_")
    target_id = parts[1]
    mid = parts[2]

    await state.update_data(reply_to=target_id, message_id=mid)
    await state.set_state(Form.adm_reply)

    await call.message.answer(
        f"📝 <b>Foydalanuvchiga javob yozing:</b>\n"
        f"Foydalanuvchi ID: <code>{target_id}</code>\n"
        f"Murojaat ID: <code>#{mid}</code>",
        reply_markup=UI.back_btn(),
        parse_mode="HTML"
    )
    await call.answer()


@dp.message(Form.adm_reply)
async def admin_reply_sent(message: Message, state: FSMContext):
    if message.from_user.id != Assets.ADMIN_ID:
        return

    data = await state.get_data()
    target_id = data.get("reply_to")
    mid = data.get("message_id")
    reply_text = message.text or ""

    if reply_text == Assets.ICO_BACK:
        await state.clear()
        return await message.answer("Bekor qilindi.", reply_markup=UI.admin_menu())

    try:
        # Foydalanuvchiga javobni yuborish
        user_msg = (
            f"📩 <b>ADMINISTRATSIYADAN JAVOB:</b>\n"
            f"{Assets.D_LINE}\n\n"
            f"{html.escape(reply_text)}\n\n"
            f"<i>Sizning #{mid}-sonli murojaatingiz yuzasidan.</i>\n"
            f"{Assets.D_LINE}"
        )
        await bot.send_message(int(target_id), user_msg, parse_mode="HTML")
        
        # Bazada xabarni "javob berildi" holatiga o'tkazish
        DB.run("UPDATE support_messages SET is_replied=1 WHERE mid=?", (mid,))

        await message.answer("✅ Javobingiz foydalanuvchiga muvaffaqiyatli yuborildi.", reply_markup=UI.admin_menu(), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi, yuborish imkoni bo'lmadi:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")

    await state.clear()


@dp.callback_query(F.data.startswith("view_profile_"))
async def view_user_profile_admin(call: CallbackQuery):
    if call.from_user.id != Assets.ADMIN_ID: return
    user_id = call.data.split("_")[2]
    
    user = DB.run("SELECT * FROM users WHERE uid=?", (user_id,), fetch="one")
    code_row = DB.run("SELECT code FROM web_codes WHERE uid=?", (user_id,), fetch="one")
    msg_count = DB.run("SELECT COUNT(*) as c FROM support_messages WHERE uid=?", (user_id,), fetch="one")["c"]

    if not user:
        return await call.answer("Foydalanuvchi ma'lumotlari topilmadi.", show_alert=True)

    profile_text = (
        f"👤 <b>FOYDALANUVCHI PROFILI</b>\n"
        f"{Assets.D_LINE}\n"
        f"Ism: <b>{html.escape(user['fullname'])}</b>\n"
        f"Username: @{user['username'] if user['username'] else 'yoqtirgan'}\n"
        f"ID: <code>{user['uid']}</code>\n"
        f"Kirgan sanasi: <b>{fmt_dt(user['joined_at'])}</b>\n"
        f"Kirish kodi: <code>{code_row['code'] if code_row else 'Yaratilmagan'}</code>\n"
        f"Jami murojaatlar: <b>{msg_count} ta</b>\n"
        f"{Assets.S_LINE}"
    )
    await call.message.reply(profile_text, parse_mode="HTML")
    await call.answer()


# ==========================================================================================
# 👤 SHAXSIY KABINET
# ==========================================================================================
@dp.message(F.text == Assets.ICO_PROF)
async def profile(message: Message):
    u = DB.run("SELECT * FROM users WHERE uid=?", (message.from_user.id,), fetch="one")
    if not u:
        return await message.answer("⚠️ Profil topilmadi. /start buyrug'ini bering.", parse_mode="HTML")

    code_row = DB.run("SELECT code FROM web_codes WHERE uid=?", (message.from_user.id,), fetch="one")
    code_status = f"<code>{code_row['code']}</code>" if code_row else "<i>Yaratilmagan</i>"

    p_text = (
        f"👤 <b>SHAXSIY KABINETINGIZ</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"👤 F.I.Sh: <b>{html.escape(u['fullname'])}</b>\n"
        f"🆔 Sizning ID: <code>{u['uid']}</code>\n"
        f"📅 Ro'yxatdan o'tgan sana: <b>{fmt_dt(u['joined_at'])}</b>\n"
        f"🌐 Kirish kodi holati: <b>{code_status}</b>\n\n"
        f"{Assets.S_LINE}\n"
        f"<i>Veb-saytga kirish uchun maxsus kirish kodidan foydalaning.</i>"
    )
    await message.answer(p_text, parse_mode="HTML")


# ==========================================================================================
# 🛠 ADMINISTRATOR BOSHQARUVI (STATISTIKA VA KUCHAYTIRILGAN BROADCAST)
# ==========================================================================================
@dp.message(F.text == Assets.ICO_ADM)
async def admin_portal(message: Message):
    if message.from_user.id != Assets.ADMIN_ID:
        return

    status_bar = "🟢 TIZIM ONLINE | Secure Sync v5.0"
    await message.answer(
        f"⚡️ <b>ADMIN DASHBOARD</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"👑 Administrator: <b>{html.escape(message.from_user.full_name)}</b>\n"
        f"⚡️ Tizim holati: <code>{html.escape(status_bar)}</code>\n"
        f"🕒 Server vaqti: <code>{datetime.now().strftime('%H:%M:%S')}</code>\n\n"
        f"<i>Kerakli boshqaruv tugmasini tanlang 👇</i>",
        reply_markup=UI.admin_menu(),
        parse_mode="HTML"
    )


@dp.message(F.text == Assets.ADM_STATS)
async def admin_stats(message: Message):
    if message.from_user.id != Assets.ADMIN_ID: return
    
    u_count = DB.run("SELECT COUNT(*) as c FROM users", fetch="one")["c"]
    code_count = DB.run("SELECT COUNT(*) as c FROM web_codes", fetch="one")["c"]
    msg_count = DB.run("SELECT COUNT(*) as c FROM support_messages", fetch="one")["c"]
    unreplied_count = DB.run("SELECT COUNT(*) as c FROM support_messages WHERE is_replied=0", fetch="one")["c"]

    text = (
        f"📊 <b>TIZIM STATISTIKASI</b>\n"
        f"{Assets.D_LINE}\n\n"
        f"👥 Ro'yxatdan o'tgan a'zolar: <b>{u_count} ta</b>\n"
        f"🔑 Kirish kodiga ega foydalanuvchilar: <b>{code_count} ta</b>\n"
        f"💬 Jami yozilgan murojaatlar: <b>{msg_count} ta</b>\n"
        f"📥 Javobsiz qolayotgan xabarlar: <b>{unreplied_count} ta</b>\n\n"
        f"<i>Ushbu ma'lumotlar real vaqt rejimida yangilanadi.</i>"
    )
    await message.answer(text, parse_mode="HTML")


# KUCHAYTIRILGAN BROADCAST (TASDIQLASH VA PREVIEW BOSQICHI BILAN)
@dp.message(F.text == Assets.ADM_BROADCAST)
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id != Assets.ADMIN_ID: return
    await state.set_state(Form.adm_broadcast)
    await message.answer(
        f"📢 <b>BARCHAGA XABAR YUBORISH</b>\n"
        f"{Assets.S_LINE}\n\n"
        f"Yubormoqchi bo'lgan xabaringiz matnini kiriting.\n"
        f"<i>(Matnda HTML taglaridan chiroyli dizayn uchun foydalanish mumkin)</i>",
        reply_markup=UI.back_btn(),
        parse_mode="HTML"
    )

@dp.message(Form.adm_broadcast)
async def broadcast_preview(message: Message, state: FSMContext):
    if message.from_user.id != Assets.ADMIN_ID: return
    msg_text = message.text or ""
    
    if msg_text == Assets.ICO_BACK:
        await state.clear()
        return await message.answer("Bekor qilindi.", reply_markup=UI.admin_menu())

    # Xabar andozasini tayyorlash
    design_msg = (
        f"✨ <b>A'LO TA'LIM PLATFORMASI</b> ✨\n"
        f"{Assets.D_LINE}\n\n"
        f"{msg_text}\n\n"
        f"{Assets.D_LINE}\n"
        f"<i>Tizim ma'muriyati 👑</i>"
    )

    await state.update_data(broadcast_text=design_msg)
    await state.set_state(Form.adm_confirm_bc)

    # Tasdiqlash tugmalari
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ TASDIQLASH (YUBORISH)", callback_data="confirm_send_broadcast"),
        InlineKeyboardButton(text="❌ BEKOR QILISH", callback_data="cancel_broadcast")
    )

    await message.answer(
        f"👀 <b>XABAR PREVIEW (KO'RINISHI):</b>\n\n"
        f"{design_msg}\n\n"
        f"⚠️ <b>Haqiqatan ham ushbu xabarni barcha foydalanuvchilarga yuborasizmi?</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "confirm_send_broadcast", Form.adm_confirm_bc)
async def broadcast_send_action(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != Assets.ADMIN_ID: return
    
    data = await state.get_data()
    msg_text = data.get("broadcast_text")
    
    await call.message.edit_text("🔄 <i>Xabar barchaga yuborilmoqda, kuting...</i>")
    
    users = DB.run("SELECT uid FROM users", fetch="all")
    success, fail = 0, 0
    
    for u in users:
        try:
            await bot.send_message(u['uid'], msg_text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05) # Telegram spam filterlariga qarshi 50ms kechikish
        except Exception:
            fail += 1

    await call.message.answer(
        f"✅ <b>Eshittirish yakunlandi!</b>\n\n"
        f"🟢 Yetkazildi: <b>{success} ta foydalanuvchiga</b>\n"
        f"🔴 Yetkazilmadi (bloklangan): <b>{fail} ta</b>",
        reply_markup=UI.admin_menu(), 
        parse_mode="HTML"
    )
    await state.clear()
    await call.answer()


@dp.callback_query(F.data == "cancel_broadcast", Form.adm_confirm_bc)
async def broadcast_cancel_action(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🚫 Xabar yuborish bekor qilindi.", parse_mode="HTML")
    await call.answer()


# ==========================================================================================
# 🌐 INTEGRATSIYALASHGAN API WEB PORTI (faqat api_login qoldi)
# ==========================================================================================
async def api_login(request):
    # CORS muammolarisiz ulanish imkoni
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    
    try:
        data = await request.json()
        entered_code = data.get("student_id", "").strip()
        web_user = DB.run("SELECT * FROM web_codes WHERE code=?", (entered_code,), fetch="one")
        
        if web_user:
            user = DB.run("SELECT * FROM users WHERE uid=?", (web_user["uid"],), fetch="one")
            if user:
                return web.json_response({
                    "success": True, 
                    "name": user["fullname"], 
                    "uid": user["uid"], 
                    "role": "admin" if user["uid"] == Assets.ADMIN_ID else "user"
                }, headers={'Access-Control-Allow-Origin': '*'})
                
        return web.json_response({
            "success": False, 
            "error": "Tizim ID kodi noto'g'ri yoki ro'yxatda yo'q! Botimiz orqali '🌐 Saytga kirish kodi' tugmasini bosing."
        }, status=400, headers={'Access-Control-Allow-Origin': '*'})

    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500, headers={'Access-Control-Allow-Origin': '*'})


async def handle(request):
    return web.Response(text="A'lo Ta'lim Bot Integratsiyasi faol holatda!")


# ==========================================================================================
# SERVER VA POLLING START (MUKAMMALLASHTIRILGAN)
# ==========================================================================================
async def main():
    try:
        DB.setup()
        
        # Veb-server port sozlashi va API yo'llari
        app = web.Application()
        app.router.add_get("/", handle)
        app.router.add_options("/api/login", api_login)
        app.router.add_post("/api/login", api_login)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
        await site.start()

        # Bot menyu buyrug'i
        await bot.set_my_commands([
            BotCommand(command="start", description="🏠 Tizimni yuklash / start")
        ])
        
        print("💎 A'LO TA'LIM INTEGRATSIYA TIZIMI PORT 8080 DA ISHLAMOQDA...")
        await dp.start_polling(bot)
        
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
eof
