<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const API_BASE = 'http://127.0.0.1:8000'

const health = ref(null)
const query = ref('')
const question = ref('')
const docs = ref([])
const searchResults = ref([])
const answer = ref('')
const sources = ref([])
const selectedFile = ref(null)
const selectedDoc = ref(null)
const uploadMessage = ref('')
const loading = ref(false)
const error = ref('')
const displayMode = ref('browse')
const activeFolder = ref('all')
const activeTags = ref([])
const searchMode = ref('hybrid')
const searchAlpha = ref(0.5)
const inFolderOnly = ref(false)
const uploadChunkSize = ref(512)
const uploadOverlap = ref(50)
const uploadTags = ref([])
const uploadTagInput = ref('')
const uploadProgress = ref(0)
const uploadSteps = ref(['初始化', '分块处理', '向量化', '索引存储', '完成'])
const uploadCurrentStep = ref(0)
const uploadTagCardOpen = ref(false)
const fileContextMenu = ref({ open: false, x: 0, y: 0, doc: null })
const workspaceLoaded = ref(false)
const leftPanelWidth = ref(300)
const rightPanelWidth = ref(420)
const activeSplitter = ref(null)

const STORAGE_KEYS = {
  folders: 'knowledge-workbench-folders-v3',
  tags: 'knowledge-workbench-tags-v3',
  meta: 'knowledge-workbench-meta-v3',
}

const STATE_FIELDS_BY_KEY = {
  [STORAGE_KEYS.folders]: 'folders',
  [STORAGE_KEYS.tags]: 'tags',
  [STORAGE_KEYS.meta]: 'docMeta',
}

const defaultFolders = [
  { id: 'research', name: '研究资料', parentId: null },
  { id: 'notes', name: '笔记', parentId: null },
  { id: 'eeg', name: '脑电', parentId: 'research' },
  { id: 'transformer', name: 'Transformer', parentId: 'research' },
]

const defaultTags = ['脑电', 'Transformer', '待阅读', '已整理', 'RAG', '论文']

const folders = ref(readStoredJSON(STORAGE_KEYS.folders, defaultFolders))
const tagCatalog = ref(readStoredJSON(STORAGE_KEYS.tags, defaultTags))
const docMeta = ref(readStoredJSON(STORAGE_KEYS.meta, {}))
const uploadFolderId = ref('research')
const selectedDocIds = ref([])
const tagEditor = ref({ open: false, docIds: [], tags: [], newTag: '' })
const draggingPayload = ref(null)
const expandedFolders = ref({})

watch(
  folders,
  (value) => {
    saveStoredJSON(STORAGE_KEYS.folders, value)
  },
  { deep: true },
)

watch(
  tagCatalog,
  (value) => {
    saveStoredJSON(STORAGE_KEYS.tags, value)
  },
  { deep: true },
)

watch(
  docMeta,
  (value) => {
    saveStoredJSON(STORAGE_KEYS.meta, value)
  },
  { deep: true },
)

watch(
  activeFolder,
  (value) => {
    if (value !== 'all' && folders.value.some((folder) => folder.id === value)) {
      uploadFolderId.value = value
    }
  },
  { immediate: true },
)

watch(uploadFolderId, (value) => {
  if (value === 'all') return
  if (folders.value.some((folder) => folder.id === value) && activeFolder.value !== value) {
    activeFolder.value = value
  }
})

function readStoredJSON(key, fallback) {
  try {
    if (typeof localStorage === 'undefined') return fallback
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function saveStoredJSON(key, value) {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(value))
    }
  } catch {
    // ignore storage failures
  }

  if (!workspaceLoaded.value) return
  const field = STATE_FIELDS_BY_KEY[key]
  if (!field) return
  persistWorkspaceState({ [field]: value })
}

async function loadWorkspaceState() {
  const localState = {
    folders: readStoredJSON(STORAGE_KEYS.folders, defaultFolders),
    tags: readStoredJSON(STORAGE_KEYS.tags, defaultTags),
    docMeta: readStoredJSON(STORAGE_KEYS.meta, {}),
  }

  try {
    const response = await fetch(`${API_BASE}/workspace/state`)
    if (response.ok) {
      const state = await response.json()
      const hasBackendState =
        (Array.isArray(state.folders) && state.folders.length > 0) ||
        (Array.isArray(state.tags) && state.tags.length > 0) ||
        (state.docMeta && Object.keys(state.docMeta).length > 0)

      if (hasBackendState) {
        folders.value = Array.isArray(state.folders) ? state.folders : localState.folders
        tagCatalog.value = Array.isArray(state.tags) ? state.tags : localState.tags
        docMeta.value = state.docMeta && typeof state.docMeta === 'object' ? state.docMeta : localState.docMeta
        workspaceLoaded.value = true
        return
      }
    }
  } catch {
    // fall back to local storage
  }

  folders.value = localState.folders
  tagCatalog.value = localState.tags
  docMeta.value = localState.docMeta
  workspaceLoaded.value = true
  await persistWorkspaceState({ folders: folders.value, tags: tagCatalog.value, docMeta: docMeta.value })
}

async function persistWorkspaceState(partialState) {
  try {
    await fetch(`${API_BASE}/workspace/state`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(partialState),
    })
  } catch {
    // ignore sync failures
  }
}

function generateId(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

function normalizeText(value) {
  return String(value ?? '').toLowerCase()
}

function formatRequestError(err, fallbackMessage) {
  if (!(err instanceof Error)) return fallbackMessage
  const message = String(err.message ?? '').trim()
  if (!message) return fallbackMessage
  if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
    return '无法连接后端（http://127.0.0.1:8000），请先启动 FastAPI 后重试。'
  }
  return message
}

function highlightText(text, keyword) {
  if (!keyword || !text) return text
  const regex = new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return text.replace(regex, '<mark style="background:#FFF59D;color:#000;">$1</mark>')
}

function inferFileType(doc) {
  const source = String(doc?.source ?? '')
  const title = String(doc?.title ?? '')
  const target = `${source} ${title}`.toLowerCase()
  if (target.includes('.pdf')) return 'PDF'
  if (target.includes('.docx') || target.includes('.doc')) return 'Word'
  if (target.includes('.xlsx') || target.includes('.xls')) return 'Excel'
  if (target.includes('.md') || target.includes('markdown')) return 'Markdown'
  if (target.includes('.csv')) return 'CSV'
  if (target.includes('.json')) return 'JSON'
  if (target.includes('.txt')) return '文本'
  return '文档'
}

function folderChildren(parentId) {
  return folders.value
    .filter((folder) => folder.parentId === parentId)
    .sort((left, right) => left.name.localeCompare(right.name, 'zh-Hans-CN'))
}

function flattenFolders(parentId = null, depth = 0) {
  return folderChildren(parentId).flatMap((folder) => [{ ...folder, depth }, ...flattenFolders(folder.id, depth + 1)])
}

const folderTree = computed(() => flattenFolders())

function isFolderExpanded(folderId) {
  return expandedFolders.value[folderId] ?? true
}

function toggleFolderExpanded(folderId) {
  expandedFolders.value[folderId] = !isFolderExpanded(folderId)
}

function expandAllFolders() {
  const nextState = {}
  const walk = (parentId = null) => {
    folderChildren(parentId).forEach((folder) => {
      nextState[folder.id] = true
      walk(folder.id)
    })
  }
  walk()
  expandedFolders.value = nextState
}

function expandFolderPath(folderId) {
  let currentId = folderId
  while (currentId) {
    expandedFolders.value[currentId] = true
    currentId = parentFolderId(currentId)
  }
}

const visibleFolderTree = computed(() => {
  const walk = (parentId = null, depth = 0) =>
    folderChildren(parentId).flatMap((folder) => {
      const hasChildren = folderChildren(folder.id).length > 0
      const node = { ...folder, depth, hasChildren }
      if (!hasChildren || !isFolderExpanded(folder.id)) {
        return [node]
      }
      return [node, ...walk(folder.id, depth + 1)]
    })

  return walk()
})

function folderLabelById(folderId) {
  if (folderId === 'all') return '全部文档'
  const folder = folders.value.find((item) => item.id === folderId)
  return folder?.name ?? '未分类'
}

function folderPathById(folderId) {
  if (folderId === 'all') return '全部文档'
  const folder = folders.value.find((item) => item.id === folderId)
  if (!folder) return '未分类'
  const path = [folder.name]
  let parentId = folder.parentId
  while (parentId) {
    const parent = folders.value.find((item) => item.id === parentId)
    if (!parent) break
    path.unshift(parent.name)
    parentId = parent.parentId
  }
  return path.join('/')
}

function parentFolderId(folderId) {
  if (!folderId || folderId === 'all') return null
  return folders.value.find((item) => item.id === folderId)?.parentId ?? null
}

function isFolderDescendant(folderId, maybeAncestorId) {
  if (!folderId || !maybeAncestorId) return false
  let current = folders.value.find((item) => item.id === folderId)?.parentId
  while (current) {
    if (current === maybeAncestorId) return true
    current = folders.value.find((item) => item.id === current)?.parentId ?? null
  }
  return false
}

function folderFromDocument(doc) {
  const meta = docMeta.value[doc.id]
  return meta?.folderId ?? inferFolder(doc)
}

function inferFolder(doc) {
  const title = normalizeText(doc?.title)
  const source = normalizeText(doc?.source)
  const content = normalizeText(doc?.content)

  if (source.includes('seed://pipeline')) return 'research'
  if (source.includes('seed://architecture')) return 'notes'
  if (source.includes('seed://frontend')) return 'notes'
  if (title.includes('eeg') || content.includes('eeg') || source.includes('eeg')) return 'eeg'
  if (title.includes('transformer') || content.includes('transformer')) return 'transformer'
  return 'notes'
}

function inferTags(doc) {
  const text = `${doc?.title ?? ''} ${doc?.content ?? ''} ${doc?.source ?? ''}`.toLowerCase()
  const tags = []
  if (text.includes('eeg')) tags.push('脑电')
  if (text.includes('transformer')) tags.push('Transformer')
  if (text.includes('rag')) tags.push('RAG')
  if (text.includes('论文') || text.includes('paper') || text.includes('article')) tags.push('论文')
  if (text.includes('note') || text.includes('笔记')) tags.push('已整理')
  if (text.includes('todo') || text.includes('待') || text.includes('draft')) tags.push('待阅读')
  return [...new Set(tags)]
}

function normalizeTagList(tags) {
  return [...new Set((tags ?? []).map((tag) => String(tag).trim()).filter(Boolean))]
}

function stripAutoGeneratedTags(doc, tags) {
  const inferred = new Set(inferTags(doc))
  return normalizeTagList(tags).filter((tag) => !inferred.has(tag))
}

function syncAutoTagMigration(docList) {
  let changed = false
  docList.forEach((doc) => {
    const meta = docMeta.value[doc.id]
    if (!meta || !Array.isArray(meta.tags) || !meta.tags.length) return
    const cleanedTags = stripAutoGeneratedTags(doc, meta.tags)
    if (cleanedTags.length === meta.tags.length) return
    docMeta.value[doc.id] = { ...meta, tags: cleanedTags }
    changed = true
  })
  return changed
}

function ensureDocumentMeta(doc, extra = {}) {
  const current = docMeta.value[doc.id] ?? {}
  const merged = {
    folderId: current.folderId ?? extra.folderId ?? inferFolder(doc),
    tags: normalizeTagList([...(current.tags ?? []), ...(extra.tags ?? [])]),
    titleOverride: current.titleOverride ?? extra.titleOverride ?? '',
    indexed: current.indexed ?? true,
    fileType: current.fileType ?? extra.fileType ?? inferFileType(doc),
    hidden: current.hidden ?? false,
  }
  docMeta.value[doc.id] = merged
  return merged
}

function normalizeDocuments(list) {
  return list
    .map((doc) => {
      const meta = ensureDocumentMeta(doc)
      return {
        ...doc,
        title: meta.titleOverride || doc.title,
        folderId: meta.folderId,
        tags: meta.tags,
        indexed: meta.indexed,
        fileType: meta.fileType,
        hidden: meta.hidden,
      }
    })
    .filter((doc) => !doc.hidden)
}

function setDocumentMeta(documentId, patch) {
  const current = docMeta.value[documentId] ?? {}
  docMeta.value[documentId] = { ...current, ...patch }
}

function makeUniqueCopyTitle(title) {
  const baseTitle = String(title ?? '未命名文档').trim() || '未命名文档'
  const existingTitles = new Set(docs.value.map((doc) => String(doc.title ?? '').trim()))
  let index = 1
  let candidate = `${baseTitle} 副本`
  while (existingTitles.has(candidate)) {
    index += 1
    candidate = `${baseTitle} 副本 ${index}`
  }
  return candidate
}

function openFileContextMenu(doc, event) {
  event.preventDefault()
  event.stopPropagation()
  fileContextMenu.value = {
    open: true,
    x: event.clientX,
    y: event.clientY,
    doc,
  }
}

function closeFileContextMenu() {
  fileContextMenu.value = { open: false, x: 0, y: 0, doc: null }
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  const tempInput = document.createElement('input')
  tempInput.value = text
  tempInput.setAttribute('readonly', 'true')
  tempInput.style.position = 'fixed'
  tempInput.style.left = '-9999px'
  document.body.appendChild(tempInput)
  tempInput.select()
  document.execCommand('copy')
  document.body.removeChild(tempInput)
}

async function copyDocumentName(doc) {
  await copyTextToClipboard(doc.title || '未命名文档')
  uploadMessage.value = `已复制文件名：${doc.title || '未命名文档'}`
}

async function copyDocument(doc) {
  const sourceDoc = docs.value.find((item) => item.id === doc.id) ?? doc
  const response = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title: makeUniqueCopyTitle(sourceDoc.title),
      content: sourceDoc.content ?? '',
      source: sourceDoc.source ?? null,
    }),
  })

  if (!response.ok) {
    throw new Error('复制文件失败')
  }

  const created = await response.json()
  const sourceMeta = docMeta.value[sourceDoc.id] ?? {}
  setDocumentMeta(created.id, {
    folderId: sourceMeta.folderId ?? sourceDoc.folderId ?? folderFromDocument(sourceDoc),
    tags: normalizeTagList(sourceDoc.tags ?? sourceMeta.tags ?? []),
    titleOverride: '',
    indexed: true,
    fileType: sourceMeta.fileType ?? inferFileType(sourceDoc),
  })
  await Promise.all([fetchHealth(), loadDocuments()])
  uploadMessage.value = `已复制：${created.title}`
}

function addUploadTag() {
  const nextTag = uploadTagInput.value.trim()
  if (!nextTag) return
  if (!uploadTags.value.includes(nextTag)) {
    uploadTags.value.push(nextTag)
  }
  if (!tagCatalog.value.includes(nextTag)) {
    tagCatalog.value.push(nextTag)
  }
  uploadTagInput.value = ''
}

function toggleUploadTagCard() {
  uploadTagCardOpen.value = !uploadTagCardOpen.value
}

function closeUploadTagCard() {
  uploadTagCardOpen.value = false
}

function toggleUploadTag(tag) {
  const index = uploadTags.value.indexOf(tag)
  if (index >= 0) {
    uploadTags.value.splice(index, 1)
    return
  }
  uploadTags.value.push(tag)
}

function clearUploadTags() {
  uploadTags.value = []
}

function moveDocuments(docIds, folderId) {
  docIds.forEach((docId) => {
    setDocumentMeta(docId, { folderId })
  })
}

function clearSelection() {
  selectedDocIds.value = []
}

function toggleDocSelection(docId) {
  const index = selectedDocIds.value.indexOf(docId)
  if (index >= 0) {
    selectedDocIds.value.splice(index, 1)
  } else {
    selectedDocIds.value.push(docId)
  }
}

function openTagEditor(docIds) {
  const targetIds = docIds?.length ? docIds : [...selectedDocIds.value]
  if (!targetIds.length) {
    error.value = '请先选择至少一个文件。'
    return
  }
  const currentTags = targetIds.flatMap((docId) => docMeta.value[docId]?.tags ?? [])
  tagEditor.value = {
    open: true,
    docIds: targetIds,
    tags: [...new Set(currentTags)],
    newTag: '',
  }
}

function closeTagEditor() {
  tagEditor.value = { open: false, docIds: [], tags: [], newTag: '' }
}

function addTagToEditor() {
  const nextTag = tagEditor.value.newTag.trim()
  if (!nextTag) return
  if (!tagEditor.value.tags.includes(nextTag)) {
    tagEditor.value.tags.push(nextTag)
  }
  if (!tagCatalog.value.includes(nextTag)) {
    tagCatalog.value.push(nextTag)
  }
  tagEditor.value.newTag = ''
}

function toggleEditorTag(tag) {
  const index = tagEditor.value.tags.indexOf(tag)
  if (index >= 0) {
    tagEditor.value.tags.splice(index, 1)
  } else {
    tagEditor.value.tags.push(tag)
  }
}

function saveTagEditor() {
  tagEditor.value.docIds.forEach((docId) => {
    const meta = docMeta.value[docId] ?? {}
    docMeta.value[docId] = { ...meta, tags: [...new Set(tagEditor.value.tags)] }
  })
  closeTagEditor()
}

function createTag() {
  const next = prompt('请输入新标签名称')
  const name = next?.trim()
  if (!name) return
  if (tagCatalog.value.includes(name)) return
  tagCatalog.value.push(name)
}

function renameTag() {
  const oldName = prompt('请输入要重命名的标签')?.trim()
  if (!oldName || !tagCatalog.value.includes(oldName)) return
  const next = prompt('请输入新的标签名称', oldName)?.trim()
  if (!next || next === oldName) return
  tagCatalog.value = tagCatalog.value.map((tag) => (tag === oldName ? next : tag))
  Object.keys(docMeta.value).forEach((docId) => {
    const tags = docMeta.value[docId]?.tags ?? []
    if (tags.includes(oldName)) {
      docMeta.value[docId] = {
        ...docMeta.value[docId],
        tags: [...new Set(tags.map((tag) => (tag === oldName ? next : tag)))],
      }
    }
  })
}

function deleteTag() {
  const targets = activeTags.value.filter((tag) => tagCatalog.value.includes(tag))
  if (!targets.length) {
    error.value = '请先点击选择要删除的标签。'
    return
  }
  if (!confirm(`确认删除标签「${targets.join('、')}」？这些标签会从所有文件中移除。`)) return
  tagCatalog.value = tagCatalog.value.filter((tag) => !targets.includes(tag))
  Object.keys(docMeta.value).forEach((docId) => {
    const tags = docMeta.value[docId]?.tags ?? []
    docMeta.value[docId] = { ...docMeta.value[docId], tags: tags.filter((tag) => !targets.includes(tag)) }
  })
  activeTags.value = []
}

function mergeTags() {
  const source = prompt('请输入要合并的源标签')?.trim()
  const target = prompt('请输入目标标签')?.trim()
  if (!source || !target || source === target) return
  if (!tagCatalog.value.includes(source) || !tagCatalog.value.includes(target)) return
  tagCatalog.value = tagCatalog.value.filter((tag) => tag !== source)
  Object.keys(docMeta.value).forEach((docId) => {
    const tags = docMeta.value[docId]?.tags ?? []
    if (tags.includes(source)) {
      docMeta.value[docId] = {
        ...docMeta.value[docId],
        tags: [...new Set(tags.filter((tag) => tag !== source).concat(target))],
      }
    }
  })
}

function createFolder(parentId = null) {
  const name = prompt('请输入文件夹名称')?.trim()
  if (!name) return
  const id = generateId('folder')
  folders.value.push({ id, name, parentId: parentId === 'all' ? null : parentId })
  activeFolder.value = id
  uploadFolderId.value = id
}

function renameFolder(folderId) {
  const folder = folders.value.find((item) => item.id === folderId)
  if (!folder) return
  const next = prompt('请输入新的文件夹名称', folder.name)?.trim()
  if (!next) return
  folder.name = next
}

function deleteFolder(folderId) {
  const folder = folders.value.find((item) => item.id === folderId)
  if (!folder) return
  if (!confirm(`确认删除文件夹「${folder.name}」？其中的文件会移回上级目录。`)) return
  const parentId = folder.parentId ?? null
  folders.value = folders.value.filter((item) => item.id !== folderId)
  Object.keys(docMeta.value).forEach((docId) => {
    const meta = docMeta.value[docId]
    if (meta?.folderId === folderId || isFolderDescendant(meta?.folderId, folderId)) {
      docMeta.value[docId] = { ...meta, folderId: parentId ?? 'all' }
    }
  })
  folders.value = folders.value.map((item) => {
    if (item.parentId === folderId) return { ...item, parentId }
    return item
  })
  if (activeFolder.value === folderId) activeFolder.value = parentId ?? 'all'
  if (uploadFolderId.value === folderId) uploadFolderId.value = parentId ?? 'research'
}

function moveFolder(folderId, newParentId) {
  if (!folderId || folderId === newParentId) return
  if (isFolderDescendant(newParentId, folderId)) return
  folders.value = folders.value.map((item) =>
    item.id === folderId ? { ...item, parentId: newParentId === 'all' ? null : newParentId } : item,
  )
}

function deleteDocument(docId) {
  const doc = docs.value.find((item) => item.id === docId)
  const groupIds = doc ? documentGroupIds(doc) : [docId]
  const confirmLabel = groupIds.length > 1 ? `确认删除这个文件及其 ${groupIds.length} 个分块？` : '确认删除这个文件？'
  if (!confirm(confirmLabel)) return Promise.resolve()

  return Promise.all(groupIds.map((id) => fetch(`${API_BASE}/documents/${id}`, { method: 'DELETE' }))).finally(async () => {
    groupIds.forEach((id) => delete docMeta.value[id])
    selectedDocIds.value = selectedDocIds.value.filter((id) => !groupIds.includes(id))
    if (selectedDoc.value && groupIds.includes(selectedDoc.value.id)) {
      selectedDoc.value = null
    }
    await loadDocuments()
  })
}

async function deleteDocumentFromMenu(doc) {
  await deleteDocument(doc.id)
  closeFileContextMenu()
}

function renameDocument(doc) {
  const next = prompt('请输入新的文件名', doc.title)?.trim()
  if (!next) return
  setDocumentMeta(doc.id, { titleOverride: next })
  if (selectedDoc.value?.id === doc.id) {
    selectedDoc.value = { ...selectedDoc.value, title: next }
  }
}

function renameDocumentFromMenu(doc) {
  renameDocument(doc)
  closeFileContextMenu()
}

function handleFileContextAction(action) {
  const doc = fileContextMenu.value.doc
  if (!doc) return

  if (action === 'copyName') {
    copyDocumentName(doc)
      .then(() => closeFileContextMenu())
      .catch((err) => {
        error.value = formatRequestError(err, '复制文件名失败')
      })
    return
  }

  if (action === 'copy') {
    copyDocument(doc)
      .then(() => closeFileContextMenu())
      .catch((err) => {
        error.value = formatRequestError(err, '复制文件失败')
      })
    return
  }

  if (action === 'rename') {
    renameDocumentFromMenu(doc)
    return
  }

  if (action === 'delete') {
    deleteDocumentFromMenu(doc).catch((err) => {
      error.value = formatRequestError(err, '删除文件失败')
    })
  }
}

function setFolder(folderId) {
  activeFolder.value = folderId
  expandFolderPath(folderId)
}

function clearFilters() {
  activeFolder.value = 'all'
  activeTags.value = []
  displayMode.value = 'browse'
  expandAllFolders()
}

function toggleTag(tag) {
  const index = activeTags.value.indexOf(tag)
  if (index >= 0) {
    activeTags.value.splice(index, 1)
  } else {
    activeTags.value.push(tag)
  }
}

function countTag(tag) {
  return new Set(
    enrichedDocs.value
      .filter((doc) => (doc.tags ?? []).includes(tag))
      .map((doc) => documentGroupKey(doc)),
  ).size
}

function baseDocumentTitle(title) {
  return String(title ?? '').replace(/\s*\[\d+\/\d+\]$/, '').trim()
}

function displayDocumentTitle(title) {
  return baseDocumentTitle(title)
}

function documentGroupKey(doc) {
  const baseTitle = baseDocumentTitle(doc.title || '未命名文档')
  return `${doc.source || ''}||${baseTitle}`
}

function documentGroupIds(doc) {
  const targetKey = documentGroupKey(doc)
  return docs.value.filter((item) => documentGroupKey(item) === targetKey).map((item) => item.id)
}

function docsInFolder(folderId) {
  const grouped = new Map()
  enrichedDocs.value.forEach((doc) => {
    const docFolderId = doc.folderId ?? folderFromDocument(doc)
    if (docFolderId !== folderId) return

    const key = documentGroupKey(doc)
    const baseTitle = baseDocumentTitle(doc.title || '未命名文档')
    if (!grouped.has(key)) {
      grouped.set(key, { ...doc, title: baseTitle })
      return
    }

    const current = grouped.get(key)
    const currentScore = Number(current?.score ?? 0)
    const nextScore = Number(doc?.score ?? 0)
    if (nextScore > currentScore) {
      grouped.set(key, { ...doc, title: baseTitle })
    }
  })

  return Array.from(grouped.values()).sort((left, right) =>
    String(left.title || '').localeCompare(String(right.title || ''), 'zh-Hans-CN'),
  )
}

const enrichedDocs = computed(() => normalizeDocuments(docs.value))

const visibleDocs = computed(() => {
  const baseList = displayMode.value === 'search' && searchResults.value.length ? searchResults.value : enrichedDocs.value
  const filtered = baseList.filter((doc) => {
    const folderId = doc.folderId ?? folderFromDocument(doc)
    const folderMatch =
      activeFolder.value === 'all' || folderId === activeFolder.value || isFolderDescendant(folderId, activeFolder.value)
    const tagsMatch = activeTags.value.length === 0 || activeTags.value.every((tag) => (doc.tags || []).includes(tag))
    return folderMatch && tagsMatch
  })

  if (displayMode.value !== 'search') {
    return filtered
  }

  const deduped = []
  const seen = new Map()
  filtered.forEach((doc) => {
    const key = doc.source || doc.title || doc.id
    const current = seen.get(key)
    if (!current) {
      const next = { ...doc }
      seen.set(key, next)
      deduped.push(next)
      return
    }

    const currentScore = Number(current.score ?? 0)
    const nextScore = Number(doc.score ?? 0)
    if (nextScore > currentScore) {
      Object.assign(current, doc)
    }
  })

  return deduped
})

const activeFolderLabel = computed(() => folderLabelById(activeFolder.value))
const indexedDocCount = computed(() => new Set(docs.value.map((doc) => documentGroupKey(doc))).size)

async function fetchHealth() {
  const response = await fetch(`${API_BASE}/health`)
  health.value = await response.json()
}

async function loadDocuments() {
  const response = await fetch(`${API_BASE}/documents`)
  docs.value = normalizeDocuments(await response.json())
  syncAutoTagMigration(docs.value)
  if (!selectedDoc.value && docs.value.length) {
    selectedDoc.value = docs.value[0]
  }
}

function handleFileChange(event) {
  const target = event.target
  selectedFile.value = target.files?.[0] ?? null
  uploadMessage.value = selectedFile.value ? `Selected: ${selectedFile.value.name}` : ''
}

async function uploadDocument() {
  if (!selectedFile.value) {
    error.value = '请先选择一个文本文件。'
    return
  }

  loading.value = true
  error.value = ''
  uploadMessage.value = '初始化上传流程...'
  uploadProgress.value = 0
  uploadCurrentStep.value = 0

  try {
    const stepDurations = [600, 800, 1000, 800, 400]
    for (let step = 0; step < uploadSteps.value.length; step++) {
      uploadCurrentStep.value = step
      uploadProgress.value = ((step + 1) / uploadSteps.value.length) * 100
      await new Promise((resolve) => setTimeout(resolve, stepDurations[step]))
    }

    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('title', selectedFile.value.name.replace(/\.[^.]+$/, '') || selectedFile.value.name)
    formData.append('source', `folder://${folderPathById(uploadFolderId.value)}/${selectedFile.value.name}`)
    formData.append('chunk_size', uploadChunkSize.value)
    formData.append('overlap', uploadOverlap.value)

    const response = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || '上传请求失败')
    }

    const payload = await response.json()
    uploadMessage.value = `✓ ${payload.filename} 已完成上传，共 ${payload.chunks} 个分块。`
    payload.documents?.forEach((doc) => {
      ensureDocumentMeta(doc, {
        folderId: uploadFolderId.value === 'all' ? 'notes' : uploadFolderId.value,
        tags: uploadTags.value,
        indexed: true,
        fileType: inferFileType(doc),
      })
    })
    await Promise.all([fetchHealth(), loadDocuments()])
    clearUploadTags()
  } catch (err) {
    error.value = formatRequestError(err, '上传失败')
  } finally {
    loading.value = false
    uploadProgress.value = 100
    selectedFile.value = null
  }
}

async function runSearch() {
  loading.value = true
  error.value = ''
  try {
    let url = `${API_BASE}/search?q=${encodeURIComponent(query.value)}&top_k=5`
    if (inFolderOnly.value && activeFolder.value !== 'all') {
      url += `&folder=${encodeURIComponent(folderLabelById(activeFolder.value))}`
    }
    url += `&search_type=${searchMode.value}`
    if (searchMode.value === 'hybrid') {
      url += `&alpha=${searchAlpha.value}`
    }
    const response = await fetch(url)
    if (!response.ok) throw new Error('检索请求失败')
    const results = await response.json()
    searchResults.value = results.map((r) => ({
      ...r,
      snippet: r.content?.substring(0, 150) || r.content || '',
    }))
    displayMode.value = 'search'
  } catch (err) {
    error.value = formatRequestError(err, '检索失败')
  } finally {
    loading.value = false
  }
}

async function openDocument(doc) {
  selectedDoc.value = doc
  displayMode.value = 'browse'
  try {
    const response = await fetch(`${API_BASE}/documents`)
    if (response.ok) {
      const all = normalizeDocuments(await response.json())
      const found = all.find((d) => d.id === doc.id)
      if (found) selectedDoc.value = found
    }
  } catch {
    // keep current doc
  }
}

async function askQuestion() {
  loading.value = true
  error.value = ''
  try {
    const effectiveFolderFilter = inFolderOnly.value && activeFolder.value !== 'all' ? folderLabelById(activeFolder.value) : null
    const response = await fetch(`${API_BASE}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question: question.value,
        top_k: 3,
        search_type: searchMode.value,
        alpha: searchAlpha.value,
        folder_filter: effectiveFolderFilter,
      }),
    })
    if (!response.ok) throw new Error('问答请求失败')
    const payload = await response.json()
    answer.value = payload.answer
    sources.value = payload.sources
  } catch (err) {
    error.value = formatRequestError(err, '问答失败')
  } finally {
    loading.value = false
  }
}

function setUploadFolderToChild() {
  const baseFolderId = activeFolder.value === 'all' ? 'research' : activeFolder.value
  const childFolder = folderChildren(baseFolderId)[0]
  uploadFolderId.value = childFolder?.id ?? baseFolderId
}

function setUploadFolderToParent() {
  const parentId = parentFolderId(activeFolder.value)
  if (parentId) {
    uploadFolderId.value = parentId
    return
  }
  uploadFolderId.value = activeFolder.value === 'all' ? 'research' : activeFolder.value
}

function createUploadChildFolder() {
  createFolder(activeFolder.value === 'all' ? null : activeFolder.value)
}

function onFolderDragStart(folderId) {
  draggingPayload.value = { type: 'folder', folderId }
}

function onFolderDrop(targetFolderId) {
  const payload = draggingPayload.value
  if (!payload) return
  if (payload.type === 'folder') {
    moveFolder(payload.folderId, targetFolderId)
  }
  draggingPayload.value = null
}

function onDragEnd() {
  draggingPayload.value = null
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function stopSplitterDrag() {
  activeSplitter.value = null
  window.removeEventListener('mousemove', handleSplitterMove)
  window.removeEventListener('mouseup', stopSplitterDrag)
}

function handleSplitterMove(event) {
  if (!activeSplitter.value) return

  const minLeft = 220
  const minMiddle = 420
  const minRight = 300
  const gap = 18 * 2 + 20

  if (activeSplitter.value === 'left') {
    const maxLeft = Math.max(minLeft, window.innerWidth - rightPanelWidth.value - minMiddle - gap)
    leftPanelWidth.value = clamp(Math.round(event.clientX), minLeft, maxLeft)
    return
  }

  if (activeSplitter.value === 'right') {
    const maxRight = Math.max(minRight, window.innerWidth - leftPanelWidth.value - minMiddle - gap)
    rightPanelWidth.value = clamp(Math.round(window.innerWidth - event.clientX), minRight, maxRight)
  }
}

function startSplitterDrag(splitter, event) {
  if (event.button !== 0) return
  event.preventDefault()
  activeSplitter.value = splitter
  window.addEventListener('mousemove', handleSplitterMove)
  window.addEventListener('mouseup', stopSplitterDrag, { once: true })
}

onBeforeUnmount(() => {
  stopSplitterDrag()
})

onMounted(async () => {
  try {
    await loadWorkspaceState()
    await Promise.all([fetchHealth(), loadDocuments()])
  } catch {
    error.value = '后端尚未就绪，请先启动 FastAPI。'
  }
})
</script>

<template>
  <main class="shell">
    <section class="hero">
      <div class="hero-main">
        <div class="hero-title-row">
          <span class="hero-icon" aria-hidden="true">📚</span>
          <span class="hero-badge">本地优先</span>
        </div>
        <h1 class="hero-title">知识工作台</h1>
        <p class="hero-desc">一个精简的 Vue + FastAPI 起步项目，用于文档检索、引用问答和资料管理。</p>
        <p class="hero-status">📄 已索引 {{ indexedDocCount }} 篇文档 · 本地模式</p>
      </div>

      <div class="hero-actions" aria-label="占位操作区">
        <button class="hero-action" type="button" aria-label="搜索占位">🔍</button>
        <button class="hero-action hero-action-primary" type="button">新建</button>
        <button class="hero-action" type="button" aria-label="设置占位">⚙</button>
      </div>

    </section>

    <section
      class="workspace three-col"
      :style="{
        '--left-panel-width': `${leftPanelWidth}px`,
        '--right-panel-width': `${rightPanelWidth}px`,
      }"
    >
      <aside class="panel sidebar-panel" @click="closeTagEditor">
        <div class="panel-header sidebar-titlebar">
          <h3>目录</h3>
          <button class="mini" @click.stop="createFolder(activeFolder === 'all' ? null : activeFolder)">+ 文件夹</button>
        </div>
        <div class="folder-tree">
          <button class="tree-reset" :class="{ active: activeFolder === 'all' && activeTags.length === 0 }" @click="clearFilters">显示全部</button>
          <ul>
            <li v-for="folder in visibleFolderTree" :key="folder.id" :style="{ paddingLeft: `${folder.depth * 14}px` }">
              <div
                class="tree-node-wrap"
                :class="{ active: activeFolder === folder.id }"
                draggable="true"
                @dragstart="onFolderDragStart(folder.id)"
                @dragover.prevent
                @drop.prevent="onFolderDrop(folder.id)"
                @dragend="onDragEnd"
              >
                <button
                  v-if="folder.hasChildren"
                  class="tree-expander"
                  @click.stop="toggleFolderExpanded(folder.id)"
                  :title="isFolderExpanded(folder.id) ? '折叠子目录' : '展开子目录'"
                >
                  {{ isFolderExpanded(folder.id) ? '▾' : '▸' }}
                </button>
                <span v-else class="tree-expander-placeholder"></span>
                <button class="tree-node" :class="{ active: activeFolder === folder.id }" @click="setFolder(folder.id)">
                  <span class="tree-marker">{{ folder.depth ? '•' : '▣' }}</span>
                  <span>{{ folder.name }}</span>
                </button>
                <div class="tree-actions">
                  <span v-if="docsInFolder(folder.id).length" class="tree-doc-count">文件 {{ docsInFolder(folder.id).length }}</span>
                  <button class="mini" @click.stop="createFolder(folder.id)">+</button>
                  <button class="mini" @click.stop="renameFolder(folder.id)">改</button>
                  <button class="mini" @click.stop="deleteFolder(folder.id)">删</button>
                </div>
              </div>
              <ul v-if="isFolderExpanded(folder.id) && docsInFolder(folder.id).length" class="folder-doc-list">
                <li v-for="doc in docsInFolder(folder.id)" :key="`sidebar-${folder.id}-${doc.id}`" class="folder-doc-item">
                  <button
                    class="folder-doc-btn"
                    :class="{ active: selectedDoc?.id === doc.id }"
                    @click.stop="openDocument(doc)"
                    @contextmenu.prevent="openFileContextMenu(doc, $event)"
                    :title="doc.source || doc.title"
                  >
                    {{ displayDocumentTitle(doc.title) }}
                  </button>
                </li>
              </ul>
            </li>
          </ul>
        </div>

        <div class="panel-header tags-header sidebar-titlebar">
          <h3>标签</h3>
          <div class="tag-actions">
            <button class="mini" @click.stop="createTag">新建</button>
            <button class="mini" @click.stop="renameTag">重命名</button>
            <button class="mini" @click.stop="deleteTag">删除</button>
            <button class="mini" @click.stop="mergeTags">合并</button>
          </div>
        </div>
        <div class="tag-pills">
          <button
            v-for="tag in tagCatalog"
            :key="tag"
            class="tag"
            :class="{ active: activeTags.includes(tag) }"
            @click="toggleTag(tag)"
            @contextmenu.prevent="openTagEditor(visibleDocs.filter((doc) => (doc.tags || []).includes(tag)).map((doc) => doc.id))"
          >
            {{ tag }} <span class="count">{{ countTag(tag) }}</span>
          </button>
        </div>
      </aside>

      <div
        class="pane-splitter"
        role="separator"
        aria-orientation="vertical"
        title="拖动调整左侧宽度"
        @mousedown="startSplitterDrag('left', $event)"
      >
        <span></span>
      </div>

      <section class="panel middle-panel">
        <article class="panel search-panel">
          <label>
            上传文本文件
            <input type="file" accept=".txt,.md,.markdown,.csv,.json,.log,.pdf,.docx,.doc,.xlsx,.xls" @change="handleFileChange" />
          </label>

          <div class="upload-target-panel">
            <label>
              上传到文件夹
              <div class="upload-folder-row">
                <select v-model="uploadFolderId">
                  <option v-for="folder in folderTree" :key="folder.id" :value="folder.id">
                    {{ '　'.repeat(folder.depth) }}{{ folderPathById(folder.id) }}
                  </option>
                </select>
                <button class="secondary upload-submit" :disabled="loading" @click="uploadDocument">上传</button>
              </div>
            </label>
            <p class="upload-target-hint">直接在这里选择目标文件夹，或点击左侧目录同步切换。</p>
            <div class="upload-target-actions">
              <button class="mini" @click="setUploadFolderToParent">上级目录</button>
              <button class="mini" @click="setUploadFolderToChild">下级目录</button>
              <button class="mini" @click="createUploadChildFolder">新建子目录</button>
              <button class="mini" @click="toggleUploadTagCard">添加标签</button>
            </div>
          </div>

          <div v-if="uploadTagCardOpen" class="upload-tag-panel">
            <div class="upload-tag-card-header">
              <strong>添加标签</strong>
              <button class="mini" @click="closeUploadTagCard">收起</button>
            </div>

            <div class="upload-tag-row">
              <input v-model="uploadTagInput" type="text" placeholder="输入新标签后点击添加" @keyup.enter.prevent="addUploadTag" />
              <button class="mini" @click="addUploadTag">添加标签</button>
            </div>

            <div class="tag-pills upload-tag-pills">
              <button
                v-for="tag in tagCatalog"
                :key="tag"
                class="tag upload-tag"
                :class="{ active: uploadTags.includes(tag) }"
                @click="toggleUploadTag(tag)"
              >
                {{ tag }}
              </button>
              <button v-if="uploadTags.length" class="mini" @click="clearUploadTags">清空</button>
            </div>

            <p v-if="uploadTags.length" class="upload-tag-summary">本次上传将添加：{{ uploadTags.join('、') }}</p>
          </div>

          <div class="panel-header">
            <h2>检索</h2>
            <span>Chroma 向量检索</span>
          </div>

          <div class="filter-bar">
            <div>
              <span>当前目录：{{ activeFolderLabel }}</span>
              <div class="folder-hint">检索将包含当前目录及其子目录。</div>
            </div>
            <div>
              <span v-if="activeTags.length">标签：{{ activeTags.join(' + ') }}</span>
              <button v-if="activeFolder !== 'all' || activeTags.length" class="mini" @click="clearFilters">清除筛选</button>
            </div>
          </div>

          <label>
            检索词
            <input v-model="query" type="text" placeholder="本地优先检索" />
          </label>

          <div class="search-mode-section">
            <label>
              检索模式
              <select v-model="searchMode">
                <option value="hybrid">混合检索（语义+关键词）</option>
                <option value="vector">向量语义</option>
                <option value="keyword">关键词(BM25)</option>
              </select>
            </label>

            <label v-if="searchMode === 'hybrid'" class="weight-slider">
              权重 ({{ searchAlpha.toFixed(1) }})
              <input v-model.number="searchAlpha" type="range" min="0" max="1" step="0.1" />
              <div class="weight-hint">注：此数值表示语义向量检索（语义）所占比重。例如 0.7 表示语义占 70%，关键词占 30%。</div>
            </label>

            <!-- removed per UI decision: the folder-restriction checkbox was redundant -->
          </div>

          <div v-if="uploadProgress > 0 && uploadProgress < 100" class="upload-progress-section">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <p class="progress-text">处理中... {{ Math.round(uploadProgress) }}%</p>
            <div class="upload-steps">
              <div v-for="(step, idx) in uploadSteps" :key="idx" class="step" :class="{ done: idx <= uploadCurrentStep }">
                {{ step }}
              </div>
            </div>
          </div>

          

          <p v-if="uploadMessage" class="upload-message">{{ uploadMessage }}</p>

          <div class="actions">
            <button :disabled="loading" @click="runSearch">运行检索</button>
          </div>

          <div class="selection-toolbar" v-if="selectedDocIds.length">
            <span>已选择 {{ selectedDocIds.length }} 个文件</span>
            <button class="mini" @click="openTagEditor()">编辑标签</button>
            <button class="mini" @click="moveDocuments(selectedDocIds, activeFolder === 'all' ? uploadFolderId : activeFolder)">移动到当前目录</button>
            <button class="mini" @click="clearSelection">清除选择</button>
          </div>

          <div class="result-list">
            <article
              v-for="item in visibleDocs"
              :key="item.id"
              class="result-card"
              @click="openDocument(item)"
              @contextmenu.prevent="openFileContextMenu(item, $event)"
            >
              <div class="result-head">
                <label class="doc-select" @click.stop>
                  <input type="checkbox" :checked="selectedDocIds.includes(item.id)" @change="toggleDocSelection(item.id)" />
                  <span>{{ item.fileType }}</span>
                </label>
                <span class="indexed-state">{{ item.indexed ? '已向量索引' : '未索引' }}</span>
                <span v-if="item.score" class="relevance-score">{{ (item.score * 100).toFixed(0) }}%</span>
              </div>
              <div class="result-topline">
                <h3>{{ displayDocumentTitle(item.title) }}</h3>
              </div>
              <div v-if="item.snippet" class="snippet-preview" v-html="displayMode === 'search' ? highlightText(item.snippet, query) : item.snippet"></div>
              <p class="result-hint">点击「打开」或整条卡片即可在下方预览区查看全文。</p>
              <div class="inline-tags">
                <button v-for="tag in item.tags || []" :key="tag" class="inline-tag" @click.stop="toggleTag(tag)">
                  {{ tag }}
                </button>
                <button class="mini add-tag" @click.stop="openTagEditor([item.id])">+ 标签</button>
                <button class="mini" @click.stop="renameDocument(item)">改名</button>
                <button class="mini danger" @click.stop="deleteDocument(item.id)">删</button>
              </div>
              <div class="result-meta">
                <small>{{ item.source || '本地文档' }} · {{ folderLabelById(item.folderId || folderFromDocument(item)) }}</small>
                <button class="mini" @click.stop="openDocument(item)">打开</button>
              </div>
            </article>
          </div>

          <div class="preview-area">
            <h3>预览</h3>
            <div v-if="selectedDoc">
              <h4>{{ displayDocumentTitle(selectedDoc.title) }}</h4>
              <small>{{ selectedDoc.source || '本地文档' }} · {{ folderLabelById(selectedDoc.folderId || folderFromDocument(selectedDoc)) }}</small>
              <div class="doc-content">
                <pre>{{ selectedDoc.content }}</pre>
              </div>
            </div>
            <div v-else>
              <p>选择一个文档或检索结果，即可在此预览内容。</p>
            </div>
          </div>
        </article>
      </section>

      <div
        class="pane-splitter"
        role="separator"
        aria-orientation="vertical"
        title="拖动调整右侧宽度"
        @mousedown="startSplitterDrag('right', $event)"
      >
        <span></span>
      </div>

      <article class="panel qa-panel">
        <div class="panel-header">
          <h2>问答</h2>
          <span>检索 + 合成</span>
        </div>

        <label>
          问题
          <textarea v-model="question" rows="5" placeholder="这个知识工作台是怎么做检索的？"></textarea>
        </label>

        <div class="actions">
          <button class="secondary" :disabled="loading" @click="askQuestion">生成答案</button>
        </div>

        <div class="answer-card" v-if="answer">
          <h3>答案</h3>
          <p>{{ answer }}</p>
        </div>

        <div class="source-grid" v-if="sources.length">
          <article v-for="item in sources" :key="item.id" class="source-chip">
            <strong>{{ displayDocumentTitle(item.title) }}</strong>
            <span>{{ item.source || '本地文档' }}</span>
          </article>
        </div>
      </article>
    </section>

    <div v-if="fileContextMenu.open" class="context-menu-backdrop" @click="closeFileContextMenu">
      <div
        class="context-menu"
        :style="{ left: `${fileContextMenu.x}px`, top: `${fileContextMenu.y}px` }"
        @click.stop
      >
        <button class="context-menu-item" @click="handleFileContextAction('copyName')">复制文件名</button>
        <button class="context-menu-item" @click="handleFileContextAction('rename')">重命名</button>
        <button class="context-menu-item danger" @click="handleFileContextAction('delete')">删除</button>
      </div>
    </div>

    <div v-if="tagEditor.open" class="modal-backdrop" @click.self="closeTagEditor">
      <div class="modal-panel">
        <div class="panel-header">
          <h3>编辑标签</h3>
          <button class="mini" @click="closeTagEditor">关闭</button>
        </div>
        <p class="modal-desc">已选 {{ tagEditor.docIds.length }} 个文件，可勾选已有标签或输入新标签。</p>
        <div class="tag-pills modal-tags">
          <button
            v-for="tag in tagCatalog"
            :key="tag"
            class="tag"
            :class="{ active: tagEditor.tags.includes(tag) }"
            @click="toggleEditorTag(tag)"
          >
            {{ tag }}
          </button>
        </div>
        <div class="modal-inline">
          <input v-model="tagEditor.newTag" type="text" placeholder="输入新标签后点击添加" @keyup.enter="addTagToEditor" />
          <button class="mini" @click="addTagToEditor">添加</button>
        </div>
        <div class="actions modal-actions">
          <button class="secondary" @click="saveTagEditor">保存标签</button>
          <button class="mini" @click="closeTagEditor">取消</button>
        </div>
      </div>
    </div>

    <p v-if="error" class="error-banner">{{ error }}</p>
  </main>
</template>

<style scoped>
.shell {
  --panel: #f9f7f3;
  --panel-strong: #ffffff;
  --border: #dcd7ce;
  --text-main: #23211d;
  --text-sub: #6d665b;
  --accent: #2f7d78;
  --accent-soft: #dbeeea;
  --warning: #b35a5a;
  font-family: 'Source Han Sans SC', 'Noto Sans SC', 'Microsoft YaHei', 'PingFang SC', sans-serif;
  color: var(--text-main);
  min-height: 100vh;
  width: 100%;
  padding: 18px;
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 32px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid var(--border);
  border-radius: 22px;
}

.hero-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: #eff6ff;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  height: 24px;
  border-radius: 4px;
  margin: 0;
  font-size: 12px;
  font-weight: 400;
  color: #3b82f6;
  background: #eff6ff;
}

.hero-title {
  margin: 0;
  font-size: 24px;
  line-height: 1.3;
  font-weight: 600;
  color: #1e293b;
}

.hero-desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: #64748b;
}

.hero-status {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-action {
  min-width: 42px;
  height: 36px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--panel-strong);
  color: #1e293b;
  font-size: 14px;
  font-weight: 600;
}

.hero-action-primary {
  padding: 0 14px;
}

.workspace.three-col {
  display: grid;
  grid-template-columns: var(--left-panel-width) 10px minmax(0, 1fr) 10px var(--right-panel-width);
  gap: 14px;
}

.panel {
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--panel);
  box-shadow: 0 10px 30px rgba(50, 43, 30, 0.08);
  padding: 14px;
}

.sidebar-panel,
.middle-panel,
.qa-panel {
  height: calc(100vh - 190px);
  overflow: auto;
}

.sidebar-panel,
.middle-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.panel-header h2,
.panel-header h3,
.result-topline h3,
.preview-area h3,
.preview-area h4,
.answer-card h3 {
  margin: 0;
}

.panel-header span,
.result-meta small,
.modal-desc,
.result-hint,
.upload-target-hint {
  color: var(--text-sub);
}

button {
  border: 1px solid transparent;
  border-radius: 12px;
  padding: 9px 12px;
  background: var(--accent);
  color: #ffffff;
  cursor: pointer;
  font-weight: 700;
}

button.secondary {
  background: #1f6b66;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.mini {
  background: var(--panel-strong);
  border-color: var(--border);
  color: var(--text-main);
  padding: 6px 9px;
  font-weight: 600;
}

.mini:hover {
  background: #f0ece5;
}

.tree-actions,
.tag-actions,
.selection-toolbar,
.modal-inline,
.modal-actions,
.upload-target-actions,
.result-head,
.inline-tags,
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tree-doc-count {
  font-size: 12px;
  color: var(--text-sub);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--panel-strong);
}

.selection-toolbar,
.filter-bar {
  justify-content: space-between;
}

.folder-tree ul,
.folder-doc-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.tree-reset,
.tree-node,
.folder-doc-btn {
  width: 100%;
  text-align: left;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-main);
  padding: 8px;
}

.tree-node-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 12px;
}

.tree-node-wrap.active,
.tree-reset.active,
.tree-node.active,
.tag.active {
  background: var(--accent-soft);
}

.tree-expander,
.tree-expander-placeholder {
  width: 18px;
  min-width: 18px;
  height: 18px;
  padding: 0;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tree-expander {
  border: none;
  background: transparent;
  color: var(--text-sub);
}

.tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 7px;
}

.tree-marker {
  width: 14px;
  text-align: center;
  color: var(--text-sub);
}

.folder-doc-list {
  margin: 2px 0 8px;
  padding-left: 26px;
}

.folder-doc-btn {
  color: var(--text-sub);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-doc-btn.active {
  border-color: var(--border);
  background: #f0ede7;
  color: var(--text-main);
}

.tag-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag,
.inline-tag {
  background: var(--panel-strong);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-main);
  padding: 5px 10px;
  font-size: 13px;
}

.tag .count {
  margin-left: 6px;
  color: var(--text-sub);
}

label {
  display: block;
  color: var(--text-sub);
  font-weight: 600;
  margin-bottom: 10px;
}

input,
textarea,
select {
  width: 100%;
  margin-top: 6px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--panel-strong);
  color: var(--text-main);
  padding: 10px 11px;
  outline: none;
}

.upload-target-panel select {
  width: min(100%, 520px);
  max-width: 520px;
  min-height: 36px;
  padding: 6px 10px;
}

.upload-target-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.upload-folder-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
}

.upload-folder-row select {
  flex: 1;
  width: auto;
  max-width: none;
  margin-top: 0;
}

.upload-submit {
  flex: 0 0 auto;
  white-space: nowrap;
  padding-inline: 16px;
}

.upload-target-actions {
  align-items: flex-start;
}

.upload-tag-panel {
  margin-top: 4px;
  padding: 12px 12px 10px;
  border-top: 1px solid rgba(220, 215, 206, 0.9);
  background: rgba(255, 255, 255, 0.55);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-tag-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 2px;
}

.upload-tag-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.upload-tag-row input {
  margin-top: 0;
  flex: 1;
}

.upload-tag-pills {
  gap: 6px;
}

.upload-tag {
  padding: 4px 10px;
}

.upload-tag.active {
  background: var(--accent-soft);
}

.upload-tag-summary {
  margin: 0;
  font-size: 12px;
  color: var(--text-sub);
}

.weight-slider {
  margin-top: 6px;
}

.weight-slider input[type="range"] {
  width: 240px;
  margin-top: 6px;
}

.weight-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-sub);
}

.folder-hint {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-sub);
}

.folder-filter input[disabled] + * {
  opacity: 0.6;
}

input:focus,
textarea:focus,
select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(47, 125, 120, 0.13);
}

.pane-splitter {
  position: relative;
  border-radius: 99px;
  cursor: col-resize;
}

.pane-splitter::before {
  content: '';
  position: absolute;
  left: 3px;
  right: 3px;
  top: 0;
  bottom: 0;
  border-radius: inherit;
  background: rgba(109, 102, 91, 0.16);
}

.pane-splitter span {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 4px;
  height: 54px;
  border-radius: 99px;
  background: rgba(109, 102, 91, 0.35);
}

.search-panel {
  background: var(--panel-strong);
}

.search-mode-section,
.upload-target-panel,
.upload-progress-section,
.selection-toolbar,
.preview-area,
.answer-card,
.source-chip,
.result-card {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--panel-strong);
  padding: 11px;
}

.result-list,
.source-grid {
  display: grid;
  gap: 10px;
}

.result-head {
  font-size: 13px;
  margin-bottom: 6px;
  color: var(--text-sub);
}

.doc-select {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.relevance-score {
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 999px;
  padding: 2px 8px;
}

.snippet-preview {
  padding: 9px;
  margin-top: 8px;
  border-radius: 8px;
  background: #f5f2de;
  color: #4c463a;
  line-height: 1.5;
}

.snippet-preview :deep(mark) {
  background: #fff2a7;
  border-radius: 3px;
  padding: 0 2px;
}

.result-meta {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.preview-area {
  margin-top: 10px;
}

.doc-content {
  max-height: 420px;
  overflow: auto;
}

.doc-content pre {
  margin: 0;
  white-space: pre-wrap;
  color: #3f3a32;
}

.qa-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.upload-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.upload-steps .step {
  border-radius: 8px;
  border: 1px solid var(--border);
  padding: 3px 8px;
  font-size: 12px;
  color: var(--text-sub);
}

.upload-steps .step.done {
  border-color: transparent;
  background: var(--accent-soft);
  color: var(--accent);
}

.progress-bar {
  height: 6px;
  border-radius: 999px;
  background: #e9e4db;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6cb5a9, #2f7d78);
  transition: width 0.3s ease;
}

.progress-text,
.upload-message,
.result-hint,
.indexed-state {
  font-size: 13px;
  color: var(--text-sub);
}

.danger {
  border-color: #e1bbbb;
  color: var(--warning);
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(40, 34, 26, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 90;
}

.modal-panel {
  width: min(640px, 92vw);
  max-height: 80vh;
  overflow: auto;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: #fbf9f4;
  padding: 16px;
  box-shadow: 0 18px 40px rgba(40, 34, 26, 0.16);
}

.modal-actions {
  justify-content: flex-end;
}

.modal-inline input {
  flex: 1;
}

.error-banner {
  position: fixed;
  left: 16px;
  bottom: 16px;
  border: 1px solid #e1bbbb;
  background: #fff2f2;
  border-radius: 10px;
  color: #8f2f2f;
  padding: 10px 12px;
}

.context-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 120;
}

.context-menu {
  position: fixed;
  min-width: 140px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 16px 34px rgba(40, 34, 26, 0.16);
  padding: 6px;
  display: grid;
  gap: 4px;
  z-index: 121;
}

.context-menu-item {
  width: 100%;
  border: none;
  border-radius: 10px;
  padding: 8px 10px;
  text-align: left;
  background: transparent;
  color: var(--text-main);
}

.context-menu-item:hover {
  background: var(--accent-soft);
}

.context-menu-item.danger {
  color: var(--warning);
}

@media (max-width: 1200px) {
  .shell {
    padding: 12px;
  }

  .hero {
    flex-direction: column;
    align-items: stretch;
    padding: 20px;
    margin-bottom: 24px;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .workspace.three-col {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .pane-splitter {
    display: none;
  }

  .sidebar-panel,
  .middle-panel,
  .qa-panel {
    height: auto;
    max-height: none;
  }

  .upload-folder-row {
    flex-direction: column;
    align-items: stretch;
  }

  .upload-submit {
    width: 100%;
  }
}
</style>
