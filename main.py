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
# MUHIM TUZATISH: TelegramForbidden -> TelegramForbiddenError
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

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
        'client_accepted': "✅ Sizning buyurtmangiz operator tomonidan qabul qilindi. Iltimos, aloqaga tayyor turing, operatorimiz siz bilan tez orada bog'lanadi.",
        'order_cancelled_client': "❌ Sizning buyurtmangiz bekor qilindi. Yangi buyurtma berish uchun /start bosing.",
        'order_cancelled_admin': "❌ Operator tomonidan buyurtmangiz bekor qilindi. Sababini bilish uchun operatorga murojaat qiling."
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
        'client_accepted': "✅ Ваш заказ принят оператором. Пожалуйста, будьте на связи, наш оператор скоро свяжется с вами.",
        'order_cancelled_client': "❌ Ваш заказ отменен клиентом. Нажмите /start для нового заказа.",
        'order_cancelled_admin': "❌ Ваш заказ отменен оператором. Обратитесь к оператору для выяснения причин."
    }
}


# --- YORDAMCHI FUNKSIYALAR ---

def get_modification_keyboard():
    # Buyurtmani o'zgartirish va bekor qilish tugmalari
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🔄 Buyurtmani o'zgartirish", callback_data="start_modification")
            ],
            [
                types.InlineKeyboardButton(text="❌ Buyurtmani bekor qilish", callback_data="cancel_order_client")
            ]
        ]
    )


def get_operator_contact_keyboard(client_id: int, username: str = None, order_id: int = None):
    """
    Operator uchun xavfsiz aloqa va amallar tugmalarini qaytaradi.
    """
    buttons = []

    # 1. Bekor qilish tugmasi
    if order_id is not None:
        buttons.append(
            types.InlineKeyboardButton(
                text="❌ Buyurtmani bekor qilish",
                callback_data=f"cancel_order_admin_{order_id}"
            )
        )

    # 2. Aloqa tugmalari
    contact_buttons = []
    if username:
        contact_url = f"https://t.me/{username}"
        contact_buttons.append(
            types.InlineKeyboardButton(
                text="📞 Mijozga yozish (@username)",
                url=contact_url
            )
        )
    contact_buttons.append(
        types.InlineKeyboardButton(
            text="💬 Mijoz bilan chatni boshlash",
            callback_data=f"start_chat_{client_id}"
        )
    )

    # 3. Yakuniy klaviatura
    keyboard = [
        buttons,  # Bekor qilish
        contact_buttons  # Aloqa
    ]

    return types.InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )


async def create_admin_order_message(final_data: dict, client_id: int, username_text: str, order_id: int):
    """
    Admin kanaliga yuborish uchun to'liq formatlangan buyurtma xabarini yaratadi,
    uning ichida statusni ham ko'rsatadi.
    """
    # 1. Statusni databasedan olish
    order_status = await db.get_order_status(order_id)
    lang = final_data.get('lang', 'uz')
    
    # 2. Statusga qarab belgi tanlash
    if order_status == 'active':
        status_emoji = "✅" # Aktiv yoki Kutilmoqda
    elif order_status in ['cancelled_by_client', 'cancelled_by_admin']:
        status_emoji = "❌" # Bekor qilingan
    elif order_status == 'completed':
        status_emoji = "☑️" # Yakunlangan
    else:
        status_emoji = "❓"  # Noma'lum holat

    # 3. Buyurtma tafsilotlarini shakllantirish
    order_details = (
        f"🚨 {hbold(LANGUAGES[lang]['operator_msg'])} {status_emoji} (ID: {order_id})\n"
        f"--- Buyurtma Holati ---\n"
        f"{hbold('STATUS:')} {order_status.upper()} {status_emoji}\n" # Statusni ko'rsatish
        f"--- Buyurtmachi Ma'lumotlari ---\n"
        f"👤 {hbold('Ism/Familiya:')} {final_data.get('full_name', '?')}\n"
        f"📞 {hbold('Telefon:')} +{final_data.get('phone_number', '?')}\n"
        f"🛫 {hbold('Qayerdan:')} {final_data.get('pickup_address', '?')}\n"
        f"🛬 {hbold('Qayergacha:')} {final_data.get('destination_address', '?')}\n"
        f"👥 {hbold('Yoʻlovchi soni:')} {final_data.get('passenger_count', '?')} kishi\n"
        f"📆 {hbold('Ketish kuni:')} {final_data.get('departure_day', '?')}\n"
        f"⏳ {hbold('Ketish vaqti:')} {final_data.get('departure_time', '?')}\n"
        f"--- Aloqa ---\n"
        f"📞 {hbold('Aloqa:')} {username_text}\n"
        f"Mijoz: {final_data.get('full_name', '?')} (ID: {client_id})"
    )
    
    return order_details


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
    order_status = order_data.get('status', 'active') 

    username_text = f"@{order_data['username']}" if order_data.get('username') else "❌ (Username yo'q)"
    phone_number = final_data.get('phone_number', 'Noma\'lum')

    # Statusga qarab emojini tanlash
    if order_status == 'active': status_emoji = "✅" 
    elif order_status in ['cancelled_by_client', 'cancelled_by_admin']: status_emoji = "❌"
    else: status_emoji = "❓"
        
    order_details = (
        f"🚨 {hbold(update_type)} BUYURTMA {status_emoji} (ID: {order_id})\n"
        f"--- Buyurtma Holati ---\n"
        f"{hbold('STATUS:')} {order_status.upper()} {status_emoji}\n"
        f"--- Yangilangan Ma'lumot ---\n"
        f"👤 {hbold('Ism/Familiya:')} {final_data.get('full_name', 'Noma`lum')}\n"
        f"📞 {hbold('Telefon:')} +{phone_number}\n"
        f"🛫 {hbold('Qayerdan:')} {final_data.get('pickup_address', 'Noma`lum')}\n"
        f"🛬 {hbold('Qayergacha:')} {final_data.get('destination_address', 'Noma`lum')}\n"
        f"👥 {hbold('Yo`lovchi soni:')} {final_data.get('passenger_count', '?')} kishi\n"
        f"📆 {hbold('Ketish kuni:')} {final_data.get('departure_day', '?')}\n"
        f"⏳ {hbold('Ketish vaqti:')} {final_data.get('departure_time', '?')}\n"
        f"--- Aloqa ---\n"
        f"📞 {hbold('Aloqa:')} {username_text}\n"
        f"Mijoz: {message_user.full_name} (ID: {client_id})"
    )

    operator_keyboard = get_operator_contact_keyboard(client_id, message_user.username, order_id)

    # BARCHA OPERATORLARGA YUBORISH UCHUN config.OPERATOR_IDS ishlatiladi
    for operator_id in config.OPERATOR_IDS:
        try:
            await bot.send_message(
                operator_id,
                order_details,
                disable_web_page_preview=True,
                reply_markup=operator_keyboard
            )
        except TelegramForbiddenError as e: 
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
    username_text = f"@{message.from_user.username}" if message.from_user.username else "❌ (Username yo'q)"

    # DBga saqlash ('active' statusi bilan saqlanadi)
    order_id = await db.save_order_to_db(
        user_id=client_id,
        username=message.from_user.username,
        data=final_data,
        offered_price=0
    )

    if not order_id:
        return await message.answer("❌ Buyurtmani saqlashda ichki xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

    # Operatorga yuboriladigan xabar
    order_details = await create_admin_order_message(
        final_data=final_data,
        client_id=client_id,
        username_text=username_text,
        order_id=order_id
    )

    # --- OPERATOR KEYBOARDNI YARATISH (STATUS BEKOR QILISH TUGMASI BILAN) ---
    operator_keyboard = get_operator_contact_keyboard(
        client_id=client_id,
        username=message.from_user.username,
        order_id=order_id # Buyurtma IDsi qo'shildi
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
        except TelegramForbiddenError as e: 
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
        f"📋 {hbold('Sizning Buyurtma Ma`lumotlaringiz')}:\n"
        f"--- \n"
        f"👤 {hbold('Kimdan:')} {final_data['full_name']}\n"
        f"📞 {hbold('Telefon:')} +{final_data.get('phone_number', '?')}\n"
        f"🛫 {hbold('Olib ketish:')} {final_data['pickup_address']}\n"
        f"🛬 {hbold('Borish:')} {final_data['destination_address']}\n"
        f"👥 {hbold('Yo`lovchi soni:')} {final_data['passenger_count']} kishi\n"
        f"📆 {hbold('Ketish kuni:')} {departure_day_display}\n"
        f"⏳ {hbold('Ketish vaqti:')} {final_data.get('departure_time', '?')}\n"
        f"--- \n"
        f"{LANGUAGES[lang]['finish']}"
    )

    await message.answer(client_summary)

    await message.answer(
        "Agar buyurtmada o'zgartirish yoki bekor qilish kiritmoqchi bo'lsangiz, quyidagi tugmalardan foydalaning:",
        reply_markup=get_modification_keyboard()
    )

    await state.clear()


# ----------------------------------------------------
# ---------------- BEKOR QILISH HANDLERLARI --------------
# ----------------------------------------------------

async def cancel_order_by_client(callback_query: types.CallbackQuery, bot: Bot):
    client_id = callback_query.from_user.id
    
    # 1. Oxirgi faol buyurtmani topish
    last_order = await db.get_last_order(client_id)

    if not last_order or not last_order.get('order_id'):
        return await callback_query.answer("❌ Kechirasiz, sizda faol buyurtma topilmadi.")

    order_id = last_order['order_id']
    order_info = await db.get_order_by_id(order_id)
    lang = order_info.get('data', {}).get('lang', 'uz')
    current_status = order_info.get('status')
    
    if current_status in ['cancelled_by_client', 'cancelled_by_admin', 'completed']:
         return await callback_query.answer("❌ Bu buyurtma allaqachon bekor qilingan yoki yakunlangan.")

    # 2. Statusni DB da yangilash
    await db.update_order_status(order_id, 'cancelled_by_client')
    
    # 3. Mijozga xabar berish
    await callback_query.message.edit_text(LANGUAGES[lang]['order_cancelled_client'])
    await callback_query.answer("Buyurtmangiz bekor qilindi.")

    # 4. Operatorlarga xabar yuborish
    try:
        await send_updated_order_to_operator(
            bot=bot,
            order_id=order_id,
            client_id=client_id,
            message_user=callback_query.from_user,
            update_type="BEKOR QILINGAN" # Xabar boshini o'zgartirish
        )
        # Operatorlarga bekor qilishni tasdiqlovchi xabar yuborish
        for operator_id in config.OPERATOR_IDS:
             await bot.send_message(
                operator_id,
                f"🚨 {hbold('DIQQAT:')} {callback_query.from_user.full_name} ({client_id}) IDli mijoz o'z buyurtmasini ({order_id}) bekor qildi. ✅",
                parse_mode='HTML'
            )
    except Exception as e:
        logging.error(f"Bekor qilish xabarini operatorlarga yuborishda xato: {e}")


async def cancel_order_by_admin(callback_query: types.CallbackQuery, bot: Bot):
    # Faqat operatorlar bekor qila olsin
    if callback_query.from_user.id not in config.OPERATOR_IDS:
        return await callback_query.answer("❌ Siz operator emassiz.")

    try:
        order_id = int(callback_query.data.split('_')[-1])
    except:
        return await callback_query.answer("❌ Buyurtma ID'si topilmadi.")

    order_info = await db.get_order_by_id(order_id)
    if not order_info:
        return await callback_query.answer("❌ Bunday buyurtma mavjud emas.")
        
    current_status = order_info.get('status')
    if current_status in ['cancelled_by_client', 'cancelled_by_admin', 'completed']:
         return await callback_query.answer(f"❌ Buyurtma allaqachon {current_status} holatida.")

    client_id = order_info['user_id']
    lang = order_info.get('data', {}).get('lang', 'uz')

    # 1. Statusni DB da yangilash
    await db.update_order_status(order_id, 'cancelled_by_admin')

    # 2. Operatorning xabarini yangilash
    await callback_query.message.edit_text(
        f"❌ {hbold('BEKOR QILINDI')} (Operator: {callback_query.from_user.full_name})\n" + callback_query.message.html_text,
        reply_markup=None
    )
    await callback_query.answer(f"Buyurtma {order_id} bekor qilindi.")

    # 3. Mijozga xabar berish
    try:
        await bot.send_message(client_id, LANGUAGES[lang]['order_cancelled_admin'])
    except TelegramForbiddenError: 
        logging.warning(f"Mijoz ({client_id}) botni bloklagan, bekor qilish xabari yetkazilmadi.")
    except Exception as e:
        logging.error(f"Mijozga bekor qilish xabarini yuborishda xato: {e}")

    # 4. Boshqa operatorlarga xabar berish (agar kerak bo'lsa)
    for operator_id in config.OPERATOR_IDS:
        if operator_id != callback_query.from_user.id:
            await bot.send_message(
                operator_id,
                f"🚨 {hbold('DIQQAT:')} Operator {callback_query.from_user.full_name} buyurtmani ({order_id}) bekor qildi. ✅",
                parse_mode='HTML'
            )


# ----------------------------------------------------
# ---------------- QOLGAN HANDLERLAR (o'zgarishsiz) ---
# ----------------------------------------------------
# ... (process_operator_action, start_chat_with_client, send_operator_reply_to_client, forward_client_to_operator, start_modification, process_modification_selection, _handle_modification_success, process_new_pickup, process_new_destination, process_new_day, process_new_date_selection_7days, process_new_time funksiyalari avvalgidek qoladi) ...

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

    # ... (Boshqa buyurtma qadamlari avvalgidek qoladi) ...

    # --- BEKOR QILISH HANDLERLARI ---
    dp.callback_query.register(cancel_order_by_client, lambda c: c.data == 'cancel_order_client')
    dp.callback_query.register(cancel_order_by_admin, lambda c: c.data.startswith('cancel_order_admin_'))
    
    # --- CHAT / QABUL QILISH / O'ZGARTIRISH HANDLERLARI ---
    # ... (Boshqa barcha handlar avvalgidek qoladi) ...


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
