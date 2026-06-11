<template>
  <transition name="sidebar-slide">
    <div v-if="visible"
      :class="inline ? 'editor-inline' : 'editor-overlay'"
      @keydown.esc="!inline && $emit('close')">
      <div class="editor-sidebar">

        <!-- ── Top bar ─────────────────────────────────────────────────── -->
        <div class="editor-topbar">
          <div class="editor-topbar-left">
            <span class="editor-title">Code Editor</span>
            <span class="badge-section mono">§{{ activeNode?.section }} · {{ activeNode?.label }}</span>
          </div>
          <div class="editor-topbar-right">
            <span v-if="lastRunStatus === 'ok'"    class="run-status ok">✓ ran ok</span>
            <span v-if="lastRunStatus === 'error'" class="run-status err">✕ error</span>
            <button class="btn-icon" title="Close (Esc)" @click="$emit('close')">✕</button>
          </div>
        </div>

        <!-- ── Three-panel body ────────────────────────────────────────── -->
        <div class="editor-body">

          <!-- LEFT: node list ─────────────────────────────────────────── -->
          <div class="node-list-panel">
            <div class="panel-hdr">Sections</div>
            <div class="node-list-scroll">
              <template v-for="group in NODE_GROUPS" :key="group.label">
                <div class="group-label">{{ group.label }}</div>
                <div
                  v-for="n in group.nodes" :key="n.id"
                  class="node-list-item"
                  :class="{
                    active:   activeNodeId === n.id,
                    done:     nodeState[n.id]?.status === 'done',
                    running:  nodeState[n.id]?.status === 'running',
                  }"
                  @click="switchNode(n.id)"
                >
                  <div class="nli-dot" :class="`dot-${nodeState[n.id]?.status || 'idle'}`"/>
                  <span class="nli-icon">{{ n.icon }}</span>
                  <div class="nli-body">
                    <div class="nli-label">{{ n.label }}</div>
                    <div class="nli-sec mono">§{{ n.section }}</div>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- CENTER: code editor ──────────────────────────────────────── -->
          <div class="code-panel">

            <!-- editor toolbar -->
            <div class="code-toolbar">
              <span class="badge-lang mono">Python</span>
              <div style="display:flex;gap:6px;align-items:center;margin-left:auto">
                <button class="btn-tool" @click="resetCode" title="Reset to original">↺ Reset</button>
                <button class="btn-tool" @click="copyCode">{{ copied ? '✓ Copied' : '⎘ Copy' }}</button>
                <button class="btn-run" :disabled="runningSnippet" @click="runSnippet">
                  {{ runningSnippet ? '⏳ Running…' : '▶ Run' }}
                </button>
              </div>
            </div>

            <!-- editor area with line numbers -->
            <div class="editor-area">
              <div class="line-numbers" ref="lineNumsRef">
                <div v-for="n in lineCount" :key="n" class="ln">{{ n }}</div>
              </div>
              <textarea
                ref="editorRef"
                class="code-textarea mono"
                v-model="editableCode"
                spellcheck="false"
                autocomplete="off"
                autocorrect="off"
                autocapitalize="off"
                @scroll="syncScroll"
                @input="onInput"
              />
            </div>

            <!-- output panel -->
            <div class="output-panel" :class="{ 'has-error': lastRunStatus === 'error' }">
              <div class="output-hdr">
                <span class="mono" style="font-size:9px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#585b70">Output</span>
                <button v-if="runOutput || runError" class="btn-clear" @click="clearOutput">clear</button>
              </div>
              <div v-if="!runOutput && !runError" class="output-empty">
                Click ▶ Run to execute this section
              </div>
              <pre v-if="runOutput" class="output-text ok mono">{{ runOutput }}</pre>
              <pre v-if="runError"  class="output-text err mono">{{ runError }}</pre>
            </div>

          </div>

          <!-- RIGHT: formula + logs ────────────────────────────────────── -->
          <div class="info-panel">
            <div class="panel-hdr" style="display:flex;gap:0">
              <button v-for="t in ['Formula','Logs']" :key="t"
                class="info-tab" :class="{ active: infoTab === t }"
                @click="infoTab = t">{{ t }}</button>
            </div>

            <!-- Formula -->
            <div v-if="infoTab === 'Formula'" class="info-scroll">
              <div v-if="!formulaData" class="info-empty">No formulas for this section.</div>
              <div v-else>
                <div class="formula-title">{{ formulaData.title }}</div>
                <div v-for="(item, i) in formulaData.items" :key="i" class="formula-card">
                  <div class="f-name">{{ item.name }}</div>
                  <pre class="f-eq mono">{{ item.formula }}</pre>
                  <div class="f-desc">{{ item.desc }}</div>
                </div>
              </div>
            </div>

            <!-- Logs -->
            <div v-if="infoTab === 'Logs'" class="info-scroll">
              <div v-if="!nodeLogs.length" class="info-empty">No logs yet.</div>
              <div v-for="(msg, i) in nodeLogs" :key="i"
                class="log-line mono" :style="{ color: logColor(msg) }">
                {{ msg }}
              </div>
              <div ref="logEndRef"/>
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
  visible:    Boolean,
  initialNodeId: String,
  nodes:      Array,
  nodeState:  Object,
  sessionId:  String,
  inline:        Boolean,
})
const emit = defineEmits(['close'])

// ── State ─────────────────────────────────────────────────────────────────────
const activeNodeId    = ref(props.initialNodeId || null)
const infoTab         = ref('Formula')
const editableCode    = ref('')
const originalCode    = ref('')
const copied          = ref(false)
const runningSnippet  = ref(false)
const runOutput       = ref('')
const runError        = ref('')
const lastRunStatus   = ref(null)
const editorRef       = ref(null)
const lineNumsRef     = ref(null)
const logEndRef       = ref(null)

// ── Computed ──────────────────────────────────────────────────────────────────
const activeNode = computed(() =>
  props.nodes?.find(n => n.id === activeNodeId.value) || null)

const lineCount = computed(() =>
  (editableCode.value.match(/\n/g) || []).length + 1)

const formulaData = computed(() =>
  FORMULAS[activeNode.value?.section] || null)

const nodeLogs = computed(() =>
  props.nodeState?.[activeNodeId.value]?.logs || [])

// ── Node groups for left panel ────────────────────────────────────────────────
const NODE_GROUPS = computed(() => {
  const groups = {}
  props.nodes?.forEach(n => {
    if (!groups[n.group]) groups[n.group] = { label: n.group, nodes: [] }
    groups[n.group].nodes.push(n)
  })
  const order = ['setup','data','optim','result']
  return order.filter(g => groups[g]).map(g => groups[g])
})

// ── Watch ─────────────────────────────────────────────────────────────────────
watch(() => props.initialNodeId, (id) => {
  if (id) switchNode(id)
})

watch(() => props.visible, (v) => {
  if (v && props.initialNodeId) switchNode(props.initialNodeId)
})

watch(nodeLogs, async () => {
  await nextTick()
  logEndRef.value?.scrollIntoView({ behavior: 'smooth' })
})

// ── Methods ───────────────────────────────────────────────────────────────────
function switchNode(id) {
  activeNodeId.value = id
  const code = CODE_SNIPPETS[props.nodes?.find(n => n.id === id)?.section] || ''
  editableCode.value  = code
  originalCode.value  = code
  runOutput.value     = ''
  runError.value      = ''
  lastRunStatus.value = null
}

function resetCode() {
  editableCode.value = originalCode.value
}

async function copyCode() {
  await navigator.clipboard.writeText(editableCode.value)
  copied.value = true
  setTimeout(() => copied.value = false, 1800)
}

function clearOutput() {
  runOutput.value = ''
  runError.value  = ''
  lastRunStatus.value = null
}

async function runSnippet() {
  runningSnippet.value = true
  runOutput.value = ''
  runError.value  = ''
  lastRunStatus.value = null
  try {
    const base = import.meta.env.VITE_API_URL || ''
    const r = await fetch(`${base}/api/session/${props.sessionId}/run-snippet`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code:    editableCode.value,
        section: activeNode.value?.section
      })
    })
    const d = await r.json()
    if (d.error) {
      runError.value  = d.error
      lastRunStatus.value = 'error'
    } else {
      runOutput.value = d.output
      lastRunStatus.value = 'ok'
    }
  } catch(e) {
    runError.value = e.message
    lastRunStatus.value = 'error'
  } finally {
    runningSnippet.value = false
  }
}

function onInput() {
  // keep line numbers in sync (handled by computed lineCount)
}

function syncScroll() {
  if (lineNumsRef.value && editorRef.value)
    lineNumsRef.value.scrollTop = editorRef.value.scrollTop
}

function logColor(msg) {
  if (msg.includes('✓') || msg.includes('AUC=')) return 'var(--vx-success)'
  if (msg.includes('Error') || msg.includes('error')) return 'var(--vx-danger)'
  if (msg.includes('===')) return 'var(--vx-primary-l)'
  if (msg.includes('lr=') || msg.includes('Time=')) return 'var(--vx-warning)'
  return 'var(--vx-text2)'
}

// ── Code snippets (exact from notebook) ──────────────────────────────────────
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
def arange_except_i(N, i):
    arr = np.arange(N)
    return np.hstack((arr[:i], arr[i+1:]))

@numba.jit(nopython=True)
def fill_diago(M, v):
    for i in range(M.shape[0]):
        M[i, i] = v
    return M

def eucl_dist_matr_cpu(X):
    return scipy.spatial.distance.squareform(
        scipy.spatial.distance.pdist(X, metric='euclidean'))

def eucl_dist_matr_gpu(X):
    try:
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
    except Exception as e:
        print(f"[GPU DM fallback] {e}")
        return eucl_dist_matr_cpu(X)

def sqeucl_dist_matr_gpu(X):
    try:
        import cupy as cp
        X_g = cp.asarray(X, dtype=cp.float32)
        sq  = cp.sum(X_g**2, axis=1, keepdims=True)
        D2  = cp.maximum(sq+sq.T-2.0*(X_g@X_g.T), 0.0)
        cp.fill_diagonal(D2, 0.0)
        result = cp.asnumpy(D2).astype(np.float64)
        del X_g, sq, D2
        cp.get_default_memory_pool().free_all_blocks()
        return result
    except Exception:
        return scipy.spatial.distance.squareform(
            scipy.spatial.distance.pdist(X, metric='sqeuclidean'))

try:
    import cupy as cp
    _t = cp.asarray(np.ones((10,10), dtype=np.float32))
    _ = _t @ _t.T
    cp.get_default_memory_pool().free_all_blocks()
    eucl_dist_matr_best = eucl_dist_matr_gpu
    USE_GPU = True
    print("Distance matrix: GPU float32 (CuPy) ✓")
except Exception as e:
    eucl_dist_matr_best = eucl_dist_matr_cpu
    USE_GPU = False
    print(f"Distance matrix: CPU fallback ({e})")

@numba.jit(nopython=True)
def ms_perplexities(N, K_star=2, L_min=-1, L_max=-1):
    if L_min == -1: L_min = 1
    if L_max == -1: L_max = int(round(np.log2(np.float64(N)/np.float64(K_star))))
    L   = L_max-L_min+1
    K_h = (np.float64(2.0)**(np.linspace(L_min-1,L_max-1,L).astype(np.float64)))*np.float64(K_star)
    return L, K_h

def init_lds(X_hds, N, init='pca', n_components=2, rand_state=None):
    if rand_state is None: rand_state = np.random
    if isinstance(init, str) and init=='pca':
        return sklearn.decomposition.PCA(n_components=n_components,
                                         random_state=rand_state).fit_transform(X_hds)
    elif isinstance(init, np.ndarray): return init
    return rand_state.randn(N, n_components)

@numba.jit(nopython=True)
def sne_sim(dsi, vi, i, compute_log=True):
    N  = dsi.size
    si = np.empty(N, dtype=np.float64); si[i] = 0.0
    log_si = np.empty(N, dtype=np.float64)
    indj   = arange_except_i(N, i); dsij = dsi[indj]
    log_num = (dsij.min()-dsij)/vi
    si[indj] = np.exp(log_num); den = si.sum(); si /= den
    if compute_log:
        log_si[i] = 0.0; log_si[indj] = log_num-np.log(den)
    return si, log_si

@numba.jit(nopython=True)
def sne_bsf(dsi, vi, i, log_perp):
    si, log_si = sne_sim(dsi, vi, i, compute_log=True)
    return -np.dot(si, log_si)-log_perp

@numba.jit(nopython=True)
def sne_bs(dsi, i, log_perp, x0=1.0):
    fx0 = sne_bsf(dsi, x0, i, log_perp)
    if close_to_zero(fx0): return x0
    elif not np.isfinite(fx0): raise ValueError("fx0 nan")
    elif fx0 > 0:
        x_up, x_low = x0, x0/2.0
        fx_low = sne_bsf(dsi, x_low, i, log_perp)
        if close_to_zero(fx_low): return x_low
        elif not np.isfinite(fx_low): return x_up
        while fx_low > 0:
            x_up, x_low = x_low, x_low/2.0
            fx_low = sne_bsf(dsi, x_low, i, log_perp)
            if close_to_zero(fx_low): return x_low
            if not np.isfinite(fx_low): return x_up
    else:
        x_up, x_low = x0*2.0, x0
        fx_up = sne_bsf(dsi, x_up, i, log_perp)
        if close_to_zero(fx_up): return x_up
        elif not np.isfinite(fx_up): return x_low
        while fx_up < 0:
            x_up, x_low = 2.0*x_up, x_up
            fx_up = sne_bsf(dsi, x_up, i, log_perp)
            if close_to_zero(fx_up): return x_up
    while True:
        x = (x_up+x_low)/2.0
        fx = sne_bsf(dsi, x, i, log_perp)
        if close_to_zero(fx): return x
        elif fx > 0: x_up = x
        else: x_low = x

@numba.jit(nopython=True)
def sne_hd_similarities(dsm_hds, perp, compute_log=True,
                         start_bs=np.ones(1, dtype=np.float64)):
    if perp <= 1: raise ValueError("perp must be > 1")
    N = dsm_hds.shape[0]
    if start_bs.size==1: start_bs = np.ones(N, dtype=np.float64)
    log_perp = np.log(min(np.float64(perp), np.floor(0.99*np.float64(N))))
    si     = np.empty((N,N), dtype=np.float64)
    log_si = np.empty((N,N), dtype=np.float64)
    arr_vi = np.empty(N, dtype=np.float64)
    for i in range(N):
        vi = sne_bs(dsm_hds[i,:], i, log_perp, x0=start_bs[i])
        tmp = sne_sim(dsm_hds[i,:], vi, i, compute_log)
        si[i,:] = tmp[0]
        if compute_log: log_si[i,:] = tmp[1]
        arr_vi[i] = vi
    return si, log_si, arr_vi

@numba.jit(nopython=True)
def mstsne_ld_sim(dsm_ld):
    global n_eps_np_float64
    dsm_ld_one     = 1.0+dsm_ld
    inv_dsm_ld_one = 1.0/np.maximum(n_eps_np_float64, dsm_ld_one)
    t_ij     = inv_dsm_ld_one.copy()
    log_t_ij = -np.log(dsm_ld_one)
    t_ij     = fill_diago(t_ij, 0.0)
    log_t_ij = fill_diago(log_t_ij, 0.0)
    den      = t_ij.sum()
    t_ij    /= np.maximum(n_eps_np_float64, den)
    log_t_ij -= np.log(den)
    return t_ij, log_t_ij, inv_dsm_ld_one

def mstsne_obj(x, tau_ij, N, n_components, arr_one, prod_N_nc):
    try:
        import cupy as cp
        X_lds = np.reshape(x, (N, n_components))
        X_g   = cp.asarray(X_lds, dtype=cp.float32)
        sq    = cp.sum(X_g**2, axis=1, keepdims=True)
        D2    = cp.maximum(sq+sq.T-2.0*(X_g@X_g.T), 0.0)
        cp.fill_diagonal(D2, 0.0); del sq
        D2_64      = D2.astype(cp.float64); del D2
        dsm_ld_one = 1.0+D2_64
        inv_one    = 1.0/cp.maximum(n_eps_np_float64, dsm_ld_one)
        t_ij_g     = inv_one.copy()
        log_t_ij_g = -cp.log(dsm_ld_one)
        del D2_64, dsm_ld_one, inv_one
        diag_idx = cp.arange(N)
        t_ij_g[diag_idx,diag_idx]     = 0.0
        log_t_ij_g[diag_idx,diag_idx] = 0.0
        den = cp.maximum(n_eps_np_float64, t_ij_g.sum())
        t_ij_g /= den; log_t_ij_g -= cp.log(den); del t_ij_g
        cp.get_default_memory_pool().free_all_blocks()
        tau_g = cp.asarray(tau_ij, dtype=cp.float64)
        cost  = float(-cp.dot(tau_g.ravel(), log_t_ij_g.ravel()))
        del tau_g, log_t_ij_g
        cp.get_default_memory_pool().free_all_blocks()
        return cost
    except Exception as e:
        X_lds    = np.reshape(x, (N, n_components))
        dsm_ld   = sqeucl_dist_matr_gpu(X_lds)
        log_t_ij = mstsne_ld_sim(dsm_ld)[1]
        return -np.dot(tau_ij.ravel(), log_t_ij.ravel())

def mstsne_grad(x, tau_ij, N, n_components, arr_one, prod_N_nc):
    try:
        import cupy as cp
        X_lds = np.reshape(x, (N, n_components))
        X_g   = cp.asarray(X_lds, dtype=cp.float32)
        sq    = cp.sum(X_g**2, axis=1, keepdims=True)
        D2    = cp.maximum(sq+sq.T-2.0*(X_g@X_g.T), 0.0)
        cp.fill_diagonal(D2, 0.0); del sq
        D2_64      = D2.astype(cp.float64); del D2
        dsm_ld_one = 1.0+D2_64
        inv_one    = 1.0/cp.maximum(n_eps_np_float64, dsm_ld_one)
        t_ij_g     = inv_one.copy()
        del D2_64, dsm_ld_one
        diag_idx = cp.arange(N)
        t_ij_g[diag_idx,diag_idx] = 0.0
        t_ij_g /= cp.maximum(n_eps_np_float64, t_ij_g.sum())
        tau_g  = cp.asarray(tau_ij, dtype=cp.float64)
        c_ij_g = 4.0*(tau_g-t_ij_g)*inv_one
        del tau_g, t_ij_g, inv_one
        cp.get_default_memory_pool().free_all_blocks()
        X_g64     = X_g.astype(cp.float64); del X_g
        arr_one_g = cp.asarray(arr_one, dtype=cp.float64)
        grad_g    = (X_g64.T*cp.dot(c_ij_g,arr_one_g)).T - cp.dot(c_ij_g,X_g64)
        del c_ij_g, X_g64, arr_one_g
        cp.cuda.Stream.null.synchronize()
        result = cp.asnumpy(grad_g).flatten(); del grad_g
        cp.get_default_memory_pool().free_all_blocks()
        return result
    except Exception as e:
        X_lds  = np.reshape(x, (N, n_components))
        dsm_ld = sqeucl_dist_matr_gpu(X_lds)
        t_ij, log_t_ij, inv_dsm_ld_one = mstsne_ld_sim(dsm_ld)
        c_ij    = 4.0*(tau_ij-t_ij)*inv_dsm_ld_one
        grad_ld = (X_lds.T*np.dot(c_ij,arr_one)).T - np.dot(c_ij,X_lds)
        return np.reshape(grad_ld, prod_N_nc)

def mstsne_manage_seed(seed_mstsne=None):
    global seed_MstSNE_def
    if seed_mstsne is None: seed_mstsne = seed_MstSNE_def
    return np.random.RandomState(seed_mstsne) if seed_mstsne > 0 else np.random

def coranking(d_hd, d_ld):
    perm_hd = d_hd.argsort(axis=-1, kind='mergesort')
    perm_ld = d_ld.argsort(axis=-1, kind='mergesort')
    N = d_hd.shape[0]; i = np.arange(N, dtype=np.int64)
    R = np.empty((N,N), dtype=np.int64)
    for j in range(N): R[perm_ld[j,i], j] = i
    Q = np.zeros((N,N), dtype=np.int64)
    for j in range(N): Q[i, R[perm_hd[j,i], j]] += 1
    return Q[1:,1:]

@numba.jit(nopython=True)
def eval_auc(arr):
    i_all_k = 1.0/(np.arange(arr.size)+1.0)
    return np.float64(np.dot(arr, i_all_k))/(i_all_k.sum())

@numba.jit(nopython=True)
def eval_rnx(Q):
    N_1 = Q.shape[0]; N = N_1+1
    qnxk = np.empty(N_1, dtype=np.float64); acc_q = 0.0
    for K in range(N_1):
        acc_q += (Q[K,K]+np.sum(Q[K,:K])+np.sum(Q[:K,K]))
        qnxk[K] = acc_q/((K+1)*N)
    arr_K = np.arange(N_1)[1:].astype(np.float64)
    return (N_1*qnxk[:N_1-1]-arr_K)/(N_1-arr_K)

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

  7: `# Load dataset (replace DATA_CSV_PATH with your actual path)
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
        formula: 'p_{j|i} = exp(−d²_ij/v_i) / Σ_{k≠i} exp(−d²_ik/v_i)',
        desc: 'Gaussian kernel. v_i found by binary search.' },
      { name: 'Symmetrised target',
        formula: 'τ_ij = (σ_ij + σ_ji) / 2N',
        desc: 'Normalised HD joint probability.' },
      { name: 'Student-t LD similarity',
        formula: 'q_ij = (1+‖y_i−y_j‖²)⁻¹ / Σ_{k≠l}(1+‖y_k−y_l‖²)⁻¹',
        desc: 'Heavy-tailed kernel. Avoids crowding.' },
      { name: 'KL divergence loss',
        formula: 'C = −Σ_ij τ_ij log q_ij',
        desc: 'Objective minimised by all optimizers.' },
      { name: 'Gradient',
        formula: '∂C/∂y_i = 4Σ_j(τ_ij−q_ij)(1+‖y_i−y_j‖²)⁻¹(y_i−y_j)',
        desc: 'Passed to every optimizer.' },
      { name: 'R_NX(K)',
        formula: 'R_NX(K) = [N·Q_NX(K) − K] / (N − K)',
        desc: '1=perfect, 0=random.' },
      { name: 'AUC',
        formula: 'AUC = Σ R_NX(K)/K  /  Σ 1/K',
        desc: '1/K-weighted. Main benchmark metric.' },
    ]
  },
  6: {
    title: 'Optimizer update rules',
    items: [
      { name: 'L-BFGS-B', formula: 'x_{t+1} = x_t − H_t⁻¹ ∇f(x_t)',
        desc: 'Quasi-Newton. maxiter=30, maxcor=6.' },
      { name: 'SGD', formula: 'x_{t+1} = x_t − α ∇f(x_t)',
        desc: 'Fails on Ms t-SNE landscape.' },
      { name: 'Momentum', formula: 'v_{t+1} = μv_t − α∇f\nx_{t+1} = x_t + v_{t+1}',
        desc: 'μ=0.5 default.' },
      { name: 'Adam', formula: 'x_{t+1} = x_t − α·m̂_t/(√v̂_t+ε)\nβ₁=0.9, β₂=0.999, ε=1e-8',
        desc: 'Best lr=1.0 wins 20/21 datasets.' },
    ]
  },
  13: {
    title: 'Adam lr sensitivity',
    items: [
      { name: 'Grid', formula: 'α ∈ {100, 10, 1.0, 0.1, 0.01, 0.001}',
        desc: 'lr=100 catastrophic. lr=1.0 optimal on 20/21.' },
    ]
  },
}
</script>

<style scoped>
.editor-overlay {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(0,0,0,.45);
  display: flex; align-items: stretch; justify-content: flex-end;
}

.sidebar-slide-enter-active, .sidebar-slide-leave-active { transition: transform .25s ease; }
.sidebar-slide-enter-from, .sidebar-slide-leave-to { transform: translateX(100%); }

.editor-sidebar {
  width: 88vw; max-width: 1200px;
  background: var(--vx-bg-card);
  display: flex; flex-direction: column;
  box-shadow: -8px 0 40px rgba(0,0,0,.4);
}

/* ── Topbar ── */
.editor-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-bottom: 1px solid var(--vx-border-soft);
  flex-shrink: 0; background: var(--vx-bg-card);
}
.editor-topbar-left { display: flex; align-items: center; gap: 12px; }
.editor-topbar-right { display: flex; align-items: center; gap: 10px; }
.editor-title { font-size: 14px; font-weight: 700; }
.badge-section {
  font-size: 11px; padding: 2px 9px; border-radius: 20px;
  background: var(--vx-primary-dim); color: var(--vx-primary-l);
}
.run-status {
  font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: 20px;
}
.run-status.ok  { background: var(--vx-success-dim); color: var(--vx-success); }
.run-status.err { background: var(--vx-danger-dim);  color: var(--vx-danger); }
.btn-icon {
  background: none; border: none; color: var(--vx-text3); font-size: 14px;
  cursor: pointer; padding: 4px 6px; border-radius: 4px;
}
.btn-icon:hover { color: var(--vx-danger); }

/* ── Body ── */
.editor-body {
  flex: 1; display: flex; overflow: hidden; min-height: 0;
}

/* ── Left node list ── */
.node-list-panel {
  width: 200px; flex-shrink: 0;
  background: var(--vx-bg);
  border-right: 1px solid var(--vx-border-soft);
  display: flex; flex-direction: column;
}
.panel-hdr {
  padding: 9px 12px; font-size: 11px; font-weight: 700;
  letter-spacing: .04em; text-transform: uppercase;
  color: var(--vx-text3); border-bottom: 1px solid var(--vx-border-soft);
  flex-shrink: 0;
}
.node-list-scroll { flex: 1; overflow-y: auto; padding: 6px 8px; }
.group-label {
  font-size: 9px; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--vx-text3);
  padding: 8px 6px 4px;
}
.node-list-item {
  display: flex; align-items: center; gap: 7px;
  padding: 7px 8px; border-radius: 7px; margin-bottom: 3px;
  cursor: pointer; transition: all .15s;
  border: 1px solid transparent;
}
.node-list-item:hover { background: var(--vx-bg-hover); }
.node-list-item.active {
  background: var(--vx-primary-dim);
  border-color: var(--vx-primary);
}
.node-list-item.done   { border-left: 2px solid var(--vx-success); }
.node-list-item.running { border-left: 2px solid var(--vx-warning); }
.nli-dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}
.dot-idle    { background: var(--vx-border); }
.dot-running { background: var(--vx-warning); }
.dot-done    { background: var(--vx-success); }
.dot-error   { background: var(--vx-danger); }
.nli-icon { font-size: 14px; }
.nli-label { font-size: 11px; font-weight: 500; color: var(--vx-text); }
.nli-sec   { font-size: 9px; color: var(--vx-text3); margin-top: 1px; }

/* ── Center code panel ── */
.code-panel {
  flex: 1; display: flex; flex-direction: column; min-width: 0;
  background: #1e1e2e;
}
.code-toolbar {
  display: flex; align-items: center; padding: 7px 14px;
  border-bottom: 1px solid #313244; flex-shrink: 0;
  background: #181825;
}
.badge-lang {
  font-size: 10px; padding: 2px 8px; border-radius: 4px;
  background: #313244; color: #6c7086;
}
.btn-tool {
  padding: 3px 10px; border-radius: 5px; font-size: 11px; font-weight: 500;
  border: 1px solid #45475a; background: transparent; color: #a6adc8;
  cursor: pointer; font-family: inherit; transition: all .15s;
}
.btn-tool:hover { background: #313244; color: #cdd6f4; }
.btn-run {
  padding: 4px 14px; border-radius: 5px; font-size: 12px; font-weight: 600;
  border: none; background: var(--vx-primary); color: #fff;
  cursor: pointer; font-family: inherit; transition: opacity .15s;
}
.btn-run:hover   { opacity: .88; }
.btn-run:disabled { opacity: .4; cursor: not-allowed; }

.editor-area {
  flex: 1; display: flex; overflow: hidden; min-height: 0;
}
.line-numbers {
  background: #181825; padding: 10px 8px; min-width: 40px;
  text-align: right; overflow: hidden; flex-shrink: 0;
  font-family: 'IBM Plex Mono', monospace; font-size: 12px;
  line-height: 1.75; color: #585b70; user-select: none;
}
.ln { height: 21px; }
.code-textarea {
  flex: 1; background: #1e1e2e; color: #cdd6f4;
  border: none; outline: none; resize: none;
  padding: 10px 14px; font-size: 12px; line-height: 1.75;
  tab-size: 4; white-space: pre; overflow-x: auto; overflow-y: auto;
  font-family: 'IBM Plex Mono', monospace;
}

.output-panel {
  border-top: 1px solid #313244; background: #11111b;
  padding: 8px 14px; max-height: 140px; overflow-y: auto; flex-shrink: 0;
}
.output-panel.has-error { border-top-color: var(--vx-danger); }
.output-hdr {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 5px;
}
.btn-clear {
  font-size: 10px; background: none; border: none;
  color: #6c7086; cursor: pointer; font-family: inherit;
}
.btn-clear:hover { color: #a6adc8; }
.output-empty { font-size: 11px; color: #585b70; font-family: 'IBM Plex Mono', monospace; }
.output-text {
  font-size: 11px; line-height: 1.7; white-space: pre-wrap;
  word-break: break-all; margin: 0;
}
.output-text.ok  { color: #a6e3a1; }
.output-text.err { color: #f38ba8; }

/* ── Right info panel ── */
.info-panel {
  width: 240px; flex-shrink: 0;
  background: var(--vx-bg-card);
  border-left: 1px solid var(--vx-border-soft);
  display: flex; flex-direction: column;
}
.info-tab {
  flex: 1; padding: 8px 0; background: none; border: none;
  color: var(--vx-text3); font-size: 12px; font-weight: 500;
  cursor: pointer; border-bottom: 2px solid transparent;
  font-family: inherit; transition: all .15s;
}
.info-tab.active { color: var(--vx-primary); border-bottom-color: var(--vx-primary); }
.info-tab:hover:not(.active) { color: var(--vx-text); }
.info-scroll { flex: 1; overflow-y: auto; padding: 12px; }
.info-empty { font-size: 11px; color: var(--vx-text3); text-align: center; margin-top: 30px; }

.formula-title { font-size: 11px; font-weight: 700; color: var(--vx-primary-l); margin-bottom: 8px; }
.formula-card {
  background: var(--vx-bg); border: 1px solid var(--vx-border-soft);
  border-radius: 7px; padding: 8px 10px; margin-bottom: 7px;
}
.f-name { font-size: 10px; font-weight: 700; color: var(--vx-info); margin-bottom: 3px; }
.f-eq   { font-size: 10px; color: var(--vx-warning); white-space: pre-wrap; margin-bottom: 4px; }
.f-desc { font-size: 10px; color: var(--vx-text3); line-height: 1.5; }

.log-line { font-size: 10px; line-height: 1.65; word-break: break-all; margin-bottom: 1px; }

.mono { font-family: 'IBM Plex Mono', monospace !important; }
</style>
