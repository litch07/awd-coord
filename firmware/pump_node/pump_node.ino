/*
  AWD-COORD — PUMP/GATEWAY NODE PRODUCTION FIRMWARE
  ===================================================
  Base: verified pump/INA219/OLED/rain sketch.
  GPIO25 switch = failure-simulation button (confirmed decision), NOT a
  manual pump on/off. Pump is driven only by PumpCommandPacket.

  Requires: mac_config.h, awd_protocol.h (same versions as Proxy/Field Node),
  Wire.h, Adafruit_GFX, Adafruit_SSD1306, Adafruit_INA219.
*/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_INA219.h>
#include <esp_now.h>
#include <WiFi.h>
#include "../common/mac_config.h"
#include "../common/awd_protocol.h"

// ---------- PIN MAP (verified — do not change) ----------
#define SDA_PIN     21
#define SCL_PIN     22
#define MOTOR_IN3   26
#define MOTOR_IN4   27
#define RAIN_PIN    33
#define SWITCH_PIN  25   // Failure-simulation button, LOW = engaged

#define STATUS_SEND_INTERVAL_MS 1000
#define HEARTBEAT_INTERVAL_MS   2000
#define PUMP_NODE_ID 0

Adafruit_SSD1306 display(128, 64, &Wire, -1);
Adafruit_INA219 ina219;

bool oledFound = true;
bool inaFound = true;

bool pumpOn = false;
bool faultSimulated = false;

unsigned long lastStatusSend = 0;
unsigned long lastHeartbeat = 0;

void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  if (status != ESP_NOW_SEND_SUCCESS) {
    Serial.println("[ESP-NOW] Send FAILED");
  } else {
    Serial.println("[ESP-NOW] Send SUCCESS");
  }
}

void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len < 1) return;
  uint8_t type = data[0];

  if (type == PKT_PUMP_COMMAND && len == sizeof(PumpCommandPacket)) {
    PumpCommandPacket cmd;
    memcpy(&cmd, data, sizeof(cmd));

    if (faultSimulated) {
      Serial.println("[COMMAND] Ignored — fault simulation active");
      return;
    }

    pumpOn = cmd.pumpOn;
    Serial.print("[COMMAND] Pump ");
    Serial.println(pumpOn ? "ON" : "OFF");
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("Starting system...");

  pinMode(MOTOR_IN3, OUTPUT);
  pinMode(MOTOR_IN4, OUTPUT);
  digitalWrite(MOTOR_IN3, LOW);
  digitalWrite(MOTOR_IN4, LOW);

  pinMode(SWITCH_PIN, INPUT_PULLUP);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  Wire.setTimeOut(50);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("ERROR: OLED not found!");
    oledFound = false;
  }

  if (!ina219.begin()) {
    Serial.println("ERROR: INA219 not found!");
    inaFound = false;
  }

  if (oledFound) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(5, 20);
    display.println("BOOT OK!");
    display.display();
    delay(1000);
  }

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  if (esp_now_init() != ESP_OK) {
    Serial.println("[ESP-NOW] Init FAILED — halting.");
    while (true) delay(1000);
  }

  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataRecv);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, PROXY_MAC, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("[ESP-NOW] Failed to add Proxy as peer.");
  }
  
  // Add Shadow Coordinator as a peer to guarantee failover command receipt
  memcpy(peerInfo.peer_addr, SHADOW_MAC, 6);
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("[ESP-NOW] Failed to add Shadow as peer.");
  }

  Serial.println("[ESP-NOW] Ready. Waiting for pump commands from Proxy.\n");
}

void loop() {
  unsigned long now = millis();

  bool switchState = digitalRead(SWITCH_PIN);
  bool newFaultState = (switchState == LOW);
  if (newFaultState != faultSimulated) {
    faultSimulated = newFaultState;
    if (faultSimulated) {
      Serial.println(">>> FAULT SIMULATION ENGAGED — pump forced OFF <<<");
      pumpOn = false;
    } else {
      Serial.println(">>> Fault simulation released — awaiting next command <<<");
    }
  }

  if (pumpOn && !faultSimulated) {
    digitalWrite(MOTOR_IN3, HIGH);
    digitalWrite(MOTOR_IN4, LOW);
  } else {
    digitalWrite(MOTOR_IN3, LOW);
    digitalWrite(MOTOR_IN4, LOW);
  }

  int rainValue = analogRead(RAIN_PIN);
  float voltage = 0.0, current = 0.0, power = 0.0;
  if (inaFound) {
    voltage = ina219.getBusVoltage_V();
    current = ina219.getCurrent_mA();
    power = ina219.getPower_mW();
  }

  if (oledFound) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);

    display.setCursor(0, 0);
    display.print(pumpOn && !faultSimulated ? "PUMP: ON" : "PUMP: OFF");

    display.setCursor(64, 0);
    display.print("RAIN:");
    display.print(rainValue);

    display.drawLine(0, 10, 128, 10, SSD1306_WHITE);

    if (faultSimulated) {
      display.setCursor(0, 16);
      display.println("** FAULT SIM **");
    } else if (inaFound) {
      display.setCursor(0, 16);
      display.print("Volt: "); display.print(voltage, 2); display.println(" V");
      display.setCursor(0, 31);
      display.print("Curr: "); display.print(current, 1); display.println(" mA");
      display.setCursor(0, 46);
      display.print("Pwr:  "); display.print(power, 1); display.println(" mW");
    } else {
      display.setCursor(0, 31);
      display.println("INA219 MISSING");
    }

    display.display();
  }

  if (now - lastStatusSend >= STATUS_SEND_INTERVAL_MS) {
    lastStatusSend = now;

    PumpStatusPacket pkt;
    pkt.type = PKT_PUMP_STATUS;
    pkt.pumpOn = pumpOn && !faultSimulated;
    pkt.rainRaw = rainValue;
    pkt.busVoltage = voltage;
    pkt.currentMa = current;
    pkt.powerMw = power;
    pkt.faultSimulated = faultSimulated;
    pkt.uptimeMs = now;

    esp_now_send(PROXY_MAC, (uint8_t *)&pkt, sizeof(pkt));
  }

  if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeat = now;
    HeartbeatPacket hb;
    hb.type = PKT_HEARTBEAT;
    hb.nodeId = PUMP_NODE_ID;
    esp_now_send(PROXY_MAC, (uint8_t *)&hb, sizeof(hb));
  }

  delay(200);
}
