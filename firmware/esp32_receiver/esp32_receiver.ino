/*
 * ESP32 RECEIVER — Smart Traffic System
 * Receives ESP-NOW, forwards to Arduino Mega via UART.
 * MEGA_SERIAL: Serial2 (GPIO17=TX, GPIO16=RX) @ 9600
 * Struct: 10 bytes (must match sender)
 */
#include <esp_now.h>
#include <WiFi.h>

#define LED_PIN     2
#define MEGA_SERIAL Serial1  // TX1=GPIO27, RX1=GPIO26

// Must match sender struct EXACTLY
typedef struct {
  char type;          // 'D','E','S'
  uint8_t lane;       // emergency lane 1-4, 0=none
  uint8_t counts[4];  // vehicle counts
  char states[4];     // signal R/Y/G
} TrafficData;        // = 10 bytes

TrafficData incoming;
unsigned long rxCount = 0;
unsigned long lastRxTime = 0;

uint8_t SENDER_MAC[6];
bool senderMacKnown = false;

void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  // Optional logging
}

void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (!senderMacKnown) {
    memcpy(SENDER_MAC, info->src_addr, 6);
    esp_now_peer_info_t peerInfo;
    memset(&peerInfo, 0, sizeof(peerInfo));
    memcpy(peerInfo.peer_addr, SENDER_MAC, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    esp_now_add_peer(&peerInfo);
    senderMacKnown = true;
    Serial.println("-> SENDER MAC captured for bi-directional link.");
  }

  if (len != sizeof(TrafficData)) {
    // If the size doesn't match the struct, assume it's a raw chat string and print it
    char buf[250];
    int copyLen = len < 249 ? len : 249;
    memcpy(buf, data, copyLen);
    buf[copyLen] = '\0';
    Serial.println();
    Serial.print("Sender: "); // Show string from sender
    Serial.println(buf);
    return;
  }

  memcpy(&incoming, data, sizeof(incoming));
  rxCount++;
  lastRxTime = millis();
  digitalWrite(LED_PIN, !digitalRead(LED_PIN));

  String cmd;
  if (incoming.type == 'D') {
    cmd = "DEN:" + String(incoming.counts[0]) + "," + String(incoming.counts[1]) + ","
                 + String(incoming.counts[2]) + "," + String(incoming.counts[3]);
  }
  else if (incoming.type == 'E') {
    cmd = "EMG:" + String(incoming.lane);
  }
  else if (incoming.type == 'S') {
    cmd = "SIG:" + String(incoming.states[0]) + "," + String(incoming.states[1]) + ","
                 + String(incoming.states[2]) + "," + String(incoming.states[3]);
  }
  else {
    Serial.printf("WARN: unknown type '%c'\n", incoming.type);
    return;
  }

  MEGA_SERIAL.println(cmd);
  Serial.println("-> Mega: " + cmd);
}

void setup() {
  Serial.begin(115200);
  MEGA_SERIAL.begin(9600, SERIAL_8N1, 26, 27); // RX=26, TX=27
  pinMode(LED_PIN, OUTPUT);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  Serial.println("================================");
  Serial.println(" ESP32 RECEIVER — Smart Traffic");
  Serial.println("================================");
  Serial.print("MAC: ");
  Serial.println(WiFi.macAddress());

  if (esp_now_init() != ESP_OK) {
    Serial.println("ERROR: ESP-NOW init failed!");
    return;
  }
  esp_now_register_recv_cb(onDataRecv);
  esp_now_register_send_cb(onDataSent);
  Serial.println("Listening...");
}

void loop() {
  // Stats every 10s
  static unsigned long lastStats = 0;
  if (millis() - lastStats > 10000) {
    lastStats = millis();
    Serial.printf("Stats: %lu msgs | Last: %lums ago\n", rxCount,
                  lastRxTime > 0 ? millis() - lastRxTime : 0);
  }

  // Forward Mega replies to debug and back to Sender via ESP-NOW
  while (MEGA_SERIAL.available()) {
    String msg = MEGA_SERIAL.readStringUntil('\n');
    msg.trim();
    if (msg.length() > 0) {
      Serial.println("Mega: " + msg);
      if (senderMacKnown) {
        esp_now_send(SENDER_MAC, (uint8_t*)msg.c_str(), msg.length() + 1);
      }
    }
  }

  // Allow USER to chat from the PC Serial Monitor back to the SENDER
  while (Serial.available()) {
    String outMsg = Serial.readStringUntil('\n');
    outMsg.trim();
    if (outMsg.length() > 0) {
      if (senderMacKnown) {
        esp_now_send(SENDER_MAC, (uint8_t*)outMsg.c_str(), outMsg.length() + 1);
        Serial.println("Me: " + outMsg);
      } else {
        Serial.println("ERR: Cannot send, Sender MAC not known yet! (Wait for them to speak first)");
      }
    }
  }

  delay(10);
}
