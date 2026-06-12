# HEPTA_GSApp

HEPTA ground station UIです。

## いちばん簡単な起動方法

GitHubの「Download ZIP」で取得して展開したら、展開したフォルダの中にある `start.bat` をダブルクリックしてください。

## コマンドで起動する方法

`npm start` は、必ず `package.json` があるフォルダで実行してください。

例:

```bat
cd /d C:\Users\User\Downloads\HEPTA_GSApp-main
npm.cmd start
```

フォルダ名は、実際にzipを展開した場所に合わせて変更してください。

悪い例:

```bat
C:\>npm start
```

この場合、npmは `C:\package.json` を探すため、`ENOENT Could not read package.json` になります。

## 必要なもの

- Node.js / npm
- Chrome または Edge
- XBee / USBシリアルドライバ

## 接続方法

起動するとブラウザが開きます。開かない場合は、コマンドプロンプトに表示されるURLをChromeまたはEdgeで開いてください。

ブラウザが開いたら、画面下部の接続ボタンからXBeeのシリアルポートを選択してください。

## 補足

- `node_modules/` はGitHub zipには含めません。
- UIで必要なブラウザ用ライブラリは `vendor/` とルート直下のJSファイルに同梱しています。
- `npm install` は通常不要です。依存関係を更新したい場合だけ実行してください。
