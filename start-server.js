const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const root = path.resolve(__dirname);
const preferPort = 8000;
const indexFile = 'hepta_ground_station_ui_compact_v36_wider_azel_graph.html';
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
    console.log('Python is not required. Use the UI connection button to select the XBee serial port.');

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
  process.exit(0);
});

process.on('SIGTERM', () => {
  process.exit(0);
});
