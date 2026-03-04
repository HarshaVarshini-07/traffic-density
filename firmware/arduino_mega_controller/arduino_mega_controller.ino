/*
 * ARDUINO MEGA — Smart Traffic LED Controller
 * Receives SIG/DEN/EMG from ESP32 via Serial1 (Pin 19).
 * No RFID, no sensors. All commands from PC.
 * Serial1 Baud: 9600 | USB Baud: 9600
 *
 * Pins: Lane1(22,23,24) Lane2(25,26,27) Lane3(34,35,36) Lane4(31,32,33)
 */

const int LEDS[4][3] = {
  {22, 23, 24},  // Lane 1: R,Y,G
  {25, 26, 27},  // Lane 2: R,Y,G
  {34, 35, 36},  // Lane 3: R,Y,G
  {31, 32, 33}   // Lane 4: R,Y,G
};

#define LED_OK  48
#define LED_EMG 47

void setup() {
  Serial.begin(9600);
  Serial1.begin(9600);

  for (int i = 0; i < 4; i++)
    for (int j = 0; j < 3; j++) {
      pinMode(LEDS[i][j], OUTPUT);
      digitalWrite(LEDS[i][j], LOW);
    }
  pinMode(LED_OK, OUTPUT);
  pinMode(LED_EMG, OUTPUT);

  // LED test
  for (int i = 0; i < 4; i++)
    for (int j = 0; j < 3; j++) {
      digitalWrite(LEDS[i][j], HIGH);
      delay(80);
      digitalWrite(LEDS[i][j], LOW);
    }

  setAllRed();
  digitalWrite(LED_OK, HIGH);
  Serial.println(F("=== Smart Traffic Remote ==="));
  Serial.println(F("Ready!"));
}

void loop() {
  // ESP32 commands
  if (Serial1.available()) {
    String line = Serial1.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      Serial.print(F("ESP> "));
      Serial.println(line);
      handleCmd(line);
    }
  }

  // USB debug commands
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      Serial.print(F("USB> "));
      Serial.println(line);
      handleCmd(line);
    }
  }

  delay(10);
}

void handleCmd(String line) {
  if (line.startsWith("SIG:")) {
    setSig(line.substring(4));
  }
  else if (line.startsWith("EMG:")) {
    int lane = line.substring(4).toInt();
    if (lane >= 1 && lane <= 4) {
      setAllRed();
      digitalWrite(LEDS[lane-1][0], LOW);
      digitalWrite(LEDS[lane-1][2], HIGH);
      digitalWrite(LED_EMG, HIGH);
      Serial.print(F("EMG Lane "));
      Serial.println(lane);
    } else {
      digitalWrite(LED_EMG, LOW);
      Serial.println(F("EMG off"));
    }
  }
  else if (line.startsWith("DEN:")) {
    Serial.print(F("DEN: "));
    Serial.println(line.substring(4));
  }
  else {
    Serial.print(F("? "));
    Serial.println(line);
  }
}

void setSig(String data) {
  char s[4] = {'R','R','R','R'};
  int idx = 0;

  for (unsigned int i = 0; i < data.length() && idx < 4; i++) {
    char c = data.charAt(i);
    if (c == 'R' || c == 'G' || c == 'Y') {
      s[idx++] = c;
      while (i+1 < data.length() && data.charAt(i+1) != ',') i++;
    }
  }

  for (int i = 0; i < 4; i++) {
    digitalWrite(LEDS[i][0], s[i] == 'R' ? HIGH : LOW);
    digitalWrite(LEDS[i][1], s[i] == 'Y' ? HIGH : LOW);
    digitalWrite(LEDS[i][2], s[i] == 'G' ? HIGH : LOW);
  }

  digitalWrite(LED_EMG, LOW);
  Serial.print(F("SET ["));
  for (int i = 0; i < 4; i++) {
    Serial.print(s[i]);
    if (i < 3) Serial.print(',');
  }
  Serial.println(']');
}

void setAllRed() {
  for (int i = 0; i < 4; i++) {
    digitalWrite(LEDS[i][0], HIGH);
    digitalWrite(LEDS[i][1], LOW);
    digitalWrite(LEDS[i][2], LOW);
  }
}
