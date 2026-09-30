# AWD-COORD: Final Demonstration Guide

This document is your master script for presenting the AWD-COORD system. Follow this step-by-step to ensure a flawless demonstration and guarantee top marks from the faculty.

---

## Part 1: Pre-Demonstration Checklist (Do This First)

1. **New SIM800L Hardware Test**
   - Buy the new SIM800L module.
   - Wire it to your ESP32 (VCC to 4.40V, GND to Common GND, TX to RX2/16, RX to TX2/17).
   - Flash `firmware/hardware_test/sim800l_test/sim800l_test.ino` and verify you get `+CREG: 0,1` (registered) in the Serial Monitor.
2. **Flash All Firmwares**
   - Because the Shadow MAC was recently updated, you **must re-flash every single ESP32**.
   - Flash Field Nodes 1, 2, 3, 4.
   - Flash the Pump Node.
   - Flash the Coordinator Proxy (this includes the new SIM800L logic).
   - Flash the Shadow Coordinator.
3. **Verify Grounds**
   - Ensure the 4.40V PSU, SIM800L, L298N motor driver, servos, and all ESP32s share a **Common Ground**.

---

## Part 2: The Live Demonstration Script

When it's time to present, follow this exact sequence:

### Step 1: The Boot Up
1. Power up all the Field Nodes and the Pump Node.
2. Plug the **Coordinator Proxy** into your laptop via USB. 
3. Open your terminal in the project folder and type: `python -m coordinator.main --live`
4. **What to say:** *"The system is now booting. The ESP32 Coordinator Proxy is forming a secure ESP-NOW wireless mesh network with the field nodes and bridging that data to our Python brain over USB."*

### Step 2: The Cloud & Dashboard
1. Open `website/dashboard.html` in your browser. Show the premium UI.
2. Open your Google Sheets on the projector.
3. **What to say:** *"Our system isn't just local. The Python backend streams live telemetry (water depth, soil moisture, voltage) to Google Sheets every 5 seconds, providing a permanent historical record for agricultural analysis."*

### Step 3: Hardware Power & Telemetry (INA219)
1. Point to the INA219 module on the Pump Node.
2. Show the terminal or Google Sheets capturing real-time Voltage, Current (mA), and Power (mW).
3. **What to say:** *"To ensure the battery doesn't die and the motor doesn't stall, the system uses an INA219 sensor to monitor the exact power consumption of the water pump in real-time."*

### Step 4: Growth Stage Adjustment
1. Twist the potentiometer on a Field Node.
2. Explain that you are changing the rice's current growth stage to "FLOWERING".
3. **What to say:** *"Rice shouldn't be dried out during the flowering stage. By twisting this dial, the Python brain instantly detects the new growth stage and automatically adjusts the AWD irrigation threshold from 15cm up to 5cm to protect the yield."*

### Step 5: System-Wide Rain Detection
1. Drop some water on the Rain Sensor connected to the Pump Node (or bridge the contacts).
2. **What to say:** *"Nature is doing the watering for us. The rain sensor just triggered, and the Python scheduler instantly suspended all active irrigation across all fields to save electricity."*

### Step 6: The "Farmer Override" & Multi-Tenant SMS
1. Press the physical button on **Field Node 2**.
2. Point out that the servo valve physically opens.
3. Show your phone (or the terminal) receiving the SMS alert.
4. **What to say:** *"If a farmer manually overrides the system in the field, the Python brain instantly detects it, suspends the automated schedule for that plot, and routes an SMS alert ONLY to Farmer 2's phone number. The system supports multi-tenant mapping."*

### Step 7: Hardware Fault Button
1. Press the physical fault button (GPIO 25) on the Pump Node.
2. **What to say:** *"If the pump physically jams or overheats in the field, pressing the fault button immediately kills the motor in hardware, and dispatches a system-wide SMS alert to the System Administrator so it can be repaired."*

### Step 8: The "Mic-Drop" Shadow Failover
1. Explain the danger of IoT systems: *"What happens if the main PC crashes or loses power while the 12V water pump is running? Normally, the field floods."*
2. **Physically unplug the USB cable** of the Coordinator Proxy from your laptop.
3. Wait 3 seconds. Point to the **Shadow Coordinator** as its LED starts blinking and the Pump turns off.
4. **What to say:** *"We engineered a Shadow Failover system. This independent ESP32 constantly listens to the network heartbeat. When I unplugged the main server, the Shadow realized it was dead within 3 seconds, and immediately broadcasted an emergency shutdown command to kill the pump and close all valves."*

---

## Part 3: The "Wow" Factors (Mention these to the Faculty)

To prove the engineering rigor of this project, make sure you casually mention these Advanced (Phase 3) features during Q&A:

1. **Mechanical Safety Latency (Industrial Grade)**
   - Explain that the code doesn't just "turn on a pump." It waits 2 seconds for valves to physically open (`VALVE_SETTLE_S`), and waits 30 seconds to verify actual water flow in the pipe (`WATER_CONFIRM_S`). If water isn't detected, it aborts to prevent burning out the pump motor.
2. **Growth-Stage AWD Suspension**
   - Explain that AWD drying is dangerous during the rice **Flowering** stage. Show them how the system reads the stage potentiometer, and automatically overrides the 15cm AWD rule to keep the water at 5cm during flowering, protecting the crop yield.
3. **System-Wide Rain Detection**
   - Explain that the Pump Node has a rain sensor. If heavy rain is detected, the Python brain intelligently suspends all irrigation across all 4 fields to save electricity.
4. **Equity Scheduling Algorithm**
   - Explain that if two fields dry out at the exact same time, the Python brain calculates the historical total seconds each field has been watered, and prioritizes the field that has received less water over the lifespan of the crop.

---

## Part 4: Common Q&A (Defense Preparation)

If the faculty starts grilling you on how it all works under the hood, use these answers:

**Q: How exactly does the website/dashboard get the data?**
> *"The website does not talk directly to the ESP32s. Our Python Coordinator (running on a laptop/Raspberry Pi) acts as a gateway. It takes the raw ESP-NOW data from the proxy, formats it, and securely POSTs it directly to Google Sheets using the Google Cloud API via a Service Account. The dashboard then pulls from that Google Sheet, making it globally accessible."*

**Q: Why use ESP-NOW instead of standard Wi-Fi for the field nodes?**
> *"Wi-Fi requires a central router, which is impractical in the middle of a large rice paddy. ESP-NOW is a connectionless, peer-to-peer protocol. It allows our nodes to talk directly to each other without a router, uses significantly less battery power, and has much lower latency."*

**Q: How does the Shadow Failover actually know when to take over?**
> *"The primary Coordinator Proxy broadcasts a `ShadowSyncPacket` over ESP-NOW every 1000 milliseconds. The Shadow Coordinator does nothing but listen for that heartbeat. If 3000 milliseconds (3 seconds) pass in total silence, the Shadow determines a catastrophic failure has occurred on the primary, and it immediately broadcasts a hardware-level override to shut down the pump and close all valves."*

**Q: What happens if a field node loses power or dies?**
> *"The Python brain tracks the uptime and heartbeat of every single node. If a node misses 3 heartbeats (6 seconds), the system marks it as `offline`, aborts any active irrigation for that specific plot, and sends an SMS alert to that farmer."*

**Q: What if multiple fields need water at the exact same time, but there is only one pump?**
> *"The Python scheduler implements a Priority Scoring Algorithm. It calculates the 'depth deficit' and the 'wait time' of every dry field. It also applies an Equity Penalty—subtracting points if a field has historically hogged the pump. The field with the highest mathematical score wins the pump lock."*

**Q: Why use a Python backend instead of putting all the logic on the Coordinator ESP32?**
> *"Separation of concerns. The ESP32 is perfect for low-latency hardware control and wireless ESP-NOW bridging. However, Python allows for vastly more complex scheduling algorithms, dynamic Google Sheets API integration, and easier multi-tenant data routing without having to recompile massive C++ state machines."*

**Q: How does the system handle sensor noise or faulty ultrasonic readings?**
> *"We implemented software debouncing and averaging at the firmware level. For example, the Field Nodes take multiple ultrasonic pings and discard anomalies before packaging the payload. Additionally, the Python backend uses time-based settling delays (e.g., `WATER_CONFIRM_S`) so it doesn't overreact to a single faulty reading."*

**Q: What happens if the SIM800L module loses cellular signal or breaks?**
> *"The SIM800L is a non-blocking peripheral. The core irrigation scheduling on the PC, and the hardware failover on the Shadow Coordinator, are completely independent. If cellular service drops, the SMS alerts will fail, but the water valves and pump will continue to operate and shut down safely."*

**Q: How scalable is this system? What if we add 50 more fields?**
> *"The architecture is highly decoupled. Field Nodes simply broadcast their state and don't care about the backend logic. The Python scheduler dynamically maps any new node ID that appears on the serial bus. While standard ESP-NOW supports 20 encrypted peers natively, by utilizing a broadcast topology, the system can scale massively without changing the codebase."*

**Q: Is this system actually "worthy"? What real-world problem is it solving?**
> *"Traditional rice farming requires continuous flooding, which wastes massive amounts of freshwater and generates heavy methane emissions. Alternate Wetting and Drying (AWD) saves up to 30% of water and reduces methane, but it requires extreme manual labor to constantly check pipes and soil depths. Our system completely automates the AWD labor constraint, making sustainable rice farming financially viable at a commercial scale."*

**Q: Will this actually work at the field level? ESP-NOW range is limited, isn't it?**
> *"You are correct that standard ESP32 ESP-NOW is limited to about 200-400 meters line-of-sight. However, our architecture is built in layers. Because the Python Coordinator and the wireless proxy are decoupled, we could easily swap the ESP32 wireless layer for LoRa (Long Range) modules like the SX1276. That would instantly extend our field coverage to over 10 kilometers without changing a single line of our Python scheduling logic!"*
**Q: Why are you using potentiometers (dials) instead of actual sensors for depth and crop stage?**
> *"This system is a scaled-down prototype designed to prove the software architecture, the wireless mesh reliability, and the failover safety loops. Real agricultural sensors (like industrial pressure transducers) are highly expensive. By using potentiometers, we can rapidly simulate weeks of environmental changes—like an entire 4-month crop cycle or a sudden drought—in a 5-minute demonstration to prove the Python brain reacts perfectly to every edge case."*

**Q: In a real commercial deployment, how would "Crop Stage" actually be measured instead of using a dial?**
> *"In a production environment, the 'Stage' input wouldn't be a physical dial in the field at all. The Python backend would calculate it automatically based on a calendar schedule (since rice growth stages are predictably tied to the planting date), or it could integrate with an API to pull NDVI (Normalized Difference Vegetation Index) satellite or drone imagery to dynamically update the crop stage."*

**Q: The depth measurement feels 'improper' or simulated. How does this work in reality?**
> *"AWD (Alternate Wetting and Drying) relies on measuring the perched water table below the soil surface. Our design utilizes a perforated PVC pipe driven into the soil as a 'stilling well.' The ultrasonic sensor sits at the top of the pipe, measuring the exact distance down to the water level inside the pipe. This provides millimeter-accurate depth readings, which is exactly the metric recommended by the International Rice Research Institute (IRRI) for AWD."*

**Q: How exactly is the messaging handled? How does it know who to text?**
> *"The Python backend uses a multi-tenant configuration map. When a fault occurs (like a broken pipe), Python identifies the exact physical Node ID. It maps that Node ID to the specific phone number of the farmer who owns that plot, dynamically constructs an AT command payload, and sends it to the SIM800L. The Admin gets pump alerts, while individual farmers only get alerts for their specific fields."*

**Q: Why use SMS messaging instead of an internet dashboard alert or a Smartphone App?**
> *"In rural agriculture, 4G internet coverage is often unreliable, and many farmers still use basic feature phones rather than smartphones. SMS runs on the 2G GSM network, which has the widest rural penetration globally and works on any $10 device. SMS is the most inclusive, immediate, and reliable way to reach a farmer during a hardware emergency."*
