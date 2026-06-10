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
TELEMETRY_PACKET_PAYLOAD_LENGTH = 23

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

SENSOR_FIELD_NAMES = ("ax", "ay", "az", "gx", "gy", "gz", "mx", "my", "mz")


def clear_sensor_telemetry_state() -> None:
	for key in SENSOR_FIELD_NAMES:
		telemetry_state[key] = None


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


def build_hk_packet(voltage_v: float, ax: float, ay: float, az: float,
                    temperature_c: float = 0.0,
                    gx: float = 0.0, gy: float = 0.0, gz: float = 0.0,
                    mx: float = 0.0, my: float = 0.0, mz: float = 0.0) -> bytes:
	global telemetry_sequence

	# Payload layout (23 bytes):
	# mode(1) | voltage mV(2) | temp(2) | accX(2) | accY(2) | accZ(2)
	# gyroX(2) | gyroY(2) | gyroZ(2) | magX(2) | magY(2) | magZ(2)
	payload: list[int] = [
		0x00,
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
		TELEMETRY_PACKET_TYPE_HK,
		*sequence_bytes,
		TELEMETRY_PACKET_PAYLOAD_LENGTH,
		*payload,
	]
	checksum = calculate_packet_checksum(packet_body)
	return bytes([TELEMETRY_PACKET_HEADER, *packet_body, checksum])


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
	if now - last_rssi_poll_time < interval_s:
		return None

	last_rssi_poll_time = now
	return read_xbee_atdb_rssi(ser)


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

		if command.lower() == "b":
			clear_sensor_telemetry_state()

		if self.serial_port is None or not self.serial_port.is_open:
			self._send_json(503, {"ok": False, "error": "serial_not_open"})
			return

		try:
			payload = command.encode("utf-8") + self.line_ending
			with self.serial_lock:
				self.serial_port.write(payload)
				self.serial_port.flush()
			print(f"[uplink] UI command sent: {command!r}")
			self._send_json(200, {"ok": True, "command": command})
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


def write_text_telemetry_state(timestamp: str) -> None:
	if telemetry_state["voltage"] is None:
		return

	temperature = telemetry_state.get("temperature") or 0.0
	data_obj = {
		"timestamp": timestamp,
		"text": "text telemetry sample",
		"hex": "",
		"packet_text": "text telemetry sample",
		"rssi": telemetry_state.get("rssi"),
		"telemetry": {
			"voltageV": telemetry_state["voltage"],
			"temperatureC": temperature,
			"accX": telemetry_state.get("ax") or 0.0,
			"accY": telemetry_state.get("ay") or 0.0,
			"accZ": telemetry_state.get("az") or 0.0,
			"gyroX": telemetry_state.get("gx") or 0.0,
			"gyroY": telemetry_state.get("gy") or 0.0,
			"gyroZ": telemetry_state.get("gz") or 0.0,
			"magX": telemetry_state.get("mx") or 0.0,
			"magY": telemetry_state.get("my") or 0.0,
			"magZ": telemetry_state.get("mz") or 0.0,
		},
	}
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
		default=5.0,
		help="Poll local XBee ATDB RSSI every N seconds. 0 disables polling.",
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
		default="lf",
		help="Line ending appended to UI commands (default: lf)",
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


def write_received_data(timestamp: str, payload: bytes, formatted: str, rssi: float | None = None) -> None:
	packet_hex = payload.hex(" ")
	data_obj = {
		"timestamp": timestamp,
		"text": formatted,
		"hex": packet_hex,
		"packet_text": formatted,
	}
	if rssi is not None:
		data_obj["rssi"] = rssi
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
	}
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
				formatted = format_payload(payload, args.hex)
				print(f"[{timestamp}] {formatted}")

				line = formatted.strip()
				if re.fullmatch(r"num\s*=\s*\d+", line, re.IGNORECASE):
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

				field_name, field_value = parse_telemetry_line(line)
				if field_name is not None and field_value is not None:
					telemetry_state[field_name] = field_value
					if field_name == "rssi":
						write_received_data(timestamp, payload, formatted, field_value)
					else:
						write_text_telemetry_state(timestamp)
						maybe_write_packet_from_sample(timestamp)
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
