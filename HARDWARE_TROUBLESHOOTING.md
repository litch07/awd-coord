# AWD-COORD Hardware Troubleshooting Guide

This document captures real-world hardware issues encountered during the physical integration of the AWD-COORD system, along with their verified solutions. 

If you or a teammate encounter strange behavior (like the Python script crashing, firmware failing to flash, or motors behaving erratically), check this guide first.

---

## 1. Python Coordinator Crashes (`[!] Serial link lost. Exiting.`)

**The Symptom:**
The Python script runs perfectly in `[DRY-RUN]` mode, but crashes almost instantly with a `Serial link lost` error when running in `--live` mode (usually right when it decides to water a plot).

**The Cause (Power Brownout):**
This is a physical hardware power issue, not a software bug. When the coordinator enters `--live` mode, it transmits a radio command. If the Field Node receives the command and attempts to move the **Servo Motor**, the servo draws a massive, instantaneous spike of current. 
If your **Proxy Board** (plugged into the laptop) and your **Field Nodes** or **Pump Node** are sharing the same power supply (e.g., the same USB hub or laptop), the servo or pump will steal all the electricity. This causes the USB voltage to drop (a brownout), Windows instantly disconnects the USB port to protect the laptop, and Python crashes because `COM10` suddenly vanished.

**The Fix:**
- **Separate the Power Supplies:** Plug the Proxy board into your laptop (so Python can read it). Plug the Field Nodes and Pump Node into a completely separate power source (like a phone wall charger or a portable USB power bank). 

---

## 2. Firmware Fails to Flash (`Unable to verify flash chip connection`)

**The Symptom:**
When trying to upload code via the Arduino IDE, the console gets to `Changing baud rate to 921600...` and then crashes with `A fatal error occurred: Unable to verify flash chip connection`.

**The Cause:**
When the ESP32 resets to accept new code, its pins temporarily float. Heavy peripherals (like Motor Drivers or Servos) can get confused and draw excessive power during this split-second window, starving the ESP32 of the voltage it needs to write to its flash memory.

**The Fix:**
- **Isolate the Power:** Temporarily unplug the `VIN` or `5V` wire going to your heavy peripherals (e.g., unplug the wire going into the INA219, or going to the motor driver). 
- Click Upload. Once it says "Done Uploading", plug the power wire back in.

---

## 3. Motor Will Not Turn Off (L9110S Driver Damage)

**The Symptom:**
The OLED screen says `PUMP: OFF`, and the firmware is sending `LOW/LOW` to the motor pins, but the motor continues to spin indefinitely.

**The Cause:**
If the L9110S motor driver previously suffered an over-voltage event (e.g., Channel A burned out), the internal silicon is physically compromised. The transistor responsible for turning Channel B off is likely partially melted (shorted closed) and leaking voltage even when the ESP32 commands it to stop.

**The Fix:**
- **Long-term Fix (Implemented):** We have replaced the damaged L9110S driver board with a more robust **L298N Motor Driver**.
- **Firmware Reversion:** Because the L298N functions correctly, the firmware logic for turning the pump off has been reverted to the standard `LOW/LOW` method. 
- *(Legacy Note: The previous workaround for the damaged L9110S was to send `HIGH/HIGH` to act as an electronic brake, which caused high resting current and voltage sag. This is no longer necessary with the new driver).*

*(Note: If you are using a generic blue Relay Module instead of a motor driver, the relay is likely "Active-Low", meaning sending `LOW` turns it ON. You must invert the logic to `HIGH` to turn it OFF).*

---

## 4. I2C Devices Not Found (OLED / INA219)

**The Symptom:**
The OLED screen doesn't turn on, and the Serial Monitor prints `ERROR: OLED not found!` or `ERROR: INA219 not found!`.

**The Cause:**
The standard hardware I2C pins on the ESP32 are strictly defined, but easily confused.
- **GPIO 21** = SDA (Data)
- **GPIO 22** = SCL / SCK (Clock)
Wiring these backwards will result in a completely dead I2C bus.

**The Fix:**
- Ensure all `SDA` pins from the sensors are connected to **Pin 21**.
- Ensure all `SCL` or `SCK` pins are connected to **Pin 22**.
