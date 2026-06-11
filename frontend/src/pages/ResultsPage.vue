<template>
  <div class="results-page">
    <div class="page-header">
      <h2 class="page-title">Results</h2>
      <div v-if="sessionId">
        <a :href="apiUrl(`/api/session/${sessionId}/download/results`)" download>
          <button class="btn btn-outline btn-sm">⬇ Download JSON</button>
        </a>
      </div>
    </div>

    <div v-if="!optimizerResults.length" class="empty-state">
      <div class="empty-icon">📊</div>
      <div class="empty-title">No results yet</div>
      <div class="empty-sub">Run an experiment from the Configure page to see results here.</div>
    </div>

    <div v-else>

      <!-- Summary cards -->
      <div class="summary-cards">
        <div class="stat-card" v-for="s in summaryStats" :key="s.label">
          <div class="stat-icon">{{ s.icon }}</div>
          <div class="stat-body">
            <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </div>
      </div>

      <!-- AUC Table -->
      <div class="card results-card">
        <div class="results-card-header">
          <span class="card-title">AUC + Time Summary</span>
          <span class="badge badge-muted">{{ optimizerResults.length }} results</span>
        </div>
        <table class="results-table">
          <thead>
            <tr>
              <th>Optimizer</th>
              <th class="right">AUC</th>
              <th class="right">Time (s)</th>
              <th>AUC Bar</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in sortedResults" :key="r.optimizer"
              :class="{ best: r.auc === maxAuc }">
              <td>
                <span v-if="r.auc === maxAuc" style="color:var(--vx-warning)">★ </span>
                <span class="mono">{{ r.optimizer }}</span>
              </td>
              <td class="right mono"
                :style="{ color: r.auc === maxAuc ? 'var(--vx-success)' : 'var(--vx-text)' }">
                {{ r.auc?.toFixed(6) }}
              </td>
              <td class="right mono" style="color:var(--vx-warning)">
                {{ r.time?.toFixed(2) }}
              </td>
              <td>
                <div class="auc-bar-wrap">
                  <div class="auc-bar-fill"
                    :style="{
                      width: `${(r.auc / maxAuc) * 100}%`,
                      background: r.auc === maxAuc ? 'var(--vx-success)' : 'var(--vx-primary)'
                    }"/>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Adam lr sensitivity -->
      <div v-if="adamGrid" class="card results-card">
        <div class="results-card-header">
          <span class="card-title">Adam lr Sensitivity</span>
          <span class="badge badge-primary">best lr = {{ adamGrid.best_lr }}</span>
        </div>
        <div class="lr-grid">
          <div v-for="(v, lr) in adamGrid.grid" :key="lr"
            class="lr-cell"
            :class="{
              'lr-best': parseFloat(lr) === adamGrid.best_lr,
              'lr-bad':  parseFloat(lr) === 100
            }">
            <div class="lr-label mono">lr = {{ lr }}</div>
            <div class="lr-auc mono">{{ parseFloat(v.auc).toFixed(4) }}</div>
            <div class="lr-time">{{ parseFloat(v.time).toFixed(1) }}s</div>
            <div v-if="parseFloat(lr) === adamGrid.best_lr" class="lr-star">★ best</div>
            <div v-if="parseFloat(lr) === 100" class="lr-bad-label">💥 catastrophic</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { apiUrl } from '../composables/useExperiment.js'

const props = defineProps({
  optimizerResults: Array,
  adamGrid: Object,
  sessionId: String,
})

const maxAuc = computed(() =>
  Math.max(...(props.optimizerResults?.map(r => r.auc) || [0])))

const sortedResults = computed(() =>
  [...(props.optimizerResults || [])].sort((a, b) => b.auc - a.auc))

const summaryStats = computed(() => {
  const best = sortedResults.value[0]
  const base = props.optimizerResults?.find(r => r.optimizer === 'L-BFGS-B')
  const gain = best && base ? (best.auc - base.auc).toFixed(4) : '—'
  return [
    { icon:'⭐', label:'Best AUC',       value: best?.auc?.toFixed(6) || '—', color:'var(--vx-success)' },
    { icon:'🔷', label:'Best Optimizer', value: best?.optimizer || '—',       color:'var(--vx-primary-light)' },
    { icon:'📈', label:'Δ vs L-BFGS-B', value: gain !== '—' ? `+${gain}` : '—', color:'var(--vx-warning)' },
    { icon:'⏱', label:'Best Time',      value: best ? `${best.time?.toFixed(1)}s` : '—', color:'var(--vx-info)' },
  ]
})
</script>

<style scoped>
.results-page { padding: 24px; height: 100%; overflow-y: auto; }
.page-header  { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-title   { font-size: 20px; font-weight: 700; }

.empty-state { text-align: center; padding: 80px 0; }
.empty-icon  { font-size: 40px; margin-bottom: 12px; }
.empty-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.empty-sub   { font-size: 13px; color: var(--vx-text-3); }

.summary-cards {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px,1fr));
  gap: 14px; margin-bottom: 20px;
}
.stat-card {
  background: var(--vx-bg-card); border: 1px solid var(--vx-border-soft);
  border-radius: var(--vx-radius-lg); padding: 16px;
  display: flex; align-items: center; gap: 12px;
}
.stat-icon  { font-size: 24px; }
.stat-value { font-size: 20px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.stat-label { font-size: 11px; color: var(--vx-text-3); margin-top: 2px; }

.results-card { margin-bottom: 16px; overflow: hidden; }
.results-card-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; border-bottom: 1px solid var(--vx-border-soft);
}
.card-title { font-size: 14px; font-weight: 600; }

.results-table { width: 100%; border-collapse: collapse; }
.results-table th {
  padding: 10px 18px; text-align: left; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .05em; color: var(--vx-text-3);
  border-bottom: 1px solid var(--vx-border-soft);
}
.results-table td { padding: 10px 18px; font-size: 13px; border-bottom: 1px solid rgba(67,73,104,.3); }
.results-table tr.best td { background: rgba(40,199,111,.05); }
.right { text-align: right; }

.auc-bar-wrap { height: 6px; border-radius: 3px; background: var(--vx-bg); min-width: 100px; overflow: hidden; }
.auc-bar-fill { height: 100%; border-radius: 3px; transition: width .5s ease; }

.lr-grid { display: flex; flex-wrap: wrap; gap: 10px; padding: 16px 18px; }
.lr-cell {
  min-width: 100px; padding: 12px 14px; border-radius: 8px;
  background: var(--vx-bg); border: 1px solid var(--vx-border-soft);
  text-align: center;
}
.lr-best { background: rgba(40,199,111,.08); border-color: var(--vx-success); }
.lr-bad  { background: rgba(234,84,85,.08);  border-color: var(--vx-danger); }
.lr-label { font-size: 10px; color: var(--vx-text-3); margin-bottom: 4px; }
.lr-auc   { font-size: 16px; font-weight: 700; color: var(--vx-text); }
.lr-time  { font-size: 10px; color: var(--vx-text-3); margin-top: 2px; }
.lr-star  { font-size: 10px; color: var(--vx-success); font-weight: 700; margin-top: 4px; }
.lr-bad-label { font-size: 10px; color: var(--vx-danger); margin-top: 4px; }
</style>
