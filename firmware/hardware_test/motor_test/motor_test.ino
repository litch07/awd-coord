// ---------- PIN MAP ----------
#define MOTOR_IN3   26
#define MOTOR_IN4   27

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- BARE MINIMUM L298N MOTOR DRIVER TEST (CHANNEL B) ---");

  // Setup Motor Pins
  pinMode(MOTOR_IN3, OUTPUT);
  pinMode(MOTOR_IN4, OUTPUT);
  
  // Ensure motor is OFF to start
  digitalWrite(MOTOR_IN3, LOW);
  digitalWrite(MOTOR_IN4, LOW);
  
  Serial.println("Starting test cycle in 3 seconds...");
  delay(3000);
}

void loop() {
  // 1. Turn Motor ON
  Serial.println("\n>>> MOTOR ON (IN3 HIGH, IN4 LOW) <<<");
  digitalWrite(MOTOR_IN3, HIGH);
  digitalWrite(MOTOR_IN4, LOW);
  
  // Let it run for 3 seconds
  delay(3000);

  // 2. Turn Motor OFF
  Serial.println(">>> MOTOR OFF <<<");
  digitalWrite(MOTOR_IN3, LOW);
  digitalWrite(MOTOR_IN4, LOW);
  
  // Wait 3 seconds before next cycle
  delay(3000);
}
