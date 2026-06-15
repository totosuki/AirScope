# AirScope Edge

`edge` は、Raspberry Pi での ADS-B データ受信から Azure IoT Hub 送信までを管理する領域です。

現時点では、実機の RTL-SDR や dump1090-fa に依存しないデモ送信用スクリプトを用意しています。

## デモ ADS-B データ送信

`send_demo_adsb.py` は ADS-B で受信したように見えるデモ航空機テレメトリを生成し、任意の HTTP エンドポイントまたは Azure IoT Hub へ JSON で送信します。

実送信せず payload を確認する場合:

```sh
python edge/send_demo_adsb.py --dry-run --count 2 --interval 0
```

任意の IP アドレスへ送信する場合:

```sh
python edge/send_demo_adsb.py --endpoint http://192.168.1.10:8080/telemetry --count 5
```

環境変数でも送信先を指定できます。

```sh
export AIRSCOPE_HTTP_ENDPOINT=http://192.168.1.10:8080/telemetry
python edge/send_demo_adsb.py --count 5
```

Azure IoT Hub へ送信する場合は、事前に `edge` の Python 依存関係をインストールし、デバイス接続文字列を環境変数で渡します。実値はリポジトリに保存しません。

```sh
python -m pip install -e edge
export AIRSCOPE_IOTHUB_DEVICE_CONNECTION_STRING='HostName=...;DeviceId=...;SharedAccessKey=...'
python edge/send_demo_adsb.py --transport azure-iot-hub --count 5
```

接続文字列をコマンドライン引数で渡すこともできますが、シェル履歴に残るため、通常は環境変数を使います。

```sh
python edge/send_demo_adsb.py \
  --transport azure-iot-hub \
  --iothub-connection-string 'HostName=...;DeviceId=...;SharedAccessKey=...'
```

## Payload 形式

送信する JSON は次の構造です。

```json
{
  "schema_version": "airscope.telemetry.demo.v1",
  "source": "airscope-demo",
  "session_id": "demo-20260608T000000Z",
  "sent_at": "2026-06-08T00:00:00.000Z",
  "telemetry": {
    "icao24": "86D9A1",
    "callsign": "ANA245",
    "lat": 35.5523,
    "lon": 139.7798,
    "altitude_ft": 12800,
    "ground_speed_kt": 286,
    "track_deg": 72,
    "vertical_rate_fpm": 640,
    "squawk": "3301",
    "seen_at": "2026-06-08T00:00:00.000Z",
    "received_at": "2026-06-08T00:00:00.000Z",
    "receiver_id": "airscope-demo-rpi",
    "distance_km": 18.4
  }
}
```

## 次の作業

- dump1090-fa の `aircraft.json` 読み取りを追加する。
- Azure IoT Hub 実環境で device-to-cloud message の受信確認を行う。
- dump1090-fa 由来 payload とデモ payload の共通化を進める。
