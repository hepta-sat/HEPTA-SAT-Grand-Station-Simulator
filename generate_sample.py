from datetime import datetime
import os

from receive_data import telemetry_state, maybe_write_packet_from_sample


def main():
    # Fill telemetry_state with plausible sample values
    telemetry_state["voltage"] = 3.70
    telemetry_state["ax"] = 0.12
    telemetry_state["ay"] = -0.05
    telemetry_state["az"] = 9.81

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    maybe_write_packet_from_sample(timestamp)

    out_path = os.path.join(os.path.dirname(__file__), "data.json")
    print(f"Wrote sample data.json -> {out_path}")


if __name__ == '__main__':
    main()
