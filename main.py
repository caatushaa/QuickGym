# import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from database import Database



# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Создаем экземпляры
# bot = Bot(token=os.getenv('BOT_TOKEN'))
bot = Bot(token='8339613511:AAGQT0s1AlLDRk7TsdrMCv05KF9L9tl3AlQ')
dp = Dispatcher()
db = Database("fitness_bot.db")


# States для FSM
class Registration(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_phone = State()  # ← ТОЛЬКО ОДНО состояние для номера
    waiting_for_subscription = State()


class Booking(StatesGroup):
    choosing_training_type = State()    # Выбор типа тренировки
    choosing_training = State()         # Выбор конкретной тренировки
    choosing_time = State()             # Выбор даты/времени
    cancelling_booking = State()        # Отмена записи
# Согласие на обработку данных
AGREEMENT_TEXT = """
📋 <b>СОГЛАСИЕ НА ОБРАБОТКУ ПЕРСОНАЛЬНЫХ ДАННЫХ</b>

Перед использованием бота необходимо ваше согласие на обработку персональных данных:

• Хранение и обработка вашего номера телефона
• Хранение истории ваших записей на тренировки
• Использование данных для связи с вами

<b>Также подтвердите, что вам исполнилось 16 лет</b> - это минимальный возраст для использования нашего сервиса.

✅ <b>Нажимая "Принять", вы соглашаетесь с условиями</b>
"""

# Аккаунты разработчиков для обратной связи
DEVELOPERS = """
👨‍💻 <b>Обратная связь с разработчиками</b>

По техническим вопросам работы бота:
• @username1 - главный разработчик
• @username2 - техподдержка

По вопросам тренировок и абонементов:
• @fitnesmanager - менеджер клуба
"""


def is_valid_phone(phone: str) -> bool:
    """Проверяет валидность номера телефона"""
    import re
    patterns = [
        r'^\+7\d{10}$',      # +79123456789
        r'^8\d{10}$',        # 89123456789
        r'^7\d{10}$',        # 79123456789
    ]
    return any(re.match(pattern, phone) for pattern in patterns)


# Главное меню для пользователей С абонементом
def get_main_menu_with_subscription():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📅 Запись на тренировку"))
    builder.add(KeyboardButton(text="👨‍🏫 Посмотреть тренеров"))
    builder.add(KeyboardButton(text="📋 Мои тренировки"))
    builder.add(KeyboardButton(text="ℹ️ Информация о клубе"))
    builder.add(KeyboardButton(text="🎫 Мои абонементы"))
    builder.add(KeyboardButton(text="👨‍💼 Связь с менеджером"))
    builder.add(KeyboardButton(text="💬 Обратная связь"))
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


# Главное меню для пользователей БЕЗ абонемента
def get_main_menu_without_subscription():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🎯 Запись на пробную тренировку"))
    builder.add(KeyboardButton(text="👨‍🏫 Посмотреть тренеров"))
    builder.add(KeyboardButton(text="💳 Купить абонемент"))
    builder.add(KeyboardButton(text="ℹ️ Информация о клубе"))
    builder.add(KeyboardButton(text="👨‍💼 Связь с менеджером"))
    builder.add(KeyboardButton(text="💬 Обратная связь"))
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)


# Кнопка для отправки номера телефона
def get_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="📞 Отправить мой номер", request_contact=True)
        ]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not db.user_exists(user_id):
        # Показываем соглашение
        await message.answer(
            AGREEMENT_TEXT,
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="✅ Принять соглашение")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        await state.set_state(Registration.waiting_for_agreement)
    else:
        await show_main_menu(message)


async def ask_about_subscription(message: types.Message, state: FSMContext):
    """Спрашивает про абонемент после успешной регистрации"""
    await message.answer(
        "✅ Номер телефона сохранен!\n\n"
        "🎫 <b>Есть ли у вас абонемент в наш фитнес-клуб?</b>\n\n"
        "Это поможет нам показать подходящие возможности для тренировок",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Да, есть абонемент")],
                [KeyboardButton(text="❌ Нет, хочу пробную тренировку")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    await state.set_state(Registration.waiting_for_subscription)


@dp.message(Registration.waiting_for_phone, F.contact)
async def process_phone_contact(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number

    # Нормализуем номер
    if phone_number.startswith('+'):
        phone_number = phone_number[1:]

    print(f"Получен номер из контакта: {phone_number}")  # Для отладки

    # Сохраняем пользователя
    db.add_user(
        user_id=message.from_user.id,
        name=message.from_user.full_name,
        phone=phone_number,
        username=message.from_user.username
    )

    await ask_about_subscription(message, state)


@dp.message(Registration.waiting_for_phone)
async def process_phone_text(message: types.Message, state: FSMContext):
    # Пропускаем если это кнопка "⌨️ Ввести номер вручную" (уже обработано выше)
    if message.text == "⌨️ Ввести номер вручную":
        return

    # Пропускаем если это контакт (уже обработано выше)
    if message.contact:
        return

    phone_number = message.text.strip()

    # Проверяем валидность номера
    if not is_valid_phone(phone_number):
        await message.answer(
            "❌ Неверный формат номера. Пожалуйста, введите номер в формате:\n"
            "<b>+7XXXYYYYYYY</b> или <b>8XXXYYYYYYY</b>\n\n"
            "Пример: +79123456789\n"
            "Или нажмите кнопку '📱 Отправить мой номер'",
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[
                    KeyboardButton(text="📱 Отправить мой номер", request_contact=True)
                ]],
                resize_keyboard=True
            )
        )
        return

    # Сохраняем пользователя
    db.add_user(
        user_id=message.from_user.id,
        name=message.from_user.full_name,
        phone=phone_number,
        username=message.from_user.username
    )

    await ask_about_subscription(message, state)


@dp.message(Registration.waiting_for_phone, F.text == "⌨️ Ввести номер вручную")
async def process_phone_manual_choice(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите ваш номер телефона в формате:\n"
        "<b>+7XXXYYYYYYY</b> или <b>8XXXYYYYYYY</b>\n\n"
        "Пример: +79123456789",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove()
    )
    # Остаемся в том же состоянии waiting_for_phone


# Добавьте метод валидации номера в класс (перед обработчиками)


@dp.message(Registration.waiting_for_agreement, F.text == "✅ Принять соглашение")
async def process_agreement(message: types.Message, state: FSMContext):
    await message.answer(
        "📞 <b>Поделитесь вашим номером телефона для связи:</b>\n\n"
        "Нажмите кнопку ниже или введите номер вручную в формате +79123456789",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
                [KeyboardButton(text="⌨️ Ввести номер вручную")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    await state.set_state(Registration.waiting_for_phone)



@dp.message(Registration.waiting_for_subscription)
async def process_subscription_info(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text == "✅ Да, есть абонемент":
        # Создаем премиум абонемент
        db.create_premium_subscription(user_id)
        await message.answer(
            "🎉 Отлично! Активируем ваш абонемент.\n"
            "Теперь вам доступны все тренировки!",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        # Создаем пробный абонемент
        db.create_trial_subscription(user_id)
        await message.answer(
            "🎯 Прекрасно! Предлагаем вам пробную тренировку.\n"
            "После занятия вы сможете приобрести абонемент",
            reply_markup=ReplyKeyboardRemove()
        )

    await show_main_menu(message)
    await state.clear()



#Обработчик для кнопки "Запись на тренировку" (для пользователей с абонементом)
@dp.message(F.text == "📅 Запись на тренировку")
async def show_training_types(message: types.Message, state: FSMContext):
    subscription = db.get_user_subscription(message.from_user.id)

    if not subscription:
        await message.answer("❌ У вас нет активного абонемента.")
        return

    training_types = db.get_training_types()

    buttons = []
    for training_type in training_types:
        buttons.append([types.InlineKeyboardButton(
            text=training_type['name'],
            callback_data=f"type_{training_type['id']}"
        )])

    # Кнопка "Все тренировки"
    buttons.append([types.InlineKeyboardButton(
        text="👀 Все тренировки",
        callback_data="type_all"
    )])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        "🏋️ <b>Выберите тип тренировки:</b>",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_training_type)


@dp.callback_query(Booking.choosing_training_type, F.data.startswith("type_"))
async def process_training_type(callback: types.CallbackQuery, state: FSMContext):
    training_type = callback.data.split("_")[1]

    if training_type == "all":
        trainings = db.get_available_trainings()
        selected_type_name = "Все тренировки"
    else:
        trainings = db.get_trainings_by_type(int(training_type))
        training_types = db.get_training_types()
        selected_type_name = next((t['name'] for t in training_types if t['id'] == int(training_type)), "Тренировка")

    await state.update_data(
        selected_training_type=training_type,
        selected_type_name=selected_type_name
    )

    if not trainings:
        await callback.message.edit_text(
            "❌ Нет доступных тренировок выбранного типа.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_types")]
            ])
        )
        return

    buttons = []
    for training in trainings:
        time_str = training['time'][11:16]  # Форматируем время
        buttons.append([types.InlineKeyboardButton(
            text=f"{training['name']} - {time_str}",
            callback_data=f"training_{training['id']}"
        )])

    # Кнопка "Назад"
    buttons.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_types")])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        f"📅 <b>Выберите тренировку</b> ({selected_type_name}):",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_training)


@dp.callback_query(Booking.choosing_training)
async def process_training_selection(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "back_to_types":
        # Возврат к выбору типа тренировки
        await show_training_types_from_callback(callback, state)
        return

    training_id = int(callback.data.split("_")[1])
    await state.update_data(selected_training_id=training_id)

    dates = db.get_available_dates(training_id)

    if not dates:
        await callback.message.edit_text(
            "❌ Нет доступных дат для этой тренировки.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trainings")]
            ])
        )
        return

    buttons = []
    for date in dates:
        # используем строковое форматирование вместо datetime
        date_str = date['date_str']
        formatted_date = f"{date_str[8:10]}.{date_str[5:7]} в {date_str[11:16]}"
        buttons.append([types.InlineKeyboardButton(
            text=formatted_date,
            callback_data=f"date_{date['id']}"
        )])

    # Кнопка "Назад"
    buttons.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trainings")])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "⏰ <b>Выберите дату и время:</b>",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_time)





async def show_training_types_from_callback(callback: types.CallbackQuery, state: FSMContext):
    """Показывает типы тренировок из callback"""
    training_types = db.get_training_types()

    buttons = []
    for training_type in training_types:
        buttons.append([types.InlineKeyboardButton(
            text=training_type['name'],
            callback_data=f"type_{training_type['id']}"
        )])

    buttons.append([types.InlineKeyboardButton(text="👀 Все тренировки", callback_data="type_all")])
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🏋️ <b>Выберите тип тренировки:</b>",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_training_type)


async def show_trainings_by_type_from_callback(callback: types.CallbackQuery, state: FSMContext, training_type: str):
    """Показывает тренировки определенного типа из callback"""
    if training_type == "all":
        trainings = db.get_available_trainings()
        selected_type_name = "Все тренировки"
    else:
        trainings = db.get_trainings_by_type(int(training_type))
        training_types = db.get_training_types()
        selected_type_name = next((t['name'] for t in training_types if t['id'] == int(training_type)), "Тренировка")

    if not trainings:
        await callback.message.edit_text("❌ Нет доступных тренировок.")
        return

    buttons = []
    for training in trainings:
        time_str = training['time'][11:16]
        buttons.append([types.InlineKeyboardButton(
            text=f"{training['name']} - {time_str}",
            callback_data=f"training_{training['id']}"
        )])

    buttons.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_types")])
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        f"📅 <b>Выберите тренировку</b> ({selected_type_name}):",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_training)


@dp.message(F.text == "🎯 Запись на пробную тренировку")
async def show_trial_training_types(message: types.Message, state: FSMContext):
    """Показывает типы тренировок для пробного занятия с ограничениями"""
    subscription = db.get_user_subscription(message.from_user.id)

    # Проверяем доступность пробной тренировки
    if not subscription or subscription['type'] != 'trial':
        await message.answer(
            "❌ <b>Пробная тренировка недоступна</b>\n\n"
            "У вас нет активного пробного абонемента.\n"
            "Обратитесь к менеджеру для получения пробного доступа.",
            parse_mode='HTML'
        )
        return

    # Проверяем не использована ли уже пробная тренировка
    bookings_count = db.get_user_bookings_count(message.from_user.id)
    if bookings_count >= 1:
        await message.answer(
            "❌ <b>Пробная тренировка уже использована</b>\n\n"
            "Вы уже записаны на 1 тренировку.\n"
            "Чтобы записаться на большее количество занятий:\n"
            "• Отмените текущую запись в разделе 'Мои тренировки'\n"
            "• Или приобретите полноценный абонемент",
            parse_mode='HTML'
        )
        return

    training_types = db.get_training_types()

    buttons = []
    for training_type in training_types:
        buttons.append([types.InlineKeyboardButton(
            text=training_type['name'],
            callback_data=f"trial_type_{training_type['id']}"
        )])

    # Кнопка "Все тренировки" для пробного пользователя
    buttons.append([types.InlineKeyboardButton(
        text="👀 Все доступные тренировки",
        callback_data="trial_type_all"
    )])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        "🎯 <b>Выберите тип тренировки для пробного занятия:</b>\n\n"
        "💡 <i>Это ваша единственная пробная тренировка</i>\n"
        "⏰ Будьте внимательны при выборе времени",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_training_type)


@dp.callback_query(F.data.startswith("cancel_"))
async def process_booking_cancellation(callback: types.CallbackQuery):
    """Обработчик отмены записи на тренировку"""
    try:
        booking_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id

        print(f"DEBUG: Отмена записи {booking_id} пользователем {user_id}")

        # Получаем информацию о записи
        booking_info = db.get_booking_by_id(booking_id)
        if not booking_info:
            await callback.answer("❌ Запись не найдена")
            return

        # Проверяем, что запись принадлежит пользователю
        if booking_info['user_id'] != user_id:
            await callback.answer("❌ Это не ваша запись")
            return

        # Проверяем статус записи
        if booking_info['status'] == 'cancelled':
            await callback.answer("❌ Запись уже отменена")
            return

        # Отменяем запись
        if db.cancel_booking(user_id, booking_id):
            # Форматируем дату для сообщения
            date_str = booking_info['date']
            if ' ' in date_str:
                date_part, time_part = date_str.split(' ')
                formatted_date = f"{date_part[8:10]}.{date_part[5:7]}.{date_part[2:4]} в {time_part[:5]}"
            else:
                formatted_date = date_str

            success_text = (
                f"✅ <b>Запись отменена</b>\n\n"
                f"🏋️ Тренировка: {booking_info['training_name']}\n"
                f"📅 Дата: {formatted_date}\n\n"
                f"💡 Место освобождено для других участников"
            )

            await callback.message.edit_text(success_text, parse_mode='HTML')
            await callback.answer("Запись отменена")
        else:
            await callback.answer("❌ Не удалось отменить запись")

    except Exception as e:
        print(f"ERROR в process_booking_cancellation: {e}")
        await callback.answer("❌ Произошла ошибка при отмене записи")

@dp.callback_query(Booking.choosing_training_type, F.data.startswith("trial_type_"))
async def process_trial_training_type(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора типа тренировки для пробных пользователей"""
    training_type = callback.data.split("_")[2]  # trial_type_1 → 1

    if training_type == "all":
        trainings = db.get_available_trainings()
        selected_type_name = "все тренировки"
    else:
        trainings = db.get_trainings_by_type(int(training_type))
        training_types = db.get_training_types()
        selected_type_name = next((t['name'] for t in training_types if t['id'] == int(training_type)), "тренировка")

    await state.update_data(
        selected_training_type=training_type,
        selected_type_name=selected_type_name,
        is_trial=True  # Помечаем что это пробная запись
    )

    if not trainings:
        await callback.message.edit_text(
            "❌ Нет доступных тренировок выбранного типа.\n"
            "Попробуйте выбрать другой тип тренировки.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад к выбору типа", callback_data="back_to_trial_types")]
            ])
        )
        return

    buttons = []
    for training in trainings:
        time_str = training['time'][11:16]
        buttons.append([types.InlineKeyboardButton(
            text=f"{training['name']} - {time_str}",
            callback_data=f"trial_training_{training['id']}"
        )])

    # Кнопка "Назад" для пробных пользователей
    buttons.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trial_types")])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        f"🎯 <b>Выберите тренировку для пробного занятия</b> ({selected_type_name}):\n\n"
        f"💡 <i>Это ваша единственная пробная запись</i>",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_training)


@dp.callback_query(Booking.choosing_training, F.data.startswith("trial_training_"))
async def process_trial_training_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора тренировки для пробных пользователей"""
    if callback.data == "back_to_trial_types":
        await show_trial_training_types_from_callback(callback, state)
        return

    training_id = int(callback.data.split("_")[2])  # trial_training_1 → 1
    await state.update_data(selected_training_id=training_id)

    dates = db.get_available_dates(training_id)

    if not dates:
        await callback.message.edit_text(
            "❌ Нет доступных дат для этой тренировки.\n"
            "Пожалуйста, выберите другую тренировку.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅️ Назад к тренировкам", callback_data="back_to_trial_trainings")]
            ])
        )
        return

    buttons = []
    for date in dates:
        date_str = date['date_str']
        formatted_date = f"{date_str[8:10]}.{date_str[5:7]} в {date_str[11:16]}"
        buttons.append([types.InlineKeyboardButton(
            text=formatted_date,
            callback_data=f"trial_date_{date['id']}"
        )])

    buttons.append([types.InlineKeyboardButton(text="⬅️ Назад к тренировкам", callback_data="back_to_trial_trainings")])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "⏰ <b>Выберите дату и время для пробной тренировки:</b>\n\n"
        "💡 <i>После записи отменить можно в разделе 'Мои тренировки'</i>",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_time)


@dp.callback_query(Booking.choosing_time, F.data.startswith("trial_date_"))
async def process_trial_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора времени для пробных пользователей"""
    if callback.data == "back_to_trial_trainings":
        data = await state.get_data()
        training_type = data.get('selected_training_type', 'all')
        await show_trial_trainings_by_type_from_callback(callback, state, training_type)
        return

    schedule_id = int(callback.data.split("_")[2])  # trial_date_1 → 1
    user_id = callback.from_user.id

    # Дополнительная проверка для пробных пользователей
    subscription = db.get_user_subscription(user_id)
    if not subscription or subscription['type'] != 'trial':
        await callback.message.edit_text(
            "❌ <b>Пробный абонемент не активен</b>\n\n"
            "Невозможно завершить запись на пробную тренировку.",
            parse_mode='HTML'
        )
        await state.clear()
        return

    bookings_count = db.get_user_bookings_count(user_id)
    if bookings_count >= 1:
        await callback.message.edit_text(
            "❌ <b>Пробная тренировка уже использована</b>\n\n"
            "Вы уже записаны на 1 тренировку.\n"
            "Отмените текущую запись или приобретите абонемент.",
            parse_mode='HTML'
        )
        await state.clear()
        return

    # Проверка дублирования и создание записи
    if db.has_duplicate_booking(user_id, schedule_id):
        await callback.message.edit_text("❌ Вы уже записаны на эту тренировку!")
        await state.clear()
        return

    if db.create_booking(user_id, schedule_id, 'trial'):
        await callback.message.edit_text(
            "🎉 <b>Пробная тренировка забронирована!</b>\n\n"
            "✅ Вы успешно записаны на пробное занятие\n"
            "📅 Не забудьте посетить тренировку\n"
            "❌ Отменить запись можно в разделе 'Мои тренировки'\n\n"
            "💡 <i>После пробного занятия приобретите абонемент для продолжения тренировок</i>",
            parse_mode='HTML'
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Не удалось записаться</b>\n\n"
            "Возможно места закончились или произошла ошибка.\n"
            "Попробуйте выбрать другое время или свяжитесь с менеджером.",
            parse_mode='HTML'
        )

    await state.clear()


async def show_trial_training_types_from_callback(callback: types.CallbackQuery, state: FSMContext):
    """Показывает типы тренировок для пробных из callback"""
    training_types = db.get_training_types()

    buttons = []
    for training_type in training_types:
        buttons.append([types.InlineKeyboardButton(
            text=training_type['name'],
            callback_data=f"trial_type_{training_type['id']}"
        )])

    buttons.append([types.InlineKeyboardButton(text="👀 Все доступные тренировки", callback_data="trial_type_all")])
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🎯 <b>Выберите тип тренировки для пробного занятия:</b>\n\n"
        "💡 <i>Это ваша единственная пробная тренировка</i>",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_training_type)


async def show_trial_trainings_by_type_from_callback(callback: types.CallbackQuery, state: FSMContext,
                                                     training_type: str):
    """Показывает тренировки для пробных пользователей"""
    if training_type == "all":
        trainings = db.get_available_trainings()
        selected_type_name = "все тренировки"
    else:
        trainings = db.get_trainings_by_type(int(training_type))
        training_types = db.get_training_types()
        selected_type_name = next((t['name'] for t in training_types if t['id'] == int(training_type)), "тренировка")

    if not trainings:
        await callback.message.edit_text("❌ Нет доступных тренировок.")
        return

    buttons = []
    for training in trainings:
        time_str = training['time'][11:16]
        buttons.append([types.InlineKeyboardButton(
            text=f"{training['name']} - {time_str}",
            callback_data=f"trial_training_{training['id']}"
        )])

    buttons.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trial_types")])
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        f"🎯 <b>Выберите тренировку для пробного занятия</b> ({selected_type_name}):\n\n"
        f"💡 <i>Это ваша единственная пробная запись</i>",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await state.set_state(Booking.choosing_training)
@dp.callback_query(Booking.choosing_time)
async def process_date_selection(callback: types.CallbackQuery, state: FSMContext):
    # Обработка кнопки "Назад"
    if callback.data == "back_to_trainings":
        data = await state.get_data()
        training_type = data.get('selected_training_type', 'all')
        await show_trainings_by_type_from_callback(callback, state, training_type)
        return

    # Основная логика с вашими ограничениями
    schedule_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    # Получаем информацию об абонементе
    subscription = db.get_user_subscription(user_id)
    subscription_type = subscription['type'] if subscription else None

    # Проверяем дублирующую запись
    if db.has_duplicate_booking(user_id, schedule_id):
        await callback.message.edit_text(
            "❌ Вы уже записаны на эту тренировку!\n"
            "Вы не можете записаться дважды на одно и то же занятие."
        )
        await state.clear()
        return

    # Для пользователей без абонемента или с пробным - проверяем ограничение
    if not subscription or subscription_type == 'trial':
        bookings_count = db.get_user_bookings_count(user_id)
        if bookings_count >= 1:
            await callback.message.edit_text(
                "❌ <b>Ограничение записи</b>\n\n"
                "С пробным абонементом можно записаться только на <b>1 тренировку</b>.\n"
                "Чтобы записаться на большее количество занятий, приобретите полноценный абонемент.",
                parse_mode='HTML'
            )
            await state.clear()
            return

    if db.create_booking(user_id, schedule_id, subscription_type):
        # Показываем разное сообщение в зависимости от типа абонемента
        if not subscription or subscription_type == 'trial':
            message_text = (
                "✅ Вы успешно записаны на <b>пробную тренировку</b>!\n\n"
                "📝 <i>Это ваша единственная запись с пробным абонементом</i>\n"
                "❌ Отменить запись можно в разделе 'Мои тренировки'\n"
                "💳 Для записи на большее количество занятий приобретите полноценный абонемент"
            )
        else:
            message_text = (
                "✅ Вы успешно записаны на тренировку!\n\n"
                "❌ Отменить запись можно в разделе 'Мои тренировки'"
            )

        await callback.message.edit_text(message_text, parse_mode='HTML')
    else:
        await callback.message.edit_text(
            "❌ Не удалось записаться. Возможно:\n"
            "• Места закончились\n"
            "• Произошла ошибка"
        )

    await state.clear()



# Обработчик для кнопки "Мои абонементы"
@dp.message(F.text == "🎫 Мои абонементы")
async def show_subscriptions(message: types.Message):
    subscription = db.get_user_subscription(message.from_user.id)

    if not subscription:
        await message.answer("❌ У вас нет активных абонементов.")
        return

    sub_type = "🏆 Премиум" if subscription['type'] == 'premium' else "🎯 Пробный"

    # Получаем количество текущих записей
    bookings_count = db.get_user_bookings_count(message.from_user.id)

    text = (
        f"🎫 <b>Ваш абонемент</b>\n"
        f"Тип: {sub_type}\n"
    )

    if subscription['type'] == 'trial':
        text += f"📊 Активных записей: {bookings_count}/1\n\n"
        text += "💡 <i>С пробным абонементом можно записаться только на 1 тренировку</i>"
    else:
        text += f"📊 Активных записей: {bookings_count}\n\n"
        text += "💪 <i>Вам доступны все групповые тренировки</i>"

    await message.answer(text, parse_mode='HTML')

# Обработчик для кнопки "Купить абонемент"
@dp.message(F.text == "💳 Купить абонемент")
async def show_buy_subscription(message: types.Message):
    # Получаем количество текущих записей для пользователя
    bookings_count = db.get_user_bookings_count(message.from_user.id)

    text = (
        f"💳 <b>Приобретение абонемента</b>\n\n"
        f"📊 Ваших активных записей: {bookings_count}\n\n"
        "Для покупки абонемента свяжитесь с менеджером:\n"
        "@fitnesmanager\n\n"
        "<b>Доступные варианты:</b>\n"
        "• 🎯 Пробный - 1 занятие (бесплатно)\n"
        "• 🔹 Базовый - до 4 занятий одновременно\n"
        "• 🏆 Премиум - до 8 занятий одновременно\n"
        "• 💫 Безлимитный - неограниченно"
    )
    await message.answer(text, parse_mode='HTML')


# Обработчик для кнопки "Обратная связь"
@dp.message(F.text == "💬 Обратная связь")
async def show_developers(message: types.Message):
    await message.answer(DEVELOPERS, parse_mode='HTML')


# Обработчик для кнопки "Связь с менеджером"
@dp.message(F.text == "👨‍💼 Связь с менеджером")
async def contact_manager(message: types.Message):
    await message.answer(
        "👨‍💼 <b>Связь с менеджером</b>\n\n"
        "По вопросам абонементов, тренировок и расписания:\n"
        "@fitnesmanager\n\n"
        "Мы ответим вам в течение 15 минут в рабочее время (9:00-21:00)",
        parse_mode='HTML'
    )


# Обработчик для кнопки "Посмотреть тренеров"
@dp.message(F.text == "👨‍🏫 Посмотреть тренеров")
async def show_trainers(message: types.Message):
    trainers_text = (
        "👨‍🏫 <b>Наша команда тренеров</b>\n\n"
        "• <b>Анна</b> - Йога, Стретчинг\n"
        "  Опыт: 5 лет\n\n"
        "• <b>Максим</b> - Силовые тренировки, Функциональный тренинг\n"
        "  Опыт: 7 лет\n\n"
        "• <b>Мария</b> - Пилатес, Калланетика\n"
        "  Опыт: 4 года\n\n"
        "Все тренеры имеют сертификаты и высшее образование в области фитнеса."
    )
    await message.answer(trainers_text, parse_mode='HTML')


# Обработчик для кнопки "Информация о клубе"
@dp.message(F.text == "ℹ️ Информация о клубе")
async def show_club_info(message: types.Message):
    club_info = (
        "🏋️ <b>Фитнес-клуб QuickGym</b>\n\n"
        "📍 <b>Адрес:</b> ул. Примерная, 123\n"
        "🕒 <b>Часы работы:</b> 7:00-23:00\n"
        "📞 <b>Телефон:</b> +7 (495) 123-45-67\n\n"
        "<b>Оснащение:</b>\n"
        "• Современные тренажеры\n"
        "• Зал для групповых занятий\n"
        "• Кардио-зона\n"
        "• Раздевалки с душевыми\n"
        "• Бесплатный Wi-Fi\n\n"
        "Мы находимся в 5 минутах от метро «Примерная»"
    )
    await message.answer(club_info, parse_mode='HTML')


# Обработчик для кнопки "Мои тренировки"
@dp.message(F.text == "📋 Мои тренировки")
async def show_user_bookings(message: types.Message):
    """Показывает записи пользователя на тренировки"""
    try:
        user_id = message.from_user.id
        print(f"DEBUG: Пользователь {user_id} нажал 'Мои тренировки'")

        # Получаем записи
        bookings = db.get_user_bookings(user_id)
        print(f"DEBUG: Найдено записей: {len(bookings)}")
        print(f"DEBUG: Записи: {bookings}")

        if not bookings:
            await message.answer("📭 У вас нет активных записей на тренировки")
            return

        # Разделяем активные и отмененные записи
        active_bookings = [b for b in bookings if b['status'] == 'active']
        cancelled_bookings = [b for b in bookings if b['status'] == 'cancelled']

        text = "📋 <b>Ваши записи:</b>\n\n"

        # Активные записи
        if active_bookings:
            text += "✅ <b>Активные записи:</b>\n"
            for booking in active_bookings:
                # Форматируем дату
                date_str = booking['date']
                if ' ' in date_str:
                    date_part, time_part = date_str.split(' ')
                    formatted_date = f"{date_part[8:10]}.{date_part[5:7]}.{date_part[2:4]} в {time_part[:5]}"
                else:
                    formatted_date = date_str

                text += f"• {booking['training_name']}\n"
                text += f"  ⏰ {formatted_date}\n"
                text += f"  🆔 ID: {booking['booking_id']}\n\n"

        # Отмененные записи
        if cancelled_bookings:
            text += "❌ <b>Отмененные записи:</b>\n"
            for booking in cancelled_bookings:
                date_str = booking['date']
                if ' ' in date_str:
                    date_part, time_part = date_str.split(' ')
                    formatted_date = f"{date_part[8:10]}.{date_part[5:7]}.{date_part[2:4]} в {time_part[:5]}"
                else:
                    formatted_date = date_str
                text += f"• {booking['training_name']} - {formatted_date}\n"
            text += "\n"

        # Если есть активные записи - показываем кнопки отмены
        if active_bookings:
            buttons = []
            for booking in active_bookings:
                # Форматируем дату для кнопки
                date_str = booking['date']
                if ' ' in date_str:
                    date_part, time_part = date_str.split(' ')
                    formatted_date = f"{date_part[8:10]}.{date_part[5:7]} {time_part[:5]}"
                else:
                    formatted_date = date_str

                buttons.append([types.InlineKeyboardButton(
                    text=f"❌ Отменить {booking['training_name']} ({formatted_date})",
                    callback_data=f"cancel_{booking['booking_id']}"
                )])

            keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)

            # Добавляем информацию об ограничениях
            subscription = db.get_user_subscription(user_id)
            if subscription and subscription['type'] == 'trial':
                text += "💡 <i>С пробным абонементом можно иметь только 1 активную запись</i>"
            else:
                text += "💡 <i>Для отмены нажмите на кнопку ниже</i>"

            await message.answer(text, parse_mode='HTML', reply_markup=keyboard)
        else:
            await message.answer(text, parse_mode='HTML')

    except Exception as e:
        print(f"ERROR в show_user_bookings: {e}")
        await message.answer("❌ Произошла ошибка при загрузке ваших записей")
async def show_main_menu(message: types.Message):
    """Показывает главное меню в зависимости от наличия абонемента"""
    subscription = db.get_user_subscription(message.from_user.id)

    if subscription:
        await message.answer(
            "🏋️ Выберите действие:",
            reply_markup=get_main_menu_with_subscription()
        )
    else:
        await message.answer(
            "🎯 Добро пожаловать! Начните с пробной тренировки:",
            reply_markup=get_main_menu_without_subscription()
        )


async def main():
    logging.info("Starting fitness bot...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Bot crashed: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
