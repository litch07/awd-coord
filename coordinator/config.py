"""All tunable / uncalibrated values live here. Nothing is guessed elsewhere."""

SERIAL_PORT = "COM10"         # CHANGE: Proxy's port, check Device Manager
BAUD = 115200

NODE_TIMEOUT_S = 6.0          # 3 missed 2 s heartbeats

# Verified conversions
ADC_MAX = 4095
DEPTH_MAX_CM = 20.0
STAGE_VEG_MAX = 1365
STAGE_FLOWER_MAX = 2730

# AWD threshold: irrigate when depth < 15 cm. Confirm with team.
IRRIGATE_BELOW_CM = 15.0
TARGET_DEPTH_CM = 18.0         # Stop irrigating before hitting absolute max (20.0) to avoid timeout
TARGET_SOIL_MOISTURE = 1500    # DEMO: if soil reading drops below 1500 (gets wet), stop the motor
MAX_IRRIGATION_S = 60          # UNKNOWN: per-plot timeout, needs calibration

# Stage logic: Keep water at 5cm (don't dry to 15cm) during flowering
SUSPEND_AWD_STAGES = ["FLOWERING"]
CRITICAL_STAGE_IRRIGATE_BELOW_CM = 5.0

# Rain threshold: Analog reading drops below this when rain is heavy
RAIN_WET_BELOW_RAW = 2000

# Priority weights, tune on the bench
W_DEPTH_DEFICIT = 1.0
W_WAIT_TIME = 0.5
W_EQUITY_PENALTY = 1.0

SHEETS_PUSH_INTERVAL_S = 5

# SMS Alerts
# Map node_ids to specific farmer phone numbers.
# Node 0 is the System Administrator (receives pump/system-wide faults).
FARMER_PHONES = {
    0: "+8801952724571", # System Admin
    1: "+8801686805636", # Farmer for Plot 1
    2: "+8801707236442", # Farmer for Plot 2
    3: "+8801647775578", # Farmer for Plot 3
    4: "+8801725758026", # Farmer for Plot 4
}

# Google Sheets Configuration
SHEETS_CREDENTIALS_PATH = "credentials.json"
SHEETS_SPREADSHEET_ID = "1HoiUuAfxN8kIdVCbGVNYUPz1p8fFHhN2B5vWP53avc0"
SHEET_TAB_SYSTEM = "system"
SHEET_TAB_PLOTS = "plots"
SHEET_TAB_MEASUREMENTS = "measurements"
# Scheduler: how long to wait for valveOpen confirmation before
# assuming the valve failed to open and aborting.
ARMING_TIMEOUT_S = 5.0         # UNKNOWN: needs calibration on real hardware

VALVE_SETTLE_S = 2.0           # UNKNOWN: servo travel time, needs calibration
WATER_CONFIRM_S = 30.0         # CHANGED FOR DEMO: 30s to detect water before aborting
PUMP_CONFIRM_S = 10.0          # UNKNOWN: needs calibration
RESELECT_COOLDOWN_S = 15.0     # CHANGED FOR DEMO: 15 second wait time before re-selecting
