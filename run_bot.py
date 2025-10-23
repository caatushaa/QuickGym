# run_bot.py - основной файл для запуска на PythonAnywhere
import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from main import dp, db, bot

# Настройка логирования для PythonAnywhere
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),  # Логи в файл
        logging.StreamHandler()          # Логи в консоль
    ]
)

async def main():
    logging.info("=== Starting Fitness Bot on PythonAnywhere ===")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Bot crashed: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())