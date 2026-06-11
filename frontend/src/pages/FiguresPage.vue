<template>
  <div class="figures-page">
    <div class="page-header">
      <h2 class="page-title">Figures</h2>
      <p class="page-sub">Embedding visualisations and quality curves</p>
    </div>

    <div v-if="!Object.keys(figures).length" class="empty-state">
      <div class="empty-icon">🖼</div>
      <div class="empty-title">No figures yet</div>
      <div class="empty-sub">Figures appear here after the experiment completes.</div>
    </div>

    <div v-else>
      <!-- Embedding plots grid -->
      <div class="section-label">Embedding Plots</div>
      <div class="figs-grid">
        <template v-for="(label, key) in embeddingFigs" :key="key">
          <div v-if="figures[key]" class="card fig-card">
            <div class="fig-header">{{ label }}</div>
            <img :src="figures[key]" :alt="label" class="fig-img"
              @click="openLightbox(figures[key], label)"/>
            <div class="fig-footer">
              <a :href="figures[key]" :download="`${key}.png`">
                <button class="btn btn-ghost btn-sm">⬇ DOWNLOAD</button>
              </a>
            </div>
          </div>
        </template>
      </div>

      <!-- Full width charts -->
      <div class="section-label" style="margin-top:20px">Quality Curves & Summary</div>
      <div class="figs-wide">
        <template v-for="(label, key) in wideFigs" :key="key">
          <div v-if="figures[key]" class="card fig-card-wide">
            <div class="fig-header">{{ label }}</div>
            <img :src="figures[key]" :alt="label" class="fig-img"
              @click="openLightbox(figures[key], label)"/>
            <div class="fig-footer">
              <a :href="figures[key]" :download="`${key}.png`">
                <button class="btn btn-ghost btn-sm">⬇ PNG</button>
              </a>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Lightbox -->
    <div v-if="lightbox" class="lightbox" @click="lightbox = null">
      <div class="lightbox-inner" @click.stop>
        <div class="lightbox-header">
          <span>{{ lightboxLabel }}</span>
          <button class="close-btn" @click="lightbox = null">✕</button>
        </div>
        <img :src="lightbox" class="lightbox-img"/>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed,watch } from 'vue'

const props = defineProps({ figures: Object })

const lightbox      = ref(null)
const lightboxLabel = ref('')

function openLightbox(src, label) { lightbox.value = src; lightboxLabel.value = label }

const embeddingFigs = {
  'embedding_LBFGSB':    'L-BFGS-B Embedding',
  'embedding_SGD':       'SGD Embedding',
  'embedding_Momentum':  'Momentum Embedding',
  'embedding_Adam_best': 'Adam Best Embedding',
}

const wideFigs = {
  rnx_curves:  'R_NX Quality Curves',
  auc_summary: 'AUC Summary + Adam lr Sensitivity',
}

watch(() => props.figures, (val) => {
  console.log('FIGURES PROP:', JSON.stringify(Object.keys(val)))
}, { deep: true })

</script>

<style scoped>
.figures-page { padding: 24px; height: 100%; overflow-y: auto; }
.page-header  { margin-bottom: 24px; }
.page-title   { font-size: 20px; font-weight: 700; }
.page-sub     { font-size: 13px; color: var(--vx-text-2); margin-top: 4px; }

.empty-state { text-align: center; padding: 80px 0; }
.empty-icon  { font-size: 40px; margin-bottom: 12px; }
.empty-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.empty-sub   { font-size: 13px; color: var(--vx-text-3); }

.section-label {
  font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: var(--vx-text-3); margin-bottom: 12px;
}

.figs-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px,1fr)); gap: 14px;
}
.figs-wide { display: flex; flex-direction: column; gap: 14px; }

.fig-card, .fig-card-wide { overflow: hidden; }
.fig-header {
  padding: 10px 14px; font-size: 12px; font-weight: 600;
  border-bottom: 1px solid var(--vx-border-soft);
}
.fig-img {
  width: 100%; display: block; cursor: zoom-in;
  transition: opacity .15s;
}
.fig-img:hover { opacity: .9; }
.fig-footer { padding: 8px 12px; border-top: 1px solid var(--vx-border-soft); }

/* Lightbox */
.lightbox {
  position: fixed; inset: 0; background: rgba(0,0,0,.85);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; cursor: zoom-out;
}
.lightbox-inner {
  background: var(--vx-bg-card); border-radius: 12px;
  max-width: 90vw; max-height: 90vh; overflow: hidden;
  cursor: default;
}
.lightbox-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; font-size: 13px; font-weight: 600;
  border-bottom: 1px solid var(--vx-border-soft);
}
.lightbox-img { max-width: 85vw; max-height: 80vh; display: block; }
.close-btn {
  background: none; border: none; cursor: pointer;
  color: var(--vx-text-3); font-size: 14px; padding: 4px;
}
.close-btn:hover { color: var(--vx-danger); }
</style>
