<template>
  <div class="configure-page">
    <div class="page-header">
      <h2 class="page-title">Configure Experiment</h2>
      <p class="page-sub">Set up your dataset and optimizer parameters</p>
    </div>

    <div class="config-grid">

      <!-- Dataset card -->
      <div class="card config-card">
        <div class="card-header">
          <span class="card-icon">📦</span>
          <div>
            <div class="card-title">Dataset</div>
            <div class="card-sub">Select built-in or upload CSV</div>
          </div>
        </div>
        <div class="card-body">

          <!-- Mode toggle -->
          <div class="toggle-row">
            <button v-for="m in ['builtin','upload']" :key="m"
              class="toggle-btn" :class="{ active: dataMode === m }"
              @click="dataMode = m">
              {{ m === 'builtin' ? '📦 Built-in' : '📁 Upload CSV' }}
            </button>
          </div>

          <!-- Built-in grouped selector -->
          <div v-if="dataMode === 'builtin'">
            <label class="field-label">Dataset</label>
            <select class="vx-input" v-model="modelCfg.dataset_source"
              @change="onDatasetChange">
              <optgroup v-for="group in datasetGroups" :key="group.label"
                :label="group.label">
                <option v-for="d in group.items" :key="d.id" :value="d.id">
                  {{ d.label }}
                </option>
              </optgroup>
            </select>

            <!-- Dataset info card -->
            <div v-if="selectedDatasetInfo" class="dataset-info-card">
              <div class="di-name">{{ selectedDatasetInfo.name }}</div>
              <div class="di-stats">
                <span class="di-badge">N = {{ selectedDatasetInfo.N?.toLocaleString() }}</span>
                <span class="di-badge">{{ selectedDatasetInfo.features }} features</span>
                <span class="di-badge">{{ selectedDatasetInfo.n_classes }} classes</span>
                <span v-if="selectedDatasetInfo.pca_applied" class="di-badge pca">
                  PCA → {{ selectedDatasetInfo.features }}
                </span>
              </div>
              <div v-if="selectedDatasetInfo.class_names?.length <= 10"
                class="di-classes">
                <span v-for="c in selectedDatasetInfo.class_names" :key="c"
                  class="di-class-chip">{{ c }}</span>
              </div>
            </div>
          </div>

          <!-- Upload CSV -->
          <div v-else class="upload-section">
            <div class="upload-zone"
              :class="{ dragging: isDragging }"
              @dragover.prevent="isDragging = true"
              @dragleave="isDragging = false"
              @drop.prevent="handleDrop"
              @click="$refs.fileInput.click()">
              <div v-if="uploadedFile" class="upload-done">
                <span style="font-size:20px">✅</span>
                <span class="mono" style="font-size:12px">{{ uploadedFile }}</span>
              </div>
              <div v-else class="upload-prompt">
                <span style="font-size:24px">📄</span>
                <span>Drop CSV here or click to browse</span>
              </div>
              <input ref="fileInput" type="file" accept=".csv"
                @change="handleFile" style="display:none"/>
            </div>
            <div class="field-row">
              <div>
                <label class="field-label">Label column</label>
                <input class="vx-input" v-model="modelCfg.label_column"
                  placeholder="last column if blank"/>
              </div>
              <div>
                <label class="field-label">PCA components</label>
                <input class="vx-input mono" type="number"
                  v-model="modelCfg.pca_components"
                  placeholder="e.g. 50 (blank = none)"/>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- Optimizers card -->
      <div class="card config-card">
        <div class="card-header">
          <span class="card-icon">🔧</span>
          <div>
            <div class="card-title">Optimizers</div>
            <div class="card-sub">Select which to run</div>
          </div>
        </div>
        <div class="card-body">
          <div class="opt-list">
            <label v-for="opt in OPTIMIZERS" :key="opt.id" class="opt-row">
              <div class="opt-check">
                <input type="checkbox" :value="opt.id"
                  v-model="modelCfg.optimizers"/>
                <span class="checkmark"/>
              </div>
              <span class="opt-icon">{{ opt.icon }}</span>
              <div class="opt-info">
                <div class="opt-name">{{ opt.name }}</div>
                <div class="opt-desc">{{ opt.desc }}</div>
              </div>
              <span class="badge" :class="opt.badge">{{ opt.type }}</span>
            </label>
          </div>
        </div>
      </div>

      <!-- Parameters card -->
      <div class="card config-card">
        <div class="card-header">
          <span class="card-icon">⚙</span>
          <div>
            <div class="card-title">Parameters</div>
            <div class="card-sub">Optimizer hyperparameters</div>
          </div>
        </div>
        <div class="card-body">
          <div class="param-grid">
            <div v-for="p in PARAMS" :key="p.key">
              <label class="field-label">{{ p.label }}</label>
              <div class="param-row">
                <input class="vx-input mono" :type="p.type" :step="p.step"
                  v-model.number="modelCfg[p.key]"
                  :placeholder="p.placeholder"/>
                <span class="param-hint">{{ p.hint }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Adam lr grid card -->
      <div class="card config-card">
        <div class="card-header">
          <span class="card-icon">⭐</span>
          <div>
            <div class="card-title">Adam lr Grid</div>
            <div class="card-sub">Learning rates to test</div>
          </div>
        </div>
        <div class="card-body">
          <label class="field-label">lr values (comma-separated)</label>
          <input class="vx-input mono"
            :value="modelCfg.adam_lr_list.join(', ')"
            @change="e => modelCfg.adam_lr_list =
              e.target.value.split(',').map(Number).filter(n => !isNaN(n))"/>
          <div class="lr-chips">
            <span v-for="lr in modelCfg.adam_lr_list" :key="lr"
              class="badge mono"
              :class="lr === 100 ? 'badge-danger' :
                      lr === 1.0 ? 'badge-success' : 'badge-muted'">
              {{ lr }}
            </span>
          </div>
          <div class="hint-box">
            <span style="color:var(--vx-danger)">lr=100</span> always catastrophic ·
            <span style="color:var(--vx-success)">lr=1.0</span> optimal (20/21 datasets)
          </div>
        </div>
      </div>

    </div>

    <!-- Run button -->
    <div class="run-row">
      <button class="btn btn-primary run-btn"
        :disabled="running"
        @click="$emit('run', modelCfg)">
        {{ running ? '⏳ Running…' : '▶ Run Experiment' }}
      </button>
      <button v-if="running" class="btn btn-ghost"
        @click="$emit('stop')">⏹ Stop</button>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'

const props = defineProps({ running: Boolean, onUpload: Function })
defineEmits(['run', 'stop'])

const dataMode     = ref('builtin')
const uploadedFile = ref(null)
const isDragging   = ref(false)
const allDatasets  = ref([])
const selectedDatasetInfo = ref(null)

const modelCfg = reactive({
  dataset_source: 'anuran_calls',
  label_column: null, pca_components: null,
  optimizers: ['L-BFGS-B', 'SGD', 'Momentum', 'Adam'],
  adam_lr_list: [100.0, 10.0, 1.0, 0.1, 0.01, 0.001],
  n_iter: 200, lr: 100.0, momentum: 0.5,
  beta1: 0.9, beta2: 0.999, seed: 40, init: 'pca',
})

// ── Load dataset list from backend ────────────────────────────────────────────
onMounted(async () => {
  try {
    const base = import.meta.env.VITE_API_URL || ''
    const r = await fetch(`${base}/api/datasets`)
    allDatasets.value = await r.json()
  } catch(e) {
    // fallback static list if API unreachable
    allDatasets.value = [
      
      { id:'anuran_calls', label:'Anuran Calls (7,195 × 22)', group:'Biological' },
      { id:'ccpp',         label:'CCPP Power Plant (9,568 × 4)', group:'Engineering' },
      { id:'musk_v2',      label:'Musk v2 (6,598 × 166)', group:'Chemical' },
      { id:'spambase',     label:'Spambase (4,601 × 57)', group:'Text' },
      { id:'gesture',      label:'Gesture Phase (9,873 × 32)', group:'Motion' },
      { id:'mnist',        label:'MNIST (5,000 × 784)', group:'Image' },
      { id:'satellite',    label:'Landsat Satellite (6,435 × 36)', group:'Remote Sensing' },
      { id:'theorem',      label:'Theorem Proving (6,118 × 56)', group:'Logic' },
      { id:'waveform',     label:'Waveform (5,000 × 21)', group:'Signal' },
      { id:'isolet',       label:'ISOLET (7,797 × 617→50)', group:'Speech' },
    ]
  }
})

watch(dataMode, v => {
  if (v === 'builtin') modelCfg.dataset_source = allDatasets.value[0]?.id || 'anuran_calls'
  else modelCfg.dataset_source = 'upload'
})

// ── Group datasets by group field ─────────────────────────────────────────────
const datasetGroups = computed(() => {
  const groups = {}
  allDatasets.value.forEach(d => {
    if (!groups[d.group]) groups[d.group] = { label: d.group, items: [] }
    groups[d.group].items.push(d)
  })
  return Object.values(groups)
})

// ── Fetch dataset info when selection changes ─────────────────────────────────
async function onDatasetChange() {
  if (!modelCfg.dataset_source || modelCfg.dataset_source === 'upload') {
    selectedDatasetInfo.value = null
    return
  }
  try {
    const base = import.meta.env.VITE_API_URL || ''
    const r = await fetch(`${base}/api/datasets/${modelCfg.dataset_source}/info`)
    if (r.ok) selectedDatasetInfo.value = await r.json()
  } catch(e) {
    selectedDatasetInfo.value = null
  }
}

async function handleFile(e) {
  const file = e.target.files[0]; if (!file) return
  uploadedFile.value = file.name
  props.onUpload?.(file)
}

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]; if (!file) return
  uploadedFile.value = file.name
  props.onUpload?.(file)
}

const OPTIMIZERS = [
  { id:'L-BFGS-B',  name:'L-BFGS-B',  icon:'🔷', type:'Quasi-Newton',
    badge:'badge-info',    desc:'Baseline. Limited-memory BFGS.' },
  { id:'SGD',       name:'SGD',        icon:'🔹', type:'First-order',
    badge:'badge-muted',   desc:'Vanilla gradient descent.' },
  { id:'Momentum',  name:'Momentum',   icon:'🔸', type:'First-order',
    badge:'badge-muted',   desc:'Heavy-ball momentum.' },
  { id:'Adam',      name:'Adam',       icon:'⭐', type:'Adaptive',
    badge:'badge-primary', desc:'Best on 21/21 datasets (lr=1.0).' },
]

const PARAMS = [
  { key:'n_iter',   label:'Iterations',    type:'number', step:10,
    hint:'default 200',   placeholder:'200' },
  { key:'lr',       label:'LR (SGD/Mom)', type:'number', step:0.1,
    hint:'default 100',   placeholder:'100' },
  { key:'momentum', label:'Momentum μ',   type:'number', step:0.1,
    hint:'default 0.5',   placeholder:'0.5' },
  { key:'beta1',    label:'Adam β₁',      type:'number', step:0.01,
    hint:'default 0.9',   placeholder:'0.9' },
  { key:'beta2',    label:'Adam β₂',      type:'number', step:0.001,
    hint:'default 0.999', placeholder:'0.999' },
  { key:'seed',     label:'Random seed',  type:'number', step:1,
    hint:'PCA+seed 40',   placeholder:'40' },
]
</script>

<style scoped>
.configure-page { padding: 24px; height: 100%; overflow-y: auto; }
.page-header    { margin-bottom: 24px; }
.page-title     { font-size: 20px; font-weight: 700; }
.page-sub       { font-size: 13px; color: var(--vx-text2); margin-top: 4px; }

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px; margin-bottom: 24px;
}
.config-card { overflow: hidden; }
.card-header {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 18px 0;
}
.card-icon  { font-size: 20px; }
.card-title { font-size: 14px; font-weight: 600; }
.card-sub   { font-size: 11px; color: var(--vx-text3); margin-top: 1px; }
.card-body  { padding: 14px 18px 16px; }

.toggle-row { display: flex; gap: 6px; margin-bottom: 12px; }
.toggle-btn {
  padding: 5px 14px; border-radius: 6px; font-size: 12px; font-weight: 500;
  cursor: pointer; border: 1px solid var(--vx-border);
  background: transparent; color: var(--vx-text2); font-family: inherit;
  transition: all .15s;
}
.toggle-btn.active {
  background: var(--vx-primary-dim); color: var(--vx-primary-l);
  border-color: var(--vx-primary);
}

/* Dataset info card */
.dataset-info-card {
  margin-top: 10px; padding: 10px 12px;
  background: var(--vx-bg); border: 1px solid var(--vx-border-soft);
  border-radius: 8px;
}
.di-name  { font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.di-stats { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 6px; }
.di-badge {
  font-size: 10px; padding: 2px 7px; border-radius: 4px;
  background: var(--vx-primary-dim); color: var(--vx-primary-l);
  font-family: 'IBM Plex Mono', monospace;
}
.di-badge.pca { background: var(--vx-warning-dim); color: var(--vx-warning); }
.di-classes   { display: flex; gap: 4px; flex-wrap: wrap; }
.di-class-chip {
  font-size: 10px; padding: 1px 6px; border-radius: 3px;
  background: var(--vx-bg-input); color: var(--vx-text2);
  border: 1px solid var(--vx-border-soft);
}

/* Upload zone */
.upload-zone {
  border: 2px dashed var(--vx-border); border-radius: 10px;
  padding: 20px; text-align: center; cursor: pointer;
  transition: all .15s; margin-bottom: 12px;
}
.upload-zone.dragging {
  border-color: var(--vx-primary); background: var(--vx-primary-dim);
}
.upload-zone:hover { border-color: var(--vx-primary); }
.upload-prompt {
  display: flex; flex-direction: column; gap: 6px;
  align-items: center; font-size: 12px; color: var(--vx-text2);
}
.upload-done {
  display: flex; flex-direction: column; gap: 6px; align-items: center;
}
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

/* Optimizers */
.opt-list { display: flex; flex-direction: column; gap: 6px; }
.opt-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px; background: var(--vx-bg);
  border: 1px solid var(--vx-border-soft); cursor: pointer;
  transition: border-color .15s;
}
.opt-row:hover { border-color: var(--vx-primary); }
.opt-check { position: relative; }
.opt-check input { opacity: 0; position: absolute; width: 16px; height: 16px; }
.checkmark {
  display: block; width: 16px; height: 16px; border-radius: 4px;
  border: 2px solid var(--vx-border); background: var(--vx-bg-input);
  transition: all .15s; position: relative;
}
.opt-check input:checked ~ .checkmark {
  background: var(--vx-primary); border-color: var(--vx-primary);
}
.opt-check input:checked ~ .checkmark::after {
  content: '✓'; position: absolute; top: -2px; left: 2px;
  font-size: 11px; color: #fff; font-weight: 700;
}
.opt-icon { font-size: 16px; }
.opt-info { flex: 1; }
.opt-name { font-size: 13px; font-weight: 600; }
.opt-desc { font-size: 11px; color: var(--vx-text3); margin-top: 1px; }

/* Params */
.param-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.param-row  { display: flex; align-items: center; gap: 6px; }
.param-hint { font-size: 10px; color: var(--vx-text3); white-space: nowrap; }

/* lr chips */
.lr-chips { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px; }
.hint-box { margin-top: 10px; font-size: 11px; color: var(--vx-text3); line-height: 1.6; }

/* Run */
.run-row { display: flex; gap: 10px; align-items: center; }
.run-btn  { padding: 10px 28px; font-size: 14px; }
</style>
