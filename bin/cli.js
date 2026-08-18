#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');

const mainPy = path.join(__dirname, '..', 'main.py');

const child = spawn('python3', [mainPy, ...process.argv.slice(2)], {
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
