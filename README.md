# HEPTA_GSApp

## 受信スクリプト

`receive_data.py` は XBee 受信データを標準出力に表示し、最新データを `data.json` に書き込みます。

```powershell
python receive_data.py -p COM18
```

`-p/--port` を省略した場合は、`SERIAL_PORT` 環境変数または接続済みシリアルポートを使います。複数ポートがある場合は、明示的に `-p` を指定してください。