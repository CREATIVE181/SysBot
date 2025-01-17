import os
import psutil
import logging
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("Токен или ID чата не найдены в .env файле.")

bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_cpu_temperature():
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                return temps['coretemp'][0].current

        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read()) / 1000
    except Exception as e:
        logging.error(f"Не удалось получить температуру CPU: {e}")
    return None

def execute_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        logging.error(f"Ошибка при выполнении команды: {e}")
        return f"Ошибка: {e}"

async def check_critical_events():
    cpu_usage = psutil.cpu_percent(interval=1)
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    cpu_temp = get_cpu_temperature()

    warnings = []
    if cpu_usage > 90:
        warnings.append("⚠️ <b>Внимание!</b> Загрузка CPU превышает 90%.")
    if ram_usage > 90:
        warnings.append("⚠️ <b>Внимание!</b> Загрузка RAM превышает 90%.")
    if disk_usage > 90:
        warnings.append("⚠️ <b>Внимание!</b> Диск заполнен более чем на 90%.")
    if cpu_temp is not None and cpu_temp > 80:
        warnings.append("⚠️ <b>Внимание!</b> Температура CPU превышает 80°C.")

    for warning in warnings:
        await bot.send_message(chat_id=CHAT_ID, text=warning, parse_mode=ParseMode.HTML)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Я бот для мониторинга сервера. Используй /help для списка команд.")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        f"📋 <b>Список команд:</b>\n"
        f"/start - Начать работу с ботом\n"
        f"/help - Показать это сообщение\n"
        f"/status - Показать текущее состояние сервера\n"
        f"/c &lt;команда&gt; - Выполнить команду на сервере\n"
        f"/top - Показать топ процессов\n"
        f"/netstat - Показать активные сетевые соединения\n"
        f"/traffic - Показать трафик\n"
        f"/ssh &lt;add|remove&gt; &lt;публичный_ключ&gt; - Управление SSH-ключами"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("status"))
async def cmd_status(message: Message):
    cpu_usage = psutil.cpu_percent(interval=1)
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    cpu_temp = get_cpu_temperature()

    status_message = (
        "📊 <b>Состояние сервера:</b>\n"
        f"• <b>CPU:</b> {cpu_usage}%\n"
        f"• <b>RAM:</b> {ram_usage}%\n"
        f"• <b>Диск:</b> {disk_usage}%\n"
    )

    if cpu_temp is not None:
        status_message += f"• <b>Температура CPU:</b> {cpu_temp}°C\n"
    else:
        status_message += "• <b>Температура CPU:</b> N/A\n"

    await message.answer(status_message, parse_mode=ParseMode.HTML)

@dp.message(Command("c"))
async def cmd_execute(message: Message):
    if str(message.from_user.id) != CHAT_ID:
        await message.answer("❌ У вас нет прав для выполнения команд.")
        return

    command = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if not command:
        await message.answer("❌ Укажите команду для выполнения.")
        return

    result = execute_command(command)
    await message.answer(f"✅ Результат выполнения команды:\n<pre>{result}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("top"))
async def cmd_top(message: Message):
    try:
        processes = sorted(
            psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
            key=lambda p: p.info['cpu_percent'], reverse=True
        )[:5]

        response = "📊 <b>Топ процессов:</b>\n"
        for p in processes:
            response += f"• PID: {p.info['pid']}, Имя: {p.info['name']}, CPU: {p.info['cpu_percent']}%, RAM: {p.info['memory_percent']}%\n"

        await message.answer(response, parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<pre>{str(e)}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("netstat"))
async def cmd_netstat(message: Message):
    try:
        result = subprocess.run("netstat -tuln", shell=True, capture_output=True, text=True)
        output = result.stdout or result.stderr

        await message.answer(f"📡 <b>Активные соединения:</b>\n<pre>{output}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<pre>{str(e)}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("ssh"))
async def cmd_ssh(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Используйте: /ssh <add|remove> <публичный_ключ>", parse_mode=ParseMode.HTML)
        return

    action, key = args[1], args[2]
    try:
        if action == "add":
            with open("/root/.ssh/authorized_keys", "a") as f:
                f.write(f"\n{key}")
        elif action == "remove":
            with open("/root/.ssh/authorized_keys", "r") as f:
                lines = f.readlines()
            with open("/root/.ssh/authorized_keys", "w") as f:
                for line in lines:
                    if key not in line:
                        f.write(line)
        else:
            await message.answer("❌ Неверное действие. Используйте add или remove.", parse_mode=ParseMode.HTML)
            return

        await message.answer("✅ SSH-ключ обновлен.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<pre>{str(e)}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("traffic"))
async def cmd_traffic(message: Message):
    try:
        result = subprocess.run("vnstat", shell=True, capture_output=True, text=True)
        output = result.stdout if result.stdout else result.stderr

        await message.answer(f"📡 <b>Сетевой трафик:</b>\n<pre>{output}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<pre>{str(e)}</pre>", parse_mode=ParseMode.HTML)

async def main():
    logging.info("Бот запущен.")
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        import asyncio

        asyncio.run(main())
    except Exception as e:
        logging.error(f"Ошибка: {e}")