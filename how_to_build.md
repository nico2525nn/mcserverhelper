# ビルドする方法

- Python環境構築済みを前提とする

- Pythonビルド用に```pyinstaller```をインストール
```
pip install pyinstaller
```

- このコマンドを使用してビルド（ファイルに応じて変更）

```
pyinstaller --onefile --name "MCServerHelper" --add-data "static;static" --add-data "templates;templates" --add-data "requirements.txt;."  app.py
```

### インストーラー形式は現在サポートしていません

- NSISのインストール
https://nsis.sourceforge.io/Download

- ```installer.nsi```のバージョンなどを確認したら、```installer.nsi```を右クリックして「Compile NSIS Script」
をクリックすればOK