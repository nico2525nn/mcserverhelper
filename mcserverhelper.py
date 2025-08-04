import os
import sys
import subprocess
import zipfile
import shutil
from datetime import datetime
import json
import platform
import urllib.request
import tarfile
import threading

# ==== Config loading (.env or config.json) ====
# 設定ファイル: 実行ディレクトリ内の 'mcserve_helper_config.json'
# ワールドデータ: 'world/'
# バックアップ: 'backups/' 内
# EULA 同意ファイル: 'eula.txt'
# PID ファイル: '.mcserve_helper.pid'
CONFIG_FILE = "mcserve_helper_config.json"
DEFAULT_CONFIG = {
    "java_cmd": "java",
    "jar_path": "",
    "world_dir": "world",
    "backup_dir": "backups",
    "ops_file": "ops.json",
    "whitelist_file": "whitelist.json",
    "log_file": "logs/latest.log",
    "eula_file": "eula.txt"
}

# グローバルプロセスオブジェクト
server_proc = None
ownserver_proc = None


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            try:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
            except json.JSONDecodeError:
                print("設定ファイルを読み込めませんでした。初期設定を行います。")
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"設定を '{CONFIG_FILE}' に保存しました。")


def initial_setup():
    print("--- 初回設定 ---")
    cfg = DEFAULT_CONFIG.copy()
    while True:
        jar = input("サーバーのJARファイルのパスを入力してください (例: server.jar): ")
        if jar and os.path.exists(jar):
            cfg['jar_path'] = jar
            break
        else:
            print("指定されたファイルが見つかりません。もう一度入力してください。")
    java = input(f"Java 実行コマンドを指定 (デフォルト: {cfg['java_cmd']}): ")
    if java.strip():
        cfg['java_cmd'] = java.strip()
    save_config(cfg)
    return cfg


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def ensure_eula(cfg):
    eula_path = cfg.get('eula_file', 'eula.txt')
    try:
        with open(eula_path, 'w', encoding='utf-8') as f:
            f.write('# By changing the setting below to TRUE you are indicating your agreement to the EULA\n')
            f.write('eula=true\n')
        print(f"EULAに同意しました: {eula_path}")
    except Exception as e:
        print(f"EULA 同意ファイルの作成に失敗しました: {e}")


def start_server(cfg, xmx="1024M", xms="1024M"):
    global server_proc
    ensure_eula(cfg)
    jar = cfg['jar_path']
    if not os.path.exists(jar):
        print(f"Error: JARファイル '{jar}' が見つかりません。設定を確認してください。")
        return
    if server_proc and server_proc.poll() is None:
        print("サーバーは既に起動しています。")
        return

    # メモリサイズをGB単位で指定
    try:
        max_memory_gb = int(input("最大メモリサイズをGB単位で指定してください (例: 2): "))
        min_memory_gb = int(input("最小メモリサイズをGB単位で指定してください (例: 1): "))
        xmx = f"{max_memory_gb * 1024}M"
        xms = f"{min_memory_gb * 1024}M"
    except ValueError:
        print("無効な入力です。デフォルト値を使用します。")

    # 新しいワールドの場合、ワールドタイプを選択
    world_dir = cfg['world_dir']
    if not os.path.exists(world_dir) or not os.listdir(world_dir):
        ensure_dir(world_dir)  # ワールドディレクトリを作成
        print("新しいワールドを作成します。ワールドタイプを選択してください:")
        print("[1] デフォルト")
        print("[2] スーパーフラット")
        print("[3] アンプリファイド")
        print("[4] 大きなバイオーム")
        print("[5] シングルバイオーム")
        print("[6] デバッグモード")
        choice = input(">> ")
        level_type = {
            '1': "default",
            '2': "flat",
            '3': "amplified",
            '4': "largeBiomes",
            '5': "singleBiome",
            '6': "debug_all_block_states"
        }.get(choice, "default")
        print(f"選択されたワールドタイプ: {level_type}")
        # server.properties ファイルを作成
        with open(os.path.join(world_dir, "server.properties"), 'w', encoding='utf-8') as f:
            f.write(f"level-type={level_type}\n")

    cmd = [cfg['java_cmd'], f"-Xmx{xmx}", f"-Xms{xms}", "-jar", jar, "nogui"]
    server_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    print(f"サーバーを起動しました (PID: {server_proc.pid})")


def stop_server():
    global server_proc
    if server_proc and server_proc.poll() is None:
        try:
            if platform.system() == 'Windows':
                subprocess.check_call(["taskkill", "/PID", str(server_proc.pid), "/F"])
            else:
                server_proc.terminate()
            server_proc.wait()
            print("サーバーを停止しました。")
        except Exception as e:
            print(f"停止中にエラー: {e}")
    else:
        print("サーバーは起動していません。")
    server_proc = None


def send_command():
    global server_proc
    if not server_proc or server_proc.poll() is not None:
        print("サーバーが起動していないか、既に停止しています。")
        return
    cmd = input("サーバーコマンドを入力: ")
    try:
        server_proc.stdin.write(cmd + "\n")
        server_proc.stdin.flush()
        print(f"コマンド送信: {cmd}")
    except Exception as e:
        print(f"コマンド送信エラー: {e}")


def backup_world(cfg):
    world = cfg['world_dir']
    bakdir = cfg['backup_dir']
    ensure_dir(bakdir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = os.path.join(bakdir, f"world_backup_{timestamp}.zip")
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(world):
            for file in files:
                full = os.path.join(root, file)
                rel = os.path.relpath(full, world)
                z.write(full, arcname=rel)
    print(f"バックアップを作成しました: {zip_name}")


def list_backups(cfg):
    bakdir = cfg['backup_dir']
    ensure_dir(bakdir)
    backups = sorted(os.listdir(bakdir))
    if not backups:
        print("バックアップは存在しません。")
        return
    for idx, name in enumerate(backups, 1):
        print(f"[{idx}] {name}")


def restore_backup(cfg):
    world = cfg['world_dir']
    bakdir = cfg['backup_dir']
    list_backups(cfg)
    try:
        choice = int(input("復元するバックアップ番号: ")) - 1
        backup_file = sorted(os.listdir(bakdir))[choice]
    except Exception:
        print("無効な選択です。")
        return
    zip_path = os.path.join(bakdir, backup_file)
    if os.path.isdir(world):
        print("既存のワールドフォルダを削除中...")
        shutil.rmtree(world)
    print(f"{backup_file} を復元しています...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(world)
    print("復元完了。")


def configure(cfg):
    print("---- 設定 ----")
    for key, val in cfg.items():
        new = input(f"{key} [{val}]: ")
        if new.strip():
            cfg[key] = new.strip()
    save_config(cfg)


def log_reader(process):
    """
    Ownserverのログを非同期で読み取る。
    """
    try:
        for line in process.stdout:
            print(line.strip())
    except Exception as e:
        print(f"ログ読み取り中にエラーが発生しました: {e}")


def setup_and_run_ownserver():
    """
    Ownserverのバイナリをダウンロードして解凍し、非ブロッキングで起動する。
    """
    global ownserver_proc
    # バイナリのダウンロードURL
    binary_url = "https://github.com/Kumassy/ownserver/releases/download/v0.7.0/ownserver_v0.7.0_x86_64-pc-windows-gnu.zip"
    binary_dir = "ownserver_bin"
    binary_path = os.path.join(binary_dir, "ownserver.exe")

    # バイナリディレクトリを作成
    ensure_dir(binary_dir)

    # バイナリをダウンロード
    if not os.path.exists(binary_path):
        print("Ownserverのバイナリをダウンロードしています...")
        zip_path = os.path.join(binary_dir, "ownserver.zip")
        try:
            urllib.request.urlretrieve(binary_url, zip_path)
            print("ダウンロード完了。解凍しています...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(binary_dir)
            os.remove(zip_path)
            print("解凍完了。")
        except Exception as e:
            print(f"バイナリのダウンロードまたは解凍中にエラーが発生しました: {e}")
            return
    else:
        print("既にバイナリが存在します。")

    # Ownserverを非ブロッキングで起動
    print("Ownserverを起動します...")
    try:
        ownserver_proc = subprocess.Popen(
            [binary_path, "--endpoint", "25565/tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"Ownserverがバックグラウンドで起動しました (PID: {ownserver_proc.pid})。")
        print("公開されたIPを確認するには以下のログを参照してください:")

        # ログを非同期で読み取るスレッドを開始
        threading.Thread(target=log_reader, args=(ownserver_proc,), daemon=True).start()
    except Exception as e:
        print(f"Ownserverの起動中にエラーが発生しました: {e}")


def stop_ownserver():
    """
    Ownserverを停止する。
    """
    global ownserver_proc
    if ownserver_proc and ownserver_proc.poll() is None:
        try:
            ownserver_proc.terminate()
            ownserver_proc.wait()
            print("Ownserverを停止しました。")
        except Exception as e:
            print(f"Ownserverの停止中にエラーが発生しました: {e}")
    else:
        print("Ownserverは起動していません。")
    ownserver_proc = None


def main_menu():
    if not os.path.exists(CONFIG_FILE):
        cfg = initial_setup()
    else:
        cfg = load_config()

    while True:
        print("==== Minecraft Server Helper ====")
        print("[1] サーバー起動")
        print("[2] サーバー停止")
        print("[3] サーバーにコマンド送信")
        print("[4] バックアップ作成")
        print("[5] バックアップ一覧")
        print("[6] バックアップ復元")
        print("[7] 設定変更")
        print("[8] Ownserverを起動")
        print("[9] Ownserverを停止")
        print("[0] 終了")
        choice = input(">> ")
        if choice == '1':
            start_server(cfg)
        elif choice == '2':
            stop_server()
        elif choice == '3':
            send_command()
        elif choice == '4':
            backup_world(cfg)
        elif choice == '5':
            list_backups(cfg)
        elif choice == '6':
            restore_backup(cfg)
        elif choice == '7':
            configure(cfg)
        elif choice == '8':
            setup_and_run_ownserver()
        elif choice == '9':
            stop_ownserver()
        elif choice == '0':
            stop_server()
            stop_ownserver()
            print("終了します。")
            sys.exit(0)
        else:
            print("無効な入力です。番号を選択してください。")


if __name__ == "__main__":
    main_menu()
