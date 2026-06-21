import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import threading
import time

import serial
from serial.tools import list_ports
import json
import os


TELEMETRY_PACKET_HEADER = 0x7E
TELEMETRY_PACKET_SAT_ID = 0x01
TELEMETRY_PACKET_TYPE_HK = 0x10
TELEMETRY_PACKET_TYPE_MISSION = 0x11
TELEMETRY_PACKET_TYPES = (0x10, 0x11, 0x12, 0x20, 0x30)
TELEMETRY_PACKET_BASIC_PAYLOAD_LENGTH = 5
TELEMETRY_PACKET_PAYLOAD_LENGTH = 23
TELEMETRY_PACKET_PAYLOAD_LENGTHS = (TELEMETRY_PACKET_BASIC_PAYLOAD_LENGTH, TELEMETRY_PACKET_PAYLOAD_LENGTH)
COMMAND_PACKET_PARAMETER = 0x00
COMMAND_PACKET_IDS = {
	"a": 0x11,
	"b": 0x12,
}
COMMAND_PACKET_LABELS = {
	"a": "SENSOR_MODE ON",
	"b": "SENSOR_MODE OFF",
}
next_command_sequence_number = 0x003B

telemetry_state = {
	"ax": None,
	"ay": None,
	"az": None,
	"voltage": None,
	"rssi": None,
	"temperature": None,
	# optional sensors
	"gx": None,
	"gy": None,
	"gz": None,
	"mx": None,
	"my": None,
	"mz": None,
}
telemetry_sequence = 0
last_warning_signature = None
last_rssi_poll_time = 0.0
last_command_send_time = 0.0
last_command_ack: dict | None = None
last_command_tx: dict | None = None
current_sensor_mode = "OFF"
COMMAND_ACK_TTL_S = 30.0
COMMAND_ACK_RSSI_GUARD_S = 4.0

SENSOR_FIELD_NAMES = ("ax", "ay", "az", "gx", "gy", "gz", "mx", "my", "mz")


def clear_sensor_telemetry_state() -> None:
	for key in SENSOR_FIELD_NAMES:
		telemetry_state[key] = None


def get_sensor_mode_display() -> tuple[str, str]:
	return ("Mission", "mission") if current_sensor_mode == "ON" else ("Standby", "normal")


def to_int16(value: int) -> int:
	return max(-32768, min(32767, int(value)))


def encode_u16(value: int) -> list[int]:
	clamped = max(0, min(65535, int(value)))
	return [(clamped >> 8) & 0xFF, clamped & 0xFF]


def encode_i16(value: int) -> list[int]:
	clamped = to_int16(value)
	if clamped < 0:
		clamped += 1 << 16
	return [(clamped >> 8) & 0xFF, clamped & 0xFF]


def calculate_packet_checksum(bytes_without_header_and_checksum: list[int]) -> int:
	return sum(bytes_without_header_and_checksum) & 0xFF


def is_packet_checksum_ok(packet: bytes) -> bool:
	checksum = packet[-1]
	without_header = calculate_packet_checksum(list(packet[1:-1]))
	with_header = calculate_packet_checksum(list(packet[:-1]))
	return checksum == without_header or checksum == with_header


def build_hk_packet(voltage_v: float, ax: float, ay: float, az: float,
                    temperature_c: float = 0.0,
                    gx: float = 0.0, gy: float = 0.0, gz: float = 0.0,
                    mx: float = 0.0, my: float = 0.0, mz: float = 0.0,
                    sensor_mode: str | None = None) -> bytes:
	global telemetry_sequence

	mode = str(sensor_mode or current_sensor_mode).upper()
	mode_byte = 0x01 if mode == "ON" else 0x00
	packet_type = TELEMETRY_PACKET_TYPE_MISSION if mode == "ON" else TELEMETRY_PACKET_TYPE_HK

	# Payload layout (23 bytes):
	# mode(1) | voltage mV(2) | temp(2) | accX(2) | accY(2) | accZ(2)
	# gyroX(2) | gyroY(2) | gyroZ(2) | magX(2) | magY(2) | magZ(2)
	payload: list[int] = [
		mode_byte,
		*encode_u16(round(voltage_v * 1000)),
		*encode_i16(round(temperature_c * 10)),
		*encode_i16(round(ax * 100)),
		*encode_i16(round(ay * 100)),
		*encode_i16(round(az * 100)),
		*encode_i16(round(gx * 10)),
		*encode_i16(round(gy * 10)),
		*encode_i16(round(gz * 10)),
		*encode_i16(round(mx * 10)),
		*encode_i16(round(my * 10)),
		*encode_i16(round(mz * 10)),
	]

	telemetry_sequence = (telemetry_sequence + 1) & 0xFFFF
	sequence_bytes = [(telemetry_sequence >> 8) & 0xFF, telemetry_sequence & 0xFF]
	packet_body = [
		TELEMETRY_PACKET_SAT_ID,
		packet_type,
		*sequence_bytes,
		TELEMETRY_PACKET_PAYLOAD_LENGTH,
		*payload,
	]
	checksum = calculate_packet_checksum(packet_body)
	return bytes([TELEMETRY_PACKET_HEADER, *packet_body, checksum])


def build_command_packet_info(command: str) -> dict | None:
	global next_command_sequence_number

	command_key = command.strip().lower()
	command_id = COMMAND_PACKET_IDS.get(command_key)
	if command_id is None:
		return None

	sequence = next_command_sequence_number & 0xFFFF
	next_command_sequence_number = (next_command_sequence_number + 1) & 0xFFFF
	packet_body = [
		TELEMETRY_PACKET_SAT_ID,
		command_id,
		COMMAND_PACKET_PARAMETER,
		(sequence >> 8) & 0xFF,
		sequence & 0xFF,
	]
	checksum = calculate_packet_checksum(packet_body)
	packet = bytes([TELEMETRY_PACKET_HEADER, *packet_body, checksum])
	return {
		"packet_hex": packet.hex(" "),
		"destination_id": TELEMETRY_PACKET_SAT_ID,
		"command_id": command_id,
		"parameter": COMMAND_PACKET_PARAMETER,
		"sequence": sequence,
		"checksum": checksum,
		"label": COMMAND_PACKET_LABELS.get(command_key, command_key.upper()),
		"bytes": packet,
	}


def command_packet_json(packet_info: dict | None) -> dict | None:
	if not packet_info:
		return None
	return {key: value for key, value in packet_info.items() if key != "bytes"}


def parse_telemetry_line(line: str) -> tuple[str | None, float | None]:
	rssi_value = parse_rssi_line(line)
	if rssi_value is not None:
		return "rssi", rssi_value

	patterns = {
		"ax": r"^AX\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"ay": r"^AY\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"az": r"^AZ\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"gx": r"^GX\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"gy": r"^GY\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"gz": r"^GZ\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"mx": r"^MX\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"my": r"^MY\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"mz": r"^MZ\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"voltage": r"^V\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"temperature": r"^(?:T|TEMP)\s*=\s*([-+]?\d+(?:\.\d+)?)$",
	}

	for key, pattern in patterns.items():
		match = re.match(pattern, line)
		if match:
			return key, float(match.group(1))

	return None, None


def normalize_rssi_dbm(value: float) -> float:
	# XBee RSSI is normally reported as a negative dBm value, while ATDB
	# reports only the positive magnitude. Accept both forms for logs/tests.
	return -value if value > 0 else value


def parse_rssi_line(line: str) -> float | None:
	direct_match = re.match(r"^RSSI\s*[:=]\s*(-?\d{1,3}(?:\.\d+)?)\s*(?:dBm)?$", line, re.IGNORECASE)
	if direct_match:
		return normalize_rssi_dbm(float(direct_match.group(1)))

	db_match = re.match(r"^DB\s*[:=]\s*([0-9A-Fa-f]{1,2})$", line, re.IGNORECASE)
	if db_match:
		return -float(int(db_match.group(1), 16))

	return None


def read_xbee_atdb_rssi(ser: serial.Serial, guard_time_s: float = 1.05) -> float | None:
	original_timeout = ser.timeout
	try:
		ser.timeout = 1.0
		time.sleep(guard_time_s)
		ser.reset_input_buffer()
		ser.write(b"+++")
		ser.flush()
		time.sleep(guard_time_s)

		response = ser.read_until(b"\r").decode("ascii", errors="ignore").strip()
		if response != "OK":
			return None

		ser.write(b"ATDB\r")
		ser.flush()
		db_response = ser.read_until(b"\r").decode("ascii", errors="ignore").strip()

		ser.write(b"ATCN\r")
		ser.flush()
		ser.read_until(b"\r")

		if re.fullmatch(r"[0-9A-Fa-f]{1,2}", db_response):
			return -float(int(db_response, 16))
		return parse_rssi_line(f"DB={db_response}")
	except Exception:
		return None
	finally:
		ser.timeout = original_timeout


def maybe_poll_xbee_rssi(ser: serial.Serial, interval_s: float) -> float | None:
	global last_rssi_poll_time

	if interval_s <= 0:
		return None

	now = time.monotonic()
	if now - last_command_send_time < COMMAND_ACK_RSSI_GUARD_S:
		return None

	if now - last_rssi_poll_time < interval_s:
		return None

	last_rssi_poll_time = now
	return read_xbee_atdb_rssi(ser)


def remember_command_ack(timestamp: str, line: str) -> None:
	global current_sensor_mode, last_command_ack

	normalized_line = line.strip().strip("\"'`“”‘’")
	match = re.match(r"^SENSOR_MODE\s*=?\s*(ON|OFF)$", normalized_line, re.IGNORECASE)
	compact_match = re.search(r"\b(MISSION|STANDBY)_ACK\b", normalized_line, re.IGNORECASE)
	if match:
		mode = match.group(1).upper()
	elif compact_match:
		mode = "ON" if compact_match.group(1).upper() == "MISSION" else "OFF"
	else:
		return
	current_sensor_mode = mode
	expected_ack = f"SENSOR_MODE = {mode}"
	now = time.monotonic()
	if (
		not last_command_tx
		or last_command_tx.get("expected_ack") != expected_ack
		or last_command_tx.get("ack_received")
		or now - float(last_command_tx.get("sent_monotonic", 0.0)) > COMMAND_ACK_TTL_S
	):
		print(f"[status] SENSOR_MODE={mode}")
		return

	last_command_ack = {
		"timestamp": timestamp,
		"text": expected_ack,
		"mode": mode,
		"received_monotonic": now,
	}
	last_command_tx["ack_received"] = True
	print(f"[ack] SENSOR_MODE={mode}")


def remember_command_tx(command: str, payload: bytes, packet_info: dict | None = None) -> None:
	global last_command_tx

	expected_ack = None
	command_key = command.lower()
	if command_key == "a":
		expected_ack = "SENSOR_MODE = ON"
	elif command_key == "b":
		expected_ack = "SENSOR_MODE = OFF"

	last_command_tx = {
		"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
		"command": command_key,
		"hex": payload.hex(" "),
		"packet_hex": packet_info.get("packet_hex") if packet_info else "",
		"packet_label": packet_info.get("label") if packet_info else "",
		"packet": command_packet_json(packet_info),
		"expected_ack": expected_ack,
		"ack_received": False,
		"sent_monotonic": time.monotonic(),
	}


def attach_recent_command_ack(data_obj: dict) -> None:
	if not last_command_ack:
		pass
	elif time.monotonic() - float(last_command_ack.get("received_monotonic", 0.0)) <= COMMAND_ACK_TTL_S:
		data_obj["command_ack"] = {
			"timestamp": last_command_ack.get("timestamp"),
			"text": last_command_ack.get("text"),
			"mode": last_command_ack.get("mode"),
		}

	if last_command_tx and time.monotonic() - float(last_command_tx.get("sent_monotonic", 0.0)) <= COMMAND_ACK_TTL_S:
		data_obj["command_tx"] = {
			"timestamp": last_command_tx.get("timestamp"),
			"command": last_command_tx.get("command"),
			"hex": last_command_tx.get("hex"),
			"packet_hex": last_command_tx.get("packet_hex"),
			"packet_label": last_command_tx.get("packet_label"),
			"packet": last_command_tx.get("packet"),
			"expected_ack": last_command_tx.get("expected_ack"),
			"ack_received": last_command_tx.get("ack_received"),
		}


class CommandApiHandler(BaseHTTPRequestHandler):
	serial_port: serial.Serial | None = None
	serial_lock = threading.Lock()
	line_ending = b"\n"

	def log_message(self, format: str, *args: object) -> None:
		print(f"[api] {format % args}")

	def _send_json(self, status_code: int, payload: dict) -> None:
		body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		self.send_response(status_code)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Content-Length", str(len(body)))
		self.send_header("Access-Control-Allow-Origin", "*")
		self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		self.send_header("Access-Control-Allow-Headers", "Content-Type")
		self.end_headers()
		self.wfile.write(body)

	def do_OPTIONS(self) -> None:
		self._send_json(200, {"ok": True})

	def do_GET(self) -> None:
		if self.path == "/health":
			self._send_json(200, {"ok": True, "serial_open": self.serial_port is not None and self.serial_port.is_open})
			return
		self._send_json(404, {"ok": False, "error": "not_found"})

	def do_POST(self) -> None:
		global last_command_send_time

		if self.path != "/send-command":
			self._send_json(404, {"ok": False, "error": "not_found"})
			return

		try:
			content_length = int(self.headers.get("Content-Length", "0"))
			raw_body = self.rfile.read(content_length).decode("utf-8")
			body = json.loads(raw_body) if raw_body else {}
			command = str(body.get("command", "")).strip()
		except Exception:
			self._send_json(400, {"ok": False, "error": "invalid_json"})
			return

		if not command:
			self._send_json(400, {"ok": False, "error": "empty_command"})
			return
		command_key = command.lower()
		if command_key not in COMMAND_PACKET_IDS:
			self._send_json(400, {"ok": False, "error": "unsupported_command", "allowed": sorted(COMMAND_PACKET_IDS)})
			return

		if command_key == "b":
			clear_sensor_telemetry_state()

		if self.serial_port is None or not self.serial_port.is_open:
			self._send_json(503, {"ok": False, "error": "serial_not_open"})
			return

		try:
			payload = command_key.encode("utf-8") + self.line_ending
			with self.serial_lock:
				self.serial_port.write(payload)
				self.serial_port.flush()
			last_command_send_time = time.monotonic()
			remember_command_tx(command_key, payload)
			print(f"[uplink] UI command sent: {command_key!r}")
			self._send_json(200, {
				"ok": True,
				"command": command_key,
				"hex": payload.hex(" "),
				"packet_hex": last_command_tx.get("packet_hex") if last_command_tx else "",
				"packet_label": last_command_tx.get("packet_label") if last_command_tx else "",
				"packet": last_command_tx.get("packet") if last_command_tx else None,
				"expected_ack": last_command_tx.get("expected_ack") if last_command_tx else None,
			})
		except Exception as exc:
			print(f"[api] command send failed: {exc}")
			self._send_json(500, {"ok": False, "error": "send_failed"})


def start_command_api(ser: serial.Serial, host: str, port: int, line_ending: bytes) -> ThreadingHTTPServer:
	CommandApiHandler.serial_port = ser
	CommandApiHandler.line_ending = line_ending
	server = ThreadingHTTPServer((host, port), CommandApiHandler)
	thread = threading.Thread(target=server.serve_forever, daemon=True)
	thread.start()
	print(f"[api] Command API listening on http://{host}:{port}")
	return server


def maybe_write_packet_from_sample(timestamp: str) -> None:
	# require minimal fields (voltage and accelerations). other sensors default to 0.
	if telemetry_state["voltage"] is None or telemetry_state["ax"] is None or telemetry_state["ay"] is None or telemetry_state["az"] is None:
		return

	gx = telemetry_state.get("gx") or 0.0
	gy = telemetry_state.get("gy") or 0.0
	gz = telemetry_state.get("gz") or 0.0
	mx = telemetry_state.get("mx") or 0.0
	my = telemetry_state.get("my") or 0.0
	mz = telemetry_state.get("mz") or 0.0
	temperature = telemetry_state.get("temperature") or 0.0

	packet = build_hk_packet(
		telemetry_state["voltage"],
		telemetry_state["ax"],
		telemetry_state["ay"],
		telemetry_state["az"],
		temperature,
		gx, gy, gz, mx, my, mz,
		current_sensor_mode,
	)
	packet_hex = packet.hex(" ")
	data_obj = {
		"timestamp": timestamp,
		"text": "HK telemetry sample",
		"hex": packet_hex,
		"packet_hex": packet_hex,
		"packet_text": "HK telemetry sample",
		"rssi": telemetry_state.get("rssi"),
		"telemetry": {
			"modeText": get_sensor_mode_display()[0],
			"modeClassName": get_sensor_mode_display()[1],
			"voltageV": telemetry_state["voltage"],
			"temperatureC": temperature,
			"accX": telemetry_state["ax"],
			"accY": telemetry_state["ay"],
			"accZ": telemetry_state["az"],
			"gyroX": gx,
			"gyroY": gy,
			"gyroZ": gz,
			"magX": mx,
			"magY": my,
			"magZ": mz,
		},
	}
	attach_recent_command_ack(data_obj)
	try:
		tmp_path = os.path.join(os.path.dirname(__file__), "data.json.tmp")
		out_path = os.path.join(os.path.dirname(__file__), "data.json")
		with open(tmp_path, "w", encoding="utf-8") as f:
			json.dump(data_obj, f, ensure_ascii=False)
			f.flush()
			os.fsync(f.fileno())
		os.replace(tmp_path, out_path)
	except Exception:
		print("[WARN] failed to write data.json")


def write_text_telemetry_state(timestamp: str, source_text: str) -> None:
	remember_command_ack(timestamp, source_text)
	text_hex = source_text.encode("utf-8").hex(" ")
	data_obj = {
		"timestamp": timestamp,
		"text": source_text,
		"hex": text_hex,
		"packet_text": source_text,
		"rssi": telemetry_state.get("rssi"),
		"telemetry": {
			"modeText": get_sensor_mode_display()[0],
			"modeClassName": get_sensor_mode_display()[1],
			"voltageV": telemetry_state.get("voltage"),
			"temperatureC": telemetry_state.get("temperature"),
			"accX": telemetry_state.get("ax"),
			"accY": telemetry_state.get("ay"),
			"accZ": telemetry_state.get("az"),
			"gyroX": telemetry_state.get("gx"),
			"gyroY": telemetry_state.get("gy"),
			"gyroZ": telemetry_state.get("gz"),
			"magX": telemetry_state.get("mx"),
			"magY": telemetry_state.get("my"),
			"magZ": telemetry_state.get("mz"),
		},
	}
	attach_recent_command_ack(data_obj)
	try:
		tmp_path = os.path.join(os.path.dirname(__file__), "data.json.tmp")
		out_path = os.path.join(os.path.dirname(__file__), "data.json")
		with open(tmp_path, "w", encoding="utf-8") as f:
			json.dump(data_obj, f, ensure_ascii=False)
			f.flush()
			os.fsync(f.fileno())
		os.replace(tmp_path, out_path)
	except Exception:
		print("[WARN] failed to write data.json")


def build_text_telemetry_object() -> dict:
	return {
		"modeText": get_sensor_mode_display()[0],
		"modeClassName": get_sensor_mode_display()[1],
		"voltageV": telemetry_state.get("voltage"),
		"temperatureC": telemetry_state.get("temperature"),
		"accX": telemetry_state.get("ax"),
		"accY": telemetry_state.get("ay"),
		"accZ": telemetry_state.get("az"),
		"gyroX": telemetry_state.get("gx"),
		"gyroY": telemetry_state.get("gy"),
		"gyroZ": telemetry_state.get("gz"),
		"magX": telemetry_state.get("mx"),
		"magY": telemetry_state.get("my"),
		"magZ": telemetry_state.get("mz"),
	}


def warn_if_sample_looks_suspicious(timestamp: str) -> None:
	global last_warning_signature

	acc = [telemetry_state.get(key) for key in ("ax", "ay", "az")]
	gyro = [telemetry_state.get(key) for key in ("gx", "gy", "gz")]
	mag = [telemetry_state.get(key) for key in ("mx", "my", "mz")]
	if any(value is None for value in [*acc, *gyro, *mag]):
		return

	warnings = []
	if len(set(round(value, 6) for value in acc)) == 1:
		warnings.append("AX/AY/AZ are identical")
	if len(set(round(value, 6) for value in gyro)) == 1:
		warnings.append("GX/GY/GZ are identical")
	if len(set(round(value, 6) for value in mag)) <= 2:
		warnings.append("MX/MY/MZ have repeated values")
	if telemetry_state.get("voltage") == 0:
		warnings.append("V is 0")

	if not warnings:
		return

	signature = tuple(warnings)
	if signature == last_warning_signature:
		return

	last_warning_signature = signature
	print(f"[{timestamp}] [WARN] suspicious telemetry: {', '.join(warnings)}")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="XBeeで受信したデータをターミナルに表示します。"
	)
	parser.add_argument(
		"-p",
		"--port",
		default=os.getenv("SERIAL_PORT"),
		help="COM18 または環境変数 SERIAL_PORT",
	)
	parser.add_argument(
		"-b",
		"--baudrate",
		type=int,
		default=9600,
		help="ボーレート (デフォルト: 9600)",
	)
	parser.add_argument(
		"-t",
		"--timeout",
		type=float,
		default=1.0,
		help="受信待ちタイムアウト秒 (デフォルト: 1.0)",
	)
	parser.add_argument(
		"--hex",
		action="store_true",
		help="受信データを16進文字列で表示する",
	)
	parser.add_argument(
		"--send-uplink",
		action="store_true",
		help="接続直後にアップリンクコマンドを1回送信する",
	)
	parser.add_argument(
		"--uplink-cmd",
		default="a",
		help="アップリンクとして送信する文字列 (デフォルト: a)",
	)
	parser.add_argument(
		"--append-crlf",
		action="store_true",
		help="アップリンク送信時にCRLFを付与する",
	)
	parser.add_argument(
		"--rssi-atdb-interval",
		type=float,
		default=0.0,
		help="Poll local XBee ATDB RSSI every N seconds. 0 disables polling. ATDB polling may interrupt telemetry.",
	)
	parser.add_argument(
		"--command-api-host",
		default="127.0.0.1",
		help="UI command API bind host (default: 127.0.0.1)",
	)
	parser.add_argument(
		"--command-api-port",
		type=int,
		default=8765,
		help="UI command API port (default: 8765)",
	)
	parser.add_argument(
		"--command-line-ending",
		choices=("lf", "crlf", "none"),
		default="none",
		help="Line ending appended to UI commands (default: none)",
	)
	return parser.parse_args()


def resolve_port(port: str | None) -> str | None:
	if port:
		return port

	detected_ports = [item.device for item in list_ports.comports()]
	if len(detected_ports) == 1:
		print(f"[info] 自動検出したシリアルポートを使用します: {detected_ports[0]}")
		return detected_ports[0]

	print("[ERROR] シリアルポートが指定されていません。-p/--port を指定するか、SERIAL_PORT を設定してください。")
	if detected_ports:
		print("[INFO] 検出されたポート: " + ", ".join(detected_ports))
	else:
		print("[INFO] 利用可能なシリアルポートが見つかりませんでした。")
	return None


def format_payload(data: bytes, use_hex: bool) -> str:
	if use_hex:
		return data.hex(" ")

	try:
		return data.decode("utf-8").rstrip("\r\n")
	except UnicodeDecodeError:
		return f"<binary> {data.hex(' ')}"


def parse_hex_text_payload(text: str) -> bytes | None:
	cleaned = text.strip()
	if not cleaned:
		return None

	if re.fullmatch(r"(?:0x)?[0-9A-Fa-f]{1,2}(?:[\s,;:]+(?:0x)?[0-9A-Fa-f]{1,2})*", cleaned):
		values = re.findall(r"(?:0x)?([0-9A-Fa-f]{1,2})", cleaned)
		return bytes(int(value, 16) for value in values)

	if re.fullmatch(r"(?:0x)?(?:[0-9A-Fa-f]{2}){7,64}", cleaned):
		hex_text = cleaned[2:] if cleaned.lower().startswith("0x") else cleaned
		return bytes.fromhex(hex_text)

	return None


def extract_complete_packets_from_hex_text(buffer: str) -> tuple[list[bytes], str]:
	packets: list[bytes] = []
	text = buffer

	while True:
		header_match = re.search(r"(?i)(?:^|[^0-9A-F])7E(?:[^0-9A-F]|$)", text)
		if not header_match:
			return packets, text[-8:]

		start = header_match.start()
		if start < len(text) and not re.match(r"(?i)7E", text[start:start + 2]):
			start += 1
		text = text[start:]

		tokens = re.findall(r"(?i)(?:0x)?[0-9A-F]{1,2}", text)
		if len(tokens) < 7:
			return packets, text[-96:]

		values = [int(token.replace("0x", "").replace("0X", ""), 16) for token in tokens]
		if values[0] != TELEMETRY_PACKET_HEADER:
			text = text[2:]
			continue

		packet_type = values[2]
		payload_length = values[5]
		if packet_type not in TELEMETRY_PACKET_TYPES or payload_length not in TELEMETRY_PACKET_PAYLOAD_LENGTHS:
			text = text[2:]
			continue

		total_length = 7 + payload_length
		if len(values) < total_length:
			return packets, text[-160:]

		packet = bytes(values[:total_length])
		if is_packet_checksum_ok(packet):
			packets.append(packet)

		consumed = 0
		for _ in range(total_length):
			match = re.search(r"(?i)(?:0x)?[0-9A-F]{1,2}", text[consumed:])
			if not match:
				break
			consumed += match.end()
		text = text[consumed:]


def extract_complete_telemetry_packets(buffer: bytearray) -> list[bytes]:
	packets: list[bytes] = []

	while True:
		header_index = buffer.find(bytes([TELEMETRY_PACKET_HEADER]))
		if header_index < 0:
			buffer.clear()
			break

		if header_index > 0:
			del buffer[:header_index]

		if len(buffer) < 7:
			break

		packet_type = buffer[2]
		payload_length = buffer[5]

		if packet_type not in TELEMETRY_PACKET_TYPES:
			del buffer[0]
			continue

		if payload_length not in TELEMETRY_PACKET_PAYLOAD_LENGTHS:
			del buffer[0]
			continue

		if payload_length > 64:
			del buffer[0]
			continue

		total_length = 7 + payload_length
		if len(buffer) < total_length:
			break

		packet = bytes(buffer[:total_length])
		if not is_packet_checksum_ok(packet):
			del buffer[0]
			continue

		del buffer[:total_length]
		packets.append(packet)

	return packets


def is_telemetry_packet(payload: bytes) -> bool:
	if len(payload) < 7:
		return False
	if payload[0] != TELEMETRY_PACKET_HEADER:
		return False
	if payload[2] not in TELEMETRY_PACKET_TYPES:
		return False
	payload_length = payload[5]
	if payload_length not in TELEMETRY_PACKET_PAYLOAD_LENGTHS or len(payload) != 7 + payload_length:
		return False
	return is_packet_checksum_ok(payload)


def write_received_data(timestamp: str, payload: bytes, formatted: str, rssi: float | None = None) -> None:
	packet_hex = payload.hex(" ")
	remember_command_ack(timestamp, formatted)
	data_obj = {
		"timestamp": timestamp,
		"text": formatted,
		"hex": packet_hex,
		"packet_text": formatted,
	}
	if is_telemetry_packet(payload):
		data_obj["packet_hex"] = packet_hex
	if rssi is not None:
		data_obj["rssi"] = rssi
	attach_recent_command_ack(data_obj)
	try:
		tmp_path = os.path.join(os.path.dirname(__file__), "data.json.tmp")
		out_path = os.path.join(os.path.dirname(__file__), "data.json")
		with open(tmp_path, "w", encoding="utf-8") as f:
			json.dump(data_obj, f, ensure_ascii=False)
			f.flush()
			os.fsync(f.fileno())
		os.replace(tmp_path, out_path)
	except Exception:
		print("[WARN] failed to write data.json")


def write_rssi_data(timestamp: str, rssi: float) -> None:
	data_obj = {
		"timestamp": timestamp,
		"text": f"RSSI={rssi:.0f}",
		"hex": "",
		"packet_text": f"RSSI={rssi:.0f}",
		"rssi": rssi,
		"telemetry": build_text_telemetry_object(),
	}
	attach_recent_command_ack(data_obj)
	try:
		tmp_path = os.path.join(os.path.dirname(__file__), "data.json.tmp")
		out_path = os.path.join(os.path.dirname(__file__), "data.json")
		with open(tmp_path, "w", encoding="utf-8") as f:
			json.dump(data_obj, f, ensure_ascii=False)
			f.flush()
			os.fsync(f.fileno())
		os.replace(tmp_path, out_path)
	except Exception:
		print("[WARN] failed to write data.json")


def main() -> None:
	args = parse_args()
	args.port = resolve_port(args.port)
	if not args.port:
		return

	line_endings = {
		"lf": b"\n",
		"crlf": b"\r\n",
		"none": b"",
	}
	command_api_server: ThreadingHTTPServer | None = None

	print(
		f"Listening on {args.port} @ {args.baudrate} bps "
		f"(timeout={args.timeout}s). Ctrl+C で終了します。"
	)

	try:
		with serial.Serial(args.port, args.baudrate, timeout=args.timeout) as ser:
			command_api_server = start_command_api(
				ser,
				args.command_api_host,
				args.command_api_port,
				line_endings[args.command_line_ending],
			)

			if args.send_uplink:
				uplink_bytes = args.uplink_cmd.encode("utf-8")
				if args.append_crlf:
					uplink_bytes += b"\r\n"
				with CommandApiHandler.serial_lock:
					ser.write(uplink_bytes)
					ser.flush()
				print(f"[uplink] 送信: {args.uplink_cmd!r}")

			telemetry_packet_buffer = bytearray()
			telemetry_hex_text_buffer = ""

			while True:
				payload = ser.readline()
				if not payload:
					timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
					with CommandApiHandler.serial_lock:
						rssi_value = maybe_poll_xbee_rssi(ser, args.rssi_atdb_interval)
					if rssi_value is not None:
						telemetry_state["rssi"] = rssi_value
						write_rssi_data(timestamp, rssi_value)
					continue

				timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

				if telemetry_packet_buffer or TELEMETRY_PACKET_HEADER in payload:
					telemetry_packet_buffer.extend(payload)
					packets = extract_complete_telemetry_packets(telemetry_packet_buffer)
					if packets:
						for packet in packets:
							packet_formatted = format_payload(packet, args.hex)
							print(f"[{timestamp}] {packet_formatted}")
							write_received_data(timestamp, packet, packet_formatted)
						continue

					if telemetry_packet_buffer:
						continue

				formatted = format_payload(payload, args.hex)
				print(f"[{timestamp}] {formatted}")

				line = formatted.strip()
				telemetry_line = line
				hex_text_payload = parse_hex_text_payload(line)
				if hex_text_payload:
					decoded_text = format_payload(hex_text_payload, False).strip()
					telemetry_hex_text_buffer += decoded_text if decoded_text and not decoded_text.startswith("<binary>") else line
					packets, telemetry_hex_text_buffer = extract_complete_packets_from_hex_text(telemetry_hex_text_buffer)
					if packets:
						for packet in packets:
							packet_formatted = packet.hex(" ")
							print(f"[{timestamp}] {packet_formatted}")
							write_received_data(timestamp, packet, packet_formatted)
						continue
					if decoded_text and not decoded_text.startswith("<binary>"):
						telemetry_line = decoded_text
				else:
					telemetry_hex_text_buffer += line
					packets, telemetry_hex_text_buffer = extract_complete_packets_from_hex_text(telemetry_hex_text_buffer)
					if packets:
						for packet in packets:
							packet_formatted = packet.hex(" ")
							print(f"[{timestamp}] {packet_formatted}")
							write_received_data(timestamp, packet, packet_formatted)
						continue

				if re.fullmatch(r"num\s*=\s*\d+", telemetry_line, re.IGNORECASE):
					clear_sensor_telemetry_state()
					write_received_data(timestamp, payload, formatted)
					continue

				if args.rssi_atdb_interval > 0 and line == "OK":
					continue
				if args.rssi_atdb_interval > 0 and re.fullmatch(r"[0-9A-Fa-f]{1,2}", line):
					rssi_value = -float(int(line, 16))
					telemetry_state["rssi"] = rssi_value
					write_rssi_data(timestamp, rssi_value)
					continue

				field_name, field_value = parse_telemetry_line(telemetry_line)
				if field_name is not None and field_value is not None:
					telemetry_state[field_name] = field_value
					if field_name == "rssi":
						write_rssi_data(timestamp, field_value)
					else:
						write_text_telemetry_state(timestamp, telemetry_line)
					warn_if_sample_looks_suspicious(timestamp)
				else:
					write_received_data(timestamp, payload, formatted)

	except PermissionError as exc:
		print(f"シリアル通信エラー: {exc}")
		print("[hint] そのポートは別のアプリか、別の receive_data.py が使用中の可能性があります。")
		print("[hint] Arduino IDE / TeraTerm / PuTTY / VS Code のシリアル系画面を閉じてから再実行してください。")
		print("[hint] それでも同じなら、USBシリアル変換器を抜き差しして COM ポートを再接続してください。")
		print("[hint] いま動いている受信プロセスがないか確認してから再実行してください。")
	except serial.SerialException as exc:
		print(f"シリアル通信エラー: {exc}")
	except KeyboardInterrupt:
		print("\n受信を終了しました。")
	finally:
		if command_api_server is not None:
			command_api_server.shutdown()
			command_api_server.server_close()


if __name__ == "__main__":
	main()
