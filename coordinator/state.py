import time
from collections import deque
from . import config

class FieldNodeState:
    def __init__(self):
        self.depth_raw = 0
        self.depth_cm = 0.0
        self.stage_name = "UNKNOWN"
        self.soil = 0
        self.water = False
        self.override = False
        self.last_seen = 0.0
        self.online = False
        self.depth_history = deque(maxlen=60)
        self.has_data = False
        self.uptime = 0
        self.reboot_detected = False
        self.valveOpen = None  # None means absent from message

class PumpNodeState:
    def __init__(self):
        self.pumpOn = False
        self.rain = 0
        self.voltage = 0.0
        self.current = 0.0
        self.power = 0.0
        self.fault = False
        self.last_seen = 0.0
        self.online = False
        self.has_data = False  # True after first valid pump_status received
        self.uptime = 0
        self.reboot_detected = False

class NetworkState:
    def __init__(self):
        self.field_nodes = {}
        self.pump_node = PumpNodeState()
        self.link_lost = False
        self.shadow_active = False
        self.seen_without_data = set()
        self.ignored_messages = 0
        self.alerts = deque(maxlen=20)

    def update_from_message(self, msg, current_time):
        t = msg.get("t")
        if t == "unparsed":
            return

        if t == "link_lost":
            self.link_lost = True
            return
            
        if t in ("ready", "error"):
            if t == "ready" and "shadow" in msg:
                self.shadow_active = msg.get("shadow", False)
            self.alerts.append({
                "ts": msg.get("ts", current_time),
                "type": t,
                "msg": msg.get("msg", "unknown")
            })
            return

        if t == "field_status":
            node_id = msg.get("node")
            if not isinstance(node_id, int) or node_id <= 0:
                self.ignored_messages += 1
                return
                
            required = ("depth", "stage", "soil", "water", "override", "uptime")
            if any(k not in msg for k in required):
                self.ignored_messages += 1
                return

            if node_id not in self.field_nodes:
                self.field_nodes[node_id] = FieldNodeState()
                
            if node_id in self.seen_without_data:
                self.seen_without_data.remove(node_id)
                
            node = self.field_nodes[node_id]
            node.depth_raw = msg.get("depth", 0)
            
            # Conversion: depth_cm = 20 - (depth_raw / 4095) * 20
            node.depth_cm = config.DEPTH_MAX_CM - (node.depth_raw / config.ADC_MAX) * config.DEPTH_MAX_CM
            node.depth_history.append(node.depth_cm)
            
            stage_raw = msg.get("stage", 0)
            if stage_raw < config.STAGE_VEG_MAX:
                node.stage_name = "VEGETATIVE"
            elif stage_raw < config.STAGE_FLOWER_MAX:
                node.stage_name = "FLOWERING"
            else:
                node.stage_name = "RIPENING"
                
            node.soil = msg.get("soil", 0)
            node.water = msg.get("water", False)
            node.override = msg.get("override", False)
            if "valveOpen" in msg:
                node.valveOpen = msg.get("valveOpen")
            
            uptime = msg.get("uptime", 0)
            if node.has_data and uptime < node.uptime:
                node.reboot_detected = True
            node.uptime = uptime
            
            node.last_seen = msg.get("ts", current_time)
            node.online = True
            node.has_data = True

        elif t == "pump_status":
            required = ("pumpOn", "rain", "voltage", "current", "power", "fault", "uptime")
            if any(k not in msg for k in required):
                self.ignored_messages += 1
                return
                
            self.pump_node.pumpOn = msg.get("pumpOn", False)
            self.pump_node.rain = msg.get("rain", 0)
            self.pump_node.voltage = msg.get("voltage", 0.0)
            self.pump_node.current = msg.get("current", 0.0)
            self.pump_node.power = msg.get("power", 0.0)
            self.pump_node.fault = msg.get("fault", False)
            
            uptime = msg.get("uptime", 0)
            if self.pump_node.uptime > 0 and uptime < self.pump_node.uptime:
                self.pump_node.reboot_detected = True
            self.pump_node.uptime = uptime
            
            self.pump_node.last_seen = msg.get("ts", current_time)
            self.pump_node.online = True
            self.pump_node.has_data = True

        elif t == "heartbeat":
            node_id = msg.get("node")
            if not isinstance(node_id, int) or node_id < 0:
                self.ignored_messages += 1
                return
                
            if node_id == 0:
                self.pump_node.last_seen = msg.get("ts", current_time)
                self.pump_node.online = True
            else:
                if node_id in self.field_nodes:
                    self.field_nodes[node_id].last_seen = msg.get("ts", current_time)
                    self.field_nodes[node_id].online = True
                else:
                    self.seen_without_data.add(node_id)

        # Check online status for all nodes
        self._check_timeouts(current_time)

    def _check_timeouts(self, current_time):
        if current_time - self.pump_node.last_seen > config.NODE_TIMEOUT_S:
            self.pump_node.online = False
            
        for node in self.field_nodes.values():
            if current_time - node.last_seen > config.NODE_TIMEOUT_S:
                node.online = False
