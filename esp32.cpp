#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Server details
const char* serverUrl = "http://your-server.com/api/temperature";

// Temperature sensor pins
const int TEMP_SENSOR_1_PIN = 4;  // GPIO4
const int TEMP_SENSOR_2_PIN = 5;  // GPIO5

// Temperature thresholds (in Celsius)
const float TEMP_HIGH_THRESHOLD = 30.0;
const float TEMP_LOW_THRESHOLD = 10.0;

// Timing constants
const unsigned long MEASUREMENT_INTERVAL = 300000;  // 5 minutes in milliseconds
unsigned long lastMeasurementTime = 0;

// Initialize temperature sensors
OneWire oneWire1(TEMP_SENSOR_1_PIN);
OneWire oneWire2(TEMP_SENSOR_2_PIN);
DallasTemperature sensor1(&oneWire1);
DallasTemperature sensor2(&oneWire2);

void setup() {
    Serial.begin(115200);

    // Initialize sensors
    sensor1.begin();
    sensor2.begin();

    // Connect to WiFi
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nConnected to WiFi");
}

void loop() {
    unsigned long currentTime = millis();

    // Check if it's time to measure and send data
    if (currentTime - lastMeasurementTime >= MEASUREMENT_INTERVAL) {
        measureAndSendData();
        lastMeasurementTime = currentTime;
    }
}

void measureAndSendData() {
    // Request temperatures from sensors
    sensor1.requestTemperatures();
    sensor2.requestTemperatures();

    float temp1 = sensor1.getTempCByIndex(0);
    float temp2 = sensor2.getTempCByIndex(0);

    // Check temperature thresholds
    bool alarm1 = checkTemperatureAlarm(temp1, 1);
    bool alarm2 = checkTemperatureAlarm(temp2, 2);

    // Create JSON payload
    StaticJsonDocument<200> doc;
    doc["timestamp"] = millis();
    doc["sensor1"] = {
        "temperature": temp1,
        "alarm": alarm1
    };
    doc["sensor2"] = {
        "temperature": temp2,
        "alarm": alarm2
    };

    // Send data to server
    sendDataToServer(doc);
}

bool checkTemperatureAlarm(float temperature, int sensorNumber) {
    if (temperature > TEMP_HIGH_THRESHOLD || temperature < TEMP_LOW_THRESHOLD) {
        Serial.printf("ALARM: Sensor %d temperature (%.2f°C) is outside safe range!\n",
                     sensorNumber, temperature);
        return true;
    }
    return false;
}

void sendDataToServer(JsonDocument& doc) {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");

        String jsonString;
        serializeJson(doc, jsonString);

        int httpResponseCode = http.POST(jsonString);

        if (httpResponseCode > 0) {
            Serial.printf("HTTP Response code: %d\n", httpResponseCode);
        } else {
            Serial.printf("Error sending POST: %d\n", httpResponseCode);
            // В случае ошибки можно сохранить данные локально или предпринять другие действия
        }

        http.end();
    } else {
        Serial.println("WiFi Disconnected. Attempting to reconnect...");
        WiFi.begin(ssid, password);
    }
}
