# AirScope Edge

`edge` は、Raspberry Pi での ADS-B データ受信から Azure IoT Hub 送信までを管理する領域です。

スクリプトは2種類あります。

- `send_adsb.py`: RTL-SDR で受信し dump1090-fa がデコードした実データ (`aircraft.json`) を読み取り、Azure IoT Hub へ送信します。
- `send_demo_adsb.py`: 実機に依存せず ADS-B 風のデモテレメトリを生成して送信します。パイプラインの初期確認用です。

どちらも `airscope_telemetry.py` の共通 payload envelope と共通 transport (HTTP / Azure IoT Hub) を利用するため、送信される JSON 構造は同一です。

## dump1090-fa 実データ送信

`send_adsb.py` は dump1090-fa の `aircraft.json` を読み取り、機体1件ごとに AirScope テレメトリを生成して Azure IoT Hub へ送信します。`aircraft.json` はローカルファイル (既定 `/run/dump1090-fa/aircraft.json`) または HTTP フィード (例: `http://localhost:8080/data/aircraft.json`) から取得できます。

事前に `edge` の Python 依存関係をインストールし、デバイス接続文字列を環境変数で渡します。実値はリポジトリに保存しません。

```sh
python -m pip install -e edge
export AIRSCOPE_IOTHUB_DEVICE_CONNECTION_STRING='HostName=...;DeviceId=...;SharedAccessKey=...'
```

ローカルファイルから1回だけ読み取り、Azure IoT Hub へ送信する場合:

```sh
python edge/send_adsb.py --receiver-id airscope-rpi
```

Raspberry Pi 上で継続受信・送信する場合 (`Ctrl-C` で停止):

```sh
python edge/send_adsb.py --follow --interval 1 \
  --receiver-id airscope-rpi \
  --receiver-lat 35.55 --receiver-lon 139.78
```

`--receiver-lat` と `--receiver-lon` を渡すと、受信地点から各機体までの距離を `distance_km` として付与します。位置のある機体だけを送る場合は `--require-position` を使います。

送信せずに payload を確認する場合:

```sh
python edge/send_adsb.py --dry-run --source-file edge/tests/sample_aircraft.json
```

ローカル検証用に、Azure IoT Hub の代わりに任意 HTTP エンドポイントへ送ることもできます。

```sh
python edge/send_adsb.py --transport http \
  --endpoint http://192.168.1.10:8080/telemetry \
  --source-url http://localhost:8080/data/aircraft.json
```

### dump1090-fa フィールドの対応

| AirScope telemetry | dump1090-fa aircraft.json | 補足 |
| --- | --- | --- |
| `icao24` | `hex` | 大文字化。非 ICAO の `~` 接頭辞は除去 |
| `callsign` | `flight` | 前後空白を除去。空なら `null` |
| `lat`, `lon` | `lat`, `lon` | 位置未確定なら `null` |
| `altitude_ft` | `alt_baro`（無ければ `alt_geom`） | `"ground"` は `0` |
| `ground_speed_kt` | `gs` | 四捨五入 |
| `track_deg` | `track` | 四捨五入 |
| `vertical_rate_fpm` | `baro_rate`（無ければ `geom_rate`） | |
| `squawk` | `squawk` | |
| `seen_at` | `now - seen` | 最後に受信した時刻 |
| `received_at` | edge 取得時刻 | このスクリプトが読み取った時刻 |
| `distance_km` | 受信局座標から算出 | `--receiver-lat/lon` 指定時のみ |

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

- Raspberry Pi 実機の dump1090-fa と RTL-SDR で `send_adsb.py` の受信・送信を確認する。
- Azure IoT Hub 実環境で device-to-cloud message の受信、および Cosmos DB への取り込みを確認する。
- Raspberry Pi 上で `send_adsb.py --follow` を systemd サービスとして常駐させる構成を検討する。
- 常時運用時の送信量・鮮度しきい値・セッション運用方針を実データで再調整する。
