import os
import psutil
import logging
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, File
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import time

load_dotenv()

TOKEN = os.getenv("TOKEN")
USER_ID = os.getenv("USER_ID")

if not TOKEN or not USER_ID:
    raise ValueError("Токен или ID пользователя не найдены в .env файле.")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)

# Глобальная переменная для хранения текущей директории
current_directory = os.getcwd()

# Создаем папку Downloads, если её нет
downloads_dir = os.path.join(current_directory, "Downloads")
os.makedirs(downloads_dir, exist_ok=True)

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
    global current_directory

    try:
        # Если команда начинается с "cd", обновляем текущую директорию
        if command.startswith("cd "):
            new_dir = command.split(" ", 1)[1].strip()
            try:
                os.chdir(new_dir)
                current_directory = os.getcwd()
                return f"Текущая директория изменена на: {current_directory}"
            except Exception as e:
                return f"Ошибка при смене директории: {e}"
        else:
            # Выполняем команду в текущей директории
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=current_directory
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
        await bot.send_message(chat_id=USER_ID, text=warning, parse_mode=ParseMode.HTML)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /start")
    await message.answer("Привет! Я бот для мониторинга сервера. Используй /help для списка команд.")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /help")
    help_text = (
        f"📋 <b>Список команд:</b>\n"
        f"/start - Начать работу с ботом\n"
        f"/help - Показать это сообщение\n"
        f"/status - Показать текущее состояние сервера\n"
        f"/c &lt;команда&gt; - Выполнить команду на сервере\n"
        f"/top - Показать топ процессов\n"
        f"/netstat - Показать активные сетевые соединения\n"
        f"/traffic - Показать трафик\n"
        f"/ssh &lt;add|remove&gt; &lt;публичный_ключ&gt; - Управление SSH-ключами\n"
        f"/file - Загрузить файл на сервер\n"
        f"/reboot - Перезагрузить сервер\n"
        f"/logs - Показать логи сервера\n"
        f"/sysinfo - Показать информацию о системе"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(Command("status"))
async def cmd_status(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /status")
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
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return

    command = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if not command:
        await message.answer("❌ Укажите команду для выполнения.")
        return

    logging.info(f"Пользователь {message.from_user.id} выполнил команду: {command}")
    result = execute_command(command)
    await message.answer(f"✅ Результат выполнения команды:\n<pre>{result}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("top"))
async def cmd_top(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /top")
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
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /netstat")
    try:
        result = subprocess.run("netstat -tuln", shell=True, capture_output=True, text=True)
        output = result.stdout or result.stderr

        await message.answer(f"📡 <b>Активные соединения:</b>\n<pre>{output}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<pre>{str(e)}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("ssh"))
async def cmd_ssh(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Используйте: /ssh <add|remove> <публичный_ключ>", parse_mode=ParseMode.HTML)
        return

    action, key = args[1], args[2]
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /ssh {action}")
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
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /traffic")
    try:
        result = subprocess.run("vnstat", shell=True, capture_output=True, text=True)
        output = result.stdout if result.stdout else result.stderr

        await message.answer(f"📡 <b>Сетевой трафик:</b>\n<pre>{output}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<pre>{str(e)}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("file"))
async def cmd_file(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return

    if not message.document and not message.photo:
        await message.answer("❌ Файлы не прикреплены.")
        return

    # Обработка нескольких файлов
    files = []
    if message.document:
        files.extend(message.document)  # Добавляем все документы
    if message.photo:
        files.append(message.photo[-1])  # Добавляем фото (самое высокое качество)

    success_files = []
    failed_files = []

    for file in files:
        # Генерируем уникальное имя файла
        timestamp = int(time.time())
        if hasattr(file, 'file_name'):
            file_name = f"{timestamp}_{file.file_name}"  # Добавляем timestamp к имени
        else:
            file_name = f"photo_{timestamp}_{file.file_id}.jpg"  # Для фото

        file_path = os.path.join(downloads_dir, file_name)

        try:
            await bot.download(file, destination=file_path)
            success_files.append(file_name)
        except Exception as e:
            failed_files.append((file_name, str(e)))

    # Формируем ответ
    response = []
    if success_files:
        response.append(f"✅ Успешно загружены файлы:\n<pre>{', '.join(success_files)}</pre>")
    if failed_files:
        failed_messages = [f"{name}: {error}" for name, error in failed_files]
        response.append(f"❌ Ошибка при загрузке файлов:\n<pre>{', '.join(failed_messages)}</pre>")

    await message.answer("\n".join(response), parse_mode=ParseMode.HTML)

@dp.message(Command("reboot"))
async def cmd_reboot(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /reboot")
    try:
        await message.answer("🔄 Сервер перезагружается...")
        subprocess.run("sudo reboot", shell=True, check=True)
    except Exception as e:
        await message.answer(f"❌ Ошибка при перезагрузке сервера:\n<pre>{str(e)}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("logs"))
async def cmd_logs(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /logs")
    try:
        with open("bot.log", "r") as log_file:
            logs = log_file.readlines()[-10:]  # Последние 10 строк логов
            logs = "".join(logs)
            await message.answer(f"📜 <b>Последние логи:</b>\n<pre>{logs}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"❌ Ошибка при чтении логов:\n<pre>{str(e)}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("sysinfo"))
async def cmd_sysinfo(message: Message):
    if str(message.from_user.id) != USER_ID:
        await message.answer("❌ У вас нет прав для использования этого бота.")
        return
    logging.info(f"Пользователь {message.from_user.id} выполнил команду /sysinfo")
    try:
        hostname = os.uname().nodename
        os_info = os.uname().sysname + " " + os.uname().release
        cpu_count = os.cpu_count()

        sysinfo_message = (
            "📊 <b>Информация о системе:</b>\n"
            f"• <b>Имя хоста:</b> {hostname}\n"
            f"• <b>ОС:</b> {os_info}\n"
            f"• <b>Количество ядер CPU:</b> {cpu_count}\n"
        )

        await message.answer(sysinfo_message, parse_mode=ParseMode.HTML)
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
