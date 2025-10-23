import os
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
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()
db = Database("fitness_bot.db")

# States для FSM
class Registration(StatesGroup):
    waiting_for_agreement = State()
    waiting_for_phone = State()
    waiting_for_age_confirmation = State()

class Booking(StatesGroup):
    choosing_training = State()
    choosing_time = State()

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

@dp.message(Registration.waiting_for_agreement, F.text == "✅ Принять соглашение")
async def process_agreement(message: types.Message, state: FSMContext):
    await message.answer(
        "📞 Теперь поделитесь вашим номером телефона для связи:",
        reply_markup=get_phone_keyboard()
    )
    await state.set_state(Registration.waiting_for_phone)

@dp.message(Registration.waiting_for_phone, F.contact)
async def process_phone_contact(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number
    
    # Сохраняем пользователя
    db.add_user(
        user_id=message.from_user.id,
        name=message.from_user.full_name,
        phone=phone_number,
        username=message.from_user.username
    )
    
    # Создаем пробный абонемент
    db.create_trial_subscription(message.from_user.id)
    
    await message.answer(
        "✅ Регистрация завершена! Теперь вам доступна пробная тренировка.",
        reply_markup=ReplyKeyboardRemove()
    )
    await show_main_menu(message)
    await state.clear()

# Обработчик для кнопки "Запись на тренировку" (для пользователей с абонементом)
@dp.message(F.text == "📅 Запись на тренировку")
async def show_trainings_with_subscription(message: types.Message, state: FSMContext):
    subscription = db.get_user_subscription(message.from_user.id)
    
    if not subscription or subscription['sessions_left'] <= 0:
        await message.answer("❌ У вас нет активного абонемента или закончились занятия.")
        return
    
    trainings = db.get_available_trainings()
    
    if not trainings:
        await message.answer("На данный момент нет доступных тренировок")
        return
    
    buttons = []
    for training in trainings:
        buttons.append([types.InlineKeyboardButton(
            text=f"{training['name']} - {training['time']}",
            callback_data=f"training_{training['id']}"
        )])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите тренировку:", reply_markup=keyboard)
    await state.set_state(Booking.choosing_training)

# Обработчик для кнопки "Запись на пробную тренировку"
@dp.message(F.text == "🎯 Запись на пробную тренировку")
async def show_trial_trainings(message: types.Message, state: FSMContext):
    subscription = db.get_user_subscription(message.from_user.id)
    
    if not subscription or subscription['type'] != 'trial' or subscription['sessions_left'] <= 0:
        await message.answer("❌ У вас нет доступных пробных тренировок.")
        return
    
    trainings = db.get_available_trainings()
    
    if not trainings:
        await message.answer("На данный момент нет доступных тренировок для записи")
        return
    
    buttons = []
    for training in trainings:
        buttons.append([types.InlineKeyboardButton(
            text=f"{training['name']} - {training['time']}",
            callback_data=f"training_{training['id']}"
        )])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("🎯 Выберите тренировку для пробного занятия:", reply_markup=keyboard)
    await state.set_state(Booking.choosing_training)

@dp.callback_query(Booking.choosing_training)
async def process_training_selection(callback: types.CallbackQuery, state: FSMContext):
    training_id = int(callback.data.split("_")[1])
    await state.update_data(training_id=training_id)
    
    dates = db.get_available_dates(training_id)
    
    if not dates:
        await callback.message.edit_text("❌ Нет доступных дат для этой тренировки")
        await state.clear()
        return
    
    buttons = []
    for date in dates:
        buttons.append([types.InlineKeyboardButton(
            text=date['date_str'],
            callback_data=f"date_{date['id']}"
        )])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выберите дату:", reply_markup=keyboard)
    await state.set_state(Booking.choosing_time)

@dp.callback_query(Booking.choosing_time)
async def process_date_selection(callback: types.CallbackQuery, state: FSMContext):
    schedule_id = int(callback.data.split("_")[1])
    user_data = await state.get_data()
    
    # Проверяем абонемент и списываем занятие
    subscription = db.get_user_subscription(callback.from_user.id)
    if not subscription or subscription['sessions_left'] <= 0:
        await callback.message.edit_text("❌ У вас нет доступных занятий.")
        await state.clear()
        return
    
    if db.create_booking(callback.from_user.id, schedule_id):
        # Списываем одно занятие
        db.update_subscription_sessions(callback.from_user.id)
        
        remaining = subscription['sessions_left'] - 1
        await callback.message.edit_text(
            f"✅ Вы успешно записаны на тренировку!\n"
            f"🎫 Осталось занятий: {remaining}"
        )
    else:
        await callback.message.edit_text("❌ Не удалось записаться. Возможно, места закончились.")
    
    await state.clear()

# Обработчик для кнопки "Мои абонементы"
@dp.message(F.text == "🎫 Мои абонементы")
async def show_subscriptions(message: types.Message):
    subscription = db.get_user_subscription(message.from_user.id)
    
    if not subscription:
        await message.answer("❌ У вас нет активных абонементов.")
        return
    
    sub_type = "Премиум" if subscription['type'] == 'premium' else "Пробный"
    text = (
        f"🎫 <b>Ваш абонемент</b>\n"
        f"Тип: {sub_type}\n"
        f"Осталось занятий: {subscription['sessions_left']}\n"
        f"Действует до: {subscription['expires_at'][:10]}"
    )
    await message.answer(text, parse_mode='HTML')

# Обработчик для кнопки "Купить абонемент"
@dp.message(F.text == "💳 Купить абонемент")
async def show_buy_subscription(message: types.Message):
    text = (
        "💳 <b>Приобретение абонемента</b>\n\n"
        "Для покупки абонемента свяжитесь с менеджером:\n"
        "@fitnesmanager\n\n"
        "Доступные варианты:\n"
        "• Пробный - 1 занятие (бесплатно)\n"
        "• Базовый - 4 занятия\n"
        "• Премиум - 8 занятий\n"
        "• Безлимитный - на месяц"
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
    bookings = db.get_user_bookings(message.from_user.id)
    
    if not bookings:
        await message.answer("У вас нет активных записей на тренировки")
        return
    
    text = "📋 <b>Ваши записи:</b>\n\n"
    for booking in bookings:
        status_emoji = "✅" if booking['status'] == 'active' else "❌"
        text += f"{status_emoji} <b>{booking['training_name']}</b>\n"
        text += f"   ⏰ {booking['date']}\n"
        text += f"   Статус: {booking['status']}\n\n"
    
    await message.answer(text, parse_mode='HTML')

async def show_main_menu(message: types.Message):
    """Показывает главное меню в зависимости от наличия абонемента"""
    subscription = db.get_user_subscription(message.from_user.id)
    
    if subscription and subscription['sessions_left'] > 0:
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
