<template>
  <transition name="panel-slide">
    <div v-if="node" class="node-panel">

      <!-- Header -->
      <div class="panel-header">
        <div class="panel-title-row">
          <span class="node-icon-lg">{{ node.icon }}</span>
          <div>
            <div class="panel-title">{{ node.label }}</div>
            <div class="panel-sub mono">Section §{{ node.section }}</div>
          </div>
          <div class="panel-status" :class="`status-${state.status}`">
            {{ state.status }}
          </div>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>

        <!-- Tab bar -->
        <div class="tab-bar">
          <button v-for="t in availableTabs" :key="t"
            class="tab" :class="{ active: activeTab === t }"
            @click="activeTab = t">
            {{ t }}
          </button>
        </div>
      </div>

      <!-- Tab content -->
      <div class="panel-body">

        <!-- LOGS tab -->
        <div v-if="activeTab === 'Logs'" class="log-container">
          <div v-if="state.logs.length === 0" class="empty-state">
            No logs yet — run the experiment to see output here.
          </div>
          <div v-for="(msg, i) in state.logs" :key="i"
               class="log-line mono" :style="{ color: logColor(msg) }">
            {{ msg }}
          </div>
          <div ref="logEnd"/>
        </div>

        <!-- CODE tab -->
        <div v-if="activeTab === 'Code'" class="code-container">
          <div class="code-toolbar">
            <span class="badge badge-muted mono">Python</span>
            <button class="btn btn-ghost btn-sm" @click="copyCode">
              {{ copied ? '✓ Copied' : '⎘ Copy' }}
            </button>
          </div>
          <textarea class="code-editor mono" v-model="editableCode"/>
          <button class="btn btn-primary btn-sm run-btn"
            :disabled="runningSnippet" @click="runSnippet">
            {{ runningSnippet ? '⏳ Running…' : '▶ Run this code' }}
          </button>
          <div v-if="runOutput" class="run-output mono">{{ runOutput }}</div>
          <div v-if="runError"  class="run-error  mono">{{ runError  }}</div>
        </div>

        <!-- FORMULA tab -->
        <div v-if="activeTab === 'Formula'" class="formula-container">
          <div v-if="!formulaData" class="empty-state">No formulas for this section.</div>
          <div v-else>
            <div class="formula-title">{{ formulaData.title }}</div>
            <div v-for="(item, i) in formulaData.items" :key="i" class="formula-item">
              <div class="formula-name">{{ item.name }}</div>
              <pre class="formula-eq mono">{{ item.formula }}</pre>
              <div class="formula-desc">{{ item.desc }}</div>
            </div>
          </div>
        </div>

        <!-- RESULT tab -->
        <div v-if="activeTab === 'Result'" class="result-container">
          <div v-if="!state.result" class="empty-state">No result yet.</div>
          <div v-else class="result-grid">
            <div class="result-card">
              <div class="result-label">AUC</div>
              <div class="result-value success">{{ state.result.auc?.toFixed(6) }}</div>
            </div>
            <div class="result-card">
              <div class="result-label">Time</div>
              <div class="result-value warning">{{ state.result.time?.toFixed(2) }}s</div>
            </div>
            <div class="result-card full">
              <div class="result-label">Optimizer</div>
              <div class="result-value mono">{{ state.result.optimizer }}</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  node: Object,
  state: Object,
  sessionId: String,
})
defineEmits(['close'])

const activeTab     = ref('Logs')
const logEnd        = ref(null)
const copied        = ref(false)
const editableCode  = ref('')
const runningSnippet = ref(false)
const runOutput     = ref('')
const runError      = ref('')

const availableTabs = computed(() => {
  const tabs = ['Logs']
  if (CODE_SNIPPETS[props.node?.section]) tabs.push('Code')
  if (FORMULAS[props.node?.section]) tabs.push('Formula')
  if (props.state?.result) tabs.push('Result')
  return tabs
})

watch(() => props.node?.section, () => {
  activeTab.value = 'Logs'
  editableCode.value = CODE_SNIPPETS[props.node?.section] || ''
  runOutput.value = ''
  runError.value  = ''
})

watch(() => props.state?.logs?.length, async () => {
  await nextTick()
  logEnd.value?.scrollIntoView({ behavior: 'smooth' })
})

const codeSnippet = computed(() => CODE_SNIPPETS[props.node?.section] || '')
const formulaData = computed(() => FORMULAS[props.node?.section] || null)

// initialise editableCode when node changes — no circular watch
watch(() => props.node?.section, () => {
  editableCode.value = CODE_SNIPPETS[props.node?.section] || ''
  runOutput.value = ''
  runError.value  = ''
}, { immediate: true })

async function copyCode() {
  await navigator.clipboard.writeText(editableCode.value)
  copied.value = true
  setTimeout(() => copied.value = false, 1800)
}

async function runSnippet() {
  runningSnippet.value = true
  runOutput.value = ''
  runError.value  = ''
  try {
    const base = import.meta.env.VITE_API_URL || ''
    const r = await fetch(`${base}/api/session/${props.sessionId}/run-snippet`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editableCode.value, section: props.node.section })
    })
    const d = await r.json()
    if (d.error)  runError.value  = d.error
    else          runOutput.value = d.output
  } catch(e) { runError.value = e.message }
  finally { runningSnippet.value = false }
}

function logColor(msg) {
  if (msg.includes('AUC=') || msg.includes('✓')) return 'var(--vx-success)'
  if (msg.includes('Error') || msg.includes('error')) return 'var(--vx-danger)'
  if (msg.includes('===')) return 'var(--vx-primary-light)'
  if (msg.includes('lr=') || msg.includes('Time=')) return 'var(--vx-warning)'
  return 'var(--vx-text-2)'
}

// ── Exact code from musk_v2_optimizer_gpu.ipynb ───────────────────────────────
const CODE_SNIPPETS = {
  1: `import os, sys
print("="*55)
print("GPU VERIFICATION")
print("="*55)
print(f"Python          : {sys.version[:30]}")
print(f"CUDA_PATH       : {os.environ.get('CUDA_PATH', 'NOT SET')}")
print(f"LD_LIBRARY_PATH : {os.environ.get('LD_LIBRARY_PATH','NOT SET')[:60]}...")
try:
    import cupy as cp
    props = cp.cuda.runtime.getDeviceProperties(0)
    print(f"CuPy version    : {cp.__version__}")
    print(f"GPU             : {props['name'].decode()}")
    free, total = cp.cuda.runtime.memGetInfo()
    print(f"VRAM free       : {free/1e9:.2f} GB / {total/1e9:.2f} GB")
    print("STATUS          : GPU ACTIVE ✓")
except Exception as e:
    print(f"STATUS          : GPU NOT ACTIVE ✗  ({e})")
print("="*55)`,

  3: `import numpy as np
import numba
import scipy.spatial.distance
import scipy.optimize
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import sklearn.decomposition
import pandas as pd
import time, os, logging, json, subprocess
from datetime import datetime

# ── Ms t-SNE constants ────────────────────────────────────────────────────────
seed_MstSNE_def  = 40
dr_nitmax        = 30
dr_gtol          = 10**(-5)
dr_ftol          = 2.2204460492503131e-09
dr_maxls         = 30
dr_maxcor        = 6
n_eps_np_float64 = np.finfo(dtype=np.float64).eps

# ── Run settings ──────────────────────────────────────────────────────────────
SEED         = 40
INIT         = 'pca'
N_ITER       = 200
LR           = 100.0
MU           = 0.5
ADAM_LR_LIST = [100.0, 10.0, 1.0, 0.1, 0.01, 0.001]

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
print(f"Imports done.")
print(f"Timestamp : {timestamp}")`,

  5: `@numba.jit(nopython=True)
def close_to_zero(v):
    return np.absolute(v) <= 10.0**(-8.0)

@numba.jit(nopython=True)
def fill_diago(M, v):
    for i in range(M.shape[0]):
        M[i, i] = v
    return M

def eucl_dist_matr_gpu(X):
    import cupy as cp
    X_g = cp.asarray(X, dtype=cp.float32)
    sq  = cp.sum(X_g**2, axis=1, keepdims=True)
    D2  = cp.maximum(sq+sq.T-2.0*(X_g@X_g.T), 0.0)
    D_g = cp.sqrt(D2); cp.fill_diagonal(D_g, 0.0)
    cp.cuda.Stream.null.synchronize()
    result = cp.asnumpy(D_g).astype(np.float64)
    del X_g, sq, D2, D_g
    cp.get_default_memory_pool().free_all_blocks()
    return result

@numba.jit(nopython=True)
def ms_perplexities(N, K_star=2, L_min=-1, L_max=-1):
    if L_min == -1: L_min = 1
    if L_max == -1: L_max = int(round(np.log2(np.float64(N)/np.float64(K_star))))
    L   = L_max-L_min+1
    K_h = (np.float64(2.0)**(np.linspace(L_min-1,L_max-1,L).astype(np.float64)))*np.float64(K_star)
    return L, K_h

def eval_dr_quality(d_hd, d_ld):
    rnxk = eval_rnx(Q=coranking(d_hd=d_hd, d_ld=d_ld))
    return rnxk, eval_auc(rnxk)

print("Core GPU functions ready ✓")`,

  6: `def run_optimizer(X_lds, tau_ij, N, n_components, arr_one, prod_N_nc,
                  optimizer='L-BFGS-B', lr=100.0, n_iter=200,
                  momentum=0.5, beta1=0.9, beta2=0.999):
    args = (tau_ij, N, n_components, arr_one, prod_N_nc)
    if optimizer == 'L-BFGS-B':
        res = scipy.optimize.minimize(
            fun=mstsne_obj, x0=X_lds, args=args, method='L-BFGS-B',
            jac=mstsne_grad, bounds=None,
            options={'disp':False,'maxls':dr_maxls,'gtol':dr_gtol,
                     'maxiter':dr_nitmax,'maxcor':dr_maxcor,
                     'maxfun':np.inf,'ftol':dr_ftol})
        return res.x
    elif optimizer == 'SGD':
        x = X_lds.copy()
        for t in range(n_iter):
            g = mstsne_grad(x, *args); x = x - lr*g
            if np.sqrt(np.sum(g**2)) < dr_gtol:
                print(f"    SGD converged at iter {t+1}"); break
        return x
    elif optimizer == 'Momentum':
        x = X_lds.copy(); v = np.zeros_like(x)
        for t in range(n_iter):
            g = mstsne_grad(x, *args)
            v = momentum*v - lr*g; x = x + v
            if np.sqrt(np.sum(g**2)) < dr_gtol:
                print(f"    Momentum converged at iter {t+1}"); break
        return x
    elif optimizer == 'Adam':
        x = X_lds.copy(); m = np.zeros_like(x); v = np.zeros_like(x); eps=1e-8
        for t in range(1, n_iter+1):
            g  = mstsne_grad(x, *args)
            m  = beta1*m + (1-beta1)*g
            v  = beta2*v + (1-beta2)*g**2
            mh = m/(1-beta1**t); vh = v/(1-beta2**t)
            x  = x - lr*mh/(np.sqrt(vh)+eps)
            if np.sqrt(np.sum(g**2)) < dr_gtol:
                print(f"    Adam converged at iter {t}"); break
        return x
    raise ValueError(f"Unknown optimizer: {optimizer}")

print("Optimizer runner ready ✓")`,

  7: `# ── Load dataset ─────────────────────────────────────────────────────────────
# Format: molecule_name, conformation_name, f1..f166, class (ends with '.')
rows = []
with open(DATA_CSV_PATH, 'r') as f:
    for line in f:
        line = line.strip().rstrip('.')
        if line:
            rows.append(line.split(','))

col_names = (['molecule_name', 'conformation_name'] +
             [f'f{i}' for i in range(1, 167)] + ['class'])
df = pd.DataFrame(rows, columns=col_names)

feature_cols = [f'f{i}' for i in range(1, 167)]
df[feature_cols] = df[feature_cols].apply(pd.to_numeric)
df['class']      = pd.to_numeric(df['class'])

X_hd = df[feature_cols].values.astype(np.float64)
y    = df['class'].values.astype(int)
N    = X_hd.shape[0]

L_est, _ = ms_perplexities(N=N, K_star=2)
print(f"N={N} | features={X_hd.shape[1]} | L={L_est} scales")
print(f"Musk={y.sum()} | Non-Musk={(y==0).sum()}")`,

  8: `print("Computing pairwise HD distances...")
t0    = time.time()
dm_hd = eucl_dist_matr_best(X_hd)
t_dm  = time.time()-t0
print(f"Done. Shape={dm_hd.shape} | Time={t_dm:.2f}s")`,

  9: `OPT = 'L-BFGS-B'
print(f"\\nRunning L-BFGS-B...")
t0   = time.time()
X_ld = mstsne_with_optimizer(
    X_hds=X_hd, init=INIT, n_components=2,
    dm_hds=dm_hd, seed_mstsne=SEED,
    optimizer=OPT, n_iter=N_ITER)
elapsed = time.time()-t0
rnx, auc = eval_dr_quality(d_hd=dm_hd, d_ld=eucl_dist_matr_best(X_ld))
print(f"[L-BFGS-B] AUC={auc:.4f} | Time={elapsed:.2f}s")`,

  10: `OPT = 'SGD'
print(f"\\nRunning SGD...")
t0   = time.time()
X_ld = mstsne_with_optimizer(
    X_hds=X_hd, init=INIT, n_components=2,
    dm_hds=dm_hd, seed_mstsne=SEED,
    optimizer=OPT, lr=LR, n_iter=N_ITER)
elapsed = time.time()-t0
rnx, auc = eval_dr_quality(d_hd=dm_hd, d_ld=eucl_dist_matr_best(X_ld))
print(f"[SGD] AUC={auc:.4f} | Time={elapsed:.2f}s")`,

  11: `OPT = 'Momentum'
print(f"\\nRunning Momentum...")
t0   = time.time()
X_ld = mstsne_with_optimizer(
    X_hds=X_hd, init=INIT, n_components=2,
    dm_hds=dm_hd, seed_mstsne=SEED,
    optimizer=OPT, lr=LR, momentum=MU, n_iter=N_ITER)
elapsed = time.time()-t0
rnx, auc = eval_dr_quality(d_hd=dm_hd, d_ld=eucl_dist_matr_best(X_ld))
print(f"[Momentum] AUC={auc:.4f} | Time={elapsed:.2f}s")`,

  12: `OPT = 'Adam'
print(f"\\nRunning Adam lr=100 (catastrophic baseline)...")
t0   = time.time()
X_ld = mstsne_with_optimizer(
    X_hds=X_hd, init=INIT, n_components=2,
    dm_hds=dm_hd, seed_mstsne=SEED,
    optimizer=OPT, lr=100.0, n_iter=N_ITER)
elapsed = time.time()-t0
rnx, auc = eval_dr_quality(d_hd=dm_hd, d_ld=eucl_dist_matr_best(X_ld))
print(f"[Adam_lr100] AUC={auc:.4f} | Time={elapsed:.2f}s")`,

  13: `print("\\nAdam lr sensitivity search...")
best_auc=0.0; best_lr=None

for lr_test in ADAM_LR_LIST:
    if lr_test == 100.0:
        print(f"  lr={lr_test:<8} AUC={results['Adam_lr100']['auc']:.4f} | (reused)")
        continue
    t0   = time.time()
    X_ld = mstsne_with_optimizer(
        X_hds=X_hd, init=INIT, n_components=2,
        dm_hds=dm_hd, seed_mstsne=SEED,
        optimizer='Adam', lr=lr_test, n_iter=N_ITER)
    elapsed = time.time()-t0
    rnx, auc = eval_dr_quality(d_hd=dm_hd, d_ld=eucl_dist_matr_best(X_ld))
    print(f"  lr={lr_test:<8} AUC={auc:.4f} | {elapsed:.2f}s")
    if auc > best_auc:
        best_auc=auc; best_lr=lr_test

print(f"\\nBest Adam: lr={best_lr} | AUC={best_auc:.4f}")`,

  14: `print("\\n"+"="*52)
print(f"{'Optimizer':<20} {'AUC':>8} {'Time (s)':>10}")
print("-"*52)
for key in ['L-BFGS-B','SGD','Momentum','Adam_lr100','Adam_best']:
    if key not in results: continue
    r = results[key]
    extra = f"  (lr={r['best_lr']})" if key=='Adam_best' else ''
    print(f"{key:<20} {r['auc']:>8.4f} {r['time']:>10.2f}s{extra}")
print("="*52)`,

  19: `fig, ax = plt.subplots(figsize=(9, 6))
plot_cfg = {
    'L-BFGS-B'  : ('black',     '-',  'L-BFGS-B'),
    'SGD'        : ('royalblue', '-',  'SGD'),
    'Momentum'   : ('green',     '-',  'Momentum'),
    'Adam_lr100' : ('red',       '--', 'Adam lr=100'),
    'Adam_best'  : ('orange',    '-',  f'Adam lr={best_lr} (best)'),
}
for key, (col, ls, label) in plot_cfg.items():
    if key not in results: continue
    rnx = np.array(results[key]['rnx'])
    K   = np.arange(1, rnx.size+1)
    ax.semilogx(K, rnx, color=col, ls=ls, lw=2,
                label=f'{label} (AUC={results[key]["auc"]:.4f})')
ax.axhline(0, color='grey', ls=':', lw=1)
ax.set_xlabel('Neighbourhood size K (log scale)', fontsize=12)
ax.set_ylabel('R_NX(K)', fontsize=12)
ax.set_title('R_NX Quality Curves', fontsize=13)
ax.legend(fontsize=9); ax.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()`,

  21: `save_data = {}
for key, val in results.items():
    save_data[key] = {'auc':val['auc'],'time':val['time'],'rnx':val['rnx']}
    if 'best_lr' in val: save_data[key]['best_lr'] = val['best_lr']

save_data['adam_lr_grid'] = {
    str(lr):{'auc':v['auc'],'time':v['time']}
    for lr,v in adam_grid.items()
}
save_data['meta'] = {
    'dataset':'Musk Version 2 (clean2)',
    'N':N, 'features':X_hd.shape[1],
    'mode':'GPU', 'seed':SEED, 'n_iter':N_ITER,
    'timestamp':timestamp
}
with open(RESULT_PATH, 'w') as f:
    json.dump(save_data, f, indent=2)
print(f"Results saved → {RESULT_PATH}")
print("Done! ✓")`,
}

const FORMULAS = {
  5: {
    title: 'Core mstSNE math',
    items: [
      { name: 'SNE conditional prob',
        formula: 'p_{j|i} = exp(−d²_ij / v_i) / Σ_{k≠i} exp(−d²_ik / v_i)',
        desc: 'Gaussian kernel. v_i found by binary search targeting log(perplexity).' },
      { name: 'Multi-scale average',
        formula: 'σ^(l)_ij = [(l−1)σ^(l−1)_ij + p^(l)_{j|i}] / l',
        desc: 'Running average of HD similarities across L scales.' },
      { name: 'Symmetrised target',
        formula: 'τ_ij = (σ_ij + σ_ji) / 2N',
        desc: 'Symmetrised and normalised HD joint probability.' },
      { name: 'Student-t LD similarity',
        formula: 'q_ij = (1+‖y_i−y_j‖²)⁻¹ / Σ_{k≠l}(1+‖y_k−y_l‖²)⁻¹',
        desc: 'Heavy-tailed kernel in 2D. Avoids crowding problem.' },
      { name: 'KL divergence loss',
        formula: 'C = −Σ_ij τ_ij log q_ij',
        desc: 'Objective minimised by all optimizers.' },
      { name: 'Gradient',
        formula: '∂C/∂y_i = 4Σ_j (τ_ij−q_ij)(1+‖y_i−y_j‖²)⁻¹(y_i−y_j)',
        desc: 'Analytical gradient passed to every optimizer.' },
      { name: 'R_NX(K)',
        formula: 'R_NX(K) = [N·Q_NX(K) − K] / (N − K)',
        desc: '1=perfect neighbourhood preservation, 0=random.' },
      { name: 'AUC (1/K-weighted)',
        formula: 'AUC = Σ R_NX(K)/K  /  Σ 1/K',
        desc: 'Main benchmark metric. Favours small-K neighbourhood.' },
    ]
  },
  6: {
    title: 'Optimizer update rules',
    items: [
      { name: 'L-BFGS-B',
        formula: 'x_{t+1} = x_t − H_t⁻¹ ∇f(x_t)',
        desc: 'Quasi-Newton. maxiter=30, maxls=30, maxcor=6. No lr needed.' },
      { name: 'SGD',
        formula: 'x_{t+1} = x_t − α ∇f(x_t)',
        desc: 'α = lr (default 100). Fails on Ms t-SNE landscape.' },
      { name: 'Momentum',
        formula: 'v_{t+1} = μv_t − α∇f(x_t)\nx_{t+1} = x_t + v_{t+1}',
        desc: 'μ = 0.5 default. Also fails on Ms t-SNE.' },
      { name: 'Adam moments',
        formula: 'm_t = β₁m_{t-1} + (1−β₁)g_t\nv_t = β₂v_{t-1} + (1−β₂)g²_t',
        desc: 'β₁=0.9, β₂=0.999. Bias-corrected estimates.' },
      { name: 'Adam update',
        formula: 'x_{t+1} = x_t − α · m̂_t / (√v̂_t + ε)\nε = 1e-8',
        desc: 'Best lr=1.0 wins 20/21 benchmark datasets. lr=100 → catastrophic.' },
    ]
  },
  13: {
    title: 'Adam lr sensitivity',
    items: [
      { name: 'lr grid',
        formula: 'α ∈ {100, 10, 1.0, 0.1, 0.01, 0.001}',
        desc: 'lr=100 always catastrophic. lr=1.0 optimal on 20/21 datasets.' },
    ]
  },
}
</script>

<style scoped>
.node-panel {
  position: absolute; right: 0; top: 0; bottom: 0;
  width: 380px;
  background: var(--vx-bg-card);
  border-left: 1px solid var(--vx-border-soft);
  display: flex; flex-direction: column;
  box-shadow: -4px 0 24px rgba(0,0,0,.25);
  z-index: 100;
}

.panel-slide-enter-active, .panel-slide-leave-active { transition: transform .22s ease; }
.panel-slide-enter-from, .panel-slide-leave-to { transform: translateX(100%); }

.panel-header {
  padding: 16px 16px 0;
  border-bottom: 1px solid var(--vx-border-soft);
}
.panel-title-row {
  display: flex; align-items: center; gap: 10px; margin-bottom: 12px;
}
.node-icon-lg { font-size: 22px; }
.panel-title { font-size: 14px; font-weight: 700; }
.panel-sub   { font-size: 11px; color: var(--vx-text3); margin-top: 1px; }
.panel-status {
  margin-left: auto; padding: 2px 9px; border-radius: 20px;
  font-size: 11px; font-weight: 600; text-transform: capitalize;
}
.status-idle    { background: rgba(255,255,255,.06); color: var(--vx-text3); }
.status-running { background: var(--vx-warning-dim); color: var(--vx-warning); }
.status-done    { background: var(--vx-success-dim); color: var(--vx-success); }
.status-error   { background: var(--vx-danger-dim);  color: var(--vx-danger); }

.close-btn {
  background: none; border: none; color: var(--vx-text3); font-size: 13px;
  cursor: pointer; padding: 4px; border-radius: 4px; transition: color .15s;
}
.close-btn:hover { color: var(--vx-danger); }

.tab-bar { display: flex; gap: 2px; }
.tab {
  padding: 7px 14px; background: none; border: none;
  color: var(--vx-text3); font-size: 12px; font-weight: 500;
  cursor: pointer; border-bottom: 2px solid transparent;
  transition: all .15s; font-family: inherit;
}
.tab.active { color: var(--vx-primary); border-bottom-color: var(--vx-primary); }
.tab:hover:not(.active) { color: var(--vx-text); }

.panel-body { flex: 1; overflow-y: auto; padding: 14px 16px; }
.empty-state { font-size: 12px; color: var(--vx-text3); text-align: center; margin-top: 40px; }

.log-container { display: flex; flex-direction: column; gap: 2px; }
.log-line { font-size: 11px; line-height: 1.6; word-break: break-all; }

.code-container {}
.code-toolbar {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;
}
.code-editor {
  width: 100%; min-height: 200px; resize: vertical;
  background: #f6f6f8; border: 1px solid var(--vx-border);
  border-radius: 8px; padding: 10px 12px;
  font-family: 'IBM Plex Mono', monospace; font-size: 11.5px;
  color: #5a3ea1; line-height: 1.7; outline: none;
}
.run-btn { width: 100%; margin-top: 8px; justify-content: center; }
.run-output {
  margin-top: 8px; padding: 10px 12px;
  background: rgba(40,199,111,.08); border: 1px solid var(--vx-success);
  border-radius: 8px; font-size: 11px; color: var(--vx-success);
  white-space: pre-wrap; max-height: 200px; overflow-y: auto;
}
.run-error {
  margin-top: 8px; padding: 10px 12px;
  background: rgba(234,84,85,.08); border: 1px solid var(--vx-danger);
  border-radius: 8px; font-size: 11px; color: var(--vx-danger);
  white-space: pre-wrap; max-height: 200px; overflow-y: auto;
}

.formula-title { font-size: 12px; font-weight: 700; color: var(--vx-primary-l); margin-bottom: 10px; }
.formula-item {
  background: var(--vx-bg); border: 1px solid var(--vx-border-soft);
  border-radius: 8px; padding: 10px 12px; margin-bottom: 8px;
}
.formula-name { font-size: 11px; font-weight: 700; color: var(--vx-info); margin-bottom: 4px; }
.formula-eq   { font-size: 11px; color: var(--vx-warning); white-space: pre-wrap; margin-bottom: 5px; }
.formula-desc { font-size: 11px; color: var(--vx-text3); line-height: 1.5; }

.result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.result-card {
  background: var(--vx-bg); border: 1px solid var(--vx-border-soft);
  border-radius: 8px; padding: 12px; text-align: center;
}
.result-card.full { grid-column: span 2; }
.result-label { font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .05em; color: var(--vx-text3); margin-bottom: 6px; }
.result-value { font-size: 18px; font-weight: 700; }
.result-value.success { color: var(--vx-success); }
.result-value.warning { color: var(--vx-warning); }
</style>