/*
 * ============================================================
 *  ESP32 SENDER — Smart Traffic Management System
 * ============================================================
 *  Role: Connects to PC via USB Serial.
 *        Receives density & emergency commands from Python.
 *        Broadcasts data to the Receiver ESP32 via ESP-NOW.
 * 
 *  Serial Protocol (from Python):
 *    DEN:c1,c2,c3,c4\n   — lane densities
 *    EMG:lane\n            — emergency on lane (1-4)
 *    EMG:0\n               — cancel emergency
 * 
 *  Wiring:
 *    USB cable to PC — that's it!
 * ============================================================
 */

#include <esp_now.h>
#include <WiFi.h>

// ─── CONFIGURATION ──────────────────────────────────────────
// Replace with the MAC address of your RECEIVER ESP32.
// To find it, upload the "get_mac" sketch below to the receiver
// and read Serial Monitor.
uint8_t RECEIVER_MAC[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
// Example: {0x24, 0x6F, 0x28, 0xAA, 0xBB, 0xCC}

#define LED_PIN       2        // Built-in LED for status
#define SERIAL_BAUD   115200
#define MAX_MSG_LEN   64

// ─── DATA STRUCTURE ─────────────────────────────────────────
// Must match the receiver's struct exactly
typedef struct {
  char type;          // 'D' = density, 'E' = emergency
  uint8_t lane;       // emergency lane (1-4), or 0 for none
  uint8_t counts[4];  // vehicle counts per lane
} TrafficData;

TrafficData outgoing;

// ─── ESP-NOW CALLBACK ───────────────────────────────────────
bool lastSendSuccess = false;

void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  lastSendSuccess = (status == ESP_NOW_SEND_SUCCESS);
  if (lastSendSuccess) {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));  // Toggle LED
  }
}

// ─── SETUP ──────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Init WiFi in Station mode (required for ESP-NOW)
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  Serial.println("================================");
  Serial.println(" ESP32 SENDER — Smart Traffic");
  Serial.println("================================");
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());

  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("ERROR: ESP-NOW init failed!");
    return;
  }

  esp_now_register_send_cb(onDataSent);

  // Register receiver as peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, RECEIVER_MAC, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("ERROR: Failed to add peer!");
    return;
  }

  Serial.println("ESP-NOW initialized. Waiting for commands...");
  Serial.println("Receiver MAC set to: ");
  for (int i = 0; i < 6; i++) {
    Serial.printf("%02X", RECEIVER_MAC[i]);
    if (i < 5) Serial.print(":");
  }
  Serial.println();
}

// ─── PARSE & SEND ───────────────────────────────────────────
void parseDensity(String data) {
  // Format: "c1,c2,c3,c4"
  int values[4] = {0, 0, 0, 0};
  int idx = 0;
  int start = 0;

  for (int i = 0; i <= data.length() && idx < 4; i++) {
    if (i == data.length() || data.charAt(i) == ',') {
      values[idx] = data.substring(start, i).toInt();
      idx++;
      start = i + 1;
    }
  }

  outgoing.type = 'D';
  outgoing.lane = 0;
  for (int i = 0; i < 4; i++) {
    outgoing.counts[i] = constrain(values[i], 0, 255);
  }

  esp_err_t result = esp_now_send(RECEIVER_MAC, (uint8_t *)&outgoing, sizeof(outgoing));

  Serial.printf("TX DEN: [%d, %d, %d, %d] → %s\n",
                outgoing.counts[0], outgoing.counts[1],
                outgoing.counts[2], outgoing.counts[3],
                result == ESP_OK ? "OK" : "FAIL");
}

void parseEmergency(String data) {
  int lane = data.toInt();

  outgoing.type = 'E';
  outgoing.lane = constrain(lane, 0, 4);
  memset(outgoing.counts, 0, 4);

  esp_err_t result = esp_now_send(RECEIVER_MAC, (uint8_t *)&outgoing, sizeof(outgoing));

  Serial.printf("TX EMG: Lane %d → %s\n",
                outgoing.lane,
                result == ESP_OK ? "OK" : "FAIL");
}

// ─── MAIN LOOP ──────────────────────────────────────────────
void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.startsWith("DEN:")) {
      parseDensity(line.substring(4));
    }
    else if (line.startsWith("EMG:")) {
      parseEmergency(line.substring(4));
    }
    else if (line == "PING") {
      Serial.println("PONG");
    }
    else if (line.length() > 0) {
      Serial.println("ERR: Unknown command: " + line);
    }
  }
}

/*
 * ============================================================
 *  HELPER: Upload this to the RECEIVER ESP32 first to get
 *  its MAC address, then paste it into RECEIVER_MAC above.
 * ============================================================
 *
 *  #include <WiFi.h>
 *
 *  void setup() {
 *    Serial.begin(115200);
 *    WiFi.mode(WIFI_STA);
 *    Serial.println();
 *    Serial.print("Receiver MAC: ");
 *    Serial.println(WiFi.macAddress());
 *  }
 *
 *  void loop() {}
 *
 * ============================================================
 */
