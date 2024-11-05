// mongo-init.js
db = db.getSiblingDB('temperature_monitoring');

// Создание коллекций
db.createCollection('temperature_data');
db.createCollection('alarms');

// Создание индексов
db.temperature_data.createIndex({ "server_timestamp": -1 });
db.alarms.createIndex({ "timestamp": -1 });

// Если нужны начальные данные
// db.temperature_data.insertMany([...]);