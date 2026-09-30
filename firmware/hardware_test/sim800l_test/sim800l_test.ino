/*
  SIM800L Serial Passthrough & Diagnostic Test
  ============================================
  This sketch bridges the USB Serial Monitor to HardwareSerial 2 on the ESP32.
  It allows you to type AT commands directly into the Serial Monitor to test
  the SIM800L module manually.
  
  WIRING:
  - SIM800L TXD -> ESP32 GPIO 16 (RX2)
  - SIM800L RXD -> ESP32 GPIO 17 (TX2)
  - SIM800L GND -> ESP32 GND (Must be shared with 4.40V PSU GND)
*/

#define SIM800L_RX 16 // ESP32 RX2
#define SIM800L_TX 17 // ESP32 TX2

HardwareSerial sim800l(2);

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // Initialize communication with the SIM800L at 9600 baud 
  // (9600 is the most common default for SIM800L modules)
  sim800l.begin(9600, SERIAL_8N1, SIM800L_RX, SIM800L_TX);
  
  Serial.println("\n============================================");
  Serial.println("     SIM800L AT Command Passthrough         ");
  Serial.println("============================================");
  Serial.println("Initialization sequence sending...");
  
  // Send a basic AT command to see if it responds 
  sim800l.println("AT");
  delay(500);
  
  Serial.println("Ready! Type AT commands in the Serial Monitor.");
  Serial.println("(Make sure your Serial Monitor is set to 'Both NL & CR')\n");
}

void loop() {
  // Read from SIM800L and send to PC
  while (sim800l.available()) {
    Serial.write(sim800l.read());
  }
  
  // Read from PC and send to SIM800L
  while (Serial.available()) {
    sim800l.write(Serial.read());
  }
}
