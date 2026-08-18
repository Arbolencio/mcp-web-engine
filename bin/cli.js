#!/usr/bin/env node
const { spawn, execSync } = require('child_process');
const path = require('path');

const mainPy = path.join(__dirname, '..', 'main.py');
const reqTxt = path.join(__dirname, '..', 'requirements.txt');

let pythonCmd = 'python3';

try {
  execSync(`${pythonCmd} -c "import fastapi"`, { stdio: 'ignore' });
} catch (e) {
  try {
    console.log('[mcp-web-engine] Installing Python dependencies (fastapi, uvicorn, etc.)...');
    execSync(`${pythonCmd} -m pip install -r "${reqTxt}" --break-system-packages`, { stdio: 'inherit' });
  } catch (err) {
    // Fallback gracefully
  }
}

const child = spawn(pythonCmd, [mainPy, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: process.env
});

child.on('error', (err) => {
  console.error('Failed to start mcp-web-engine python process:', err);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
