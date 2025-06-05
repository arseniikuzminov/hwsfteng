import time
import psutil
from datetime import datetime
import threading
import telebot
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')  # ID чата для уведомлений

# Создаем объект бота
bot = telebot.TeleBot('BOT_TOKEN')

# Список игровых приложений для отслеживания
game_process_names = ['game.exe', 'steam.exe', 'minecraft.exe']

# Словари для хранения данных с блокировкой потоков
data_lock = threading.Lock()
start_times = {}
total_play_time = {}

def send_notification(message):
    """Отправка уведомления в Telegram"""
    try:
        if CHAT_ID:
            bot.send_message(CHAT_ID, message)
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")

def format_time(seconds):
    """Форматирование времени в удобочитаемый вид"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def check_games():
    """Проверка запущенных игр"""
    current_games = set()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pname = proc.info['name']
            if pname in game_process_names:
                current_games.add(pname)
                with data_lock:
                    if pname not in start_times:
                        start_times[pname] = datetime.now()
                        message = f"🎮 Игра {pname} запущена в {start_times[pname].strftime('%H:%M:%S')}"
                        print(message)
                        send_notification(message)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    with data_lock:
        stopped_games = set(start_times.keys()) - current_games
        for pname in stopped_games:
            end_time = datetime.now()
            play_time = (end_time - start_times[pname]).total_seconds()
            total_play_time[pname] = total_play_time.get(pname, 0) + play_time
            formatted_time = format_time(play_time)
            message = f"⏹️ Игра {pname} закрыта в {end_time.strftime('%H:%M:%S')}\nВремя сессии: {formatted_time}"
            print(message)
            send_notification(message)
            del start_times[pname]

def get_play_times_text():
    """Получение текста статистики игрового времени"""
    with data_lock:
        if not total_play_time and not start_times:
            return "📊 Статистика пуста. Пока нет данных об играх."
        
        text = "📊 **Статистика игрового времени:**\n\n"
        
        # Завершенные сессии
        if total_play_time:
            text += "🏁 **Завершенные сессии:**\n"
            for game, seconds in total_play_time.items():
                formatted_time = format_time(seconds)
                text += f"  • {game}: {formatted_time}\n"
        
        # Текущие активные игры
        if start_times:
            text += "\n🟢 **Активные сейчас:**\n"
            current_time = datetime.now()
            for game, start_time in start_times.items():
                current_session = (current_time - start_time).total_seconds()
                formatted_time = format_time(current_session)
                text += f"  • {game}: {formatted_time} (активна)\n"
        
        return text

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    welcome_text = """
🎮 **Добро пожаловать в Мониторинг Игр!**

Этот бот отслеживает время, проведенное в играх, и предоставляет детальную статистику.

📋 **Доступные команды:**
/start - Показать это сообщение
/status - Текущие активные игры
/stats - Полная статистика времени
/help - Справка по командам


🔔 Вы будете получать уведомления о запуске и закрытии игр автоматически!
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def send_status(message):
    """Обработчик команды /status"""
    with data_lock:
        if not start_times:
            bot.reply_to(message, "🔸 Сейчас нет активных игр")
            return
        
        text = "🟢 **Активные игры:**\n\n"
        current_time = datetime.now()
        for game, start_time in start_times.items():
            session_time = (current_time - start_time).total_seconds()
            formatted_time = format_time(session_time)
            start_time_str = start_time.strftime('%H:%M:%S')
            text += f"🎮 {game}\n"
            text += f"  ⏰ Запущена: {start_time_str}\n"
            text += f"  ⏱️ Время сессии: {formatted_time}\n\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Обработчик команды /stats"""
    stats_text = get_play_times_text()
    bot.reply_to(message, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def send_help(message):
    """Обработчик команды /help"""
    help_text = """
📚 **Справка по командам:**

🔹 `/start` - Приветственное сообщение и основная информация
🔹 `/status` - Показать текущие активные игры и время текущих сессий
🔹 `/stats` - Полная статистика времени игры (завершенные + активные)
🔹 `/help` - Эта справка

🔔 **Автоматические уведомления:**
• Уведомление при запуске игры
• Уведомление при закрытии игры с временем сессии

🛠 **Отслеживаемые приложения:**
""" + "\n".join([f"• {game}" for game in game_process_names])
    
    bot.reply_to(message, help_text, parse_mode='Markdown')

def monitor_games():
    """Основной цикл мониторинга игр"""
    while True:
        try:
            check_games()
            time.sleep(5)
        except Exception as e:
            print(f"Ошибка в мониторинге: {e}")
            time.sleep(10)

def bot_polling():
    """Запуск бота с обработкой ошибок"""
    print("Запуск Telegram бота...")
    while True:
        try:
            bot.polling(none_stop=True, interval=3, timeout=30)
        except Exception as ex:
            print(f"Ошибка бота, перезапуск через 30 сек: {ex}")
            time.sleep(30)

if __name__ == "__main__":
    print("Мониторинг игр с Telegram ботом запущен...")
    
    # Запуск мониторинга в отдельном потоке
    monitor_thread = threading.Thread(target=monitor_games, daemon=True)
    monitor_thread.start()
    
    # Запуск бота в отдельном потоке
    bot_thread = threading.Thread(target=bot_polling, daemon=True)
    bot_thread.start()
    
    print("Система запущена. Введите 'exit' для выхода.")
    while True:
        cmd = input().strip().lower()
        if cmd == 'exit':
            print("Завершение работы...")
            break
