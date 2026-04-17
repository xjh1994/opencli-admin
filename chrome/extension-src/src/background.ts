/**
 * opencli Browser Bridge — Service Worker (background script).
 *
 * Connects to the opencli daemon via WebSocket, receives commands,
 * dispatches them to Chrome APIs (debugger/tabs/cookies), returns results.
 *
 * Synced with @jackwener/opencli v1.7.4:
 * - tabId replaced by page (targetId string) in protocol
 * - workspace-based automation window isolation
 * - ping-before-connect to suppress ERR_CONNECTION_REFUSED noise
 * - hello message on open
 * - new actions: close-window, cdp, sessions, set-file-input, insert-text,
 *   bind-current, network-capture-start, network-capture-read
 */

import type { Command, Result } from './protocol';
import { DAEMON_WS_URL, DAEMON_PING_URL, WS_RECONNECT_BASE_DELAY, WS_RECONNECT_MAX_DELAY } from './protocol';
import * as cdp from './cdp';
import * as identity from './identity';

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectAttempts = 0;

// ─── Console log forwarding ──────────────────────────────────────────

const _origLog = console.log.bind(console);
const _origWarn = console.warn.bind(console);
const _origError = console.error.bind(console);

function forwardLog(level: 'info' | 'warn' | 'error', args: unknown[]): void {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  try {
    const msg = args.map(a => typeof a === 'string' ? a : JSON.stringify(a)).join(' ');
    ws.send(JSON.stringify({ type: 'log', level, msg, ts: Date.now() }));
  } catch { /* don't recurse */ }
}

console.log = (...args: unknown[]) => { _origLog(...args); forwardLog('info', args); };
console.warn = (...args: unknown[]) => { _origWarn(...args); forwardLog('warn', args); };
console.error = (...args: unknown[]) => { _origError(...args); forwardLog('error', args); };

// ─── WebSocket connection ────────────────────────────────────────────

async function connect(): Promise<void> {
  if (ws?.readyState === WebSocket.OPEN || ws?.readyState === WebSocket.CONNECTING) return;

  try {
    const res = await fetch(DAEMON_PING_URL, { signal: AbortSignal.timeout(1000) });
    if (!res.ok) return;
  } catch {
    return; // daemon not running — skip to avoid console noise
  }

  try {
    ws = new WebSocket(DAEMON_WS_URL);
  } catch {
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    console.log('[opencli] Connected to daemon');
    reconnectAttempts = 0;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    ws?.send(JSON.stringify({
      type: 'hello',
      version: chrome.runtime.getManifest().version,
    }));
  };

  ws.onmessage = async (event) => {
    try {
      const command = JSON.parse(event.data as string) as Command;
      const result = await handleCommand(command);
      ws?.send(JSON.stringify(result));
    } catch (err) {
      console.error('[opencli] Message handling error:', err);
    }
  };

  ws.onclose = () => {
    console.log('[opencli] Disconnected from daemon');
    ws = null;
    scheduleReconnect();
  };

  ws.onerror = () => {
    ws?.close();
  };
}

const MAX_EAGER_ATTEMPTS = 6;

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  reconnectAttempts++;
  if (reconnectAttempts > MAX_EAGER_ATTEMPTS) return;
  const delay = Math.min(WS_RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttempts - 1), WS_RECONNECT_MAX_DELAY);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    void connect();
  }, delay);
}

// ─── Automation window isolation ─────────────────────────────────────

type AutomationSession = {
  windowId: number;
  idleTimer: ReturnType<typeof setTimeout> | null;
  idleDeadlineAt: number;
  owned: boolean;
  preferredTabId: number | null;
};

const automationSessions = new Map<string, AutomationSession>();
const IDLE_TIMEOUT_DEFAULT = 30_000;
const IDLE_TIMEOUT_INTERACTIVE = 600_000;
const workspaceTimeoutOverrides = new Map<string, number>();

function getIdleTimeout(workspace: string): number {
  const override = workspaceTimeoutOverrides.get(workspace);
  if (override !== undefined) return override;
  if (workspace.startsWith('browser:') || workspace.startsWith('operate:')) {
    return IDLE_TIMEOUT_INTERACTIVE;
  }
  return IDLE_TIMEOUT_DEFAULT;
}

let windowFocused = false;

function getWorkspaceKey(workspace?: string): string {
  return workspace?.trim() || 'default';
}

function resetWindowIdleTimer(workspace: string): void {
  const session = automationSessions.get(workspace);
  if (!session) return;
  if (session.idleTimer) clearTimeout(session.idleTimer);
  const timeout = getIdleTimeout(workspace);
  session.idleDeadlineAt = Date.now() + timeout;
  session.idleTimer = setTimeout(async () => {
    const current = automationSessions.get(workspace);
    if (!current) return;
    if (!current.owned) {
      workspaceTimeoutOverrides.delete(workspace);
      automationSessions.delete(workspace);
      return;
    }
    try { await chrome.windows.remove(current.windowId); } catch { /* already gone */ }
    workspaceTimeoutOverrides.delete(workspace);
    automationSessions.delete(workspace);
  }, timeout);
}

const BLANK_PAGE = 'about:blank';

function isSafeNavigationUrl(url: string): boolean {
  return url.startsWith('http://') || url.startsWith('https://');
}

function isDebuggableUrl(url?: string): boolean {
  if (!url) return true;
  return url.startsWith('http://') || url.startsWith('https://') || url === 'about:blank' || url.startsWith('data:');
}

async function getAutomationWindow(workspace: string, initialUrl?: string): Promise<number> {
  const existing = automationSessions.get(workspace);
  if (existing) {
    try {
      await chrome.windows.get(existing.windowId);
      return existing.windowId;
    } catch {
      automationSessions.delete(workspace);
    }
  }

  const startUrl = (initialUrl && isSafeNavigationUrl(initialUrl)) ? initialUrl : BLANK_PAGE;
  const win = await chrome.windows.create({
    url: startUrl,
    focused: windowFocused,
    width: 1280,
    height: 900,
    type: 'normal',
  });
  const session: AutomationSession = {
    windowId: win.id!,
    idleTimer: null,
    idleDeadlineAt: Date.now() + getIdleTimeout(workspace),
    owned: true,
    preferredTabId: null,
  };
  automationSessions.set(workspace, session);
  resetWindowIdleTimer(workspace);
  const tabs = await chrome.tabs.query({ windowId: win.id! });
  if (tabs[0]?.id) {
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(resolve, 500);
      const listener = (tabId: number, info: chrome.tabs.TabChangeInfo) => {
        if (tabId === tabs[0].id && info.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(listener);
          clearTimeout(timeout);
          resolve();
        }
      };
      if (tabs[0].status === 'complete') { clearTimeout(timeout); resolve(); }
      else chrome.tabs.onUpdated.addListener(listener);
    });
  }
  return session.windowId;
}

chrome.windows.onRemoved.addListener(async (windowId) => {
  for (const [workspace, session] of automationSessions.entries()) {
    if (session.windowId === windowId) {
      if (session.idleTimer) clearTimeout(session.idleTimer);
      automationSessions.delete(workspace);
      workspaceTimeoutOverrides.delete(workspace);
    }
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  identity.evictTab(tabId);
});

// ─── Lifecycle events ────────────────────────────────────────────────

let initialized = false;

function initialize(): void {
  if (initialized) return;
  initialized = true;
  chrome.alarms.create('keepalive', { periodInMinutes: 0.4 });
  cdp.registerListeners();
  void connect();
  console.log('[opencli] Browser Bridge extension initialized');
}

chrome.runtime.onInstalled.addListener(() => { initialize(); });
chrome.runtime.onStartup.addListener(() => { initialize(); });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'keepalive') void connect();
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === 'getStatus') {
    sendResponse({ connected: ws?.readyState === WebSocket.OPEN, reconnecting: reconnectTimer !== null });
  }
  return false;
});

// ─── Command dispatcher ─────────────────────────────────────────────

async function handleCommand(cmd: Command): Promise<Result> {
  const workspace = getWorkspaceKey(cmd.workspace);
  windowFocused = cmd.windowFocused === true;
  if (cmd.idleTimeout != null && cmd.idleTimeout > 0) {
    workspaceTimeoutOverrides.set(workspace, cmd.idleTimeout * 1000);
  }
  resetWindowIdleTimer(workspace);
  try {
    switch (cmd.action) {
      case 'exec':              return await handleExec(cmd, workspace);
      case 'navigate':          return await handleNavigate(cmd, workspace);
      case 'tabs':              return await handleTabs(cmd, workspace);
      case 'cookies':           return await handleCookies(cmd);
      case 'screenshot':        return await handleScreenshot(cmd, workspace);
      case 'close-window':      return await handleCloseWindow(cmd, workspace);
      case 'cdp':               return await handleCdp(cmd, workspace);
      case 'sessions':          return await handleSessions(cmd);
      case 'set-file-input':    return await handleSetFileInput(cmd, workspace);
      case 'insert-text':       return await handleInsertText(cmd, workspace);
      case 'bind-current':      return await handleBindCurrent(cmd, workspace);
      case 'network-capture-start': return await handleNetworkCaptureStart(cmd, workspace);
      case 'network-capture-read':  return await handleNetworkCaptureRead(cmd, workspace);
      default:
        return { id: cmd.id, ok: false, error: `Unknown action: ${cmd.action}` };
    }
  } catch (err) {
    return { id: cmd.id, ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

// ─── Tab resolution ──────────────────────────────────────────────────

async function resolveCommandTabId(cmd: Command): Promise<number | undefined> {
  if (cmd.page) return identity.resolveTabId(cmd.page);
  return undefined;
}

type ResolvedTab = { tabId: number; tab: chrome.tabs.Tab | null };

async function resolveTab(tabId: number | undefined, workspace: string, initialUrl?: string): Promise<ResolvedTab> {
  if (tabId !== undefined) {
    try {
      const tab = await chrome.tabs.get(tabId);
      const session = automationSessions.get(workspace);
      const matchesSession = session
        ? (session.preferredTabId !== null ? session.preferredTabId === tabId : tab.windowId === session.windowId)
        : false;
      if (isDebuggableUrl(tab.url) && matchesSession) return { tabId, tab };
    } catch {
      console.warn(`[opencli] Tab ${tabId} no longer exists, re-resolving`);
    }
  }

  const existingSession = automationSessions.get(workspace);
  if (existingSession?.preferredTabId !== null && existingSession?.preferredTabId !== undefined) {
    try {
      const preferredTab = await chrome.tabs.get(existingSession.preferredTabId);
      if (isDebuggableUrl(preferredTab.url)) return { tabId: preferredTab.id!, tab: preferredTab };
    } catch {
      automationSessions.delete(workspace);
    }
  }

  const windowId = await getAutomationWindow(workspace, initialUrl);
  const tabs = await chrome.tabs.query({ windowId });
  const debuggableTab = tabs.find(t => t.id && isDebuggableUrl(t.url));
  if (debuggableTab?.id) return { tabId: debuggableTab.id, tab: debuggableTab };

  const reuseTab = tabs.find(t => t.id);
  if (reuseTab?.id) {
    await chrome.tabs.update(reuseTab.id, { url: BLANK_PAGE });
    await new Promise(resolve => setTimeout(resolve, 300));
    try {
      const updated = await chrome.tabs.get(reuseTab.id);
      if (isDebuggableUrl(updated.url)) return { tabId: reuseTab.id, tab: updated };
    } catch { /* tab gone */ }
  }

  const newTab = await chrome.tabs.create({ windowId, url: BLANK_PAGE, active: true });
  if (!newTab.id) throw new Error('Failed to create tab in automation window');
  return { tabId: newTab.id, tab: newTab };
}

async function pageScopedResult(id: string, tabId: number, data?: unknown): Promise<Result> {
  const page = await identity.resolveTargetId(tabId);
  return { id, ok: true, data, page };
}

async function resolveTabId(tabId: number | undefined, workspace: string, initialUrl?: string): Promise<number> {
  const resolved = await resolveTab(tabId, workspace, initialUrl);
  return resolved.tabId;
}

async function listAutomationWebTabs(workspace: string): Promise<chrome.tabs.Tab[]> {
  const session = automationSessions.get(workspace);
  if (!session) return [];
  if (session.preferredTabId !== null) {
    try { return [await chrome.tabs.get(session.preferredTabId)]; }
    catch { automationSessions.delete(workspace); return []; }
  }
  try { return (await chrome.tabs.query({ windowId: session.windowId })).filter(t => isDebuggableUrl(t.url)); }
  catch { automationSessions.delete(workspace); return []; }
}

function setWorkspaceSession(workspace: string, session: Omit<AutomationSession, 'idleTimer' | 'idleDeadlineAt'>): void {
  const existing = automationSessions.get(workspace);
  if (existing?.idleTimer) clearTimeout(existing.idleTimer);
  automationSessions.set(workspace, {
    ...session,
    idleTimer: null,
    idleDeadlineAt: Date.now() + getIdleTimeout(workspace),
  });
}

// ─── Action handlers ─────────────────────────────────────────────────

async function handleExec(cmd: Command, workspace: string): Promise<Result> {
  if (!cmd.code) return { id: cmd.id, ok: false, error: 'Missing code' };
  const cmdTabId = await resolveCommandTabId(cmd);
  const tabId = await resolveTabId(cmdTabId, workspace);
  try {
    const aggressive = workspace.startsWith('browser:') || workspace.startsWith('operate:');
    const data = await cdp.evaluateAsync(tabId, cmd.code, aggressive);
    return pageScopedResult(cmd.id, tabId, data);
  } catch (err) {
    return { id: cmd.id, ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

function normalizeUrlForComparison(url?: string): string {
  if (!url) return '';
  try {
    const parsed = new URL(url);
    if ((parsed.protocol === 'https:' && parsed.port === '443') || (parsed.protocol === 'http:' && parsed.port === '80')) {
      parsed.port = '';
    }
    const pathname = parsed.pathname === '/' ? '' : parsed.pathname;
    return `${parsed.protocol}//${parsed.host}${pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return url;
  }
}

function isTargetUrl(currentUrl: string | undefined, targetUrl: string): boolean {
  return normalizeUrlForComparison(currentUrl) === normalizeUrlForComparison(targetUrl);
}

async function handleNavigate(cmd: Command, workspace: string): Promise<Result> {
  if (!cmd.url) return { id: cmd.id, ok: false, error: 'Missing url' };
  if (!isSafeNavigationUrl(cmd.url)) {
    return { id: cmd.id, ok: false, error: 'Blocked URL scheme — only http:// and https:// are allowed' };
  }
  const cmdTabId = await resolveCommandTabId(cmd);
  const resolved = await resolveTab(cmdTabId, workspace, cmd.url);
  const tabId = resolved.tabId;

  const beforeTab = resolved.tab ?? await chrome.tabs.get(tabId);
  const beforeNormalized = normalizeUrlForComparison(beforeTab.url);
  const targetUrl = cmd.url;

  if (beforeTab.status === 'complete' && isTargetUrl(beforeTab.url, targetUrl)) {
    return pageScopedResult(cmd.id, tabId, { title: beforeTab.title, url: beforeTab.url, timedOut: false });
  }

  if (!cdp.hasActiveNetworkCapture(tabId)) {
    await cdp.detach(tabId);
  }

  await chrome.tabs.update(tabId, { url: targetUrl });

  let timedOut = false;
  await new Promise<void>((resolve) => {
    let settled = false;
    let checkTimer: ReturnType<typeof setTimeout> | null = null;
    let timeoutTimer: ReturnType<typeof setTimeout> | null = null;

    const finish = () => {
      if (settled) return;
      settled = true;
      chrome.tabs.onUpdated.removeListener(listener);
      if (checkTimer) clearTimeout(checkTimer);
      if (timeoutTimer) clearTimeout(timeoutTimer);
      resolve();
    };

    const isNavigationDone = (url: string | undefined): boolean =>
      isTargetUrl(url, targetUrl) || normalizeUrlForComparison(url) !== beforeNormalized;

    const listener = (id: number, info: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => {
      if (id !== tabId) return;
      if (info.status === 'complete' && isNavigationDone(tab.url ?? info.url)) finish();
    };
    chrome.tabs.onUpdated.addListener(listener);

    checkTimer = setTimeout(async () => {
      try {
        const currentTab = await chrome.tabs.get(tabId);
        if (currentTab.status === 'complete' && isNavigationDone(currentTab.url)) finish();
      } catch { /* tab gone */ }
    }, 100);

    timeoutTimer = setTimeout(() => {
      timedOut = true;
      console.warn(`[opencli] Navigate to ${targetUrl} timed out after 15s`);
      finish();
    }, 15000);
  });

  const tab = await chrome.tabs.get(tabId);
  return pageScopedResult(cmd.id, tabId, { title: tab.title, url: tab.url, timedOut });
}

async function handleTabs(cmd: Command, workspace: string): Promise<Result> {
  switch (cmd.op) {
    case 'list': {
      const tabs = await listAutomationWebTabs(workspace);
      const data = await Promise.all(tabs.map(async (t, i) => {
        let page: string | undefined;
        try { page = t.id ? await identity.resolveTargetId(t.id) : undefined; } catch { /* skip */ }
        return { index: i, page, url: t.url, title: t.title, active: t.active };
      }));
      return { id: cmd.id, ok: true, data };
    }
    case 'new': {
      if (cmd.url && !isSafeNavigationUrl(cmd.url)) {
        return { id: cmd.id, ok: false, error: 'Blocked URL scheme — only http:// and https:// are allowed' };
      }
      const windowId = await getAutomationWindow(workspace);
      const tab = await chrome.tabs.create({ windowId, url: cmd.url ?? BLANK_PAGE, active: true });
      if (!tab.id) return { id: cmd.id, ok: false, error: 'Failed to create tab' };
      return pageScopedResult(cmd.id, tab.id, { url: tab.url });
    }
    case 'close': {
      if (cmd.index !== undefined) {
        const tabs = await listAutomationWebTabs(workspace);
        const target = tabs[cmd.index];
        if (!target?.id) return { id: cmd.id, ok: false, error: `Tab index ${cmd.index} not found` };
        const closedPage = await identity.resolveTargetId(target.id).catch(() => undefined);
        await chrome.tabs.remove(target.id);
        await cdp.detach(target.id);
        return { id: cmd.id, ok: true, data: { closed: closedPage } };
      }
      const cmdTabId = await resolveCommandTabId(cmd);
      const tabId = await resolveTabId(cmdTabId, workspace);
      const closedPage = await identity.resolveTargetId(tabId).catch(() => undefined);
      await chrome.tabs.remove(tabId);
      await cdp.detach(tabId);
      return { id: cmd.id, ok: true, data: { closed: closedPage } };
    }
    case 'select': {
      if (cmd.index === undefined && cmd.page === undefined)
        return { id: cmd.id, ok: false, error: 'Missing index or page' };
      const cmdTabId = await resolveCommandTabId(cmd);
      if (cmdTabId !== undefined) {
        const session = automationSessions.get(workspace);
        try {
          const tab = await chrome.tabs.get(cmdTabId);
          if (!session || tab.windowId !== session.windowId) {
            return { id: cmd.id, ok: false, error: 'Page is not in the automation window' };
          }
          await chrome.tabs.update(cmdTabId, { active: true });
          return pageScopedResult(cmd.id, cmdTabId, { selected: true });
        } catch {
          return { id: cmd.id, ok: false, error: 'Page no longer exists' };
        }
      }
      const tabs = await listAutomationWebTabs(workspace);
      const target = tabs[cmd.index!];
      if (!target?.id) return { id: cmd.id, ok: false, error: `Tab index ${cmd.index} not found` };
      await chrome.tabs.update(target.id, { active: true });
      return pageScopedResult(cmd.id, target.id, { selected: true });
    }
    default:
      return { id: cmd.id, ok: false, error: `Unknown tabs op: ${cmd.op}` };
  }
}

async function handleCookies(cmd: Command): Promise<Result> {
  if (!cmd.domain && !cmd.url) {
    return { id: cmd.id, ok: false, error: 'Cookie scope required: provide domain or url' };
  }
  const details: chrome.cookies.GetAllDetails = {};
  if (cmd.domain) details.domain = cmd.domain;
  if (cmd.url) details.url = cmd.url;
  const cookies = await chrome.cookies.getAll(details);
  const data = cookies.map((c) => ({
    name: c.name, value: c.value, domain: c.domain, path: c.path,
    secure: c.secure, httpOnly: c.httpOnly, expirationDate: c.expirationDate,
  }));
  return { id: cmd.id, ok: true, data };
}

async function handleScreenshot(cmd: Command, workspace: string): Promise<Result> {
  const cmdTabId = await resolveCommandTabId(cmd);
  const tabId = await resolveTabId(cmdTabId, workspace);
  try {
    const data = await cdp.screenshot(tabId, { format: cmd.format, quality: cmd.quality, fullPage: cmd.fullPage });
    return pageScopedResult(cmd.id, tabId, data);
  } catch (err) {
    return { id: cmd.id, ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

const CDP_ALLOWLIST = new Set([
  'Accessibility.getFullAXTree', 'DOM.getDocument', 'DOM.getBoxModel', 'DOM.getContentQuads',
  'DOM.querySelectorAll', 'DOM.scrollIntoViewIfNeeded', 'DOMSnapshot.captureSnapshot',
  'Input.dispatchMouseEvent', 'Input.dispatchKeyEvent', 'Input.insertText',
  'Page.getLayoutMetrics', 'Page.captureScreenshot', 'Runtime.enable',
  'Emulation.setDeviceMetricsOverride', 'Emulation.clearDeviceMetricsOverride',
]);

async function handleCdp(cmd: Command, workspace: string): Promise<Result> {
  if (!cmd.cdpMethod) return { id: cmd.id, ok: false, error: 'Missing cdpMethod' };
  if (!CDP_ALLOWLIST.has(cmd.cdpMethod)) {
    return { id: cmd.id, ok: false, error: `CDP method not permitted: ${cmd.cdpMethod}` };
  }
  const cmdTabId = await resolveCommandTabId(cmd);
  const tabId = await resolveTabId(cmdTabId, workspace);
  try {
    const aggressive = workspace.startsWith('browser:') || workspace.startsWith('operate:');
    await cdp.ensureAttached(tabId, aggressive);
    const data = await chrome.debugger.sendCommand({ tabId }, cmd.cdpMethod, cmd.cdpParams ?? {});
    return pageScopedResult(cmd.id, tabId, data);
  } catch (err) {
    return { id: cmd.id, ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

async function handleCloseWindow(cmd: Command, workspace: string): Promise<Result> {
  const session = automationSessions.get(workspace);
  if (session) {
    if (session.owned) {
      try { await chrome.windows.remove(session.windowId); } catch { /* already closed */ }
    }
    if (session.idleTimer) clearTimeout(session.idleTimer);
    workspaceTimeoutOverrides.delete(workspace);
    automationSessions.delete(workspace);
  }
  return { id: cmd.id, ok: true, data: { closed: true } };
}

async function handleSetFileInput(cmd: Command, workspace: string): Promise<Result> {
  if (!cmd.files || !Array.isArray(cmd.files) || cmd.files.length === 0) {
    return { id: cmd.id, ok: false, error: 'Missing or empty files array' };
  }
  const cmdTabId = await resolveCommandTabId(cmd);
  const tabId = await resolveTabId(cmdTabId, workspace);
  try {
    await cdp.setFileInputFiles(tabId, cmd.files, cmd.selector);
    return pageScopedResult(cmd.id, tabId, { count: cmd.files.length });
  } catch (err) {
    return { id: cmd.id, ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

async function handleInsertText(cmd: Command, workspace: string): Promise<Result> {
  if (typeof cmd.text !== 'string') return { id: cmd.id, ok: false, error: 'Missing text payload' };
  const cmdTabId = await resolveCommandTabId(cmd);
  const tabId = await resolveTabId(cmdTabId, workspace);
  try {
    await cdp.insertText(tabId, cmd.text);
    return pageScopedResult(cmd.id, tabId, { inserted: true });
  } catch (err) {
    return { id: cmd.id, ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

async function handleNetworkCaptureStart(cmd: Command, workspace: string): Promise<Result> {
  const cmdTabId = await resolveCommandTabId(cmd);
  const tabId = await resolveTabId(cmdTabId, workspace);
  try {
    await cdp.startNetworkCapture(tabId, cmd.pattern);
    return pageScopedResult(cmd.id, tabId, { started: true });
  } catch (err) {
    return { id: cmd.id, ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

async function handleNetworkCaptureRead(cmd: Command, workspace: string): Promise<Result> {
  const cmdTabId = await resolveCommandTabId(cmd);
  const tabId = await resolveTabId(cmdTabId, workspace);
  try {
    const data = await cdp.readNetworkCapture(tabId);
    return pageScopedResult(cmd.id, tabId, data);
  } catch (err) {
    return { id: cmd.id, ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

async function handleSessions(cmd: Command): Promise<Result> {
  const now = Date.now();
  const data = await Promise.all([...automationSessions.entries()].map(async ([workspace, session]) => ({
    workspace,
    windowId: session.windowId,
    tabCount: (await chrome.tabs.query({ windowId: session.windowId })).filter(t => isDebuggableUrl(t.url)).length,
    idleMsRemaining: Math.max(0, session.idleDeadlineAt - now),
  })));
  return { id: cmd.id, ok: true, data };
}

function matchesBindCriteria(tab: chrome.tabs.Tab, cmd: Command): boolean {
  if (!tab.id || !isDebuggableUrl(tab.url)) return false;
  if (cmd.matchDomain) {
    try {
      const parsed = new URL(tab.url!);
      const domain = cmd.matchDomain;
      if (parsed.hostname !== domain && !parsed.hostname.endsWith(`.${domain}`)) return false;
    } catch { return false; }
  }
  if (cmd.matchPathPrefix) {
    try {
      const parsed = new URL(tab.url!);
      if (!parsed.pathname.startsWith(cmd.matchPathPrefix)) return false;
    } catch { return false; }
  }
  return true;
}

async function handleBindCurrent(cmd: Command, workspace: string): Promise<Result> {
  const activeTabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  const fallbackTabs = await chrome.tabs.query({ lastFocusedWindow: true });
  const allTabs = await chrome.tabs.query({});
  const boundTab = activeTabs.find(t => matchesBindCriteria(t, cmd))
    ?? fallbackTabs.find(t => matchesBindCriteria(t, cmd))
    ?? allTabs.find(t => matchesBindCriteria(t, cmd));
  if (!boundTab?.id) {
    return {
      id: cmd.id, ok: false,
      error: cmd.matchDomain || cmd.matchPathPrefix
        ? `No visible tab matching ${cmd.matchDomain ?? 'domain'}${cmd.matchPathPrefix ? ` ${cmd.matchPathPrefix}` : ''}`
        : 'No active debuggable tab found',
    };
  }
  setWorkspaceSession(workspace, {
    windowId: boundTab.windowId,
    owned: false,
    preferredTabId: boundTab.id,
  });
  resetWindowIdleTimer(workspace);
  return pageScopedResult(cmd.id, boundTab.id, { url: boundTab.url, title: boundTab.title, workspace });
}
