# main.py

import logging
from datetime import datetime, timedelta, timezone
import threading
from json import dumps

import telebot
from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from config import TELEGRAM_TOKEN
from bot_handler import run_bot, get_active_subscribers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
telebot.logger.setLevel(logging.DEBUG)
app = Flask(__name__)

try:
    # MongoDB connection with timeout
    client = MongoClient('mongodb://mdbesp:27017', serverSelectionTimeoutMS=5000)
    # Проверка соединения
    client.server_info()
    db = client['temperature_monitoring']
    collection = db['temperature_data']
except ConnectionFailure as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# Telegram bot initialization
bot = telebot.TeleBot(TELEGRAM_TOKEN)


def start_bot_polling():
    """Запуск бота в отдельном потоке"""
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True  # Поток будет завершен вместе с основной программой
    bot_thread.start()
    logger.info("Bot polling started in separate thread")


def log_outgoing_message(message):
    logger.info(f"TG_OUT: {dumps(message, ensure_ascii=False)}")


def check_alarms(data):
    """
    Check temperature values and send alarms to Telegram
    Args:
        data (dict): Temperature data containing sensor readings
    """
    try:
        for sensor in ['sensor1', 'sensor2']:
            if sensor not in data:
                logger.warning(f"Missing {sensor} data in alarm check")
                continue

            sensor_data = data[sensor]
            if not isinstance(sensor_data, dict) or 'alarm' not in sensor_data:
                logger.warning(f"Invalid {sensor} data format")
                continue

            if sensor_data['alarm']:
                message = (
                    f"🚨 TEMPERATURE ALARM!\n"
                    f"Sensor: {sensor}\n"
                    f"Temperature: {sensor_data.get('temperature', 'N/A')}°C\n"
                    f"Time: {data['server_timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
                )

                # Получаем список активных подписчиков и отправляем им уведомления
                active_subscribers = get_active_subscribers()
                for chat_id in active_subscribers:
                    try:
                        log_outgoing_message(f"Sending to {chat_id}: {message}")
                        bot.send_message(chat_id=chat_id, text=message)
                    except Exception as err:
                        logger.error(f"Failed to send Telegram message to {chat_id}: {err}")

                # Save alarm to database
                try:
                    alarm_data = {
                        'timestamp': data['server_timestamp'],
                        'sensor': sensor,
                        'temperature': sensor_data.get('temperature'),
                        'created_at': datetime.now(timezone.utc)
                    }
                    db['alarms'].insert_one(alarm_data)
                except Exception as err:
                    logger.error(f"Failed to save alarm to database: {err}")

    except Exception as err:
        logger.error(f"Error in alarm checking: {err}")


# Остальные маршруты Flask остаются без изменений...
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/2')
def index2():
    return render_template('index2.html')


@app.route('/3')
def index3():
    return render_template('index3.html')


@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200


@app.route('/api/temperature', methods=['POST'])
def receive_temperature():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data received"}), 400

        # Validate incoming data
        required_fields = ['sensor1', 'sensor2']
        if not all(sensor in data for sensor in required_fields):
            return jsonify({"status": "error", "message": "Missing required sensor data"}), 400

        # Add server timestamp
        data['server_timestamp'] = datetime.now(timezone.utc) + timedelta(hours=4)

        # Save to MongoDB
        try:
            collection.insert_one(data)
        except OperationFailure as err:
            logger.error(f"MongoDB write error: {err}")
            return jsonify({"status": "error", "message": "Database write failed"}), 500

        # Check for alarms
        check_alarms(data)

        return jsonify({"status": "success"}), 200

    except Exception as err:
        logger.error(f"Error processing temperature data: {err}")
        return jsonify({"status": "error", "message": str(err)}), 500


@app.route('/api/temperature/history')
def get_temperature_history():
    try:
        # Get last 24 hours of data
        start_time = datetime.now(timezone.utc) - timedelta(hours=24)

        # Query MongoDB with proper index hint
        cursor = collection.find(
            {"server_timestamp": {"$gte": start_time}},
            {"_id": 0, "server_timestamp": 1, "sensor1.temperature": 1, "sensor2.temperature": 1}
        ).sort("server_timestamp", 1)

        # Format data for chart
        data = list(cursor)
        if not data:
            return jsonify({
                "timestamps": [],
                "sensor1": [],
                "sensor2": []
            })

        timestamps = [entry['server_timestamp'].strftime('%Y-%m-%d %H:%M:%S') for entry in data]
        sensor1_temps = [entry.get('sensor1', {}).get('temperature') for entry in data]
        sensor2_temps = [entry.get('sensor2', {}).get('temperature') for entry in data]

        return jsonify({
            "timestamps": timestamps,
            "sensor1": sensor1_temps,
            "sensor2": sensor2_temps
        })

    except Exception as err:
        logger.error(f"Error retrieving temperature history: {err}")
        return jsonify({"status": "error", "message": str(err)}), 500


if __name__ == '__main__':
    # Создаем индекс для оптимизации запросов по timestamp
    try:
        collection.create_index([("server_timestamp", -1)])
        db['alarms'].create_index([("timestamp", -1)])
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")

    # Запускаем бота в отдельном потоке
    start_bot_polling()

    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=5001, debug=False)