/*
 * ESP32 RECEIVER — Smart Traffic System
 * Receives ESP-NOW, forwards to Arduino Mega via UART.
 * MEGA_SERIAL: Serial2 (GPIO17=TX, GPIO16=RX) @ 9600
 * Struct: 10 bytes (must match sender)
 */
#include <esp_now.h>
#include <WiFi.h>

#define LED_PIN     2
#define MEGA_SERIAL Serial2  // TX2=GPIO17, RX2=GPIO16

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

void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (len != sizeof(TrafficData)) {
    Serial.printf("WARN: size %d != %d\n", len, sizeof(TrafficData));
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
  Serial.begin(9600);
  MEGA_SERIAL.begin(9600);
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

  // Forward Mega replies to debug
  while (MEGA_SERIAL.available()) {
    String msg = MEGA_SERIAL.readStringUntil('\n');
    msg.trim();
    if (msg.length() > 0) Serial.println("Mega: " + msg);
  }

  delay(10);
}
