<script setup lang="ts">
const mode = useInterfaceMode();
const wb = useWorkbench();
const bots = useBotStore();
const router = useRouter();
const route = useRoute();
let poll: ReturnType<typeof setInterval>;

async function connect(engine: 'research' | 'trading') {
  if (engine === 'trading' && !wb.status.value?.engines.trading?.running) {
    await guided('trading');
    return;
  }
  await wb.action(async () => {
    await wb.connect(engine);
    await router.push(engine === 'research' ? '/backtest' : '/trade');
  });
}

async function guided(view = 'overview') {
  mode.value = 'guided';
  await router.push({ path: '/', query: { view } });
}

onMounted(async () => {
  await wb.action(() => wb.refresh());
  poll = setInterval(() => void wb.refresh().catch(() => {}), 5000);
  if (bots.hasBots && route.path === '/') {
    await router.replace(bots.canRunBacktest ? '/backtest' : '/trade');
  }
});
onBeforeUnmount(() => clearInterval(poll));
</script>

<template>
  <div class="native-workspace flex min-h-0 flex-1 flex-col text-left bg-default text-default">
    <div
      class="flex flex-wrap items-center gap-2 border-b border-default px-3 py-2"
      aria-label="Workspace views"
    >
      <strong class="mr-auto">FreqMyAss · Full FreqUI</strong>
      <UBadge
        :color="wb.status.value?.engines.trading?.mode === 'live' ? 'error' : 'success'"
        variant="subtle"
      >
        {{
          wb.status.value?.engines.trading?.mode === 'live' ? 'LIVE TRADING' : 'SIMULATION FIRST'
        }}
      </UBadge>
      <UButton
        variant="soft"
        icon="mdi:flask-outline"
        :loading="wb.busy.value"
        @click="connect('research')"
        >Research engine</UButton
      >
      <UButton
        variant="soft"
        icon="mdi:swap-horizontal"
        :loading="wb.busy.value"
        @click="connect('trading')"
        >Trading engine</UButton
      >
      <UButton variant="outline" icon="mdi:chart-box-outline" @click="guided('reports')"
        >QuantStats reports</UButton
      >
      <UButton variant="outline" icon="mdi:chart-bell-curve" @click="guided('simulation')"
        >Monte Carlo</UButton
      >
      <UButton variant="outline" icon="mdi:view-dashboard-outline" @click="guided()"
        >Guided workspace</UButton
      >
    </div>
    <NavBar />
    <UAlert
      v-if="wb.error.value"
      color="error"
      :title="wb.error.value"
      class="m-3"
      close
      @update:open="wb.error.value = ''"
    />
    <main class="min-h-0 min-w-0 flex-1 overflow-auto">
      <div v-if="route.path === '/'" class="mx-auto max-w-2xl p-6">
        <h1 class="mb-3 text-2xl font-semibold">Your complete FreqUI workspace</h1>
        <p class="mb-5 text-muted">
          Choose Research engine for native backtesting, charts, data downloads and strategy
          analysis. Choose Trading engine for trades, balances and the portfolio dashboard.
        </p>
        <p class="text-muted">
          Configure a new trading engine in the guided workspace; it opens in stopped simulation.
          Connecting controls does not start entries. Your guided workflows and QuantStats reports
          remain one click away.
        </p>
      </div>
      <slot v-else />
    </main>
    <NavFooter />
  </div>
</template>
