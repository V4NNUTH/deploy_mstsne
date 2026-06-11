<template>
  <div class="editor-page">
    <CodeEditorSidebar
      :visible="true"
      :initialNodeId="initialNodeId || nodes[0]?.id"
      :nodes="nodes"
      :nodeState="nodeState"
      :sessionId="sessionId"
      :inline="true"
      @close="() => {}"
    />
  </div>
</template>

<script setup>
import CodeEditorSidebar from '../components/CodeEditorSidebar.vue'
defineProps({ nodes: Array, nodeState: Object, sessionId: String, initialNodeId: String })
</script>

<style scoped>
.editor-page { height: 100%; display: flex; overflow: hidden; }
</style>