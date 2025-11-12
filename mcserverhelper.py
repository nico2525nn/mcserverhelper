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
# サーバーデータ: 'server_data/' (デフォルト)
#   - ワールドデータ: 'world/'
#   - バックアップ: 'backups/' 内
#   - EULA 同意ファイル: 'eula.txt'
# PID ファイル: '.mcserve_helper.pid'
CONFIG_FILE = "mcserve_helper_config.json"
DEFAULT_CONFIG = {
    "java_cmd": "java",
    "jar_path": "",
    "server_data_dir": "server_data", # サーバー関連ファイルのルートディレクトリ
    "world_dir": "world",
    "backup_dir": "backups",
    "ops_file": "ops.json",
    "whitelist_file": "whitelist.json",
    "log_file": "logs/latest.log",
    "eula_file": "eula.txt"
}

# グローバルプロセスオブジェクト
# これらはapp.pyから直接管理される
server_proc = None # Minecraft server process
ownserver_proc = None # Ownserver for MC process


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            try:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
            except json.JSONDecodeError:
                print("設定ファイルを読み込めませんでした。")
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"設定を '{CONFIG_FILE}' に保存しました。")
    return True


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def ensure_eula(cfg):
    server_data_dir = cfg.get('server_data_dir', '.')
    eula_path = os.path.join(server_data_dir, cfg.get('eula_file', 'eula.txt'))
    ensure_dir(os.path.dirname(eula_path))
    try:
        with open(eula_path, 'w', encoding='utf-8') as f:
            f.write('# By changing the setting below to TRUE you are indicating your agreement to the EULA\n')
            f.write('eula=true\n')
        print(f"EULAに同意しました: {eula_path}")
    except Exception as e:
        print(f"EULA 同意ファイルの作成に失敗しました: {e}")


def start_server(cfg, xmx="1024M", xms="1024M", world_type="default"):
    """
    Minecraftサーバーを起動する。
    成功した場合はsubprocess.Popenオブジェクトを、失敗した場合はNoneを返す。
    """
    global server_proc

    server_data_dir = cfg.get('server_data_dir', '.')
    ensure_dir(server_data_dir)
    
    ensure_eula(cfg)

    # jar_pathが相対パスの場合、スクリプトの場所からの相対パスとして解決し、絶対パスに変換
    script_dir = os.path.dirname(os.path.abspath(__file__))
    jar_abs_path = os.path.join(script_dir, cfg['jar_path']) if not os.path.isabs(cfg['jar_path']) else cfg['jar_path']
    
    if not os.path.exists(jar_abs_path):
        print(f"Error: JARファイル '{jar_abs_path}' が見つかりません。設定を確認してください。")
        return None
    if server_proc and server_proc.poll() is None:
        print("サーバーは既に起動しています。")
        return server_proc

    # 新しいワールドの場合、ワールドタイプを設定
    world_dir = os.path.join(server_data_dir, cfg['world_dir'])
    if not os.path.exists(world_dir) or not os.listdir(world_dir):
        ensure_dir(world_dir)
        print(f"新しいワールドを作成します。ワールドタイプ: {world_type}")
        # server.properties ファイルを作成または更新
        props_path = os.path.join(server_data_dir, "server.properties")
        props = {}
        if os.path.exists(props_path):
            with open(props_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        props[key.strip()] = value.strip()
        props['level-type'] = world_type
        with open(props_path, 'w', encoding='utf-8') as f:
            for key, value in props.items():
                f.write(f"{key}={value}\n")

    cmd = [cfg['java_cmd'], f"-Xmx{xmx}", f"-Xms{xms}", "-jar", jar_abs_path, "nogui"]
    
    # stdoutとstderrをキャプチャするためにPIPEを使用
    proc = subprocess.Popen(
        cmd, 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True, 
        cwd=server_data_dir, # サーバーの作業ディレクトリを変更
        encoding='utf-8',
        errors='replace'
    )
    print(f"サーバーを起動しました (PID: {proc.pid})")
    server_proc = proc
    return proc

def stop_server():
    """サーバーを停止する。"""
    global server_proc
    if server_proc and server_proc.poll() is None:
        print("サーバーに 'stop' コマンドを送信し、正常なシャットダウンを試みます...")
        try:
            server_proc.stdin.write("stop\n")
            server_proc.stdin.flush()
            server_proc.wait(timeout=60)
            print("サーバーは正常に停止しました。")
        except (subprocess.TimeoutExpired, BrokenPipeError):
            print("シャットダウンがタイムアウトしたか、パイプが壊れました。プロセスを強制終了します。")
            if platform.system() == 'Windows':
                subprocess.check_call(["taskkill", "/PID", str(server_proc.pid), "/F"])
            else:
                server_proc.terminate()
            server_proc.wait()
            print("サーバーを強制的に停止しました。")
        except Exception as e:
            print(f"サーバー停止中にエラーが発生しました: {e}")
        finally:
            server_proc = None
            return True
    else:
        print("サーバーは起動していません。")
        server_proc = None
        return False


def send_command(cmd):
    """サーバーにコマンドを送信する。"""
    global server_proc
    if not server_proc or server_proc.poll() is not None:
        print("サーバーが起動していないか、既に停止しています。")
        return False
    try:
        server_proc.stdin.write(cmd + "\n")
        server_proc.stdin.flush()
        print(f"コマンド送信: {cmd}")
        return True
    except (BrokenPipeError, ValueError, OSError) as e:
        print(f"コマンド送信エラー: {e}")
        return False

def backup_world(cfg):
    """ワールドのバックアップを作成する。成功した場合はzipファイル名を返す。"""
    server_data_dir = cfg.get('server_data_dir', '.')
    world = os.path.join(server_data_dir, cfg['world_dir'])
    bakdir = os.path.join(server_data_dir, cfg['backup_dir'])
    ensure_dir(bakdir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = os.path.join(bakdir, f"world_backup_{timestamp}.zip")
    try:
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(world):
                for file in files:
                    full = os.path.join(root, file)
                    rel = os.path.relpath(full, world)
                    z.write(full, arcname=rel)
        print(f"バックアップを作成しました: {zip_name}")
        return zip_name
    except Exception as e:
        print(f"バックアップ作成中にエラー: {e}")
        return None

def list_backups(cfg):
    """バックアップのリストを返す。"""
    server_data_dir = cfg.get('server_data_dir', '.')
    bakdir = os.path.join(server_data_dir, cfg['backup_dir'])
    ensure_dir(bakdir)
    if not os.path.exists(bakdir) or not os.path.isdir(bakdir):
        return []
    backups = sorted(os.listdir(bakdir), reverse=True)
    return backups

def restore_backup(cfg, backup_file):
    """指定されたバックアップファイルを復元する。"""
    server_data_dir = cfg.get('server_data_dir', '.')
    world = os.path.join(server_data_dir, cfg['world_dir'])
    bakdir = os.path.join(server_data_dir, cfg['backup_dir'])
    zip_path = os.path.join(bakdir, backup_file)

    if not os.path.exists(zip_path):
        msg = f"バックアップファイル '{backup_file}' が見つかりません。"
        print(msg)
        return False, msg

    if server_proc and server_proc.poll() is None:
        msg = "サーバーが起動中です。復元前にサーバーを停止してください。"
        print(msg)
        return False, msg

    try:
        if os.path.isdir(world):
            print("既存のワールドフォルダを削除中...")
            shutil.rmtree(world)
        print(f"'{backup_file}' を復元しています...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(world)
        msg = "復元完了。"
        print(msg)
        return True, msg
    except Exception as e:
        msg = f"復元中にエラーが発生しました: {e}"
        print(msg)
        return False, msg


def log_reader(process, callback):
    """
    プロセスの出力を非同期で読み取り、コールバック関数に渡す。
    """
    try:
        for line in iter(process.stdout.readline, ''):
            callback(line.strip())
    except Exception as e:
        print(f"ログ読み取り中にエラーが発生しました: {e}")
    finally:
        process.stdout.close()


def setup_and_run_ownserver(port=25565, log_callback=None):
    """
    Ownserverを起動する。
    成功した場合はsubprocess.Popenオブジェクトを、失敗した場合はNoneを返す。
    """
    global ownserver_proc
    binary_url = "https://github.com/Kumassy/ownserver/releases/download/v0.7.0/ownserver_v0.7.0_x86_64-pc-windows-gnu.zip"
    binary_dir = "ownserver_bin"
    binary_path = os.path.join(binary_dir, "ownserver.exe")

    ensure_dir(binary_dir)

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
            if log_callback:
                log_callback(f"ERROR: バイナリのダウンロードまたは解凍中にエラーが発生しました: {e}")
            return None

    print(f"Ownserverをポート {port}/tcp で起動します...")
    try:
        proc = subprocess.Popen(
            [binary_path, "--endpoint", f"{port}/tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # エラー出力を標準出力にマージ
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        print(f"Ownserverがバックグラウンドで起動しました (PID: {proc.pid})。")
        
        if log_callback:
            threading.Thread(target=log_reader, args=(proc, log_callback), daemon=True).start()

        ownserver_proc = proc
        return proc
    except Exception as e:
        print(f"Ownserverの起動中にエラーが発生しました: {e}")
        if log_callback:
            log_callback(f"ERROR: Ownserverの起動中にエラーが発生しました: {e}")
        return None

def stop_ownserver():
    """Ownserverを停止する。"""
    global ownserver_proc
    if ownserver_proc and ownserver_proc.poll() is None:
        try:
            ownserver_proc.terminate()
            ownserver_proc.wait(timeout=5)
            print("Ownserverを停止しました。")
        except subprocess.TimeoutExpired:
            print("Ownserverの停止がタイムアウトしました。強制終了します。")
            ownserver_proc.kill()
            ownserver_proc.wait()
        except Exception as e:
            print(f"Ownserverの停止中にエラーが発生しました: {e}")
        finally:
            ownserver_proc = None
            return True
    else:
        print("Ownserverは起動していません。")
        ownserver_proc = None
        return False

def get_properties(cfg):
    """server.propertiesの内容を辞書として読み込む。"""
    server_data_dir = cfg.get('server_data_dir', '.')
    props_path = os.path.join(server_data_dir, "server.properties")
    props = {}
    if not os.path.exists(props_path):
        return props
        
    try:
        with open(props_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        props[key.strip()] = value.strip()
    except Exception as e:
        print(f"Error reading server properties file '{props_path}': {e}")
        # In case of error, return an empty dict to avoid crashing the API
        return {}
    return props

def save_properties(cfg, props_data):
    """server.propertiesファイルに設定を保存する。コメントや順序は維持しようと試みる。"""
    server_data_dir = cfg.get('server_data_dir', '.')
    props_path = os.path.join(server_data_dir, "server.properties")
    
    lines = []
    if os.path.exists(props_path):
        with open(props_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    # props_dataにあるキーをセットとして持っておく
    keys_to_update = set(props_data.keys())

    # 既存の行を更新
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if line_strip and not line_strip.startswith('#'):
            if '=' in line_strip:
                key, _ = line_strip.split('=', 1)
                key = key.strip()
                if key in props_data:
                    lines[i] = f"{key}={props_data[key]}\n"
                    keys_to_update.discard(key) # 更新済みのキーをセットから削除

    # ファイルに存在しなかった新しいキーを追加
    for key in keys_to_update:
        lines.append(f"{key}={props_data[key]}\n")

    try:
        with open(props_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"サーバープロパティを '{props_path}' に保存しました。")
        return True, "プロパティを保存しました。"
    except Exception as e:
        msg = f"プロパティの保存中にエラーが発生しました: {e}"
        print(msg)
        return False, msg