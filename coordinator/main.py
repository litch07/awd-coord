"""
coordinator/main.py
===================
Entry point for the AWD-COORD scheduler.

Usage
-----
  python -m coordinator.main                     # dry-run (default); reads real data, prints commands only
  python -m coordinator.main --dry-run           # explicit dry-run (same as above)
  python -m coordinator.main --live              # LIVE mode: sends real commands over serial
  python -m coordinator.main --port COM5         # override serial port
  python -m coordinator.main --live --port COM5  # live on specific port

In dry-run mode the serial port is opened normally (real incoming data is consumed
and state is built from it), but NO bytes are ever written to the port. This is the safe
default that satisfies the task requirement: "Default is dry-run ON."

All commands (sent or dry-run) are logged with a timestamp to tests/logs/.
"""

import argparse
import json
import os
import sys
import time
import threading
from pathlib import Path

import serial

from . import config
from .scheduler import SchedulerState, SystemMode, decide
from .serial_link import SerialLink
from .state import NetworkState
from .sheets_uplink import start_sheets_uplink_thread


# ---------------------------------------------------------------------------
# Command logger
# ---------------------------------------------------------------------------

class CommandLogger:
    """Appends every command (sent or dry-run) to a JSONL log file."""

    def __init__(self, log_path: Path, dry_run: bool):
        self._path = log_path
        self._dry_run = dry_run
        self._file = open(log_path, "a", buffering=1, encoding="utf-8")

    def log(self, cmd: dict, sent: bool):
        record = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "dry_run": self._dry_run,
            "sent": sent,
            "cmd": cmd,
        }
        self._file.write(json.dumps(record) + "\n")

    def close(self):
        self._file.close()


# ---------------------------------------------------------------------------
# IrrigationEngine - wires decide() into the main loop
# ---------------------------------------------------------------------------

class IrrigationEngine:
    """
    Stateful wrapper around the pure decide() function.
    Holds SchedulerState between ticks and dispatches commands to the serial link.

    Safety audit - pump on with no open valve
    -----------------------------------------
    The only path to pump-on is: ARMING -> ACTIVE transition inside decide().
    That transition only fires after a valve-open command was issued (in the
    IDLE->ARMING transition of the same or a previous tick). Because we send
    valve-open and wait at least one tick (plus ARMING_TIMEOUT_S) before
    pump-on, the valve command always precedes the pump command in time.
    However: the coordinator does not get hardware acknowledgment that the
    servo physically moved. If the servo fails silently (jammed, powered off),
    the pump can turn on with the valve mechanically closed. This is a hardware
    gap, not a software gap; the coordinator has no sensor for servo position.
    """

    def __init__(self, link: SerialLink, dry_run: bool, cmd_logger: CommandLogger):
        self._link = link
        self._dry_run = dry_run
        self._logger = cmd_logger
        self._sched = SchedulerState()
        self.lock = threading.Lock()

    def get_snapshot(self, net_state: NetworkState):
        import copy
        with self.lock:
            return copy.deepcopy(net_state), copy.deepcopy(self._sched)

    def tick(self, net_state: NetworkState, now: float):
        cmds = decide(net_state, self._sched, now)
        for cmd in cmds:
            self._dispatch(cmd)

    def _dispatch(self, cmd: dict):
        if self._dry_run:
            print(f"  [DRY-RUN] Would send: {json.dumps(cmd)}")
            self._logger.log(cmd, sent=False)
        else:
            t = cmd.get("t")
            if t == "valve":
                self._link.valve(cmd["node"], cmd["open"])
            elif t == "pump":
                self._link.pump(cmd["on"])
            elif t == "sms":
                self._link.sms(cmd["phone"], cmd["msg"])
            self._logger.log(cmd, sent=True)
            print(f"  [SENT]    {json.dumps(cmd)}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _parse_args():
    p = argparse.ArgumentParser(
        prog="python -m coordinator.main",
        description="AWD-COORD irrigation scheduler",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", dest="dry_run", action="store_true", default=True,
        help="Consume real data but only print commands (default).",
    )
    mode.add_argument(
        "--live", dest="dry_run", action="store_false",
        help="Send real commands over serial. Requires explicit flag.",
    )
    p.add_argument(
        "--port", default=config.SERIAL_PORT,
        help=f"Serial port (default: {config.SERIAL_PORT}).",
    )
    return p.parse_args()


def main():
    args = _parse_args()
    dry_run = args.dry_run

    if os.name == "nt":
        os.system("")  # Enable ANSI on Windows

    # Prepare log directory
    log_dir = Path("tests/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    session_ts = int(time.time())
    raw_log_path = log_dir / f"session_{session_ts}.jsonl"
    cmd_log_path = log_dir / f"commands_{session_ts}.jsonl"

    mode_label = "DRY-RUN (default)" if dry_run else "LIVE - REAL COMMANDS WILL BE SENT"
    print(f"Starting AWD-COORD Coordinator [{mode_label}]")
    print(f"Port: {args.port}")
    print(f"Raw message log : {raw_log_path}")
    print(f"Command log     : {cmd_log_path}")
    if not dry_run:
        print("WARNING: Live mode active. Commands will be sent to hardware.")
        
    if config.TARGET_DEPTH_CM >= config.DEPTH_MAX_CM:
        print(f"[WARNING] config.TARGET_DEPTH_CM ({config.TARGET_DEPTH_CM}) is >= config.DEPTH_MAX_CM ({config.DEPTH_MAX_CM})")

    link = SerialLink(port=args.port, baud=config.BAUD)
    try:
        link.start()
    except serial.SerialException as e:
        print(f"[ERROR] Cannot open {args.port}: {e}")
        print("Close Arduino Serial Monitor, check Device Manager, and retry.")
        sys.exit(1)

    state = NetworkState()
    cmd_logger = CommandLogger(cmd_log_path, dry_run)
    engine = IrrigationEngine(link, dry_run, cmd_logger)

    start_sheets_uplink_thread(engine, state)

    last_print_time = 0.0

    with open(raw_log_path, "w", buffering=1, encoding="utf-8") as raw_log:
        try:
            while True:
                now = time.time()

                # Drain incoming messages
                while not link.rx.empty():
                    msg = link.rx.get()
                    raw_log.write(json.dumps(msg) + "\n")
                    with engine.lock:
                        state.update_from_message(msg, now)

                # Timeout check
                with engine.lock:
                    state._check_timeouts(now)

                # Link lost: engine will emit safe flush on next tick
                with engine.lock:
                    if state.link_lost:
                        engine.tick(state, now)
                        print("\n[!] Serial link lost. Exiting.")
                        break

                # Run scheduler
                with engine.lock:
                    engine.tick(state, now)

                # Console status (1 Hz)
                if now - last_print_time >= 1.0:
                    last_print_time = now
                    with engine.lock:
                        _print_status(state, engine._sched, dry_run)

                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            cmd_logger.close()
            link.stop()


def _print_status(state: NetworkState, sched: SchedulerState, dry_run: bool):
    """Print a live status table to stdout."""
    has_nodes = bool(state.field_nodes) or state.pump_node.last_seen > 0
    if not has_nodes:
        print("Waiting for live data...", end="\r")
        return

    sys.stdout.write("\033[2J\033[H")  # Clear screen
    mode_tag = "[DRY-RUN]" if dry_run else "[LIVE]"
    print(f"=== AWD-COORD Live Status {mode_tag} ===")
    print(f"Scheduler mode : {sched.mode.name}  active node: {sched.active_node}")
    
    shadow_tag = "ONLINE (Failover Active)" if state.shadow_active else "OFFLINE / NOT CONFIGURED"
    print(f"Shadow Coord   : {shadow_tag}")

    p = state.pump_node
    p_online = "ONLINE" if p.online else "OFFLINE"
    p_data   = "has_data" if p.has_data else "NO DATA"
    p_reboot = " (REBOOTED)" if p.reboot_detected else ""
    print(
        f"PUMP [Node 0]: {p_online} {p_data}{p_reboot} | "
        f"On: {p.pumpOn} | Rain: {p.rain} | "
        f"V: {p.voltage:.2f}V  I: {p.current:.2f}A  P: {p.power:.2f}W | "
        f"Fault: {p.fault}"
    )

    print("\nFIELD NODES:")
    print(f"{'Node':<6} | {'Status':<7} | {'Data':<8} | {'Depth':<6} | {'Stage':<10} | {'Soil':<5} | {'Water':<5} | Override")
    print("-" * 75)
    for node_id, n in sorted(state.field_nodes.items()):
        n_status = "ONLINE" if n.online else "OFFLINE"
        n_reboot = "*" if n.reboot_detected else ""
        if not n.has_data:
            print(f"{str(node_id)+n_reboot:<6} | {n_status:<7} | waiting  | (no data yet)")
        else:
            active_mark = " <-- IRRIGATING" if node_id == sched.active_node else ""
            print(
                f"{str(node_id)+n_reboot:<6} | {n_status:<7} | has_data | "
                f"{n.depth_cm:<5.1f}  | {n.stage_name:<10} | {n.soil:<5} | "
                f"{str(n.water):<5} | {n.override}{active_mark}"
            )

    if state.seen_without_data:
        ids = ", ".join(map(str, sorted(state.seen_without_data)))
        print(f"\nHeartbeat-only (no data yet): {ids}")

    if state.alerts:
        print("\nRECENT ALERTS:")
        for alert in list(state.alerts)[-5:]:
            ts_str = time.strftime("%H:%M:%S", time.localtime(alert["ts"]))
            print(f"  [{ts_str}] {alert['type'].upper()}: {alert['msg']}")

    if state.ignored_messages > 0:
        print(f"\nIgnored invalid messages: {state.ignored_messages}")

    print("\n(Ctrl+C to stop)")


if __name__ == "__main__":
    main()
