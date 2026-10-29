<script setup lang="ts">
const wb = useWorkbench();
const log = ref('');
const opened = ref('');
const page = ref(0);
async function view(id: string) {
  await wb.action(async () => {
    opened.value = id;
    log.value = (await workbenchApi<{ text: string }>(`/jobs/${id}/log`)).text;
  });
}
</script>
<template>
  <section class="card job-queue">
    <div class="section-title">
      <div>
        <h2>Research activity</h2>
        <p>Every run has a configuration, log and outcome.</p>
      </div>
      <span class="pill">{{ wb.status.value?.jobs.length || 0 }} runs</span>
    </div>
    <div v-if="!wb.status.value?.jobs.length" class="empty-inline">
      <UIcon name="mdi:play-box-outline" />
      <p>Your first experiment will appear here.</p>
    </div>
    <div
      v-for="job in wb.status.value?.jobs.slice(page * 12, (page + 1) * 12)"
      :key="job.id"
      class="job-row"
    >
      <div class="job-icon">
        <UIcon
          :name="
            job.status === 'completed'
              ? 'mdi:check'
              : job.status === 'failed'
                ? 'mdi:alert-outline'
                : 'mdi:clock-outline'
          "
        />
      </div>
      <div class="job-description">
        <strong>{{ job.payload.strategies?.join(' + ') || 'Dataset inventory' }}</strong
        ><small>{{ job.kind }} · {{ new Date(job.created).toLocaleString('en-US') }}</small>
        <p>{{ job.message }}</p>
      </div>
      <span
        class="pill"
        :class="job.status === 'completed' ? 'safe' : job.status === 'failed' ? 'danger' : ''"
        >{{ job.status }}</span
      ><button class="text-button" @click="view(job.id)">Log</button
      ><button
        v-if="['queued', 'running'].includes(job.status)"
        class="text-button"
        @click="wb.action(() => workbenchApi(`/jobs/${job.id}/cancel`, {}))"
      >
        Cancel
      </button>
    </div>
    <div v-if="(wb.status.value?.jobs.length || 0) > 12" class="button-row">
      <button class="secondary-button" :disabled="page === 0" @click="page--">Previous</button>
      <span>Page {{ page + 1 }}</span>
      <button
        class="secondary-button"
        :disabled="(page + 1) * 12 >= (wb.status.value?.jobs.length || 0)"
        @click="page++"
      >
        Next
      </button>
    </div>
    <details v-if="opened" open class="log-panel">
      <summary>
        Job output <button class="text-button" @click.prevent="view(opened)">Refresh</button>
      </summary>
      <pre>{{ log }}</pre>
    </details>
  </section>
</template>
