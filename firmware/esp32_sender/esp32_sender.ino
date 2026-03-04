/*
 * ESP32 SENDER — Smart Traffic System
 * Receives commands from PC via USB, forwards via ESP-NOW.
 * USB Baud: 115200 | Struct: 10 bytes
 */
#include <esp_now.h>
#include <WiFi.h>

// Receiver MAC address
uint8_t RECEIVER_MAC[] = {0x80, 0xF3, 0xDA, 0x63, 0x3F, 0xA0};

#define LED_PIN 2

// Must match receiver struct EXACTLY
typedef struct {
  char type;          // 'D','E','S'
  uint8_t lane;       // emergency lane 1-4, 0=none
  uint8_t counts[4];  // vehicle counts
  char states[4];     // signal R/Y/G
} TrafficData;        // = 10 bytes

TrafficData outgoing;
bool lastSendOK = false;

void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  lastSendOK = (status == ESP_NOW_SEND_SUCCESS);
  if (lastSendOK) digitalWrite(LED_PIN, !digitalRead(LED_PIN));
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  Serial.println("================================");
  Serial.println(" ESP32 SENDER — Smart Traffic");
  Serial.println("================================");
  Serial.print("MAC: ");
  Serial.println(WiFi.macAddress());

  if (esp_now_init() != ESP_OK) {
    Serial.println("ERROR: ESP-NOW init failed!");
    return;
  }
  esp_now_register_send_cb(onDataSent);

  esp_now_peer_info_t peer;
  memset(&peer, 0, sizeof(peer));
  memcpy(peer.peer_addr, RECEIVER_MAC, 6);
  peer.channel = 0;
  peer.encrypt = false;

  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println("ERROR: Add peer failed!");
  }

  Serial.print("Receiver MAC: ");
  for (int i = 0; i < 6; i++) {
    if (RECEIVER_MAC[i] < 0x10) Serial.print("0");
    Serial.print(RECEIVER_MAC[i], HEX);
    if (i < 5) Serial.print(":");
  }
  Serial.println("\nReady!");
}

void sendData() {
  esp_err_t r = esp_now_send(RECEIVER_MAC, (uint8_t *)&outgoing, sizeof(outgoing));
  Serial.print(r == ESP_OK ? "OK" : "FAIL");
  Serial.println();
}

void loop() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  if (line.startsWith("SIG:")) {
    // Parse "R,G,R,R"
    String d = line.substring(4);
    outgoing.type = 'S';
    outgoing.lane = 0;
    memset(outgoing.counts, 0, 4);
    int idx = 0;
    for (unsigned int i = 0; i < d.length() && idx < 4; i++) {
      char c = d.charAt(i);
      if (c == 'R' || c == 'G' || c == 'Y') {
        outgoing.states[idx++] = c;
        while (i + 1 < d.length() && d.charAt(i + 1) != ',') i++;
      }
    }
    while (idx < 4) outgoing.states[idx++] = 'R';
    Serial.printf("TX SIG [%c,%c,%c,%c] ", outgoing.states[0], outgoing.states[1], outgoing.states[2], outgoing.states[3]);
    sendData();
  }
  else if (line.startsWith("DEN:")) {
    String d = line.substring(4);
    outgoing.type = 'D';
    outgoing.lane = 0;
    memset(outgoing.states, 0, 4);
    int idx = 0, start = 0;
    for (unsigned int i = 0; i <= d.length() && idx < 4; i++) {
      if (i == d.length() || d.charAt(i) == ',') {
        outgoing.counts[idx++] = d.substring(start, i).toInt();
        start = i + 1;
      }
    }
    Serial.printf("TX DEN [%d,%d,%d,%d] ", outgoing.counts[0], outgoing.counts[1], outgoing.counts[2], outgoing.counts[3]);
    sendData();
  }
  else if (line.startsWith("EMG:")) {
    outgoing.type = 'E';
    outgoing.lane = line.substring(4).toInt();
    memset(outgoing.counts, 0, 4);
    memset(outgoing.states, 0, 4);
    Serial.printf("TX EMG lane=%d ", outgoing.lane);
    sendData();
  }
  else if (line == "PING") {
    Serial.println("PONG");
  }
  else {
    Serial.println("ERR: " + line);
  }
}
