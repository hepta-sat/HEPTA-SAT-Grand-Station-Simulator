# HEPTA_GSApp

HEPTA ground station UIです。WindowsではNode.jsをインストールしなくても、zipを展開して `start.bat` を実行するだけで起動できます。

## いちばん簡単な起動方法

GitHubの「Download ZIP」で取得して展開したら、展開したフォルダの中にある `start.bat` をダブルクリックしてください。

Windows用のポータブルNode.jsを同梱しているため、通常はNode.js / npm / Python / VS Codeのインストールは不要です。

## コマンドで起動する方法

`npm start` は通常不要です。コマンドで起動したい場合も、基本は `start.bat` を実行してください。

例:

```bat
cd /d C:\Users\User\Downloads\HEPTA_GSApp-main
start.bat
```

フォルダ名は、実際にzipを展開した場所に合わせて変更してください。

悪い例:

```bat
C:\>npm start
```

この場合、npmは `C:\package.json` を探すため、`ENOENT Could not read package.json` になります。`start.bat` を使うと、この問題を避けられます。

## 必要なもの

- Chrome または Edge
- XBee / USBシリアルドライバ

## 接続方法

起動するとブラウザが開きます。開かない場合は、コマンドプロンプトに表示されるURLをChromeまたはEdgeで開いてください。

ブラウザが開いたら、画面下部の接続ボタンからXBeeのシリアルポートを選択してください。

## 補足

- `node_modules/` はGitHub zipには含めません。
- UIで必要なブラウザ用ライブラリは `vendor/` とルート直下のJSファイルに同梱しています。
- Windows用の同梱Node.jsは `tools/node/win-x64/node.exe` にあります。
- `npm install` は不要です。
