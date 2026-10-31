<script setup lang="ts">
import './styles/workbench.css';
const settingsStore = useSettingsStore();
const colorStore = useColorStore();
const interfaceMode = useInterfaceMode();
// An explicit guided-page URL takes precedence over the saved workspace preference.
if (new URLSearchParams(location.search).has('view')) interfaceMode.value = 'guided';
if (!localStorage.getItem('freqmyass-dark-default')) {
  settingsStore.currentTheme = 'dark';
  localStorage.setItem('freqmyass-dark-default', '1');
}
watch(
  () => settingsStore.isDarkTheme,
  (dark) => document.documentElement.classList.toggle('dark', dark),
  { immediate: true },
);
onMounted(() => {
  setTimezone(settingsStore.timezone);
  colorStore.updateProfitLossColor();
});
watch(
  () => settingsStore.timezone,
  (tz) => {
    console.log('timezone changed', tz);
    setTimezone(tz);
  },
);
</script>

<template>
  <UApp>
    <div id="app" class="flex flex-col h-dvh" :style="colorStore.cssVars">
      <NativeWorkspace v-if="interfaceMode === 'native'"><RouterView /></NativeWorkspace>
      <WorkspaceShell v-else><RouterView /></WorkspaceShell>
    </div>
  </UApp>
</template>

<style scoped>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
}

/* * {
  outline: 1px solid #f00 !important;
} */
</style>
