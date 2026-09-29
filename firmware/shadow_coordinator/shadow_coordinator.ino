/*
  AWD-COORD — SHADOW COORDINATOR PRODUCTION FIRMWARE
  =====================================================
  Role: Silently mirrors Proxy state via ShadowSyncPacket. Detects primary
  failure (no sync received within timeout) and asserts a SAFE SHUTDOWN
  state (all valves closed, pump off) — not a replication of scheduling
  intelligence, since that logic lives only in the Python coordinator.

  FAILOVER BEHAVIOR (confirmed decision): safe shutdown only. This does NOT
  continue irrigation scheduling — it only ensures a safe state when the
  primary link is lost.

  ARCHITECTURE NOTE: field nodes and the pump node currently address their
  status packets only to PROXY_MAC, never to this board. So in practice the
  only packet type this board will ever receive is PKT_SHADOW_SYNC. The
  receive callback below explicitly checks type and size for every defined
  packet anyway, and safely ignores anything unexpected, so nothing breaks
  if that addressing ever changes later.

  Requires: mac_config.h, awd_protocol.h (identical versions to every other
  board — struct sizes must match exactly, or packets are silently dropped).
*/

#include <esp_now.h>
#include <WiFi.h>
#include "../common/mac_config.h"
#include "../common/awd_protocol.h"

#define STATUS_LED 4
#define SYNC_TIMEOUT_MS 3000   // no ShadowSyncPacket for 3s = primary considered down
#define LED_BLINK_INTERVAL_MS 300

bool primaryDown = false;
bool failoverActionTaken = false; // ensures shutdown commands are sent only once per failure
unsigned long lastSyncReceived = 0;
unsigned long lastBlink = 0;
bool blinkState = false;

// Last known state, for Serial diagnostics only — no scheduling decisions made from this
ShadowSyncPacket lastKnownState;
bool hasReceivedSync = false;

void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  if (status != ESP_NOW_SEND_SUCCESS) {
    Serial.println("[ESP-NOW] Send FAILED");
  }
}

void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len < 1) return;
  uint8_t type = data[0];

  switch (type) {
    case PKT_SHADOW_SYNC:
      if (len != sizeof(ShadowSyncPacket)) {
        Serial.println("[WARN] SHADOW_SYNC size mismatch — check awd_protocol.h matches Proxy");
        return;
      }
      memcpy(&lastKnownState, data, sizeof(lastKnownState));
      hasReceivedSync = true;
      lastSyncReceived = millis();

      if (primaryDown) {
        Serial.println(">>> PRIMARY RESTORED — Shadow standing down <<<");
        primaryDown = false;
        failoverActionTaken = false;
      }
      break;

    // These are never expected to arrive here given current unicast addressing
    // (see architecture note above). Logged, not acted on, in case that changes.
    case PKT_FIELD_STATUS:
    case PKT_PUMP_STATUS:
    case PKT_HEARTBEAT:
    case PKT_VALVE_COMMAND:
    case PKT_PUMP_COMMAND:
      Serial.print("[INFO] Unexpected packet type ");
      Serial.print(type);
      Serial.println(" received — no addressing currently sends this here; ignored.");
      break;

    default:
      Serial.println("[WARN] Unknown packet type received; ignored.");
      break;
  }
}

void sendSafeShutdown() {
  Serial.println(">>> SHADOW FAILOVER: sending safe-shutdown to all nodes <<<");

  ValveCommandPacket valveCmd;
  valveCmd.type = PKT_VALVE_COMMAND;
  valveCmd.openValve = false;

  uint8_t* fieldMacs[] = {FIELD1_MAC, FIELD2_MAC, FIELD3_MAC, FIELD4_MAC};
  for (int i = 0; i < 4; i++) {
    valveCmd.nodeId = i + 1;
    esp_now_send(fieldMacs[i], (uint8_t *)&valveCmd, sizeof(valveCmd));
    delay(20); // small gap between sends, avoid radio congestion
  }

  PumpCommandPacket pumpCmd;
  pumpCmd.type = PKT_PUMP_COMMAND;
  pumpCmd.pumpOn = false;
  esp_now_send(PUMP_MAC, (uint8_t *)&pumpCmd, sizeof(pumpCmd));

  Serial.println(">>> Safe-shutdown commands sent to all 4 field nodes + pump <<<");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== AWD-COORD SHADOW COORDINATOR — PRODUCTION ===");

  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);

  WiFi.mode(WIFI_STA);
  Serial.print("Shadow Coordinator MAC: ");
  Serial.println(WiFi.macAddress());

  if (esp_now_init() != ESP_OK) {
    Serial.println("[ESP-NOW] Init FAILED — halting.");
    while (true) delay(1000);
  }

  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataRecv);

  // Needs to send to field/pump nodes directly if failover triggers
  uint8_t* allTargets[] = {FIELD1_MAC, FIELD2_MAC, FIELD3_MAC, FIELD4_MAC, PUMP_MAC};
  const char* targetNames[] = {"field1", "field2", "field3", "field4", "pump"};
  for (int i = 0; i < 5; i++) {
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, allTargets[i], 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
      Serial.print("[ESP-NOW] Failed to add peer: ");
      Serial.println(targetNames[i]);
    }
  }

  lastSyncReceived = millis(); // don't immediately trigger failover at boot
  Serial.println("Shadow Coordinator ready. Monitoring for Proxy sync...\n");
}

void loop() {
  unsigned long now = millis();

  bool syncTimedOut = (now - lastSyncReceived) > SYNC_TIMEOUT_MS;

  if (syncTimedOut && !primaryDown) {
    primaryDown = true;
    Serial.println(">>> PRIMARY DOWN — no ShadowSync received within timeout <<<");
  }

  if (primaryDown && !failoverActionTaken) {
    sendSafeShutdown();
    failoverActionTaken = true;
  }

  // --- LED: solid = normal, blinking = failover active, off = no sync yet ---
  if (primaryDown) {
    if (now - lastBlink >= LED_BLINK_INTERVAL_MS) {
      lastBlink = now;
      blinkState = !blinkState;
      digitalWrite(STATUS_LED, blinkState);
    }
  } else {
    digitalWrite(STATUS_LED, hasReceivedSync ? HIGH : LOW);
  }

  // --- Diagnostic print, once per second ---
  static unsigned long lastPrint = 0;
  if (now - lastPrint >= 1000) {
    lastPrint = now;
    if (hasReceivedSync) {
      Serial.printf("[STATUS] Primary: %s | Fields online: %d%d%d%d | Pump online: %s | Pump on: %s | Active plot: %d\n",
        primaryDown ? "DOWN" : "OK",
        lastKnownState.fieldOnline[0], lastKnownState.fieldOnline[1],
        lastKnownState.fieldOnline[2], lastKnownState.fieldOnline[3],
        lastKnownState.pumpOnline ? "yes" : "no",
        lastKnownState.pumpCurrentlyOn ? "yes" : "no",
        lastKnownState.activePlot);
    } else {
      Serial.println("[STATUS] Waiting for first ShadowSync from Proxy...");
    }
  }
}
