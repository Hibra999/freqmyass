<script setup lang="ts">
const route = useRoute();
const bots = useBotStore();
const wb = useWorkbench();
const interfaceMode = useInterfaceMode();
const settingsStore = useSettingsStore();
const menu = ref(false);
const links = [
  ['overview', 'Overview', 'mdi:view-dashboard-outline'],
  ['strategies', 'Strategies', 'mdi:flask-outline'],
  ['backtesting', 'Backtesting', 'mdi:play-circle-outline'],
  ['reports', 'Reports', 'mdi:chart-box-outline'],
  ['simulation', 'Monte Carlo', 'mdi:chart-bell-curve'],
  ['data', 'Market data', 'mdi:database-outline'],
  ['trading', 'Trading', 'mdi:swap-horizontal'],
  ['advanced', 'Advanced', 'mdi:tune-variant'],
  ['setup', 'Settings', 'mdi:cog-outline'],
];
const active = computed(() => String(route.query.view || 'overview'));
let poll: ReturnType<typeof setInterval>;
onMounted(async () => {
  document.title = 'FreqMyAss · Trading workspace';
  try {
    await wb.refresh();
  } catch (e) {
    wb.error.value = String(e);
  }
  poll = setInterval(() => {
    void wb.refresh().catch(() => {});
  }, 5000);
});
onBeforeUnmount(() => clearInterval(poll));
</script>
<template>
  <div class="workspace" :class="{ 'dark-workspace': settingsStore.isDarkTheme }">
    <aside class="sidebar" :class="{ 'is-open': menu }">
      <RouterLink to="/" class="brand"
        ><span class="brand-symbol">fm</span>
        <div>FreqMyAss<small>YOUR TRADING WORKSPACE</small></div></RouterLink
      >
      <div class="workspace-label">WORKSPACE <span>LOCAL</span></div>
      <nav aria-label="Main navigation">
        <RouterLink
          v-for="[key, label, icon] in links"
          :key="key"
          :to="{ path: '/', query: { view: key } }"
          :class="{ selected: route.path === '/' && active === key }"
          @click="menu = false"
          ><UIcon :name="icon" /><span>{{ label }}</span
          ><span v-if="key === 'strategies'" class="nav-count">4</span></RouterLink
        >
      </nav>
      <div class="sidebar-bottom">
        <button
          class="secondary-button"
          style="margin-bottom: 18px; width: 100%"
          @click="interfaceMode = 'native'"
        >
          <UIcon name="mdi:application-brackets-outline" /> Full FreqUI
        </button>
        <span class="status-dot"></span> Powered by Freqtrade<small
          >{{ wb.status.value?.app_version || 'development' }} · Freqtrade
          {{ wb.status.value?.engine_version || 'connecting' }} · Conda</small
        ><a href="https://github.com/Hibra999/freqmyass" target="_blank" rel="noreferrer"
          >Project & documentation ↗</a
        >
      </div>
    </aside>
    <div class="workspace-main">
      <header class="workspace-topbar">
        <button class="mobile-menu" aria-label="Toggle navigation" @click="menu = !menu">
          <UIcon name="mdi:menu" />
        </button>
        <div class="breadcrumb">
          Workspace <span>/</span>
          <strong>{{
            route.path === '/' ? links.find((l) => l[0] === active)?.[1] : 'Engine tools'
          }}</strong>
        </div>
        <div class="topbar-actions">
          <ThemeSelect />
          <span
            class="pill"
            :class="wb.status.value?.engines.trading?.mode === 'live' ? 'danger' : 'safe'"
            >{{
              wb.status.value?.engines.trading?.mode === 'live'
                ? 'LIVE TRADING'
                : 'SIMULATION FIRST'
            }}</span
          ><span class="local-label">Windows · Local</span>
        </div>
      </header>
      <main class="workspace-content">
        <div v-if="wb.error.value" class="message error" role="alert">
          {{ wb.error.value
          }}<button aria-label="Dismiss error" @click="wb.error.value = ''">×</button>
        </div>
        <div v-if="wb.notice.value" class="message success" role="status">
          {{ wb.notice.value
          }}<button aria-label="Dismiss notification" @click="wb.notice.value = ''">×</button>
        </div>
        <div v-if="route.path !== '/' && bots.hasBots" class="native-toolbar">
          <RouterLink to="/">← Workspace</RouterLink><BotSelect /><ReloadControl /><ThemeSelect />
        </div>
        <slot />
      </main>
    </div>
  </div>
</template>
