# ビルドする方法

- Python環境構築済みを前提とする

- Pythonビルド用に`pyinstaller`をインストール
```bash
pip install pyinstaller
```

- このコマンドを使用してビルド（ファイルに応じて変更）

```bash
pyinstaller --onefile --name "MCServerHelper" --add-data "static;static" --add-data "templates;templates" --add-data "requirements.txt;." --add-data "server_software_api.py;." --add-data "modrinth_api.py;." --hidden-import="simple_websocket" --hidden-import="engineio.async_drivers.threading" --hidden-import="flask_socketio" --hidden-import="charset_normalizer" --hidden-import="certifi" --hidden-import="xml.etree.ElementTree" --hidden-import="server_software_api" --hidden-import="modrinth_api" --collect-all="flask_socketio" --collect-all="simple_websocket" app.py
```

**追加された主な変更点:**
- `--add-data "server_software_api.py;."` - サーバーソフトウェアAPIモジュール
- `--add-data "modrinth_api.py;."` - Modrinth APIモジュール
- `--hidden-import="xml.etree.ElementTree"` - NeoForge/ForgeのXMLパース用
- `--hidden-import="server_software_api"` - サーバーソフトウェアAPIの明示的インポート
- `--hidden-import="modrinth_api"` - Modrinth APIの明示的インポート
- `--collect-all="flask_socketio"` - Flask-SocketIOのリソース一括収集
- `--collect-all="simple_websocket"` - simple-websocketのリソース一括収集

### インストーラー形式は現在サポートしていません

- NSISのインストール
https://nsis.sourceforge.io/Download

- `installer.nsi`のバージョンなどを確認したら、`installer.nsi`を右クリックして「Compile NSIS Script」をクリックすればOK