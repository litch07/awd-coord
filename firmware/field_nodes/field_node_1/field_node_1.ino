
#include <ESP32Servo.h>
#include <esp_now.h>
#include <WiFi.h>
#include "../../common/mac_config.h"
#include "../../common/awd_protocol.h"

#define NODE_ID 1

#define PIN_DEPTH_POT     32
#define PIN_STAGE_POT     33
#define PIN_SOIL_MOISTURE 34
#define PIN_WATER_PROBE   35
#define PIN_SERVO         25
#define PIN_LED_GREEN     26
#define PIN_LED_RED       27
#define PIN_OVERRIDE_SW   14

#define STATUS_SEND_INTERVAL_MS    1000
#define HEARTBEAT_INTERVAL_MS      2000
#define VALVE_OPEN_ANGLE           90
#define VALVE_CLOSED_ANGLE         0

Servo valveServo;
bool lastOverrideState = HIGH;
bool isOverrideActive = false;
bool valveOpen = false;
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

  if (type == PKT_VALVE_COMMAND && len == sizeof(ValveCommandPacket)) {
    ValveCommandPacket cmd;
    memcpy(&cmd, data, sizeof(cmd));
    if (cmd.nodeId != NODE_ID) return;

    if (isOverrideActive) {
      Serial.println("[COMMAND] Ignored due to MANUAL OVERRIDE");
      return;
    }

    valveOpen = cmd.openValve;
    valveServo.write(valveOpen ? VALVE_OPEN_ANGLE : VALVE_CLOSED_ANGLE);

    Serial.print("[COMMAND] Valve ");
    Serial.println(valveOpen ? "OPEN" : "CLOSED");
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.print("\n=== AWD-COORD FIELD NODE PRODUCTION — NODE_ID ");
  Serial.print(NODE_ID);
  Serial.println(" ===");

  pinMode(PIN_OVERRIDE_SW, INPUT_PULLUP);
  pinMode(PIN_WATER_PROBE, INPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);

  ESP32PWM::allocateTimer(0);
  valveServo.setPeriodHertz(50);
  valveServo.attach(PIN_SERVO, 500, 2400);
  valveServo.write(VALVE_CLOSED_ANGLE);
  valveOpen = false;

  digitalWrite(PIN_LED_GREEN, HIGH);
  digitalWrite(PIN_LED_RED, LOW);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("[ESP-NOW] Init FAILED — halting.");
    digitalWrite(PIN_LED_GREEN, LOW);
    digitalWrite(PIN_LED_RED, HIGH);
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

  Serial.println("[ESP-NOW] Ready. Sending status + heartbeat to Proxy.\n");
}

void loop() {
  unsigned long now = millis();

  bool currentButtonState = digitalRead(PIN_OVERRIDE_SW);
  if (currentButtonState == LOW && lastOverrideState == HIGH) {
    isOverrideActive = !isOverrideActive;
    if (isOverrideActive) {
      // Farmer took control! Invert the current valve state.
      valveOpen = !valveOpen;
      valveServo.write(valveOpen ? VALVE_OPEN_ANGLE : VALVE_CLOSED_ANGLE);
      
      Serial.print(">>> MANUAL OVERRIDE ENGAGED! Valve Forced ");
      Serial.print(valveOpen ? "OPEN" : "CLOSED");
      Serial.println(" <<<");
      
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_RED, HIGH);
    } else {
      // Farmer released control. Leave valve as-is, let Python decide what to do next.
      Serial.println(">>> Manual override released (Waiting for Auto) <<<");
      digitalWrite(PIN_LED_GREEN, HIGH);
      digitalWrite(PIN_LED_RED, LOW);
    }
    delay(250); // Simple debounce
  }
  lastOverrideState = currentButtonState;

  if (now - lastStatusSend >= STATUS_SEND_INTERVAL_MS) {
    lastStatusSend = now;

    FieldStatusPacket pkt;
    pkt.type = PKT_FIELD_STATUS;
    pkt.nodeId = NODE_ID;
    pkt.depthRaw = analogRead(PIN_DEPTH_POT);
    pkt.cropStageRaw = analogRead(PIN_STAGE_POT);
    pkt.soilMoisture = analogRead(PIN_SOIL_MOISTURE);
    pkt.waterPresent = !digitalRead(PIN_WATER_PROBE);
    pkt.overrideActive = isOverrideActive;
    pkt.valveOpen = valveOpen;
    pkt.uptimeMs = now;

    esp_now_send(PROXY_MAC, (uint8_t *)&pkt, sizeof(pkt));
  }

  if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeat = now;

    HeartbeatPacket hb;
    hb.type = PKT_HEARTBEAT;
    hb.nodeId = NODE_ID;
    esp_now_send(PROXY_MAC, (uint8_t *)&hb, sizeof(hb));
  }
}
