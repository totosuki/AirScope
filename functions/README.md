# AirScope Functions

`functions` は、Azure IoT Hub に届いた AirScope telemetry を処理し、Cosmos DB に raw telemetry と current aircraft snapshot を保存するAzure Functionsアプリです。Cosmos DBから表示用データを読み取り、HTTP APIとして返す処理も管理します。

## 役割

- IoT Hub built-in endpoint を Event Hubs 互換 trigger で読む。
- 受信した payload を `telemetry` container に raw item として保存する。
- `session_id` と `icao24` ごとの最新状態を `current_aircraft` container に upsert する。
- 古い telemetry で current snapshot が巻き戻らないように `freshness_at` を比較する。
- 対象sessionのcurrent snapshotを読み、応答時点の鮮度を再判定してexpiredを除外する。
- 対象sessionの最新telemetryを件数上限付きで読み取る。
- HTTP Triggerで現在機体と最新telemetryをJSON APIとして返す。

## Cosmos DB読み取りロジック

`airscope_query.py` はHTTP triggerから独立した読み取り処理です。

- `read_current_aircraft`: `/session_id`をpartition keyとしてcurrent snapshotを取得し、`current` / `stale`を再判定する。
- `read_recent_telemetry`: `/session_id`をpartition keyとして、最新telemetryを既定50件、最大200件取得する。
- `validate_session_id`: session IDの必須性、長さ、使用可能文字を検証する。
- `validate_telemetry_limit`: telemetry取得件数を検証する。

query parameterはCosmos DBのparameterized queryとして渡し、Cosmos DBの内部フィールドは返却データから除外します。HTTP statusやJSON envelopeへの変換は`airscope_http.py`、Azure Functions固有のrequest/response変換は`function_app.py`が担当します。

## HTTP API

| Method | Route | 用途 |
| --- | --- | --- |
| GET | `/api/aircraft/current?session_id=<session-id>` | 1sessionの表示可能な最新機体を取得する |
| GET | `/api/telemetry/recent?session_id=<session-id>&limit=50` | 1sessionの最新telemetryを取得する |

両endpointは`FUNCTION` authorization levelで、responseには`Cache-Control: no-store`を付けます。入力不正は400、0件は200と空配列、予期しない内部エラーは詳細を伏せた500を返します。ローカルFunctions hostは既定でauthorizationを強制しませんが、Azure上で直接呼ぶ場合はfunction keyが必要です。

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
| `AIRSCOPE_CURRENT_THRESHOLD_SECONDS` | current 判定秒数。Web経路のテスト中の既定: `86400`（1日） |
| `AIRSCOPE_STALE_THRESHOLD_SECONDS` | stale 判定上限秒数。Web経路のテスト中の既定: `86400`（stale期間なし） |

Web表示経路を構築している間は、デモデータを確認しやすいよう、`freshness_at`から1日以内の機体を`current`として扱います。1日を超えた機体は`expired`です。実際のリアルタイム運用へ移る際は、App Settingsを例えば`30`と`120`へ変更し、受信環境に合わせて再調整します。

## ローカルでのロジック検証

Azure Functions runtime や Cosmos DB なしで、payload 変換ロジックだけを検証できます。

```sh
python -m unittest discover -s functions/tests
```

Azure Functions として動かす場合は、`requirements.txt` の依存関係をインストールし、`local.settings.json` にローカル用の設定を入れてから Functions Core Tools で起動します。`local.settings.json` には秘密情報が入るため、コミットしません。
