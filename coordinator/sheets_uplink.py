"""
coordinator/sheets_uplink.py
============================
Google Sheets uplink for AWD-COORD.
"""

import argparse
import datetime
import sys
import threading
import time
import traceback
from typing import List, Any, Tuple

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None


from . import config
from .state import NetworkState
from .scheduler import SchedulerState, SystemMode


def format_bool(val: bool) -> str:
    if val is None:
        return ""
    return "TRUE" if val else "FALSE"


def build_system_row(net_state: NetworkState, sched: SchedulerState, now: float) -> List[Any]:
    """
    Pure function to build the single data row for the 'system' tab.
    Unknown values are represented as empty strings.
    """
    has_nodes = bool(net_state.field_nodes) or net_state.pump_node.last_seen > 0
    if not has_nodes:
        return []

    p = net_state.pump_node

    updated_at_epoch_s = int(now)
    updated_at_iso_utc = datetime.datetime.utcfromtimestamp(now).isoformat() + "Z"
    system_mode = sched.mode.name
    active_plot = sched.active_node if sched.active_node is not None else ""
    
    pump_on = format_bool(p.pumpOn) if p.has_data else ""
    pump_fault = format_bool(p.fault) if p.has_data else ""
    pump_online = format_bool(p.online) if p.last_seen > 0 else ""
    
    rain_raw = p.rain if p.has_data else ""
    pump_voltage = p.voltage if p.has_data else ""
    pump_current_ma = p.current * 1000.0 if p.has_data else ""
    pump_power_mw = p.power * 1000.0 if p.has_data else ""
    
    link_status = "LINK_LOST" if net_state.link_lost else "OK"

    return [
        updated_at_epoch_s,
        updated_at_iso_utc,
        system_mode,
        active_plot,
        pump_on,
        pump_fault,
        pump_online,
        rain_raw,
        pump_voltage,
        pump_current_ma,
        pump_power_mw,
        link_status
    ]


def build_plots_rows(net_state: NetworkState, sched: SchedulerState, now: float) -> List[List[Any]]:
    """
    Pure function to build rows for the 'plots' tab.
    One row per field node that has sent data this run.
    """
    rows = []
    has_nodes = bool(net_state.field_nodes) or net_state.pump_node.last_seen > 0
    if not has_nodes:
        return rows
        
    for node_id, node in sorted(net_state.field_nodes.items()):
        if not node.has_data:
            continue
            
        ps = sched.plots.get(node_id)
        
        online = format_bool(node.online)
        depth_cm = round(node.depth_cm, 2) if node.depth_cm is not None else ""
        stage = node.stage_name
        water_present = format_bool(node.water)
        override = format_bool(node.override)
        valve_open = format_bool(node.valveOpen) if node.valveOpen is not None else ""
        
        irrigation_seconds_total = int(ps.cumulative_irrigation_s) if ps else 0
        last_service = int(ps.last_service_ts) if ps and ps.last_service_ts else ""
        
        row = [
            node_id,
            online,
            depth_cm,
            stage,
            water_present,
            override,
            valve_open,
            irrigation_seconds_total,
            last_service
        ]
        rows.append(row)
        
    return rows


class UplinkThread(threading.Thread):
    def __init__(self, engine, state):
        super().__init__(daemon=True)
        self.engine = engine
        self.state = state
        self.client = None
        self.sheet = None

    def run(self):
        print("[Sheets] Uplink thread starting.")
        if gspread is None:
            print("[Sheets] gspread or google-auth not installed. Sheets uplink disabled.")
            return

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        try:
            creds = Credentials.from_service_account_file(config.SHEETS_CREDENTIALS_PATH, scopes=scopes)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(config.SHEETS_SPREADSHEET_ID)
        except FileNotFoundError:
            print(f"[Sheets] Credentials file '{config.SHEETS_CREDENTIALS_PATH}' not found. Running without Google Sheets.")
            return
        except Exception as e:
            print(f"[Sheets] Failed to initialize Google Sheets: {e}")
            return

        print("[Sheets] Successfully authenticated and opened spreadsheet.")

        while True:
            time.sleep(config.SHEETS_PUSH_INTERVAL_S)
            self._push()

    def _push(self):
        try:
            net_state, sched = self.engine.get_snapshot(self.state)
            
            system_row = build_system_row(net_state, sched, time.time())
            plots_rows = build_plots_rows(net_state, sched, time.time())
            
            if not system_row and not plots_rows:
                return  # Nothing to write
                
            requests = []
            
            if system_row:
                requests.append({
                    "range": f"'{config.SHEET_TAB_SYSTEM}'!A2:L2",
                    "values": [system_row]
                })
                
            if plots_rows:
                padded_plots = plots_rows[:]
                while len(padded_plots) < 20:
                    padded_plots.append([""] * 9)
                    
                requests.append({
                    "range": f"'{config.SHEET_TAB_PLOTS}'!A2:I21",
                    "values": padded_plots
                })
                
            if requests:
                self.sheet.values_batch_update({
                    "valueInputOption": "USER_ENTERED",
                    "data": requests
                })
                
        except Exception as e:
            ts = time.strftime("%H:%M:%S", time.localtime())
            print(f"[{ts}] [Sheets] Error pushing to sheets: {e}")
            time.sleep(5)


def start_sheets_uplink_thread(engine, state):
    thread = UplinkThread(engine, state)
    thread.start()
    return thread


def check_setup():
    if gspread is None:
        print("Error: gspread and/or google-auth are not installed.")
        sys.exit(1)
        
    print("Checking Google Sheets setup...")
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        creds = Credentials.from_service_account_file(config.SHEETS_CREDENTIALS_PATH, scopes=scopes)
        print("✓ Credentials file found and parsed.")
    except FileNotFoundError:
        print(f"✗ Credentials file '{config.SHEETS_CREDENTIALS_PATH}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Failed to parse credentials: {e}")
        sys.exit(1)
        
    try:
        client = gspread.authorize(creds)
        print("✓ Authenticated with Google.")
    except Exception as e:
        print(f"✗ Failed to authenticate: {e}")
        sys.exit(1)
        
    try:
        sheet = client.open_by_key(config.SHEETS_SPREADSHEET_ID)
        print("✓ Spreadsheet opened successfully.")
    except Exception as e:
        print(f"✗ Failed to open spreadsheet '{config.SHEETS_SPREADSHEET_ID}': {e}")
        sys.exit(1)
        
    expected_tabs = {config.SHEET_TAB_SYSTEM, config.SHEET_TAB_PLOTS, config.SHEET_TAB_MEASUREMENTS}
    actual_tabs = {ws.title for ws in sheet.worksheets()}
    
    missing = expected_tabs - actual_tabs
    if missing:
        print(f"✗ Missing expected tabs: {', '.join(missing)}")
        sys.exit(1)
        
    print("✓ All expected tabs are present.")
    print("\nSetup verification passed! No data was written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Sheets Uplink utilities")
    parser.add_argument("--check", action="store_true", help="Verify credentials and sheet setup")
    args = parser.parse_args()
    
    if args.check:
        check_setup()
    else:
        parser.print_help()
