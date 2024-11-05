# bot_handler.py

import logging
from datetime import datetime, timezone
from pymongo import MongoClient
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from config import TELEGRAM_TOKEN

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Подключение к MongoDB
try:
    client = MongoClient('mongodb://mdbesp:27017', serverSelectionTimeoutMS=5000)
    db = client['temperature_monitoring']
    subscribers_collection = db['telegram_subscribers']
except Exception as err:
    logger.error(f"Failed to connect to MongoDB: {err}")
    raise

def create_keyboard():
    """Создание клавиатуры с кнопками"""
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    start_button = KeyboardButton('🟢 Start')
    stop_button = KeyboardButton('🔴 Stop')
    keyboard.add(start_button, stop_button)
    return keyboard

def init_subscriber_collection():
    """Инициализация коллекции подписчиков если она не существует"""
    try:
        if 'telegram_subscribers' not in db.list_collection_names():
            subscribers_collection.create_index([("chat_id", 1)], unique=True)
    except Exception as er:
        logger.error(f"Failed to initialize subscriber collection: {er}")

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработка команды /start"""
    try:
        chat_id = message.chat.id
        user_name = message.from_user.username or message.from_user.first_name

        # Проверяем, не подписан ли уже пользователь
        existing_subscriber = subscribers_collection.find_one({"chat_id": chat_id})

        if existing_subscriber and existing_subscriber.get('is_active', False):
            bot.reply_to(
                message,
                "Вы уже подписаны на уведомления о температуре! 🌡",
                reply_markup=create_keyboard()
            )
            return

        # Создаем или обновляем запись подписчика
        subscriber_data = {
            "chat_id": chat_id,
            "username": user_name,
            "is_active": True,
            "subscribed_at": datetime.now(timezone.utc),
            "last_updated": datetime.now(timezone.utc)
        }

        subscribers_collection.update_one(
            {"chat_id": chat_id},
            {"$set": subscriber_data},
            upsert=True
        )

        welcome_message = (
            f"Привет, {user_name}! 👋\n"
            "Вы успешно подписались на уведомления о температуре.\n"
            "Вы будете получать оповещения при критических изменениях температуры.\n"
            "Для отключения уведомлений нажмите кнопку Stop или используйте команду /stop"
        )
        bot.reply_to(message, welcome_message, reply_markup=create_keyboard())
        logger.info(f"New subscriber added: {chat_id} ({user_name})")

    except Exception as er:
        error_message = "Произошла ошибка при подписке на уведомления. Пожалуйста, попробуйте позже."
        bot.reply_to(message, error_message, reply_markup=create_keyboard())
        logger.error(f"Error in handle_start: {er}")

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    """Обработка команды /stop"""
    try:
        chat_id = message.chat.id
        user_name = message.from_user.username or message.from_user.first_name

        # Проверяем, подписан ли пользователь
        subscriber = subscribers_collection.find_one({"chat_id": chat_id})

        if not subscriber or not subscriber.get('is_active', False):
            bot.reply_to(
                message,
                "Вы не были подписаны на уведомления! 🤔",
                reply_markup=create_keyboard()
            )
            return

        # Обновляем статус подписки
        subscribers_collection.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "is_active": False,
                    "last_updated": datetime.now(timezone.utc)
                }
            }
        )

        goodbye_message = (
            f"До свидания, {user_name}! 👋\n"
            "Вы успешно отписались от уведомлений о температуре.\n"
            "Для повторной подписки нажмите кнопку Start или используйте команду /start"
        )
        bot.reply_to(message, goodbye_message, reply_markup=create_keyboard())
        logger.info(f"Subscriber deactivated: {chat_id} ({user_name})")

    except Exception as er:
        error_message = "Произошла ошибка при отписке от уведомлений. Пожалуйста, попробуйте позже."
        bot.reply_to(message, error_message, reply_markup=create_keyboard())
        logger.error(f"Error in handle_stop: {er}")

@bot.message_handler(func=lambda message: message.text in ['🟢 Start', '🔴 Stop'])
def handle_button_click(message):
    """Обработка нажатий на кнопки"""
    if message.text == '🟢 Start':
        handle_start(message)
    elif message.text == '🔴 Stop':
        handle_stop(message)

def get_active_subscribers():
    """Получение списка активных подписчиков"""
    try:
        active_subscribers = subscribers_collection.find({"is_active": True})
        return [subscriber["chat_id"] for subscriber in active_subscribers]
    except Exception as er:
        logger.error(f"Error getting active subscribers: {er}")
        return []

def run_bot():
    """Запуск бота"""
    try:
        init_subscriber_collection()
        logger.info("Telegram bot started...")
        bot.polling(none_stop=True)
    except Exception as er:
        logger.error(f"Error running bot: {er}")