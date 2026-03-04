/*
 * ============================================================
 *  ESP32 RECEIVER — Smart Traffic Management System
 * ============================================================
 *  Role: Receives ESP-NOW data from the Sender ESP32.
 *        Forwards commands to the Arduino Mega via UART.
 *
 *  Wiring to Arduino Mega:
 *    ESP32 TX2 (GPIO 17) → Mega RX1 (Pin 19)
 *    ESP32 RX2 (GPIO 16) → Mega TX1 (Pin 18) [via level shifter 5V→3.3V]
 *    ESP32 GND           → Mega GND
 *
 *  UART Protocol (to Mega):
 *    DEN:c1,c2,c3,c4\n   — lane vehicle counts
 *    EMG:lane\n            — emergency on lane (1-4)
 *    EMG:0\n               — cancel emergency
 *    SIG:s1,s2,s3,s4\n    — signal states (R/Y/G per lane)
 * ============================================================
 */

#include <esp_now.h>
#include <WiFi.h>

#define LED_PIN       2        // Built-in LED for status
#define SERIAL_BAUD   115200
#define MEGA_SERIAL   Serial2  // TX2=GPIO17, RX2=GPIO16

// ─── DATA STRUCTURE ─────────────────────────────────────────
// Must match the sender's struct exactly
typedef struct {
  char type;          // 'D' = density, 'E' = emergency, 'S' = signal states
  uint8_t lane;       // emergency lane (1-4), or 0 for none
  uint8_t counts[4];  // vehicle counts per lane
  char states[4];     // signal states: 'R', 'Y', 'G' per lane
} TrafficData;

TrafficData incoming;

// ─── TIMING ─────────────────────────────────────────────────
unsigned long lastReceiveTime = 0;
unsigned long receiveCount = 0;

// ─── ESP-NOW CALLBACK ───────────────────────────────────────
void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(TrafficData)) {
    Serial.printf("WARN: Unexpected data size: %d (expected %d)\n", len, sizeof(TrafficData));
    return;
  }

  memcpy(&incoming, data, sizeof(incoming));
  lastReceiveTime = millis();
  receiveCount++;

  // Blink LED
  digitalWrite(LED_PIN, !digitalRead(LED_PIN));

  if (incoming.type == 'D') {
    // Forward density to Mega
    String cmd = "DEN:" + String(incoming.counts[0]) + ","
                        + String(incoming.counts[1]) + ","
                        + String(incoming.counts[2]) + ","
                        + String(incoming.counts[3]);
    MEGA_SERIAL.println(cmd);
    Serial.println("RX→Mega: " + cmd);
  }
  else if (incoming.type == 'E') {
    // Forward emergency to Mega
    String cmd = "EMG:" + String(incoming.lane);
    MEGA_SERIAL.println(cmd);
    Serial.println("RX->Mega: " + cmd);
  }
  else if (incoming.type == 'S') {
    // Forward signal states to Mega
    String cmd = "SIG:" + String(incoming.states[0]) + ","
                        + String(incoming.states[1]) + ","
                        + String(incoming.states[2]) + ","
                        + String(incoming.states[3]);
    MEGA_SERIAL.println(cmd);
    Serial.println("RX->Mega: " + cmd);
  }
  else {
    Serial.printf("WARN: Unknown type '%c'\n", incoming.type);
  }
}

// ─── SETUP ──────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);         // USB debug monitor
  MEGA_SERIAL.begin(SERIAL_BAUD);    // UART to Arduino Mega
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  Serial.println("================================");
  Serial.println(" ESP32 RECEIVER — Smart Traffic");
  Serial.println("================================");
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
  Serial.println("(Use this MAC in the sender's RECEIVER_MAC)");

  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("ERROR: ESP-NOW init failed!");
    return;
  }

  esp_now_register_recv_cb(onDataRecv);

  Serial.println("ESP-NOW initialized. Listening for data...");
}

// ─── MAIN LOOP ──────────────────────────────────────────────
void loop() {
  // Heartbeat: print stats every 10 seconds
  static unsigned long lastStatsTime = 0;
  if (millis() - lastStatsTime > 10000) {
    lastStatsTime = millis();

    unsigned long sinceLast = (lastReceiveTime > 0) ? (millis() - lastReceiveTime) : 0;
    Serial.printf("--- Stats: %lu msgs received | Last: %lu ms ago ---\n",
                  receiveCount, sinceLast);

    // If no data for 30s, warn
    if (lastReceiveTime > 0 && sinceLast > 30000) {
      Serial.println("WARNING: No data from sender for 30+ seconds!");
    }
  }

  // Forward any response from Mega back to debug serial
  while (MEGA_SERIAL.available()) {
    String megaMsg = MEGA_SERIAL.readStringUntil('\n');
    megaMsg.trim();
    if (megaMsg.length() > 0) {
      Serial.println("Mega→: " + megaMsg);
    }
  }

  delay(10);
}
