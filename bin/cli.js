#!/usr/bin/env node
// Ship the Python src package in the npm tarball and let uv isolate it.
// No pip/bootstrap chatter can ever enter MCP stdout.
const { spawn } = require('node:child_process');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const child = spawn('uv', ['tool', 'run', '--from', root, 'mcp-web-engine', ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: process.env,
});
child.on('error', (error) => {
  console.error(`[mcp-web-engine] Cannot launch uv: ${error.message}. Install uv: https://docs.astral.sh/uv/getting-started/installation/`);
  process.exitCode = 1;
});
const signals = ['SIGINT', 'SIGTERM'];
for (const signal of signals) {
  process.on(signal, () => { if (!child.killed) child.kill(signal); });
}
child.on('exit', (code, signal) => {
  process.exitCode = code ?? (signal === 'SIGINT' ? 130 : 143);
});
