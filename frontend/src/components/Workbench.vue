<script setup lang="ts">
const route = useRoute();
const wb = useWorkbench();
const view = computed(() => String(route.query.view || 'overview'));
const titles: Record<string, [string, string]> = {
  overview: [
    'A clearer view of your trading.',
    'Research, test and manage your strategies. All in one place.',
  ],
  strategies: [
    'Find your next edge.',
    'Four original strategies. One consistent research workflow.',
  ],
  backtesting: [
    'Test an idea. See the whole picture.',
    'Build an experiment in a few steps. Freqtrade does the calculations.',
  ],
  reports: [
    'Understand every result.',
    'Portfolio returns, monthly performance and the complete QuantStats report.',
  ],
  data: [
    'Your entire market library.',
    'All available files from NostalgiaForInfinityData, stored locally.',
  ],
  trading: [
    'From research to a running bot.',
    'Start in simulation. Live trading always requires explicit activation.',
  ],
  advanced: [
    'More control, when you need it.',
    'Official Freqtrade tools, with the same engine and original execution logic.',
  ],
  setup: ['Make this workspace yours.', 'Defaults, local connections and private credentials.'],
};
const latest = computed(() => wb.status.value?.reports[0]);
const totalPairs = computed(() => wb.status.value?.datasets.reduce((n, d) => n + d.pairs, 0) || 0);
const telegramStatus = computed(() =>
  wb.status.value?.telegram_engine_running
    ? 'Engine running · send /help in Telegram to verify reception'
    : wb.status.value?.telegram_ready
      ? 'Credentials saved · open or restart the trading engine to receive commands'
      : 'Add credentials in Settings',
);
const inventory = ref<{
  count: number;
  bytes: number;
  revision?: string;
  scanned?: string;
  files: {
    file: string;
    bytes: number;
    start?: string;
    end?: string;
    gaps?: number;
    duplicates?: number;
    error?: string;
  }[];
}>({ count: 0, bytes: 0, files: [] });
const search = ref('');
const page = ref(0);
const filtered = computed(() =>
  inventory.value.files.filter((f) => f.file.toLowerCase().includes(search.value.toLowerCase())),
);
watch(search, () => (page.value = 0));
watch(
  view,
  async (v) => {
    if (v === 'data') await wb.action(async () => (inventory.value = await workbenchApi('/data')));
  },
  { immediate: true },
);
const form = reactive({
  capital: 1000,
  max_open_trades: 3,
  telegram_token: '',
  telegram_chat_id: '',
  exchange_key: '',
  exchange_secret: '',
  exchange_password: '',
  credential_exchange: 'binance',
});
let initialized = false;
watch(
  wb.status,
  (s) => {
    if (s && !initialized) {
      form.capital = s.capital;
      form.max_open_trades = s.max_open_trades;
      form.credential_exchange = s.credential_exchange || 'binance';
      initialized = true;
    }
  },
  { immediate: true },
);
const engineLog = ref('');
async function save() {
  await wb.action(async () => {
    await workbenchApi('/settings', {
      ...form,
      telegram_token: form.telegram_token || null,
      telegram_chat_id: form.telegram_chat_id || null,
      exchange_key: form.exchange_key || null,
      exchange_secret: form.exchange_secret || null,
      exchange_password: form.exchange_password || null,
    });
    form.telegram_token = '';
    form.exchange_key = '';
    form.exchange_secret = '';
    form.exchange_password = '';
  }, 'Settings saved locally. Existing engines keep their current configuration until restarted.');
}
const tools = [
  [
    '/backtest',
    'Backtest explorer',
    'Compare engine results, charts and individual trades.',
    'mdi:chart-timeline-variant',
  ],
  [
    '/graph',
    'Candles & indicators',
    'Explore the market with strategy overlays.',
    'mdi:chart-candlestick',
  ],
  [
    '/download_data',
    'Download more candles',
    'The official collector for additional market data.',
    'mdi:download-outline',
  ],
  [
    '/pairlist_config',
    'Pairlist builder',
    'Build and test the list of markets your bot uses.',
    'mdi:format-list-checks',
  ],
  [
    '/lookahead_analysis',
    'Lookahead analysis',
    'Check whether signals use future information.',
    'mdi:eye-check-outline',
  ],
  [
    '/recursive_analysis',
    'Warmup analysis',
    'Measure indicator stability across startup periods.',
    'mdi:reload',
  ],
];
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">{{ view === 'overview' ? 'YOUR RESEARCH, SIMPLIFIED' : view }}</div>
      <h1>{{ titles[view]?.[0] || 'Workspace' }}</h1>
      <p>{{ titles[view]?.[1] }}</p>
    </div>
    <RouterLink v-if="view === 'overview'" class="primary-button" to="/?view=backtesting"
      ><UIcon name="mdi:plus" />New backtest</RouterLink
    >
  </div>
  <template v-if="view === 'overview'">
    <div class="metric-grid">
      <section class="card metric">
        <div class="metric-label">Starting capital<UIcon name="mdi:wallet-outline" /></div>
        <div class="metric-value">
          {{ money(wb.status.value?.capital || 1000) }}<small>USDT</small>
        </div>
        <div class="metric-foot">Simulation budget · editable</div>
      </section>
      <section class="card metric">
        <div class="metric-label">Strategy library<UIcon name="mdi:flask-outline" /></div>
        <div class="metric-value">
          {{ wb.status.value?.strategies.filter((s) => s.installed).length || 0
          }}<small>strategies</small>
        </div>
        <div class="metric-foot">Spot + futures · 5-minute candles</div>
      </section>
      <section class="card metric">
        <div class="metric-label">Market coverage<UIcon name="mdi:database-outline" /></div>
        <div class="metric-value">{{ totalPairs }}<small>markets</small></div>
        <div class="metric-foot">Across 3 exchange / market datasets</div>
      </section>
      <section class="card metric">
        <div class="metric-label">Completed reports<UIcon name="mdi:chart-box-outline" /></div>
        <div class="metric-value">
          {{ wb.status.value?.reports.length || 0 }}<small>reports</small>
        </div>
        <div class="metric-foot">Reconciled with the engine wallet</div>
      </section>
    </div>
    <section class="card welcome-card">
      <div>
        <div class="eyebrow">LESS SETUP. MORE UNDERSTANDING.</div>
        <h2>Your strategy. The full picture.</h2>
        <p>
          Start with a strategy, choose your market, and let the research lab handle the rest. Every
          result comes with context.
        </p>
        <div class="button-row">
          <RouterLink class="primary-button" to="/?view=backtesting"
            >Run your next experiment <UIcon name="mdi:arrow-right" /></RouterLink
          ><RouterLink class="text-button" to="/?view=strategies">Explore strategies</RouterLink>
        </div>
      </div>
      <UIcon class="welcome-art" name="mdi:chart-areaspline" />
    </section>
    <div class="two-columns">
      <section class="card">
        <div class="section-title">
          <div>
            <h2>Workspace readiness</h2>
            <p>A reliable starting point for your next experiment.</p>
          </div>
          <span class="pill safe">LOCAL WORKSPACE</span>
        </div>
        <div class="steps-list">
          <div class="checklist-row">
            <span class="checklist-icon"><UIcon name="mdi:check" /></span>
            <div>
              <strong>Freqtrade engine connected to Conda</strong
              ><small>Original engine · {{ wb.status.value?.engine_version }}</small>
            </div>
          </div>
          <div class="checklist-row">
            <span class="checklist-icon"
              ><UIcon :name="wb.status.value?.data_ready ? 'mdi:check' : 'mdi:download'"
            /></span>
            <div>
              <strong>{{
                wb.status.value?.data_ready ? 'Market data available' : 'Import your market history'
              }}</strong
              ><small>Binance spot & futures · KuCoin spot</small>
            </div>
            <RouterLink class="text-button" to="/?view=data">View</RouterLink>
          </div>
          <div class="checklist-row">
            <span class="checklist-icon"
              ><UIcon
                :name="wb.status.value?.telegram_engine_running ? 'mdi:check' : 'mdi:send-outline'"
            /></span>
            <div>
              <strong>Native Telegram integration</strong><small>{{ telegramStatus }}</small>
            </div>
          </div>
        </div>
      </section>
      <section class="card">
        <div class="section-title">
          <h2>Latest experiment</h2>
          <span class="pill">{{ latest ? 'REPORT READY' : 'YOUR FIRST RUN' }}</span>
        </div>
        <template v-if="latest"
          ><strong style="overflow-wrap: anywhere">{{ latest.strategy }}</strong>
          <div class="metric-value" :class="latest.profit >= 0 ? 'positive' : 'negative'">
            {{ percent(latest.profit) }}
          </div>
          <p>{{ latest.trades }} trades · {{ latest.exchange }} {{ latest.market }}</p>
          <p>{{ latest.start.slice(0, 10) }} — {{ latest.end.slice(0, 10) }}</p>
          <RouterLink class="text-button" to="/?view=reports"
            >Explore full report →</RouterLink
          ></template
        >
        <div v-else class="empty-inline">
          <UIcon name="mdi:chart-line" />
          <p>Real results will appear after your first completed backtest.</p>
        </div>
      </section>
    </div>
    <JobQueue />
  </template>
  <template v-else-if="view === 'strategies'"
    ><div class="strategy-grid">
      <section v-for="s in wb.status.value?.strategies" :key="s.name" class="card strategy-card">
        <div class="strategy-top">
          <span class="strategy-avatar"
            ><UIcon :name="s.market === 'spot' ? 'mdi:chart-line' : 'mdi:swap-vertical'" /></span
          ><span class="pill safe">{{ s.market }} · 5m</span>
        </div>
        <h2>{{ s.name }}</h2>
        <p>{{ s.description }}</p>
        <div class="warning-note">{{ s.warning }}</div>
        <small>{{
          s.informative.length
            ? 'Includes 1h informative candles.'
            : 'No additional informative timeframe required.'
        }}</small>
        <div class="button-row">
          <RouterLink class="secondary-button" to="/?view=backtesting">Test strategy →</RouterLink
          ><a
            class="text-button"
            :href="`https://github.com/${s.repo}/blob/${s.branch}/${s.path}`"
            target="_blank"
            rel="noreferrer"
            >Original source ↗</a
          >
        </div>
      </section>
    </div>
    <p class="muted" style="margin-top: 24px; font-size: 12px">
      1,000 USDT and 3 open positions are your comparison defaults, not author recommendations.
      Original parameters and signals are preserved.
    </p></template
  >
  <template v-else-if="view === 'backtesting'"><ResearchForm /><JobQueue /></template>
  <template v-else-if="view === 'reports'"><ReportPanel /></template>
  <template v-else-if="view === 'data'"
    ><div class="metric-grid">
      <section
        v-for="d in wb.status.value?.datasets"
        :key="`${d.exchange}-${d.market}`"
        class="card metric"
      >
        <div class="metric-label">{{ d.exchange }} · {{ d.market }}</div>
        <div class="metric-value">{{ d.pairs }}<small>pairs</small></div>
        <div class="metric-foot">5m · 15m · 1h · 4h · 1d</div>
      </section>
      <section class="card metric">
        <div class="metric-label">Indexed candle files</div>
        <div class="metric-value">{{ inventory.count }}</div>
        <div class="metric-foot">{{ (inventory.bytes / 1024 ** 3).toFixed(2) }} GiB</div>
      </section>
    </div>
    <section class="card">
      <div class="section-title">
        <div>
          <h2>Data integrity & coverage</h2>
          <p>
            KuCoin futures is empty in the source repository. Coverage is measured from each file,
            not inferred from config dates.
          </p>
        </div>
        <div class="button-row">
          <button
            class="secondary-button"
            :disabled="wb.busy.value"
            @click="wb.action(() => workbenchApi('/data/import', {}), 'Import queued.')"
          >
            Import all</button
          ><button
            class="primary-button"
            :disabled="wb.busy.value"
            @click="wb.action(() => workbenchApi('/data/scan', {}), 'Coverage scan queued.')"
          >
            Scan coverage
          </button>
        </div>
      </div>
      <p v-if="inventory.scanned">
        Scanned {{ new Date(inventory.scanned).toLocaleString('en-US') }} · Snapshot
        {{ inventory.revision?.slice(0, 12) }}
      </p>
      <label style="margin: 20px 0"
        >Find a pair, exchange or timeframe<input v-model="search" placeholder="BTC, futures, 1h…"
      /></label>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>File</th>
              <th>First candle</th>
              <th>Last candle</th>
              <th>Gaps</th>
              <th>Duplicates</th>
              <th>Size</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in filtered.slice(page * 50, (page + 1) * 50)" :key="f.file">
              <td>{{ f.file }}</td>
              <td>{{ f.start?.slice(0, 16) || f.error }}</td>
              <td>{{ f.end?.slice(0, 16) }}</td>
              <td :class="f.gaps ? 'negative' : ''">{{ f.gaps }}</td>
              <td>{{ f.duplicates }}</td>
              <td>{{ (f.bytes / 1024 ** 2).toFixed(1) }} MB</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="button-row">
        <button class="secondary-button" :disabled="page === 0" @click="page--">Previous</button
        ><span class="muted"
          >{{ page + 1 }} / {{ Math.max(1, Math.ceil(filtered.length / 50)) }}</span
        ><button
          class="secondary-button"
          :disabled="(page + 1) * 50 >= filtered.length"
          @click="page++"
        >
          Next</button
        ><button
          class="text-button"
          @click="wb.action(async () => (inventory = await workbenchApi('/data')))"
        >
          Refresh inventory
        </button>
      </div>
    </section>
    <JobQueue
  /></template>
  <template v-else-if="view === 'trading'"
    ><div v-if="wb.status.value?.engines.trading?.running" class="card">
      <div class="section-title">
        <div>
          <h2>Your trading engine</h2>
          <p>
            {{ wb.status.value.engines.trading.strategy }} ·
            {{ wb.status.value.engines.trading.mode }}
          </p>
        </div>
        <button class="primary-button" @click="wb.action(() => wb.connect('trading'))">
          Connect controls
        </button>
      </div>
      <div class="button-row">
        <RouterLink class="secondary-button" to="/trade">Trading desk</RouterLink
        ><RouterLink class="secondary-button" to="/dashboard">Portfolio dashboard</RouterLink
        ><RouterLink class="secondary-button" to="/trade_history">Trade history</RouterLink
        ><RouterLink class="secondary-button" to="/balance">Wallet</RouterLink
        ><RouterLink class="secondary-button" to="/logs">Logs</RouterLink>
      </div>
    </div>
    <TradingPanel v-if="wb.status.value?.engines.trading?.running" />
    <ResearchForm v-else trading
  /></template>
  <template v-else-if="view === 'advanced'"
    ><section class="card">
      <div class="section-title">
        <div>
          <h2>Official engine tools</h2>
          <p>Connect the research engine once to enable the tools below.</p>
        </div>
        <button
          class="primary-button"
          :disabled="wb.busy.value"
          @click="wb.action(() => wb.connect('research'), 'Research engine connected.')"
        >
          {{ wb.busy.value ? 'Connecting…' : 'Connect research engine' }}
        </button>
      </div>
      <div class="tool-grid">
        <RouterLink
          v-for="[path, title, text, icon] in tools"
          :key="path"
          class="card tool-card"
          :to="path!"
          ><UIcon :name="icon" />
          <h2>{{ title }}</h2>
          <p>{{ text }}</p></RouterLink
        >
      </div>
    </section>
    <ResearchForm advanced /><JobQueue
  /></template>
  <template v-else-if="view === 'setup'"
    ><div class="two-columns">
      <form class="card settings-form" @submit.prevent="save">
        <h2>Workspace defaults</h2>
        <p>Private settings stay on this computer and never enter Git.</p>
        <div class="form-grid" style="margin-top: 22px">
          <label
            >Starting capital · USDT<input
              v-model.number="form.capital"
              type="number"
              min="1"
              required /></label
          ><label
            >Maximum positions<input
              v-model.number="form.max_open_trades"
              type="number"
              min="1"
              max="100"
              required
          /></label>
        </div>
        <h2>Native Telegram</h2>
        <span class="pill" :class="wb.status.value?.telegram_ready ? 'safe' : ''">{{
          wb.status.value?.telegram_ready ? 'CONFIGURED' : 'NOT CONFIGURED'
        }}</span
        ><label
          >Bot token<input
            v-model="form.telegram_token"
            type="password"
            autocomplete="new-password"
            placeholder="Leave blank to keep the saved token" /></label
        ><label
          >Chat ID<input
            v-model="form.telegram_chat_id"
            placeholder="Leave blank to keep the saved chat ID"
        /></label>
        <p>
          {{ telegramStatus }}. Freqtrade owns all commands. Use a dedicated Telegram token; another
          program such as OpenClaw can consume its messages. The outbound test only checks sending.
        </p>
        <div class="button-row">
          <RouterLink class="secondary-button" to="/?view=trading"
            >Open trading controls</RouterLink
          >
          <button
            type="button"
            class="secondary-button"
            :disabled="wb.busy.value || !wb.status.value?.telegram_ready"
            @click="
              wb.action(
                () => workbenchApi('/telegram/commands', {}),
                'Freqtrade command menu installed. Reopen the Telegram chat, then send /help.',
              )
            "
          >
            Install Freqtrade command menu
          </button>
        </div>
        <p>
          Installing the menu replaces this bot's command list. It does not start trading. Use /help
          or /show_config to check reception. /start starts trading in the active mode.
        </p>
        <details class="advanced-details">
          <summary>Exchange credentials · required only for live trading</summary>
          <label
            >Credentials belong to<select v-model="form.credential_exchange">
              <option value="binance">Binance</option>
              <option value="kucoin">KuCoin</option>
            </select></label
          >
          <label
            >API key<input
              v-model="form.exchange_key"
              type="password"
              autocomplete="new-password" /></label
          ><label
            >API secret<input
              v-model="form.exchange_secret"
              type="password"
              autocomplete="new-password" /></label
          ><label
            >API passphrase · if required<input
              v-model="form.exchange_password"
              type="password"
              autocomplete="new-password"
          /></label>
          <p>
            Use keys without withdrawal permission. Backtests and simulation do not need exchange
            keys.
          </p>
        </details>
        <div class="button-row">
          <button class="primary-button" :disabled="wb.busy.value">Save settings</button
          ><button
            type="button"
            class="secondary-button"
            :disabled="wb.busy.value"
            @click="wb.action(() => workbenchApi('/telegram/test', {}), 'Test message sent.')"
          >
            Test outgoing message
          </button>
        </div>
      </form>
      <div>
        <section class="card">
          <h2>Local connections</h2>
          <p>
            Research and trading use separate Freqtrade processes. Existing exchange accounts remain
            under your control.
          </p>
          <div class="button-row">
            <RouterLink class="secondary-button" to="/login">Connect another bot</RouterLink
            ><RouterLink class="secondary-button" to="/settings"
              >Chart & engine preferences</RouterLink
            >
          </div>
        </section>
        <section class="card">
          <h2>Engine diagnostics</h2>
          <p>Inspect startup failures without opening a terminal.</p>
          <div class="button-row">
            <button
              v-for="mode in ['research', 'trading']"
              :key="mode"
              class="secondary-button"
              @click="
                wb.action(
                  async () =>
                    (engineLog = (await workbenchApi<{ text: string }>(`/engines/${mode}/log`))
                      .text),
                )
              "
            >
              {{ mode }} log
            </button>
          </div>
          <div v-if="engineLog" class="log-panel">
            <pre>{{ engineLog }}</pre>
          </div>
          <div class="button-row">
            <button
              v-for="mode in ['research', 'trading']"
              :key="mode"
              class="secondary-button"
              :disabled="wb.busy.value || !wb.status.value?.engines[mode]?.running"
              @click="
                wb.action(
                  () => workbenchApi(`/engines/${mode}/close`, {}),
                  'Engine closed. You can select another profile.',
                )
              "
            >
              Close {{ mode }} engine
            </button>
          </div>
          <p style="margin-top: 16px">
            Trading cannot be closed here while positions remain open. Use Pause entries to stop new
            entries while managing existing positions.
          </p>
        </section>
      </div>
    </div></template
  >
</template>
