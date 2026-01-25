import { app, BrowserWindow, screen, ipcMain, dialog } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import * as fs from 'fs';

let backendProcess: ChildProcess | null = null;

function startBackend() {
    const isDev = !app.isPackaged;
    let scriptPath: string;
    let command: string;
    let args: string[] = [];

    if (isDev) {
        // In development, run the python script directly
        // Assuming we are running from the project root
        command = 'python3';
        scriptPath = path.join(__dirname, '../../backend/main.py');
        args = [scriptPath];
        console.log('Starting backend in DEV mode:', command, args);
    } else {
        // In production, run the bundled executable
        // PyInstaller one-dir mode creates a directory 'silicon_server' containing the binary 'silicon_server'
        // electron-builder copied the full path 'backend/dist/silicon_server' to Resources
        const binaryName = 'silicon_server';
        scriptPath = path.join(process.resourcesPath, 'backend', 'dist', 'silicon_server', binaryName);
        command = scriptPath;
        console.log('Starting backend in PROD mode:', command);
    }

    try {
        backendProcess = spawn(command, args, {
            cwd: isDev ? path.join(__dirname, '../../backend') : path.join(process.resourcesPath, 'backend', 'dist', 'silicon_server'),
            stdio: ['ignore', 'pipe', 'pipe']
        });

        backendProcess.on('error', (err) => {
            console.error('Failed to spawn backend process:', err);
            dialog.showErrorBox('Backend Error', `Failed to start backend: ${err.message}\nPath: ${command}`);
        });

    } catch (e) {
        console.error('Exception spawning backend:', e);
        if (e instanceof Error) {
            dialog.showErrorBox('Backend Exception', `Exception starting backend: ${e.message}`);
        }
    }

    // Log to console only (debug file logging disabled for production)
    if (backendProcess && backendProcess.stdout) {
        backendProcess.stdout.on('data', (data) => {
            console.log(`[Backend]: ${data.toString()}`);
        });
    }

    if (backendProcess && backendProcess.stderr) {
        backendProcess.stderr.on('data', (data) => {
            console.error(`[Backend Error]: ${data.toString()}`);
        });
    }

    if (backendProcess) {
        backendProcess.on('close', (code) => {
            console.log(`Backend process exited with code ${code}`);
            backendProcess = null;
        });
    }
}

function stopBackend() {
    if (backendProcess) {
        console.log('Stopping backend process...');
        backendProcess.kill();
        backendProcess = null;
    }
}

function createWindow() {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;

    const mainWindow = new BrowserWindow({
        width: Math.floor(width * 0.8),
        height: Math.floor(height * 0.9),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
        },
        titleBarStyle: 'hiddenInset', // Apple Native feel
        vibrancy: 'under-window',     // Apple Native blur
        visualEffectState: 'active',
        backgroundColor: '#00000000', // Transparent for vibrancy
    });

    // Load the Vite dev server URL in development, or the local index.html in production
    const isDev = !app.isPackaged;
    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        // mainWindow.webContents.openDevTools({ mode: 'detach' });
    } else {
        // In production, the file structure is:
        // dist/main/main.js (Current file)
        // dist/renderer/index.html
        mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
    }
}

app.whenReady().then(() => {
    // Start the Python Backend
    startBackend();

    ipcMain.handle('dialog:openFile', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openFile'],
            filters: [{ name: 'CSV/JSONL', extensions: ['csv', 'jsonl', 'json'] }]
        });
        if (result.canceled) return null;
        return result.filePaths[0];
    });

    ipcMain.handle('dialog:openDirectory', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openDirectory']
        });
        if (result.canceled) return null;
        return result.filePaths[0];
    });

    createWindow();

    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('will-quit', () => {
    stopBackend();
});

app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') app.quit();
});
