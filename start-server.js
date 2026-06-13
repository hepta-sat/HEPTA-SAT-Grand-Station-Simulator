const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec, spawn } = require('child_process');

const root = path.resolve(__dirname);
const preferPort = 8000;
const indexFile = 'hepta_ground_station_ui_compact_v36_wider_azel_graph.html';
const rssiAtdbInterval = process.env.RSSI_ATDB_INTERVAL || '5';
let receiverProcess = null;
let receiverLastExit = null;

function jsonResponse(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  });
  res.end(body);
}

function pythonCandidates() {
  const candidates = [
    process.env.HEPTA_PYTHON,
    path.join(root, '.venv', 'Scripts', 'python.exe'),
    path.join(root, '.venv-1', 'Scripts', 'python.exe'),
    'python'
  ].filter(Boolean);
  return candidates.filter((candidate, index) => candidates.indexOf(candidate) === index);
}

function resolvePythonCommand() {
  const candidates = pythonCandidates();
  for (const candidate of candidates) {
    if (candidate === 'python' || fs.existsSync(candidate)) return candidate;
  }
  return 'python';
}

function startReceiver() {
  if (receiverProcess && receiverProcess.exitCode === null) {
    return { started: false, running: true, pid: receiverProcess.pid };
  }

  const python = resolvePythonCommand();
  const args = ['receive_data.py', '--rssi-atdb-interval', rssiAtdbInterval];
  receiverLastExit = null;
  receiverProcess = spawn(python, args, {
    cwd: root,
    env: process.env,
    windowsHide: false,
    stdio: ['ignore', 'pipe', 'pipe']
  });

  receiverProcess.stdout.on('data', data => process.stdout.write(`[receive_data] ${data}`));
  receiverProcess.stderr.on('data', data => process.stderr.write(`[receive_data] ${data}`));
  receiverProcess.on('error', error => {
    receiverLastExit = { code: null, signal: null, error: error.message };
    receiverProcess = null;
    console.error(`[receive_data] failed to start: ${error.message}`);
  });
  receiverProcess.on('exit', (code, signal) => {
    receiverLastExit = { code, signal };
    receiverProcess = null;
    console.log(`[receive_data] exited code=${code} signal=${signal || ''}`);
  });

  console.log(`[receive_data] started pid=${receiverProcess.pid} (${python} ${args.join(' ')})`);
  return { started: true, running: true, pid: receiverProcess.pid };
}

function contentTypeFor(file) {
  const ext = path.extname(file).toLowerCase();
  switch (ext) {
    case '.html': return 'text/html; charset=utf-8';
    case '.js': return 'application/javascript; charset=utf-8';
    case '.css': return 'text/css; charset=utf-8';
    case '.json': return 'application/json; charset=utf-8';
    case '.png': return 'image/png';
    case '.jpg': case '.jpeg': return 'image/jpeg';
    case '.svg': return 'image/svg+xml';
    case '.wasm': return 'application/wasm';
    default: return 'application/octet-stream';
  }
}

function createServer() {
  return http.createServer((req, res) => {
    try {
      let reqPath = decodeURI(new URL(req.url, 'http://localhost').pathname);
      if (req.method === 'OPTIONS') {
        jsonResponse(res, 200, { ok: true });
        return;
      }
      if (reqPath === '/start-receiver' && req.method === 'POST') {
        jsonResponse(res, 200, { ok: true, ...startReceiver(), rssi_atdb_interval: rssiAtdbInterval });
        return;
      }
      if (reqPath === '/receiver-status' && req.method === 'GET') {
        const running = Boolean(receiverProcess && receiverProcess.exitCode === null);
        jsonResponse(res, 200, {
          ok: true,
          running,
          pid: running ? receiverProcess.pid : null,
          last_exit: receiverLastExit
        });
        return;
      }
      if (reqPath === '/') reqPath = '/' + indexFile;
      // Prevent path traversal
      const fsPath = path.join(root, path.normalize(reqPath.replace(/^\//, '')));
      if (!fsPath.startsWith(root)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
      }

      fs.stat(fsPath, (err, st) => {
        if (err) {
          res.writeHead(404);
          res.end('Not found');
          return;
        }
        if (st.isDirectory()) {
          res.writeHead(302, { Location: '/' + indexFile });
          res.end();
          return;
        }

        const stream = fs.createReadStream(fsPath);
        res.writeHead(200, { 'Content-Type': contentTypeFor(fsPath) });
        stream.pipe(res);
      });
    } catch (e) {
      res.writeHead(500);
      res.end('Server error');
    }
  });
}

function tryListen(port) {
  return new Promise((resolve, reject) => {
    const server = createServer();
    function onError(err) {
      server.close();
      reject(err);
    }
    server.on('error', onError);
    server.listen(port, () => {
      server.removeListener('error', onError);
      const assigned = server.address() && server.address().port ? server.address().port : port;
      resolve({ server, port: assigned });
    });
  });
}

(async () => {
  try {
    let info;
    try {
      info = await tryListen(preferPort);
    } catch (e) {
      // fallback to random free port
      info = await tryListen(0);
    }

    const url = `http://localhost:${info.port}/${indexFile}`;
    console.log(`Serving ${root} on ${url}`);
    console.log('Use the UI connection button to start receive_data.py and connect the Python backend.');

    if (process.env.HEPTA_NO_OPEN === '1') {
      console.log('Browser auto-open skipped because HEPTA_NO_OPEN=1.');
      return;
    }

    // Open default browser on Windows, macOS, Linux
    const startCmd = process.platform === 'win32' ? `start "" "${url}"` : process.platform === 'darwin' ? `open "${url}"` : `xdg-open "${url}"`;
    exec(startCmd, (err) => {
      if (err) console.log('Failed to open browser:', err.message || err);
    });
  } catch (err) {
    console.error('Failed to start server:', err && err.message ? err.message : err);
    process.exit(1);
  }
})();

process.on('SIGINT', () => {
  if (receiverProcess) receiverProcess.kill();
  process.exit(0);
});

process.on('SIGTERM', () => {
  if (receiverProcess) receiverProcess.kill();
  process.exit(0);
});
