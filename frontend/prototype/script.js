// 简单原型交互与 mock 数据
const folders = [
  {id:'f1',name:'全部文档'},
  {id:'f2',name:'项目资料'},
  {id:'f3',name:'论文'}
]

const tags = ['待办','读过','重要']

const mockResults = [
  {id:'d1',title:'EEG 研究论文',score:0.92,snippet:'Transformer 在 EEG 信号处理中的应用，展示了卷积-Transformer 协同的优势...',source:'EEG_paper.pdf',fullSnippet:'基于深度学习的脑电信号处理新方法——Transformer 在 EEG 信号处理中的应用，展示了卷积-Transformer 协同的优势'},
  {id:'d2',title:'项目计划说明',score:0.81,snippet:'项目背景与目标：本项目致力于构建一个高效的知识管理和检索平台...',source:'plan.md',fullSnippet:'项目背景与目标：本项目致力于构建一个高效的知识管理和检索平台，支持多模式检索和智能问答'}
]

const uploadSteps = ['初始化','分块处理','向量化','索引存储','完成']

function $(id){return document.getElementById(id)}

function renderFolders(){
  const el = $('folderList');
  el.innerHTML = '';
  folders.forEach(f=>{
    const li = document.createElement('li'); li.textContent = f.name; li.dataset.id=f.id;
    li.onclick = ()=>{ alert('点击目录: '+f.name) }
    el.appendChild(li);
  })
}

function renderTags(){
  const el=$('tagCloud'); el.innerHTML='';
  tags.forEach(t=>{const d=document.createElement('div');d.className='tag';d.textContent=t;el.appendChild(d)})
}

function renderResults(results){
  const list = $('resultsList'); list.innerHTML='';
  $('resultCount').textContent = results.length;
  results.forEach(r=>{
    const card = document.createElement('div'); card.className='result-card';
    const title = document.createElement('div'); title.className='result-title'; title.textContent = r.title;
    const score = document.createElement('div'); score.className='score'; score.textContent = (r.score*100).toFixed(0)+'%';
    const meta = document.createElement('div'); meta.className='result-meta'; meta.textContent = r.source;
    const snippet = document.createElement('div'); snippet.className='snippet'; 
    snippet.innerHTML = highlightSnippet(r.snippet, $('globalSearch').value);
    const ref = document.createElement('details'); 
    ref.innerHTML = '<summary>参考片段</summary><div style="padding:8px;color:#666;font-size:12px">'+r.fullSnippet+'</div>';
    card.appendChild(title); card.appendChild(score); card.appendChild(meta); card.appendChild(snippet); card.appendChild(ref);
    list.appendChild(card);
  })
}

function highlightSnippet(text, keyword) {
  if (!keyword) return text;
  const regex = new RegExp(`(${keyword})`, 'gi');
  return text.replace(regex, '<span class="highlight">$1</span>');
}

function setup(){
  renderFolders(); renderTags(); renderResults([]);
  $('globalSearch').addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ doSearch() } })
  $('uploadBtn').addEventListener('click', ()=>{ simulateUpload() })
  $('askBtn').addEventListener('click', ()=>{ doAsk() })
  
  // 权重滑块逻辑
  $('modeSelect').addEventListener('change', (e)=>{
    const show = e.target.value === 'hybrid';
    $('weightSlider').style.display = show ? 'flex' : 'none';
  })
  $('alphaSlide').addEventListener('input', (e)=>{
    $('alphaValue').textContent = e.target.value;
  })
}

function doSearch(){
  // 模拟根据检索模式返回结果
  const mode = $('modeSelect').value; console.log('search mode',mode);
  renderResults(mockResults);
}

function simulateUpload(){
  const config = $('uploadConfig');
  config.style.display = config.style.display === 'none' ? 'flex' : 'none';
  if(config.style.display === 'flex'){
    $('uploadBtn').textContent = '✓ 开始上传';
    let step = 0;
    $('uploadSteps').innerHTML = uploadSteps.map(s=>`<div class="step">${s}</div>`).join('');
    const interval = setInterval(()=>{
      step++;
      const steps = document.querySelectorAll('.step');
      if(step-1 < steps.length) steps[step-1].classList.add('done');
      const pct = Math.min((step/uploadSteps.length)*100, 100);
      $('progressText').textContent = pct<100 ? `处理中... ${Math.round(pct)}%` : '✓ 上传完成';
      if(step >= uploadSteps.length){ clearInterval(interval); $('uploadBtn').textContent = '上传文件' }
    }, 600);
  }
}

function doAsk(){
  const q = $('qaInput').value || '示例问题';
  $('answerArea').textContent = '生成中...';
  setTimeout(()=>{
    $('answerArea').textContent = '基于检索结果：在知识工作台的设计中，我们采用了三栏布局，以降低用户认知负荷。左栏用于目录与标签导航，中栏展示检索结果卡片，右栏提供问答交互。这样的设计参考了 Notion 与 AnythingLLM 等主流工具的最佳实践。';
    $('sources').style.display = 'block';
    $('sourcesList').innerHTML = '<li>📄 EEG 研究论文 (相关度 92%)</li><li>📄 项目计划说明 (相关度 81%)</li>';
  }, 1000);
}

window.addEventListener('DOMContentLoaded', setup);
