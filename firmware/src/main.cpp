#include <Arduino.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "BuddyUI.hpp"

#define SERVICE_UUID        "0000ffe0-0000-1000-8000-00805f9b34fb"
#define CHARACTERISTIC_UUID "0000ffe1-0000-1000-8000-00805f9b34fb"

BuddyUI ui;
BLEServer* pServer = nullptr;
BLECharacteristic* pCharacteristic = nullptr;
bool deviceConnected = false;

void initBoardHardware() {
    // 1. Initialize I2C Bus for PCA9557, FT6336, QMI8658
    Wire.begin(1, 2, 400000);

    // 2. Initialize PCA9557 IO Expander (address 0x19)
    // Configuration register 0x03: Set IO0..IO2 as OUTPUT (0xF8)
    Wire.beginTransmission(0x19);
    Wire.write(0x03);
    Wire.write(0xF8);
    Wire.endTransmission();

    // Output register 0x01: IO0=0 (LCD enable), IO1=1 (Audio PA enable), IO2=0 (Camera off)
    Wire.beginTransmission(0x19);
    Wire.write(0x01);
    Wire.write(0x02);
    Wire.endTransmission();

    delay(30);

    // 3. I2C device discovery log
    Serial.println("\n--- Scanning I2C Bus ---");
    for (uint8_t a = 1; a < 127; a++) {
        Wire.beginTransmission(a);
        if (Wire.endTransmission() == 0) {
            Serial.printf("Found I2C device: 0x%02X\n", a);
        }
    }
    Serial.println("------------------------\n");
}

void parseIncomingCommand(const String& cmd) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, cmd);
    if (err) {
        String trimmed = cmd;
        trimmed.trim();
        if (trimmed == "idle") ui.setState(STATE_IDLE, "Idle");
        else if (trimmed == "thinking") ui.setState(STATE_THINKING, "Thinking...");
        else if (trimmed == "approval") ui.setState(STATE_APPROVAL, "Permission Needed");
        else if (trimmed == "success") ui.setState(STATE_SUCCESS, "Success!");
        else if (trimmed == "error") ui.setState(STATE_ERROR, "Error!");
        return;
    }

    const char* stateStr = doc["state"] | "idle";
    const char* msgStr = doc["msg"] | "";

    int qPct = doc["q_pct"] | -1;
    const char* qStr = doc["q_str"] | "";
    const char* qGem = doc["q_gem"] | "";
    const char* qCla = doc["q_cla"] | "";
    const char* qArg = doc["q_arg"] | "";
    if (qPct >= 0) {
        ui.setQuota(qPct, qStr, qGem, qCla, qArg);
    }

    const char* wCity = doc["w_city"] | "";
    const char* wTemp = doc["w_temp"] | "";
    const char* wText = doc["w_text"] | "";
    const char* wRange = doc["w_range"] | "";
    const char* wHum = doc["w_hum"] | "";
    int wIcon = doc["w_icon"] | -1;
    if (strlen(wTemp) > 0) {
        ui.setWeather(wCity, wTemp, wText, wRange, wHum, wIcon);
    }

    if (doc["dim_sec"].is<unsigned long>()) {
        ui.setDimTimeout(doc["dim_sec"].as<unsigned long>() * 1000UL);
    }

    if (strcmp(stateStr, "idle") == 0) {
        ui.setState(STATE_IDLE, msgStr);
    } else if (strcmp(stateStr, "thinking") == 0) {
        ui.setState(STATE_THINKING, msgStr);
    } else if (strcmp(stateStr, "approval") == 0) {
        ui.setState(STATE_APPROVAL, msgStr);
    } else if (strcmp(stateStr, "success") == 0) {
        ui.setState(STATE_SUCCESS, msgStr);
    } else if (strcmp(stateStr, "error") == 0) {
        ui.setState(STATE_ERROR, msgStr);
    }
}

class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) override {
        deviceConnected = true;
        ui.setState(STATE_SUCCESS, "BLE Connected!");
    }

    void onDisconnect(BLEServer* pServer) override {
        deviceConnected = false;
        ui.setState(STATE_IDLE, "BLE Waiting...");
        BLEDevice::startAdvertising();
    }
};

class CharCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pChar) override {
        String rxValue = pChar->getValue();
        if (rxValue.length() > 0) {
            parseIncomingCommand(rxValue);
        }
    }
};

void setupBLE() {
    BLEDevice::init("Antigravity-Buddy");
    BLEDevice::setMTU(517);

    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());

    BLEService* pService = pServer->createService(SERVICE_UUID);
    pCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_READ |
        BLECharacteristic::PROPERTY_WRITE |
        BLECharacteristic::PROPERTY_NOTIFY
    );
    pCharacteristic->addDescriptor(new BLE2902());
    pCharacteristic->setCallbacks(new CharCallbacks());
    pService->start();

    BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    BLEDevice::startAdvertising();
}

void notifyAction(const char* action) {
    JsonDocument doc;
    doc["event"] = action;
    String out;
    serializeJson(doc, out);

    // 1. Notify over BLE
    if (deviceConnected && pCharacteristic) {
        pCharacteristic->setValue(out.c_str());
        pCharacteristic->notify();
    }

    // 2. Also output to USB Serial
    Serial.println(out);
}

void setup() {
    Serial.begin(115200);
    delay(200);

    Serial.println("\n==================================");
    Serial.println("  Antigravity Desktop Buddy v1.2  ");
    Serial.println("==================================");

    initBoardHardware();

    ui.init();
    ui.setState(STATE_IDLE, "Antigravity BLE Ready");

    Serial.printf("PSRAM: %s | Free PSRAM: %d | Free Heap: %d\n",
                  psramFound() ? "FOUND" : "NOT FOUND",
                  ESP.getFreePsram(),
                  ESP.getFreeHeap());

    setupBLE();
    Serial.println("[BLE] GATT Server advertising started.");
}

String serialBuffer = "";

void loop() {
    // 1. High-Frequency Touch Screen Polling (Immediate Event Dispatch)
    int touchEvent = ui.checkTouch();
    if (touchEvent == 1) {
        notifyAction("approved");
        ui.setState(STATE_SUCCESS, "Approved!");
    } else if (touchEvent == 2) {
        notifyAction("denied");
        ui.setState(STATE_ERROR, "Denied!");
    }

    // 2. Read USB Serial Commands
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (serialBuffer.length() > 0) {
                parseIncomingCommand(serialBuffer);
                serialBuffer = "";
            }
        } else {
            serialBuffer += c;
        }
    }

    // 3. Smooth Non-Blocking Frame Pacing (~40 FPS)
    static unsigned long lastFrameTime = 0;
    unsigned long now = millis();
    if (now - lastFrameTime >= 24) {
        lastFrameTime = now;
        ui.update();
    } else {
        delay(2); // Short yield keeps touch polling ultra-responsive!
    }
}
