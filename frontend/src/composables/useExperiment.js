import { ref, reactive, computed } from 'vue'

const API_BASE = (() => {
  const env = import.meta.env.VITE_API_URL
  return (env && env.trim()) ? env.trim().replace(/\/$/, '') : ''
})()

export function apiUrl(path) { return `${API_BASE}${path}` }
export function wsUrl(path) {
  const base = API_BASE
    ? API_BASE.replace(/^http/, 'ws')
    : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`
  return `${base}${path}`
}

export function useExperiment() {
  const sessionId   = ref(null)
  const gpuInfo     = ref(null)
  const running     = ref(false)
  const error       = ref(null)
  const currentStep = ref(null)

  // Per-node state: { status, logs, result }
  const nodeState = reactive({})

  const optimizerResults = ref([])   // [{optimizer, auc, time}]
  const adamGrid         = ref(null) // {grid, best_lr}
  //const figures          = ref({})   // {key: url}
  const figures          = reactive({})

  let ws = null

  // ── Pipeline node definitions ──────────────────────────────────────────────
  const NODES = [
    { id: 'gpu',      label: 'GPU Check',         icon: '⚡', section: 1,  group: 'setup' },
    { id: 'config',   label: 'Constants',          icon: '⚙',  section: 3,  group: 'setup' },
    { id: 'core',     label: 'Core Functions',     icon: '🧮', section: 5,  group: 'setup' },
    { id: 'data',     label: 'Load Dataset',       icon: '📦', section: 7,  group: 'data'  },
    { id: 'hd',       label: 'HD Distances',       icon: '📐', section: 8,  group: 'data'  },
    { id: 'lbfgsb',   label: 'L-BFGS-B',          icon: '🔷', section: 9,  group: 'optim' },
    { id: 'sgd',      label: 'SGD',                icon: '🔹', section: 10, group: 'optim' },
    { id: 'momentum', label: 'Momentum',           icon: '🔸', section: 11, group: 'optim' },
    { id: 'adam100',  label: 'Adam lr=100',        icon: '💥', section: 12, group: 'optim' },
    { id: 'adamlr',   label: 'Adam lr Search',     icon: '⭐', section: 13, group: 'optim' },
    { id: 'summary',  label: 'Summary Table',      icon: '📊', section: 14, group: 'result'},
    { id: 'figs',     label: 'Plots & Figures',    icon: '🖼',  section: 19, group: 'result'},
    { id: 'save',     label: 'Save JSON',          icon: '💾', section: 21, group: 'result'},
  ]

  // Initialise node state
  NODES.forEach(n => {
    nodeState[n.id] = { status: 'idle', logs: [], result: null }
  })

  function sectionToNode(sec) {
    const map = {1:'gpu',3:'config',5:'core',7:'data',8:'hd',
                 9:'lbfgsb',10:'sgd',11:'momentum',12:'adam100',13:'adamlr',
                 14:'summary',19:'figs',20:'figs',21:'save'}
    return map[sec] || null
  }

  function addLog(nodeId, msg) {
    if (!nodeId) return
    nodeState[nodeId].logs.push(msg)
    if (nodeState[nodeId].logs.length > 100)
      nodeState[nodeId].logs.shift()
  }

  function setStatus(nodeId, status) {
    if (!nodeId) return
    nodeState[nodeId].status = status
  }

  // ── Session ────────────────────────────────────────────────────────────────
  async function initSession() {
    const r = await fetch(apiUrl('/api/session'), { method: 'POST' })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const d = await r.json()
    sessionId.value = d.session_id
    return d.session_id
  }

  async function fetchGpuStatus() {
    try {
      const r = await fetch(apiUrl('/api/gpu-status'))
      gpuInfo.value = await r.json()
    } catch { gpuInfo.value = { gpu_active: false, error: 'backend unreachable' } }
  }

  // ── Upload CSV ─────────────────────────────────────────────────────────────
  async function uploadFile(file) {
    let sid = sessionId.value || await initSession()
    const fd = new FormData(); fd.append('file', file)
    await fetch(apiUrl(`/api/session/${sid}/upload`), { method: 'POST', body: fd })
    addLog('data', `✓ Uploaded: ${file.name}`)
  }

  // ── Run experiment ─────────────────────────────────────────────────────────
  async function run(payload) {
    error.value = null
    // reset
    optimizerResults.value = []
    adamGrid.value = null
    //figures.value  = {}
    Object.keys(figures).forEach(k => delete figures[k])
    currentStep.value = null
    NODES.forEach(n => {
      nodeState[n.id].status = 'idle'
      nodeState[n.id].logs   = []
      nodeState[n.id].result = null
    })

    let sid = sessionId.value
    if (!sid) {
      try { sid = await initSession() }
      catch(e) { error.value = 'Cannot create session: ' + e.message; return }
    }

    running.value = true
    const url = wsUrl(`/ws/${sid}/run`)
    ws = new WebSocket(url)

    ws.onopen  = () => ws.send(JSON.stringify({ ...payload, session_id: sid }))
    ws.onerror = () => { error.value = 'WebSocket error — backend unreachable?'; running.value = false }
    ws.onclose = () => { running.value = false }

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      const nid = sectionToNode(msg.section)

      switch (msg.type) {
        case 'log':
          addLog(nid, msg.msg)
          setStatus(nid, 'running')
          currentStep.value = nid
          break
        case 'gpu_status':
          gpuInfo.value = msg.data
          setStatus('gpu', 'done')
          break
        case 'dataset_info':
          addLog('data', `N=${msg.N} | features=${msg.M}`)
          setStatus('data', 'done')
          setStatus('hd', 'running')
          break
        case 'optimizer_result': {
          const r = { optimizer: msg.optimizer, auc: msg.auc, time: msg.time }
          optimizerResults.value.push(r)
          const om = {'L-BFGS-B':'lbfgsb','SGD':'sgd','Momentum':'momentum'}
          const nid2 = om[msg.optimizer] || (msg.optimizer.includes('100') ? 'adam100' : 'adamlr')
          setStatus(nid2, 'done')
          nodeState[nid2].result = r
          break
        }
        case 'adam_sensitivity':
          adamGrid.value = { grid: msg.grid, best_lr: msg.best_lr }
          setStatus('adamlr', 'done')
          break
        case 'figure_ready':
          console.log('FIGURE KEY:', msg.key, '| URL:', msg.url)
          //figures.value = { ...figures.value, [msg.key]: apiUrl(msg.url) }
          figures[msg.key] = apiUrl(msg.url)
          break
        case 'done':
          setStatus('save', 'done')
          running.value = false
          break
        case 'error':
          error.value = msg.msg
          running.value = false
          break
      }
    }
  }

  function stop() { ws?.close(); running.value = false }

  return {
    sessionId, gpuInfo, running, error, currentStep,
    nodeState, optimizerResults, adamGrid, figures,
    NODES, initSession, fetchGpuStatus, uploadFile, run, stop
  }
}
