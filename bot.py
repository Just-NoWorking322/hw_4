import smtplib
from email.mime.text import MIMEText
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from config import token, smtp_server, smtp_port, smtp_user, smtp_password
import re
import logging
from aiosqlite import connect as async_connect
from aiogram import Router

bot = Bot(token=token) 
dp = Dispatcher()
dp.include_router(Router())

logging.basicConfig(level=logging.INFO)

async def init_db():
    async with async_connect("emails.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY,
            recipient TEXT,
            message TEXT,
            status TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.commit()

def val_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email)

async def send_email(recipient, message):
    if not val_email(recipient):
        return "Некорректный eвфmail"

    if not message.strip():
        return "Сообщение не может быть пустым"

    if len(message) > 1000:
        return "Сообщение слишком длинное (максимум 1000 символов)"

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)

            msg = MIMEText(message)
            msg["From"] = smtp_user
            msg["To"] = recipient
            msg["Subject"] = "Сообщение от Telegram-бота"

            server.sendmail(smtp_user, recipient, msg.as_string())
            status = "Успешно"
    except Exception as e:
        status = f"Ошибка: {e}"

    async with async_connect("emails.db") as db:
        await db.execute("INSERT INTO emails (recipient, message, status) VALUES (?, ?, ?)",
                         (recipient, message, status))
        await db.commit()

    return status

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Привет! Введите email получателя:")

@dp.message()
async def process_email(message: Message, state):
    email = message.text.strip()
    if not val_email(email):
        await message.reply("Некорректный email. Попробуйте снова.")
    else:
        await state.update_data(recipient=email)
        await message.reply("Введите текст сообщения (макс. 1000 символов):")

@dp.message(lambda msg: len(msg.text.strip()) > 1000)
async def long_message_handler(message: Message):
    await message.reply("Сообщение слишком длинное. Укоротите его до 1000 символов.")

@dp.message()
async def send_message_handler(message: Message, state):
    data = await state.get_data()
    recipient = data.get("recipient")
    result = await send_email(recipient, message.text.strip())
    await message.reply(result)

@dp.message(Command("log"))
async def log_handler(message: Message):
    async with async_connect("emails.db") as db:
        cursor = await db.execute("SELECT * FROM emails ORDER BY sent_at DESC")
        rows = await cursor.fetchall()
        if rows:
            log = "\n".join([f"{row[3]} | {row[1]} | {row[2][:50]}..." for row in rows])
            await message.reply(f"Лог:\n{log}")
        else:
            await message.reply("Лог пуст.")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
