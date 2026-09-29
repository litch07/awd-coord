/*
  AWD-COORD Coordinator Proxy: ESP-NOW <-> USB serial (JSON lines) bridge.
  No scheduling logic. Requires mac_config.h, awd_protocol.h, ArduinoJson.

  Changes from the earlier draft:
  - field_status JSON now includes "valveOpen".
  - Shadow peer/sync is skipped while SHADOW_MAC is still all zeros.
*/

#include <esp_now.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include "../common/mac_config.h"
#include "../common/awd_protocol.h"

#define HEARTBEAT_TIMEOUT_MS    6000
#define SHADOW_SYNC_INTERVAL_MS 1000

unsigned long lastFieldHeartbeat[4] = {0, 0, 0, 0};
unsigned long lastPumpHeartbeat = 0;
bool lastPumpOn = false;
uint8_t lastActivePlot = 0;
unsigned long lastShadowSync = 0;
bool shadowConfigured = false;

bool macIsSet(const uint8_t *m) {
  for (int i = 0; i < 6; i++) if (m[i] != 0) return true;
  return false;
}

uint8_t* fieldMacById(uint8_t nodeId) {
  switch (nodeId) {
    case 1: return FIELD1_MAC;
    case 2: return FIELD2_MAC;
    case 3: return FIELD3_MAC;
    case 4: return FIELD4_MAC;
    default: return nullptr;
  }
}

void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  if (status != ESP_NOW_SEND_SUCCESS) {
    Serial.println("{\"t\":\"error\",\"msg\":\"espnow_send_failed\"}");
  }
}

void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len < 1) return;
  uint8_t type = data[0];
  unsigned long now = millis();

  if (type == PKT_FIELD_STATUS && len == sizeof(FieldStatusPacket)) {
    FieldStatusPacket pkt;
    memcpy(&pkt, data, sizeof(pkt));
    if (pkt.nodeId >= 1 && pkt.nodeId <= 4) lastFieldHeartbeat[pkt.nodeId - 1] = now;

    StaticJsonDocument<256> doc;
    doc["t"] = "field_status";
    doc["node"] = pkt.nodeId;
    doc["depth"] = pkt.depthRaw;
    doc["stage"] = pkt.cropStageRaw;
    doc["soil"] = pkt.soilMoisture;
    doc["water"] = pkt.waterPresent;
    doc["override"] = pkt.overrideActive;
    doc["valveOpen"] = pkt.valveOpen;
    doc["uptime"] = pkt.uptimeMs;
    serializeJson(doc, Serial);
    Serial.println();
  }
  else if (type == PKT_PUMP_STATUS && len == sizeof(PumpStatusPacket)) {
    PumpStatusPacket pkt;
    memcpy(&pkt, data, sizeof(pkt));
    lastPumpHeartbeat = now;
    lastPumpOn = pkt.pumpOn;

    StaticJsonDocument<256> doc;
    doc["t"] = "pump_status";
    doc["pumpOn"] = pkt.pumpOn;
    doc["rain"] = pkt.rainRaw;
    doc["voltage"] = pkt.busVoltage;
    doc["current"] = pkt.currentMa;
    doc["power"] = pkt.powerMw;
    doc["fault"] = pkt.faultSimulated;
    doc["uptime"] = pkt.uptimeMs;
    serializeJson(doc, Serial);
    Serial.println();
  }
  else if (type == PKT_HEARTBEAT && len == sizeof(HeartbeatPacket)) {
    HeartbeatPacket pkt;
    memcpy(&pkt, data, sizeof(pkt));
    if (pkt.nodeId == 0) lastPumpHeartbeat = now;
    else if (pkt.nodeId >= 1 && pkt.nodeId <= 4) lastFieldHeartbeat[pkt.nodeId - 1] = now;

    StaticJsonDocument<128> doc;
    doc["t"] = "heartbeat";
    doc["node"] = pkt.nodeId;
    serializeJson(doc, Serial);
    Serial.println();
  }
}

void handleSerialLine(const String &line) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) {
    Serial.println("{\"t\":\"error\",\"msg\":\"bad_json\"}");
    return;
  }
  const char* cmdType = doc["t"];
  if (cmdType == nullptr) return;

  if (strcmp(cmdType, "valve") == 0) {
    uint8_t nodeId = doc["node"];
    bool openValve = doc["open"];
    uint8_t* mac = fieldMacById(nodeId);
    if (mac == nullptr) {
      Serial.println("{\"t\":\"error\",\"msg\":\"unknown_field_node\"}");
      return;
    }
    ValveCommandPacket pkt;
    pkt.type = PKT_VALVE_COMMAND;
    pkt.nodeId = nodeId;
    pkt.openValve = openValve;
    esp_now_send(mac, (uint8_t *)&pkt, sizeof(pkt));
    lastActivePlot = openValve ? nodeId : (lastActivePlot == nodeId ? 0 : lastActivePlot);
  }
  else if (strcmp(cmdType, "pump") == 0) {
    bool pumpOn = doc["on"];
    PumpCommandPacket pkt;
    pkt.type = PKT_PUMP_COMMAND;
    pkt.pumpOn = pumpOn;
    esp_now_send(PUMP_MAC, (uint8_t *)&pkt, sizeof(pkt));
  }
  else {
    Serial.println("{\"t\":\"error\",\"msg\":\"unknown_command_type\"}");
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000); // Wait 2 seconds for Serial Monitor to catch up
  Serial.println("\n\n--- Proxy Setup Started ---");

  WiFi.mode(WIFI_STA);
  WiFi.disconnect(); // Good practice for ESP-NOW in newer cores
  if (esp_now_init() != ESP_OK) {
    Serial.println("{\"t\":\"error\",\"msg\":\"espnow_init_failed\"}");
    while (true) delay(1000);
  }

  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataRecv);

  shadowConfigured = macIsSet(SHADOW_MAC);

  uint8_t* allPeers[] = {FIELD1_MAC, FIELD2_MAC, FIELD3_MAC, FIELD4_MAC, PUMP_MAC, SHADOW_MAC};
  const char* peerNames[] = {"field1", "field2", "field3", "field4", "pump", "shadow"};
  int peerCount = shadowConfigured ? 6 : 5;

  for (int i = 0; i < peerCount; i++) {
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, allPeers[i], 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
      Serial.print("{\"t\":\"error\",\"msg\":\"peer_add_failed\",\"peer\":\"");
      Serial.print(peerNames[i]);
      Serial.println("\"}");
    }
  }

  Serial.print("{\"t\":\"ready\",\"msg\":\"proxy_online\",\"shadow\":");
  Serial.print(shadowConfigured ? "true" : "false");
  Serial.println("}");
}

void loop() {
  unsigned long now = millis();

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) handleSerialLine(line);
  }

  if (shadowConfigured && now - lastShadowSync >= SHADOW_SYNC_INTERVAL_MS) {
    lastShadowSync = now;
    ShadowSyncPacket sync;
    sync.type = PKT_SHADOW_SYNC;
    for (int i = 0; i < 4; i++) {
      sync.fieldOnline[i] = (now - lastFieldHeartbeat[i]) < HEARTBEAT_TIMEOUT_MS;
    }
    sync.pumpOnline = (now - lastPumpHeartbeat) < HEARTBEAT_TIMEOUT_MS;
    sync.pumpCurrentlyOn = lastPumpOn;
    sync.activePlot = lastActivePlot;
    sync.timestampMs = now;
    esp_now_send(SHADOW_MAC, (uint8_t *)&sync, sizeof(sync));
  }
}
