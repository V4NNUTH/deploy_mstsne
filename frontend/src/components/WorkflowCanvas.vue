<template>
  <div class="canvas-wrap" ref="canvasRef" @mousemove="onMouseMove" @mouseup="onMouseUp">

    <!-- SVG edges layer -->
    <svg class="edges-layer" :width="canvasW" :height="canvasH">
      <defs>
        <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4"
                markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M1 1L7 4L1 7" fill="none" stroke-width="1.5"
                stroke-linecap="round" stroke-linejoin="round"
                :stroke="'var(--edge-color)'"/>
        </marker>
        <marker id="arrow-active" viewBox="0 0 8 8" refX="7" refY="4"
                markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M1 1L7 4L1 7" fill="none" stroke-width="1.5"
                stroke-linecap="round" stroke-linejoin="round"
                stroke="#7367f0"/>
        </marker>
      </defs>

      <path v-for="edge in edges" :key="edge.id"
        :d="edgePath(edge)"
        fill="none"
        :stroke="isEdgeActive(edge) ? 'var(--edge-active)' : 'var(--edge-color)'"
        :stroke-width="isEdgeActive(edge) ? 2 : 1.5"
        :stroke-dasharray="isEdgeActive(edge) ? '0' : '5 4'"
        :marker-end="isEdgeActive(edge) ? 'url(#arrow-active)' : 'url(#arrow)'"
        :opacity="isEdgeActive(edge) ? 1 : 0.45"
        style="transition: stroke .3s, opacity .3s"
      />
    </svg>

    <!-- Nodes -->
    <div v-for="node in layoutNodes" :key="node.id"
      class="workflow-node"
      :class="[`node-${nodeState[node.id]?.status || 'idle'}`, { 'node-active': currentStep === node.id }]"
      :style="{ left: node.x + 'px', top: node.y + 'px' }"
      @mousedown="startDrag($event, node.id)"
      @click="selectNode(node.id)"
    >
      <!-- Status indicator -->
      <div class="node-status-dot" :class="`dot-${nodeState[node.id]?.status || 'idle'}`">
        <span v-if="nodeState[node.id]?.status === 'running'" class="dot-pulse"/>
      </div>

      <!-- Icon + label -->
      <div class="node-icon">{{ node.icon }}</div>
      <div class="node-body">
        <div class="node-label">{{ node.label }}</div>
        <div class="node-section mono">§{{ node.section }}</div>
      </div>

      <!-- Edit code button — always visible on hover -->
      <button v-if="hasCode(node.section)"
        class="node-edit-btn"
        @click.stop="$emit('edit-node', node.id)"
        title="Edit & run code">
        &lt;/&gt;
      </button>

      <!-- Result badge -->
      <div v-if="nodeState[node.id]?.result" class="node-result">
        <span class="badge badge-success mono" style="font-size:10px">
          {{ nodeState[node.id].result.auc?.toFixed(4) }}
        </span>
      </div>

      <!-- Running spinner -->
      <div v-if="nodeState[node.id]?.status === 'running'" class="node-spinner"/>
    </div>

    <!-- Group labels -->
    <div v-for="g in groupLabels" :key="g.id"
      class="group-label"
      :style="{ left: g.x + 'px', top: g.y + 'px' }">
      {{ g.label }}
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'

const props = defineProps({
  nodes: Array,
  nodeState: Object,
  currentStep: String,
})

//const emit = defineEmits(['select'])
const emit = defineEmits(['select', 'edit-node'])

const canvasRef = ref(null)
const canvasW   = ref(1200)
const canvasH   = ref(680)

// ── Layout — position nodes in a pipeline flow ──────────────────────────────
const GROUP_X = { setup: 60, data: 290, optim: 520, result: 860 }
const GROUP_LABEL = { setup: 'Setup', data: 'Data', optim: 'Optimizers', result: 'Results' }
const GROUP_Y_START = { setup: 100, data: 160, optim: 60, result: 160 }
const GROUP_SPACING = { setup: 110, data: 130, optim: 110, result: 130 }

const nodePositions = reactive({})

function hasCode(section) {
  return [1,3,5,6,7,8,9,10,11,12,13,14,19,21].includes(section)
}

const layoutNodes = computed(() => {
  const groupCounts = {}
  return props.nodes.map(n => {
    const g = n.group
    if (groupCounts[g] === undefined) groupCounts[g] = 0
    const idx = groupCounts[g]++
    const x = GROUP_X[g] || 60
    const y = (GROUP_Y_START[g] || 80) + idx * (GROUP_SPACING[g] || 110)
    if (!nodePositions[n.id]) nodePositions[n.id] = { x, y }
    return { ...n, x: nodePositions[n.id].x, y: nodePositions[n.id].y }
  })
})

const groupLabels = computed(() => {
  return Object.entries(GROUP_LABEL).map(([id, label]) => ({
    id, label,
    x: GROUP_X[id] || 60, y: 36
  }))
})

// ── Edges definition ─────────────────────────────────────────────────────────
const EDGES = [
  { id: 'e1',  from: 'gpu',      to: 'config'   },
  { id: 'e2',  from: 'config',   to: 'core'     },
  { id: 'e3',  from: 'core',     to: 'data'     },
  { id: 'e4',  from: 'data',     to: 'hd'       },
  { id: 'e5',  from: 'hd',       to: 'lbfgsb'   },
  { id: 'e6',  from: 'hd',       to: 'sgd'      },
  { id: 'e7',  from: 'hd',       to: 'momentum' },
  { id: 'e8',  from: 'hd',       to: 'adam100'  },
  { id: 'e9',  from: 'hd',       to: 'adamlr'   },
  { id: 'e10', from: 'lbfgsb',   to: 'summary'  },
  { id: 'e11', from: 'sgd',      to: 'summary'  },
  { id: 'e12', from: 'momentum', to: 'summary'  },
  { id: 'e13', from: 'adamlr',   to: 'summary'  },
  { id: 'e14', from: 'summary',  to: 'figs'     },
  { id: 'e15', from: 'figs',     to: 'save'     },
]

const edges = computed(() => EDGES)

function nodeCenter(nodeId) {
  const n = layoutNodes.value.find(n => n.id === nodeId)
  if (!n) return { x: 0, y: 0 }
  return { x: n.x + 90, y: n.y + 38 }
}

function edgePath(edge) {
  const s = nodeCenter(edge.from)
  const t = nodeCenter(edge.to)
  const dx = Math.abs(t.x - s.x)
  const cp = Math.max(40, dx * 0.45)
  return `M ${s.x} ${s.y} C ${s.x + cp} ${s.y}, ${t.x - cp} ${t.y}, ${t.x} ${t.y}`
}

function isEdgeActive(edge) {
  const fromSt = props.nodeState[edge.from]?.status
  const toSt   = props.nodeState[edge.to]?.status
  return fromSt === 'done' || toSt === 'running' || toSt === 'done'
}

// ── Drag ─────────────────────────────────────────────────────────────────────
let dragging = null
let dragOffset = { x: 0, y: 0 }

function startDrag(e, nodeId) {
  dragging = nodeId
  const n = layoutNodes.value.find(n => n.id === nodeId)
  dragOffset = { x: e.clientX - n.x, y: e.clientY - n.y }
  e.preventDefault()
}

function onMouseMove(e) {
  if (!dragging) return
  nodePositions[dragging] = {
    x: Math.max(0, e.clientX - dragOffset.x),
    y: Math.max(0, e.clientY - dragOffset.y),
  }
}

function onMouseUp() { dragging = null }

function selectNode(id) { emit('select', id) }

// ── Resize canvas ─────────────────────────────────────────────────────────────
const ro = new ResizeObserver(entries => {
  const r = entries[0].contentRect
  canvasW.value = r.width
  canvasH.value = r.height
})
onMounted(() => { if (canvasRef.value) ro.observe(canvasRef.value) })
onUnmounted(() => ro.disconnect())
</script>

<style scoped>
.canvas-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--vx-bg);
  background-image:
    radial-gradient(circle at 1px 1px, var(--vx-border-soft) 1px, transparent 0);
  background-size: 28px 28px;
  cursor: default;
  user-select: none;
}

.edges-layer {
  position: absolute;
  top: 0; left: 0;
  pointer-events: none;
  overflow: visible;
}

/* ── Node ── */
.workflow-node {
  position: absolute;
  width: 180px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--vx-bg-card);
  border: 1px solid var(--vx-border-soft);
  border-radius: 10px;
  cursor: grab;
  transition: border-color .2s, box-shadow .2s, background .2s;
  box-shadow: var(--vx-shadow-sm);
}
.workflow-node:hover {
  border-color: var(--vx-primary);
  box-shadow: 0 0 0 1px var(--vx-primary), var(--vx-shadow);
  z-index: 10;
}
.workflow-node:active { cursor: grabbing; }

.node-idle    { border-left: 3px solid var(--vx-border); }
.node-running { border-left: 3px solid var(--vx-warning); background: var(--node-running); }
.node-done    { border-left: 3px solid var(--vx-success); background: var(--node-done); }
.node-error   { border-left: 3px solid var(--vx-danger);  background: var(--node-error); }
.node-active  {
  border-color: var(--vx-primary);
  box-shadow: 0 0 0 2px var(--vx-primary-glow), var(--vx-shadow);
  z-index: 20;
}

.node-status-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  position: relative;
}
.dot-idle    { background: var(--vx-border); }
.dot-running { background: var(--vx-warning); }
.dot-done    { background: var(--vx-success); }
.dot-error   { background: var(--vx-danger); }

.dot-pulse {
  position: absolute; inset: -4px;
  border-radius: 50%;
  border: 2px solid var(--vx-warning);
  animation: pulse-ring 1.4s infinite;
}

.node-icon {
  font-size: 18px; flex-shrink: 0;
}

.node-body { flex: 1; min-width: 0; }
.node-label {
  font-size: 12px; font-weight: 600; color: var(--vx-text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.node-section { font-size: 10px; color: var(--vx-text-3); margin-top: 1px; }

.node-result { flex-shrink: 0; }

.node-spinner {
  position: absolute; top: 6px; right: 6px;
  width: 14px; height: 14px;
  border: 2px solid var(--vx-warning-dim);
  border-top-color: var(--vx-warning);
  border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Group labels ── */
.group-label {
  position: absolute;
  font-size: 10px; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--vx-text-3);
  pointer-events: none;
}

.node-edit-btn {
  position: absolute;
  top: 4px; right: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 9px; font-weight: 700;
  border: 1px solid var(--vx-border);
  background: var(--vx-bg);
  color: var(--vx-text3);
  cursor: pointer;
  opacity: 0;
  transition: opacity .15s, background .15s;
  font-family: 'IBM Plex Mono', monospace;
  z-index: 5;
}
.workflow-node:hover .node-edit-btn {
  opacity: 1;
}
.node-edit-btn:hover {
  background: var(--vx-primary-dim);
  color: var(--vx-primary-l);
  border-color: var(--vx-primary);
}
</style>
