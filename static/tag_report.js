/*
Copyright © 2025 Sid Ahmed KHETTAB

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/agpl-3.0.html>.
*/

// Static JS for Tag Report page (no HTML <script> tags, no server-side templating inside)
// Globals expected: jQuery ($), Chart, optional window.markdownit

function tr(key, fallback) {
  return (window.TR_I18N && window.TR_I18N[key]) || fallback || key;
}

const projectName = (typeof window !== 'undefined' && window.TR_PROJECT_NAME) ? window.TR_PROJECT_NAME : '';
const annotationsPerPage = 10;
let currentPage = 1;
let totalAnnotations = 0;

function hexToRgb(hex) {
  const bigint = parseInt((hex || '').slice(1), 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return { r, g, b };
}

function getContrastTextColor(hexColor) {
  if (!hexColor) return '#000000';
  const rgb = hexToRgb(hexColor);
  const luminance = (0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b) / 255;
  return luminance > 0.5 ? '#000000' : '#FFFFFF';
}

function highlightText(text, start, end, backgroundColor) {
  if (start === undefined || end === undefined || text == null) return text || '';
  const textColor = getContrastTextColor(backgroundColor);
  const style = backgroundColor ? `background-color: ${backgroundColor}; color: ${textColor}; --highlight-text: ${textColor};` : '';
  return text.substring(0, start) + `<span class='highlight' style="${style}">${text.substring(start, end)}</span>` + text.substring(end);
}

function highlightDiffText(diffHtml, start, end, backgroundColor) {
  if (start === undefined || end === undefined || diffHtml == null) return diffHtml || '';
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = diffHtml;
  const textNodes = [];
  const walker = document.createTreeWalker(tempDiv, NodeFilter.SHOW_TEXT, null, false);
  while (walker.nextNode()) textNodes.push(walker.currentNode);
  let currentPos = 0;
  textNodes.forEach(textNode => {
    const textLength = textNode.nodeValue.length;
    const nodeStart = currentPos;
    const nodeEnd = currentPos + textLength;
    if (nodeEnd > start && nodeStart < end) {
      const localStart = Math.max(0, start - nodeStart);
      const localEnd = Math.min(textLength, end - nodeStart);
      const parent = textNode.parentNode;
      const frag = document.createDocumentFragment();
      if (localStart > 0) frag.appendChild(document.createTextNode(textNode.nodeValue.substring(0, localStart)));
      const span = document.createElement('span');
      span.style.backgroundColor = backgroundColor;
      span.style.color = getContrastTextColor(backgroundColor);
      span.textContent = textNode.nodeValue.substring(localStart, localEnd);
      frag.appendChild(span);
      if (localEnd < textLength) frag.appendChild(document.createTextNode(textNode.nodeValue.substring(localEnd)));
      parent.replaceChild(frag, textNode);
    }
    currentPos += textLength;
  });
  return tempDiv.innerHTML;
}

function buildTagTree(tags) {
  const tagMap = new Map();
  tags.forEach(tag => { tagMap.set(tag.id, { ...tag, children: [] }); });
  const tree = [];
  tagMap.forEach(tag => {
    if (tag.parent_tag_id) {
      const parent = tagMap.get(tag.parent_tag_id);
      if (parent) parent.children.push(tag); else tree.push(tag);
    } else tree.push(tag);
  });
  tree.forEach(tag => tag.children.sort((a,b)=> a.name.localeCompare(b.name)));
  tree.sort((a,b)=> a.name.localeCompare(b.name));
  return tree;
}

// Normalize data_type values coming from backend (manual vs auto annotations)
function normalizeDataType(dt) {
  if (!dt) return '';
  const s = String(dt).toLowerCase();
  if (s === 'wrong' || s === 'error_text' || s === 'error') return 'wrong';
  if (s === 'correct' || s === 'corrected' || s === 'corrected_text') return 'corrected';
  if (s === 'diff' || s === 'diff_text') return 'diff';
  return s;
}

function renderTagGroup(tag, annotationsByTag, container, level = 0) {
  const tagGroup = $(`<div class='tag-group' style='margin-left: ${level * 20}px;'></div>`);
  const hasChildren = tag.children.length > 0;
  const toggleIcon = hasChildren ? '<i class="fas fa-caret-down toggle-children"></i> ' : '';
  tagGroup.append(`<div class='tag-title'>${toggleIcon}${tag.name}</div>`);
  if (tag.description) tagGroup.append(`<div class='tag-description'>${tag.description}</div>`);
  const annotationsForTag = annotationsByTag[tag.name] ? annotationsByTag[tag.name].annotations : [];
  const annotationsContainer = $('<div class="annotations-container"></div>');
  annotationsForTag.forEach(annotation => {
    const dtype = normalizeDataType(annotation.data_type);
    let contextText, highlightedText;
    if (dtype === 'diff') {
      contextText = annotation.diff_text;
      highlightedText = highlightDiffText(contextText, annotation.start_offset, annotation.end_offset, tag.color);
    } else if (dtype === 'wrong') {
      contextText = annotation.error_text;
      highlightedText = highlightText(contextText, annotation.start_offset, annotation.end_offset, tag.color);
    } else { // 'corrected' (default)
      contextText = annotation.corrected_text;
      highlightedText = highlightText(contextText, annotation.start_offset, annotation.end_offset, tag.color);
    }
    const annotationElement = `
      <div class="annotation-context">
        <p><strong>${tr('pair_id','Pair ID')}:</strong> <a href="/comparison/${encodeURIComponent(projectName)}/${annotation.pair_id}">${annotation.pair_id}</a></p>
        <p><strong>${tr('context','Context')}:</strong> ${highlightedText}</p>
      </div>`;
    annotationsContainer.append(annotationElement);
  });
  tagGroup.append(annotationsContainer);
  const childrenContainer = $('<div class="children-container"></div>');
  tag.children.forEach(childTag => renderTagGroup(childTag, annotationsByTag, childrenContainer, level + 1));
  tagGroup.append(childrenContainer);
  container.append(tagGroup);
  if (hasChildren) {
    tagGroup.find('.toggle-children').on('click', function() {
      $(this).toggleClass('fa-caret-down fa-caret-right');
      childrenContainer.slideToggle();
    });
  }
}

function findTagInTree(tree, name) {
  if (!name) return null;
  for (const node of tree) {
    if ((node.name || '') === name) return node;
    if (node.children && node.children.length) {
      const found = findTagInTree(node.children, name);
      if (found) return found;
    }
  }
  return null;
}

function loadTags(tags, selectedTagName) {
  const filterSelect = $('#tag-filter');
  filterSelect.empty();
  filterSelect.append(`<option value="">${tr('all_tags','All Tags')}</option>`);
  const tagMap = new Map();
  tags.forEach(tag => { tagMap.set(tag.id, { ...tag, children: [] }); });
  const rootTags = [];
  tags.forEach(tag => {
    if (tag.parent_tag_id) {
      const parent = tagMap.get(tag.parent_tag_id);
      if (parent) parent.children.push(tagMap.get(tag.id)); else rootTags.push(tagMap.get(tag.id));
    } else rootTags.push(tagMap.get(tag.id));
  });
  rootTags.sort((a,b)=> a.name.localeCompare(b.name));
  rootTags.forEach(tag => tag.children.sort((a,b)=> a.name.localeCompare(b.name)));
  (function appendTagOptions(tagList, level){
    tagList.forEach(tag => {
      const prefix = "&nbsp;&nbsp;".repeat(level);
      filterSelect.append(`<option value="${tag.name}">${prefix}${tag.name}</option>`);
      if (tag.children.length > 0) appendTagOptions(tag.children, level + 1);
    });
  })(rootTags, 0);
  if (selectedTagName) {
    try { filterSelect.val(selectedTagName); } catch(e){}
  }
}

function loadAnnotations(tagFilter = '', dataTypeFilter = '', sortBy = 'pair_id', searchQuery = '', chartFilter = '') {
  const isAll = (!tagFilter && !dataTypeFilter && !searchQuery && !chartFilter);
  const offset = isAll ? 0 : (currentPage - 1) * annotationsPerPage;
  const limit = isAll ? 100000 : annotationsPerPage;
  // Expose current filters globally so other UI (e.g., Insights) can use them
  try {
    window.TR_ACTIVE_FILTERS = { tag: tagFilter, dtype: dataTypeFilter, sort: sortBy, search: searchQuery, chart: chartFilter };
    window.TR_CHART_FILTER = chartFilter || '';
  } catch(_) {}
  $.when(
    $.ajax({ url: `/api/tags?project_name=${encodeURIComponent(projectName)}`, type: 'GET' }),
    $.ajax({ url: `/api/annotations?project_name=${encodeURIComponent(projectName)}&tag_name=${encodeURIComponent(tagFilter)}&data_type=${encodeURIComponent(dataTypeFilter)}&search_query=${encodeURIComponent(searchQuery)}&limit=${limit}&offset=${offset}&chart_filter=${encodeURIComponent(chartFilter)}`, type: 'GET' })
  ).done(function(tagsResponse, annotationsResponse) {
    const tags = tagsResponse[0];
    let annotations = annotationsResponse[0].annotations;
    totalAnnotations = annotationsResponse[0].total;
    $('#total-annotations').text(totalAnnotations);
    const uniqueTagNames = new Set(annotations.map(ann => ann.tag_name));
    $('#unique-tags').text(uniqueTagNames.size);
    // Normalize data_type for consistent rendering and sorting
    annotations = annotations.map(a => ({ ...a, data_type: normalizeDataType(a.data_type) }));
    annotations.sort((a, b) => {
      if (sortBy === 'pair_id') return a.pair_id - b.pair_id;
      if (sortBy === 'start_offset') return a.start_offset - b.start_offset;
      return 0;
    });
    loadTags(tags, tagFilter);
    const reportContent = $('#tag-report-content');
    reportContent.empty();
    const annotationsByTag = {};
    annotations.forEach(annotation => {
      if (!annotationsByTag[annotation.tag_name]) {
        annotationsByTag[annotation.tag_name] = { description: annotation.tag_description, color: annotation.tag_color, annotations: [] };
      }
      annotationsByTag[annotation.tag_name].annotations.push(annotation);
    });
    const tagTree = buildTagTree(tags);
    const nodesToRender = (tagFilter && String(tagFilter).trim().length)
      ? (function(){ const n = findTagInTree(tagTree, tagFilter); return n ? [n] : []; })()
      : tagTree;
    nodesToRender.forEach(tag => renderTagGroup(tag, annotationsByTag, reportContent));
    window.currentAnnotations = annotations;
    if (isAll) {
      $('#pagination-controls').hide();
    } else {
      $('#pagination-controls').show();
      const totalPages = Math.ceil(totalAnnotations / annotationsPerPage) || 1;
      $('#page-info').text(`Page ${currentPage} of ${totalPages}`);
      $('#prev-page').prop('disabled', currentPage === 1);
      $('#next-page').prop('disabled', currentPage === totalPages || totalPages === 0);
    }
  }).fail(function(xhr, status, error) {
    console.error('Error loading data:', error);
  });
}

// Helpers to read current filters from the UI
function currentFilters(){
  return {
    tag: $('#tag-filter').val() || '',
    dtype: $('#data-type-filter').val() || '',
    sort: $('#sort-by').val() || 'pair_id',
    search: $('#search-input').val() || ''
  };
}

// Wire up filter controls and pagination on DOM ready
$(function(){
  function refresh(){
    const f = currentFilters();
    currentPage = 1;
    loadAnnotations(f.tag, f.dtype, f.sort, f.search);
  }

  $('#tag-filter').on('change', refresh);
  $('#data-type-filter').on('change', refresh);
  $('#sort-by').on('change', function(){
    const f = currentFilters();
    loadAnnotations(f.tag, f.dtype, f.sort, f.search);
  });
  // Debounced search
  let _searchTimer = null;
  $('#search-input').on('input', function(){
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(function(){
      const f = currentFilters();
      currentPage = 1;
      loadAnnotations(f.tag, f.dtype, f.sort, f.search);
    }, 300);
  });

  // Pagination controls
  $('#prev-page').on('click', function(){
    if (currentPage <= 1) return;
    currentPage -= 1;
    const f = currentFilters();
    loadAnnotations(f.tag, f.dtype, f.sort, f.search);
  });
  $('#next-page').on('click', function(){
    const totalPages = Math.ceil(totalAnnotations / annotationsPerPage) || 1;
    if (currentPage >= totalPages) return;
    currentPage += 1;
    const f = currentFilters();
    loadAnnotations(f.tag, f.dtype, f.sort, f.search);
  });

  // Initial load
  refresh();
});

function exportToCsv(filename, annotations) {
  const csvRows = [];
  csvRows.push(['Pair ID', 'Tag Name', 'Tag Description', 'Tag Color', 'Data Type', 'Error Text', 'Corrected Text', 'Start Offset', 'End Offset'].join(','));
  annotations.forEach(annotation => {
    const row = [
      `"${annotation.pair_id}"`,
      `"${annotation.tag_name}"`,
      `"${annotation.tag_description ? annotation.tag_description.replace(/"/g, '""') : ''}"`,
      `"${annotation.tag_color || ''}"`,
      `"${annotation.data_type || ''}"`,
      `"${annotation.error_text ? annotation.error_text.replace(/"/g, '""') : ''}"`,
      `"${annotation.corrected_text ? annotation.corrected_text.replace(/"/g, '""') : ''}"`,
      `"${annotation.start_offset || ''}"`,
      `"${annotation.end_offset || ''}"`
    ];
    csvRows.push(row.join(','));
  });
  const csvString = csvRows.join('\n');
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  if (link.download !== undefined) {
    link.setAttribute('href', URL.createObjectURL(blob));
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } else {
    window.open('data:text/csv;charset=utf-8,' + encodeURIComponent(csvString));
  }
}

// Notes Report rendering in Tag Report page
const md = (window.markdownit ? window.markdownit() : { render: (t)=>t });
function loadNotesReportTR() {
  const container = $('#notes-report-content');
  if (!container.length) return;
  // Do not load report automatically, wait for button click
  // container.html('<p class="text-secondary" style="color:#65676b">Refreshing analysis...</p>');
  // $.ajax({
  //   url: `/api/generate_notes_report/${encodeURIComponent(projectName)}`,
  //   type: 'GET',
  //   success: function(resp) {
  //     const text = (resp && resp.report) ? String(resp.report).trim() : '';
  //     if (!text) container.html('<p class="text-secondary" style="color:#65676b">No content.</p>');
  //     else { try { container.html(md.render(text)); } catch(e) { container.text(text); } }
  //   },
  //   error: function() { container.html('<p class="text-secondary" style="color:#65676b">No content.</p>'); }
  // });
}

// NLP Summary charts
let charts = {};
function _mkBar(ctx, labels, wrong, correct, title){
  if (charts[ctx]) { charts[ctx].destroy(); }
  const el = document.getElementById(ctx);
  if (!el) return;
  charts[ctx] = new Chart(el.getContext('2d'), {
    type: 'bar',
    data: { labels, datasets: [ { label: tr('wrong_label','Wrong'), backgroundColor: '#e53e3e', data: wrong }, { label: tr('correct_label','Correct'), backgroundColor: '#3182ce', data: correct } ] },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: title } },
      scales: { x: { stacked: false }, y: { beginAtZero: true } },
      onClick: (e) => {
        const activePoints = charts[ctx].getElementsAtEventForMode(e, 'nearest', { intersect: true }, true);
        if (activePoints.length > 0) {
          const clickedIndex = activePoints[0].index;
          const label = charts[ctx].data.labels[clickedIndex];
          loadAnnotations(label);
        }
      }
    }
  });
}
function _mkHBar(ctx, labels, data, title, colors){
  if (charts[ctx]) { charts[ctx].destroy(); }
  const el = document.getElementById(ctx);
  if (!el) return;
  charts[ctx] = new Chart(el.getContext('2d'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Δ (Correct - Wrong)', backgroundColor: (colors||'#805ad5'), data }] },
    options: { indexAxis: 'y', responsive: true, plugins: { title: { display: true, text: title } }, scales: { x: { beginAtZero: true } } }
  });
}
function _mkPie(ctx, labels, values, title){
  if (charts[ctx]) { charts[ctx].destroy(); }
  const el = document.getElementById(ctx);
  if (!el) return;
  charts[ctx] = new Chart(el.getContext('2d'), {
    type: 'pie',
    data: { labels, datasets: [{ data: values, backgroundColor: ['#3182ce','#e53e3e','#38a169','#dd6b20','#805ad5','#a0aec0','#4a5568','#319795','#b83280','#ed8936'] }] },
    options: { responsive: true, plugins: { title: { display: true, text: title } } }
  });
}

function _topKMap(mapObj, k=12){
  const entries = Object.entries(mapObj || {});
  entries.sort((a,b)=> (b[1]||0)-(a[1]||0));
  return entries.slice(0,k);
}

function loadNlpSummary(){
  $('.chart-loading-spinner').show();
  $.ajax({
    url: `/api/nlp_summary/${encodeURIComponent(projectName)}`,
    type: 'GET',
    success: function(resp){
      try{
        // Helper to extract entries list (new API) or fallback to legacy simple counts
        function asEntries(cat){
          if (!cat) return [];
          if (Array.isArray(cat.entries)) return cat.entries;
          // legacy: build entries from simple counts
          const wrong = (cat.wrong||cat.simple_counts?.wrong)||{};
          const correct = (cat.correct||cat.simple_counts?.correct)||{};
          const labels = Array.from(new Set([...Object.keys(wrong), ...Object.keys(correct)]));
          return labels.map(l=>({
            label: l,
            wrong_count: wrong[l]||0,
            correct_count: correct[l]||0,
            wrong_rate: wrong[l]||0,
            correct_rate: correct[l]||0,
            delta_rate: (correct[l]||0) - (wrong[l]||0),
            log_odds: 0, z: 0, p: 1, q: 1,
            paired:{n_pairs:0,mean_delta_rate:0,se:0,ci_low:0,ci_high:0}
          }));
        }
        function topByAbs(arr, field, k){
          return arr.slice().sort((a,b)=> Math.abs((b[field]||0)) - Math.abs((a[field]||0))).slice(0,k);
        }

        // POS: top by |z|, plot rates per 1k
        const posEntries = asEntries(resp.pos);
        const posTopE = topByAbs(posEntries, 'z', 12);
        _mkBar('chart-pos', posTopE.map(e=>e.label), posTopE.map(e=>e.wrong_rate), posTopE.map(e=>e.correct_rate), tr('pos_rates_title','POS Rates per 1k (Wrong vs Correct)'));

        // Dependencies: rates per 1k
        const depEntries = asEntries(resp.dep);
        const depTopE = topByAbs(depEntries, 'z', 12);
        _mkBar('chart-dep', depTopE.map(e=>e.label), depTopE.map(e=>e.wrong_rate), depTopE.map(e=>e.correct_rate), tr('dep_rates_title','Dependencies per 1k (Wrong vs Correct)'));

        // Dependency delta (rate delta)
        const depDeltaLabels = depTopE.map(e=>e.label);
        const depDeltaVals = depTopE.map(e=> e.delta_rate || (e.correct_rate - e.wrong_rate));
        const depDeltaColors = depDeltaVals.map(v=> v>=0 ? '#805ad5' : '#e53e3e');
        _mkHBar('chart-dep-delta', depDeltaLabels, depDeltaVals, tr('dep_delta_title','Dependencies Δ (Correct - Wrong)'), depDeltaColors);

        // Entities: rates per 1k
        const entEntries = asEntries(resp.ent);
        const entTopE = topByAbs(entEntries, 'z', 8);
        _mkBar('chart-entities-wc', entTopE.map(e=>e.label), entTopE.map(e=>e.wrong_rate), entTopE.map(e=>e.correct_rate), tr('entities_rates_title','Entities per 1k (Wrong vs Correct)'));
        const edata = entTopE.map(e=> e.delta_rate || (e.correct_rate - e.wrong_rate));
        const ecolors = edata.map(v=> v>=0 ? '#805ad5' : '#e53e3e');
        _mkHBar('chart-entities-delta', entTopE.map(e=>e.label), edata, 'Entities Δ (Correct - Wrong)', ecolors);

        // Tense and Number: rates per 1k
        const teEntries = asEntries(resp.tense);
        const teTopE = topByAbs(teEntries, 'z', 8);
        _mkBar('chart-tense', teTopE.map(e=>e.label), teTopE.map(e=>e.wrong_rate), teTopE.map(e=>e.correct_rate), 'Tense per 1k (Wrong vs Correct)');

        const nuEntries = asEntries(resp.number);
        const nuTopE = topByAbs(nuEntries, 'z', 6);
        _mkBar('chart-number', nuTopE.map(e=>e.label), nuTopE.map(e=>e.wrong_rate), nuTopE.map(e=>e.correct_rate), 'Number per 1k (Wrong vs Correct)');

        const ed = resp.edits||{};
        const lab = ['added','deleted','replaced'];
        const vals = lab.map(k=> ed[k]||0);
        _mkPie('chart-edits', lab, vals, 'Surface Edits');

        // Dependency slope chart (top-10 by |z|) — per-1k rates before→after
        (function(){
          const el = document.getElementById('chart-dep-slope'); if (!el) return;
          const top = depTopE.slice(0,10);
          const labels = ['Wrong','Correct'];
          if (charts['chart-dep-slope']) charts['chart-dep-slope'].destroy();
          const datasets = top.map((e, idx) => {
            const color = `hsl(${(idx*37)%360},70%,50%)`;
            return {
              label: e.label,
              data: [{x: 'Wrong', y: e.wrong_rate||0}, {x: 'Correct', y: e.correct_rate||0}],
              borderColor: color,
              backgroundColor: color,
              fill: false,
              tension: 0,
            };
          });
          charts['chart-dep-slope'] = new Chart(el.getContext('2d'), {
            type: 'line',
            data: { labels, datasets },
            options: {
              responsive: true,
              maintainAspectRatio: true,
              aspectRatio: 2,
              plugins: {
                title: { display: true, text: 'Top Dependencies: Slope (rates per 1k)' },
                legend: { display: true, position: 'right' },
                tooltip: {
                  callbacks: {
                    label: function(ctx){
                      const dsLabel = ctx.dataset && ctx.dataset.label ? ctx.dataset.label : '';
                      const x = ctx.parsed.x; const y = ctx.parsed.y;
                      return `${dsLabel}: ${x} → ${y.toFixed(2)}`;
                    }
                  }
                }
              },
              scales: { y: { beginAtZero: true } }
            }
          });
          // Render a simple legend list with color chips under the chart for clarity
          try {
            const container = el.parentElement;
            if (container) {
              const legendId = 'chart-dep-slope-legend';
              const old = container.querySelector(`#${legendId}`);
              if (old) old.remove();
              const legend = document.createElement('div');
              legend.id = legendId;
              legend.style.marginTop = '8px';
              legend.style.display = 'flex';
              legend.style.flexWrap = 'wrap';
              legend.style.gap = '8px 12px';
              datasets.forEach(ds => {
                const item = document.createElement('div');
                item.style.display = 'flex';
                item.style.alignItems = 'center';
                const chip = document.createElement('span');
                chip.style.display = 'inline-block';
                chip.style.width = '12px';
                chip.style.height = '12px';
                chip.style.borderRadius = '2px';
                chip.style.backgroundColor = ds.borderColor || '#666';
                chip.style.marginRight = '6px';
                const label = document.createElement('span');
                label.textContent = ds.label || '';
                item.appendChild(chip);
                item.appendChild(label);
                legend.appendChild(item);
              });
              container.appendChild(legend);
            }
          } catch(_) {}
        })();

        // Dependency volcano plot (effect size vs reliability)
        (function(){
          const el = document.getElementById('chart-dep-volcano'); if (!el) return;
          const pts = depEntries.map(e => ({
            x: e.log_odds || 0,
            y: (e.q>0 ? -Math.log10(e.q) : 0),
            r: Math.min(8, 3 + Math.min(200, Math.abs(e.delta_rate||0)) / 10),
            label: e.label,
            up: (e.delta_rate||0) >= 0
          }));
          if (charts['chart-dep-volcano']) charts['chart-dep-volcano'].destroy();
          charts['chart-dep-volcano'] = new Chart(el.getContext('2d'), {
            type: 'scatter',
            data: {
              datasets: [{
                label: tr('dep_volcano_dataset_label','Dependencies'),
                data: pts.map(p => ({x: p.x, y: p.y})),
                pointRadius: pts.map(p => p.r),
                pointBackgroundColor: pts.map(p => p.up ? '#805ad5' : '#e53e3e'),
              }]
            },
            options: {
              responsive: true,
              plugins: {
                title: { display: true, text: tr('dep_volcano_title','Dependency Volcano (effect vs reliability)') },
                tooltip: {
                  callbacks: {
                    label: function(ctx){
                      const i = ctx.dataIndex; const p = pts[i];
                      return `${p.label}: log-odds=${p.x.toFixed(2)}, -log10(q)=${p.y.toFixed(2)}`;
                    }
                  }
                }
              },
              scales: { x: { title: { display: true, text: tr('dep_volcano_x_title','Log-odds (Correct vs Wrong)') } }, y: { title: { display: true, text: tr('dep_volcano_y_title','-log10(q)') } } }
            }
          });
        })();
      } catch(e){ console.error('Failed to render NLP summary', e); }
      $('.chart-loading-spinner').hide();
    },
    error: function(){
      console.error(tr('failed_fetch_nlp','Failed to fetch NLP summary'));
      $('.chart-loading-spinner').hide();
      $('.col-md-6, .col-md-12').each(function() {
        $(this).find('canvas').hide();
        $(this).append(`<div class="chart-error-message">${tr('failed_load_chart_data','Failed to load chart data.')}</div>`);
      });
    }
  });
}

// Event bindings
$(document).ready(function() {
  loadAnnotations();
  $('#tag-filter, #data-type-filter, #sort-by').on('change', function() {
    currentPage = 1;
    loadAnnotations($('#tag-filter').val(), $('#data-type-filter').val(), $('#sort-by').val(), $('#search-input').val());
  });
  $('#search-input').on('keyup', function() {
    currentPage = 1;
    loadAnnotations($('#tag-filter').val(), $('#data-type-filter').val(), $('#sort-by').val(), $(this).val());
  });
  $('#prev-page').on('click', function() {
    if (currentPage > 1) {
      currentPage--;
      loadAnnotations($('#tag-filter').val(), $('#data-type-filter').val(), $('#sort-by').val(), $('#search-input').val());
    }
  });
  $('#next-page').on('click', function() {
    const totalPages = Math.ceil(totalAnnotations / annotationsPerPage);
    if (currentPage < totalPages) {
      currentPage++;
      loadAnnotations($('#tag-filter').val(), $('#data-type-filter').val(), $('#sort-by').val(), $('#search-input').val());
    }
  });
  $('#export-csv-btn').on('click', function() {
    const filename = `tag_report_${projectName}.csv`;
    exportToCsv(filename, window.currentAnnotations || []);
  });
  $(document).on('click', '.export-chart-item', function(e){
    e.preventDefault();
    const chartId = $(this).data('chart');
    const format = $(this).data('format');
    const chart = charts[chartId];
    if (!chart) return;
    const title = (chart.options && chart.options.plugins && chart.options.plugins.title && chart.options.plugins.title.text) || chartId;
    const payload = {
      project_name: projectName,
      chart_id: chartId,
      title: title,
      labels: chart.data.labels,
      datasets: (chart.data.datasets || []).map(d => ({ label: d.label || '', data: d.data }))
    };
    const url = `/api/export_chart/${format}`;
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(function(resp){
      if (!resp.ok) throw new Error('export_failed');
      const disposition = resp.headers.get('Content-Disposition') || '';
      return resp.blob().then(function(blob){ return { blob, disposition }; });
    })
    .then(function(result){
      const blob = result.blob;
      const disposition = result.disposition || '';
      let filename = `${projectName}_${chartId}.${format}`;
      const match = /filename=\"?([^\";]+)\"?/i.exec(disposition);
      if (match) filename = match[1];
      const link = document.createElement('a');
      const objUrl = window.URL.createObjectURL(blob);
      link.href = objUrl; link.download = filename;
      document.body.appendChild(link); link.click();
      setTimeout(function(){ document.body.removeChild(link); window.URL.revokeObjectURL(objUrl); }, 0);
    })
    .catch(function(){
      alert(tr('export_failed','Failed to export chart.'));
    });
  });
  // Tab switching
  $('.analysis-tab-btn').on('click', function(){
    const tab = $(this).data('tab');
    $('.analysis-tab-btn').removeClass('active');
    $(this).addClass('active');
    $('.analysis-tab-content').removeClass('active').hide();
    $(`.analysis-tab-content[data-tab="${tab}"]`).addClass('active').show();
    if (tab === 'nlp') {
      // loadNlpSummary(); // Removed automatic loading
    }
    else if (tab === 'notes') {
      // loadNotesReportTR(); // Removed automatic loading
    }
  });
  // Notes refresh
  $('#refresh-notes-report').on('click', function(){ loadNotesReportTR(); });
  // NLP refresh
  $('#refresh-nlp-summary').on('click', function(){ loadNlpSummary(); });
  // NLP LLM report
  $('#nlp-llm-report-btn').on('click', function(e){
    e.preventDefault();
    const $btn = $(this);
    const box = $('#nlp-llm-report');
    box.show().html(`<p class="text-secondary" style="color:#65676b">${tr('generating_report','Generating report...')}</p>`);
    try { box[0].scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch(_) {}
    const originalHtml = $btn.html();
    $btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i>');
    $.ajax({
      url: `/api/nlp_visual_report/${encodeURIComponent(projectName)}`,
      type: 'GET',
      success: function(resp){
        const text = (resp && resp.report) ? String(resp.report) : '';
        // Normalize headings and lists to ensure proper Markdown rendering
        const norm = (function(t){
          try {
            let s = String(t || '').trim();
            // Normalize headings without altering inline hyphens (e.g., "Correct - Wrong")
            s = s.replace(/\s*#\s/g, '\n# ');
            s = s.replace(/\s*##\s/g, '\n\n## ');
            s = s.replace(/\s*###\s/g, '\n\n### ');
            // Do NOT convert inline hyphens to bullet lists
            s = s.replace(/\n{3,}/g, '\n\n');
            return s.trim();
          } catch(_) { return t; }
        })(text);
        try { box.html(md.render(norm)); } catch(e) { box.text(norm); }
        try { box[0].scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch(_) {}
        $btn.prop('disabled', false).html(originalHtml);
      },
      error: function(){
        box.html(`<p class="text-secondary" style="color:#65676b">${tr('failed_generate_report','Failed to generate report.')}</p>`);
        $btn.prop('disabled', false).html(originalHtml);
      }
    });
  });
  // If the NLP tab is active on load, initialize
  // if ($('.analysis-tab-btn.active').data('tab') === 'nlp') {
  //   loadNlpSummary();
  // }
});
