<script setup lang="ts">
import type { ReportDetail } from '@/composables/workbench';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components';
use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
]);
const wb = useWorkbench();
const current = ref<ReportDetail>();
const tab = ref('overview');
const tradePage = ref(0);
const archives = ref<{ file: string; strategies: string[] }[]>([]);
const archive = ref('');
const archiveStrategy = ref('');
async function loadArchives() {
  await wb.action(async () => {
    archives.value = await workbenchApi('/results');
  });
}
watch(archive, () => {
  archiveStrategy.value = archives.value.find((a) => a.file === archive.value)?.strategies[0] || '';
});
async function generateReport() {
  await wb.action(
    () => workbenchApi('/reports/create', { file: archive.value, strategy: archiveStrategy.value }),
    'Report generation queued. Research activity shows its progress.',
  );
}
async function select(id: string) {
  await wb.action(async () => {
    current.value = await workbenchApi<ReportDetail>(`/reports/${id}`);
    tradePage.value = 0;
  });
}
watch(
  () => wb.status.value?.reports[0]?.id,
  (id) => {
    if (id && !current.value) void select(id);
  },
  { immediate: true },
);
const chart = computed(() => ({
  animation: false,
  tooltip: { trigger: 'axis' },
  grid: { left: 65, right: 20, top: 25, bottom: 55 },
  xAxis: {
    type: 'category',
    data: current.value?.equity.map((d) => d.date),
    axisLine: { lineStyle: { color: '#dbe5e6' } },
    axisLabel: { color: '#91a0a6', fontSize: 10 },
  },
  yAxis: {
    type: 'value',
    scale: true,
    axisLabel: { color: '#91a0a6', fontSize: 10 },
    splitLine: { lineStyle: { color: '#eff3f4' } },
  },
  dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 5 }],
  series: [
    {
      name: 'Wallet · USDT',
      type: 'line',
      showSymbol: false,
      data: current.value?.equity.map((d) => d.value),
      lineStyle: { color: '#238671', width: 2 },
      itemStyle: { color: '#238671' },
      areaStyle: { color: '#d8f2e4', opacity: 0.55 },
    },
  ],
}));
const drawdown = computed(() => ({
  ...chart.value,
  yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
  series: [
    {
      name: 'Drawdown %',
      type: 'line',
      showSymbol: false,
      data: current.value?.equity.map((d) => +(d.drawdown * 100).toFixed(3)),
      lineStyle: { color: '#d78069', width: 1.5 },
      areaStyle: { color: '#f7ded5' },
    },
  ],
}));
const years = computed(() => [...new Set(current.value?.monthly.map((m) => m.year))]);
function monthly(year: number, month: number) {
  return current.value?.monthly.find((m) => m.year === year && m.month === month)?.value;
}
function heat(value: number | undefined) {
  return value === undefined
    ? ''
    : `background:${value >= 0 ? '#e5f4ea' : '#fbeae5'};color:${value >= 0 ? '#34895e' : '#bc6656'}`;
}
</script>
<template>
  <details class="card advanced-details">
    <summary @click="loadArchives">Generate QuantStats for a saved engine archive</summary>
    <p>Includes runs made in the native backtest explorer. Wallet exports are required.</p>
    <form class="form-grid" @submit.prevent="generateReport">
      <label
        >Engine archive<select v-model="archive" required>
          <option value="" disabled>Select an archive</option>
          <option v-for="item in archives" :key="item.file" :value="item.file">
            {{ item.file }}
          </option>
        </select></label
      >
      <label
        >Strategy<select v-model="archiveStrategy" required>
          <option
            v-for="name in archives.find((a) => a.file === archive)?.strategies || []"
            :key="name"
          >
            {{ name }}
          </option>
        </select></label
      >
      <button class="primary-button" :disabled="wb.busy.value || !archiveStrategy">
        Generate report
      </button>
    </form>
  </details>
  <section v-if="!wb.status.value?.reports.length" class="card empty-state">
    <UIcon name="mdi:chart-box-outline" />
    <h2>Your results belong here.</h2>
    <p>
      Complete a backtest to unlock portfolio charts, year-by-year returns and your QuantStats tear
      sheet.
    </p>
    <RouterLink class="primary-button" to="/?view=backtesting">Create an experiment</RouterLink>
  </section>
  <template v-else
    ><section class="card">
      <div class="section-title">
        <div>
          <h2>Compare experiments</h2>
          <p>Select a row to explore its full results. Compare matching markets and periods.</p>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Market</th>
              <th>Period</th>
              <th>Return</th>
              <th>Max drawdown</th>
              <th>Trades</th>
              <th>Win rate</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in wb.status.value?.reports"
              :key="r.id"
              tabindex="0"
              class="report-list-item"
              :class="{ selected: current?.id === r.id }"
              @click="select(r.id)"
              @keydown.enter="select(r.id)"
            >
              <td>{{ r.strategy }}</td>
              <td>{{ r.exchange }} · {{ r.market }}</td>
              <td>{{ r.start.slice(0, 10) }} — {{ r.end.slice(0, 10) }}</td>
              <td :class="r.profit >= 0 ? 'positive' : 'negative'">{{ percent(r.profit) }}</td>
              <td>{{ percent(r.drawdown) }}</td>
              <td>{{ r.trades }}</td>
              <td>{{ percent(r.winrate) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <template v-if="current"
      ><section class="card">
        <h2>{{ current.strategy }}</h2>
        <p v-for="warning in current.warnings" :key="warning" class="negative">{{ warning }}</p>
        <p>
          Position allocation:
          {{
            current.stake_amount === 'unlimited'
              ? 'Automatic / compound balance'
              : `${current.stake_amount ?? '—'} USDT fixed`
          }}
          · {{ current.max_open_trades ?? '—' }} maximum open positions
        </p>
        <p>
          {{ current.exchange }} · {{ current.market }} ·
          {{ current.processed_pairs ?? '—' }} processed /
          {{ current.requested_pairs ?? '—' }} requested pairs ·
          {{ current.dataset_pairs ?? '—' }} pairs in the dataset
        </p>
        <p>
          Backtests use historical candles and current exchange rules. Execution assumptions, warmup
          and liquidity can materially change live results.
        </p>
        <p v-if="current.skipped_pairs?.length" class="negative">
          Skipped by the engine: {{ current.skipped_pairs.join(', ') }}
        </p>
      </section>
      <div class="metric-grid">
        <section class="card metric">
          <div class="metric-label">Net return</div>
          <div class="metric-value" :class="current.profit >= 0 ? 'positive' : 'negative'">
            {{ percent(current.profit) }}
          </div>
          <div class="metric-foot">{{ money(current.profit_abs) }} USDT</div>
        </section>
        <section class="card metric">
          <div class="metric-label">Final balance</div>
          <div class="metric-value">{{ money(current.final) }}<small>USDT</small></div>
          <div class="metric-foot">Started with {{ money(current.initial) }} USDT</div>
        </section>
        <section class="card metric">
          <div class="metric-label">Maximum drawdown</div>
          <div class="metric-value">{{ percent(current.drawdown) }}</div>
          <div class="metric-foot">Native Freqtrade metric</div>
        </section>
        <section class="card metric">
          <div class="metric-label">Profit factor</div>
          <div class="metric-value">{{ current.profit_factor?.toFixed(2) || '—' }}</div>
          <div class="metric-foot">
            Sharpe {{ current.sharpe?.toFixed(2) || '—' }} · Sortino
            {{ current.sortino?.toFixed(2) || '—' }}
          </div>
        </section>
      </div>
      <div class="report-tabs">
        <button
          v-for="t in ['overview', 'trades', 'QuantStats HTML']"
          :key="t"
          :class="{ active: tab === t }"
          @click="tab = t"
        >
          {{ t }}</button
        ><a
          class="text-button"
          :href="`/workbench/results/download?file=${encodeURIComponent(current.file)}`"
          >Download engine archive</a
        >
      </div>
      <template v-if="tab === 'overview'"
        ><section class="card">
          <div class="section-title">
            <div>
              <h2>Portfolio growth</h2>
              <p>Daily wallet equity · USDT · UTC</p>
            </div>
            <span class="pill safe">RECONCILED</span>
          </div>
          <VChart class="report-chart" :option="chart" autoresize />
          <p>{{ current.basis }}</p>
        </section>
        <section class="card">
          <h2>Monthly returns, year by year</h2>
          <p>Compounded daily portfolio returns. Empty cells have no covered period.</p>
          <div class="table-wrap" style="margin-top: 20px">
            <table class="data-table heatmap">
              <thead>
                <tr>
                  <th>Year</th>
                  <th
                    v-for="month in [
                      'Jan',
                      'Feb',
                      'Mar',
                      'Apr',
                      'May',
                      'Jun',
                      'Jul',
                      'Aug',
                      'Sep',
                      'Oct',
                      'Nov',
                      'Dec',
                    ]"
                    :key="month"
                  >
                    {{ month }}
                  </th>
                  <th>Year</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="year in years" :key="year">
                  <th>{{ year }}</th>
                  <td v-for="month in 12" :key="month" :style="heat(monthly(year, month))">
                    {{ percent(monthly(year, month)) }}
                  </td>
                  <th>{{ percent(current.yearly.find((y) => y.year === year)?.value) }}</th>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="card">
          <h2>Daily wallet drawdown</h2>
          <VChart class="report-chart" :option="drawdown" autoresize /></section
      ></template>
      <section v-else-if="tab === 'trades'" class="card">
        <h2>Every trade, in context</h2>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Pair</th>
                <th>Direction</th>
                <th>Opened</th>
                <th>Closed</th>
                <th>Profit USDT</th>
                <th>Return</th>
                <th>Exit reason</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(t, i) in current.trade_list.slice(tradePage * 100, (tradePage + 1) * 100)"
                :key="i"
              >
                <td>{{ t.pair }}</td>
                <td>{{ t.is_short ? 'Short' : 'Long' }}</td>
                <td>{{ t.open_date }}</td>
                <td>{{ t.close_date }}</td>
                <td :class="t.profit_abs >= 0 ? 'positive' : 'negative'">
                  {{ money(t.profit_abs) }}
                </td>
                <td>{{ percent(t.profit_ratio) }}</td>
                <td>{{ t.exit_reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="button-row">
          <button class="secondary-button" :disabled="tradePage === 0" @click="tradePage--">
            Previous</button
          ><button
            class="secondary-button"
            :disabled="(tradePage + 1) * 100 >= current.trade_list.length"
            @click="tradePage++"
          >
            Next
          </button>
        </div>
      </section>
      <section v-else class="card">
        <div class="section-title">
          <div>
            <h2>Complete QuantStats tear sheet</h2>
            <p>365 periods per year · BTC benchmark when its daily history covers the run.</p>
          </div>
          <a
            v-if="current.html_ready"
            class="secondary-button"
            :href="`/workbench/reports/${current.id}/html?download=true`"
            >Download HTML</a
          >
        </div>
        <iframe
          v-if="current.html_ready"
          class="report-frame"
          :src="`/workbench/reports/${current.id}/html`"
          sandbox
          title="QuantStats performance report"
        ></iframe>
        <p v-else>
          Not enough nonzero daily returns to produce a meaningful QuantStats HTML report.
        </p>
      </section></template
    ></template
  >
</template>
