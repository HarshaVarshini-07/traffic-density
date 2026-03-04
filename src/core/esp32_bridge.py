"""
ESP32 Serial Bridge — Smart Traffic Management System

Sends lane density and emergency data from the Python GUI
to the ESP32 Sender via USB Serial.

Protocol:
  DEN:c1,c2,c3,c4\n  — lane vehicle counts
  EMG:lane\n           — emergency trigger (1-4)
  EMG:0\n              — cancel emergency
  PING\n               — health check (expects PONG)
"""

import serial
import serial.tools.list_ports
import threading
import time
import logging

logger = logging.getLogger(__name__)


class ESP32Bridge:
    """Serial bridge to communicate with ESP32 Sender over USB."""

    def __init__(self, port: str = "COM3", baud: int = 115200, enabled: bool = True):
        self.port = port
        self.baud = baud
        self.enabled = enabled
        self.serial_conn: serial.Serial | None = None
        self.connected = False
        self.lock = threading.Lock()
        self._reconnect_interval = 5.0  # seconds
        self._last_reconnect_attempt = 0
        self._send_count = 0
        self._error_count = 0

    # ── Connection ──────────────────────────────────────────

    def connect(self) -> bool:
        """Open serial connection to ESP32."""
        if not self.enabled:
            logger.info("ESP32 bridge disabled in config")
            return False

        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=1,
                write_timeout=1
            )
            time.sleep(2)  # Wait for ESP32 to reset after serial connect
            self.connected = True
            self._error_count = 0
            logger.info(f"ESP32 connected on {self.port} @ {self.baud}")
            return True
        except serial.SerialException as e:
            logger.warning(f"ESP32 connection failed on {self.port}: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Close serial connection."""
        with self.lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
            self.connected = False
            logger.info("ESP32 disconnected")

    def _try_reconnect(self):
        """Attempt reconnect if enough time has passed."""
        now = time.time()
        if now - self._last_reconnect_attempt < self._reconnect_interval:
            return
        self._last_reconnect_attempt = now
        logger.info(f"Attempting ESP32 reconnect on {self.port}...")
        self.disconnect()
        self.connect()

    # ── Sending ─────────────────────────────────────────────

    def _send(self, message: str):
        """Thread-safe serial write."""
        if not self.enabled:
            return

        if not self.connected:
            self._try_reconnect()
            if not self.connected:
                return

        with self.lock:
            try:
                data = (message.strip() + "\n").encode("utf-8")
                self.serial_conn.write(data)
                self.serial_conn.flush()
                self._send_count += 1
            except (serial.SerialException, OSError) as e:
                self._error_count += 1
                logger.warning(f"ESP32 send error: {e}")
                self.connected = False

    def send_density(self, counts: list):
        """
        Send lane density data to ESP32.
        counts: list of 4 integers [lane1, lane2, lane3, lane4]
        """
        if len(counts) != 4:
            logger.error(f"Expected 4 lane counts, got {len(counts)}")
            return

        msg = f"DEN:{counts[0]},{counts[1]},{counts[2]},{counts[3]}"
        self._send(msg)

    def send_emergency(self, lane: int):
        """
        Send emergency trigger for a specific lane.
        lane: 1-4 for emergency, 0 to cancel.
        """
        if lane < 0 or lane > 4:
            logger.error(f"Invalid emergency lane: {lane}")
            return

        msg = f"EMG:{lane}"
        self._send(msg)

    def send_states(self, states: list):
        """
        Send traffic light states directly to Arduino via ESP32.
        states: list of 4 strings, each 'R', 'Y', or 'G'
        Example: ['R', 'G', 'R', 'R'] → SIG:R,G,R,R
        """
        if len(states) != 4:
            logger.error(f"Expected 4 states, got {len(states)}")
            return

        msg = f"SIG:{states[0]},{states[1]},{states[2]},{states[3]}"
        self._send(msg)

    def ping(self) -> bool:
        """Send PING and wait for PONG response."""
        if not self.connected:
            return False

        with self.lock:
            try:
                self.serial_conn.write(b"PING\n")
                self.serial_conn.flush()
                response = self.serial_conn.readline().decode("utf-8").strip()
                return response == "PONG"
            except Exception:
                return False

    # ── Status ──────────────────────────────────────────────

    @property
    def status(self) -> dict:
        """Return connection status info."""
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "port": self.port,
            "baud": self.baud,
            "sent": self._send_count,
            "errors": self._error_count,
        }

    # ── Utility ─────────────────────────────────────────────

    @staticmethod
    def list_ports() -> list:
        """List available serial ports on the system."""
        ports = serial.tools.list_ports.comports()
        return [
            {"port": p.device, "desc": p.description, "hwid": p.hwid}
            for p in ports
        ]
