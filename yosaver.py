import os
import logging
import urllib.parse
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pytube import YouTube
import tempfile

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменной окружения (или используем напрямую)
TOKEN = os.getenv("BOT_TOKEN")
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 ГБ

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = """
🎵 YoSaver Bot 🎵

Привет! Я помогу тебе скачать видео с YouTube быстро и удобно!

Отправь мне ссылку на YouTube видео, и я скачаю его для тебя.
"""
    await update.message.reply_text(welcome_text)


def is_valid_youtube_url(url):
    """Проверка ссылки на YouTube"""
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\\?]{11})'
    return bool(re.match(youtube_regex, url))


def get_video_info(url):
    """Получение информации о видео"""
    try:
        yt = YouTube(url)
        return {
            'title': yt.title,
            'author': yt.author,
            'length': yt.length,
            'streams': yt.streams
        }
    except Exception as e:
        logger.error(f"Ошибка при получении информации о видео: {e}")
        return None


def format_duration(seconds):
    """Форматирование длительности видео"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours > 0 else f"{minutes}:{secs:02d}"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    url = update.message.text.strip()

    if not is_valid_youtube_url(url):
        await update.message.reply_text("❌ Это не похоже на ссылку YouTube. Проверь и попробуй снова.")
        return

    await update.message.reply_text("⏳ Загружаю видео... Это может занять пару минут.")

    try:
        video_info = get_video_info(url)
        if not video_info:
            await update.message.reply_text("❌ Не удалось получить информацию о видео.")
            return

        # Ищем лучший поток с видео и аудио
        stream = video_info['streams'].filter(progressive=True).order_by('resolution').desc().first()

        if not stream:
            await update.message.reply_text("❌ Не удалось найти подходящее видео.")
            return

        if stream.filesize > MAX_FILE_SIZE:
            size_mb = stream.filesize / (1024 * 1024)
            await update.message.reply_text(f"❌ Файл слишком большой: {size_mb:.1f} MB (макс. 2 ГБ)")
            return

        # Создаём временный файл
        file_path = f"video_{stream.itag}.mp4"

        # Скачиваем
        stream.download(filename=file_path)

        # Отправляем
        with open(file_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=update.message.chat_id,
                video=video_file,
                caption=f"🎬 {video_info['title']}\n📥 Готово! Скачано через @yosaverbot",
                supports_streaming=True
            )

        # Удаляем файл
        os.remove(file_path)

    except Exception as e:
        logger.error(f"Ошибка при загрузке видео: {e}")
        await update.message.reply_text("❌ Произошла ошибка при загрузке видео. Попробуй позже.")


def main():
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ YoSaver Bot запущен и готов к работе...")
    application.run_polling()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_health_check():
    server = HTTPServer(('0.0.0.0', 8080), HealthCheckHandler)
    print("Health check server running on port 8080")
    server.serve_forever()

# Запуск сервера проверки здоровья
health_check_thread = threading.Thread(target=run_health_check)
health_check_thread.daemon = True
health_check_thread.start()


if __name__ == '__main__':
    main()