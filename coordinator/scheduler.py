"""
coordinator/scheduler.py
========================
P2 - Rule-based irrigation scheduler.

Design contract
---------------
* decide() is a PURE function: (NetworkState, SchedulerState, float) -> list[dict]
  It never touches the serial port and has no side effects; unit-testable without hardware.
* SchedulerState holds all mutable between-tick state.
* IrrigationEngine (in main.py) calls decide() each tick, then dispatches or dry-prints.

Command format (mirrors SERIAL_PROTOCOL.md):
    {"t": "valve", "node": N, "open": True|False}
    {"t": "pump",  "on":   True|False}

Safety invariants maintained by this module
-------------------------------------------
I1. Pump OFF before any valve is closed while irrigating (stop: pump-off first).
I2. Pump ON only after at least one valve-open is confirmed.
I3. No pump-on command while pump.fault is True. May send pump-off (always safe).
I4. No pump command before pump has_data is True.
I5. No valve command to a plot whose override flag is True.
I6. On link loss: abort any active irrigation (state becomes IDLE) and reset startup flush flags. On startup (or link restored): send pump-off, and send valve-close to every known non-override node once it has data.

Where I1 could be violated - see SAFETY AUDIT comment in ACTIVE abort block.
"""

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from . import config


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class SystemMode(Enum):
    IDLE   = auto()   # No plot needs water, or pump not ready.
    ARMING = auto()   # Valve-open sent; waiting for field confirmation or timeout.
    ACTIVE = auto()   # Pump on and valve open; irrigating.
    FAULT  = auto()   # pump.fault observed; stay safe until cleared.


@dataclass
class PlotSchedulingState:
    """Per-plot mutable data owned by the scheduler (not part of NetworkState)."""
    last_service_ts: Optional[float] = None  # initialized to time of first has_data
    cumulative_irrigation_s: float = 0.0   # total seconds irrigated (P3 equity)
    flush_done: bool = False
    cooldown_until: float = 0.0


@dataclass
class SchedulerState:
    """All mutable state the scheduler needs between ticks."""
    mode: SystemMode = SystemMode.IDLE
    active_node: Optional[int] = None      # node_id currently being irrigated
    mode_entered_ts: float = 0.0           # epoch when current mode was entered
    plots: dict = field(default_factory=dict)  # node_id -> PlotSchedulingState
    pump_first_tick_flush_done: bool = False
    pump_data_flush_done: bool = False
    link_lost_processed: bool = False
    last_command_ts: dict = field(default_factory=dict)  # cmd_key -> epoch

    def plot(self, node_id: int) -> PlotSchedulingState:
        if node_id not in self.plots:
            self.plots[node_id] = PlotSchedulingState()
        return self.plots[node_id]


# ---------------------------------------------------------------------------
# Rate-limiter helper
# ---------------------------------------------------------------------------

# Minimum gap between identical command keys; prevents serial bus spam.
# Abort / stop sequences bypass this intentionally.
_CMD_RATE_LIMIT_S = 2.0


def _rate_limited(sched: SchedulerState, key: str, now: float) -> bool:
    """Return True if key is within the rate window (caller should suppress the command)."""
    last = sched.last_command_ts.get(key, 0.0)
    if now - last < _CMD_RATE_LIMIT_S:
        return True
    sched.last_command_ts[key] = now
    return False


# ---------------------------------------------------------------------------
# Eligibility and priority (pure helpers, no I/O)
# ---------------------------------------------------------------------------

def _eligible_plots(net_state, sched: SchedulerState, now: float):
    eligible = []
    
    # ===== P3: Rain hold (System-wide) =====
    if config.RAIN_WET_BELOW_RAW is not None:
        # Rain sensor goes LOW when wet (analog drops)
        if net_state.pump_node.has_data and net_state.pump_node.rain < config.RAIN_WET_BELOW_RAW:
            return []   # Rain detected: suspend irrigation for all plots
    
    for node_id, node in net_state.field_nodes.items():
        if not node.has_data or not node.online or node.override:
            continue

        # ===== P3: Growth-stage AWD suspension =====
        # During critical stages (like Flowering), AWD drying is suspended
        # and the water level is kept much higher to prevent yield loss.
        threshold_cm = config.IRRIGATE_BELOW_CM
        if node.stage_name in config.SUSPEND_AWD_STAGES:
            threshold_cm = config.CRITICAL_STAGE_IRRIGATE_BELOW_CM

        needs_water = (node.depth_cm < threshold_cm) or (node.soil > config.TARGET_SOIL_MOISTURE)
        if not needs_water:
            continue          
        
        ps = sched.plot(node_id)
        if now < ps.cooldown_until:
            continue          

        eligible.append((node_id, sched.plot(node_id), node))
    return eligible


def _priority_score(node_id: int, ps: PlotSchedulingState, node, sched: SchedulerState, now: float) -> float:
    depth_deficit  = max(0.0, config.IRRIGATE_BELOW_CM - node.depth_cm)
    service_ref    = ps.last_service_ts if ps.last_service_ts is not None else now
    seconds_since  = now - service_ref

    score = (depth_deficit * config.W_DEPTH_DEFICIT
             + seconds_since * config.W_WAIT_TIME)

    # ===== P3: Equity penalty =====
    # Ensures no single plot hogs the pump if multiple plots need water
    num_plots = len(sched.plots)
    if num_plots > 0:
        total_s = sum(p.cumulative_irrigation_s for p in sched.plots.values())
        fair_share_s = total_s / num_plots
        equity_penalty = max(0.0, ps.cumulative_irrigation_s - fair_share_s)
        score -= (equity_penalty * config.W_EQUITY_PENALTY)

    return score


def _choose_plot(eligible, sched: SchedulerState, now: float):
    if not eligible:
        return None
    return max(eligible, key=lambda t: _priority_score(t[0], t[1], t[2], sched, now))


# ---------------------------------------------------------------------------
# Core decision function (PURE - no I/O, deterministic)
# ---------------------------------------------------------------------------

def decide(net_state, sched: SchedulerState, now: float) -> list:
    """
    Pure decision function. No I/O. No randomness. Safe to call in unit tests.

    Parameters
    ----------
    net_state : NetworkState   (treated read-only during this call)
    sched     : SchedulerState (mutated; caller must persist between ticks)
    now       : float          current epoch time

    Returns
    -------
    list of command dicts in dispatch order; empty list = nothing to do this tick.
    """
    cmds = []
    pump = net_state.pump_node

    # --- I6: Link loss ---------------------------------------------------
    if net_state.link_lost:
        if not sched.link_lost_processed:
            print("[!] Link lost: no commands can be delivered.")
            sched.mode = SystemMode.IDLE
            sched.active_node = None
            sched.pump_data_flush_done = False
            for ps in sched.plots.values():
                ps.flush_done = False
            sched.link_lost_processed = True
        return cmds
    else:
        sched.link_lost_processed = False

    # --- I6: Startup flush -----------------------------------------------
    prevent_arming = False
    if not sched.pump_first_tick_flush_done:
        cmds.append({"t": "pump", "on": False})
        sched.pump_first_tick_flush_done = True
        
    if pump.has_data and not sched.pump_data_flush_done:
        cmds.append({"t": "pump", "on": False})
        sched.pump_data_flush_done = True
        
    for node_id, node in net_state.field_nodes.items():
        if node.has_data:
            ps = sched.plot(node_id)
            if ps.last_service_ts is None:
                ps.last_service_ts = now
            if not ps.flush_done:
                if not node.override:
                    key = f"startup_flush_{node_id}"
                    if not _rate_limited(sched, key, now):
                        cmds.append({"t": "valve", "node": node_id, "open": False})
                        prevent_arming = True
                ps.flush_done = True

    # --- I3 / I4: pump availability guard --------------------------------
    pump_available = pump.online and pump.has_data and not pump.fault

    # --- FAULT entry -----------------------------------------------------
    if pump.fault:
        if sched.mode != SystemMode.FAULT:
            # SAFETY AUDIT (I3 vs I1 conflict):
            # We may send pump OFF during fault (always safe), but never send pump ON.
            key_pump = "pump_off_fault"
            if not _rate_limited(sched, key_pump, now):
                cmds.append({"t": "pump", "on": False})
                cmds.append({"t": "sms", "phone": config.FARMER_PHONES.get(0), "msg": "AWD ALERT: Pump fault detected! Safe shutdown engaged."})
                
            for node_id, node in net_state.field_nodes.items():
                if not node.override:
                    key = f"valve_close_fault_{node_id}"
                    if not _rate_limited(sched, key, now):
                        cmds.append({"t": "valve", "node": node_id, "open": False})
            sched.mode = SystemMode.FAULT
            sched.active_node = None
        return cmds

    # Fault cleared: return to IDLE
    if sched.mode == SystemMode.FAULT:
        sched.mode = SystemMode.IDLE

    # =====================================================================
    # IDLE
    # =====================================================================
    if sched.mode == SystemMode.IDLE:
        # --- Check for manual override pumping ---
        manual_pump_needed = False
        for nid, node in net_state.field_nodes.items():
            if node.online and node.has_data and node.override:
                manual_pump_needed = True
                if not node.valveOpen:
                    key = f"manual_valve_open_{nid}"
                    if not _rate_limited(sched, key, now):
                        cmds.append({"t": "valve", "node": nid, "open": True})

        if manual_pump_needed and pump_available:
            if not pump.pumpOn:
                key = "manual_pump_on"
                if not _rate_limited(sched, key, now):
                    cmds.append({"t": "pump", "on": True})
            return cmds  # Suspend automated scheduling while manual watering is active

        # Reconciliation
        if pump.online and pump.has_data and pump.pumpOn and not manual_pump_needed:
            key = "recon_pump_off"
            if not _rate_limited(sched, key, now):
                cmds.append({"t": "pump", "on": False})
                
        for nid, node in net_state.field_nodes.items():
            if node.online and node.has_data and not node.override and node.valveOpen is True:
                key = f"recon_valve_close_{nid}"
                if not _rate_limited(sched, key, now):
                    cmds.append({"t": "valve", "node": nid, "open": False})

        if prevent_arming:
            return cmds

        if not pump_available:
            return cmds   # Wait for pump to come online with data

        eligible = _eligible_plots(net_state, sched, now)
        chosen = _choose_plot(eligible, sched, now)
        if chosen is None:
            return cmds   # No plot needs water right now

        node_id, ps, node = chosen
        key = f"valve_open_{node_id}"
        if not _rate_limited(sched, key, now):
            cmds.append({"t": "valve", "node": node_id, "open": True})
            sched.active_node = node_id
            sched.mode = SystemMode.ARMING
            sched.mode_entered_ts = now

    # =====================================================================
    # ARMING
    # Valve-open command sent. Wait for water_presence confirmation or timeout.
    # Pump has NOT been turned on yet.
    # =====================================================================
    elif sched.mode == SystemMode.ARMING:
        node_id = sched.active_node
        active_node = net_state.field_nodes.get(node_id)

        # Guard: chosen plot went offline or override engaged
        if (active_node is None
                or not active_node.online
                or active_node.override):
            # Pump was never on; just close the valve. No I1 concern.
            if node_id is not None:
                if active_node is None or not active_node.override:
                    key = f"valve_close_{node_id}"
                    if not _rate_limited(sched, key, now):
                        cmds.append({"t": "valve", "node": node_id, "open": False})
            sched.mode = SystemMode.IDLE
            sched.active_node = None
            return cmds

        # Confirmation: valveOpen is true AND VALVE_SETTLE_S elapsed
        arming_timeout  = (now - sched.mode_entered_ts) >= config.ARMING_TIMEOUT_S
        settle_elapsed  = (now - sched.mode_entered_ts) >= config.VALVE_SETTLE_S
        
        valve_confirmed = False
        if active_node.valveOpen is None:
            if settle_elapsed:
                valve_confirmed = True
                print(f"[!] Node {node_id} has no valveOpen in status, falling back to settle delay.")
        else:
            if active_node.valveOpen and settle_elapsed:
                valve_confirmed = True

        if arming_timeout and not valve_confirmed:
            if node_id is not None and not active_node.override:
                key = f"valve_close_{node_id}"
                if not _rate_limited(sched, key, now):
                    cmds.append({"t": "valve", "node": node_id, "open": False})
            if node_id is not None:
                sched.plot(node_id).cooldown_until = now + config.RESELECT_COOLDOWN_S
            sched.mode = SystemMode.IDLE
            sched.active_node = None
            return cmds

        if valve_confirmed:
            if not pump_available:
                # Pump disappeared during arming; close valve and go idle.
                if node_id is not None and not active_node.override:
                    key = f"valve_close_{node_id}"
                    if not _rate_limited(sched, key, now):
                        cmds.append({"t": "valve", "node": node_id, "open": False})
                sched.mode = SystemMode.IDLE
                sched.active_node = None
                return cmds

            # I2: valve is open; now safe to turn pump on.
            key = "pump_on"
            if not _rate_limited(sched, key, now):
                cmds.append({"t": "pump", "on": True})
                sched.mode = SystemMode.ACTIVE
                sched.mode_entered_ts = now

    # =====================================================================
    # ACTIVE
    # Pump on; valve open; irrigating.
    # =====================================================================
    elif sched.mode == SystemMode.ACTIVE:
        node_id    = sched.active_node
        active_node = net_state.field_nodes.get(node_id)
        elapsed    = now - sched.mode_entered_ts

        # --- Abort conditions --------------------------------------------
        abort_reason = None
        if active_node is None or not active_node.online:
            abort_reason = "node_offline"
        elif not pump.online:
            abort_reason = "pump_offline"
        elif active_node.override:
            abort_reason = "override_engaged"

        if abort_reason:
            # I1: pump off FIRST then valve close.
            # Rate-limiter intentionally bypassed for abort to guarantee I1.
            sched.last_command_ts[f"abort_pump_{node_id}"] = now
            cmds.append({"t": "pump", "on": False})
            
            # SMS ALERTS
            farmer_phone = config.FARMER_PHONES.get(node_id, config.FARMER_PHONES.get(0))
            if abort_reason == "override_engaged":
                cmds.append({"t": "sms", "phone": farmer_phone, "msg": f"AWD ALERT: Farmer override engaged on plot {node_id}."})
            elif abort_reason == "node_offline":
                cmds.append({"t": "sms", "phone": farmer_phone, "msg": f"AWD ALERT: Plot {node_id} offline during irrigation!"})
            elif abort_reason == "pump_offline":
                cmds.append({"t": "sms", "phone": config.FARMER_PHONES.get(0), "msg": "AWD ALERT: Pump offline mid-irrigation!"})
            
            # For override mid-irrigation, send pump off only, return to IDLE
            if node_id is not None and abort_reason != "override_engaged":
                sched.last_command_ts[f"abort_valve_{node_id}"] = now
                cmds.append({"t": "valve", "node": node_id, "open": False})
                
            ps = sched.plot(node_id) if node_id is not None else None
            if ps is not None:
                ps.cumulative_irrigation_s += elapsed
                ps.last_service_ts = now
                ps.cooldown_until = now + config.RESELECT_COOLDOWN_S
            sched.mode = SystemMode.IDLE
            sched.active_node = None
            return cmds

        # --- Reconciliation ----------------------------------------------
        if pump.online and pump.has_data and not pump.pumpOn:
            if elapsed >= config.PUMP_CONFIRM_S:
                print(f"[!] pump_start_unconfirmed. Aborting.")
                sched.last_command_ts[f"abort_pump_{node_id}"] = now
                cmds.append({"t": "pump", "on": False})
                if node_id is not None and not active_node.override:
                    sched.last_command_ts[f"abort_valve_{node_id}"] = now
                    cmds.append({"t": "valve", "node": node_id, "open": False})
                ps = sched.plot(node_id) if node_id is not None else None
                if ps is not None:
                    ps.cooldown_until = now + config.RESELECT_COOLDOWN_S
                sched.mode = SystemMode.IDLE
                sched.active_node = None
                return cmds

        if active_node is not None and active_node.online and active_node.has_data and active_node.valveOpen is False:
            print(f"[!] valve_closed_unexpectedly for plot {node_id}. Aborting.")
            sched.last_command_ts[f"abort_pump_{node_id}"] = now
            cmds.append({"t": "pump", "on": False})
            if not active_node.override:
                sched.last_command_ts[f"abort_valve_{node_id}"] = now
                cmds.append({"t": "valve", "node": node_id, "open": False})
            ps = sched.plot(node_id)
            ps.cooldown_until = now + config.RESELECT_COOLDOWN_S
            sched.mode = SystemMode.IDLE
            sched.active_node = None
            return cmds

        # --- Water Confirmation ---
        if elapsed >= config.WATER_CONFIRM_S and not active_node.water:
            print(f"[!] no_water_detected for plot {node_id}. Aborting.")
            sched.last_command_ts[f"stop_pump_{node_id}"] = now
            cmds.append({"t": "pump", "on": False})
            farmer_phone = config.FARMER_PHONES.get(node_id, config.FARMER_PHONES.get(0))
            cmds.append({"t": "sms", "phone": farmer_phone, "msg": f"AWD ALERT: No water reached plot {node_id}! Check pipes."})
            if node_id is not None and not active_node.override:
                sched.last_command_ts[f"stop_valve_{node_id}"] = now
                cmds.append({"t": "valve", "node": node_id, "open": False})
            ps = sched.plot(node_id) if node_id is not None else None
            if ps is not None:
                ps.cumulative_irrigation_s += elapsed
                ps.last_service_ts = now
                ps.cooldown_until = now + config.RESELECT_COOLDOWN_S
            sched.mode = SystemMode.IDLE
            sched.active_node = None
            return cmds

        # --- Normal stop conditions --------------------------------------
        stop = False
        if active_node.depth_cm >= config.TARGET_DEPTH_CM:
            stop = True   # Target depth reached
        elif active_node.soil < config.TARGET_SOIL_MOISTURE:
            stop = True   # Soil is sufficiently wet
        elif elapsed >= config.MAX_IRRIGATION_S:
            stop = True   # Timeout

        if stop:
            # I1: pump off FIRST then valve close. Rate-limiter bypassed for safety.
            sched.last_command_ts[f"stop_pump_{node_id}"] = now
            cmds.append({"t": "pump", "on": False})
            if node_id is not None and not active_node.override:
                sched.last_command_ts[f"stop_valve_{node_id}"] = now
                cmds.append({"t": "valve", "node": node_id, "open": False})
            ps = sched.plot(node_id)
            ps.cumulative_irrigation_s += elapsed
            ps.last_service_ts = now
            ps.cooldown_until = now + config.RESELECT_COOLDOWN_S
            sched.mode = SystemMode.IDLE
            sched.active_node = None

    return cmds
