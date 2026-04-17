/**
 * CDP execution via chrome.debugger API.
 *
 * Synced with @jackwener/opencli v1.7.4.
 * Added: network capture, insertText, setFileInputFiles, ensureAttached export.
 */

const attached = new Set<number>();

type NetworkCaptureEntry = {
  kind: 'cdp';
  url: string;
  method: string;
  requestHeaders?: Record<string, string>;
  requestBodyKind?: string;
  requestBodyPreview?: string;
  responseStatus?: number;
  responseContentType?: string;
  responseHeaders?: Record<string, string>;
  responsePreview?: string;
  timestamp: number;
};

type NetworkCaptureState = {
  patterns: string[];
  entries: NetworkCaptureEntry[];
  requestToIndex: Map<string, number>;
};

const networkCaptures = new Map<number, NetworkCaptureState>();

function isDebuggableUrl(url?: string): boolean {
  if (!url) return true;
  return url.startsWith('http://') || url.startsWith('https://') || url === 'about:blank' || url.startsWith('data:');
}

export async function ensureAttached(tabId: number, aggressiveRetry: boolean = false): Promise<void> {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!isDebuggableUrl(tab.url)) {
      attached.delete(tabId);
      throw new Error(`Cannot debug tab ${tabId}: URL is ${tab.url ?? 'unknown'}`);
    }
  } catch (e) {
    if (e instanceof Error && e.message.startsWith('Cannot debug tab')) throw e;
    attached.delete(tabId);
    throw new Error(`Tab ${tabId} no longer exists`);
  }

  if (attached.has(tabId)) {
    try {
      await chrome.debugger.sendCommand({ tabId }, 'Runtime.evaluate', {
        expression: '1', returnByValue: true,
      });
      return;
    } catch {
      attached.delete(tabId);
    }
  }

  const MAX_ATTACH_RETRIES = aggressiveRetry ? 5 : 2;
  const RETRY_DELAY_MS = aggressiveRetry ? 1500 : 500;
  let lastError = '';

  for (let attempt = 1; attempt <= MAX_ATTACH_RETRIES; attempt++) {
    try {
      try { await chrome.debugger.detach({ tabId }); } catch { /* ignore */ }
      await chrome.debugger.attach({ tabId }, '1.3');
      lastError = '';
      break;
    } catch (e: unknown) {
      lastError = e instanceof Error ? e.message : String(e);
      if (attempt < MAX_ATTACH_RETRIES) {
        console.warn(`[opencli] attach attempt ${attempt}/${MAX_ATTACH_RETRIES} failed: ${lastError}`);
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
      }
    }
  }

  if (lastError) {
    throw new Error(`attach failed: ${lastError}`);
  }
  attached.add(tabId);

  try {
    await chrome.debugger.sendCommand({ tabId }, 'Runtime.enable');
  } catch {
    // Some pages may not need explicit enable
  }
}

export async function evaluate(tabId: number, expression: string, aggressiveRetry: boolean = false): Promise<unknown> {
  const MAX_EVAL_RETRIES = aggressiveRetry ? 3 : 2;
  for (let attempt = 1; attempt <= MAX_EVAL_RETRIES; attempt++) {
    try {
      await ensureAttached(tabId, aggressiveRetry);

      const result = await chrome.debugger.sendCommand({ tabId }, 'Runtime.evaluate', {
        expression,
        returnByValue: true,
        awaitPromise: true,
      }) as {
        result?: { type: string; value?: unknown; description?: string; subtype?: string };
        exceptionDetails?: { exception?: { description?: string }; text?: string };
      };

      if (result.exceptionDetails) {
        const errMsg = result.exceptionDetails.exception?.description
          || result.exceptionDetails.text
          || 'Eval error';
        throw new Error(errMsg);
      }

      return result.result?.value;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      const isAttachError = msg.includes('Inspected target navigated') || msg.includes('Target closed')
        || msg.includes('attach failed') || msg.includes('Debugger is not attached');
      if (isAttachError && attempt < MAX_EVAL_RETRIES) {
        attached.delete(tabId);
        await new Promise(resolve => setTimeout(resolve, 200));
        continue;
      }
      throw e;
    }
  }
  throw new Error('evaluate: max retries exhausted');
}

export const evaluateAsync = evaluate;

export async function screenshot(
  tabId: number,
  options: { format?: 'png' | 'jpeg'; quality?: number; fullPage?: boolean } = {},
): Promise<string> {
  await ensureAttached(tabId);

  const format = options.format ?? 'png';

  if (options.fullPage) {
    const metrics = await chrome.debugger.sendCommand({ tabId }, 'Page.getLayoutMetrics') as {
      contentSize?: { width: number; height: number };
      cssContentSize?: { width: number; height: number };
    };
    const size = metrics.cssContentSize || metrics.contentSize;
    if (size) {
      await chrome.debugger.sendCommand({ tabId }, 'Emulation.setDeviceMetricsOverride', {
        mobile: false,
        width: Math.ceil(size.width),
        height: Math.ceil(size.height),
        deviceScaleFactor: 1,
      });
    }
  }

  try {
    const params: Record<string, unknown> = { format };
    if (format === 'jpeg' && options.quality !== undefined) {
      params.quality = Math.max(0, Math.min(100, options.quality));
    }

    const result = await chrome.debugger.sendCommand({ tabId }, 'Page.captureScreenshot', params) as {
      data: string;
    };

    return result.data;
  } finally {
    if (options.fullPage) {
      await chrome.debugger.sendCommand({ tabId }, 'Emulation.clearDeviceMetricsOverride').catch(() => {});
    }
  }
}

export async function setFileInputFiles(
  tabId: number,
  files: string[],
  selector?: string,
): Promise<void> {
  await ensureAttached(tabId);
  await chrome.debugger.sendCommand({ tabId }, 'DOM.enable');
  const doc = await chrome.debugger.sendCommand({ tabId }, 'DOM.getDocument') as {
    root: { nodeId: number };
  };
  const query = selector || 'input[type="file"]';
  const result = await chrome.debugger.sendCommand({ tabId }, 'DOM.querySelector', {
    nodeId: doc.root.nodeId,
    selector: query,
  }) as { nodeId: number };
  if (!result.nodeId) throw new Error(`No element found matching selector: ${query}`);
  await chrome.debugger.sendCommand({ tabId }, 'DOM.setFileInputFiles', {
    files,
    nodeId: result.nodeId,
  });
}

export async function insertText(tabId: number, text: string): Promise<void> {
  await ensureAttached(tabId);
  await chrome.debugger.sendCommand({ tabId }, 'Input.insertText', { text });
}

function normalizeCapturePatterns(pattern?: string): string[] {
  return String(pattern || '').split('|').map(p => p.trim()).filter(Boolean);
}

function shouldCaptureUrl(url: string | undefined, patterns: string[]): boolean {
  if (!url) return false;
  if (!patterns.length) return true;
  return patterns.some(p => url.includes(p));
}

function normalizeHeaders(headers: unknown): Record<string, string> {
  if (!headers || typeof headers !== 'object') return {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(headers as Record<string, unknown>)) {
    out[String(k)] = String(v);
  }
  return out;
}

function getOrCreateEntry(tabId: number, requestId: string, fallback?: {
  url?: string; method?: string; requestHeaders?: Record<string, string>;
}): NetworkCaptureEntry | null {
  const state = networkCaptures.get(tabId);
  if (!state) return null;
  const existing = state.requestToIndex.get(requestId);
  if (existing !== undefined) return state.entries[existing] || null;
  const url = fallback?.url || '';
  if (!shouldCaptureUrl(url, state.patterns)) return null;
  const entry: NetworkCaptureEntry = {
    kind: 'cdp', url, method: fallback?.method || 'GET',
    requestHeaders: fallback?.requestHeaders || {}, timestamp: Date.now(),
  };
  state.entries.push(entry);
  state.requestToIndex.set(requestId, state.entries.length - 1);
  return entry;
}

export async function startNetworkCapture(tabId: number, pattern?: string): Promise<void> {
  await ensureAttached(tabId);
  await chrome.debugger.sendCommand({ tabId }, 'Network.enable');
  networkCaptures.set(tabId, {
    patterns: normalizeCapturePatterns(pattern),
    entries: [],
    requestToIndex: new Map(),
  });
}

export async function readNetworkCapture(tabId: number): Promise<NetworkCaptureEntry[]> {
  const state = networkCaptures.get(tabId);
  if (!state) return [];
  const entries = state.entries.slice();
  state.entries = [];
  state.requestToIndex.clear();
  return entries;
}

export function hasActiveNetworkCapture(tabId: number): boolean {
  return networkCaptures.has(tabId);
}

export async function detach(tabId: number): Promise<void> {
  if (!attached.has(tabId)) return;
  attached.delete(tabId);
  networkCaptures.delete(tabId);
  try { await chrome.debugger.detach({ tabId }); } catch { /* ignore */ }
}

export function registerListeners(): void {
  chrome.tabs.onRemoved.addListener((tabId) => {
    attached.delete(tabId);
    networkCaptures.delete(tabId);
  });
  chrome.debugger.onDetach.addListener((source) => {
    if (source.tabId) {
      attached.delete(source.tabId);
      networkCaptures.delete(source.tabId);
    }
  });
  chrome.tabs.onUpdated.addListener(async (tabId, info) => {
    if (info.url && !isDebuggableUrl(info.url)) {
      await detach(tabId);
    }
  });
  chrome.debugger.onEvent.addListener(async (source, method, params) => {
    const tabId = source.tabId;
    if (!tabId) return;
    const state = networkCaptures.get(tabId);
    if (!state) return;

    if (method === 'Network.requestWillBeSent') {
      const requestId = String((params as Record<string, unknown>)?.requestId || '');
      const req = (params as Record<string, unknown>)?.request as {
        url?: string; method?: string; headers?: Record<string, unknown>; postData?: string; hasPostData?: boolean;
      } | undefined;
      const entry = getOrCreateEntry(tabId, requestId, {
        url: req?.url, method: req?.method, requestHeaders: normalizeHeaders(req?.headers),
      });
      if (!entry) return;
      entry.requestBodyKind = req?.hasPostData ? 'string' : 'empty';
      entry.requestBodyPreview = String(req?.postData || '').slice(0, 4000);
      try {
        const postData = await chrome.debugger.sendCommand({ tabId }, 'Network.getRequestPostData', { requestId }) as { postData?: string };
        if (postData?.postData) {
          entry.requestBodyKind = 'string';
          entry.requestBodyPreview = postData.postData.slice(0, 4000);
        }
      } catch { /* optional */ }
    } else if (method === 'Network.responseReceived') {
      const requestId = String((params as Record<string, unknown>)?.requestId || '');
      const resp = (params as Record<string, unknown>)?.response as {
        url?: string; mimeType?: string; status?: number; headers?: Record<string, unknown>;
      } | undefined;
      const entry = getOrCreateEntry(tabId, requestId, { url: resp?.url });
      if (!entry) return;
      entry.responseStatus = resp?.status;
      entry.responseContentType = resp?.mimeType || '';
      entry.responseHeaders = normalizeHeaders(resp?.headers);
    } else if (method === 'Network.loadingFinished') {
      const requestId = String((params as Record<string, unknown>)?.requestId || '');
      const idx = state.requestToIndex.get(requestId);
      if (idx === undefined) return;
      const entry = state.entries[idx];
      if (!entry) return;
      try {
        const body = await chrome.debugger.sendCommand({ tabId }, 'Network.getResponseBody', { requestId }) as {
          body?: string; base64Encoded?: boolean;
        };
        if (typeof body?.body === 'string') {
          entry.responsePreview = body.base64Encoded
            ? `base64:${body.body.slice(0, 4000)}`
            : body.body.slice(0, 4000);
        }
      } catch { /* optional */ }
    }
  });
}
