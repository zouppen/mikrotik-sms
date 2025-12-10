# mikrotik-sms

A small utility that reads **MikroTik RouterOS SMS inbox** output in
terse mode, extracts the **PDU**, decodes it using
`smspdudecoder`, and publishes the fully decoded SMS as **JSON over
MQTT**.

This tool is intended to be used together with:

- Mikrotik SSH command `/tool sms inbox print without-paging terse proplist=pdu follow-only`
- A local MQTT broker such as **Mosquitto**
- Consumers like **Node-RED**, **Home Assistant**, custom apps, etc.

The program terminates immediately on:

- MQTT authentication/connection failure at startup
- Any MQTT publish error
- Any non-empty input line that does not contain a valid `pdu=<hex>` field

## Features

- Parses message directly from PDU, enabling non-ASCII message payloads
- Full GSM 03.40 decoding using `smspdudecoder`
- MQTT v5 support with strict failure handling
- JSON output with **Unix timestamps**

## Requirements

- Python **≥ 3.10**
- `paho-mqtt ≥ 2.0`
- `smspdudecoder`

All Python dependencies are installed automatically when using `pip install`.

## Installation

To install it inside a virtual environment:

```sh
virtualenv env
. env/bin/activate
pip install -e .
```

## Usage

First, reate SSH key using `ssh-keygen` on the host you want to run
this project. Then, create a new user on Mikrotik and add the public
SSH key to that user. See
[MikroTik SSH documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/132350014/SSH).
Then run this tool (preferably in a systemd unit) by running:

```sh
stdbuf -oL ssh \
	-o ConnectTimeout=10 \
	-o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
	-o BatchMode=yes \
	user@mikrotik_ip \
	/tool sms/inbox/print without-paging terse proplist=pdu follow-only | \
	mikrotik-sms --mqtt-host MQTT_IP --mqtt-username MQTT_USER --mqtt-password MQTT_PW
```

## License

This project is released under the GNU General Public License v3.0, or
(at your option) any later version.

See [LICENSE file](LICENSE).
