#include <Servo.h>
#include <LiquidCrystal_I2C.h>

#define IR_SPOT1 2
#define IR_SPOT2 3
#define IR_SPOT3 4
#define IR_SPOT4 5
#define IR_ENTER 6
#define IR_EXIT 7

Servo gateServo;
LiquidCrystal_I2C lcd(0x27, 16, 2);
bool spotFree[4] = {true, true, true, true};
unsigned long lastGateTime = 0, gateDelay = 2000;

void setup() {
  Serial.begin(9600);
  gateServo.attach(9); gateServo.write(0);
  lcd.init(); lcd.backlight(); updateLCD();
  pinMode(IR_SPOT1, INPUT);
  pinMode(IR_SPOT2, INPUT);
  pinMode(IR_SPOT3, INPUT);
  pinMode(IR_SPOT4, INPUT);
  pinMode(IR_ENTER, INPUT);
  pinMode(IR_EXIT, INPUT);
}

void loop() {
  unsigned long now = millis();
  if (now - lastGateTime >= gateDelay) {
    if (digitalRead(IR_ENTER) == HIGH && anySpotAvailable()) {
      lastGateTime = now;
      openGate();
      claimFirstFreeSpot();
      updateLCD();
    } else if (digitalRead(IR_EXIT) == HIGH) {
      lastGateTime = now;
      openGate();
      detectFreedSpots();
      updateLCD();
    }
  }
  handleSerialCommands();
}

void openGate() {
  gateServo.write(90);
  delay(1000);
  gateServo.write(0);
}

bool anySpotAvailable() {
  for (int i = 0; i < 4; i++) if (spotFree[i]) return true;
  return false;
}

void claimFirstFreeSpot() {
  for (int i = 0; i < 4; i++) {
    if (spotFree[i]) { spotFree[i] = false; break; }
  }
}

void detectFreedSpots() {
  if (digitalRead(IR_SPOT1) == LOW) spotFree[0] = true;
  if (digitalRead(IR_SPOT2) == LOW) spotFree[1] = true;
  if (digitalRead(IR_SPOT3) == LOW) spotFree[2] = true;
  if (digitalRead(IR_SPOT4) == LOW) spotFree[3] = true;
}

void updateLCD() {
  lcd.clear(); lcd.print("Free spots:");
  for (int i = 0; i < 4; i++) {
    lcd.setCursor(i*4, 1);
    lcd.print(spotFree[i] ? String(i+1) : "X");
  }
}

void handleSerialCommands() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd == "STATUS") {
    for (int i = 0; i < 4; i++) {
      Serial.print("SPOT"); Serial.print(i+1);
      Serial.print(":"); Serial.println(spotFree[i] ? "FREE" : "RESERVED");
    }
  }
}
