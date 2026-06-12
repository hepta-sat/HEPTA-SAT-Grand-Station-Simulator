# HEPTA_GSApp

HEPTA Ground Station Simulator.

このブランチは Python / pyserial で XBee を受信し、XBee の ATDB から取得した実測 RSSI を UI に表示します。

## 必要なもの

- Python 3
- pyserial
- Chrome または Edge
- XBee / USB シリアルドライバ

## セットアップ

```sh
python -m pip install pyserial
```

## 起動方法

ターミナルを2つ開きます。

### 1. UI サーバを起動

```sh
npm start
```

ブラウザが開かない場合は、ターミナルに表示された URL を Chrome または Edge で開いてください。

### 2. Python 受信バックエンドを起動

Windows の例:

```sh
python receive_data.py -p COM3 --rssi-atdb-interval 5
```

macOS の例:

```sh
python3 receive_data.py -p /dev/tty.usbserial-XXXX --rssi-atdb-interval 5
```

`-p` の値は環境に合わせて変更してください。ポートを1つだけ検出できる環境では、`-p` を省略できます。

## UI での接続

ブラウザ画面下部の「接続」を押すと、Python バックエンドへの接続確認をします。

このブランチでは UI の Web Serial ではなく、`receive_data.py` が pyserial でシリアルポートを開きます。

## RSSI 表示

RSSI は UI 内のシミュレーション値ではなく、`receive_data.py` が XBee に `+++` → `ATDB` → `ATCN` を送って取得した実測値を表示します。

取得間隔は `--rssi-atdb-interval` で指定します。`0` を指定すると ATDB ポーリングを無効化します。

例:

```sh
python receive_data.py -p COM3 --rssi-atdb-interval 2
```
