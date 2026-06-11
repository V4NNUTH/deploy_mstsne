<template>
  <div class="app-shell">
    <!-- Sidebar -->
    <AppSidebar :active="page" :gpuInfo="gpuInfo"
      @navigate="page = $event"
      @device-change="selectedDevice = $event"/>

    <!-- Main content -->
    <div class="app-main">

      <!-- ── Workflow page ── -->
      <div v-if="page === 'workflow'" class="workflow-page">
        <div class="workflow-topbar">
          <div class="topbar-left">
            <span class="topbar-title">Pipeline Workflow</span>
            <span v-if="currentStep" class="badge badge-warning" style="margin-left:10px">
              ◉ Running §{{ NODES.find(n=>n.id===currentStep)?.section }}
              — {{ NODES.find(n=>n.id===currentStep)?.label }}
            </span>
            <span v-else-if="!running && optimizerResults.length" class="badge badge-success" style="margin-left:10px">
              ✓ Completed — {{ optimizerResults.length }} optimizers
            </span>
          </div>
          <div class="topbar-right">
            <span v-if="error" class="badge badge-danger" style="margin-right:10px">{{ error }}</span>
            <button class="btn btn-ghost btn-sm" @click="page='configure'">⚙ Configure</button>
            <button class="btn btn-primary btn-sm" :class="{ pulse: running }"
              @click="running ? stop() : page='configure'">
              {{ running ? '⏹ Stop' : '▶ Run' }}
            </button>
          </div>
        </div>

        <div class="canvas-area" :class="{ 'panel-open': selectedNode }">
          <WorkflowCanvas
            :nodes="NODES"
            :nodeState="nodeState"
            :currentStep="currentStep"
            @select="onSelectNode"
            @edit-node="editingNodeId = $event"
          />
          <NodePanel
            v-if="selectedNode"
            :node="selectedNode"
            :state="nodeState[selectedNode.id]"
            :sessionId="sessionId"
            @close="selectedNode = null"
          />
        </div>
      </div>

      <!-- ── Configure page ── -->
      <div v-else-if="page === 'configure'" class="page-content">
        <ConfigurePage
          :running="running"
          :onUpload="uploadFile"
          @run="handleRun"
          @stop="stop"
        />
      </div>

      <!-- ── Results page ── -->
      <div v-else-if="page === 'results'" class="page-content">
        <ResultsPage
          :optimizerResults="optimizerResults"
          :adamGrid="adamGrid"
          :sessionId="sessionId"
        />
      </div>

      <!-- ── Figures page ── -->
      <div v-else-if="page === 'figures'" class="page-content">
        <FiguresPage :figures="figures"/>
      </div>

      <!-- ── Code Editor page ── -->
      <div v-else-if="page === 'codeeditor'" class="page-content">
        <CodeEditorPage
          :nodes="NODES"
          :nodeState="nodeState"
          :sessionId="sessionId"
          :initialNodeId="editingNodeId"
        />
      </div>

    </div>

    <!-- ── Code editor sidebar — outside app-main so it overlays everything ── -->
    <CodeEditorSidebar
      :visible="!!editingNodeId"
      :initialNodeId="editingNodeId"
      :nodes="NODES"
      :nodeState="nodeState"
      :sessionId="sessionId"
      @close="editingNodeId = null"
    />

  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import CodeEditorPage from './pages/CodeEditorPage.vue'
import AppSidebar        from './components/AppSidebar.vue'
import WorkflowCanvas    from './components/WorkflowCanvas.vue'
import NodePanel         from './components/NodePanel.vue'
import CodeEditorSidebar from './components/CodeEditorSidebar.vue'
import ConfigurePage     from './pages/ConfigurePage.vue'
import ResultsPage       from './pages/ResultsPage.vue'
import FiguresPage       from './pages/FiguresPage.vue'
import { useExperiment } from './composables/useExperiment.js'

const page          = ref('workflow')
const selectedNode  = ref(null)
const editingNodeId = ref(null)
const selectedDevice = ref('gpu')

const {
  sessionId, gpuInfo, running, error, currentStep,
  nodeState, optimizerResults, adamGrid, figures,
  NODES, initSession, fetchGpuStatus, uploadFile, run, stop
} = useExperiment()

onMounted(async () => {
  await fetchGpuStatus()
  await initSession().catch(() => {})
})

function onSelectNode(nodeId) {
  const node = NODES.find(n => n.id === nodeId)
  selectedNode.value = selectedNode.value?.id === nodeId ? null : node
}

watch(editingNodeId, (id) => {
  if (id) page.value = 'codeeditor'
})

async function handleRun(cfg) {
  page.value = 'workflow'
  selectedNode.value = null
  await run({ ...cfg, device: selectedDevice.value })
}

watch(running, (val, oldVal) => {
  if (!val && oldVal && optimizerResults.value.length) {
    // experiment completed
  }
})
</script>

<style>
html, body, #app { height: 100%; }
</style>

<style scoped>
.app-shell {
  display: flex; height: 100vh; overflow: hidden; position: relative;
}
.app-main {
  flex: 1; overflow: hidden; display: flex; flex-direction: column;
}
.workflow-page { display: flex; flex-direction: column; height: 100%; }
.workflow-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 20px;
  background: var(--vx-bg-card);
  border-bottom: 1px solid var(--vx-border-soft);
  flex-shrink: 0;
}
.topbar-left  { display: flex; align-items: center; }
.topbar-right { display: flex; align-items: center; gap: 8px; }
.topbar-title { font-size: 14px; font-weight: 600; }
.canvas-area  { flex: 1; position: relative; overflow: hidden; display: flex; }
.page-content { flex: 1; overflow: hidden; }
</style>