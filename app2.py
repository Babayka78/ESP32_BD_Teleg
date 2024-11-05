import requests
import time
import random
from datetime import datetime, timezone, timedelta


def generate_temperature():
    """
    Generate random temperature between 18 and 28°C
    Add some noise every now and then to simulate temperature spikes
    """
    base_temp = random.uniform(18, 28)
    # 10% chance of temperature spike
    if random.random() < 0.1:
        base_temp += random.uniform(5, 10)
    return round(base_temp, 2)


def create_sensor_data(sensor_id):
    temp = generate_temperature()
    return {
        "temperature": temp,
        "alarm": temp > 30  # Alarm threshold at 30°C
    }


def main():
    while True:
        # Generate data for both sensors
        tz_offset = timezone(timedelta(hours=4))
        data = {
            "timestamp": datetime.now(tz_offset).isoformat(),
            "sensor1": create_sensor_data(1),
            "sensor2": create_sensor_data(2)
        }

        # Send to API
        try:
            response = requests.post(
                'http://127.0.0.1:5001/api/temperature',
                json=data
            )
            print(f"Data sent: {data}")
            print(f"Response: {response.status_code}")
        except Exception as e:
            print(f"Error sending data: {e}")

        # Wait 30 seconds before next reading
        time.sleep(5)


if __name__ == "__main__":
    main()