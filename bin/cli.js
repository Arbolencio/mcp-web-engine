#!/usr/bin/env node

/**
 * MCP Web Engine CLI Entry Point (npm package executable)
 * Spawns the MCP Web Engine Python server (stdio/SSE)
 * Respects SEARXNG_URL, PORT, ALLOWED_NETWORKS, and environment settings.
 */

const { spawn, execSync } = require('child_process');
const path = require('path');

const mainPy = path.join(__dirname, '..', 'main.py');
const reqTxt = path.join(__dirname, '..', 'requirements.txt');

function findPython() {
  const candidates = ['python3', 'python'];
  for (const cmd of candidates) {
    try {
      execSync(`${cmd} --version`, { stdio: 'ignore' });
      return cmd;
    } catch (e) {}
  }
  return 'python3';
}

const pythonCmd = findPython();

// Auto-check and install python dependencies if missing (pip logs sent to stderr to preserve stdio JSON-RPC)
try {
  execSync(`${pythonCmd} -c "import fastapi, uvicorn, requests, bs4"`, { stdio: 'ignore' });
} catch (e) {
  try {
    execSync(`${pythonCmd} -m pip install -r "${reqTxt}" --break-system-packages`, { stdio: [0, 2, 2] });
  } catch (err) {
    // Fallback gracefully
  }
}

// Spawn MCP Web Engine
const child = spawn(pythonCmd, [mainPy, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: process.env
});

child.on('error', (err) => {
  console.error('[mcp-web-engine] Failed to start Python process:', err.message);
  process.exit(1);
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.exit(128 + (signal === 'SIGINT' ? 2 : 15));
  }
  process.exit(code ?? 0);
});
