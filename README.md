# HEPTA_GSApp

HEPTA Ground Station Simulator です。
GitHub の Download ZIP などで取得して展開したあと、OS に合った起動ファイルをダブルクリックしてください。

## 起動方法

### Windows

展開したフォルダ内の `start.bat` をダブルクリックしてください。

Windows 用 Node.js は `tools/node/win-x64/node.exe` に同梱しています。
通常は Node.js / npm / Python / VS Code のインストールは不要です。

### macOS

展開したフォルダ内の `start.command` をダブルクリックしてください。

macOS 用 Node.js は次の場所に同梱しています。

- Apple Silicon Mac: `tools/node/darwin-arm64/node`
- Intel Mac: `tools/node/darwin-x64/node`

そのため、通常は macOS 側に Node.js や Python をインストールしていなくても起動できます。

もし「開発元を検証できません」などの警告が出る場合は、Finder で `start.command` を右クリックして「開く」を選んでください。
もし「権限がありません」と表示される場合は、ターミナルで展開したフォルダへ移動して次を1回だけ実行してください。

```sh
chmod +x start.command
```

GitHub の Download ZIP から取得した場合は、通常この操作は不要です。

## コマンドで起動する場合

通常は `start.bat` または `start.command` を使ってください。
コマンドで起動する場合は、必ず展開したフォルダに移動してから実行します。

```sh
npm start
```

ただし、`npm start` はローカルに Node.js が入っている場合だけ使えます。
環境構築なしで起動したい場合は、同梱 Node.js を使う `start.bat` / `start.command` を使ってください。

## 必要なもの

- Chrome または Edge
- XBee / USB シリアルドライバ

## 接続方法

起動するとブラウザが開きます。
開かない場合は、ターミナルまたはコマンドプロンプトに表示された URL を Chrome または Edge で開いてください。

画面下部の「ポート選択」から XBee のシリアルポートを選び、「接続」を押してください。

## 補足

- `node_modules/` は不要です。
- UI で必要なブラウザ用ライブラリは、`vendor/` とルート直下の JS ファイルに同梱しています。
- Windows / macOS 用の Node.js 実行ファイルは `tools/node/` に同梱しています。
- macOS の `start.command` は、CPU 種別に合わせて同梱 Node.js を自動選択します。
