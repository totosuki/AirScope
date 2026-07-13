# AirScope Web ダッシュボード

`web`は、AirScopeがAzure Cosmos DBへ保存したADS-B航空機情報を、Azure Static Web Apps上で可視化するNext.jsアプリケーションである。

本READMEの計画に基づき、Next.js、shadcn/ui、Leaflet、Chart.jsを使用した初期ダッシュボードを実装している。

## 実装状況

- Web Step 3-1: 完了。Next.js App Router、TypeScript、shadcn/ui、Vitest、静的exportを構成済み。
- Web Step 3-2: 完了。2つのHTTP API、応答検証、3秒polling、loading・empty・error表示を実装済み。
- Web Step 3-3: 完了。高度帯別marker、機体選択、詳細表示を備えたLeaflet地図を実装済み。
- Web Step 3-4: 完了。最新telemetry一覧と高度帯別Chart.jsグラフを実装済み。
- Web Step 3-5: 未着手。Azure Static Web Appsの作成と認証方式の確定が必要。

ローカル起動時はAzure Functionsを`localhost:7071`で起動し、別terminalで次を実行する。

```sh
cd web
cp .env.example .env.local
npm install
npm run dev
```

ブラウザで`http://localhost:3000/?session_id=demo-session`を開く。本番ではAPI base URLを未指定にするとsame-originの`/api`を使用する。Function keyを公開環境変数へ設定してはならない。URLに`session_id`を指定すると、その値を使ってAPIを取得する。

## 1. 目的

- `current_aircraft`の最新機体を地図上へ表示する。
- 機体数、API更新時刻、接続状態を一目で確認できるようにする。
- 機体のcallsign、ICAO 24-bit address、高度、速度、進行方向、最終観測時刻を確認できるようにする。
- `telemetry`の最新受信履歴を一覧表示する。
- 将来は高度帯、受信距離、機体数などの統計をChart.jsで表示する。
- desktopとmobileの両方で、受信状況を無理なく確認できるUIにする。

AirScopeは受信専用の実験・可視化システムである。画面には、公開ブロードキャストの受信結果であり、運航安全や個人追跡を目的としない旨を明記する。

## 2. 現在の前提

2026-06-29時点で、次の経路は動作確認済みである。

```text
デモsender
  -> Azure IoT Hub
    -> Azure Functions
      -> Cosmos DB
        ├─ current_aircraft
        └─ telemetry
          -> Azure Functions HTTP API
```

テスト用の`session_id`は`demo-session`で、30件のデモデータがCosmos DBに保存されている。

利用するHTTP API:

| Method | Route | 用途 |
| --- | --- | --- |
| GET | `/api/aircraft/current?session_id=demo-session` | 表示可能な最新機体を取得する |
| GET | `/api/telemetry/recent?session_id=demo-session&limit=50` | 最新telemetryを取得する |

Web経路のテスト中は、`freshness_at`から1日以内の機体を`current`として扱い、1日を超えた機体はAPIで除外する。実機運用へ移る段階で、30秒/120秒などの短い判定へ戻す。

## 3. 技術構成

| 分類 | 採用候補 | 方針 |
| --- | --- | --- |
| Framework | Next.js App Router | TypeScriptと`src/`構成を使う |
| Rendering | Static export | `next.config.ts`で`output: "export"`を指定する |
| Runtime | Node.js 22 | repositoryのdevcontainer方針に合わせる |
| Package manager | npm | `package-lock.json`をGit管理する |
| UI components | shadcn/ui | 必要なcomponentだけを追加し、AirScope向けに調整する |
| Styling | Tailwind CSS、CSS variables | shadcn/uiのtokenを基準にする |
| Icons | Lucide | shadcn/uiと一貫したiconを使う |
| Map | Leaflet、React Leaflet | browser専用componentとして読み込む |
| Charts | Chart.js | 地図とAPI経路の完成後に追加する |
| Unit/component test | Vitest、Testing Library | 状態表示とデータ変換を検証する |
| E2E | Playwright | Azure接続前はmock、公開後は主要経路だけ確認する |
| Hosting | Azure Static Web Apps | build成果物は`out/`とする |

Static exportを選ぶ理由:

- 画面はbrowserから既存Azure Functions APIをpollingすれば成立する。
- SSR、Server Actions、Next.js Route Handlerを初期実装で必要としない。
- Azure Static Web Appsの静的配信と既存Functions backendを分離できる。
- build成果物とruntime責務が明確になる。

## 4. shadcn/uiの使用方針

shadcn/uiはcomponentのsource codeを`web`内へ追加して所有する方式で使う。npm packageから完成済み画面をそのまま表示するのではなく、必要なcomponentを選び、アクセシビリティを保ちながらAirScope向けに組み合わせる。

初期導入候補:

| Component | 用途 |
| --- | --- |
| `Card` | 機体数、更新時刻、受信状態のsummary |
| `Badge` | current/stale、接続状態、高度帯 |
| `Button` | 手動更新、再試行、panel操作 |
| `Select` | session切り替え。初期は`demo-session`固定でもよい |
| `Table` | 最新telemetry一覧 |
| `Sheet` | mobileの機体詳細・機体一覧 |
| `Alert` | API失敗、更新停止、設定不足 |
| `Skeleton` | 初回loading |
| `Tooltip` | icon button、地図操作の補助説明 |
| `Separator` | panel内の情報整理 |

デザイン原則:

- 地図と航空機情報を主役にし、装飾を増やしすぎない。
- 色だけで状態を伝えず、labelやiconも併用する。
- shadcn/uiのCSS variablesでlight/dark両方に対応できるtokenを定義する。
- 最初から独自の巨大なdesign systemを作らず、使用componentが増えた段階でtokenを整理する。
- 航空機markerと高度色は、背景地図上で判別できるcontrastを確保する。
- 外部画像や自動生成した装飾assetは初期実装で使用しない。

## 5. 初期画面計画

### 5.1 Dashboard `/`

最初に作る主画面。desktopでは地図を中央に大きく配置し、上部にsummary、右側または下部に機体情報を置く。

```text
+----------------------------------------------------------+
| AirScope | session | 接続状態 | 最終更新 | 手動更新       |
+----------------------------------------------------------+
| 機体数 Card | current Card | API状態 Card               |
+--------------------------------------+-------------------+
|                                      | 機体一覧/詳細      |
|              Leaflet map             | callsign          |
|                                      | altitude / speed  |
|                                      | freshness         |
+--------------------------------------+-------------------+
| 最新telemetry table                                      |
+----------------------------------------------------------+
| 注意事項・データ利用方針                                 |
+----------------------------------------------------------+
```

mobileでは地図を先に表示し、機体一覧と詳細は`Sheet`で開く。summary cardは横scrollさせず、2列または縦積みにする。

### 5.2 初期表示項目

- 表示中の`session_id`
- API接続状態
- 表示中の機体数
- API responseの`generated_at`
- browserが最後に取得成功した時刻
- polling失敗回数または「更新停止」状態
- 航空機marker
- 選択した機体の詳細
- 最新telemetry一覧

### 5.3 航空機詳細

- callsign。欠損時は`—`
- `icao24`
- 緯度・経度
- 高度（ft）
- 対地速度（kt）
- 進行方向（degree）
- 垂直速度（ft/min）
- squawk
- 受信地点からの距離（km）
- `freshness_at`
- 最終観測からの経過時間
- current/stale status

## 6. データ取得方針

### 6.1 API client

API request、response validation、error変換は`src/lib/api/`へ集約し、React component内へ直接散らさない。

想定する型:

```ts
type AircraftStatus = "current" | "stale";

type Aircraft = {
  icao24: string;
  callsign: string | null;
  lat: number;
  lon: number;
  altitude_ft: number | null;
  ground_speed_kt: number | null;
  track_deg: number | null;
  vertical_rate_fpm: number | null;
  squawk: string | null;
  freshness_at: string;
  receiver_id: string | null;
  distance_km: number | null;
  status: AircraftStatus;
};

type CurrentAircraftResponse = {
  session_id: string;
  generated_at: string;
  aircraft: Aircraft[];
};
```

API responseは信用しきらず、少なくとも必須fieldと型をclient境界で検証する。validation libraryの追加は、手書きguardより保守性が上がると判断した場合に限定する。

### 6.2 Polling

- current aircraftは初期値3秒間隔で取得する。
- 同じrequestが重複しないよう、前回request中は次を開始しない。
- component unmount時にtimerとrequestを停止する。
- `AbortController`で古いrequestを破棄できるようにする。
- 失敗時に既存データを即座に消さず、画面を「更新停止」として明示する。
- 連続失敗時はbackoffを検討し、無制限に3秒requestを続けない。
- browser tabが非表示の間はpolling頻度を落とすか停止する。

初期段階では専用data-fetching libraryを追加せず、小さなcustom hookで要件を確認する。cache、deduplication、再接続処理が複雑になった場合にSWRまたはTanStack Queryを再評価する。

### 6.3 時刻

- APIとの交換はUTC ISO 8601を維持する。
- UIでは日本時間と「n秒前」を併記できるようにする。
- `generated_at`はAPIの生成時刻、browser側の取得成功時刻は通信を含む画面更新時刻として分ける。

## 7. API認証と環境変数

現在のAzure Functions HTTP Triggerは`FUNCTION` authorization levelである。function keyを`NEXT_PUBLIC_*`へ入れるとbrowser bundleから閲覧できるため、採用してはならない。

本番接続は、Web実装と並行して次のどちらかへ確定する。

### 推奨: Static Web Apps Standard＋linked backend

- 既存Function AppをStatic Web Appsへlinkする。
- browserはsame-originの`/api/...`を呼ぶ。
- Static Web Apps側でroute accessを管理する。
- linked backendの認証構成に合わせ、Function keyをbrowserへ渡さずに済むようHTTP Triggerのauthorizationを再設計する。

### 代替: Static Web Apps Free＋Functions URL

- Functions側CORSをStatic Web Appsのoriginへ限定する。
- browserへ公開できるのはAPI base URLだけとする。
- function keyが必要な現在のままでは安全に直接呼べないため、API Management等の安全な境界を追加するか、Functions/App Service認証を再設計する。

ローカル開発では、Functions hostを`localhost:7071`で起動し、Next.jsからそこへ接続する。local Functions hostは通常authorizationを強制しない。

予定する公開可能な環境変数:

```text
NEXT_PUBLIC_AIRSCOPE_API_BASE_URL=http://localhost:7071
NEXT_PUBLIC_AIRSCOPE_SESSION_ID=demo-session
```

`NEXT_PUBLIC_AIRSCOPE_SESSION_ID`はURLの`session_id`が未指定の場合のfallbackである。通常は次のようにURLで対象sessionを指定する。

```text
http://localhost:3000/?session_id=demo-session
https://<static-site-host>/?session_id=live-rpi-20260713
```

クエリパラメータが環境変数より優先される。秘密値を`web/.env.example`へ記載しない。`.env.local`はGit管理しない。

## 8. 想定ディレクトリ構成

実装後の候補であり、必要になるまで空directoryは作らない。

```text
web/
├── README.md
├── package.json
├── package-lock.json
├── next.config.ts
├── components.json
├── public/
├── src/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── dashboard/
│   │   ├── map/
│   │   └── ui/                  # shadcn/ui components
│   ├── hooks/
│   │   └── use-current-aircraft.ts
│   └── lib/
│       ├── api/
│       ├── format/
│       └── utils.ts
└── tests/
```

## 9. Component境界

| Component候補 | 責務 |
| --- | --- |
| `DashboardShell` | page全体のlayout |
| `StatusHeader` | session、API状態、更新時刻、手動更新 |
| `SummaryCards` | 機体数などのsummary |
| `AircraftMap` | Leaflet mapとmarker描画 |
| `AircraftMarker` | 位置、track、高度色、選択event |
| `AircraftList` | 表示中機体の一覧 |
| `AircraftDetails` | 選択中機体の詳細 |
| `TelemetryTable` | 最新受信履歴 |
| `ConnectionAlert` | 通信失敗、更新停止、再試行 |
| `EmptyState` | データ0件時の説明 |

LeafletはDOMへ依存するため、map componentをClient Componentとして分離し、必要ならdynamic importでSSR対象外にする。page全体を不用意にClient Componentへしない。

## 10. 状態設計

少なくとも次を見分ける。

| 状態 | UI |
| --- | --- |
| 初回loading | map/list位置にSkeleton |
| 正常・データあり | map、機体一覧、更新時刻 |
| 正常・0件 | sessionと期間を確認するEmptyState |
| request失敗 | Alertと再試行Button |
| 過去データ表示中 | 更新停止labelを表示し、最新と誤認させない |
| response不正 | 一般的なerror表示、詳細は開発log |
| 機体field欠損 | `—`表示。componentを落とさない |

## 11. テスト方針

### Unit test

- API URL生成
- response validation
- UTC/JSTと経過時間のformat
- 高度帯から表示tokenへの変換
- null fieldのfallback

### Component test

- loading、empty、success、error
- polling成功後の更新
- 連続失敗時の更新停止表示
- 機体選択と詳細表示
- Tableのnull表示
- keyboardで操作できること

### E2E

- mock APIでdashboardが表示される。
- `demo-session`の機体がmap/listへ表示される。
- API更新後、同じ`icao24`のmarkerが増殖せず更新される。
- API停止時に接続異常が表示される。
- mobile viewportで詳細Sheetを開ける。

## 12. Accessibility

- iconだけのButtonにはaccessible nameを付ける。
- statusは色だけでなくtextで示す。
- mapだけに情報を閉じず、同じ機体をlistでも選択できるようにする。
- keyboard focusを見失わない。
- Sheet、Tooltip等はshadcn/uiが利用するaccessible primitiveを維持する。
- polling更新のたびにscreen readerへ過剰通知しない。
- motionを追加する場合は`prefers-reduced-motion`を尊重する。

## 13. 実装順

### Web Step 3-1: Project基盤

1. Next.js App Router、TypeScript、ESLint、Tailwind CSS、`src/`構成を初期化する。
2. `output: "export"`を設定する。
3. shadcn/uiを初期化する。
4. 最小限のshadcn/ui componentを追加する。
5. lint、test、build commandを確立する。

完了条件: 初期pageが表示され、`npm run lint`、test、`npm run build`が成功し、`out/`が生成される。

### Web Step 3-2: API接続

1. TypeScript型とAPI clientを実装する。
2. `demo-session`のcurrent aircraftを文字とCardで表示する。
3. loading、empty、errorを実装する。
4. 3秒pollingを実装する。

完了条件: 30件のデモ送信結果から、APIが返すユニークなcurrent aircraftを画面で確認できる。

### Web Step 3-3: Map

1. Leaflet/React Leafletを追加する。
2. marker、track方向、popupを実装する。
3. listとmap選択を同期する。
4. current/stale表示を実装する。

完了条件: markerが増殖せず更新され、選択した機体の詳細を確認できる。

### Web Step 3-4: Telemetry

1. 最新telemetry APIへ接続する。
2. shadcn/ui Tableで表示する。
3. 件数制限、空状態、再取得を実装する。

### Web Step 3-5: Azure Static Web Apps

1. API認証方式とStatic Web Apps planを確定する。
2. Static Web Apps resourceを作成する。
3. `app_location: web`、`output_location: out`、`api_location: ""`でbuildを設定する。
4. 既存Function Appとの接続を設定する。
5. 公開URLでE2E確認する。

## 14. 初期化時の予定command

実装開始時にversionと公式CLI optionを再確認してから実行する。以下は現時点の候補であり、本README作成時には未実行である。

```sh
npx create-next-app@latest web \
  --typescript \
  --eslint \
  --tailwind \
  --app \
  --src-dir \
  --import-alias '@/*'
```

```sh
cd web
npx shadcn@latest init
```

必要なcomponentだけを追加する。

```sh
npx shadcn@latest add card badge button select table sheet alert skeleton tooltip separator
```

既に`web/README.md`が存在するため、scaffold実行前にREADMEを保持できる方法を確認する。CLIによる意図しない上書きは行わない。

## 15. 検証command

実装後は最低限、次を実行する。

```sh
cd web
npm run lint
npm test
npm run build
```

加えて、browserで次を確認する。

- desktop/mobile layout
- map操作
- 3秒polling
- API停止時の表示
- keyboard操作
- browser console errorがないこと

## 16. 未決事項

1. Static Web Apps Standard＋linked backendを使うか、別の安全なAPI公開方式を使うか。
2. HTTP Triggerの`FUNCTION` authorizationを本番接続時にどう置き換えるか。
3. 初期公開を匿名閲覧とするか、Static Web Apps認証を必須とするか。
4. session_idをURLの`session_id`クエリパラメータで指定できるようにするか。実装済み。
5. 地図の初期中心座標。自宅の正確な位置を公開しない。
6. OpenStreetMap tile利用時のattributionと本番traffic方針。
7. current aircraft APIの実際の機体数。30 telemetry件とユニーク機体数は一致しない場合がある。
8. Chart.jsで最初に表示する統計指標。

## 17. 参照資料

- [Next.js App Router](https://nextjs.org/docs/app)
- [Next.js Static Exports](https://nextjs.org/docs/app/building-your-application/deploying/static-exports)
- [shadcn/ui Next.js installation](https://ui.shadcn.com/docs/installation/next)
- [shadcn CLI](https://ui.shadcn.com/docs/cli)
- [Azure Static Web AppsのNext.jsサポート](https://learn.microsoft.com/en-us/azure/static-web-apps/nextjs)
- `functions/README.md`
- `docs/設計/データベース設計.md`
- `documents/260629/001-Static Web Apps表示実装計画.md`
