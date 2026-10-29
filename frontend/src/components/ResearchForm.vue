<script setup lang="ts">
const props = withDefaults(defineProps<{ trading?: boolean; advanced?: boolean }>(), { trading: false, advanced: false });
const wb = useWorkbench(); const router = useRouter();
const market = ref('spot'); const selected = ref<string[]>(['NASOSv4_SMA']); const exchange = ref('binance');
const capital = ref(wb.status.value?.capital || 1000); const positions = ref(wb.status.value?.max_open_trades || 3);
const start = ref(''); const end = ref(''); const pairs = ref('');
const kind = ref('backtesting'); const epochs = ref(100); const workers = ref(2);
const loss = ref('SharpeHyperOptLossDaily'); const spaces = ref('buy sell');
const live = ref(false); const confirmation = ref(''); const model = ref(''); const freqai = ref('');
const visible = computed(() => wb.status.value?.strategies.filter(s => s.market === market.value) || []);
watch(market, () => { selected.value = visible.value.length ? [visible.value[0]!.name] : []; if (market.value === 'futures') exchange.value = 'binance'; });
function select(name: string) {
  if (props.trading) { selected.value = [name]; return; }
  selected.value = selected.value.includes(name) ? selected.value.filter(s => s !== name) : [...selected.value, name];
}
async function submit() {
  await wb.action(async () => {
    if (!selected.value.length) throw new Error('Choose at least one strategy.');
    if (!!start.value !== !!end.value) throw new Error('Enter both dates, or leave both blank for all history.');
    const payload = {
      kind: props.advanced ? kind.value : 'backtesting', strategies: selected.value, exchange: exchange.value,
      capital: capital.value, max_open_trades: positions.value,
      timerange: start.value && end.value ? `${start.value.replaceAll('-', '')}-${end.value.replaceAll('-', '')}` : '',
      pairs: pairs.value.trim() ? pairs.value.split(/[\s,]+/).filter(Boolean) : null,
      epochs: epochs.value, workers: workers.value, loss: loss.value, spaces: spaces.value.split(/\s+/),
      freqai_model: model.value || null, freqai_config: freqai.value ? JSON.parse(freqai.value) : null,
    };
    if (props.trading) { await wb.connect('trading', { ...payload, live: live.value, confirmation: confirmation.value }); await router.push('/trade'); }
    else { await workbenchApi('/jobs', payload); }
  }, props.trading ? 'Engine connected. Use Start to begin the selected mode.' : 'Added to your research queue. Results will appear automatically.');
}
</script>
<template>
  <form class="research-form" @submit.prevent="submit">
    <section class="card"><div class="step-heading"><span>01</span><div><h2>Choose your strategy</h2><p>Original signals. Clear market compatibility.</p></div></div>
      <div class="segmented"><button type="button" :class="{ active: market === 'spot' }" @click="market = 'spot'">Spot · long only</button><button type="button" :class="{ active: market === 'futures' }" @click="market = 'futures'">Futures · long & short</button></div>
      <div class="strategy-options"><button v-for="item in visible" :key="item.name" type="button" class="strategy-option" :class="{ chosen: selected.includes(item.name) }" @click="select(item.name)"><span class="selection-dot">{{ selected.includes(item.name) ? '✓' : '' }}</span><strong>{{ item.name }}</strong><span>{{ item.description }}</span><small>5m {{ item.informative.length ? '+ 1h context' : '' }} · {{ item.market }}</small></button></div>
    </section>
    <section class="card"><div class="step-heading"><span>02</span><div><h2>{{ trading ? 'Set your trading budget' : 'Set up the experiment' }}</h2><p>{{ trading ? 'The engine starts stopped. You control when it begins.' : 'Leave dates and pairs empty to use all available history and pairs.' }}</p></div></div>
      <div class="form-grid"><label>Exchange<select v-model="exchange"><option value="binance">Binance</option><option v-if="market === 'spot'" value="kucoin">KuCoin</option></select></label><label>Starting capital · USDT<input v-model.number="capital" type="number" min="1" step="any" required /></label><label>Maximum open positions<input v-model.number="positions" type="number" min="1" max="100" required /></label><label>Timeframe<input value="5 minutes" readonly /><small>Strategy default · automatic stake sizing</small></label><template v-if="!trading"><label>From <span class="optional">optional</span><input v-model="start" type="date" /></label><label>Until <span class="optional">exclusive</span><input v-model="end" type="date" /></label></template></div>
      <details class="advanced-details" :open="advanced"><summary>Advanced configuration</summary><label>Specific pairs <span class="optional">blank = all {{ wb.status.value?.datasets.find(d => d.exchange === exchange && d.market === market)?.pairs }} pairs</span><textarea v-model="pairs" :placeholder="market === 'spot' ? 'BTC/USDT, ETH/USDT' : 'BTC/USDT:USDT, ETH/USDT:USDT'" rows="2"></textarea></label><p>Commissions, funding, execution and protections are calculated by Freqtrade. Futures use the strategy's native leverage (1× unless overridden).</p>
        <template v-if="advanced"><div class="form-grid"><label>Research task<select v-model="kind"><option value="backtesting">Backtest</option><option value="hyperopt">Hyperopt</option><option value="lookahead-analysis">Lookahead analysis</option><option value="recursive-analysis">Recursive analysis</option></select></label><template v-if="kind === 'hyperopt'"><label>Epochs<input v-model.number="epochs" type="number" min="1" max="10000" /></label><label>Workers<input v-model.number="workers" type="number" min="1" max="8" /></label><label>Loss function<select v-model="loss"><option>SharpeHyperOptLossDaily</option><option>SortinoHyperOptLossDaily</option><option>CalmarHyperOptLoss</option><option>ProfitDrawDownHyperOptLoss</option></select></label><label>Parameter spaces<input v-model="spaces" /><small>buy sell roi stoploss trailing protection</small></label></template></div><label>FreqAI model <span class="optional">requires a compatible strategy</span><input v-model="model" placeholder="Optional model class" /></label><label v-if="model">FreqAI configuration JSON<textarea v-model="freqai" rows="6" placeholder="Full freqai configuration object"></textarea></label><p>The four bundled strategies do not implement FreqAI features. Connect a compatible external engine through Settings to use your own FreqAI strategies.</p></template>
      </details>
    </section>
    <section class="card run-card"><div><h2>{{ trading ? 'Ready when you are' : 'Your next insight starts here' }}</h2><p>{{ selected.length }} strategies · {{ exchange }} {{ market }} · {{ money(capital) }} USDT · {{ positions }} positions</p><p v-if="!trading">Full-history jobs run one at a time to keep memory usage predictable.</p></div><template v-if="trading"><label class="check-label"><input v-model="live" type="checkbox" /> Use real money</label><div v-if="live" class="message error"><strong>Live trading can lose real funds.</strong><label>Type ENABLE LIVE TRADING<input v-model="confirmation" autocomplete="off" placeholder="ENABLE LIVE TRADING" required /></label></div></template><button class="primary-button" type="submit" :disabled="wb.busy.value || !wb.status.value?.data_ready"><UIcon :name="trading ? 'mdi:power' : 'mdi:play'" />{{ wb.busy.value ? 'Working…' : trading ? live ? 'Connect live engine' : 'Connect simulation' : 'Run experiment' }}</button></section>
  </form>
</template>
