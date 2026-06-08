import argparse
from datetime import datetime
import re

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
	# optional sensors
	"gx": None,
	"gy": None,
	"gz": None,
	"mx": None,
	"my": None,
	"mz": None,
}
telemetry_sequence = 0


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
                    gx: float = 0.0, gy: float = 0.0, gz: float = 0.0,
                    mx: float = 0.0, my: float = 0.0, mz: float = 0.0) -> bytes:
	global telemetry_sequence

	# Payload layout (23 bytes):
	# mode(1) | voltage mV(2) | temp(2) | accX(2) | accY(2) | accZ(2)
	# gyroX(2) | gyroY(2) | gyroZ(2) | magX(2) | magY(2) | magZ(2)
	payload: list[int] = [
		0x00,
		*encode_u16(round(voltage_v * 1000)),
		*encode_i16(0),  # temperature placeholder
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
	patterns = {
		"ax": r"^AX\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"ay": r"^AY\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"az": r"^AZ\s*=\s*([-+]?\d+(?:\.\d+)?)$",
		"voltage": r"^V\s*=\s*([-+]?\d+(?:\.\d+)?)$",
	}

	for key, pattern in patterns.items():
		match = re.match(pattern, line)
		if match:
			return key, float(match.group(1))

	return None, None


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

	packet = build_hk_packet(
		telemetry_state["voltage"],
		telemetry_state["ax"],
		telemetry_state["ay"],
		telemetry_state["az"],
		gx, gy, gz, mx, my, mz,
	)
	packet_hex = packet.hex(" ")
	data_obj = {
		"timestamp": timestamp,
		"text": "HK telemetry sample",
		"hex": packet_hex,
		"packet_hex": packet_hex,
		"packet_text": "HK telemetry sample",
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


def main() -> None:
	args = parse_args()
	args.port = resolve_port(args.port)
	if not args.port:
		return

	print(
		f"Listening on {args.port} @ {args.baudrate} bps "
		f"(timeout={args.timeout}s). Ctrl+C で終了します。"
	)

	try:
		with serial.Serial(args.port, args.baudrate, timeout=args.timeout) as ser:
			if args.send_uplink:
				uplink_bytes = args.uplink_cmd.encode("utf-8")
				if args.append_crlf:
					uplink_bytes += b"\r\n"
				ser.write(uplink_bytes)
				ser.flush()
				print(f"[uplink] 送信: {args.uplink_cmd!r}")

			while True:
				payload = ser.readline()
				if not payload:
					continue

				timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
				formatted = format_payload(payload, args.hex)
				print(f"[{timestamp}] {formatted}")

				line = formatted.strip()
				field_name, field_value = parse_telemetry_line(line)
				if field_name is not None and field_value is not None:
					telemetry_state[field_name] = field_value
					if field_name == "voltage":
						maybe_write_packet_from_sample(timestamp)
				else:
					# For non-telemetry text, preserve the original behavior.
					data_obj = {
						"timestamp": timestamp,
						"text": formatted,
						"hex": payload.hex(" ")
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


if __name__ == "__main__":
	main()
