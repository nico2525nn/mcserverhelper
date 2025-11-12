document.addEventListener('DOMContentLoaded', () => {
    const socket = io({ transports: ['websocket'] });

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
                if(result.status === 'Success') {
                    // Optionally, re-read values to confirm they were set
                    addLog(consoleOutput, '--- Server properties saved. A restart may be required for some changes. ---');
                }
            })
            .catch(err => {
                console.error('Error saving properties:', err);
                alert('プロパティの保存中にエラーが発生しました。');
            });
        });
    }


    // --- Initial State ---
    fetch('/api/status').then(res => res.json()).then(data => updateStatus(data.status));
    fetch('/api/ownserver/status').then(res => res.json()).then(data => {
        updateOwnserverStatus('mc', data.mc);
        updateOwnserverStatus('web', data.web);
    });
    fetch('/api/config').then(res => res.json()).then(data => jarPathInput.value = data.jar_path);
    refreshBackupList();
    buildPropertiesForm();

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
                        // The server will shut down, so the connection will be lost.
                        // We can try to close the window after a short delay.
                        addLog(consoleOutput, '--- The application will close shortly. ---');
                        setTimeout(() => {
                            window.close();
                        }, 3000);
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

    console.log("MC Server Helper UI Initialized");
});
