# AirScope

AirScope は、Raspberry Pi 4 と RTL-SDR で受信した ADS-B 航空機データを Azure に送信・蓄積し、Web ダッシュボードでリアルタイム可視化するためのモノレポです。受信データは AirScope 本体の処理とは独立して、fr24feed により Flightradar24 へも提供できる構成を目指します。

## 目的

- Raspberry Pi 4 + RTL-SDR + dump1090-fa で ADS-B 1090 MHz の航空機情報を受信する。
- 受信データを整形し、Azure IoT Hub 経由で Cosmos DB に蓄積する。
- Azure Static Web Apps 上の Next.js ダッシュボードで、航空機の現在位置、軌跡、受信ログ、統計を可視化する。
- fr24feed を Raspberry Pi 上で並行動作させ、Flightradar24 へ受信データを提供する。

## 全体構成

```text
Raspberry Pi 4
  ├─ RTL-SDR V4 + 1090 MHz antenna
  ├─ dump1090-fa
  ├─ AirScope edge collector
  │    └─ Azure IoT Hub / demo HTTP endpoint
  └─ fr24feed

Azure
  ├─ IoT Hub
  ├─ telemetry ingest
  ├─ Cosmos DB
  └─ Static Web Apps + Next.js dashboard
```

AirScope の Azure パイプラインと fr24feed は独立させます。fr24feed の認証情報や受信局固有情報は、このリポジトリには含めません。

## モノレポ構成

```text
AirScope/
├── AGENTS.md
├── README.md
├── docs/
│   └── 設計/
│       └── データベース設計.md
├── documents/
│   └── yyMMdd/
│       └── 001-書類名の例.md
├── edge/
├── functions/
├── fr24/
└── web/
```

`edge` は Raspberry Pi での受信から Azure IoT Hub 送信まで、`functions` は IoT Hub から Cosmos DB への取り込み、`fr24` は Flightradar24 contribute 関連、`web` は Azure Static Web Apps 上の可視化アプリを管理します。`docs` は Git 管理する正式書類、`documents` は Git 管理しないローカル作業記録です。Azure IaC、共通パッケージ、リポジトリ横断スクリプトは、必要になった段階で追加します。

## Phase 0: リポジトリ基盤

Phase 0 では、実装を始めるための土台を整えます。

- README と開発方針を整備する。
- モノレポのディレクトリ構成を作成する。
- ADS-B テレメトリのサンプル JSON と共通スキーマを用意する。
- 秘密情報をコミットしないための `.env.example` と `.gitignore` を整備する。
- Raspberry Pi からデモデータを送信する最小構成を作る。

## Devcontainer

このリポジトリには軽量な devcontainer を用意しています。Python 3.12 と Node.js 22 を揃え、`edge` の Python 開発と `web` の Next.js 開発を同じ環境で始められるようにします。

Azure CLI、Azure Functions Core Tools、Static Web Apps CLI は初期 devcontainer には含めません。必要になった段階で追加します。

想定用途:

- `edge` のデモ送信処理をローカルで動かす。
- `web` の開発サーバーを動かす。
- サンプル JSON やスキーマ検証を同じ Python / Node.js バージョンで実行する。

devcontainer では RTL-SDR 実機受信、dump1090-fa の実受信確認、fr24feed の本番稼働、Raspberry Pi 固有の systemd 確認は行いません。これらは Raspberry Pi 実機で検証します。

## 次の実装: Raspberry Pi デモ送信

次に作るべき最小機能は、Raspberry Pi からデモ ADS-B データを送信する `edge` です。

最初は実機の dump1090-fa に依存せず、サンプル JSON からテレメトリを生成して送信します。送信先は次の2系統を想定します。

- `azure-iot-hub`: Azure IoT Hub へ MQTT または Azure SDK で送信する。
- `http`: 任意の IP アドレスまたは URL に HTTP POST で送信する。

これにより、Azure 構成が未完成でも、手元の受信サーバーや検証用 API に対して送信処理を確認できます。

想定する最小コマンドは次の形です。

```sh
python edge/send_demo_adsb.py --dry-run --count 2 --interval 0
python edge/send_demo_adsb.py --endpoint http://192.168.1.10:8080/telemetry --count 5
```

Azure IoT Hub 送信は `--transport azure-iot-hub` で実行します。IoT Hub 接続文字列、デバイス ID、任意 HTTP エンドポイントなどは環境変数またはローカルの `.env` で渡します。実値はコミットしません。

```sh
python -m pip install -e edge
export AIRSCOPE_IOTHUB_DEVICE_CONNECTION_STRING='HostName=...;DeviceId=...;SharedAccessKey=...'
python edge/send_demo_adsb.py --transport azure-iot-hub --count 5
```

## ドキュメント運用

`documents` ディレクトリはローカル書類置き場として扱い、Git には載せません。AI に書類作成を依頼する場合のみ、`documents/yyMMdd/<連番>-<内容>.md` に記録します。書類作成・更新時は、毎回現在日付を確認します。

実装と一緒に継続保守する正式な設計書、仕様書、運用手順書は `docs` に配置して Git 管理します。

例:

```text
documents/260608/001-AirScope初期計画.md
documents/260608/002-ディレクトリ構成方針.md
```

## 開発メモ

- 当面は `main` ブランチのみで開発します。
- Issue と Pull Request は使用しません。
- 受信専用システムとして扱い、送信機能や無線機制御機能は追加しません。
- ADS-B データは公開ブロードキャストですが、運航安全や個人追跡を目的とした用途には使いません。
