<script setup lang="ts">
const wb = useWorkbench();
const bots = useBotStore();
const bot = computed(() => bots.activeBot);
const ready = computed(
  () => bot.value && !bot.value.isWebserverMode && bot.value.botStatusAvailable,
);
onMounted(() => {
  void wb.action(() => wb.connect('trading'));
});
</script>
<template>
  <template v-if="ready">
    <div class="metric-grid">
      <section class="card metric">
        <div class="metric-label">Bot state</div>
        <div class="metric-value" style="font-size: 23px">{{ bot.botState.state }}</div>
        <div class="metric-foot">
          {{ bot.botState.dry_run ? 'Simulated funds' : 'Real funds' }} ·
          {{ bot.botState.strategy }}
        </div>
      </section>
      <section class="card metric">
        <div class="metric-label">Wallet value</div>
        <div class="metric-value">
          {{ money(bot.balance.total || 0) }}<small>{{ bot.stakeCurrency }}</small>
        </div>
      </section>
      <section class="card metric">
        <div class="metric-label">Portfolio profit</div>
        <div
          class="metric-value"
          :class="(bot.profit?.profit_all_coin || 0) >= 0 ? 'positive' : 'negative'"
        >
          {{ money(bot.profit?.profit_all_coin || 0) }}
        </div>
        <div class="metric-foot">
          {{ percent(bot.profit?.profit_all_ratio) }} · native Freqtrade accounting
        </div>
      </section>
      <section class="card metric">
        <div class="metric-label">Open positions</div>
        <div class="metric-value">
          {{ bot.openTradeCount }}<small>/ {{ bot.botState.max_open_trades }}</small>
        </div>
      </section>
    </div>
    <section class="card">
      <div class="section-title">
        <div>
          <h2>You are in control.</h2>
          <p>
            Pause entries keeps managing existing trades. Stop bot stops all processing, including
            exits.
          </p>
        </div>
        <span class="pill" :class="bot.botState.dry_run ? 'safe' : 'danger'">{{
          bot.botState.dry_run ? 'SIMULATION' : 'LIVE TRADING'
        }}</span>
      </div>
      <BotControls />
    </section>
    <section class="card">
      <TradeList
        :trades="bot.openTrades"
        title="Open positions"
        :stake-currency="bot.stakeCurrency"
        active-trades
        empty-text="No open positions. Start the bot when you are ready."
      />
    </section>
    <section class="card">
      <TradeList
        :trades="bot.trades"
        title="Recent trades"
        :stake-currency="bot.stakeCurrency"
        show-filter
        empty-text="Completed trades will appear here."
      />
    </section>
  </template>
  <section v-else class="card">
    <h2>Connecting your trading desk…</h2>
    <p>If the connection fails, inspect the engine log in Settings.</p>
  </section>
</template>
