import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
from aiogram.filters import Command, StateFilter
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramForbidden

from datetime import datetime, timedelta

import config
import db  # db.py faylingiz mavjud deb faraz qilinadi

# --- Logging sozlamalari ---
logging.basicConfig(level=logging.INFO)


# --- FSM (Finite State Machine) - Holatlar sinfi ---
class OrderStates(StatesGroup):
    waiting_for_lang = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_pickup = State()
    waiting_for_destination = State()
    waiting_for_count = State()

    waiting_for_day = State()
    waiting_for_date_selection_7days = State()
    waiting_for_time = State()

    waiting_for_note = State() # Buyurtma izohi uchun holat qo'shildi deb faraz qilamiz
    waiting_for_final_confirm = State() # Yakuniy tasdiqlash uchun holat qo'shildi deb faraz qilamiz


    waiting_for_operator_reply = State()
    waiting_for_change_selection = State()
    waiting_for_new_pickup = State()
    waiting_for_new_destination = State()

    waiting_for_new_day = State()
    waiting_for_new_date_selection_7days = State()
    waiting_for_new_time = State()


# --- Utility Functions (Yordamchi Funksiyalar) ---

# Buyurtma ma'lumotlarini operatorga yuborish uchun formatlaydi.
def format_operator_message(order_info: dict) -> str:
    """Buyurtma ma'lumotlarini operatorga jo'natish uchun formatlaydi va holatni ko'rsatadi."""
    data = order_info['data']
    status = order_info.get('status', 'ACTIVE') # Status default ACTIVE bo'lsin
    order_id = data.get('order_id', 'N/A')

    # Status emojisi qo'shildi (Talab bo'yicha)
    status_emoji = "✅ ACTIVE" if status == 'ACTIVE' else "❌ BEKOR QILINGAN"

    text = (
        f"**Yangi Buyurtma ID: {order_id}**\n"
        f"**HOLAT: {status_emoji}**\n\n"
        f"👤 Mijoz ID: {data.get('user_id', 'N/A')} ({data.get('username', 'N/A')})\n"
        f"📞 Telefon: {data.get('phone', 'N/A')}\n"
        f"📍 Manzil (olish): {data.get('pickup', 'N/A')}\n"
        f"📍 Manzil (yetkazish): {data.get('destination', 'N/A')}\n"
        f"📦 Yuk soni: {data.get('count', 'N/A')}\n"
        f"📅 Kuni: {data.get('day', 'N/A')} / {data.get('date', 'N/A')}\n"
        f"⏰ Vaqti: {data.get('time', 'N/A')}\n"
        f"📝 Izoh: {data.get('note', 'N/A')}"
    )
    return text

# Mijozga yuboriladigan yakuniy xabar keyboardi
def get_client_final_keyboard(order_id: int) -> types.InlineKeyboardMarkup:
    """Mijoz uchun buyurtmani o'zgartirish va bekor qilish tugmalari."""
    keyboard = [
        [
            types.InlineKeyboardButton(text="🔄 O'zgartirish", callback_data=f"start_modification:{order_id}"), # ID qo'shildi
            # YANGI TUGMA: Bekor qilish (Talab bo'yicha)
            types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel:{order_id}"),
        ]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


# --- Handlers ---

# Buyurtmani yakunlash va operatorga yuborish (Namuna)
async def send_final_order_to_operator(message: types.Message, state: FSMContext, bot: Bot):
    """Buyurtmani yakunlash, operatorlarga yuborish va DBga saqlash (operator_message_id bilan)."""
    
    # State dan barcha ma'lumotlarni olish
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else str(user_id)

    data['user_id'] = user_id
    data['username'] = username

    # 1. Operatorga yuborish (operator_message_idni olish uchun)
    temp_order_info = {'data': data, 'status': 'ACTIVE'}
    operator_text = format_operator_message(temp_order_info)
    operator_message_id = 0

    for operator_id in config.OPERATOR_IDS:
        try:
            # Xabarni yuborish
            msg = await bot.send_message(
                chat_id=operator_id,
                text=operator_text,
                parse_mode="Markdown"
            )
            # Birinchi operator xabar ID'sini saqlash (Bekor qilish uchun bitta ID yetarli)
            if operator_message_id == 0:
                operator_message_id = msg.message_id
            logging.info(f"Operatorga buyurtma yuborildi. Msg ID: {msg.message_id}")
        except TelegramForbidden as e:
            logging.error(f"Operatorga xabar yuborish taqiqlandi. ID: {operator_id}. Xato: {e}")
        except Exception as e:
            logging.error(f"Operatorga xabar yuborishda umumiy xato: {e}")

    # 2. DBga kiritish va haqiqiy buyurtma ID'sini olish
    order_id = await db.insert_order(user_id, username, data, operator_message_id)

    if order_id > 0:
        # Buyurtma ID'sini order_info dict'ga qo'shib, operator xabarini yangilash
        data['order_id'] = order_id
        final_order_info = {'data': data, 'status': 'ACTIVE'}
        final_operator_text = format_operator_message(final_order_info)

        # Operator xabarini yangi ID bilan tahrirlash
        if operator_message_id:
             for operator_id in config.OPERATOR_IDS:
                try:
                    await bot.edit_message_text(
                        chat_id=operator_id,
                        message_id=operator_message_id,
                        text=final_operator_text,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.warning(f"Operator xabarini yakuniy ID bilan tahrirlashda xato: {e}")


        # 3. Mijozga yakuniy tasdiq xabarini yuborish (Bekor qilish tugmasi bilan)
        final_text = (
            f"✅ **Buyurtmangiz qabul qilindi!**\n"
            f"Sizning buyurtma raqamingiz: **{order_id}**.\n\n"
            f"Operatorimiz buyurtmani ko'rib chiqadi va siz bilan bog'lanadi.\n\n"
            f"Buyurtmani o'zgartirish yoki bekor qilish uchun pastdagi tugmalardan foydalaning."
        )
        await message.answer(
            final_text,
            reply_markup=get_client_final_keyboard(order_id),
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Buyurtmani saqlashda kutilmagan xato yuz berdi. Iltimos, qayta urinib ko'ring.")

    # Holatni tozalash
    await state.clear()


# YANGI HANDLER: Buyurtmani bekor qilish (Talab bo'yicha)
async def cancel_order_handler(callback: types.CallbackQuery, bot: Bot):
    """Mijoz buyurtmani bekor qilganida ishlaydigan handler."""
    # callback.data formati: cancel:<order_id>
    parts = callback.data.split(':')
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("Noto'g'ri buyurtma ID.", show_alert=True)
        return

    order_id = int(parts[1])

    # 1. DBda statusni 'CANCELLED' ga yangilash
    result = await db.update_order_status(order_id, 'CANCELLED')

    if not result:
        await callback.answer("Buyurtmani bekor qilishda xatolik yuz berdi.", show_alert=True)
        return

    user_id = result['user_id']
    operator_message_id = result['operator_message_id']

    # 2. Mijozga xabar yuborish (va tugmani olib tashlash) (Talab bo'yicha)
    try:
        await callback.message.edit_text(
            "❌ **Sizning buyurtmangiz bekor qilindi.** Agar xohlasangiz, yangi buyurtma berishingiz mumkin /start.",
            reply_markup=None,
            parse_mode="Markdown"
        )
    except TelegramBadRequest as e:
        # Xabar allaqachon tahrirlangan bo'lishi mumkin
        logging.warning(f"Mijoz buyurtma xabarini tahrirlashda xato: {e}")
        try:
            await bot.send_message(user_id, "❌ **Sizning buyurtmangiz bekor qilindi.**", parse_mode="Markdown")
        except:
             pass


    # 3. Operator xabarini yangilash (Talab bo'yicha)
    order_info = await db.get_order_info(order_id)
    if order_info and operator_message_id:
        # Tahrirlangan xabarni yaratish
        operator_text = format_operator_message(order_info)

        for operator_id in config.OPERATOR_IDS:
            try:
                await bot.edit_message_text(
                    chat_id=operator_id,
                    message_id=operator_message_id,
                    text=operator_text,
                    parse_mode="Markdown"
                )
                logging.info(f"Operator (ID: {operator_id}) xabari bekor qilish holati bilan yangilandi. Buyurtma ID: {order_id}")
            except TelegramBadRequest as e:
                logging.warning(f"Operator xabarini tahrirlashda xato (ID: {operator_id}, MsgID: {operator_message_id}): {e}")
            except TelegramForbidden as e:
                logging.error(f"Operatorga xabar yuborish taqiqlandi. ID: {operator_id}. Xato: {e}")

    await callback.answer("Buyurtma bekor qilindi.")

# Boshqa handlerlar (funktsiyalar avvalgi holatida qoldirildi, chunki to'liq kod mavjud emas)
async def start_modification(callback: types.CallbackQuery, state: FSMContext):
    # Buyurtma IDsini callback datadan olish
    parts = callback.data.split(':')
    if len(parts) == 2 and parts[1].isdigit():
        order_id = int(parts[1])
        await callback.answer(f"Buyurtma {order_id} o'zgartirilmoqda...")
    else:
        await callback.answer("O'zgartirish boshlandi (ID topilmadi).")
    await state.set_state(OrderStates.waiting_for_change_selection)


async def process_modification_selection(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer(f"Tanlov: {callback.data}")
    # ...


async def process_new_pickup(message: types.Message, state: FSMContext):
    # ...
    pass


async def process_new_destination(message: types.Message, state: FSMContext):
    # ...
    pass


async def process_new_day(message: types.Message, state: FSMContext):
    # ...
    pass


async def process_new_date_selection_7days(message: types.Message, state: FSMContext):
    # ...
    pass


async def process_new_time(message: types.Message, state: FSMContext):
    # ...
    pass

async def forward_client_to_operator(message: types.Message):
    # ...
    pass

async def send_operator_reply_to_client(message: types.Message):
    # ...
    pass

async def start(message: types.Message, state: FSMContext):
    # ...
    pass


# --- Main Logic ---

def setup_handlers(dp: Dispatcher):
    # --- START HANDLER ---
    dp.message.register(start, Command("start"), StateFilter(None))

    # --- BUYURTMA QADAMLARI HANDLERLARI (Namuna) ---
    # dp.message.register(process_name, StateFilter(OrderStates.waiting_for_name))
    # ... va hokazo ...

    # --- BUYURTMANI YAKUNLASH HANDLERI (Namuna) ---
    # Bu taxminiy holat. Buni o'z tizimingizdagi mos keladigan yakuniy holatga almashtiring.
    dp.message.register(send_final_order_to_operator, StateFilter(OrderStates.waiting_for_final_confirm))


    # --- OPERATOR JAVOBINI FORWARD QILISH HANDLERI ---
    dp.message.register(send_operator_reply_to_client, StateFilter(OrderStates.waiting_for_operator_reply),
                        lambda m: m.from_user.id in config.OPERATOR_IDS)

    # --- O'ZGARTIRISH HANDLERLARI ---
    # O'zgartirish tugmasi endi buyurtma ID'sini o'z ichiga oladi, shuning uchun checkni o'zgartiramiz
    dp.callback_query.register(start_modification, lambda c: c.data.startswith('start_modification:'))
    dp.callback_query.register(process_modification_selection, StateFilter(OrderStates.waiting_for_change_selection))
    dp.message.register(process_new_pickup, StateFilter(OrderStates.waiting_for_new_pickup))
    dp.message.register(process_new_destination, StateFilter(OrderStates.waiting_for_new_destination))

    dp.message.register(process_new_day, StateFilter(OrderStates.waiting_for_new_day))
    dp.message.register(process_new_date_selection_7days, StateFilter(OrderStates.waiting_for_new_date_selection_7days))
    dp.message.register(process_new_time, StateFilter(OrderStates.waiting_for_new_time))

    # YANGI HANDLER: Buyurtmani bekor qilish (Talab bo'yicha)
    dp.callback_query.register(cancel_order_handler, lambda c: c.data.startswith('cancel:'))

    # --- MIJOZ JAVOBINI FORWARD QILISH (Operator bo'lmagan har qanday holat) ---
    dp.message.register(forward_client_to_operator, StateFilter(None))


async def main():
    # Dispatcher va Bot obyektlarini yaratish
    # parse_mode Markdown ekanligini ta'minlash muhim
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # DB ulanishini o'rnatish va jadvallarni yaratish
    await db.create_db_pool()
    await db.create_tables()

    # Handlerlarni ro'yxatdan o'tkazish
    setup_handlers(dp)

    # Pollingni ishga tushirish (Bot uzluksiz ishlashi uchun)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi.")
    except Exception as e:
        logging.error(f"Asosiy jarayonda xato: {e}")
    finally:
        # DB ulanishini to'g'ri yopish
        asyncio.run(db.close_db_pool())
