#!/usr/bin/env node
/**
 * Post-install patch for @jackwener/opencli (CommonJS, works on Node 18+).
 *
 * Adds two env-var hooks that the published package lacks:
 *
 *   OPENCLI_DAEMON_LISTEN  (daemon.js)
 *     Default: 127.0.0.1 — set to 0.0.0.0 so the API container can reach
 *     the daemon running inside the chrome-N container.
 *
 *   OPENCLI_DAEMON_HOST  (daemon-client.js + mcp.js)
 *     Default: 127.0.0.1 — set to chrome-1 (or chrome-N) so the CLI in the
 *     API container contacts the remote daemon instead of spawning one locally.
 */

'use strict';

const fs = require('fs');
const path = require('path');

function resolvePackageDir() {
  try {
    return path.dirname(require.resolve('@jackwener/opencli/package.json'));
  } catch (_) {
    // Fallback: ask npm where its global root is (works with NodeSource installs)
    const { execSync } = require('child_process');
    const npmRoot = execSync('npm root -g').toString().trim();
    return path.join(npmRoot, '@jackwener', 'opencli');
  }
}

function patch(filePath, search, replace, label) {
  let content = fs.readFileSync(filePath, 'utf8');
  if (content.includes(replace.slice(0, 40))) {
    console.log('  [skip] ' + label + ' already patched');
    return;
  }
  if (!content.includes(search)) {
    console.error('  [warn] ' + label + ': search string not found in ' + filePath);
    return;
  }
  content = content.replace(search, replace);
  fs.writeFileSync(filePath, content);
  console.log('  [ok]   ' + label);
}

const pkgDir = resolvePackageDir();
console.log('Patching opencli at ' + pkgDir + ' ...');

// ── 1. daemon.js: honour OPENCLI_DAEMON_LISTEN ───────────────────────────────
patch(
  path.join(pkgDir, 'dist', 'daemon.js'),
  "httpServer.listen(PORT, '127.0.0.1', () => {",
  "const DAEMON_LISTEN = process.env.OPENCLI_DAEMON_LISTEN ?? '127.0.0.1';\nhttpServer.listen(PORT, DAEMON_LISTEN, () => {",
  'daemon.js: OPENCLI_DAEMON_LISTEN'
);

// ── 2. daemon-client.js: honour OPENCLI_DAEMON_HOST ─────────────────────────
patch(
  path.join(pkgDir, 'dist', 'browser', 'daemon-client.js'),
  'const DAEMON_URL = `http://127.0.0.1:${DAEMON_PORT}`;',
  "const DAEMON_HOST = process.env.OPENCLI_DAEMON_HOST ?? '127.0.0.1';\nconst DAEMON_URL = `http://${DAEMON_HOST}:${DAEMON_PORT}`;",
  'daemon-client.js: OPENCLI_DAEMON_HOST'
);

// ── 3. mcp.js: skip local auto-spawn when daemon is remote ───────────────────
patch(
  path.join(pkgDir, 'dist', 'browser', 'mcp.js'),
  'async _ensureDaemon() {',
  "async _ensureDaemon() {\n        const _dHost = process.env.OPENCLI_DAEMON_HOST;\n        if (_dHost && _dHost !== '127.0.0.1' && _dHost !== 'localhost') {\n            if (!await isDaemonRunning()) throw new Error('Remote Browser Bridge daemon at ' + _dHost + ' is not reachable. Ensure BROWSER_BRIDGE_ENABLED=true on the chrome container.');\n            return;\n        }",
  'mcp.js: skip auto-spawn for remote daemon'
);

console.log('Done.');
