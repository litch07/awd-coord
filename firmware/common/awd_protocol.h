// awd_protocol.h
#ifndef AWD_PROTOCOL_H
#define AWD_PROTOCOL_H

#include <stdint.h>

enum PacketType : uint8_t {
  PKT_FIELD_STATUS  = 1,
  PKT_PUMP_STATUS   = 2,
  PKT_VALVE_COMMAND = 3,
  PKT_PUMP_COMMAND  = 4,
  PKT_HEARTBEAT     = 5,
  PKT_SHADOW_SYNC   = 6
};

struct FieldStatusPacket {
  uint8_t  type;
  uint8_t  nodeId;
  uint16_t depthRaw;
  uint16_t cropStageRaw;
  uint16_t soilMoisture;
  bool     waterPresent;    // true = water detected (HIGH on GPIO35)
  bool     overrideActive;
  bool     valveOpen;       // last commanded valve state (no servo position sensor)
  uint32_t uptimeMs;
};

struct PumpStatusPacket {
  uint8_t  type;
  bool     pumpOn;
  uint16_t rainRaw;
  float    busVoltage;
  float    currentMa;
  float    powerMw;
  bool     faultSimulated;
  uint32_t uptimeMs;
};

struct ValveCommandPacket {
  uint8_t type;
  uint8_t nodeId;
  bool    openValve;
};

struct PumpCommandPacket {
  uint8_t type;
  bool    pumpOn;
};

struct HeartbeatPacket {
  uint8_t type;
  uint8_t nodeId;   // 0 = pump, 1-4 = field nodes
};

struct ShadowSyncPacket {
  uint8_t  type;
  bool     fieldOnline[4];
  bool     pumpOnline;
  bool     pumpCurrentlyOn;
  uint8_t  activePlot;
  uint32_t timestampMs;
};

#endif
