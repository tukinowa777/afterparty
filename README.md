# 二次会居酒屋ファインダー

夜9時以降に入れる二次会向け居酒屋を、現在地や駅を起点に探せるスマートフォン向け Web アプリです。

## 使い方

1. `python3 server.py --port 8123` を実行する
2. PC では `http://localhost:8123` を開く
3. iPhone / Android では、同じ Wi-Fi 上でこのPCのLAN IPに `:8123` を付けて開く
4. 必要なら「現在地を使う」で位置情報を許可する
5. 現在地検索か駅検索を選ぶ
6. 人数、予算、料理ジャンル、移動距離を指定する
7. 条件に合う候補を最大3件確認する

例: `http://192.168.1.10:8123`

## HTTPS 起動

- `bash scripts/start_https.sh` を実行する
- 外部向けURLは `https://161.33.151.114:8443`
- 自己署名証明書のため、初回はブラウザ警告が出ます
- 常駐起動する場合は `bash scripts/run_public_https.sh`
- 停止する場合は `bash scripts/stop_public_https.sh`

## 補足

スマホで現在地取得を安定させるなら HTTPS 配信が望ましいです。このリポジトリでは `scripts/start_https.sh` で自己署名 HTTPS を起動できますが、実運用では正式証明書つきのドメイン運用が望ましいです。

## 現在の開発状況

- フロント画面と条件検索は実装済み
- 現在地取得による再計算に対応済み
- 銀座線、丸ノ内線、山手線、田園都市線の駅を選んで検索できる
- 店舗データは `data/venues.json` に分離済み
- `server.py` から `GET /api/venues` で条件付き検索を返す簡易 API を追加済み
- OpenStreetMap / Overpass の無料データ取得に対応し、失敗時はサンプルデータへフォールバック
- DB、認証、予約 API 連携は未実装

## 構成

- `index.html`: 画面構造
- `styles.css`: レイアウトと見た目
- `app.js`: API 読み込み、現在地取得、絞り込み、描画
- `server.py`: 静的配信と簡易 API
- `data/venues.json`: 店舗データ
- `data/stations.json`: 駅一覧データ
- `DEVELOPMENT.md`: 継続開発メモ

現在は OpenStreetMap / Overpass の無料データ取得を優先し、取得できない場合はローカルのサンプル店舗データで動作します。
