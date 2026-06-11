<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="sidebar-brand">
      <div class="brand-icon">
        <span>t</span>
      </div>
      <div class="brand-text">
        <div class="brand-name">Ms t-SNE</div>
        <div class="brand-sub">Optimizer Explorer</div>
      </div>
    </div>

    <div class="divider" style="margin: 8px 16px;"/>

    <!-- Nav -->
    <nav class="sidebar-nav">
      <div class="nav-section-label">Main</div>
      <a v-for="item in navItems" :key="item.id"
        class="nav-item" :class="{ active: active === item.id }"
        @click="$emit('navigate', item.id)">
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
        <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
      </a>
    </nav>

    <!-- GPU status -->
    <div class="sidebar-footer">
      <div class="gpu-card" :class="gpuInfo?.gpu_active ? 'gpu-on' : 'gpu-off'">
        <div class="gpu-icon">{{ selectedDevice === 'gpu' ? '⚡' : '🖥' }}</div>
        <div class="gpu-info">
          <div class="gpu-name">{{ gpuInfo?.gpu_name || 'No GPU' }}</div>
          <div class="gpu-vram" v-if="gpuInfo?.vram_free_gb && selectedDevice === 'gpu'">
            {{ gpuInfo.vram_free_gb }}GB free
          </div>
        </div>
        <div class="gpu-dot" :class="selectedDevice === 'gpu' && gpuInfo?.gpu_active ? 'dot-on' : 'dot-off'"/>
      </div>

      <!-- Device toggle -->
      <div class="device-toggle">
        <button
          v-for="d in ['gpu','cpu']" :key="d"
          class="device-btn"
          :class="{ active: selectedDevice === d, disabled: d === 'gpu' && !gpuInfo?.gpu_active }"
          :disabled="d === 'gpu' && !gpuInfo?.gpu_active"
          @click="selectDevice(d)">
          {{ d === 'gpu' ? '⚡ GPU' : '🖥 CPU' }}
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, watch } from 'vue'

defineProps({ active: String, gpuInfo: Object })
defineEmits(['navigate', 'device-change'])

const navItems = [
  { id: 'workflow',  icon: '⬡', label: 'Workflow',  },
  { id: 'configure', icon: '⚙',  label: 'Configure', },
  { id: 'results',   icon: '📊', label: 'Results',   },
  { id: 'figures',   icon: '🖼',  label: 'Figures',   },
  { id: 'codeeditor', icon: '⌨',   label: 'Code Editor', },
]

const selectedDevice = ref('gpu')

watch(() => props.gpuInfo?.gpu_active, (active) => {
  if (!active) selectedDevice.value = 'cpu'
})

function selectDevice(d) {
  selectedDevice.value = d
  emit('device-change', d)
}

</script>

<style scoped>
.sidebar {
  width: 230px; flex-shrink: 0;
  background: var(--vx-bg-card);
  border-right: 1px solid var(--vx-border-soft);
  display: flex; flex-direction: column;
  height: 100vh;
}

.sidebar-brand {
  display: flex; align-items: center; gap: 12px;
  padding: 20px 18px 14px;
}
.brand-icon {
  width: 34px; height: 34px; border-radius: 8px;
  background: var(--vx-primary);
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 800; color: #fff;
  box-shadow: 0 4px 12px var(--vx-primary-glow);
}
.brand-name { font-size: 15px; font-weight: 700; letter-spacing: -.01em; }
.brand-sub  { font-size: 10px; color: var(--vx-text-3); letter-spacing: .04em; text-transform: uppercase; }

.sidebar-nav { flex: 1; padding: 8px 10px; }
.nav-section-label {
  font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  color: var(--vx-text-3); padding: 8px 8px 6px;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px; border-radius: 8px; margin-bottom: 2px;
  cursor: pointer; transition: all .15s; color: var(--vx-text-2);
  text-decoration: none; font-size: 13px; font-weight: 500;
}
.nav-item:hover { background: var(--vx-bg-hover); color: var(--vx-text); }
.nav-item.active {
  background: var(--vx-primary-dim);
  color: var(--vx-primary-light);
}
.nav-icon  { font-size: 16px; width: 20px; text-align: center; }
.nav-label { flex: 1; }
.nav-badge {
  font-size: 10px; padding: 1px 7px; border-radius: 10px;
  background: var(--vx-primary-dim); color: var(--vx-primary-light);
}

.sidebar-footer { padding: 12px 14px 16px; }
.gpu-card {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 10px; border: 1px solid var(--vx-border-soft);
}
.gpu-on  { background: rgba(40,199,111,.07); border-color: rgba(40,199,111,.25); }
.gpu-off { background: rgba(255,255,255,.03); }
.gpu-icon { font-size: 16px; }
.gpu-name { font-size: 11px; font-weight: 600; color: var(--vx-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 110px; }
.gpu-vram { font-size: 10px; color: var(--vx-text-3); margin-top: 1px; }
.gpu-dot  { width: 7px; height: 7px; border-radius: 50%; margin-left: auto; flex-shrink: 0; }
.dot-on   { background: var(--vx-success); box-shadow: 0 0 6px var(--vx-success); }
.dot-off  { background: var(--vx-text-3); }
</style>
