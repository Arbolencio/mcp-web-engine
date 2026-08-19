#!/usr/bin/env node

/**
 * MCP Web Engine CLI Entry Point (npm / npx fallback)
 * Spawns MCP Web Engine in an ISOLATED Python environment without polluting global system packages.
 * 
 * Recommended execution for AI agents:
 *   uvx mcp-web-engine
 */

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const reqTxt = path.join(__dirname, '..', 'requirements.txt');

function forwardChild(child) {
  child.on('error', (err) => {
    console.error('[mcp-web-engine] Failed to start process:', err.message);
    process.exit(1);
  });
  child.on('exit', (code, signal) => {
    if (signal) {
      process.exit(128 + (signal === 'SIGINT' ? 2 : 15));
    }
    process.exit(code ?? 0);
  });
}

// 1. Try running with 'uv' if available (fastest, cleanest, isolated)
function tryUv() {
  try {
    execSync('uv --version', { stdio: 'ignore' });
    const repoRoot = path.join(__dirname, '..');
    const child = spawn('uv', ['run', '--directory', repoRoot, 'python', '-m', 'mcp_web_engine.main', ...process.argv.slice(2)], {
      stdio: 'inherit',
      env: process.env
    });
    forwardChild(child);
    return true;
  } catch (e) {
    return false;
  }
}

// 2. Fallback to dedicated isolated virtualenv in user cache dir (~/.cache/mcp-web-engine/venv)
function runInIsolatedVenv() {
  const cacheDir = process.env.XDG_CACHE_HOME || path.join(os.homedir(), '.cache');
  const venvDir = path.join(cacheDir, 'mcp-web-engine', 'venv');
  const venvPython = process.platform === 'win32' 
    ? path.join(venvDir, 'Scripts', 'python.exe')
    : path.join(venvDir, 'bin', 'python');
  const venvPip = process.platform === 'win32'
    ? path.join(venvDir, 'Scripts', 'pip.exe')
    : path.join(venvDir, 'bin', 'pip');

  function findSystemPython() {
    for (const cmd of ['python3', 'python']) {
      try {
        execSync(`${cmd} --version`, { stdio: 'ignore' });
        return cmd;
      } catch (e) {}
    }
    throw new Error('Python 3 is required but was not found on PATH.');
  }

  // Ensure isolated venv exists and has requirements installed
  if (!fs.existsSync(venvPython)) {
    console.log('[mcp-web-engine] Creating isolated Python venv at:', venvDir);
    const sysPython = findSystemPython();
    fs.mkdirSync(path.dirname(venvDir), { recursive: true });
    execSync(`${sysPython} -m venv "${venvDir}"`, { stdio: 'inherit' });
    console.log('[mcp-web-engine] Installing dependencies into isolated venv...');
    execSync(`"${venvPip}" install -r "${reqTxt}"`, { stdio: 'inherit' });
  }

  const repoRoot = path.join(__dirname, '..');
  const env = { ...process.env, PYTHONPATH: path.join(repoRoot, 'src') };

  const child = spawn(venvPython, ['-m', 'mcp_web_engine.main', ...process.argv.slice(2)], {
    stdio: 'inherit',
    env: env
  });
  forwardChild(child);
}

if (!tryUv()) {
  runInIsolatedVenv();
}
