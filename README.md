# HEPTA_GSApp

HEPTA ground station UIです。GitHubの「Download ZIP」で取得して展開した場合でも、Node.jsが入っていれば起動できます。

## 起動方法

コマンドプロンプトでこのフォルダを開いて、次を実行します。

```bat
npm start
```

PowerShellで `npm.ps1` の実行ポリシーエラーが出る場合は、次のどちらかで起動してください。

```bat
npm.cmd start
```

または、同梱の `start.bat` をダブルクリックしてください。

起動するとブラウザが開きます。開かない場合は、コマンドプロンプトに表示されるURLをChromeまたはEdgeで開いてください。

## 必要なもの

- Node.js / npm
- Chrome または Edge
- XBee / USBシリアルドライバ

## 接続方法

ブラウザが開いたら、画面下部の接続ボタンからXBeeのシリアルポートを選択してください。

## 補足

- `node_modules/` はGitHub zipには含めません。
- UIで必要なブラウザ用ライブラリは `vendor/` とルート直下のJSファイルに同梱しています。
- `npm install` は通常不要です。依存関係を更新したい場合だけ実行してください。
