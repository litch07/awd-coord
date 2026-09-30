import json
import queue
import threading
import time
import serial

from . import config


class SerialLink:
    """Reads JSON lines from the Proxy into a queue; sends JSON commands back."""

    def __init__(self, port=config.SERIAL_PORT, baud=config.BAUD):
        self.port, self.baud = port, baud
        self.rx = queue.Queue()
        self._ser = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def start(self):
        self._stop.clear()
        threading.Thread(target=self._run_loop, daemon=True).start()

    def stop(self):
        self._stop.set()
        with self._lock:
            if self._ser:
                self._ser.close()

    def _run_loop(self):
        while not self._stop.is_set():
            try:
                with self._lock:
                    self._ser = serial.Serial(self.port, self.baud, timeout=0.5)
                # Ensure link restoral creates no immediate noise, just ready to read
                self._reader()
            except serial.SerialException as e:
                self.rx.put({"t": "link_lost", "ts": time.time(), "msg": str(e)})
                time.sleep(3.0)  # Wait before reconnecting

    def _reader(self):
        while not self._stop.is_set():
            try:
                raw = self._ser.readline()
            except serial.SerialException:
                # Link lost, break out of reader to allow reconnect
                self.rx.put({"t": "link_lost", "ts": time.time()})
                with self._lock:
                    self._ser.close()
                    self._ser = None
                return
            if not raw:
                continue
            try:
                msg = json.loads(raw.decode("utf-8", errors="replace").strip())
            except json.JSONDecodeError:
                self.rx.put({"t": "unparsed", "line": raw.decode("utf-8", errors="replace").strip(), "ts": time.time()})
                continue
            msg["ts"] = time.time()
            self.rx.put(msg)

    def _send(self, obj):
        line = (json.dumps(obj) + "\n").encode()
        with self._lock:
            if self._ser and self._ser.is_open:
                try:
                    self._ser.write(line)
                except serial.SerialException:
                    pass

    def valve(self, node, open_):
        self._send({"t": "valve", "node": node, "open": bool(open_)})

    def pump(self, on):
        self._send({"t": "pump", "on": bool(on)})

    def sms(self, phone, msg):
        self._send({"t": "sms", "phone": str(phone), "msg": str(msg)})

