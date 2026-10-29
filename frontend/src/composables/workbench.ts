export interface StrategyCard {
  name: string; market: string; exchange: string; informative: string[];
  description: string; warning: string; installed: boolean; repo: string; path: string; branch: string;
}
export interface ResearchJob {
  id: string; kind: string; status: string; message: string; created: string;
  payload: { strategies?: string[]; exchange?: string; timerange?: string }; results: string[];
}
export interface ReportSummary {
  id: string; file: string; strategy: string; initial: number; final: number; start: string; end: string;
  exchange: string; market: string; profit: number; profit_abs: number; trades: number;
  winrate: number | null; drawdown: number | null; sharpe: number | null; sortino: number | null;
  profit_factor: number | null; html_ready: boolean; basis: string;
  monthly: { year: number; month: number; value: number }[];
  yearly: { year: number; value: number }[];
}
export interface ReportDetail extends ReportSummary {
  equity: { date: string; value: number; drawdown: number }[];
  trade_list: { pair: string; open_date: string; close_date: string; profit_abs: number; profit_ratio: number; exit_reason: string; is_short: boolean }[];
}
export interface WorkbenchStatus {
  engine_version: string; quantstats_version: string; strategies: StrategyCard[];
  engines: Record<string, { running: boolean; mode: string; strategy: string; port: number }>;
  data_ready: boolean; datasets: { exchange: string; market: string; pairs: number }[];
  capital: number; max_open_trades: number; telegram_ready: boolean; exchange_ready: boolean;
  jobs: ResearchJob[]; reports: ReportSummary[];
}
const status = ref<WorkbenchStatus>();
const error = ref('');
const notice = ref('');
const busy = ref(false);

export async function workbenchApi<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/workbench${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', 'X-FMA-Request': '1' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(Array.isArray(detail) ? detail.map((d: { msg: string }) => d.msg).join(' ') : String(detail || response.statusText));
  }
  return data as T;
}

export function useWorkbench() {
  async function refresh() { status.value = await workbenchApi<WorkbenchStatus>('/status'); }
  async function action(fn: () => Promise<unknown>, message = '') {
    busy.value = true; error.value = ''; notice.value = '';
    try { await fn(); notice.value = message; await refresh(); }
    catch (e) { error.value = e instanceof Error ? e.message : String(e); }
    finally { busy.value = false; }
  }
  async function connect(mode: 'research' | 'trading', payload?: unknown) {
    await workbenchApi(`/engines/${mode}`, payload || { strategies: ['NASOSv4_SMA'] });
    const auth = await workbenchApi<{ botName: string; url: string; username: string; password: string }>(`/engines/${mode}/connection`);
    const bots = useBotStore();
    const existing = Object.values(bots.availableBots).find(b => b.botUrl === auth.url);
    const botId = existing?.botId || bots.nextBotId;
    let last: unknown;
    for (let i = 0; i < 45; i++) {
      try {
        await useLoginInfo(botId).login(auth);
        if (!existing) bots.addBot({ botName: auth.botName, botId, botUrl: auth.url, sortId: bots.botCount + 1 });
        bots.selectBot(botId);
        await bots.allRefreshFull();
        return;
      } catch (e) { last = e; await new Promise(resolve => setTimeout(resolve, 1000)); }
    }
    throw new Error(`Engine did not become ready. Open its log in Settings. ${String(last)}`);
  }
  return { status, error, notice, busy, refresh, action, connect };
}
export function money(value: number) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(value);
}
export function percent(value: number | null | undefined) { return value == null ? '—' : `${(value * 100).toFixed(2)}%`; }
