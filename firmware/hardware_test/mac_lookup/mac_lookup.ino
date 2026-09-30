#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  
  // Wait for serial monitor to connect
  delay(2000);
  
  // Put ESP32 into Station mode to read the primary MAC address
  WiFi.mode(WIFI_STA);
  
  Serial.println("\n=========================================");
  Serial.println("       ESP32 MAC Address Lookup          ");
  Serial.println("=========================================");
  
  // Print standard string format
  Serial.print("Raw MAC Address: ");
  Serial.println(WiFi.macAddress());
  
  // Print formatted specifically for mac_config.h
  uint8_t mac[6];
  WiFi.macAddress(mac);
  Serial.println("\nCopy and paste this into common/mac_config.h:");
  Serial.printf("{0x%02X, 0x%02X, 0x%02X, 0x%02X, 0x%02X, 0x%02X}\n", 
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  Serial.println("=========================================\n");
}

void loop() {
  // Nothing to do
  delay(1000);
}
