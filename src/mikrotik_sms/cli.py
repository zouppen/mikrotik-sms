import sys
import re
import json
import argparse
import threading
from datetime import datetime
from io import StringIO

from paho.mqtt import client as mqtt
from smspdudecoder.fields import SMSDeliver


# Regex: pdu=<one or more hex chars>
PDU_RE = re.compile(r"pdu=([0-9A-Fa-f]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read MikroTik SMS PDU lines from stdin, decode, and publish to MQTT."
    )
    parser.add_argument(
        "--mqtt-host",
        default="localhost",
        help="MQTT broker host (default: localhost)",
    )
    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=1883,
        help="MQTT broker port (default: 1883)",
    )
    parser.add_argument(
        "--mqtt-topic",
        default="sms/incoming/mikrotik",
        help='MQTT topic for incoming SMS (default: "sms/incoming/mikrotik")',
    )
    parser.add_argument(
        "--mqtt-username",
        default=None,
        help="MQTT username (optional)",
    )
    parser.add_argument(
        "--mqtt-password",
        default=None,
        help="MQTT password (optional)",
    )
    parser.add_argument(
        "--client-id",
        default="mikrotik-sms-gateway",
        help="MQTT client ID (default: mikrotik-sms-gateway)",
    )
    return parser.parse_args()


def make_mqtt_client(args: argparse.Namespace) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.client_id,
        protocol=mqtt.MQTTv5,
    )

    if args.mqtt_username is not None:
        client.username_pw_set(args.mqtt_username, args.mqtt_password)

    connected_event = threading.Event()
    connect_result = {"ok": False, "reason": None}

    def on_connect(client, userdata, flags, reason_code, properties):
        code_int = reason_code.value
        if code_int == 0:
            connect_result["ok"] = True
        else:
            connect_result["ok"] = False
            connect_result["reason"] = reason_code
        connected_event.set()

    client.on_connect = on_connect

    try:
        client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
    except Exception as e:
        print(f"MQTT connect failed immediately: {e}", file=sys.stderr)
        sys.exit(1)

    client.loop_start()

    if not connected_event.wait(timeout=10):
        print("MQTT connect timeout (no CONNACK received)", file=sys.stderr)
        sys.exit(1)

    if not connect_result["ok"]:
        print(f"MQTT connect failed: {connect_result['reason']}", file=sys.stderr)
        sys.exit(1)

    print("MQTT connected successfully", file=sys.stderr)
    return client


def datetime_to_unix(obj):
    if isinstance(obj, datetime):
        return int(obj.timestamp())
    raise TypeError(f"Type {type(obj)} is not JSON serializable")


def publish_decoded_pdu(
    pdu_hex: str,
    client: mqtt.Client,
    topic: str,
) -> None:
    try:
        deliver_pdu = StringIO(pdu_hex)
        sms = SMSDeliver.decode(deliver_pdu)
    except Exception as e:
        print(f"Failed to decode PDU: {e}", file=sys.stderr)
        return

    try:
        payload_str = json.dumps(
            sms,
            ensure_ascii=False,
            default=datetime_to_unix,
        )
    except Exception as e:
        print(f"Failed to serialize SMS to JSON: {e}", file=sys.stderr)
        return

    info = client.publish(topic, payload_str, qos=1, retain=False)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Failed to publish MQTT message, rc={info.rc}", file=sys.stderr)
        sys.exit(1)

    sender = sms.get("sender", {}).get("number") or "unknown number"

    print(f"Published SMS from {sender} to {topic}", file=sys.stderr)


def main() -> None:
    args = parse_args()
    client = make_mqtt_client(args)

    print(
        f"Reading MikroTik SMS PDU lines from stdin and publishing them to {args.mqtt_topic}",
        file=sys.stderr,
    )

    for line in sys.stdin:
        raw_line = line.rstrip("\n")
        if not raw_line.strip():
            continue

        match = PDU_RE.search(raw_line)
        if not match:
            print(f"Error: cannot parse line (no PDU found): {raw_line!r}", file=sys.stderr)
            sys.exit(1)

        pdu_hex = match.group(1)
        publish_decoded_pdu(pdu_hex, client, args.mqtt_topic)


if __name__ == "__main__":
    main()
