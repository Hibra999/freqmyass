<script setup lang="ts">
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent]);

interface RunState {
  id: string;
  status: string;
  running: boolean;
  completed: number;
  target: number;
  strategy_evaluations: number;
  failures: number;
  workers: number;
  horizon_days: number;
  eta_seconds?: number;
  paths_per_hour?: number;
  message: string;
  publication?: { status: string; message?: string; commit?: string };
}
interface Summary {
  completed: number;
  target: number;
  assumptions: string[];
  prices: Record<
    string,
    {
      count: number;
      chart_sample: number;
      daily_percentiles: number[][];
      final_percentiles: number[];
    }
  >;
  strategies: {
    regime: string;
    strategy: string;
    valid: number;
    failed: number;
    probability_loss: number | null;
    probability_no_trades: number | null;
    final_percentiles: number[];
    drawdown_percentiles: number[];
    average_trades: number | null;
  }[];
}
const wb = useWorkbench();
const settings = useSettingsStore();
const runs = ref<RunState[]>([]);
const selected = ref('');
const current = ref<{
  state: RunState;
  summary: Summary | null;
  config: {
    backend: string;
    drifts: number[];
    seed: number;
    volatility: number;
    capital: number;
    stake_amount: string | number;
  };
}>();
const source = ref<{
  initial_price: number;
  volatility: number;
  observations: number;
  start: string;
  end: string;
  gpu: { name: string; cupy: string };
}>();
const form = reactive({
  paths: 1000000,
  days: 365,
  workers: 16,
  seed: 20261030,
  capital: 1000,
  max_open_trades: 3,
  allocation: 'automatic',
  fixed_stake: 330,
  bear: -30,
  neutral: 0,
  bull: 30,
});
const regime = ref('neutral');
let poll: ReturnType<typeof setInterval>;
async function refresh() {
  runs.value = await workbenchApi('/simulations');
  if (!selected.value && runs.value[0]) selected.value = runs.value[0].id;
  if (selected.value) current.value = await workbenchApi(`/simulations/${selected.value}`);
}
async function start() {
  await wb.action(async () => {
    const result = await workbenchApi<RunState>('/simulations', {
      paths: form.paths,
      days: form.days,
      workers: form.workers,
      seed: form.seed,
      capital: form.capital,
      max_open_trades: form.max_open_trades,
      stake_amount: form.allocation === 'automatic' ? 'unlimited' : form.fixed_stake,
      drifts: [form.bear, form.neutral, form.bull].map((n) => n / 100),
    });
    selected.value = result.id;
    await refresh();
  }, 'CUDA simulation started. Freqtrade evaluates every path on CPU. Progress survives closing this browser.');
}
async function action(name: 'pause' | 'resume' | 'export') {
  await wb.action(
    async () => {
      await workbenchApi(`/simulations/${selected.value}/${name}`, {});
      await refresh();
    },
    name === 'export'
      ? 'Repository snapshot queued. Research activity shows completion.'
      : `${name === 'pause' ? 'Pause requested; active paths finish first' : 'Simulation resumed'}.`,
  );
}
onMounted(async () => {
  await wb.action(async () => {
    await refresh();
    source.value = await workbenchApi('/simulations/calibration');
  });
  poll = setInterval(() => void refresh().catch(() => {}), 5000);
});
onBeforeUnmount(() => clearInterval(poll));
const rows = computed(
  () => current.value?.summary?.strategies.filter((row) => row.regime === regime.value) || [],
);
const prices = computed(() => current.value?.summary?.prices[regime.value]);
const chart = computed(() => ({
  color: ['#f5a197', '#8be0b6', '#6fbce5'],
  backgroundColor: 'transparent',
  animation: false,
  tooltip: { trigger: 'axis' },
  legend: { top: 0 },
  grid: { left: 80, right: 25, top: 45, bottom: 35 },
  xAxis: {
    type: 'category',
    name: 'Day',
    data: prices.value?.daily_percentiles[0]?.map((_, i) => i),
  },
  yAxis: { type: 'value', name: 'BTC · USDT', scale: true },
  series: ['Low · P5', 'Median · P50', 'High · P95'].map((name, index) => ({
    name,
    type: 'line',
    showSymbol: false,
    data: prices.value?.daily_percentiles[index],
    lineStyle: { color: ['#f5a197', '#8be0b6', '#6fbce5'][index], width: 2 },
  })),
}));
const eta = computed(() => {
  const value = current.value?.state;
  if (value?.completed === value?.target) return '0 days';
  if (!value?.eta_seconds || value.completed < value.workers * 3) return 'Estimating…';
  return `${(value.eta_seconds / 86400).toFixed(1)} days`;
});
</script>

<template>
  <section class="card">
    <div class="section-title">
      <div>
        <h2>Synthetic price paths. Original strategy execution.</h2>
        <p>
          CUDA generates complete BTC/USDT paths with geometric Brownian motion. Freqtrade evaluates
          all four strategies on every path.
        </p>
      </div>
      <span class="pill safe">CUDA + NATIVE FREQTRADE</span>
    </div>
    <p v-if="source">
      {{ source.gpu.name }} · CuPy {{ source.gpu.cupy }} · calibrated annual volatility
      {{ percent(source.volatility) }} · initial BTC {{ money(source.initial_price) }} USDT.
    </p>
    <p>
      One million annual paths at 5m contain 105.12 billion trading candles and require four million
      native backtests. CUDA accelerates price generation; Freqtrade execution remains on CPU. This
      is a long-running workload, not an instant forecast.
    </p>
    <p>
      Progress is saved after every path. Windows stays awake while computing; closing this browser
      does not stop the run. Completion exports all outcomes and pushes this run's results to main
      when the repository has no unrelated changes. After a shutdown, reopen the app and resume.
    </p>
    <form class="settings-form" style="margin-top: 20px" @submit.prevent="start">
      <div class="form-grid">
        <label
          >Complete trajectories<input
            v-model.number="form.paths"
            type="number"
            min="1"
            max="1000000"
            required
        /></label>
        <label
          >Days per trajectory<input
            v-model.number="form.days"
            type="number"
            min="1"
            max="365"
            required
        /></label>
        <label
          >CPU workers<input v-model.number="form.workers" type="number" min="1" max="16" required
        /></label>
        <label
          >Reproducible seed<input
            v-model.number="form.seed"
            type="number"
            min="0"
            max="4294967295"
            required
        /></label>
      </div>
      <details class="advanced-details">
        <summary>Model assumptions and native allocation</summary>
        <p>
          Paths are split evenly between these three assumed annual drifts. Volatility comes from
          available historical BTC 5m returns. These are hypothetical model inputs.
        </p>
        <div class="form-grid">
          <label
            >Bear drift · % per year<input
              v-model.number="form.bear"
              type="number"
              min="-200"
              max="200"
              step="1"
              required
          /></label>
          <label
            >Neutral drift · % per year<input
              v-model.number="form.neutral"
              type="number"
              min="-200"
              max="200"
              step="1"
              required
          /></label>
          <label
            >Bull drift · % per year<input
              v-model.number="form.bull"
              type="number"
              min="-200"
              max="200"
              step="1"
              required
          /></label>
          <label
            >Starting strategy capital · USDT<input
              v-model.number="form.capital"
              type="number"
              min="1"
              required
          /></label>
          <label
            >Maximum positions<input
              v-model.number="form.max_open_trades"
              type="number"
              min="1"
              max="100"
              required
          /></label>
          <label
            >Allocation<select v-model="form.allocation">
              <option value="automatic">Automatic / compound balance</option>
              <option value="fixed">Fixed USDT per entry</option>
            </select></label
          >
          <label v-if="form.allocation === 'fixed'"
            >Fixed stake · USDT<input
              v-model.number="form.fixed_stake"
              type="number"
              min="0.01"
              step="0.01"
              required
          /></label>
        </div>
        <p>
          One-minute GBM samples form 5m candles. Fourteen days of synthetic warmup supply
          informative candles. Volume is fixed at 100 BTC/candle, funding is zero, and futures mark
          equals synthetic spot. Original signal and risk rules stay unchanged.
        </p>
      </details>
      <div class="button-row">
        <button
          class="primary-button"
          :disabled="wb.busy.value || !source || runs.some((r) => r.running)"
        >
          Start {{ form.paths.toLocaleString('en-US') }} trajectories
        </button>
      </div>
    </form>
  </section>
  <section v-if="runs.length" class="card">
    <label
      >Saved simulation<select v-model="selected" @change="wb.action(refresh)">
        <option v-for="run in runs" :key="run.id" :value="run.id">
          {{ run.target.toLocaleString('en-US') }} paths · {{ run.horizon_days }} days ·
          {{ run.status }} · {{ run.id.slice(0, 8) }}
        </option>
      </select></label
    >
    <template v-if="current"
      ><div class="section-title" style="margin-top: 22px">
        <h2>
          {{ current.state.completed.toLocaleString('en-US') }} /
          {{ current.state.target.toLocaleString('en-US') }} paths evaluated
        </h2>
        <span class="pill">{{ current.state.status }}</span>
      </div>
      <progress
        style="width: 100%; accent-color: #80d8b5"
        :value="current.state.completed"
        :max="current.state.target"
        aria-label="Simulation progress"
      ></progress>
      <p>
        {{ current.state.strategy_evaluations.toLocaleString('en-US') }} strategy evaluations ·
        {{ current.state.failures }} failures · {{ current.state.workers }} CPU workers · estimated
        remaining {{ eta }}.
      </p>
      <p>{{ current.state.message }}</p>
      <p v-if="current.state.publication">
        Publication: {{ current.state.publication.status }} ·
        {{ current.state.publication.message || current.state.publication.commit }}
      </p>
      <p>
        Saved model: {{ current.config.backend.toUpperCase() }} · drifts
        {{ current.config.drifts.map(percent).join(' / ') }} · volatility
        {{ percent(current.config.volatility) }} · seed {{ current.config.seed }} ·
        {{ money(current.config.capital) }} USDT · allocation {{ current.config.stake_amount }}.
      </p>
      <div class="button-row">
        <button
          v-if="current.state.running"
          class="secondary-button"
          :disabled="wb.busy.value"
          @click="action('pause')"
        >
          Pause after active paths
        </button>
        <button
          v-else-if="current.state.completed < current.state.target"
          class="primary-button"
          :disabled="wb.busy.value || runs.some((r) => r.running)"
          @click="action('resume')"
        >
          Resume simulation
        </button>
        <button
          class="secondary-button"
          :disabled="wb.busy.value || !current.state.completed || current.state.running"
          @click="action('export')"
        >
          Save snapshot in repository
        </button>
      </div>
    </template>
  </section>
  <template v-if="current?.summary?.completed">
    <section class="card">
      <div class="section-title">
        <div>
          <h2>Conditional scenarios</h2>
          <p>
            Statistics snapshot: {{ current.summary.completed.toLocaleString('en-US') }} completed
            paths. Updates at checkpoints and on pause/completion.
          </p>
        </div>
        <select v-model="regime" aria-label="Market regime">
          <option value="bear">Bear</option>
          <option value="neutral">Neutral</option>
          <option value="bull">Bull</option>
        </select>
      </div>
      <VChart class="report-chart" :option="chart" :theme="settings.chartTheme" autoresize />
      <p v-if="prices?.final_percentiles.length">
        Final BTC price · all completed paths in this regime · P5 / P50 / P95:
        {{ prices.final_percentiles.map(money).join(' / ') }} USDT.
      </p>
      <p>
        Pointwise price percentiles from {{ prices?.chart_sample || 0 }} example paths in this
        regime. Terminal metrics include all
        {{ prices?.count.toLocaleString('en-US') || 0 }} completed paths in the snapshot. These
        lines are not individual paths.
      </p>
    </section>
    <section class="card">
      <h2>Strategy outcomes · native Freqtrade</h2>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Valid / failed</th>
              <th>Loss probability</th>
              <th>No trades</th>
              <th>Final P5</th>
              <th>Final P50</th>
              <th>Final P95</th>
              <th>Drawdown P95</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.strategy">
              <td>{{ row.strategy }}</td>
              <td>{{ row.valid }} / {{ row.failed }}</td>
              <td>{{ percent(row.probability_loss) }}</td>
              <td>{{ percent(row.probability_no_trades) }}</td>
              <td>{{ row.final_percentiles.length ? money(row.final_percentiles[0]!) : '—' }}</td>
              <td>{{ row.final_percentiles.length ? money(row.final_percentiles[1]!) : '—' }}</td>
              <td>{{ row.final_percentiles.length ? money(row.final_percentiles[2]!) : '—' }}</td>
              <td>{{ percent(row.drawdown_percentiles[2]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        Final balance in USDT. Probabilities exclude failed evaluations; failures and zero-trade
        runs remain visible. Drawdown is calculated by Freqtrade from closed-trade equity.
      </p>
      <details class="advanced-details">
        <summary>Assumptions and limits</summary>
        <p v-for="text in current.summary.assumptions" :key="text">{{ text }}</p>
      </details>
    </section>
  </template>
  <JobQueue />
</template>
