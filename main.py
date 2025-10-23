import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import Database

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Создаем экземпляры
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()
db = Database("fitness_bot.db")


# States для FSM
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()


class Booking(StatesGroup):
    choosing_training = State()
    choosing_time = State()


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if not db.user_exists(user_id):
        await message.answer("👋 Добро пожаловать! Для регистрации введите ваше имя:")
        await state.set_state(Registration.waiting_for_name)
    else:
        await show_main_menu(message)


@dp.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📞 Теперь введите ваш номер телефона:")
    await state.set_state(Registration.waiting_for_phone)


@dp.message(Registration.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    user_data = await state.get_data()

    db.add_user(
        user_id=message.from_user.id,
        name=user_data['name'],
        phone=message.text,
        username=message.from_user.username
    )

    await message.answer("✅ Регистрация завершена!")
    await show_main_menu(message)
    await state.clear()


async def show_main_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📅 Записаться на тренировку")],
            [types.KeyboardButton(text="📋 Мои записи"),
             types.KeyboardButton(text="❓ FAQ")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите действие:", reply_markup=keyboard)


@dp.message(lambda message: message.text and "Записаться на тренировку" in message.text)
async def show_trainings(message: types.Message, state: FSMContext):
    trainings = db.get_available_trainings()

    if not trainings:
        await message.answer("На данный момент нет доступных тренировок")
        return

    keyboard = types.InlineKeyboardMarkup()
    for training in trainings:
        keyboard.add(types.InlineKeyboardButton(
            text=f"{training['name']} - {training['time']}",
            callback_data=f"training_{training['id']}"
        ))

    await message.answer("Выберите тренировку:", reply_markup=keyboard)
    await state.set_state(Booking.choosing_training)


@dp.callback_query(Booking.choosing_training)
async def process_training_selection(callback: types.CallbackQuery, state: FSMContext):
    training_id = int(callback.data.split("_")[1])
    await state.update_data(training_id=training_id)

    dates = db.get_available_dates(training_id)
    keyboard = types.InlineKeyboardMarkup()
    for date in dates:
        keyboard.add(types.InlineKeyboardButton(
            text=date['date_str'],
            callback_data=f"date_{date['id']}"
        ))

    await callback.message.edit_text("Выберите дату:", reply_markup=keyboard)
    await state.set_state(Booking.choosing_time)


@dp.callback_query(Booking.choosing_time)
async def process_date_selection(callback: types.CallbackQuery, state: FSMContext):
    schedule_id = int(callback.data.split("_")[1])
    user_data = await state.get_data()

    if db.create_booking(callback.from_user.id, schedule_id):
        await callback.message.edit_text("✅ Вы успешно записаны на тренировку!")
    else:
        await callback.message.edit_text("❌ Не удалось записаться. Возможно, места закончились.")

    await state.clear()


@dp.message(lambda message: message.text == "📋 Мои записи")
async def show_user_bookings(message: types.Message):
    bookings = db.get_user_bookings(message.from_user.id)

    if not bookings:
        await message.answer("У вас нет активных записей")
        return

    text = "Ваши записи:\n\n"
    for booking in bookings:
        text += f"📅 {booking['training_name']}\n"
        text += f"⏰ {booking['date']}\n"
        text += f"Статус: {booking['status']}\n\n"

    await message.answer(text)


@dp.message(lambda message: message.text == "❓ FAQ")
async def show_faq(message: types.Message):
    faq_text = """
🤔 Часто задаваемые вопросы:

❓ Как отменить запись?
➡ Напишите администратору @username

❓ Что взять с собой на тренировку?
➡ Удобную форму, воду и хорошее настроение!

❓ Есть ли бесплатное пробное занятие?
➡ Да, первая тренировка бесплатно!
    """
    await message.answer(faq_text)

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
