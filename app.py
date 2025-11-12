from gevent import monkey
monkey.patch_all()

import subprocess
import sys
import os
import webbrowser
import threading

def check_and_install_dependencies():
    """必要なライブラリがインストールされているか確認し、なければインストールする"""
    requirements_path = 'requirements.txt'
    if not os.path.exists(requirements_path):
        print(f"'{requirements_path}' が見つかりません。依存関係のチェックをスキップします。")
        return

    print("依存関係をチェックしています...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
        print("依存関係は最新です。")
    except subprocess.CalledProcessError:
        try:
            # gevent-websocket might need special handling on some systems
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gevent-websocket"])
        except subprocess.CalledProcessError as e:
            print(f"エラー: 依存関係のインストールに失敗しました。: {e}")
            print(f"手動で 'pip install -r {requirements_path}' を実行してください。")
            sys.exit(1)

# --- スクリプト開始時に依存関係をチェック ---
check_and_install_dependencies()

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import mcserverhelper as mc

# --- Globals ---
# 静的ファイルとテンプレートフォルダのパスを正しく設定
app = Flask(__name__, 
            static_folder='static', 
            template_folder='templates')
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, async_mode='gevent')

# --- グローバル変数 ---
# mcserverhelper.py内のグローバル変数を直接参照・更新する
# server_process -> mc.server_proc
# ownserver_mc_process -> mc.ownserver_proc
# ownserver_web_process -> 新しく追加
ownserver_web_process = None
log_thread_stdout = None
log_thread_stderr = None
config = mc.load_config()

# --- Helper Functions ---
def log_streamer_stdout(process):
    """サーバープロセスのstdoutを読み取り、WebSocket経由で送信する"""
    try:
        for line in iter(process.stdout.readline, ''):
            socketio.emit('console_output', {'log': line})
    except Exception as e:
        print(f"Log streaming (stdout) error: {e}")

def log_streamer_stderr(process):
    """サーバープロセスのstderrを読み取り、WebSocket経由で送信する"""
    try:
        for line in iter(process.stderr.readline, ''):
            socketio.emit('console_output', {'log': f"[STDERR] {line}"})
    except Exception as e:
        print(f"Log streaming (stderr) error: {e}")

def get_server_status():
    """サーバーの現在の状態を返す"""
    if mc.server_proc and mc.server_proc.poll() is None:
        return "Running"
    return "Stopped"

# --- Web Pages ---
@app.route('/')
def index():
    """メインページを表示します。"""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """Minecraftサーバーの状態をJSONで返す"""
    return jsonify(status=get_server_status())

# --- Minecraft Server API ---
@app.route('/api/start', methods=['POST'])
def start_server_route():
    """Minecraftサーバーを起動する"""
    global log_thread_stdout, log_thread_stderr
    if get_server_status() == "Running":
        return jsonify(status="Already running"), 400

    # WebUIからの設定値を取得
    xmx = request.json.get('xmx', '2G')
    xms = request.json.get('xms', '1G')
    world_type = request.json.get('world_type', 'default')
    
    # JARファイルの存在チェック
    jar_abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config['jar_path']) if not os.path.isabs(config['jar_path']) else config['jar_path']
    if not config.get('jar_path') or not os.path.exists(jar_abs_path):
        socketio.emit('console_output', {'log': "ERROR: server.jarのパスが設定されていないか、ファイルが存在しません。"})
        return jsonify(status="Error", message="JAR file not configured or found."), 400

    proc = mc.start_server(config, xmx=xmx, xms=xms, world_type=world_type)
    if proc:
        # ログをWebUIにストリーミングするスレッドを開始
        log_thread_stdout = socketio.start_background_task(target=log_streamer_stdout, process=mc.server_proc)
        log_thread_stderr = socketio.start_background_task(target=log_streamer_stderr, process=mc.server_proc)
        socketio.emit('status_update', {'status': 'Running'})
        return jsonify(status="Started")
    else:
        socketio.emit('console_output', {'log': "ERROR: サーバーの起動に失敗しました。コンソールログを確認してください。"})
        return jsonify(status="Error"), 500

@app.route('/api/stop', methods=['POST'])
def stop_server_route():
    """Minecraftサーバーを停止する"""
    if get_server_status() == "Stopped":
        return jsonify(status="Already stopped"), 400
    
    if mc.stop_server():
        # mc.stop_server()内で mc.server_proc は None に設定される
        socketio.emit('status_update', {'status': 'Stopped'})
        socketio.emit('console_output', {'log': "--- Server stopped ---"})
        return jsonify(status="Stopped")
    else:
        return jsonify(status="Error"), 500

@app.route('/api/command', methods=['POST'])
def command_route():
    """サーバーにコマンドを送信する"""
    if get_server_status() == "Stopped":
        return jsonify(status="Server is not running"), 400
    
    command = request.json.get('command')
    if not command:
        return jsonify(error="Command is empty"), 400
        
    socketio.emit('console_output', {'log': f"> {command}"}) # コマンドをエコーバック
    if mc.send_command(command):
        return jsonify(status="Command sent")
    else:
        return jsonify(status="Error sending command"), 500

@app.route('/api/quick_command', methods=['POST'])
def quick_command_route():
    """一般的な管理コマンドを簡単に実行する"""
    if get_server_status() == "Stopped":
        return jsonify(status="Server is not running"), 400

    data = request.json
    action = data.get('action')
    player = data.get('player')
    
    command = None
    player_commands = ['op', 'deop', 'kick', 'ban', 'pardon']

    if action in player_commands:
        if not player:
            return jsonify(error="Player name is required"), 400
        command = f"{action} {player}"
    elif action == 'time_day':
        command = "time set day"
    elif action == 'time_night':
        command = "time set night"
    elif action == 'weather_clear':
        command = "weather clear"
    elif action == 'weather_rain':
        command = "weather rain"
    # 他のコマンドもここに追加可能

    if command:
        socketio.emit('console_output', {'log': f"> {command}"})
        if mc.send_command(command):
            return jsonify(status="Command sent")
        else:
            return jsonify(status="Error sending command"), 500
    
    return jsonify(error="Invalid action"), 400

# --- Ownserver API ---
def ownserver_log_callback(log_type, line):
    socketio.emit('ownserver_log', {'type': log_type, 'log': line})

@app.route('/api/ownserver/status')
def ownserver_status():
    mc_status = "Running" if mc.ownserver_proc and mc.ownserver_proc.poll() is None else "Stopped"
    web_status = "Running" if ownserver_web_process and ownserver_web_process.poll() is None else "Stopped"
    return jsonify(mc=mc_status, web=web_status)

@app.route('/api/ownserver/mc/start', methods=['POST'])
def start_ownserver_mc():
    if mc.ownserver_proc and mc.ownserver_proc.poll() is None:
        return jsonify(status="Already running"), 400
    
    proc = mc.setup_and_run_ownserver(port=25565, log_callback=lambda line: ownserver_log_callback('mc', line))
    if proc:
        socketio.emit('ownserver_status_update', {'type': 'mc', 'status': 'Running'})
        return jsonify(status="Started")
    return jsonify(status="Error"), 500

@app.route('/api/ownserver/mc/stop', methods=['POST'])
def stop_ownserver_mc():
    if mc.stop_ownserver():
        socketio.emit('ownserver_status_update', {'type': 'mc', 'status': 'Stopped'})
        return jsonify(status="Stopped")
    return jsonify(status="Already stopped")

@app.route('/api/ownserver/web/start', methods=['POST'])
def start_ownserver_web():
    global ownserver_web_process
    if ownserver_web_process and ownserver_web_process.poll() is None:
        return jsonify(status="Already running"), 400
    
    # mcserverhelperの関数を再利用
    proc = mc.setup_and_run_ownserver(port=5000, log_callback=lambda line: ownserver_log_callback('web', line))
    if proc:
        ownserver_web_process = proc
        socketio.emit('ownserver_status_update', {'type': 'web', 'status': 'Running'})
        return jsonify(status="Started")
    return jsonify(status="Error"), 500

@app.route('/api/ownserver/web/stop', methods=['POST'])
def stop_ownserver_web():
    global ownserver_web_process
    if ownserver_web_process and ownserver_web_process.poll() is None:
        # mcserverhelperの停止ロジックを模倣
        ownserver_web_process.terminate()
        try:
            ownserver_web_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ownserver_web_process.kill()
            ownserver_web_process.wait()
        ownserver_web_process = None
        socketio.emit('ownserver_status_update', {'type': 'web', 'status': 'Stopped'})
        return jsonify(status="Stopped")
    return jsonify(status="Already stopped")

# --- Backup API ---
@app.route('/api/backups')
def list_backups_route():
    return jsonify(backups=mc.list_backups(config))

@app.route('/api/backups/create', methods=['POST'])
def create_backup_route():
    if get_server_status() == "Running":
        mc.send_command("say バックアップを開始します。サーバーが一時的に停止する可能性があります。")
        mc.send_command("save-all")
        socketio.sleep(5) # save-allが完了するのを少し待つ

    result = mc.backup_world(config)
    if result:
        if get_server_status() == "Running":
            mc.send_command("say バックアップが完了しました。")
        return jsonify(status="Success", filename=os.path.basename(result))
    return jsonify(status="Error"), 500

@app.route('/api/backups/restore', methods=['POST'])
def restore_backup_route():
    if get_server_status() == "Running":
        return jsonify(status="Error", message="サーバーを停止してから復元してください。"), 400
    
    filename = request.json.get('filename')
    if not filename:
        return jsonify(status="Error", message="ファイル名が指定されていません。"), 400

    success, message = mc.restore_backup(config, filename)
    if success:
        return jsonify(status="Success", message=message)
    return jsonify(status="Error", message=message), 500

# --- Config API ---
@app.route('/api/config', methods=['GET', 'POST'])
def config_route():
    global config
    if request.method == 'POST':
        new_config_data = request.json
        # jar_pathのみ更新を許可
        if 'jar_path' in new_config_data:
            config['jar_path'] = new_config_data['jar_path']
            mc.save_config(config)
            return jsonify(status="Success", message="設定を保存しました。")
        return jsonify(status="Error", message="無効な設定です。"), 400
    else: # GET
        # 現在の設定を返す
        return jsonify(jar_path=config.get('jar_path', ''))

# --- Server Properties API ---
@app.route('/api/properties', methods=['GET', 'POST'])
def properties_route():
    if request.method == 'POST':
        props_data = request.json
        success, message = mc.save_properties(config, props_data)
        if success:
            return jsonify(status="Success", message=message)
        return jsonify(status="Error", message=message), 500
    else: # GET
        props = mc.get_properties(config)
        return jsonify(props)

# --- Shutdown API ---
@app.route('/api/stop_all', methods=['POST'])
def stop_all_services():
    """すべての関連サービスを停止し、アプリケーションを終了する"""
    print("Stopping all services...")
    socketio.emit('console_output', {'log': "--- すべてのサービスを停止しています ---"})

    # 1. Minecraftサーバーを停止
    if get_server_status() == "Running":
        print("Stopping Minecraft server...")
        if mc.stop_server():
            socketio.emit('status_update', {'status': 'Stopped'})
            socketio.emit('console_output', {'log': "Minecraftサーバーを停止しました。"})
        else:
            # このelseブロックは mc.stop_server の実装上、通常は通らない
            socketio.emit('console_output', {'log': "Minecraftサーバーは既に停止していました。"})


    # 2. ownserver (MC) を停止
    # mc.ownserver_proc はグローバル変数なので直接チェック
    if mc.ownserver_proc and mc.ownserver_proc.poll() is None:
        print("Stopping ownserver (MC)...")
        if mc.stop_ownserver():
            socketio.emit('ownserver_status_update', {'type': 'mc', 'status': 'Stopped'})
            socketio.emit('console_output', {'log': "ownserver (MC) を停止しました。"})
        else:
            # このelseブロックは mc.stop_ownserver の実装上、通常は通らない
            socketio.emit('console_output', {'log': "ownserver (MC) は既に停止していました。"})


    # 3. ownserver (Web) を停止
    global ownserver_web_process
    if ownserver_web_process and ownserver_web_process.poll() is None:
        print("Stopping ownserver (Web)...")
        ownserver_web_process.terminate()
        try:
            ownserver_web_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ownserver_web_process.kill()
            ownserver_web_process.wait()
        finally:
            ownserver_web_process = None
            socketio.emit('ownserver_status_update', {'type': 'web', 'status': 'Stopped'})
            socketio.emit('console_output', {'log': "ownserver (Web) を停止しました。"})


    print("All services stopped. Shutting down web server.")
    socketio.emit('console_output', {'log': "--- Webサーバーをシャットダウンします ---"})
    
    # 4. Flaskサーバーをシャットダウン
    # 少し遅延させて、クライアントがメッセージを受信する時間を確保する
    def shutdown():
        socketio.sleep(1)
        # sys.exit() よりも os._exit(0) の方がこのような状況では確実
        os._exit(0)

    # シャットダウンをバックグラウンドで実行
    socketio.start_background_task(shutdown)
    
    return jsonify(status="All services stopped. Shutting down.")


# --- SocketIO Events ---
@socketio.on('connect')
def handle_connect():
    """クライアント接続時のイベントハンドラ。"""
    print('Client connected')
    # 接続時に現在の状態を送信
    emit('status_update', {'status': get_server_status()})

@socketio.on('disconnect')
def handle_disconnect():
    """クライアント切断時のイベントハンドラ。"""
    print('Client disconnected')

# --- Main ---
def run_app():
    """Webサーバーを起動し、ブラウザを開きます。"""
    print("WebUIを起動しています...")
    url = "http://127.0.0.1:5000"
    print(f"ブラウザで {url} を開いてください。")
    threading.Timer(1, lambda: webbrowser.open(url)).start()
    socketio.run(app, host='127.0.0.1', port=5000, use_reloader=False, log_output=False)

if __name__ == '__main__':
    run_app()
