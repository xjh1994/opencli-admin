/**
 * Page identity mapping — targetId ↔ tabId.
 *
 * targetId is the cross-layer page identity (CDP target UUID).
 * tabId is an internal Chrome Tabs API routing detail — never exposed outside the extension.
 *
 * Synced with @jackwener/opencli v1.7.4.
 */

const targetToTab = new Map<string, number>();
const tabToTarget = new Map<number, string>();

export async function resolveTargetId(tabId: number): Promise<string> {
  const cached = tabToTarget.get(tabId);
  if (cached) return cached;
  await refreshMappings();
  const result = tabToTarget.get(tabId);
  if (!result) throw new Error(`No targetId for tab ${tabId} — page may have been closed`);
  return result;
}

export async function resolveTabId(targetId: string): Promise<number> {
  const cached = targetToTab.get(targetId);
  if (cached !== undefined) return cached;
  await refreshMappings();
  const result = targetToTab.get(targetId);
  if (result === undefined) throw new Error(`Page not found: ${targetId} — stale page identity`);
  return result;
}

export function evictTab(tabId: number): void {
  const targetId = tabToTarget.get(tabId);
  if (targetId) targetToTab.delete(targetId);
  tabToTarget.delete(tabId);
}

async function refreshMappings(): Promise<void> {
  const targets = await chrome.debugger.getTargets();
  targetToTab.clear();
  tabToTarget.clear();
  for (const t of targets) {
    if (t.type === 'page' && t.tabId !== undefined) {
      targetToTab.set(t.id, t.tabId);
      tabToTarget.set(t.tabId, t.id);
    }
  }
}
