# AirScope Functions

`functions` は、Azure IoT Hub に届いた AirScope telemetry を処理し、Cosmos DB に raw telemetry と current aircraft snapshot を保存する Azure Functions アプリです。

## 役割

- IoT Hub built-in endpoint を Event Hubs 互換 trigger で読む。
- 受信した payload を `telemetry` container に raw item として保存する。
- `session_id` と `icao24` ごとの最新状態を `current_aircraft` container に upsert する。
- 古い telemetry で current snapshot が巻き戻らないように `freshness_at` を比較する。

## 必要な App Settings

実値は Azure Functions の App settings に保存し、Git 管理ファイルには書きません。

| 名前 | 用途 |
| --- | --- |
| `AIRSCOPE_IOTHUB_EVENTHUB_CONNECTION` | IoT Hub built-in endpoint の Event Hubs 互換接続文字列 |
| `AIRSCOPE_IOTHUB_EVENTHUB_NAME` | IoT Hub の Event Hub-compatible name |
| `AIRSCOPE_IOTHUB_CONSUMER_GROUP` | Functions 用 consumer group。例: `airscope-functions` |
| `AIRSCOPE_COSMOS_ENDPOINT` | Cosmos DB account endpoint |
| `AIRSCOPE_COSMOS_KEY` | Cosmos DB key |
| `AIRSCOPE_COSMOS_DATABASE` | Cosmos DB database id。既定: `airscope` |
| `AIRSCOPE_COSMOS_TELEMETRY_CONTAINER` | raw telemetry container。既定: `telemetry` |
| `AIRSCOPE_COSMOS_CURRENT_CONTAINER` | current snapshot container。既定: `current_aircraft` |
| `AIRSCOPE_CURRENT_THRESHOLD_SECONDS` | current 判定秒数。既定: `30` |
| `AIRSCOPE_STALE_THRESHOLD_SECONDS` | stale 判定秒数。既定: `120` |

## ローカルでのロジック検証

Azure Functions runtime や Cosmos DB なしで、payload 変換ロジックだけを検証できます。

```sh
python -m unittest discover -s functions/tests
```

Azure Functions として動かす場合は、`requirements.txt` の依存関係をインストールし、`local.settings.json` にローカル用の設定を入れてから Functions Core Tools で起動します。`local.settings.json` には秘密情報が入るため、コミットしません。
