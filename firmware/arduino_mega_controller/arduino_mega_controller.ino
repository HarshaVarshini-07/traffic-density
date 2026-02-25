/*
 * ============================================================
 *  ARDUINO MEGA — Smart Traffic Signal Controller
 * ============================================================
 *  Role: Controls 4-lane traffic signals (Red, Yellow, Green).
 *        Receives density & emergency data from ESP32 via UART.
 *        Also supports local RFID-based emergency triggering.
 *
 *  Serial Protocol (from ESP32 via Serial1):
 *    DEN:c1,c2,c3,c4\n   — lane densities (vehicle counts)
 *    EMG:lane\n            — emergency on lane 1-4
 *    EMG:0\n               — cancel emergency
 *
 *  Pin Mapping:
 *    Lane 1: R=22, Y=23, G=24
 *    Lane 2: R=25, Y=26, G=27
 *    Lane 3: R=28, Y=29, G=30
 *    Lane 4: R=31, Y=32, G=33
 *    Status LED: 34 (Ready), 35 (Emergency Blink)
 *    Buzzer: 36
 *    ESP32 UART: Serial1 (TX1=18, RX1=19)
 *    RFID SPI: SS=53, SCK=52, MOSI=51, MISO=50
 * ============================================================
 */

#include <SPI.h>
#include <MFRC522.h>

// ─── PIN DEFINITIONS ────────────────────────────────────────

// Traffic Signal LEDs: [lane][R, Y, G]
const int LIGHT_PINS[4][3] = {
  {22, 23, 24},  // Lane 1: Red, Yellow, Green
  {25, 26, 27},  // Lane 2
  {28, 29, 30},  // Lane 3
  {31, 32, 33}   // Lane 4
};

const int LED_READY      = 34;
const int LED_EMERGENCY  = 35;
const int BUZZER_PIN     = 36;

// RFID
#define RFID_SS_PIN   53
#define RFID_RST_PIN  49

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);

// ─── TIMING CONSTANTS ───────────────────────────────────────

const unsigned long YELLOW_TIME      = 3000;   // 3 seconds
const unsigned long RED_ALL_TIME     = 1000;   // 1 second all-red safety
const unsigned long EMERGENCY_TIME   = 30000;  // 30 seconds
const unsigned long MIN_GREEN_TIME   = 5000;   // 5 seconds min
const unsigned long MAX_GREEN_TIME   = 30000;  // 30 seconds max
const unsigned long FALLBACK_TIMEOUT = 10000;  // 10s before round-robin fallback
const unsigned long RFID_COOLDOWN    = 2000;   // 2 seconds between RFID reads

// ─── REGISTERED RFID CARDS ──────────────────────────────────
// Format: {byte1, byte2, byte3, byte4} → lane number
// Add your emergency vehicle RFID UIDs here!
struct RFIDCard {
  byte uid[4];
  int lane;
};

const RFIDCard RFID_CARDS[] = {
  {{0xA1, 0xB2, 0xC3, 0xD4}, 1},  // Emergency vehicle → Lane 1
  {{0xE5, 0xF6, 0x07, 0x18}, 2},  // Emergency vehicle → Lane 2
  {{0x29, 0x3A, 0x4B, 0x5C}, 3},  // Emergency vehicle → Lane 3
  {{0x6D, 0x7E, 0x8F, 0x90}, 4},  // Emergency vehicle → Lane 4
};
const int NUM_RFID_CARDS = sizeof(RFID_CARDS) / sizeof(RFID_CARDS[0]);

// ─── STATE MACHINE ──────────────────────────────────────────

enum SystemState {
  STATE_NORMAL,
  STATE_EMERGENCY
};

enum SignalPhase {
  PHASE_GREEN,
  PHASE_YELLOW,
  PHASE_RED_ALL
};

SystemState   systemState    = STATE_NORMAL;
SignalPhase   signalPhase    = PHASE_GREEN;
int           currentLane    = 0;         // Active green lane (0-3)
int           emergencyLane  = -1;        // Emergency lane (0-3), -1 = none
unsigned long phaseStartTime = 0;
unsigned long greenDuration  = 10000;     // Default 10s green
unsigned long lastDataTime   = 0;         // Last density data received
unsigned long lastRfidCheck  = 0;
unsigned long emergencyStart = 0;

// Lane densities from camera system
int laneCounts[4] = {0, 0, 0, 0};

// ─── SETUP ──────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);   // USB debug
  Serial1.begin(115200);  // ESP32 UART (RX1=19, TX1=18)

  // Initialize traffic light pins
  for (int lane = 0; lane < 4; lane++) {
    for (int light = 0; light < 3; light++) {
      pinMode(LIGHT_PINS[lane][light], OUTPUT);
      digitalWrite(LIGHT_PINS[lane][light], LOW);
    }
  }

  // Status LEDs and Buzzer
  pinMode(LED_READY, OUTPUT);
  pinMode(LED_EMERGENCY, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_READY, HIGH);
  digitalWrite(LED_EMERGENCY, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  // RFID
  SPI.begin();
  rfid.PCD_Init();

  // Start with all red, then begin
  setAllRed();
  delay(1000);

  currentLane = 0;
  signalPhase = PHASE_GREEN;
  phaseStartTime = millis();
  greenDuration = MIN_GREEN_TIME;
  setGreen(currentLane);

  Serial.println("================================");
  Serial.println(" Arduino Mega Traffic Controller");
  Serial.println("================================");
  Serial.println("System ready. Waiting for ESP32 data...");
}

// ─── MAIN LOOP ──────────────────────────────────────────────

void loop() {
  // 1. Check for serial commands from ESP32
  checkSerial();

  // 2. Check RFID for local emergency
  checkRFID();

  // 3. Run state machine
  if (systemState == STATE_EMERGENCY) {
    handleEmergency();
  } else {
    handleNormal();
  }

  delay(10);
}

// ─── SERIAL COMMAND HANDLING ────────────────────────────────

void checkSerial() {
  while (Serial1.available()) {
    String line = Serial1.readStringUntil('\n');
    line.trim();

    if (line.startsWith("DEN:")) {
      parseDensity(line.substring(4));
    }
    else if (line.startsWith("EMG:")) {
      int lane = line.substring(4).toInt();
      if (lane >= 1 && lane <= 4) {
        triggerEmergency(lane - 1);  // Convert to 0-indexed
      }
      else if (lane == 0) {
        cancelEmergency();
      }
    }
  }

  // Also check USB serial for debugging
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.startsWith("DEN:")) {
      parseDensity(line.substring(4));
    }
    else if (line.startsWith("EMG:")) {
      int lane = line.substring(4).toInt();
      if (lane >= 1 && lane <= 4) {
        triggerEmergency(lane - 1);
      }
      else if (lane == 0) {
        cancelEmergency();
      }
    }
    else if (line == "STATUS") {
      printStatus();
    }
  }
}

void parseDensity(String data) {
  int values[4] = {0, 0, 0, 0};
  int idx = 0;
  int start = 0;

  for (unsigned int i = 0; i <= data.length() && idx < 4; i++) {
    if (i == data.length() || data.charAt(i) == ',') {
      values[idx] = data.substring(start, i).toInt();
      idx++;
      start = i + 1;
    }
  }

  for (int i = 0; i < 4; i++) {
    laneCounts[i] = constrain(values[i], 0, 255);
  }

  lastDataTime = millis();

  Serial.printf("Density: [%d, %d, %d, %d]\n",
                laneCounts[0], laneCounts[1], laneCounts[2], laneCounts[3]);
}

// ─── NORMAL MODE ────────────────────────────────────────────

void handleNormal() {
  unsigned long elapsed = millis() - phaseStartTime;

  switch (signalPhase) {
    case PHASE_GREEN:
      if (elapsed >= greenDuration) {
        // Transition to yellow
        signalPhase = PHASE_YELLOW;
        phaseStartTime = millis();
        setYellow(currentLane);
        Serial.printf("Lane %d: GREEN → YELLOW\n", currentLane + 1);
      }
      break;

    case PHASE_YELLOW:
      if (elapsed >= YELLOW_TIME) {
        // Transition to all-red safety
        signalPhase = PHASE_RED_ALL;
        phaseStartTime = millis();
        setAllRed();
        Serial.printf("Lane %d: YELLOW → ALL RED\n", currentLane + 1);
      }
      break;

    case PHASE_RED_ALL:
      if (elapsed >= RED_ALL_TIME) {
        // Switch to next lane
        selectNextLane();
        signalPhase = PHASE_GREEN;
        phaseStartTime = millis();
        calculateGreenTime();
        setGreen(currentLane);
        Serial.printf("Lane %d: GREEN (%lu ms)\n", currentLane + 1, greenDuration);
      }
      break;
  }
}

void selectNextLane() {
  bool hasData = (millis() - lastDataTime) < FALLBACK_TIMEOUT;

  if (hasData) {
    // Density-based: pick lane with highest count
    int maxCount = -1;
    int bestLane = (currentLane + 1) % 4;  // Default: next lane

    for (int i = 0; i < 4; i++) {
      int candidate = (currentLane + 1 + i) % 4;  // Start from next lane
      if (laneCounts[candidate] > maxCount) {
        maxCount = laneCounts[candidate];
        bestLane = candidate;
      }
    }

    // If all counts are zero, just go to next lane (round-robin)
    if (maxCount <= 0) {
      bestLane = (currentLane + 1) % 4;
    }

    currentLane = bestLane;
  } else {
    // Fallback: simple round-robin
    currentLane = (currentLane + 1) % 4;
    Serial.println("(Fallback: round-robin — no data from camera)");
  }
}

void calculateGreenTime() {
  // Dynamic green time: 2 seconds per vehicle, clamped to [5s, 30s]
  int count = laneCounts[currentLane];
  greenDuration = constrain((unsigned long)count * 2000, MIN_GREEN_TIME, MAX_GREEN_TIME);
}

// ─── EMERGENCY MODE ─────────────────────────────────────────

void triggerEmergency(int lane) {
  if (lane < 0 || lane > 3) return;

  systemState = STATE_EMERGENCY;
  emergencyLane = lane;
  emergencyStart = millis();

  // Force green on emergency lane, all others red
  setAllRed();
  setGreen(emergencyLane);

  // Alert
  digitalWrite(LED_EMERGENCY, HIGH);
  tone(BUZZER_PIN, 1000, 500);  // Short beep

  Serial.printf("🚨 EMERGENCY: Lane %d forced GREEN for %lu sec\n",
                emergencyLane + 1, EMERGENCY_TIME / 1000);

  // Send acknowledgment back to ESP32
  Serial1.printf("ACK:EMG:%d\n", emergencyLane + 1);
}

void cancelEmergency() {
  if (systemState == STATE_EMERGENCY) {
    Serial.println("Emergency cancelled.");
    resumeNormal();
  }
}

void handleEmergency() {
  unsigned long elapsed = millis() - emergencyStart;

  // Blink emergency LED
  if ((elapsed / 500) % 2 == 0) {
    digitalWrite(LED_EMERGENCY, HIGH);
  } else {
    digitalWrite(LED_EMERGENCY, LOW);
  }

  // Check timeout
  if (elapsed >= EMERGENCY_TIME) {
    Serial.println("Emergency timeout. Resuming normal operation.");
    resumeNormal();
  }
}

void resumeNormal() {
  systemState = STATE_NORMAL;
  emergencyLane = -1;

  digitalWrite(LED_EMERGENCY, LOW);
  noTone(BUZZER_PIN);

  // Start fresh: all red → then next green
  setAllRed();
  signalPhase = PHASE_RED_ALL;
  phaseStartTime = millis();

  Serial1.println("ACK:NORMAL");
}

// ─── RFID HANDLING ──────────────────────────────────────────

void checkRFID() {
  if (millis() - lastRfidCheck < RFID_COOLDOWN) return;
  lastRfidCheck = millis();

  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  // Read UID
  byte uid[4];
  for (int i = 0; i < 4; i++) {
    uid[i] = rfid.uid.uidByte[i];
  }

  Serial.printf("RFID scanned: %02X:%02X:%02X:%02X\n",
                uid[0], uid[1], uid[2], uid[3]);

  // Match against registered cards
  for (int c = 0; c < NUM_RFID_CARDS; c++) {
    bool match = true;
    for (int b = 0; b < 4; b++) {
      if (uid[b] != RFID_CARDS[c].uid[b]) {
        match = false;
        break;
      }
    }
    if (match) {
      Serial.printf("RFID match! Emergency → Lane %d\n", RFID_CARDS[c].lane);
      triggerEmergency(RFID_CARDS[c].lane - 1);  // Convert to 0-indexed
      break;
    }
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

// ─── LED CONTROL ────────────────────────────────────────────

void setAllRed() {
  for (int lane = 0; lane < 4; lane++) {
    digitalWrite(LIGHT_PINS[lane][0], HIGH);  // Red ON
    digitalWrite(LIGHT_PINS[lane][1], LOW);   // Yellow OFF
    digitalWrite(LIGHT_PINS[lane][2], LOW);   // Green OFF
  }
}

void setGreen(int lane) {
  // All others stay red (call setAllRed first if needed)
  digitalWrite(LIGHT_PINS[lane][0], LOW);   // Red OFF
  digitalWrite(LIGHT_PINS[lane][1], LOW);   // Yellow OFF
  digitalWrite(LIGHT_PINS[lane][2], HIGH);  // Green ON
}

void setYellow(int lane) {
  digitalWrite(LIGHT_PINS[lane][0], LOW);   // Red OFF
  digitalWrite(LIGHT_PINS[lane][1], HIGH);  // Yellow ON
  digitalWrite(LIGHT_PINS[lane][2], LOW);   // Green OFF
}

// ─── STATUS REPORT ──────────────────────────────────────────

void printStatus() {
  Serial.println("\n--- SYSTEM STATUS ---");
  Serial.printf("State: %s\n", systemState == STATE_EMERGENCY ? "EMERGENCY" : "NORMAL");
  Serial.printf("Phase: %s\n",
                signalPhase == PHASE_GREEN ? "GREEN" :
                signalPhase == PHASE_YELLOW ? "YELLOW" : "RED_ALL");
  Serial.printf("Current Lane: %d\n", currentLane + 1);
  Serial.printf("Densities: [%d, %d, %d, %d]\n",
                laneCounts[0], laneCounts[1], laneCounts[2], laneCounts[3]);
  Serial.printf("Green Duration: %lu ms\n", greenDuration);
  Serial.printf("Last Data: %lu ms ago\n", millis() - lastDataTime);

  if (systemState == STATE_EMERGENCY) {
    Serial.printf("Emergency Lane: %d\n", emergencyLane + 1);
    Serial.printf("Emergency Remaining: %lu ms\n",
                  EMERGENCY_TIME - (millis() - emergencyStart));
  }
  Serial.println("--------------------\n");
}
