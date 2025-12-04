# main.py

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
# MUHIM TUZATISH: Bu qator aiogram 3.x da to'g'ri ishlashi kerak.
# Agar TelegramForbidden'ni topa olmasa, iltimos, aiogram'ni yangilang.
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

    waiting_for_operator_reply = State()

    waiting_for_change_selection = State()
    waiting_for_new_pickup = State()
    waiting_for_new_destination = State()
    waiting_for_new_day = State()
    waiting_for_new_date_selection_7days = State()
    waiting_for_new_time = State()


# --- Tarjima Lug'ati ---
MONTH_NAMES = {
    'uz': ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr",
           "Dekabr"],
    'ru': ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь",
           "Декабрь"]
}

LANGUAGES = {
    'uz': {
        'start': "Assalomu alaykum! Xizmatimizdan foydalanish uchun tilni tanlang:",
        'ask_name': "Ism va familiyangizni kiriting:",
        'ask_phone': "📞 Aloqa uchun telefon raqamingizni kiriting yoki pastdagi tugmani bosing:",
        'err_phone': "❌ Iltimos, raqamni 998XXYYYYZZZZ formatida kiriting.",
        'ask_pickup': "📍 Qayerdan olib ketish kerak? (Tuman, mahalla, uygacha kiriting):",
        'ask_dest': "🏁 Qayergacha borasiz? (Tuman, mahalla, uygacha kiriting):",
        'ask_count': "👥 Yo'lovchilar sonini tanlang (maks. 4 kishi):",
        'passenger_count_btn': " kishi",
        'ask_day': "📆 Qaysi kuni ketmoqchisiz?",
        'ask_time': "⏳ Taxminan qaysi vaqtda olib ketish kerak? (Masalan: ertalab 7:30, kechki 22:00)",
        'btn_today': "Bugun ☀️",
        'btn_tomorrow': "Ertaga 🌤️",
        'btn_later': "Keyinroq 🗓️",
        'ask_date_7days': "📆 Ketish sanasini tanlang (bugundan 7 kun ichida):",
        'err_invalid_date_7days': "❌ Noto'g'ri sana. Iltimos, faqat tugmalardagi sanalarni tanlang.",
        'finish': "✅ Buyurtmangiz qabul qilindi! Tez orada operatorimiz siz bilan bog'lanadi. Rahmat!",
        'err_text': "❌ Iltimos, to'liqroq ma'lumot kiriting (kamida 5 belgi).",
        'operator_msg': "🚕 Yangi Buyurtma (UZ):",
        'client_accepted': "✅ Sizning buyurtmangiz operator tomonidan qabul qilindi. Iltimos, aloqaga tayyor turing, operatorimiz siz bilan tez orada bog'lanadi."
    },
    'ru': {
        'start': "Здравствуйте! Выберите язык для использования сервиса:",
        'ask_name': "Введите ваше имя и фамилию:",
        'ask_phone': "📞 Введите ваш номер телефона для связи или нажмите кнопку ниже:",
        'err_phone': "❌ Пожалуйста, введите номер в формате 998XXYYYYZZZZ.",
        'ask_pickup': "📍 Откуда вас забрать? (Укажите район, махаллю, до дома):",
        'ask_dest': "🏁 Куда направляетесь? (Укажите район, махаллю, до дома):",
        'ask_count': "👥 Выберите количество пассажиров (макс. 4 человека):",
        'passenger_count_btn_1': " человек",
        'passenger_count_btn_2': " человека",
        'passenger_count_btn_5': " человек",
        'ask_day': "📆 В какой день вы хотите поехать?",
        'ask_time': "⏳ В какое приблизительное время вас забрать? (Например: 7:30 утра, 22:00 вечера)",
        'btn_today': "Сегодня ☀️",
        'btn_tomorrow': "Завтра 🌤️",
        'btn_later': "Позже 🗓️",
        'ask_date_7days': "📆 Выберите дату отправления (в пределах 7 дней с сегодняшнего дня):",
        'err_invalid_date_7days': "❌ Неверная дата. Пожалуйста, выбирайте только из кнопок.",
        'finish': "✅ Ваш заказ принят! Наш оператор свяжется с вами в ближайшее время. Спасибо!",
        'err_text': "❌ Пожалуйста, введите более полную информацию (минимум 5 символов).",
        'operator_msg': "🚕 Новый Заказ (RU):",
        'client_accepted': "✅ Ваш заказ принят оператором. Пожалуйста, будьте на связи, наш оператор скоро свяжется с вами."
    }
}


# --- YORDAMCHI FUNKSIYALAR ---

def get_modification_keyboard():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🔄 Buyurtmani o'zgartirish", callback_data="start_modification")
            ]
        ]
    )


def get_operator_contact_keyboard(client_id: int, username: str = None):
    """
    Operator uchun xavfsiz aloqa tugmalarini qaytaradi.
    Username bo'lmasa, BUTTON_USER_PRIVACY_RESTRICTED xatosini oldini oladi.
    """
    buttons = []

    # 1. Tashqi aloqa tugmasi (FAQAT username bo'lsa)
    if username:
        contact_url = f"https://t.me/{username}"
        buttons.append(
            types.InlineKeyboardButton(
                text="📞 Mijozga yozish (@username)",
                url=contact_url
            )
        )

    # 2. Ichki chatni boshlash tugmasi (Har doim mavjud)
    buttons.append(
        types.InlineKeyboardButton(
            text="💬 Mijoz bilan chatni boshlash",
            callback_data=f"start_chat_{client_id}"
        )
    )

    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            buttons
        ]
    )


async def send_updated_order_to_operator(bot: Bot, order_id: int, client_id: int, message_user: types.User,
                                         update_type: str = "YANGILANGAN"):
    """
    Buyurtma ma'lumotlarini DB'dan olib, uni formatlaydi va barcha operatorlarga yuboradi.
    """

    order_data = await db.get_order_by_id(order_id)

    if not order_data:
        logging.error(f"Order ID {order_id} not found for re-sending.")
        return

    final_data = order_data['data']
    lang = final_data.get('lang', 'uz')

    username_text = f"@{order_data['username']}" if order_data.get('username') else "❌ (Username yo'q)"
    phone_number = final_data.get('phone_number', 'Noma\'lum')

    order_details = (
        f"🚨 {hbold(update_type)} BUYURTMA ({'UZ' if lang == 'uz' else 'RU'}):\n"
        f"--- Yangilangan Ma'lumot ---\n"
        f"👤 {hbold('Ism/Familiya:')} {final_data.get('full_name', 'Noma\'lum')}\n"
        f"📞 {hbold('Telefon:')} +{phone_number}\n"
        f"🛫 {hbold('Qayerdan:')} {final_data.get('pickup_address', 'Noma\'lum')}\n"
        f"🛬 {hbold('Qayergacha:')} {final_data.get('destination_address', 'Noma\'lum')}\n"
        f"👥 {hbold('Yo\'lovchi soni:')} {final_data.get('passenger_count', '?')} kishi\n"

        f"📆 {hbold('Ketish kuni:')} {final_data.get('departure_day', '?')}\n"
        f"⏳ {hbold('Ketish vaqti:')} {final_data.get('departure_time', '?')}\n"

        f"--- \n"
        f"📞 {hbold('Aloqa:')} {username_text}\n"
        # Yopiq akkauntlar xato bermasligi uchun ID ni text ko'rinishida yuboramiz.
        f"Mijoz: {message_user.full_name} (ID: {client_id})\n"
    )

    operator_keyboard = get_operator_contact_keyboard(client_id, message_user.username)

    # BARCHA OPERATORLARGA YUBORISH UCHUN config.OPERATOR_IDS ishlatiladi
    for operator_id in config.OPERATOR_IDS:
        try:
            await bot.send_message(
                operator_id,
                order_details,
                disable_web_page_preview=True,
                reply_markup=operator_keyboard
            )
        except TelegramForbidden as e:
            logging.warning(f"Operator {operator_id} ga xabar yuborishda xato (Bloklangan?): {e}")
        except Exception as e:
            logging.error(f"Operator {operator_id} ga yuborishda noma'lum xato: {e}")


def get_next_seven_days_keyboard(lang: str) -> types.ReplyKeyboardMarkup:
    # ... (Mavjud funksiya o'zgarishsiz)
    now = datetime.now()
    day_buttons = []

    for i in range(7):
        current_date = now + timedelta(days=i)

        month_name = MONTH_NAMES[lang][current_date.month - 1]

        btn_text = f"{current_date.day} ({month_name})"

        day_buttons.append(types.KeyboardButton(text=btn_text))

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            day_buttons[:4],
            day_buttons[4:]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


# ----------------------------------------------------
# ---------------- BUYURTMA HANDLERLARI --------------
# ----------------------------------------------------

# ... (process_time gacha bo'lgan handlerlar o'zgarishsiz qoladi)

async def cmd_start(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🇺🇿 O'zbek tili", callback_data="lang_uz"),
                types.InlineKeyboardButton(text="🇷🇺 Русский язык", callback_data="lang_ru")
            ]
        ]
    )
    await message.answer(LANGUAGES['uz']['start'], reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_lang)


async def cmd_stop(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')

    await state.clear()

    if lang == 'uz':
        response = "❌ Joriy buyurtma jarayoni bekor qilindi. Boshlash uchun /start bosing."
    else:
        response = "❌ Текущий процесс заказа отменен. Нажмите /start для начала."

    await message.answer(response, reply_markup=types.ReplyKeyboardRemove())


async def cmd_restart(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()

    data = await state.get_data()
    lang = data.get('lang', 'uz')

    if lang == 'uz':
        await message.answer("🔄 Bot qayta ishga tushirildi. Tilni qayta tanlang yoki /start bosing.",
                             reply_markup=types.ReplyKeyboardRemove())
    else:
        await message.answer("🔄 Бот перезапущен. Выберите язык снова или нажмите /start.",
                             reply_markup=types.ReplyKeyboardRemove())

    await cmd_start(message, state, bot)


async def process_language(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    lang = callback_query.data.split('_')[1]
    await state.update_data(lang=lang)
    await callback_query.message.delete()
    await callback_query.message.answer(LANGUAGES[lang]['ask_name'])
    await state.set_state(OrderStates.waiting_for_name)


async def process_name(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')

    if len(message.text.strip()) < 3 or len(message.text.strip()) > 255:
        return await message.answer(LANGUAGES[lang]['ask_name'])

    await state.update_data(full_name=message.text.strip())

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text="📞 Raqamni yuborish", request_contact=True)
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(LANGUAGES[lang]['ask_phone'], reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_phone)


async def process_phone(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')
    phone_number = None

    if message.contact and message.contact.phone_number:
        phone_number = message.contact.phone_number.replace('+', '').strip()

    elif message.text:
        text = message.text.strip().replace(' ', '').replace('+', '')

        match = re.fullmatch(r'(?:998)?(\d{2})(\d{7})', text)

        if match:
            phone_number = '998' + match.group(1) + match.group(2)

    if not phone_number or not phone_number.startswith('998') or len(phone_number) != 12:
        return await message.answer(LANGUAGES[lang]['err_phone'])

    await state.update_data(phone_number=phone_number)

    await message.answer(LANGUAGES[lang]['ask_pickup'], reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(OrderStates.waiting_for_pickup)


async def process_pickup(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')
    if len(message.text.strip()) < 5: return await message.answer(LANGUAGES[lang]['err_text'])
    await state.update_data(pickup_address=message.text.strip())
    await message.answer(LANGUAGES[lang]['ask_dest'])
    await state.set_state(OrderStates.waiting_for_destination)


async def process_destination(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')

    if len(message.text.strip()) < 5: return await message.answer(LANGUAGES[lang]['err_text'])

    await state.update_data(destination_address=message.text.strip())

    # --- YO'LOVCHI SONI UCHUN TUGMALAR ---
    count_buttons = []
    for i in range(1, 5):
        if lang == 'uz':
            btn_text = f"{i}{LANGUAGES[lang]['passenger_count_btn']}"
        else:
            if i == 1:
                suffix = LANGUAGES['ru']['passenger_count_btn_1']
            elif 2 <= i <= 4:
                suffix = LANGUAGES['ru']['passenger_count_btn_2']
            else:
                suffix = LANGUAGES['ru']['passenger_count_btn_5']
            btn_text = f"{i}{suffix}"

        count_buttons.append(types.KeyboardButton(text=btn_text))

    keyboard = types.ReplyKeyboardMarkup(keyboard=[count_buttons[:2], count_buttons[2:]], resize_keyboard=True,
                                         one_time_keyboard=True)

    await message.answer(LANGUAGES[lang]['ask_count'], reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_count)


async def process_count(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')
    input_text = message.text.strip()

    valid_counts = {}
    for i in range(1, 5):
        if lang == 'uz':
            btn_text = f"{i}{LANGUAGES[lang]['passenger_count_btn']}"
        else:
            if i == 1:
                suffix = LANGUAGES['ru']['passenger_count_btn_1']
            elif 2 <= i <= 4:
                suffix = LANGUAGES['ru']['passenger_count_btn_2']
            else:
                suffix = LANGUAGES['ru']['passenger_count_btn_5']
            btn_text = f"{i}{suffix}"

        valid_counts[btn_text] = i

    if input_text not in valid_counts:
        return await message.answer(LANGUAGES[lang]['ask_count'])

    count = valid_counts[input_text]
    await state.update_data(passenger_count=count)

    # --- KUNNI SO'RASH ---
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text=LANGUAGES[lang]['btn_today']),
                types.KeyboardButton(text=LANGUAGES[lang]['btn_tomorrow'])
            ],
            [
                types.KeyboardButton(text=LANGUAGES[lang]['btn_later'])
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(LANGUAGES[lang]['ask_day'], reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_day)


async def process_day(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')

    valid_days = [
        LANGUAGES[lang]['btn_today'],
        LANGUAGES[lang]['btn_tomorrow'],
        LANGUAGES[lang]['btn_later']
    ]

    selected_day = message.text.strip()

    if selected_day not in valid_days:
        return await message.answer(LANGUAGES[lang]['ask_day'])

    if selected_day == LANGUAGES[lang]['btn_later']:
        # "Keyinroq" ni bossa, 7 kunlik tugmalarni ko'rsatamiz
        keyboard = get_next_seven_days_keyboard(lang=lang)
        await message.answer(LANGUAGES[lang]['ask_date_7days'],
                             reply_markup=keyboard)
        await state.set_state(OrderStates.waiting_for_date_selection_7days)
    else:
        # "Bugun" yoki "Ertaga" ni bossa, to'g'ridan-to'g'ri vaqtga o'tamiz
        await state.update_data(departure_day=selected_day)
        await message.answer(LANGUAGES[lang]['ask_time'], reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(OrderStates.waiting_for_time)


async def process_date_selection_7days(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')

    input_text = message.text.strip()

    valid_dates_keyboard = get_next_seven_days_keyboard(lang=lang)
    valid_texts = [btn.text for row in valid_dates_keyboard.keyboard for btn in row]

    if input_text not in valid_texts:
        return await message.answer(LANGUAGES[lang]['err_invalid_date_7days'])

    try:
        day_str, month_name_str = input_text.split(' (')
        day = int(day_str)

        month_name = month_name_str[:-1]
        month_index = MONTH_NAMES[lang].index(month_name) + 1

        now = datetime.now()
        year = now.year
        if now.month > month_index:
            year += 1

        selected_date_str = f"{year}-{month_index:02d}-{day:02d}"

        if datetime.strptime(selected_date_str, "%Y-%m-%d").date() < now.date():
            return await message.answer(LANGUAGES[lang]['err_invalid_date_7days'])

    except Exception as e:
        logging.error(f"Sana tanlashda xato: {e}")
        return await message.answer(LANGUAGES[lang]['err_invalid_date_7days'])

    await state.update_data(departure_day=selected_date_str)

    await message.answer(LANGUAGES[lang]['ask_time'], reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(OrderStates.waiting_for_time)


async def process_time(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')

    if len(message.text.strip()) < 3:
        return await message.answer(LANGUAGES[lang]['ask_time'])

    await state.update_data(departure_time=message.text.strip())

    final_data = await state.get_data()
    client_id = message.from_user.id

    # DBga saqlash
    order_id = await db.save_order_to_db(
        user_id=client_id,
        username=message.from_user.username,
        data=final_data,
        offered_price=0
    )

    if not order_id:
        return await message.answer("❌ Buyurtmani saqlashda ichki xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

    username_text = f"@{message.from_user.username}" if message.from_user.username else "❌ (Username yo'q)"
    phone_number = final_data.get('phone_number', 'Noma\'lum')

    # Operatorga yuboriladigan xabar
    order_details = (
        f"{hbold(LANGUAGES[lang]['operator_msg'])}\n"
        f"--- Yangi Buyurtma ---\n"
        f"👤 {hbold('Ism/Familiya:')} {final_data['full_name']}\n"
        f"📞 {hbold('Telefon:')} +{phone_number}\n"
        f"🛫 {hbold('Qayerdan:')} {final_data['pickup_address']}\n"
        f"🛬 {hbold('Qayergacha:')} {final_data['destination_address']}\n"
        f"👥 {hbold('Yo\'lovchi soni:')} {final_data['passenger_count']} kishi\n"
        f"📆 {hbold('Ketish kuni:')} {final_data.get('departure_day', '?')}\n"
        f"⏳ {hbold('Ketish vaqti:')} {final_data.get('departure_time', '?')}\n"
        f"--- \n"
        f"📞 {hbold('Aloqa:')} {username_text}\n"
        # Yopiq akkauntlar xato bermasligi uchun ID ni text ko'rinishida yuboramiz.
        f"Mijoz: {message.from_user.full_name} (ID: {client_id})"
    )

    # --- OPERATOR KEYBOARDNI YARATISH (Xavfsiz versiya) ---
    operator_keyboard = get_operator_contact_keyboard(
        client_id=client_id,
        username=message.from_user.username
    )

    # --- BARCHA OPERATORLARGA YUBORISH ---
    for operator_id in config.OPERATOR_IDS:
        try:
            await bot.send_message(
                operator_id,
                order_details,
                disable_web_page_preview=True,
                reply_markup=operator_keyboard
            )
        except TelegramForbidden as e:
            # Agar bot operator tomonidan bloklangan bo'lsa
            logging.warning(f"Operator {operator_id} ga xabar yuborishda xato (Bloklangan?): {e}")
        except Exception as e:
            logging.error(f"Operator {operator_id} ga yuborishda noma'lum xato: {e}")

    # --- MIJOZGA YAKUNIY XULOSA YUBORISH ---
    departure_day_raw = final_data.get('departure_day', '?')

    if re.match(r'\d{4}-\d{2}-\d{2}', departure_day_raw):
        try:
            date_obj = datetime.strptime(departure_day_raw, "%Y-%m-%d")
            month_name = MONTH_NAMES[lang][date_obj.month - 1]
            departure_day_display = f"{date_obj.day} {month_name}, {date_obj.year}-yil"
        except:
            departure_day_display = departure_day_raw
    else:
        departure_day_display = departure_day_raw

    client_summary = (
        f"📋 {hbold('Sizning Buyurtma Ma\'lumotlaringiz')}:\n"
        f"--- \n"
        f"👤 {hbold('Kimdan:')} {final_data['full_name']}\n"
        f"📞 {hbold('Telefon:')} +{phone_number}\n"
        f"🛫 {hbold('Olib ketish:')} {final_data['pickup_address']}\n"
        f"🛬 {hbold('Borish:')} {final_data['destination_address']}\n"
        f"👥 {hbold('Yo\'lovchi soni:')} {final_data['passenger_count']} kishi\n"
        f"📆 {hbold('Ketish kuni:')} {departure_day_display}\n"
        f"⏳ {hbold('Ketish vaqti:')} {final_data.get('departure_time', '?')}\n"
        f"--- \n"
        f"{LANGUAGES[lang]['finish']}"
    )

    await message.answer(client_summary)

    await message.answer(
        "Agar buyurtmada o'zgartirish kiritmoqchi bo'lsangiz, operator qabul qilguncha cheksiz o'zgartirish kiritishingiz mumkin:",
        reply_markup=get_modification_keyboard()
    )

    await state.clear()


# ----------------------------------------------------
# ---------------- CHAT & FORWARD HANDLERLARI
# ----------------------------------------------------

async def process_operator_action(callback_query: types.CallbackQuery, bot: Bot):
    try:
        parts = callback_query.data.split('_')
        client_id_str = parts[2]
        lang = parts[3]
        client_id = int(client_id_str)
    except Exception:
        return await callback_query.answer("Xato: Mijoz ID'si yoki til topilmadi.")

    await callback_query.message.edit_reply_markup(reply_markup=None)

    client_message = LANGUAGES[lang]['client_accepted']

    try:
        # Mijozga xabar yuborishda ham xato bo'lishi mumkin
        await bot.send_message(chat_id=client_id, text=client_message)
        await callback_query.answer(f"Mijozga ({client_id}) xabar muvaffaqiyatli yuborildi!")

    except TelegramForbidden:
        await callback_query.answer(f"❌ Mijozga xabar yuborishda xato: Mijoz botni bloklagan bo'lishi mumkin.")
    except Exception as e:
        await callback_query.answer(f"❌ Mijozga xabar yuborishda noma'lum xato: {e}")


async def start_chat_with_client(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    try:
        parts = callback_query.data.split('_')
        client_id_str = parts[2]
        client_id = int(client_id_str)
    except Exception:
        return await callback_query.answer("Xato: Mijoz ID'si topilmadi.")

    # OPERATORLAR RO'YXATIDA TEKSHIRISH
    if callback_query.from_user.id not in config.OPERATOR_IDS:
        return await callback_query.answer("Siz operator emassiz.")

    await state.set_state(OrderStates.waiting_for_operator_reply)
    await state.update_data(target_client_id=client_id)

    stop_keyboard = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="💬 Chatni yakunlash")]],
                                              resize_keyboard=True, one_time_keyboard=True)

    await callback_query.answer(f"Mijoz ({client_id}) bilan chatni boshladingiz.")

    await bot.send_message(
        callback_query.from_user.id,
        f"➡️ **Mijoz ({client_id})** ga xabar yuborish rejimidasiz. Xabaringizni kiriting.",
        reply_markup=stop_keyboard
    )


async def send_operator_reply_to_client(message: types.Message, state: FSMContext, bot: Bot):
    # OPERATORLAR RO'YXATIDA TEKSHIRISH
    if message.from_user.id not in config.OPERATOR_IDS: return

    if message.text == "💬 Chatni yakunlash":
        await state.clear()
        return await message.answer("Chat yakunlandi.", reply_markup=types.ReplyKeyboardRemove())

    data = await state.get_data()
    target_client_id = data.get('target_client_id')

    if target_client_id:
        try:
            # Xabarni mijozga forward qilishda xato tutish
            await bot.copy_message(chat_id=target_client_id, from_chat_id=message.chat.id,
                                   message_id=message.message_id)
            await message.answer(f"✅ Xabar mijozga ({target_client_id}) yetkazildi.")
        except TelegramForbidden:
            await message.answer(f"❌ Xabarni yetkazishda xato: Mijoz botni bloklagan bo'lishi mumkin.")
        except Exception as e:
            await message.answer(f"❌ Xabarni yetkazishda noma'lum xato: {e}")
    else:
        await state.clear()
        await message.answer("Xabarni yuborish uchun mijoz tanlanmagan.")


async def forward_client_to_operator(message: types.Message, state: FSMContext, bot: Bot):
    # OPERATORLAR RO'YXATIDA BO'LMASA
    if message.from_user.id in config.OPERATOR_IDS: return

    client_id = message.from_user.id
    username_text = f"@{message.from_user.username}" if message.from_user.username else "❌ (Username yo'q)"

    caption = (
        f"📩 {hbold('MIJOZDAN YANGI XABAR')} ({message.from_user.id}):\n"
        f"Nik: {username_text}\n"
        f"Mijoz: {message.from_user.full_name} (ID: {client_id})"  # Xavfsiz ID ko'rinishi
    )

    # Username'ni operator kontakt tugmasiga yuborish
    operator_keyboard = get_operator_contact_keyboard(client_id, message.from_user.username)

    # BARCHA OPERATORLARGA FORWARD QILISH
    for operator_id in config.OPERATOR_IDS:
        try:
            await bot.copy_message(
                chat_id=operator_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=caption,
                reply_markup=operator_keyboard
            )
        except TelegramForbidden:
            logging.warning(
                f"Mijoz xabarini operator {operator_id} ga yuborishda xato: Operator bloklagan bo'lishi mumkin.")
        except Exception as e:
            logging.error(f"Mijoz xabarini operator {operator_id} ga yuborishda noma'lum xato: {e}")

    await message.answer("Xabaringiz operatorlarga yetkazildi.")


# ----------------------------------------------------
# ---------------- O'ZGARTIRISH HANDLERLARI
# ----------------------------------------------------

async def start_modification(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    client_id = callback_query.from_user.id

    last_order = await db.get_last_order(client_id)

    if not last_order or not last_order.get('order_id'):
        await callback_query.message.edit_text(
            "❌ Kechirasiz, sizda hozircha faol buyurtma topilmadi.\nYangi buyurtma berish uchun /start komandasini bosing.",
            reply_markup=None
        )
        return await callback_query.answer("Faol buyurtma topilmadi.")

    # --- O'zgartirish tugmalari ---
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📍 Olib ketish manzilini o'zgartirish", callback_data="change_pickup")],
            [types.InlineKeyboardButton(text="🏁 Borish manzilini o'zgartirish", callback_data="change_destination")],
            [types.InlineKeyboardButton(text="📆 Ketish Kunini o'zgartirish", callback_data="change_day")],
            [types.InlineKeyboardButton(text="⏳ Ketish Vaqtini o'zgartirish", callback_data="change_time")],
            [types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_modification")]
        ]
    )

    await callback_query.message.edit_text(
        "Nimani o'zgartirmoqchisiz? \n"
        "**Eslatma: O'zgartirishlar faqat operator buyurtmani qabul qilguncha amal qiladi.**",
        reply_markup=keyboard
    )

    await state.update_data(current_order_id=last_order['order_id'])
    await state.set_state(OrderStates.waiting_for_change_selection)
    await callback_query.answer()


async def process_modification_selection(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    action = callback_query.data

    order_data = await db.get_order_by_id((await state.get_data()).get('current_order_id'))
    lang = order_data.get('data', {}).get('lang', 'uz')

    if action == "cancel_modification":
        await state.clear()
        await callback_query.message.edit_text("O'zgartirish bekor qilindi.", reply_markup=get_modification_keyboard())
        return await callback_query.answer()

    await callback_query.message.edit_reply_markup(reply_markup=None)

    if action == "change_pickup":
        await callback_query.message.answer(LANGUAGES[lang]['ask_pickup'])
        await state.set_state(OrderStates.waiting_for_new_pickup)
    elif action == "change_destination":
        await callback_query.message.answer(LANGUAGES[lang]['ask_dest'])
        await state.set_state(OrderStates.waiting_for_new_destination)
    elif action == "change_day":
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text=LANGUAGES[lang]['btn_today']),
                    types.KeyboardButton(text=LANGUAGES[lang]['btn_tomorrow'])
                ],
                [
                    types.KeyboardButton(text=LANGUAGES[lang]['btn_later'])
                ]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await callback_query.message.answer(LANGUAGES[lang]['ask_day'], reply_markup=keyboard)
        await state.set_state(OrderStates.waiting_for_new_day)
    elif action == "change_time":
        await callback_query.message.answer(LANGUAGES[lang]['ask_time'], reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(OrderStates.waiting_for_new_time)

    await callback_query.answer()


async def _handle_modification_success(message: types.Message, state: FSMContext, bot: Bot, field: str, value):
    """O'zgartirish muvaffaqiyatli yakunlanganda DBni yangilash va TO'LIQ XABAR yuborish."""

    data = await state.get_data()
    order_id = data.get('current_order_id')

    if order_id:
        await db.update_order_data(order_id, field, value)

        await state.clear()

        # BARCHA OPERATORLARGA YANGILANGAN BUYURTMANI YUBORISH
        await send_updated_order_to_operator(
            bot=bot,
            order_id=order_id,
            client_id=message.from_user.id,
            message_user=message.from_user,
            update_type="YANGILANGAN"
        )

        field_names = {
            'pickup_address': "Olib ketish manzili",
            'destination_address': "Borish manzili",
            'departure_day': "Ketish kuni",
            'departure_time': "Ketish vaqti"
        }
        change_name = field_names.get(field, "Ma'lumot")

        await message.answer(
            f"✅ **{change_name}** muvaffaqiyatli o'zgartirildi va operatorlarga xabar yuborildi.",
            reply_markup=get_modification_keyboard()
        )
    else:
        await state.clear()
        await message.answer("Xatolik yuz berdi. O'zgartirish bekor qilindi.")


async def process_new_pickup(message: types.Message, state: FSMContext, bot: Bot):
    if len(message.text.strip()) < 5: return await message.answer("❌ Iltimos, yangi manzilni aniqroq kiriting.")
    await _handle_modification_success(message, state, bot, 'pickup_address', message.text.strip())


async def process_new_destination(message: types.Message, state: FSMContext, bot: Bot):
    if len(message.text.strip()) < 5: return await message.answer("❌ Iltimos, yangi manzilni aniqroq kiriting.")
    await _handle_modification_success(message, state, bot, 'destination_address', message.text.strip())


async def process_new_day(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_data = await db.get_order_by_id(data.get('current_order_id'))
    lang = order_data.get('data', {}).get('lang', 'uz')

    valid_days = [
        LANGUAGES[lang]['btn_today'],
        LANGUAGES[lang]['btn_tomorrow'],
        LANGUAGES[lang]['btn_later']
    ]

    selected_day = message.text.strip()

    if selected_day not in valid_days:
        return await message.answer(LANGUAGES[lang]['ask_day'])

    if selected_day == LANGUAGES[lang]['btn_later']:
        keyboard = get_next_seven_days_keyboard(lang=lang)
        await message.answer(LANGUAGES[lang]['ask_date_7days'],
                             reply_markup=keyboard)
        await state.set_state(OrderStates.waiting_for_new_date_selection_7days)
    else:
        await message.answer("✅ Kun muvaffaqiyatli qabul qilindi.", reply_markup=types.ReplyKeyboardRemove())
        await _handle_modification_success(message, state, bot, 'departure_day', selected_day)


async def process_new_date_selection_7days(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_data = await db.get_order_by_id(data.get('current_order_id'))
    lang = order_data.get('data', {}).get('lang', 'uz')

    input_text = message.text.strip()

    valid_dates_keyboard = get_next_seven_days_keyboard(lang=lang)
    valid_texts = [btn.text for row in valid_dates_keyboard.keyboard for btn in row]

    if input_text not in valid_texts:
        return await message.answer(LANGUAGES[lang]['err_invalid_date_7days'])

    try:
        day_str, month_name_str = input_text.split(' (')
        day = int(day_str)
        month_name = month_name_str[:-1]
        month_index = MONTH_NAMES[lang].index(month_name) + 1

        now = datetime.now()
        year = now.year
        if now.month > month_index:
            year += 1

        new_day = f"{year}-{month_index:02d}-{day:02d}"

        if datetime.strptime(new_day, "%Y-%m-%d").date() < now.date():
            return await message.answer(LANGUAGES[lang]['err_invalid_date_7days'])

    except Exception as e:
        logging.error(f"O'zgartirishda sana tanlash xatosi: {e}")
        return await message.answer(LANGUAGES[lang]['err_invalid_date_7days'])

    await message.answer("✅ Kun muvaffaqiyatli qabul qilindi.", reply_markup=types.ReplyKeyboardRemove())
    await _handle_modification_success(message, state, bot, 'departure_day', new_day)


async def process_new_time(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_data = await db.get_order_by_id(data.get('current_order_id'))
    lang = order_data.get('data', {}).get('lang', 'uz')

    if len(message.text.strip()) < 3:
        return await message.answer(LANGUAGES[lang]['ask_time'])

    new_time = message.text.strip()

    await _handle_modification_success(message, state, bot, 'departure_time', new_time)


# ----------------------------------------------------
# ---------------- BOTNI ISHGA TUSHIRISH -------------
# ----------------------------------------------------

async def on_startup(dispatcher: Dispatcher, bot: Bot):
    try:
        await db.create_db_pool()
        await db.create_tables()
        logging.info("🚀 Bot ishga tushdi va DB tayyor.")
    except Exception as e:
        logging.error(f"❌ DBni sozlashda xato: {e}")


async def on_shutdown(dispatcher: Dispatcher):
    await db.close_db_pool()
    logging.info("🔴 Bot o'chirildi.")


async def main():
    default_properties = DefaultBotProperties(parse_mode='HTML')

    bot = Bot(token=config.BOT_TOKEN, default=default_properties)
    dp = Dispatcher(storage=MemoryStorage())

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Bot komandalarini o'rnatish
    await bot.set_my_commands([
        types.BotCommand(command="/start", description="Buyurtma berishni boshlash"),
        types.BotCommand(command="/stop", description="Joriy buyurtmani bekor qilish"),
        types.BotCommand(command="/restart", description="Botni qayta ishga tushirish")
    ])

    # --- BUYURTMA JARAYONI HANDLERLARI ---
    dp.message.register(cmd_start, Command("start"), StateFilter("*"))
    dp.message.register(cmd_stop, Command("stop"), StateFilter("*"))
    dp.message.register(cmd_restart, Command("restart"), StateFilter("*"))

    dp.callback_query.register(process_language, lambda c: c.data.startswith('lang_'),
                               StateFilter(OrderStates.waiting_for_lang))
    dp.message.register(process_name, StateFilter(OrderStates.waiting_for_name))
    dp.message.register(process_phone, StateFilter(OrderStates.waiting_for_phone))
    dp.message.register(process_pickup, StateFilter(OrderStates.waiting_for_pickup))
    dp.message.register(process_destination, StateFilter(OrderStates.waiting_for_destination))
    dp.message.register(process_count, StateFilter(OrderStates.waiting_for_count))

    dp.message.register(process_day, StateFilter(OrderStates.waiting_for_day))
    dp.message.register(process_date_selection_7days, StateFilter(OrderStates.waiting_for_date_selection_7days))
    dp.message.register(process_time, StateFilter(OrderStates.waiting_for_time))

    # --- CHAT / QABUL QILISH HANDLERLARI ---
    dp.callback_query.register(process_operator_action, lambda c: c.data.startswith('order_accept_'), StateFilter("*"))
    dp.callback_query.register(start_chat_with_client, lambda c: c.data.startswith('start_chat_'), StateFilter("*"))

    # Faqat operatorlar javob berishi mumkin
    dp.message.register(send_operator_reply_to_client, StateFilter(OrderStates.waiting_for_operator_reply),
                        lambda m: m.from_user.id in config.OPERATOR_IDS)

    # --- O'ZGARTIRISH HANDLERLARI ---
    dp.callback_query.register(start_modification, lambda c: c.data == 'start_modification')
    dp.callback_query.register(process_modification_selection, StateFilter(OrderStates.waiting_for_change_selection))
    dp.message.register(process_new_pickup, StateFilter(OrderStates.waiting_for_new_pickup))
    dp.message.register(process_new_destination, StateFilter(OrderStates.waiting_for_new_destination))

    dp.message.register(process_new_day, StateFilter(OrderStates.waiting_for_new_day))
    dp.message.register(process_new_date_selection_7days, StateFilter(OrderStates.waiting_for_new_date_selection_7days))
    dp.message.register(process_new_time, StateFilter(OrderStates.waiting_for_new_time))

    # --- MIJOZ JAVOBINI FORWARD QILISH (Operator bo'lmagan har qanday holat) ---
    dp.message.register(forward_client_to_operator, StateFilter(None))

    # Pollingni ishga tushirish (Bot uzluksiz ishlashi uchun)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        logging.basicConfig(level=logging.INFO)
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi (KeyboardInterrupt).")
    except Exception as e:
        logging.error(f"❌ Kutilmagan global xatolik yuz berdi: {e}")