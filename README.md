# HEPTA_GSApp

## 起動手順

このブランチでは VS Code と Python は不要です。
Windows のコマンドプロンプトだけで起動できます。

```bat
npm install
npm start
```

ブラウザが開いたら、画面下部の接続ボタンから XBee のシリアルポートを選択してください。

## 必要なもの

- Node.js / npm
- Chrome または Edge
- XBee / USB シリアルドライバ

## RSSI 表示

RSSI は実測値ではなく、UI 内で生成したシミュレーション値を表示します。
Python や RSSI 取得用の追加ライブラリは使用しません。
