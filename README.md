<div align="center">
  <img src="website/assets/img/uiu.webp" alt="UIU Logo" width="100">

  <h1>AWD-COORD System</h1>
  <p><strong>Autonomous Multi-Node Alternate Wetting and Drying (AWD) Irrigation Coordinator</strong></p>
  
  <p>
    An intelligent, IoT-based water management system designed to optimize irrigation for rice fields. By enforcing AWD agronomy logic, this system allows multiple farmers to autonomously share a single pump, preventing conflicts and saving 25-50% of agricultural water.
  </p>

  <p>
    <em>Microprocessors and Microcontrollers Laboratory Project</em><br>
    <strong>Team PhaseShift | United International University</strong>
  </p>
</div>

---

## 🌟 System Overview

The **AWD-COORD** system spans embedded hardware, a backend control daemon, and a premium frontend telemetry dashboard. 

It uses RF communication (nRF24L01 / ESP-NOW) to collect live soil and water depth telemetry from distributed agricultural field nodes, coordinates pump access fairly via a Priority Scheduling State Machine, and pushes live updates to a Google Sheets-backed cloud API for public dashboard visualization.

### Key Capabilities
- **AWD Agronomy Logic**: Prevents overwatering by dynamically switching between vegetative and flowering water thresholds.
- **Fair Pump Sharing**: Enforces priority queues so neighboring farmers don't conflict over a single water source.
- **Hardware Watchdogs & Fault Detection**: Detects jammed valves, dry pumps, and broken pipes using safety timeouts and flow confirmation.
- **Manual Overrides**: Physical switch integration for farmers to temporarily bypass automation safely.
- **Live Telemetry**: Real-time visualization of network health, pump status, and water usage via an elegant web frontend.

---

## 📂 Repository Structure

The repository contains the complete end-to-end stack:

```text
📁 awd-coord/
├── 📁 coordinator/   # Python backend (Runs on Master Laptop/Raspberry Pi)
│   ├── main.py       # Core entry point
│   ├── scheduler.py  # AWD logic & priority queues
│   ├── serial_link.py# USB Serial parsing from the proxy
│   └── sheets_uplink.py # Live telemetry syncing
├── 📁 firmware/      # C++/Arduino code for the Microcontrollers
│   ├── coordinator_proxy/ # Node connected via USB to the Master PC
│   ├── field_nodes/  # Edge nodes in the rice plots (Water depth & soil sensors)
│   └── pump_node/    # Controller for the main water pump relay
├── 📁 website/       # HTML/CSS/JS Live Web Dashboard
│   ├── index.html    # Landing & Project Info
│   ├── dashboard.html# Live Telemetry View
│   └── 📁 docs/      # Contains downloadable PDF project documentation
└── 📁 docs/          # Technical specifications
    └── SERIAL_PROTOCOL.md
```

---

## 🚀 Setup & Execution

### 1. Hardware & Firmware
Ensure all ESP32/Arduino microcontrollers are flashed with their respective sketches located in the `/firmware/` directory. The **Coordinator Proxy** node must be physically plugged into the USB port of the master control machine.

### 2. Running the Python Coordinator
The backend orchestrates the state machine and bridges the local serial network to the cloud.

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the coordinator:
   ```bash
   python -m coordinator.main --live
   ```

### 3. Viewing the Dashboard
The frontend is completely static and dependency-free.
To view the dashboard, simply serve the `/website/` directory locally:
```bash
cd website
python -m http.server 8080
```
Navigate to `http://localhost:8080` in your browser to view the premium dashboard.

---

## 👥 Development Team
Developed by **Team PhaseShift**  
Department of Computer Science & Engineering, **United International University (UIU)**

- **Mostafizur Rahman** (ID: 112330844)
- **Fahad Parvez Sagor** (ID: 112330829)
- **Saikat Raihan** (ID: 112230611)
- **M.M.Sayem Prodhan** (ID: 112330411)
- **Sadid Ahmed** (ID: 112330154)

---
<div align="center">
  <p><em>Empowering Next-Gen Agriculture through smart, autonomous resource sharing.</em></p>
</div>
