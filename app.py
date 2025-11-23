import subprocess
import sys
import os
import webbrowser
import threading
import time
import logging
import json
try:
    import simple_websocket
except ImportError:
    pass

def check_and_install_dependencies():
    """必要なライブラリがインストールされているか確認し、なければインストールする"""
    # PyInstaller でバンドルした実行ファイル実行時は pip インストール処理をスキップ
    if getattr(sys, 'frozen', False):
        return

    requirements_path = 'requirements.txt'
    if not os.path.exists(requirements_path):
        return

    try:
        # 出力を抑制して実行
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("依存関係: OK")
    except subprocess.CalledProcessError:
        try:
            # gevent-websocket might need special handling on some systems
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gevent-websocket"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # simple-websocket also
            subprocess.check_call([sys.executable, "-m", "pip", "install", "simple-websocket"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("依存関係: OK (修正済み)")
        except subprocess.CalledProcessError as e:
            print(f"エラー: 依存関係のインストールに失敗しました。: {e}")
            print(f"手動で 'pip install -r {requirements_path}' を実行してください。")
            sys.exit(1)

# --- スクリプト開始時に依存関係をチェック ---
check_and_install_dependencies()

from flask import Flask, render_template, jsonify, request
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
import threading
import mcserverhelper as mc

# --- Globals ---
# 静的ファイルとテンプレートフォルダのパスを正しく設定
app = Flask(__name__, 
            static_folder='static', 
            template_folder='templates')
app.config['SECRET_KEY'] = os.urandom(24)

# --- 追加: ロギング設定（werkzeug/Flask のアクセスログを抑制） ---
# --debug オプションがある場合のみログファイルに出力する
if '--debug' in sys.argv:
    logging.basicConfig(
        filename='debug.log',
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s: %(message)s'
    )
else:
    logging.basicConfig(level=logging.ERROR)

# Flask のデフォルトロガーを無効化（不要なら True のまま)
app.logger.disabled = True
# werkzeug のアクセスログを抑制
logging.getLogger('werkzeug').setLevel(logging.CRITICAL)

# --- 変更: 複数モードを順に試して SocketIO を初期化する（失敗時はフェイクにフォールバック） ---
class FakeSocketIO:
    """最低限のインターフェースを提供するフェイク SocketIO。
    WebSocket が使えない環境（PyInstallerでのバンドル等）でのフォールバック用。
    """
    def __init__(self, app):
        self.app = app

    def emit(self, event, data=None, broadcast=False):
        # 出力を抑制（ログは必要なら logging.debug に切り替え）
        # logging.debug(f"[FakeSocketIO.emit] {event}: {data}")
        return None

    def start_background_task(self, target=None, *args, **kwargs):
        if target is None:
            return None
        t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        t.start()
        return t

    def sleep(self, seconds):
        time.sleep(seconds)

    def on(self, event):
        # デコレータを返す（何もしない）
        def decorator(fn):
            return fn
        return decorator

    def run(self, app, host='127.0.0.1', port=5000, use_reloader=False, log_output=False):
        # フェイク時は通常の Flask サーバーで起動
        app.run(host=host, port=port, use_reloader=use_reloader)

def init_socketio(app):
    """複数の async_mode 候補を順に試して SocketIO を初期化する。
    すべて失敗した場合は FakeSocketIO を返す。
    """
    # threading を優先する (Windowsでのsubprocessとの相性のため)
    candidates = ['threading', 'eventlet', 'gevent', 'gevent_uwsgi', 'asyncio', None]
    last_exc = None
    for mode in candidates:
        try:
            if mode is None:
                sio = SocketIO(app)
            else:
                sio = SocketIO(app, async_mode=mode)
            logging.debug(f"SocketIO initialized with async_mode={mode}")
            return sio
        except Exception as e:
            # 初期化失敗はデバッグログに出す（標準出力は増やさない）
            logging.debug(f"SocketIO init failed with async_mode={mode}: {e}")
            last_exc = e
    # 全て失敗したらフェイクにフォールバック（ログ出力は抑制）
    logging.debug("All SocketIO async_mode initializations failed. Falling back to FakeSocketIO.")
    return FakeSocketIO(app)

# 実際の SocketIO 初期化
socketio = init_socketio(app)

# --- グローバル変数 ---
# mcserverhelper.py内のグローバル変数を直接参照・更新する
# server_process -> mc.server_proc
# ownserver_mc_process -> mc.ownserver_proc
# ownserver_web_process -> 新しく追加
ownserver_web_process = None
log_thread = None
config = mc.load_config()
MODRINTH_INSTALLED_FILE = 'modrinth_installed.json'

# --- Helper Functions ---
def load_installed_projects():
    """Reads the list of installed Modrinth projects from the JSON file."""
    if not os.path.exists(MODRINTH_INSTALLED_FILE):
        return {}
    try:
        with open(MODRINTH_INSTALLED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_installed_projects(data):
    """Saves the list of installed Modrinth projects to the JSON file."""
    try:
        with open(MODRINTH_INSTALLED_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving installed projects file: {e}")

def log_streamer(process):
    """サーバープロセスの出力を読み取り、WebSocket経由で送信する"""
    try:
        # stdoutとstderrはマージされているため、stdoutのみ読み取る
        for line in iter(process.stdout.readline, ''):
            socketio.emit('console_output', {'log': line})
    except Exception as e:
        logging.error(f"Log streaming error: {e}")

def get_server_status():
    """サーバーの現在の状態を返す"""
    if mc.server_proc and mc.server_proc.poll() is None:
        return "Running"
    return "Stopped"

# --- Web Pages ---
@app.route('/')
def index():
    """メインページを表示します。"""
    mods_folder_exists = os.path.isdir('mods')
    plugins_folder_exists = os.path.isdir('plugins')
    return render_template('index.html', 
                           mods_folder_exists=mods_folder_exists, 
                           plugins_folder_exists=plugins_folder_exists)

@app.route('/api/status')
def status():
    """Minecraftサーバーの状態をJSONで返す"""
    return jsonify(status=get_server_status())

# --- Minecraft Server API ---
@app.route('/api/start', methods=['POST'])
def start_server_route():
    """Minecraftサーバーを起動する"""
    global log_thread
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
        log_thread = socketio.start_background_task(target=log_streamer, process=mc.server_proc)
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

@app.route('/api/upload_mod', methods=['POST'])
def upload_mod_route():
    """Modファイルをアップロードする"""
    if 'file' not in request.files:
        return jsonify(status="Error", message="ファイルがありません"), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify(status="Error", message="ファイルが選択されていません"), 400
    if file:
        filename = secure_filename(file.filename)
        # フォルダが存在することを確認
        if not os.path.isdir('mods'):
             os.makedirs('mods')
        file.save(os.path.join('mods', filename))
        socketio.emit('console_output', {'log': f"Mod '{filename}' がアップロードされました。"})
        return jsonify(status="Success", filename=filename)
    return jsonify(status="Error", message="不明なエラー"), 500

@app.route('/api/upload_plugin', methods=['POST'])
def upload_plugin_route():
    """Pluginファイルをアップロードする"""
    if 'file' not in request.files:
        return jsonify(status="Error", message="ファイルがありません"), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify(status="Error", message="ファイルが選択されていません"), 400
    if file:
        filename = secure_filename(file.filename)
        # フォルダが存在することを確認
        if not os.path.isdir('plugins'):
            os.makedirs('plugins')
        file.save(os.path.join('plugins', filename))
        socketio.emit('console_output', {'log': f"Plugin '{filename}' がアップロードされました。"})
        return jsonify(status="Success", filename=filename)
    return jsonify(status="Error", message="不明なエラー"), 500

# --- Mods & Plugins API ---
def list_files_in_dir(directory):
    """指定されたディレクトリ内の.jarファイルをリストアップする"""
    if not os.path.isdir(directory):
        return []
    try:
        # .jar ファイルのみをリストアップ
        return [f for f in os.listdir(directory) if f.endswith('.jar') and os.path.isfile(os.path.join(directory, f))]
    except OSError:
        return []

@app.route('/api/mods', methods=['GET'])
def list_mods_route():
    """modsフォルダ内のファイル一覧を返す"""
    return jsonify(files=list_files_in_dir('mods'))

@app.route('/api/plugins', methods=['GET'])
def list_plugins_route():
    """pluginsフォルダ内のファイル一覧を返す"""
    return jsonify(files=list_files_in_dir('plugins'))

@app.route('/api/installed_projects', methods=['GET'])
def list_installed_projects_route():
    """Returns the list of installed Modrinth projects from the JSON file."""
    return jsonify(load_installed_projects())

@app.route('/api/delete_mod/<path:filename>', methods=['DELETE'])
def delete_mod_route(filename):
    """Modファイルを削除し、メタデータも更新する"""
    safe_filename = secure_filename(filename)
    if safe_filename != filename:
        return jsonify(status="Error", message="無効なファイル名です。"), 400
    
    file_path = os.path.join('mods', safe_filename)
    
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
            
            # Update metadata JSON
            installed = load_installed_projects()
            if safe_filename in installed:
                del installed[safe_filename]
                save_installed_projects(installed)

            socketio.emit('console_output', {'log': f"Mod '{safe_filename}' が削除されました。"})
            return jsonify(status="Success", message="ファイルが削除されました。")
        else:
            return jsonify(status="Error", message="ファイルが見つかりません。"), 404
    except OSError as e:
        return jsonify(status="Error", message=f"ファイルの削除中にエラーが発生しました: {e}"), 500

@app.route('/api/delete_plugin/<path:filename>', methods=['DELETE'])
def delete_plugin_route(filename):
    """Pluginファイルを削除し、メタデータも更新する"""
    safe_filename = secure_filename(filename)
    if safe_filename != filename:
        return jsonify(status="Error", message="無効なファイル名です。"), 400
        
    file_path = os.path.join('plugins', safe_filename)
    
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)

            # Update metadata JSON
            installed = load_installed_projects()
            if safe_filename in installed:
                del installed[safe_filename]
                save_installed_projects(installed)

            socketio.emit('console_output', {'log': f"Plugin '{safe_filename}' が削除されました。"})
            return jsonify(status="Success", message="ファイルが削除されました。")
        else:
            return jsonify(status="Error", message="ファイルが見つかりません。"), 404
    except OSError as e:
        return jsonify(status="Error", message=f"ファイルの削除中にエラーが発生しました: {e}"), 500

# --- Modrinth API ---
from modrinth_api import ModrinthClient, ModrinthApiException
import modrinth_api # Keep for download_file
modrinth_client = ModrinthClient(project_name="MCServerHelper", project_version="1.0.0")

@app.route('/api/modrinth/search')
def modrinth_search_route():
    query = request.args.get('query', '')
    game_version = request.args.get('game_version', '')
    loader = request.args.get('loader', '')
    project_type = request.args.get('project_type', 'mod') # Default to searching mods
    limit = request.args.get('limit', 20)

    facets = []
    if game_version:
        facets.append([f"versions:{v.strip()}" for v in game_version.split(',')])
    if loader:
        facets.append([f"categories:{l.strip()}" for l in loader.split(',')])
    if project_type:
        facets.append([f"project_type:{pt.strip()}" for pt in project_type.split(',')])

    facets_str = json.dumps(facets) if facets else None
    
    try:
        results = modrinth_client.search(query, limit=int(limit), facets=facets_str)
        # API can return None or a dict without 'hits' on success, so handle it
        if results and 'hits' in results:
            return jsonify(results)
        else:
            return jsonify({"hits": []})
            
    except ModrinthApiException as e:
        error_message = f"Modrinth API Error: {e}"
        logging.error(error_message)
        socketio.emit('console_output', {'log': f"ERROR: {error_message}"})
        return jsonify({"hits": [], "error": str(e)}), 500

@app.route('/api/modrinth/project/<project_id>/versions')
def modrinth_project_versions_route(project_id):
    loaders_str = request.args.get('loaders', '')
    game_versions_str = request.args.get('game_versions', '')
    
    loaders = loaders_str.split(',') if loaders_str else None
    game_versions = game_versions_str.split(',') if game_versions_str else None

    versions = modrinth_client.get_project_versions(project_id, loaders=loaders, game_versions=game_versions)

    if versions is not None: # Check for None explicitly as an empty list is a valid response
        return jsonify(versions)
    else:
        return jsonify([]), 500

@app.route('/api/modrinth/check_updates', methods=['POST'])
def modrinth_check_updates_route():
    installed_projects = load_installed_projects()
    updates_available = []

    for filename, project in installed_projects.items():
        project_id = project.get('project_id')
        installed_version_id = project.get('version_id')
        
        # Get the same context for updates
        game_versions = project.get('game_versions')
        loaders = project.get('loaders')

        if not project_id or not installed_version_id:
            continue

        # Fetch latest versions matching the installed context
        latest_versions = modrinth_client.get_project_versions(
            project_id,
            loaders=loaders,
            game_versions=game_versions
        )

        if latest_versions:
            latest_version = latest_versions[0] # The first one is the newest
            if latest_version['id'] != installed_version_id:
                updates_available.append({
                    'filename': filename,
                    'project_id': project_id,
                    'project_title': project.get('project_title'),
                    'installed_version_id': installed_version_id,
                    'installed_version_name': project.get('version_name'),
                    'latest_version_id': latest_version['id'],
                    'latest_version_name': latest_version['name'],
                    'project_type': project.get('project_type')
                })
    
    return jsonify(updates_available)

@app.route('/api/modrinth/install', methods=['POST'])
def modrinth_install_route():
    data = request.json
    project_id = data.get('project_id')
    version_id = data.get('version_id')
    project_type = data.get('project_type', 'mod')  # 'mod', 'plugin', or 'datapack'
    
    # デバッグログ
    socketio.emit('console_output', {'log': f"[DEBUG] Modrinth インストール: project_type='{project_type}', project_id='{project_id}'"})

    if not version_id or not project_id:
        return jsonify(status="Error", message="Project ID and Version ID are required."), 400

    # Determine download directory based on project_type
    # 検索条件で指定したproject_typeに基づいて配置先を決定
    if project_type == 'plugin':
        target_dir = 'plugins'
    elif project_type == 'datapack':
        target_dir = 'datapacks'
    else:  # 'mod' or default
        target_dir = 'mods'
    
    socketio.emit('console_output', {'log': f"配置先ディレクトリ: {target_dir}"})

    # Get version details to find the file URL
    version_info = modrinth_client.get_version(version_id)
    if not version_info or not version_info.get('files'):
        return jsonify(status="Error", message="Version information not found or version has no files."), 404

    # Find the primary file to download
    primary_file = next((f for f in version_info['files'] if f['primary']), version_info['files'][0])
    
    file_url = primary_file['url']
    file_name = primary_file['filename']

    # Notify UI about the download
    socketio.emit('console_output', {'log': f"Downloading '{file_name}' from Modrinth..."})

    # Download the file
    downloaded_path = modrinth_api.download_file(file_url, target_dir, file_name)

    if downloaded_path:
        socketio.emit('console_output', {'log': f"Successfully installed '{file_name}' to '{target_dir}' folder."})
        
        # Save metadata
        project_info = modrinth_client.get_project(project_id)
        project_title = project_info.get('title', 'Unknown Project') if project_info else 'Unknown Project'

        installed_projects = load_installed_projects()
        
        # Remove old entry if a different version of the same project is installed
        # This assumes one version per project.
        installed_projects = {k: v for k, v in installed_projects.items() if v.get('project_id') != project_id}

        new_entry = {
            "project_id": project_id,
            "project_title": project_title,
            "version_id": version_id,
            "version_name": version_info.get('name', 'Unknown Version'),
            "project_type": project_type,
            "installed_file": file_name,
            "icon_url": project_info.get('icon_url') if project_info else None,
            "game_versions": version_info.get('game_versions', []),
            "loaders": version_info.get('loaders', [])
        }
        # Use filename as key to handle multiple files from the same project (though current logic doesn't support it)
        installed_projects[file_name] = new_entry
        save_installed_projects(installed_projects)
        
        return jsonify(status="Success", message=f"Downloaded {file_name}", path=downloaded_path)
    else:
        socketio.emit('console_output', {'log': f"ERROR: Failed to download '{file_name}'."})
        return jsonify(status="Error", message=f"Failed to download {file_name}."), 500

# --- Server Software API ---
from server_software_api import ServerSoftwareClient, ServerSoftwareException, download_file as sw_download_file

server_software_client = ServerSoftwareClient()

@app.route('/api/server_software/types')
def software_types_route():
    """サポートされているサーバーソフトウェアタイプのリストを返す"""
    return jsonify(server_software_client.get_software_types())

@app.route('/api/server_software/versions')
def software_versions_route():
    """指定されたソフトウェアタイプのバージョンリストを返す"""
    software_type = request.args.get('project')
    if not software_type:
        return jsonify({"error": "Project parameter is required"}), 400

    try:
        client = server_software_client.get_client(software_type)
        
        if software_type == "vanilla":
            versions = client.get_versions("release")
        elif software_type == "paper":
            versions = client.get_versions()
        elif software_type == "purpur":
            versions = client.get_versions()
        elif software_type == "fabric":
            versions = client.get_game_versions()
        elif software_type == "neoforge":
            versions = client.get_versions()
        elif software_type == "forge":
            # Forgeの場合、Minecraftバージョンのリストを返す
            versions = client.get_mc_versions()
        else:
            return jsonify({"error": f"Unsupported project type: {software_type}"}), 400
        
        return jsonify(versions)

    except ServerSoftwareException as e:
        logging.error(f"Server software API Error ({software_type}): {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/server_software/builds')
def software_builds_route():
    """指定されたソフトウェアタイプとバージョンのビルドリストを返す"""
    software_type = request.args.get('project')
    version = request.args.get('version')
    
    if not software_type:
        return jsonify({"error": "Project parameter is required"}), 400
    if not version:
        return jsonify({"error": "Version parameter is required"}), 400
    
    try:
        client = server_software_client.get_client(software_type)
        
        if software_type == "paper":
            builds = client.get_builds(version)
            return jsonify(builds)
        elif software_type == "purpur":
            builds = client.get_builds(version)
            return jsonify(builds)
        elif software_type == "fabric":
            # Fabricの場合、Loaderバージョンのリストを返す
            loader_versions = client.get_loader_versions()
            return jsonify(loader_versions)
        elif software_type == "forge":
            # Forgeの場合、指定されたMCバージョンのForgeバージョンリストを返す
            forge_versions = client.get_versions_by_mc_version(version)
            return jsonify(forge_versions)
        elif software_type in ["vanilla", "neoforge"]:
            # Vanilla と NeoForge にはビルドの概念がない
            return jsonify([])
        else:
            return jsonify({"error": f"Unsupported project type: {software_type}"}), 400

    except ServerSoftwareException as e:
        logging.error(f"Server software API Error ({software_type}): {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/server_software/install', methods=['POST'])
def install_server_software_route():
    """サーバーソフトウェアをダウンロードしてインストールする"""
    data = request.json
    software_type = data.get('project')
    version = data.get('version')
    build = data.get('build')  # オプション

    if not all([software_type, version]):
        return jsonify(status="Error", message="Project and version are required."), 400

    try:
        client = server_software_client.get_client(software_type)
        
        # ダウンロードURLとファイル名を取得
        if software_type == "vanilla":
            download_url, filename = client.get_download_url(version)
        elif software_type == "paper":
            download_url, filename = client.get_download_url(version, build)
        elif software_type == "purpur":
            download_url, filename = client.get_download_url(version, build)
        elif software_type == "fabric":
            # buildはloader_versionとして使用
            download_url, filename = client.get_download_url(version, build)
        elif software_type == "neoforge":
            download_url, filename = client.get_download_url(version)
        elif software_type == "forge":
            # versionはmc_version、buildはforge_versionとして使用
            download_url, filename = client.get_download_url(version, build)
        else:
            return jsonify(status="Error", message=f"Unsupported project type: {software_type}."), 400
        
        # ダウンロード実行
        socketio.emit('console_output', {'log': f"サーバーソフトウェア '{filename}' をダウンロード中..."})
        downloaded_path = sw_download_file(download_url, '.', filename)

        if downloaded_path:
            socketio.emit('console_output', {'log': f"'{filename}' のダウンロードが完了しました。"})
            
            # 設定を更新
            global config
            config['jar_path'] = os.path.basename(downloaded_path)
            mc.save_config(config)
            socketio.emit('console_output', {'log': f"サーバーJARパスを '{config['jar_path']}' に設定しました。"})

            return jsonify(status="Success", message=f"{filename} をダウンロードしました", jar_path=config['jar_path'])
        else:
            socketio.emit('console_output', {'log': f"ERROR: '{filename}' のダウンロードに失敗しました。"})
            return jsonify(status="Error", message="ダウンロードに失敗しました。"), 500

    except ServerSoftwareException as e:
        error_message = f"サーバーソフトウェアAPIエラー ({software_type}): {e}"
        logging.error(error_message)
        socketio.emit('console_output', {'log': f"ERROR: {error_message}"})
        return jsonify(status="Error", message=str(e)), 500

# --- Logic Functions ---
def start_ownserver_web_logic():
    """Ownserver (Web) を起動するロジック"""
    global ownserver_web_process
    if ownserver_web_process and ownserver_web_process.poll() is None:
        return False, "Already running"
    
    # mcserverhelperの関数を再利用
    proc = mc.setup_and_run_ownserver(port=5000, log_callback=lambda line: ownserver_log_callback('web', line))
    if proc:
        ownserver_web_process = proc
        socketio.emit('ownserver_status_update', {'type': 'web', 'status': 'Running'})
        return True, "起動しました"
    return False, "エラーが発生しました"

def stop_ownserver_web_logic():
    """Ownserver (Web) を停止するロジック"""
    global ownserver_web_process
    if ownserver_web_process and ownserver_web_process.poll() is None:
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
        return True, "停止しました"
    return False, "Already stopped"

def stop_all_services_logic():
    """すべての関連サービスを停止するロジック"""
    print("すべてのサービスを停止しています...")
    socketio.emit('console_output', {'log': "--- すべてのサービスを停止しています ---"})

    # 1. Minecraftサーバーを停止
    if get_server_status() == "Running":
        print("Minecraftサーバーを停止しています...")
        if mc.stop_server():
            socketio.emit('status_update', {'status': 'Stopped'})
            socketio.emit('console_output', {'log': "Minecraftサーバーを停止しました。"})
        else:
            socketio.emit('console_output', {'log': "Minecraftサーバーは既に停止していました。"})

    # 2. ownserver (MC) を停止
    if mc.ownserver_proc and mc.ownserver_proc.poll() is None:
        print("ownserver (MC) を停止しています...")
        if mc.stop_ownserver():
            socketio.emit('ownserver_status_update', {'type': 'mc', 'status': 'Stopped'})
            socketio.emit('console_output', {'log': "ownserver (MC) を停止しました。"})
        else:
            socketio.emit('console_output', {'log': "ownserver (MC) は既に停止していました。"})

    # 3. ownserver (Web) を停止
    stop_ownserver_web_logic()

    print("すべてのサービスが停止しました。")

# --- Ownserver API ---
def ownserver_log_callback(log_type, line):
    socketio.emit('ownserver_log', {'type': log_type, 'log': line})
    # URLが含まれる行のみコンソールに表示
    if "tcp://" in line:
        print(f"\n[公開URL] {line}")

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
    success, message = start_ownserver_web_logic()
    if success:
        return jsonify(status=message)
    elif message == "Already running":
        return jsonify(status=message), 400
    return jsonify(status=message), 500

@app.route('/api/ownserver/web/stop', methods=['POST'])
def stop_ownserver_web():
    success, message = stop_ownserver_web_logic()
    if success:
        return jsonify(status=message)
    return jsonify(status=message)

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
    stop_all_services_logic()
    
    print("Webサーバーをシャットダウンします。")
    socketio.emit('console_output', {'log': "--- Webサーバーをシャットダウンします ---"})
    
    # 4. Flaskサーバーをシャットダウン
    def shutdown():
        socketio.sleep(1)
        os._exit(0)

    socketio.start_background_task(shutdown)
    return jsonify(status="All services stopped. Shutting down.")


# --- SocketIO Events ---
@socketio.on('connect')
def handle_connect():
    """クライアント接続時のイベントハンドラ。"""
    # print('Client connected')
    # 接続時に現在の状態を送信
    emit('status_update', {'status': get_server_status()})

@socketio.on('disconnect')
def handle_disconnect():
    """クライアント切断時のイベントハンドラ。"""
    # print('Client disconnected')

# --- Main ---
def run_app():
    """Webサーバーを起動し、ブラウザを開き、CLIメニューを表示する。"""
    url = "http://127.0.0.1:5000"
    
    # Flaskサーバーをデーモンスレッドで起動
    # use_reloader=False は必須 (スレッド内でシグナルハンドラが動作しないため、また2重起動防止)
    server_thread = threading.Thread(target=lambda: socketio.run(app, host='127.0.0.1', port=5000, use_reloader=False, log_output=False))
    server_thread.daemon = True
    server_thread.start()

    # 少し待ってからブラウザを開く
    time.sleep(1)
    print(f"\nWebUIのローカルアドレス: {url}")
    print("ブラウザを自動的に開いています...")
    webbrowser.open(url)

    # CLIメニュー
    while True:
        print("\n[操作を選択してください]")
        print("1. OwnserverでWebUIを公開")
        print("2. 全てのサービスを停止")
        try:
            choice = input("番号を入力: ")
            if choice == '1':
                print("OwnserverでWebUIを公開します...")
                success, msg = start_ownserver_web_logic()
                if success:
                    print(f"成功: {msg}")
                else:
                    print(f"状態: {msg}")
            elif choice == '2':
                print("全てのサービスを停止しています...")
                stop_all_services_logic()
                print("終了します。")
                os._exit(0)
            else:
                print("無効な選択です。")
        except (KeyboardInterrupt, EOFError):
            print("\n終了します。")
            stop_all_services_logic()
            os._exit(0)

if __name__ == '__main__':
    run_app()
