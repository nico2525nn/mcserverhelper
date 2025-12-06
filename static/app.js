document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // --- DOM Elements ---
    const statusEl = document.getElementById('server-status');
    const startBtn = document.getElementById('start-server-btn');
    const stopBtn = document.getElementById('stop-server-btn');
    const consoleOutput = document.getElementById('console-output');
    const commandForm = document.getElementById('command-form');
    const commandInput = document.getElementById('command-input');
    const maxMemoryInput = document.getElementById('max-memory');
    const minMemoryInput = document.getElementById('min-memory');
    const worldTypeSelect = document.getElementById('world-type');

    // Ownserver MC
    const ownserverMcStatusEl = document.getElementById('ownserver-mc-status');
    const startOwnserverMcBtn = document.getElementById('start-ownserver-mc-btn');
    const stopOwnserverMcBtn = document.getElementById('stop-ownserver-mc-btn');
    const ownserverMcLog = document.getElementById('ownserver-mc-log');

    // Ownserver Web
    const ownserverWebStatusEl = document.getElementById('ownserver-web-status');
    const startOwnserverWebBtn = document.getElementById('start-ownserver-web-btn');
    const stopOwnserverWebBtn = document.getElementById('stop-ownserver-web-btn');
    const ownserverWebLog = document.getElementById('ownserver-web-log');

    // Backups
    const createBackupBtn = document.getElementById('create-backup-btn');
    const backupList = document.getElementById('backup-list');
    const restoreBackupBtn = document.getElementById('restore-backup-btn');

    // Config
    const configForm = document.getElementById('config-form');
    const jarPathInput = document.getElementById('jar-path-input');

    // Server Properties
    const propertiesForm = document.getElementById('properties-form');
    const propertiesContainer = document.getElementById('properties-container');

    // Quick Commands
    const quickCommandsContainer = document.querySelector('.quick-commands');

    // System
    const shutdownBtn = document.getElementById('shutdown-btn');


    // --- Helper Functions ---
    const updateStatus = (status) => {
        statusEl.textContent = status;
        if (status === 'Running') {
            statusEl.className = 'status-running';
            startBtn.disabled = true;
            stopBtn.disabled = false;
            commandInput.disabled = false;
        } else {
            statusEl.className = 'status-stopped';
            startBtn.disabled = false;
            stopBtn.disabled = true;
            commandInput.disabled = true;
        }
    };

    const updateOwnserverStatus = (type, status) => {
        const statusEl = type === 'mc' ? ownserverMcStatusEl : ownserverWebStatusEl;
        const startBtn = type === 'mc' ? startOwnserverMcBtn : startOwnserverWebBtn;
        const stopBtn = type === 'mc' ? stopOwnserverMcBtn : stopOwnserverWebBtn;

        statusEl.textContent = status;
        if (status === 'Running') {
            statusEl.className = 'status-running';
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusEl.className = 'status-stopped';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    };

    const addLog = (element, message, isHtml = false) => {
        if (isHtml) {
            element.innerHTML += message + '<br>';
        } else {
            element.textContent += message + '\n';
        }
        // Auto-scroll to the bottom
        element.parentElement.scrollTop = element.parentElement.scrollHeight;
    };

    // --- Socket.IO Event Handlers ---
    socket.on('connect', () => {
        console.log('Connected to server');
        addLog('--- WebUI connected ---');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        addLog(consoleOutput, '--- WebUI disconnected ---');
        updateStatus('Unknown');
    });

    socket.on('status_update', (data) => {
        console.log('Status update:', data.status);
        updateStatus(data.status);
    });

    socket.on('console_output', (data) => {
        addLog(consoleOutput, data.log.trim());
    });

    socket.on('ownserver_status_update', (data) => {
        updateOwnserverStatus(data.type, data.status);
    });

    socket.on('ownserver_log', (data) => {
        const logEl = data.type === 'mc' ? ownserverMcLog : ownserverWebLog;
        addLog(logEl, data.log.trim());
    });

    // --- DOM Event Listeners ---

    // Server Control
    startBtn.addEventListener('click', () => {
        const maxMem = maxMemoryInput.value || '2';
        const minMem = minMemoryInput.value || '1';
        const worldType = worldTypeSelect.value;

        addLog(consoleOutput, '--- Starting server... ---');
        fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                xmx: `${maxMem}G`,
                xms: `${minMem}G`,
                world_type: worldType
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.status !== 'Started') {
                    addLog(consoleOutput, `--- Start failed: ${data.message || 'Check console'} ---`);
                }
            })
            .catch(err => {
                console.error('Error starting server:', err);
                addLog(consoleOutput, '--- Start failed: Network or server error ---');
            });
    });

    stopBtn.addEventListener('click', () => {
        addLog(consoleOutput, '--- Stopping server... ---');
        fetch('/api/stop', { method: 'POST' })
            .catch(err => console.error('Error stopping server:', err));
    });

    commandForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const command = commandInput.value;
        if (command) {
            fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: command })
            })
                .catch(err => console.error('Error sending command:', err));
            commandInput.value = '';
        }
    });

    // Ownserver MC
    startOwnserverMcBtn.addEventListener('click', () => {
        addLog(ownserverMcLog, '--- Starting Ownserver for MC... ---');
        fetch('/api/ownserver/mc/start', { method: 'POST' });
    });
    stopOwnserverMcBtn.addEventListener('click', () => {
        addLog(ownserverMcLog, '--- Stopping Ownserver for MC... ---');
        fetch('/api/ownserver/mc/stop', { method: 'POST' });
    });

    // Ownserver Web
    startOwnserverWebBtn.addEventListener('click', () => {
        addLog(ownserverWebLog, '--- Starting Ownserver for WebUI... ---');
        fetch('/api/ownserver/web/start', { method: 'POST' });
    });
    stopOwnserverWebBtn.addEventListener('click', () => {
        addLog(ownserverWebLog, '--- Stopping Ownserver for WebUI... ---');
        fetch('/api/ownserver/web/stop', { method: 'POST' });
    });

    // Backups
    const refreshBackupList = () => {
        fetch('/api/backups')
            .then(res => res.json())
            .then(data => {
                backupList.innerHTML = '';
                if (data.backups && data.backups.length > 0) {
                    data.backups.forEach(file => {
                        const option = document.createElement('option');
                        option.value = file;
                        option.textContent = file;
                        backupList.appendChild(option);
                    });
                    restoreBackupBtn.disabled = false;
                } else {
                    const option = document.createElement('option');
                    option.textContent = 'バックアップはありません';
                    backupList.appendChild(option);
                    restoreBackupBtn.disabled = true;
                }
            });
    };

    createBackupBtn.addEventListener('click', () => {
        addLog(consoleOutput, '--- Creating backup... ---');
        createBackupBtn.disabled = true;
        fetch('/api/backups/create', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'Success') {
                    addLog(consoleOutput, `--- Backup created: ${data.filename} ---`);
                    refreshBackupList();
                } else {
                    addLog(consoleOutput, `--- Backup failed ---`);
                }
            })
            .finally(() => {
                createBackupBtn.disabled = false;
            });
    });

    restoreBackupBtn.addEventListener('click', () => {
        const filename = backupList.value;
        if (!filename || !confirm(`本当に '${filename}' を復元しますか？\n現在のワールドは削除されます！`)) {
            return;
        }
        addLog(consoleOutput, `--- Restoring backup: ${filename} ---`);
        fetch('/api/backups/restore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        })
            .then(res => res.json())
            .then(data => {
                addLog(consoleOutput, `--- ${data.message} ---`);
            });
    });

    // Config
    configForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const newJarPath = jarPathInput.value;
        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jar_path: newJarPath })
        })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
            });
    });

    // Quick Commands
    if (quickCommandsContainer) {
        quickCommandsContainer.addEventListener('click', (e) => {
            if (!e.target.matches('.qc-btn')) return;

            const command = e.target.dataset.command;
            const playerNameInput = document.getElementById('player-name-input');
            const player = playerNameInput.value;

            const playerCommands = ['op', 'deop', 'kick', 'ban', 'pardon'];

            if (playerCommands.includes(command) && !player) {
                alert('プレイヤー名を入力してください。');
                playerNameInput.focus();
                return;
            }

            // 確認ダイアログ
            if (command === 'ban' && !confirm(`本当にプレイヤー '${player}' をBANしますか？`)) {
                return;
            }

            fetch('/api/quick_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: command,
                    player: player
                })
            }).catch(err => console.error('Error sending quick command:', err));
        });
    }

    // --- Server Properties ---
    let propsDef = {}; // Make propsDef available in the wider scope

    const buildPropertiesForm = async () => {
        try {
            // Fetch definitions and current values in parallel
            const [propsRes, currentPropsRes] = await Promise.all([
                fetch('/static/server_properties_jp.json'),
                fetch('/api/properties')
            ]);

            if (!propsRes.ok || !currentPropsRes.ok) {
                throw new Error('Failed to load property data');
            }

            propsDef = await propsRes.json(); // Assign to the outer scope variable
            const currentProps = await currentPropsRes.json();

            propertiesContainer.innerHTML = ''; // Clear existing

            for (const key in propsDef) {
                const def = propsDef[key];
                const currentValue = currentProps[key] !== undefined ? currentProps[key] : '';

                const item = document.createElement('div');
                item.className = 'property-item';

                let inputHtml = '';
                const inputId = `prop-${key}`;

                switch (def.type) {
                    case 'boolean':
                        inputHtml = `
                            <div class="input-wrapper">
                                <input type="checkbox" id="${inputId}" name="${key}" ${currentValue === 'true' ? 'checked' : ''}>
                            </div>`;
                        break;
                    case 'integer':
                        inputHtml = `
                            <div class="input-wrapper">
                                <input type="number" id="${inputId}" name="${key}" value="${currentValue}">
                            </div>`;
                        break;
                    case 'enum':
                        const optionsHtml = def.options.map(opt =>
                            `<option value="${opt}" ${currentValue === opt ? 'selected' : ''}>${opt}</option>`
                        ).join('');
                        inputHtml = `
                            <div class="input-wrapper">
                                <select id="${inputId}" name="${key}">${optionsHtml}</select>
                            </div>`;
                        break;
                    case 'string':
                    default:
                        inputHtml = `
                            <div class="input-wrapper">
                                <input type="text" id="${inputId}" name="${key}" value="${currentValue}">
                            </div>`;
                        break;
                }

                item.innerHTML = `
                    <div>
                        <label for="${inputId}">${def.jp}</label>
                        <p class="description">${def.desc}</p>
                    </div>
                    ${inputHtml}
                `;
                propertiesContainer.appendChild(item);
            }

        } catch (error) {
            console.error('Error building properties form:', error);
            propertiesContainer.innerHTML = '<p>サーバープロパティの読み込みに失敗しました。</p>';
        }
    };

    if (propertiesForm) {
        propertiesForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(propertiesForm);
            const data = {};
            // FormData doesn't include unchecked checkboxes, so we need to handle them
            for (const key in propsDef) {
                if (propsDef[key].type === 'boolean') {
                    data[key] = formData.has(key) ? 'true' : 'false';
                } else {
                    data[key] = formData.get(key);
                }
            }

            fetch('/api/properties', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
                .then(res => res.json())
                .then(result => {
                    alert(result.message);
                    if (result.status === 'Success') {
                        addLog(consoleOutput, '--- Server properties saved. A restart may be required for some changes. ---');
                    }
                })
                .catch(err => {
                    console.error('Error saving properties:', err);
                    alert('プロパティの保存中にエラーが発生しました。');
                });
        });
    }

    const propertySearchInput = document.getElementById('property-search-input');
    if (propertySearchInput) {
        propertySearchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const items = propertiesContainer.querySelectorAll('.property-item');

            items.forEach(item => {
                const label = item.querySelector('label').textContent.toLowerCase();
                const desc = item.querySelector('.description').textContent.toLowerCase();
                const inputElement = item.querySelector('[name]');
                const key = inputElement ? inputElement.name.toLowerCase() : '';

                if (label.includes(query) || desc.includes(query) || key.includes(query)) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }


    // --- Server Software Downloader ---
    const softwareTypeSelect = document.getElementById('software-type-select');
    const softwareMcVersionSelect = document.getElementById('software-mc-version-select');
    const softwareBuildSelect = document.getElementById('software-build-select');
    const downloadSoftwareBtn = document.getElementById('download-software-btn');

    const initSoftwareDownloader = async () => {
        try {
            const response = await fetch('/api/server_software/types');
            const types = await response.json();
            softwareTypeSelect.innerHTML = '';
            types.forEach(type => {
                const option = new Option(type.name, type.id);
                softwareTypeSelect.add(option);
            });
            softwareTypeSelect.disabled = false;
            // Trigger change to load versions for the default selection
            softwareTypeSelect.dispatchEvent(new Event('change'));
        } catch (error) {
            console.error('Error fetching software types:', error);
            softwareTypeSelect.innerHTML = '<option>Error loading types</option>';
        }
    };

    softwareTypeSelect.addEventListener('change', async () => {
        const project = softwareTypeSelect.value;
        softwareMcVersionSelect.disabled = true;
        softwareBuildSelect.disabled = true;
        downloadSoftwareBtn.disabled = true;
        softwareMcVersionSelect.innerHTML = '<option>Loading...</option>';
        try {
            const response = await fetch(`/api/server_software/versions?project=${project}`);
            const versions = await response.json();
            softwareMcVersionSelect.innerHTML = '';
            versions.forEach(version => {
                const option = new Option(version, version);
                softwareMcVersionSelect.add(option);
            });
            softwareMcVersionSelect.disabled = false;
            softwareMcVersionSelect.dispatchEvent(new Event('change')); // Trigger build load
        } catch (error) {
            console.error('Error fetching software versions:', error);
            softwareMcVersionSelect.innerHTML = '<option>Error</option>';
        }
    });

    softwareMcVersionSelect.addEventListener('change', async () => {
        const project = softwareTypeSelect.value;
        const version = softwareMcVersionSelect.value;
        softwareBuildSelect.disabled = true;
        downloadSoftwareBtn.disabled = true;

        if (project === 'vanilla') {
            softwareBuildSelect.innerHTML = '<option value="">ビルドなし</option>';
            softwareBuildSelect.disabled = true; // Vanilla has no builds
            downloadSoftwareBtn.disabled = false; // Enable download for Vanilla without build
            return;
        }

        softwareBuildSelect.innerHTML = '<option>Loading...</option>';
        try {
            const response = await fetch(`/api/server_software/builds?project=${project}&version=${version}`);
            const builds = await response.json();
            softwareBuildSelect.innerHTML = '';
            builds.forEach(build => {
                const option = new Option(`Build #${build}`, build);
                softwareBuildSelect.add(option);
            });
            softwareBuildSelect.disabled = false;
            downloadSoftwareBtn.disabled = false;
        } catch (error) {
            console.error('Error fetching software builds:', error);
            softwareBuildSelect.innerHTML = '<option>Error</option>';
        }
    });

    downloadSoftwareBtn.addEventListener('click', async () => {
        const project = softwareTypeSelect.value;
        const version = softwareMcVersionSelect.value;
        const build = softwareBuildSelect.value; // May be empty for Vanilla

        if (!project || !version || (project !== 'vanilla' && !build)) { // Build is required for non-Vanilla
            alert('すべての項目を選択してください。');
            return;
        }

        downloadSoftwareBtn.disabled = true;
        downloadSoftwareBtn.textContent = 'ダウンロード中...';

        try {
            const response = await fetch('/api/server_software/install', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project, version, build })
            });
            const result = await response.json();

            if (result.status === 'Success') {
                addLog(consoleOutput, `--- ${result.message} ---`);
                jarPathInput.value = result.jar_path; // Update the manual path input
                alert('サーバーソフトウェアのダウンロードと設定が完了しました。');
            } else {
                addLog(consoleOutput, `--- ERROR: ${result.message} ---`);
                alert(`エラー: ${result.message}`);
            }

        } catch (error) {
            console.error('Error installing server software:', error);
            addLog(consoleOutput, '--- ERROR: サーバーソフトウェアのインストールに失敗しました。 ---');
        } finally {
            downloadSoftwareBtn.disabled = false;
            downloadSoftwareBtn.textContent = 'ダウンロード＆設定';
        }
    });


    // --- Initial State ---
    fetch('/api/status').then(res => res.json()).then(data => updateStatus(data.status));
    fetch('/api/ownserver/status').then(res => res.json()).then(data => {
        updateOwnserverStatus('mc', data.mc);
        updateOwnserverStatus('web', data.web);
    });
    fetch('/api/config').then(res => res.json()).then(data => jarPathInput.value = data.jar_path);
    refreshBackupList();
    buildPropertiesForm();
    initSoftwareDownloader();

    // System Shutdown
    if (shutdownBtn) {
        shutdownBtn.addEventListener('click', () => {
            if (confirm('本当にすべてのサービスを停止してアプリケーションを終了しますか？')) {
                addLog(consoleOutput, '--- Shutting down all services... ---');

                // Disable all buttons to prevent further actions
                document.querySelectorAll('button').forEach(btn => btn.disabled = true);

                fetch('/api/stop_all', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        addLog(consoleOutput, `--- ${data.status} ---`);
                        addLog(consoleOutput, '--- アプリケーションは終了しました。このタブを閉じてください。 ---');

                        // タブを閉じる試み（JavaScriptで開いたタブのみ成功）
                        setTimeout(() => {
                            const closed = window.close();
                            if (!closed) {
                                // タブを閉じられなかった場合、ユーザーに通知
                                alert('アプリケーションは終了しました。このタブを手動で閉じてください。');
                            }
                        }, 1500);
                    })
                    .catch(err => {
                        console.error('Error shutting down:', err);
                        addLog(consoleOutput, '--- Shutdown failed. Please check the application console. ---');
                        // Re-enable buttons if shutdown fails
                        document.querySelectorAll('button').forEach(btn => {
                            // We need to re-evaluate which buttons should be enabled
                            // For simplicity, we'll just reload the page to reset state.
                            window.location.reload();
                        });
                    });
            }
        });
    }

    // --- Mods, Plugins & Modrinth ---
    const modDropZone = document.getElementById('mod-drop-zone');
    const pluginDropZone = document.getElementById('plugin-drop-zone');
    const modList = document.getElementById('mod-list');
    const pluginList = document.getElementById('plugin-list');

    const modrinthSearchBtn = document.getElementById('modrinth-search-btn');
    const modrinthSearchQuery = document.getElementById('modrinth-search-query');
    const modrinthGameVersion = document.getElementById('modrinth-game-version');
    const modrinthLoader = document.getElementById('modrinth-loader');
    const modrinthProjectType = document.getElementById('modrinth-project-type');
    const modrinthResultsContainer = document.getElementById('modrinth-results-container');
    const checkUpdatesBtn = document.getElementById('check-updates-btn');

    // --- Functions for this section ---

    const refreshInstalledList = async (updates = []) => {
        if (!modList && !pluginList) return;

        try {
            const response = await fetch('/api/installed_projects');
            const projects = await response.json();

            if (modList) modList.innerHTML = '';
            if (pluginList) pluginList.innerHTML = '';

            if (Object.keys(projects).length === 0) {
                if (modList) modList.innerHTML = '<p>Modはインストールされていません。</p>';
                if (pluginList) pluginList.innerHTML = '<p>Pluginはインストールされていません。</p>';
                return;
            }

            for (const filename in projects) {
                const project = projects[filename];
                // Mod と Datapack は modList に、Plugin は pluginList に振り分け
                const targetList = (project.project_type === 'plugin') ? pluginList : modList;
                if (!targetList) continue;

                const updateInfo = updates.find(u => u.filename === filename);
                const item = document.createElement('div');
                item.className = 'file-list-item installed-project-card';

                let updateButtonHtml = '';
                if (updateInfo) {
                    updateButtonHtml = `<button class="update-btn" data-project-id="${updateInfo.project_id}" data-version-id="${updateInfo.latest_version_id}" data-project-type="${updateInfo.project_type}" title="Update to ${updateInfo.latest_version_name}">更新</button>`;
                }

                item.innerHTML = `
                    <img src="${project.icon_url}" alt="${project.project_title}" class="installed-project-icon">
                    <div class="installed-project-info">
                        <a href="https://modrinth.com/project/${project.project_id}" target="_blank" class="project-title">${project.project_title}</a>
                        <span class="project-version">${project.version_name} ${updateInfo ? `-> <strong class="update-available">${updateInfo.latest_version_name}</strong>` : ''}</span>
                        <span class="file-name">${project.installed_file}</span>
                    </div>
                    <div class="actions">
                        ${updateButtonHtml}
                        <button class="delete-btn" data-filename="${filename}" data-type="${project.project_type}">削除</button>
                    </div>
                `;
                targetList.appendChild(item);
            }

            if (modList && !modList.hasChildNodes()) modList.innerHTML = '<p>Modはインストールされていません。</p>';
            if (pluginList && !pluginList.hasChildNodes()) pluginList.innerHTML = '<p>Pluginはインストールされていません。</p>';

        } catch (error) {
            console.error('Error fetching installed projects:', error);
            if (modList) modList.innerHTML = '<p>インストール済みリストの読み込みに失敗しました。</p>';
            if (pluginList) pluginList.innerHTML = '<p>インストール済みリストの読み込みに失敗しました。</p>';
        }
    };

    const uploadFiles = (files, type) => {
        const statusContainer = document.getElementById(`${type}-upload-status`);
        if (!statusContainer) return;
        statusContainer.innerHTML = '';
        const uploadPromises = Array.from(files).map(file => {
            if (!file.name.endsWith('.jar')) {
                const statusItem = document.createElement('div');
                statusItem.className = 'status-item error';
                statusItem.textContent = `${file.name} - Error: Only .jar files are allowed.`;
                statusContainer.appendChild(statusItem);
                return Promise.resolve();
            }
            const formData = new FormData();
            formData.append('file', file);
            const statusItem = document.createElement('div');
            statusItem.className = 'status-item';
            statusItem.textContent = `${file.name} - Uploading...`;
            statusContainer.appendChild(statusItem);
            return fetch(`/api/upload_${type}`, { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'Success') {
                        statusItem.textContent = `${data.filename} - Upload successful!`;
                        statusItem.classList.add('success');
                    } else {
                        statusItem.textContent = `${file.name} - Error: ${data.message}`;
                        statusItem.classList.add('error');
                    }
                })
                .catch(err => {
                    console.error(`Error uploading ${type}:`, err);
                    statusItem.textContent = `${file.name} - Upload failed.`;
                    statusItem.classList.add('error');
                });
        });
        Promise.allSettled(uploadPromises).then(() => refreshInstalledList());
    };

    const setupDropZone = (dropZone, fileInput, type) => {
        if (!dropZone) return;
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => dropZone.addEventListener(eventName, e => { e.preventDefault(); e.stopPropagation(); }));
        ['dragenter', 'dragover'].forEach(eventName => dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over')));
        ['dragleave', 'drop'].forEach(eventName => dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over')));
        dropZone.addEventListener('drop', e => uploadFiles(e.dataTransfer.files, type));
        fileInput.addEventListener('change', e => uploadFiles(e.target.files, type));
    };

    const setupFileListListeners = (listEl) => {
        if (!listEl) return;
        listEl.addEventListener('click', e => {
            const button = e.target;
            if (button.matches('.delete-btn')) {
                const filename = button.dataset.filename;
                const type = button.dataset.type;
                if (confirm(`本当に'${filename}'を削除しますか？`)) {
                    fetch(`/api/delete_${type}/${filename}`, { method: 'DELETE' })
                        .then(res => res.json())
                        .then(data => data.status === 'Success' ? refreshInstalledList() : alert(`Error: ${data.message}`))
                        .catch(err => { console.error(`Error deleting ${type}:`, err); alert('ファイルの削除中にエラーが発生しました。'); });
                }
            }
            if (button.matches('.update-btn')) {
                handleModrinthInstall(button.dataset.projectId, button.dataset.versionId, button.dataset.projectType, button);
            }
        });
    };

    const handleModrinthInstall = async (projectId, versionId, projectType, button) => {
        if (!versionId || !projectId) { alert('プロジェクトとバージョンを選択してください。'); return; }

        // デバッグログ
        console.log('[DEBUG] Modrinth Install:', { projectId, versionId, projectType });

        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = '処理中...';
        try {
            const response = await fetch('/api/modrinth/install', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_id: projectId, version_id: versionId, project_type: projectType })
            });
            const result = await response.json();

            // レスポンスをログに出力
            console.log('[DEBUG] Install Response:', result);

            if (result.status === 'Success') {
                button.textContent = '完了';
                button.style.backgroundColor = 'var(--success)';
                refreshInstalledList();
            } else {
                button.textContent = 'エラー';
                button.style.backgroundColor = 'var(--danger)';
                alert(`処理失敗: ${result.message}`);
            }
        } catch (error) {
            console.error('Error with Modrinth installation/update:', error);
            button.textContent = 'エラー';
            button.style.backgroundColor = 'var(--danger)';
            alert('処理中にエラーが発生しました。');
        } finally {
            setTimeout(() => {
                button.disabled = false;
                button.textContent = originalText;
                button.style.backgroundColor = '';
            }, 3000);
        }
    };


    const fetchProjectVersions = async (projectId, selectElement) => {
        const installBtn = selectElement.nextElementSibling;

        // カードからproject_typeを取得
        const card = selectElement.closest('.modrinth-result-card');
        const projectType = card ? card.dataset.projectType : null;

        try {
            const params = new URLSearchParams();

            // プロジェクトタイプに応じて適切なローダーを自動設定
            let loaders = [];
            if (projectType === 'plugin') {
                // Pluginの場合: サーバー系ローダー
                loaders = ['bukkit', 'spigot', 'paper', 'purpur', 'folia'];
            } else if (projectType === 'mod') {
                // Modの場合: クライアント/サーバー系ローダー
                loaders = ['forge', 'fabric', 'quilt', 'neoforge'];
            }
            // Datapackの場合はローダー指定なし

            // ユーザーがローダーを明示的に選択している場合は、それを優先
            if (modrinthLoader.value) {
                params.append('loaders', modrinthLoader.value);
            } else if (loaders.length > 0) {
                // 自動設定されたローダーを使用（JSON配列形式）
                params.append('loaders', JSON.stringify(loaders));
            }

            if (modrinthGameVersion.value) params.append('game_versions', modrinthGameVersion.value);

            console.log('[DEBUG] Fetching versions with loaders:', loaders.length > 0 ? loaders : modrinthLoader.value || 'none');

            const response = await fetch(`/api/modrinth/project/${projectId}/versions?${params.toString()}`);
            const versions = await response.json();
            selectElement.innerHTML = '';
            if (versions && versions.length > 0) {
                versions.forEach(version => {
                    const option = document.createElement('option');
                    option.value = version.id;
                    option.textContent = version.name;
                    option.title = `MC: ${version.game_versions.join(', ')} | Loader: ${version.loaders.join(', ')}`;
                    selectElement.appendChild(option);
                });
                selectElement.disabled = false;
                installBtn.disabled = false;
            } else {
                selectElement.innerHTML = '<option>利用可能なバージョンなし</option>';
            }
        } catch (error) {
            console.error('Error fetching project versions:', error);
            selectElement.innerHTML = '<option>取得エラー</option>';
        }
    };

    const renderModrinthResults = (results, searchProjectType) => {
        console.log('[DEBUG] Rendering results with project_type:', searchProjectType);

        modrinthResultsContainer.innerHTML = '';
        if (!results || !results.hits || results.hits.length === 0) {
            modrinthResultsContainer.innerHTML = '<p>検索結果が見つかりませんでした。</p>';
            return;
        }
        results.hits.forEach(hit => {
            const card = document.createElement('div');
            card.className = 'modrinth-result-card';
            card.dataset.projectId = hit.project_id;
            // 検索条件で指定したproject_typeを使用（APIのproject_typeではなく）
            card.dataset.projectType = searchProjectType;

            console.log('[DEBUG] Card created:', {
                title: hit.title,
                projectId: hit.project_id,
                projectType: card.dataset.projectType,
                apiProjectType: hit.project_type
            });

            const downloads = hit.downloads.toLocaleString();
            const follows = hit.follows.toLocaleString();
            card.innerHTML = `
                <img src="${hit.icon_url}" alt="${hit.title}" class="icon">
                <div class="info">
                    <h3 class="title" title="${hit.title}">${hit.title}</h3>
                    <p class="description">${hit.summary}</p>
                    <div class="meta">
                        <span class="meta-item" title="Downloads">📥 ${downloads}</span>
                        <span class="meta-item" title="Follows">⭐ ${follows}</span>
                        <span class="meta-item" title="Created">📅 ${new Date(hit.date_created).toLocaleDateString()}</span>
                    </div>
                </div>
                <div class="actions">
                    <select class="version-select" disabled><option>バージョンを選択</option></select>
                    <button class="install-btn" disabled>インストール</button>
                </div>`;
            modrinthResultsContainer.appendChild(card);
            fetchProjectVersions(hit.project_id, card.querySelector('.version-select'));
        });
    };

    const handleModrinthSearch = async () => {
        const searchProjectType = modrinthProjectType.value; // 検索条件で指定したproject_type

        console.log('[DEBUG] Search initiated with project_type:', searchProjectType);
        console.log('[DEBUG] Dropdown value:', modrinthProjectType.value);

        const params = new URLSearchParams({
            query: modrinthSearchQuery.value,
            game_version: modrinthGameVersion.value,
            loader: modrinthLoader.value,
            project_type: searchProjectType,
            limit: 20
        });
        modrinthSearchBtn.disabled = true;
        modrinthSearchBtn.textContent = '検索中...';
        modrinthResultsContainer.innerHTML = '<p>Modrinthから検索しています...</p>';
        try {
            const response = await fetch(`/api/modrinth/search?${params.toString()}`);
            const results = await response.json();
            renderModrinthResults(results, searchProjectType); // 検索条件のproject_typeを渡す
        } catch (error) {
            console.error('Error searching Modrinth:', error);
            modrinthResultsContainer.innerHTML = '<p>検索中にエラーが発生しました。</p>';
        } finally {
            modrinthSearchBtn.disabled = false;
            modrinthSearchBtn.textContent = '検索';
        }
    };

    // --- Event Listeners for this section ---
    if (modDropZone) {
        setupDropZone(modDropZone, document.getElementById('mod-file-input'), 'mod');
        setupFileListListeners(modList);
        refreshInstalledList();
    }
    if (pluginDropZone) {
        setupDropZone(pluginDropZone, document.getElementById('plugin-file-input'), 'plugin');
        setupFileListListeners(pluginList);
        refreshInstalledList(); // This might be redundant if modDropZone exists, but safe
    }
    if (modrinthSearchBtn) {
        modrinthSearchBtn.addEventListener('click', handleModrinthSearch);
        modrinthSearchQuery.addEventListener('keypress', e => { if (e.key === 'Enter') handleModrinthSearch(); });
        modrinthGameVersion.addEventListener('keypress', e => { if (e.key === 'Enter') handleModrinthSearch(); });
    }
    if (modrinthResultsContainer) {
        modrinthResultsContainer.addEventListener('click', e => {
            if (e.target.classList.contains('install-btn')) {
                const card = e.target.closest('.modrinth-result-card');
                const versionSelect = card.querySelector('.version-select');
                handleModrinthInstall(card.dataset.projectId, versionSelect.value, card.dataset.projectType, e.target);
            }
        });
    }
    if (checkUpdatesBtn) {
        checkUpdatesBtn.addEventListener('click', async () => {
            checkUpdatesBtn.disabled = true;
            checkUpdatesBtn.textContent = 'チェック中...';
            try {
                const response = await fetch('/api/modrinth/check_updates', { method: 'POST' });
                const updates = await response.json();
                // Update the list first
                await refreshInstalledList(updates);

                // Then show the alert
                if (updates.length > 0) {
                    alert(`${updates.length}件の更新が見つかりました。リストを確認してください。`);
                } else {
                    alert('利用可能な更新はありません。');
                }

            } catch (error) {
                console.error('Error checking for updates:', error);
                alert('更新のチェック中にエラーが発生しました。');
            } finally {
                checkUpdatesBtn.disabled = false;
                checkUpdatesBtn.textContent = '更新をチェック';
            }
        });
    }

    // Open Server Folder
    const openFolderBtn = document.getElementById('open-folder-btn');
    if (openFolderBtn) {
        openFolderBtn.addEventListener('click', () => {
            fetch('/api/open_folder', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.status !== 'Success') {
                        alert('フォルダを開けませんでした: ' + (data.message || 'Unknown error'));
                    }
                })
                .catch(err => console.error('Error opening folder:', err));
        });
    }

    // --- Tab Navigation ---
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.tab;

            // Deactivate all
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Activate target
            btn.classList.add('active');
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    console.log("MC Server Helper UI Initialized");
});
