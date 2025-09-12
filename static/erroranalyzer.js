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

// Initialize markdown-it
const md = window.markdownit({ html: true });

let chatHistoryQueue = [];
const MAX_HISTORY_LENGTH = 3;

let visibleTags = new Set();
// Exploration toggle for selecting text in Wrong Text card
let exploreSelectionActive = false;
// Selected model for AI (Flash/Pro)
let selectedModel = (function(){
    try { return localStorage.getItem('ea_model') || 'gemini-2.5-flash'; } catch(e){ return 'gemini-2.5-flash'; }
})();

function updateAnnotationVisibility() {
    const anns = document.querySelectorAll('.annotation-span');
    // If no filters active, ensure all annotation styles are visible
    if (visibleTags.size === 0) {
        anns.forEach(el => el.classList.remove('annotation-hidden'));
        return;
    }
    anns.forEach(el => {
        const tagId = (el.dataset && el.dataset.tagId) ? String(el.dataset.tagId) : '';
        if (tagId && visibleTags.has(tagId)) {
            el.classList.remove('annotation-hidden');
        } else {
            // Hide only the annotation styling, not the underlying text
            el.classList.add('annotation-hidden');
        }
    });
}

function toggleTagVisibility(event) {
    event.stopPropagation();
    const btn = event.currentTarget; // button.tag-visibility-toggle
    const tagId = btn.dataset.tagId;

    if (visibleTags.has(tagId)) {
        visibleTags.delete(tagId);
        btn.classList.remove('active');
    } else {
        visibleTags.add(tagId);
        btn.classList.add('active');
    }
    updateAnnotationVisibility();
    updateVisibilityToggleUI();
}

function updateVisibilityToggleUI() {
    const buttons = document.querySelectorAll('.tag-visibility-toggle');
    buttons.forEach(b => {
        const tid = String(b.dataset.tagId);
        const isActive = visibleTags.has(tid);
        b.classList.toggle('active', isActive);
        const iconEl = b.querySelector('i');
        if (iconEl) {
            iconEl.className = `fas ${isActive ? 'fa-eye' : 'fa-eye-slash'}`;
        }
        b.title = isActive ? 'Filtering by this tag' : 'Show only this tag';
    });
}

// i18n helper
function i18nLabel(key, fallback) {
    try {
        if (window.I18N && typeof window.I18N[key] === 'string' && window.I18N[key].length) {
            return window.I18N[key];
        }
    } catch (_) {}
    return fallback;
}

// Function to get the class based on the operation type
function getOperationClass(operation) {
    switch (operation) {
        case 'deleted':
            return 'deleted';
        case 'replaced':
            return 'replaced';
        case 'added':
            return 'added';
        case 'replacedby':
            return 'replacedby';
        case 'unchanged':
            return 'unchanged';
        default:
            return '';
    }
}

function showElementsByPairId(pairId, wrongData, correctData, diffData) {
    console.log("Showing elements for pairId:", pairId);

    const container = $('#text-comparison-container');
    container.empty(); // Clear previous content

    // Create and append Wrong Text section
    const wrongTextHtml = `
        <div class="text-section">
            <div class="text-section-header">
                <h4>
                    ${i18nLabel('wrongText', 'Wrong Text')}
                    <button id="explore-wrong-btn" class="icon-button" title="Explore/Select Text">
                        <i class="fas fa-compass"></i>
                    </button>
                </h4>
            </div>
            <div id="result_wrong_${pairId}" class="text-card">${concatenateElements(wrongData, pairId, 'wrong')}</div>
        </div>`;
    container.append(wrongTextHtml);

    // Create and append Correct Text section
    const correctTextHtml = `
        <div class="text-section">
            <div class="text-section-header">
                <h4>${i18nLabel('correctText', 'Correct Text')}</h4>
            </div>
            <div id="result_correct_${pairId}" class="text-card">${concatenateElements(correctData, pairId, 'correct')}</div>
        </div>`;
    container.append(correctTextHtml);

    // Create and append Diff View section
    const diffTextHtml = `
        <div class="text-section">
            <div class="text-section-header">
                <h4>${i18nLabel('diffView', 'Diff View')}</h4>
            </div>
            <div id="result_diff_${pairId}" class="diff-view text-card">${concatenateElements(diffData, pairId, 'diff')}</div>
        </div>`;
    container.append(diffTextHtml);

    // Re-apply visual tags after new content is loaded
    applyVisualTags();
    loadAndDisplayAnnotations();
    loadChatHistory(pairId);
    loadNotes(pairId);
    loadLinguisticAnalysis(pairId);
    // Load NER analysis alongside the main analysis so the NER tab is present after reload
    try { loadNerAnalysis(pairId); } catch (e) { console.warn('Failed to start NER load', e); }

    // Initialize explore button state and handler
    const exploreBtn = $('#explore-wrong-btn');
    if (exploreSelectionActive) exploreBtn.addClass('active'); else exploreBtn.removeClass('active');
    exploreBtn.off('click').on('click', function() {
        exploreSelectionActive = !exploreSelectionActive;
        $(this).toggleClass('active', exploreSelectionActive);
        if (!exploreSelectionActive) {
            // Clear any yellow exploration highlights when turning off
            $('#left-panel .text-card span').removeClass('selected-text-highlight');
        }
    });

    // Initialize model selector UI state every render
    try {
        $('.model-btn').removeClass('active');
        $(`.model-btn[data-model="${selectedModel}"]`).addClass('active');
    } catch(e){}
}

// Function to concatenate "element" fields with styling based on "operation"
function concatenateElements(data, pairId, type) {
    let concatenatedText = '';
    data.forEach(item => {
        if (parseInt(item.pair_id) === pairId) {
            let operationClass = getOperationClass(item.operation);
            const elementId = `p${item.pair_id}-wt${item.position_in_wrong}-ct${item.position_in_correct}-dt${item.position_in_diff}`;
            // Add data attributes for tagging
            let dataAttributes = `id="${elementId}" data-pair-id="${item.pair_id}" data-pos-wrong="${item.position_in_wrong}" data-pos-correct="${item.position_in_correct}" data-pos-diff="${item.position_in_diff}" data-type="${type}"`;
            concatenatedText += `<span class="${operationClass}" ${dataAttributes}>${item.element}</span>`;
        }
    });
    return concatenatedText;
}

// Global variables to store selected element data for tagging
let selectedElementText = '';
let selectedElementType = '';
let selectedElementPosWrong = null;
let selectedElementPosCorrect = null;
let selectedElementPosDiff = null;
let selectedElementPairId = null;
let noteQuillEditor;
let nlpConclusion = null; // Holds latest NLP conclusion for current pair

// Get project name from URL
var projectName = getUrlParameter('project_name');

// Replacement: robust URL parameter parser
function getUrlParameter(name) {
    const sanitized = String(name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp('[?&]' + sanitized + '=([^&#]*)');
    const results = regex.exec(window.location.search);
    return results ? decodeURIComponent(results[1].replace(/\+/g, ' ')) : '';
}

// Function to update tag checkboxes based on the selected element's highlights
function updateTagCheckboxesForSelectedElement() {
    $('.tag-list input[type="checkbox"]').prop('checked', false); // Uncheck all first

    if (selectedElementPairId !== null) {
        // Filter highlightsData for the current selected element
        const relevantHighlights = highlightsData.filter(highlight => {
            return highlight.pair_id === selectedElementPairId &&
                   highlight.position_in_wrong === selectedElementPosWrong &&
                   highlight.position_in_correct === selectedElementPosCorrect &&
                   highlight.position_in_diff === selectedElementPosDiff &&
                   highlight.operation === selectedElementType; // Assuming operation matches type
        });

        relevantHighlights.forEach(highlight => {
            if (highlight.active) {
                $(`#tag-${highlight.name.replace(/ /g, '-')}`).prop('checked', true);
            }
        });
    }
}

// Function to send highlight/tag data to Flask using AJAX
function sendHighlightData(url, data, isNewTag = false) {
    $.ajax({
        url: url,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            console.log('Highlight/Tag data sent successfully:', response);
            // Update highlightsData with the new/updated highlight
            if (isNewTag) {
                // Add the new tag to the list of checkboxes
                const newTagHtml = `<li><label><input type="checkbox" id="tag-${data.name.replace(/ /g, '-')}" value="${data.name}" checked> ${data.name}</label></li>`;
                $('.tag-list').append(newTagHtml);
                // Also add to highlightsData for future reference
                highlightsData.push({
                    name: data.name,
                    active: true,
                    pair_id: data.elementDataPairId,
                    position_in_wrong: data.elementPosWrong,
                    position_in_correct: data.elementPosCorrect,
                    position_in_diff: data.elementPosDiff,
                    operation: data.elementType
                });
            }
            // Re-apply visual tags to reflect changes
            applyVisualTags();
            updateTagCheckboxesForSelectedElement(); // Update checkboxes after operation
        },
        error: function(xhr, status, error) {
            console.error('Error sending highlight/tag data:', error);
            Swal.fire('Error', 'Error saving tag. Please try again.', 'error');
        }
    });
}

// Function to apply visual tags to text spans
function applyVisualTags() {
    $('.text-card span').removeClass('applied-tag-highlight'); // Remove all existing applied tag highlights

    highlightsData.forEach(highlight => {
        if (highlight.active) {
            // Find the span element that matches the highlight's attributes
            const selector = `span[data-pair-id="${highlight.pair_id}"]` +
                             `[data-pos-wrong="${highlight.position_in_wrong}"]` +
                             `[data-pos-correct="${highlight.position_in_correct}"]` +
                             `[data-pos-diff="${highlight.position_in_diff}"]` +
                             `[data-type="${highlight.operation}"]`;
            $(selector).addClass('applied-tag-highlight');
        }
    });
}

function sendChatMessage() {
    const question = $('#chat-input-field').val().trim();
    if (question === '') {
        return;
    }

    const chatHistory = $('#chat-history');
    chatHistory.append(`<div class="chat-message user"><p>${question}</p></div>`);
    $('#chat-input-field').val('');

    // Add user message to history
    chatHistoryQueue.push({role: 'user', content: question});
    if (chatHistoryQueue.length > MAX_HISTORY_LENGTH * 2) { // Each interaction has user and AI message
        chatHistoryQueue.splice(0, 2);
    }

    // Show typing indicator
    chatHistory.append(`
        <div class="chat-message ai" id="typing-indicator">
            <div class="typing-indicator-container">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `);
    chatHistory.scrollTop(chatHistory[0].scrollHeight);

    // Find the current pair ID
    const currentPairId = selectedElementPairId || (textPairs.length > 0 ? textPairs[0].id : null);
    if (currentPairId === null) {
        $('#typing-indicator').remove();
        chatHistory.append(`<div class="chat-message ai"><p>Error: Could not determine the current text pair.</p></div>`);
        return;
    }

    const pairData = textPairs.find(p => p.id === currentPairId);

    const selectedTag = $('.selected-annotation-highlight').closest('.annotation-span').data('tag-id');
    const annotatedText = selectedElementText;

    const normalizedNlp = nlpConclusion && nlpConclusion.response ? nlpConclusion.response : nlpConclusion;
    let analysisSummary = 'N/A';
    if (normalizedNlp && Array.isArray(normalizedNlp.categories)) {
        const names = normalizedNlp.categories.map(c => c.name).filter(Boolean);
        if (names.length) analysisSummary = `Key categories: ${names.join(', ')}`;
    }
    const patternsList = normalizedNlp && Array.isArray(normalizedNlp.global_patterns) && normalizedNlp.global_patterns.length
        ? `Patterns: ${normalizedNlp.global_patterns.join('; ')}`
        : '';
    const context = {
        selected_text: annotatedText || 'N/A',
        selected_tag: selectedTag || 'N/A',
        analysis: `${analysisSummary}${patternsList ? ' | ' + patternsList : ''}`,
        tags: 'N/A',
        wrong_text: pairData ? pairData.error_text : 'N/A',
        correct_text: pairData ? pairData.corrected_text : 'N/A'
    };

    const useWebSearch = ($('#chat-input-container').data('active-tool') === 'web-search');
    $.ajax({
        url: '/api/ai_chat',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            project_name: projectName,
            question: question,
            context: context,
            pair_id: currentPairId,
            chat_history: chatHistoryQueue,
            use_web_search: useWebSearch,
            model_name: selectedModel
        }),
        success: function(response) {
            $('#typing-indicator').remove();
            const formattedResponse = md.render(response.response);
            const messageId = `ai-message-${Date.now()}`;
            const messageHtml = `
                <div class="chat-message ai" id="${messageId}">
                    <div class="ai-content">${formattedResponse}</div>
                    <button class="add-to-notes-btn" data-message-id="${messageId}">
                        <i class="fas fa-plus"></i> <span>Add to Notes</span>
                    </button>
                </div>`;
            chatHistory.append(messageHtml);
            chatHistory.scrollTop(chatHistory[0].scrollHeight);

            // Add AI response to history
            chatHistoryQueue.push({role: 'assistant', content: response.response});
            if (chatHistoryQueue.length > MAX_HISTORY_LENGTH * 2) {
                chatHistoryQueue.splice(0, 2);
            }
        },
        error: function(xhr, status, error) {
            $('#typing-indicator').remove();
            console.error('Error with AI chat:', error);
            chatHistory.append(`<div class="chat-message ai"><p>Sorry, I encountered an error. Please try again.</p></div>`);
            chatHistory.scrollTop(chatHistory[0].scrollHeight);
        }
    });
}

function renderLinguisticAnalysis(output) {
    // Allow backend to return either {conclusion, inconsistencies} or {response: { ... }}
    if (output && output.response) {
        output = output.response;
    }
    const container = $('.analysis-output');

    // Normalize loosely structured outputs coming from the model
    function parseCategoryString(str) {
        try { str = String(str).trim(); } catch (e) { return null; }
        if (!str || /^no findings\.?$/i.test(str)) return null;
        const nameMatch = str.match(/^(.*?)\.?\s*Description:/i);
        const name = nameMatch ? nameMatch[1].trim() : (str.split('\n')[0].trim() || 'Category');
        let description = '';
        let explanation = '';
        const descMatch = str.match(/Description:\s*([\s\S]*?)(?:Explanation:|Findings:|$)/i);
        if (descMatch) description = descMatch[1].trim();
        const explMatch = str.match(/Explanation:\s*([\s\S]*?)(?:Findings:|$)/i);
        if (explMatch) explanation = explMatch[1].trim();
        let findings = [];
        const findMatch = str.match(/Findings:\s*(\[[\s\S]*?\])/i);
        if (findMatch) {
            try {
                findings = JSON.parse(findMatch[1]);
            } catch (e) {
                // Try to sanitize minor JSON formatting issues
                try { findings = JSON.parse(findMatch[1].replace(/\'|\n/g, '')); } catch (e2) { findings = []; }
            }
        }
        // If we don't have parsed findings, synthesize from extracted name/explanation
        if (!Array.isArray(findings) || findings.length === 0) {
            // Try to extract a short code from parentheses in the name
            const codeMatch = name.match(/\(([^)]+)\)/);
            const label = codeMatch ? codeMatch[1] : (name || 'Finding');
            const exp = explanation || description || str;
            findings = [{ label, explanation: exp }];
        }
        return { name, description, findings };
    }

    function normalize(output) {
        const norm = { categories: [], layers: [], global_patterns: [], notes: null, summary_delta: null, evidence: [], interdisciplinary_summary: null };
        if (!output || typeof output !== 'object') return norm;
        // categories
        if (Array.isArray(output.categories)) {
            output.categories.forEach(cat => {
                if (!cat) return;
                if (typeof cat === 'string') {
                    const parsed = parseCategoryString(cat);
                    if (parsed) norm.categories.push(parsed);
                    return;
                }
                if (typeof cat === 'object') {
                    const c = { name: cat.name || 'Category', description: cat.description || '', findings: [] };
                    if (Array.isArray(cat.findings)) {
                        c.findings = cat.findings;
                    } else if (typeof cat.findings === 'string') {
                        try { c.findings = JSON.parse(cat.findings); } catch (e) { c.findings = []; }
                    }
                    // Also handle cases where model stuffed text into description containing Findings:
                    if (c.findings.length === 0 && c.description && /Findings:/i.test(c.description)) {
                        const parsed = parseCategoryString(`${c.name}. Description: ${c.description}`);
                        if (parsed) { c.description = parsed.description; c.findings = parsed.findings; }
                    }
                    norm.categories.push(c);
                }
            });
        }
        // layers
        if (Array.isArray(output.layers)) {
            norm.layers = output.layers.filter(Boolean);
        }
        // global_patterns
        if (Array.isArray(output.global_patterns)) {
            norm.global_patterns = output.global_patterns.filter(x => typeof x === 'string' && !/^no findings\.?$/i.test(x.trim()));
        } else if (typeof output.global_patterns === 'string' && !/^no findings\.?$/i.test(output.global_patterns.trim())) {
            norm.global_patterns = [output.global_patterns.trim()];
        }
        // notes
        if (output.notes && typeof output.notes === 'object') norm.notes = output.notes;
        // deltas
        norm.summary_delta = output.summary_delta || output.delta || output.comparative || null;
        // evidence
        if (Array.isArray(output.evidence)) norm.evidence = output.evidence;
        // pass-through optional sections from backend
        if (output.dependency_trees) norm.dependency_trees = output.dependency_trees;
        if (output.morphology_analysis) norm.morphology_analysis = output.morphology_analysis;
        if (output.topics) norm.topics = output.topics;
        if (output.cohesion_analysis) norm.cohesion_analysis = output.cohesion_analysis;
        if (output.ner_analysis) norm.ner_analysis = output.ner_analysis;
        // Cognitive load analysis removed
        if (output.interdisciplinary_summary) norm.interdisciplinary_summary = output.interdisciplinary_summary;
        return norm;
    }

    // If we have the newer structured format with categories, render that
    const normalized = normalize(output);
    if (normalized.categories.length > 0 || normalized.global_patterns.length > 0 || normalized.summary_delta || (normalized.evidence && normalized.evidence.length)) {
        const pairIdAttr = container.attr('data-pair-id') || '';
        const patterns = normalized.global_patterns;

        // Build tabs
        const tabBtns = [
            `<button class="analysis-tab-btn active" data-tab="overview">${i18nLabel('tabOverview','Overview')}</button>`
        ];
        tabBtns.push(`<button class="analysis-tab-btn" data-tab="categories">${i18nLabel('tabCategories','Categories')}</button>`);
        if (normalized.layers && normalized.layers.length) {
            tabBtns.push(`<button class="analysis-tab-btn" data-tab="layers">${i18nLabel('tabLayers','Layers')}</button>`);
        }
        tabBtns.push(`<button class="analysis-tab-btn" data-tab="delta">${i18nLabel('tabDelta','Delta')}</button>`);
        tabBtns.push(`<button class="analysis-tab-btn" data-tab="evidence">${i18nLabel('tabEvidence','Evidence')}</button>`);
        if (normalized.dependency_trees) {
            tabBtns.push(`<button class="analysis-tab-btn" data-tab="dependency">${i18nLabel('tabDependency','Dependency')}</button>`);
        }
        if (normalized.morphology_analysis) {
            tabBtns.push(`<button class="analysis-tab-btn" data-tab="morphology">${i18nLabel('tabMorphology','Morphology')}</button>`);
        }
        // Prefer NER bundled with main analysis; fallback to separate fetch
        if (normalized.ner_analysis || (typeof window !== 'undefined' && window.nerAnalysisData && window.nerAnalysisData.ner_analysis)) {
            tabBtns.push(`<button class="analysis-tab-btn" data-tab="ner">${i18nLabel('tabNer','NER')}</button>`);
        }
        if (normalized.topics) {
            tabBtns.push(`<button class="analysis-tab-btn" data-tab="topics">${i18nLabel('tabTopics','Topics')}</button>`);
        }
        if (normalized.cohesion_analysis) {
            tabBtns.push(`<button class="analysis-tab-btn" data-tab="cohesion">${i18nLabel('tabCohesion','Cohesion')}</button>`);
        }
        // Cognitive Load tab removed
        const hasDebug = Array.isArray(normalized.debug_log) && normalized.debug_log.length > 0;
        if (hasDebug) {
            tabBtns.push('<button class="analysis-tab-btn" data-tab="debug">Debug</button>');
        }
        const tabsHeader = `<div class="analysis-tabs">${tabBtns.join('')}</div>`;

        // Overview tab (global patterns + optional notes)
        let overviewHtml = '';
        if (patterns.length) {
            overviewHtml += `<div class="analysis-patterns"><h5>${i18nLabel('globalPatterns','Global Patterns')}</h5><ul class="analysis-list">` + patterns.map(p => `<li>${md.renderInline(String(p))}</li>`).join('') + '</ul></div>';
        }
        if (normalized.notes) {
            const obs = Array.isArray(normalized.notes.observations) ? normalized.notes.observations : [];
            const interp = Array.isArray(normalized.notes.interpretations) ? normalized.notes.interpretations : [];
            const limits = Array.isArray(normalized.notes.limitations) ? normalized.notes.limitations : [];
            if (obs.length) {
                overviewHtml += `<div class="analysis-observations"><h5>${i18nLabel('observations','Observations')} <span class="badge">${i18nLabel('dataBacked','data-backed')}</span></h5><ul class="analysis-list">` + obs.map(x => `<li>${md.renderInline(String(x))}</li>`).join('') + '</ul></div>';
            }
            if (interp.length) {
                overviewHtml += `<div class="analysis-interpretations"><h5>${i18nLabel('interpretations','Interpretations')} <span class="badge">${i18nLabel('theoryGuided','theory-guided')}</span></h5><ul class="analysis-list">` + interp.map(x => `<li>${md.renderInline(String(x))}</li>`).join('') + '</ul></div>';
            }
            if (limits.length) {
                overviewHtml += `<div class="analysis-limitations"><h5>${i18nLabel('limitations','Limitations')}</h5><ul class="analysis-list">` + limits.map(x => `<li>${md.renderInline(String(x))}</li>`).join('') + '</ul></div>';
            }
        }
        if (!overviewHtml) {
            overviewHtml = `<p class="analysis-conclusion">${i18nLabel('overviewNotAvailable','Overview not available.')}</p>`;
        }

        // Categories tab
        let categoriesHtml = normalized.categories.map(cat => {
            const findings = Array.isArray(cat.findings) ? cat.findings : [];
            const findingsHtml = findings.length
                ? '<ul class="analysis-list">' + findings.map((f, idx) => {
                    const conf = (typeof f.confidence === 'number') ? `<span class="badge">${Math.round(f.confidence * 100)}%</span>` : '';
                    const ltxt = f && f.label ? i18nLabel(String(f.label), String(f.label)) : '';
                    const label = ltxt ? `<strong>${ltxt}</strong>` : '';
                    const expl = f.explanation || '';
                    const explHtml = md.renderInline(String(expl));
                    return `<li class="analysis-finding" data-finding-index="${idx}">${label}${label && expl ? ': ' : ''}${explHtml} ${conf}</li>`;
                }).join('') + '</ul>'
                : `<p class="text-secondary" style="color:#65676b">${i18nLabel('noFindings','No findings.')}</p>`;
            const descHtml = cat.description ? `<div class="analysis-category-desc">${md.render(String(cat.description))}</div>` : '';
            const catName = cat && cat.name ? i18nLabel(String(cat.name), String(cat.name)) : i18nLabel('category','Category');
            return `
                <div class="analysis-category">
                    <h5 class="analysis-category-title">${catName}</h5>
                    ${descHtml}
                    ${findingsHtml}
                </div>
            `;
        }).join('');

        if (normalized.interdisciplinary_summary) {
            categoriesHtml += `
                <div class="analysis-category" style="margin-top: 20px; border-top: 1px solid var(--border-color); padding-top: 15px;">
                    <h5 class="analysis-category-title">${i18nLabel('interdisciplinaryInterpretation','Interdisciplinary Interpretation')}</h5>
                    <div class="analysis-category-desc">${md.render(String(normalized.interdisciplinary_summary))}</div>
                </div>
            `;
        }

        // Layers tab
        let layersHtml = '';
        if (normalized.layers && normalized.layers.length) {
            layersHtml = normalized.layers.map(layer => {
                const cats = Array.isArray(layer.categories) ? layer.categories : [];
                const catsHtml = cats.map(cat => {
                    const findings = Array.isArray(cat.findings) ? cat.findings : [];
                    const findingsHtml = findings.length
                        ? '<ul class="analysis-list">' + findings.map(f => {
                            const lbl = f && f.label ? i18nLabel(String(f.label), String(f.label)) : '';
                            const expl = f && f.explanation ? String(f.explanation) : '';
                            const explInline = expl ? md.renderInline(expl) : '';
                            const parts = [lbl, explInline].filter(Boolean);
                            return `<li>${parts.join(': ')}</li>`;
                          }).join('') + '</ul>'
                        : `<p class="text-secondary" style="color:#65676b">${i18nLabel('noFindings','No findings.')}</p>`;
                    const descHtml = cat.description ? `<div class="analysis-category-desc">${md.render(String(cat.description))}</div>` : '';
                    const catName = cat.name ? i18nLabel(String(cat.name), String(cat.name)) : i18nLabel('category','Category');
                    return `
                        <div class="analysis-category">
                            <h5 class="analysis-category-title">${catName}</h5>
                            ${descHtml}
                            ${findingsHtml}
                        </div>
                    `;
                }).join('');
                const layerName = layer.name ? i18nLabel(String(layer.name), String(layer.name)) : i18nLabel('layer','Layer');
                return `
                    <div class="analysis-layer">
                        <h4 class="analysis-category-title">${layerName}</h4>
                        ${catsHtml}
                    </div>
                `;
            }).join('');
        }

        // Delta tab (comparative summaries if present)
        let deltaHtml = '';
        const delta = normalized.summary_delta;
        if (delta && (delta.pos_counts_diff || delta.dependency_counts_diff || delta.entity_type_diff || delta.tense_counts_diff || delta.number_counts_diff || delta.surface_edit_counts)) {
            const posHuman = (code) => {
                const map = {
                    'ADJ':'Adjective','ADP':'Adposition','ADV':'Adverb','AUX':'Auxiliary','CCONJ':'Coordinating conjunction',
                    'DET':'Determiner','INTJ':'Interjection','NOUN':'Noun','NUM':'Numeral','PART':'Particle','PRON':'Pronoun',
                    'PROPN':'Proper noun','PUNCT':'Punctuation','SCONJ':'Subordinating conjunction','SYM':'Symbol','VERB':'Verb','X':'Other'
                };
                const tb = {
                    'NN':'Noun','NNS':'Noun','NNP':'Proper noun','NNPS':'Proper noun',
                    'VB':'Verb','VBD':'Verb','VBG':'Verb','VBN':'Verb','VBP':'Verb','VBZ':'Verb',
                    'JJ':'Adjective','JJR':'Adjective','JJS':'Adjective',
                    'RB':'Adverb','RBR':'Adverb','RBS':'Adverb',
                    'PRP':'Pronoun','PRP$':'Pronoun','WP':'Pronoun','WP$':'Pronoun',
                    'DT':'Determiner','IN':'Adposition','CC':'Coordinating conjunction',
                    'CD':'Numeral','UH':'Interjection','SYM':'Symbol','FW':'Other',
                    'POS':'Particle','TO':'Particle'
                };
                const key = String(code).toUpperCase();
                const human = map[key] || tb[key] || String(code);
                return i18nLabel(human, human);
            };
            const entHuman = (code) => {
                const map = {
                    'PERSON':'Person','LOCATION':'Location','ORGANIZATION':'Organization','GPE':'Geo-political entity','EVENT':'Event',
                    'WORK_OF_ART':'Work of art','CONSUMER_GOOD':'Consumer good','OTHER':'Other','NUMBER':'Number','ORDINAL':'Ordinal',
                    'DATE':'Date','TIME':'Time','DURATION':'Duration','MONEY':'Money'
                };
                const human = map[String(code).toUpperCase()] || String(code);
                return i18nLabel(human, human);
            };
            const depHuman = (lbl) => {
                try {
                    const s = String(lbl);
                    if (!s) return s;
                    const ud = {
                        'nsubj':'Nominal subject','csubj':'Clausal subject','obj':'Object','iobj':'Indirect object','obl':'Oblique nominal',
                        'det':'Determiner','amod':'Adjectival modifier','advmod':'Adverbial modifier','nmod':'Nominal modifier','cc':'Coordinating conjunction',
                        'conj':'Conjunct','aux':'Auxiliary','cop':'Copula','mark':'Marker','punct':'Punctuation','root':'Root','xcomp':'Open clausal complement',
                        'ccomp':'Clausal complement','appos':'Appositional modifier','case':'Case marking'
                    };
                    const g = {
                        'NSUBJ':'Nominal subject','CSUBJ':'Clausal subject','DOBJ':'Direct object','IOBJ':'Indirect object','POBJ':'Object of preposition',
                        'AUX':'Auxiliary','AUXPASS':'Passive auxiliary','NSUBJPASS':'Nominal subject (passive)','CSUBJPASS':'Clausal subject (passive)',
                        'DET':'Determiner','AMOD':'Adjectival modifier','ADVMOD':'Adverbial modifier','NMOD':'Nominal modifier','CC':'Coordinating conjunction',
                        'CONJ':'Conjunct','COP':'Copula','MARK':'Marker','PUNCT':'Punctuation','ROOT':'Root','XCOMP':'Open clausal complement','CCOMP':'Clausal complement',
                        'APPOS':'Appositional modifier','NEG':'Negation modifier','PREP':'Preposition','PRT':'Particle','ATTR':'Attribute','PARATAXIS':'Parataxis',
                        'TMOD':'Temporal modifier','RCMOD':'Relative clause modifier','EXPL':'Expletive','NUM':'Numeric modifier','NUMBER':'Number','POSS':'Possessive modifier'
                    };
                    if (g[s]) return i18nLabel(g[s], g[s]);
                    const sl = s.toLowerCase();
                    if (ud[sl]) return i18nLabel(ud[sl], ud[sl]);
                    if (s.includes('SUBJ')) {
                        let base = 'Nominal subject';
                        if (s.startsWith('CSUBJ')) base = 'Clausal subject';
                        if (s.includes('PASS')) base += ' (passive)';
                        return i18nLabel(base, base);
                    }
                    if (s.endsWith('OBJ')) {
                        if (s === 'DOBJ') return i18nLabel('Direct object','Direct object');
                        if (s === 'IOBJ') return i18nLabel('Indirect object','Indirect object');
                        if (s === 'POBJ') return i18nLabel('Object of preposition','Object of preposition');
                        return i18nLabel('Object','Object');
                    }
                    return s;
                } catch (_) { return String(lbl); }
            };
            const renderDeltaSection = (title, obj, formatter=null) => {
                if (!obj || typeof obj !== 'object') return '';
                const items = Object.entries(obj).filter(([k, v]) => {
                    const n = parseInt(v, 10);
                    if (isNaN(n) || n === 0) return false;
                    // Exclude 'N/A' buckets from stats display
                    const key = String(k).toUpperCase();
                    if (key === 'N/A' || key === 'NA') return false;
                    return true;
                });
                if (items.length === 0) {
                    return `<div><h5>${title}</h5><p class="text-secondary" style="color:#65676b">${i18nLabel('noChanges','No changes.')}</p></div>`;
                }
                const list = items.map(([k, v]) => {
                    const n = parseInt(v, 10) || 0;
                    const lab = formatter ? formatter(k) : k;
                    return `<li>${lab}: ${n >= 0 ? '+' + n : n}</li>`;
                }).join('');
                return `<div><h5>${title}</h5><ul class="analysis-list">${list}</ul></div>`;
            };

            const sections = [];
            sections.push(renderDeltaSection(i18nLabel('posDelta','POS Delta'), delta.pos_counts_diff, posHuman));
            sections.push(renderDeltaSection(i18nLabel('dependencyDelta','Dependency Delta'), delta.dependency_counts_diff, depHuman));
            sections.push(renderDeltaSection(i18nLabel('entitiesDelta','Entities Delta'), delta.entity_type_diff, entHuman));
            sections.push(renderDeltaSection(i18nLabel('tenseDelta','Tense Delta'), delta.tense_counts_diff, (k)=>i18nLabel(String(k), String(k))));
            sections.push(renderDeltaSection(i18nLabel('numberDelta','Number Delta'), delta.number_counts_diff, (k)=>i18nLabel(String(k), String(k))));
            // Surface edit counts rendered even if zero, to show basic overview
            if (delta.surface_edit_counts && typeof delta.surface_edit_counts === 'object') {
                const sec = (function(){
                    const obj = delta.surface_edit_counts;
                    const entries = Object.entries(obj);
                    if (!entries.length) return '';
                    const list = entries.map(([k, v]) => {
                        const human = k.replace(/_/g,' ');
                        const label = i18nLabel(human, human);
                        return `<li>${label}: ${parseInt(v,10) || 0}</li>`;
                    }).join('');
                    return `<div><h5>${i18nLabel('surfaceEdits','Surface Edits')}</h5><ul class="analysis-list">${list}</ul></div>`;
                })();
                sections.push(sec);
            }
            deltaHtml = sections.filter(Boolean).join('');
            if (!deltaHtml) {
                deltaHtml = `<p class="text-secondary" style="color:#65676b">${i18nLabel('noDifferencesFound','No differences found.')}</p>`;
            }
        } else {
            deltaHtml = `<p class="analysis-conclusion">${i18nLabel('comparativeDeltasNotAvailable','Comparative deltas not available.')}</p>`;
        }

        // Evidence tab (click to highlight if tokens provided)
        let evidenceHtml = '';
        const evidence = normalized.evidence || [];
        if (Array.isArray(evidence) && evidence.length) {
            evidenceHtml = '<ul class="analysis-list">' + evidence.map((ev, i) => {
                const title = ev.label || ev.summary || `${i18nLabel('evidence','Evidence')} ${i+1}`;
                const titleHtml = md.renderInline(String(title));
                const wrong = Array.isArray(ev.wrong_tokens) ? ev.wrong_tokens.map(t => (t && t.token) ? String(t.token) : '').filter(Boolean).slice(0,5) : [];
                const correct = Array.isArray(ev.correct_tokens) ? ev.correct_tokens.map(t => (t && t.token) ? String(t.token) : '').filter(Boolean).slice(0,5) : [];
                let examples = '';
                if (wrong.length || correct.length) {
                    const wrongLine = wrong.length ? `<div class="ev-line"><strong>${i18nLabel('wrongText','Wrong Text')}:</strong> ${wrong.join(', ')}</div>` : '';
                    const corrLine = correct.length ? `<div class="ev-line"><strong>${i18nLabel('correctText','Correct Text')}:</strong> ${correct.join(', ')}</div>` : '';
                    examples = `<div class="evidence-examples">${wrongLine}${corrLine}</div>`;
                }
                return `<li class=\"analysis-evidence\" data-ev-index=\"${i}\">${titleHtml}${examples}</li>`;
            }).join('') + '</ul>';
        } else {
            evidenceHtml = `<p>${i18nLabel('noExplicitEvidence','No explicit evidence provided by the model.')}</p>`;
        }

        // Morphology Analysis Tab
        let morphologyHtml = '';
        if (normalized.morphology_analysis) {
            const renderMorphTable = (data) => {
                if (!data || data.length === 0) return `<p>${i18nLabel('noMorphologyData','No morphology data available.')}</p>`;
                let table = `<table class="morph-table"><thead><tr><th>${i18nLabel('colToken','Token')}</th><th>${i18nLabel('colLemma','Lemma')}</th><th>${i18nLabel('colPOS','POS')}</th><th>${i18nLabel('colFeatures','Features')}</th></tr></thead><tbody>`;
                const featLabel = (k) => {
                    const map = {
                        'tense': i18nLabel('featTense','Tense'),
                        'number': i18nLabel('featNumber','Number'),
                        'person': i18nLabel('featPerson','Person'),
                        'mood': i18nLabel('featMood','Mood'),
                        'voice': i18nLabel('featVoice','Voice'),
                        'case': i18nLabel('featCase','Case'),
                        'gender': i18nLabel('featGender','Gender'),
                    };
                    return map[k] || k;
                };
                const featValue = (v) => {
                    if (v == null) return '';
                    const s = String(v).toUpperCase();
                    return i18nLabel(s, String(v));
                };
                data.forEach(token => {
                    const features = Object.entries(token)
                        .filter(([key]) => !['token', 'lemma', 'pos'].includes(key))
                        .map(([key, value]) => `<strong>${featLabel(String(key).toLowerCase())}:</strong> ${featValue(value)}`)
                        .join('<br>');
                    table += `<tr><td>${token.token}</td><td>${token.lemma}</td><td>${token.pos}</td><td>${features}</td></tr>`;
                });
                table += '</tbody></table>';
                return table;
            };

            let qualitativeHtml = '';
            if (normalized.morphology_analysis.qualitative_analysis) {
                const qa = normalized.morphology_analysis.qualitative_analysis;
                const findingsList = Array.isArray(qa.findings) && qa.findings.length
                    ? '<ul class="analysis-list">' + qa.findings.map(f => {
                        const lbl = (f && f.label) ? String(f.label) : '';
                        const explHtml = md.render(String((f && f.explanation) ? f.explanation : ''));
                        return `<li>${lbl ? `<strong>${lbl}</strong>:` : ''}<div>${explHtml}</div></li>`;
                      }).join('') + '</ul>'
                    : `<p>${i18nLabel('noSalientMorphological','No salient morphological divergences detected.')}</p>`;
                qualitativeHtml = `
                    <div class="qualitative-morphology-analysis">
                        ${qa.summary ? `<div>${md.render(String(qa.summary))}</div>` : ''}
                        <h5>${i18nLabel('divergenceFindings','Divergence Findings')}</h5>
                        ${findingsList}
                        ${qa.interpretation ? `<h5>${i18nLabel('interdisciplinaryInterpretation','Interdisciplinary Interpretation')}</h5><div>${md.render(String(qa.interpretation))}</div>` : ''}
                    </div>
                `;
            }

            morphologyHtml = `
                <div class="morphology-container">
                    ${qualitativeHtml}
                    <h5>${i18nLabel('wrongText','Wrong Text')}</h5>
                    ${renderMorphTable(normalized.morphology_analysis.wrong)}
                    <h5>${i18nLabel('correctText','Correct Text')}</h5>
                    ${renderMorphTable(normalized.morphology_analysis.correct)}
                </div>
            `;
        }

        // Topics Analysis Tab
        let topicsHtml = '';
        if (normalized.topics) {
            const ta = normalized.topics;
            const findingsList = Array.isArray(ta.findings) && ta.findings.length
                ? '<ul class="analysis-list">' + ta.findings.map(f => {
                    const lbl = f && f.label ? `<strong>${i18nLabel(String(f.label), String(f.label))}:</strong> ` : '';
                    const expl = f && f.explanation ? md.renderInline(String(f.explanation)) : '';
                    return `<li>${lbl}${expl}</li>`;
                }).join('') + '</ul>'
                : `<p>${i18nLabel('noSalientTopics','No salient topic divergences detected.')}</p>`;
            topicsHtml = `
                <div class="topics-container">
                    ${ta.summary ? `<div>${md.render(String(ta.summary))}</div>` : ''}
                    <h5>${i18nLabel('divergenceFindings','Divergence Findings')}</h5>
                    ${findingsList}
                    ${ta.interpretation ? `<h5>${i18nLabel('interdisciplinaryInterpretation','Interdisciplinary Interpretation')}</h5><div>${md.render(String(ta.interpretation))}</div>` : ''}
                </div>
            `;
        }

        // Cohesion Analysis Tab (divergence from corrected baseline)
        let cohesionHtml = '';
        if (normalized.cohesion_analysis) {
            const ca = normalized.cohesion_analysis;
            const findingsList = Array.isArray(ca.findings) && ca.findings.length
                ? '<ul class="analysis-list">' + ca.findings.map(f => {
                    const lbl = f && f.label ? `<strong>${i18nLabel(String(f.label), String(f.label))}:</strong> ` : '';
                    const expl = f && f.explanation ? md.renderInline(String(f.explanation)) : '';
                    const delta = (f.delta !== undefined) ? ` <em>(Δ=${Number(f.delta).toFixed(2)})</em>` : '';
                    return `<li>${lbl}${expl}${delta}</li>`;
                  }).join('') + '</ul>'
                : `<p>${i18nLabel('noSalientCohesion','No salient cohesion divergences detected.')}</p>`;
            cohesionHtml = `
                <div class="cohesion-container">
                    ${ca.summary ? `<div>${md.render(String(ca.summary))}</div>` : ''}
                    <h5>${i18nLabel('divergenceFindings','Divergence Findings')}</h5>
                    ${findingsList}
                    ${ca.interpretation ? `<h5>${i18nLabel('interdisciplinaryInterpretation','Interdisciplinary Interpretation')}</h5><div>${md.render(String(ca.interpretation))}</div>` : ''}
                </div>
            `;
        }

        // NER tab content
        let nerHtml = '';
        try {
            if (normalized.ner_analysis) {
                nerHtml = renderNerAnalysis({ ner_analysis: normalized.ner_analysis });
            } else if (typeof window !== 'undefined' && window.nerAnalysisData && window.nerAnalysisData.ner_analysis) {
                nerHtml = renderNerAnalysis(window.nerAnalysisData);
            }
        } catch (e) { nerHtml = ''; }

        // Debug tab content
        const debugHtml = hasDebug ? ('<pre class="analysis-debug-log">' + normalized.debug_log.map(l => String(l)).join('\n') + '</pre>') : '';

        container.html(`
            <div class="analysis-card" data-pair-id="${pairIdAttr}">
                <div class="analysis-card-header">
                    <div class="title"><i class="fas fa-chart-line"></i> ${i18nLabel('nlpAnalysisTitle','NLP Analysis')}</div>
                    <div class="actions">
                        <button class="analysis-refresh" title="${i18nLabel('refreshTooltip','Refresh')}"><i class="fas fa-sync"></i></button>
                        <button class="analysis-collapse" title="${i18nLabel('collapseExpandTooltip','Collapse/Expand')}"><i class="fas fa-chevron-up"></i></button>
                    </div>
                </div>
                <div class="analysis-card-body">
                    ${tabsHeader}
                    <div class="analysis-tab-content active" data-tab="overview">${overviewHtml}</div>
                    <div class="analysis-tab-content" data-tab="categories">${categoriesHtml}</div>
                    ${layersHtml ? `<div class=\"analysis-tab-content\" data-tab=\"layers\">${layersHtml}</div>` : ''}
                    <div class="analysis-tab-content" data-tab="delta">${deltaHtml}</div>
                    <div class="analysis-tab-content" data-tab="evidence">${evidenceHtml}</div>
                    <div class="analysis-tab-content" data-tab="dependency">
                        <div class="dependency-container">
                            <div class="dependency-selector" style="margin-bottom: 10px;">
                                <label for="dep-tree-select" style="margin-right: 5px;">${i18nLabel('viewLabel','View:')}</label>
                                <select id="dep-tree-select" style="padding: 5px; border-radius: 4px;">
                                    <option value="wrong" selected>${i18nLabel('wrongText','Wrong Text')}</option>
                                    <option value="correct">${i18nLabel('correctText','Correct Text')}</option>
                                </select>
                            </div>
                            <div id="dep-wrong" class="dependency-parse"></div>
                            <div id="dep-correct" class="dependency-parse" style="display: none;"></div>
                        </div>
                    </div>
                    ${morphologyHtml ? `<div class="analysis-tab-content" data-tab="morphology">${morphologyHtml}</div>` : ''}
                    ${nerHtml ? `<div class="analysis-tab-content" data-tab="ner">${nerHtml}</div>` : ''}
                    ${topicsHtml ? `<div class="analysis-tab-content" data-tab="topics">${topicsHtml}</div>` : ''}
                    ${cohesionHtml ? `<div class="analysis-tab-content" data-tab="cohesion">${cohesionHtml}</div>` : ''}
                    
                    ${hasDebug ? `<div class="analysis-tab-content" data-tab="debug">${debugHtml}</div>` : ''}
                </div>
            </div>
        `);

        // Tab switching
        container.find('.analysis-tab-btn').on('click', function() {
            const tab = $(this).data('tab');
            container.find('.analysis-tab-btn').removeClass('active');
            $(this).addClass('active');
            container.find('.analysis-tab-content').removeClass('active');
            container.find(`.analysis-tab-content[data-tab="${tab}"]`).addClass('active');
        });

        // Dependency tree view switcher
        container.find('#dep-tree-select').on('change', function() {
            const selectedView = $(this).val();
            if (selectedView === 'wrong') {
                container.find('#dep-wrong').show();
                container.find('#dep-correct').hide();
            } else {
                container.find('#dep-wrong').hide();
                container.find('#dep-correct').show();
            }
        });

        // Evidence highlighting
        function clearEvidenceHighlights() {
            $('#left-panel .text-card span').removeClass('evidence-highlight');
        }
        function highlightTokens(tokens, type) {
            if (!Array.isArray(tokens)) return;
            tokens.forEach(t => {
                const val = (t.token || t.text || '').trim();
                if (!val) return;
                // naive match: highlight spans whose text matches token
                $(`#result_${type}_${pairIdAttr} span`).filter(function(){ return $(this).text() === val; }).addClass('evidence-highlight');
            });
        }
        container.find('.analysis-evidence').on('click', function() {
            clearEvidenceHighlights();
            const idx = parseInt($(this).data('ev-index'), 10);
            const ev = evidence[idx] || {};
            if (ev.wrong_tokens) highlightTokens(ev.wrong_tokens, 'wrong');
            if (ev.correct_tokens) highlightTokens(ev.correct_tokens, 'correct');
        });

        // Render dependency trees if data is available, using a minimal inline SVG renderer (no CDN, no external JS)
        if (normalized.dependency_trees) {
            const wrong = normalized.dependency_trees.wrong || {};
            const correct = normalized.dependency_trees.correct || {};
            const hasWrong = Array.isArray(wrong.words) && wrong.words.length > 0;
            const hasCorrect = Array.isArray(correct.words) && correct.words.length > 0;

            const renderSimpleDep = (containerSel, tree) => {
                try {
                    const words = Array.isArray(tree.words) ? tree.words : [];
                    const arcs = Array.isArray(tree.arcs) ? tree.arcs : [];
                    if (!words.length) {
                        $(containerSel).html(`<p class="text-secondary" style="color:#65676b">${i18nLabel('noDependencyData','No dependency data.')}</p>`);
                        return;
                    }
                    // Colors for POS and labels
                    const posColor = {
                        'NOUN':'#2b6cb0','PROPN':'#2b6cb0','PRON':'#2b6cb0',
                        'VERB':'#d53f8c','AUX':'#d53f8c',
                        'ADJ':'#805ad5','ADV':'#38a169',
                        'DET':'#dd6b20','ADP':'#319795','CCONJ':'#718096','SCONJ':'#718096',
                        'NUM':'#319795','PART':'#e53e3e','INTJ':'#b83280','SYM':'#718096','PUNCT':'#a0aec0','X':'#4a5568'
                    };
                    const depColor = {
                        'nsubj':'#3182ce','nsubjpass':'#3182ce','obj':'#e53e3e','dobj':'#e53e3e','iobj':'#dd6b20',
                        'obl':'#38a169','amod':'#805ad5','advmod':'#38a169','nmod':'#2b6cb0','det':'#dd6b20',
                        'cc':'#718096','conj':'#a0aec0','aux':'#d53f8c','cop':'#d53f8c','mark':'#718096',
                        'xcomp':'#ed8936','ccomp':'#ed8936','punct':'#a0aec0','root':'#4a5568'
                    };

                    const tokenGap = 130;
                    const marginX = 30;
                    const baseY = 120;
                    const tagY = 85;
                    const arcUnit = 24;
                    const width = marginX * 2 + tokenGap * words.length;
                    let maxHeight = baseY + 40;

                    // Precompute token x positions
                    const xs = words.map((_, i) => marginX + i * tokenGap + tokenGap / 2);

                    // Compute max arc height
                    arcs.forEach(a => {
                        const span = Math.max(1, (a.end - a.start));
                        const h = baseY - (arcUnit * (span + 1));
                        if (h < 20) maxHeight = Math.max(maxHeight, baseY + (arcUnit * (span + 2)));
                    });
                    const height = Math.max(maxHeight, 600);

                    let minPeak = tagY;
                    arcs.forEach(a => {
                        try {
                            const start = Math.max(0, Math.min(words.length - 1, parseInt(a.start, 10)));
                            const end = Math.max(0, Math.min(words.length - 1, parseInt(a.end, 10)));
                            if (isNaN(start) || isNaN(end) || start === end) return;
                            const span = Math.max(1, Math.abs(end - start));
                            const peak = baseY - (arcUnit * (span + 1));
                            if (peak < minPeak) minPeak = peak;
                        } catch (e) { /* ignore */ }
                    });
                    const usedTop = Math.min(minPeak - 12, tagY - 14);
                    const usedBottom = baseY + 40;
                    const usedHeight = usedBottom - usedTop;
                    const initialOffsetY = Math.max(0, (height - usedHeight) / 2 - usedTop);

                    const esc = (s) => String(s == null ? '' : s).replace(/[&<>]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[ch]));
                    const getPosColor = (tag) => posColor[(tag||'').toUpperCase()] || '#4a5568';
                    const getDepColor = (label) => depColor[(label||'').toLowerCase()] || '#718096';
                    const posHuman = (code) => {
                        const map = {
                            'ADJ':'Adjective','ADP':'Adposition','ADV':'Adverb','AUX':'Auxiliary','CCONJ':'Coordinating conjunction',
                            'DET':'Determiner','INTJ':'Interjection','NOUN':'Noun','NUM':'Numeral','PART':'Particle','PRON':'Pronoun',
                            'PROPN':'Proper noun','PUNCT':'Punctuation','SCONJ':'Subordinating conjunction','SYM':'Symbol','VERB':'Verb','X':'Other'
                        };
                        const human = map[(code||'').toUpperCase()] || String(code||'');
                        return i18nLabel(human, human);
                    };
                    const depHuman = (lbl) => {
                        try {
                            const s = String(lbl||'');
                            if (!s) return s;
                            const ud = {
                                'nsubj':'Nominal subject','csubj':'Clausal subject','obj':'Object','iobj':'Indirect object','obl':'Oblique nominal',
                                'det':'Determiner','amod':'Adjectival modifier','advmod':'Adverbial modifier','nmod':'Nominal modifier','cc':'Coordinating conjunction',
                                'conj':'Conjunct','aux':'Auxiliary','cop':'Copula','mark':'Marker','punct':'Punctuation','root':'Root','xcomp':'Open clausal complement',
                                'ccomp':'Clausal complement','appos':'Appositional modifier','case':'Case marking'
                            };
                            const g = {
                                'NSUBJ':'Nominal subject','CSUBJ':'Clausal subject','DOBJ':'Direct object','IOBJ':'Indirect object','POBJ':'Object of preposition',
                                'AUX':'Auxiliary','AUXPASS':'Passive auxiliary','NSUBJPASS':'Nominal subject (passive)','CSUBJPASS':'Clausal subject (passive)',
                                'DET':'Determiner','AMOD':'Adjectival modifier','ADVMOD':'Adverbial modifier','NMOD':'Nominal modifier','CC':'Coordinating conjunction',
                                'CONJ':'Conjunct','COP':'Copula','MARK':'Marker','PUNCT':'Punctuation','ROOT':'Root','XCOMP':'Open clausal complement','CCOMP':'Clausal complement',
                                'APPOS':'Appositional modifier','NEG':'Negation modifier','PREP':'Preposition','PRT':'Particle','ATTR':'Attribute','PARATAXIS':'Parataxis',
                                'TMOD':'Temporal modifier','RCMOD':'Relative clause modifier','EXPL':'Expletive','NUM':'Numeric modifier','NUMBER':'Number','POSS':'Possessive modifier'
                            };
                            let human = g[s] || ud[s.toLowerCase()] || s;
                            // Pattern-based expansion
                            if (!g[s] && !ud[s.toLowerCase()]) {
                                if (s.includes('SUBJ')) {
                                    human = s.startsWith('CSUBJ') ? 'Clausal subject' : 'Nominal subject';
                                    if (s.includes('PASS')) human += ' (passive)';
                                } else if (s.endsWith('OBJ')) {
                                    if (s === 'DOBJ') human = 'Direct object';
                                    else if (s === 'IOBJ') human = 'Indirect object';
                                    else if (s === 'POBJ') human = 'Object of preposition';
                                    else human = 'Object';
                                }
                            }
                            return i18nLabel(human, human);
                        } catch (_) { return String(lbl||''); }
                    };

                    let svg = '';
                    svg += `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMin meet" style="width: 100%; height: 100%; cursor: grab;">
  <style>
    .dep-token rect { fill: #f7fafc; stroke: #e2e8f0; rx: 6; ry: 6; }
    .dep-token text.word { font: 15px/1.1 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif; fill: #1a202c; }
    .dep-token text.tag { font: 12px/1.1 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif; fill: #4a5568; }
    .dep-arc path { fill: none; stroke-width: 1.8; opacity: 0.85; }
    .dep-arc text { font: 12px/1.1 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif; fill: #2d3748; }
    .dep-arc:hover path { stroke-width: 2.6; opacity: 1; }
    .dep-arc:hover text { font-weight: 600; }
    .highlight text.word { fill: #000; font-weight: 600; }
    .highlight rect { stroke: #4c51bf; stroke-width: 2; }
  </style>
  <defs>
    <marker id="arrow-grey" markerWidth="7" markerHeight="7" refX="2.5" refY="2" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L0,4 L4,2 Z" fill="#718096"/>
    </marker>
  </defs>
  <g class="dep-viewport">`;
                    // Draw tokens (background chips + texts)
                    const chipW = tokenGap - 28;
                    const chipH = 34;
                    words.forEach((w, i) => {
                        const x = xs[i];
                        const txt = esc(w.text || '');
                        const tag = esc(posHuman(w.tag || ''));
                        const posC = getPosColor(w.tag);
                        const rectX = x - chipW/2;
                        const rectY = baseY - chipH + 6;
                        svg += `
  <g class="dep-token" data-idx="${i}">
    <rect x="${rectX}" y="${rectY}" width="${chipW}" height="${chipH}" />
    <text x="${x}" y="${tagY}" text-anchor="middle" class="tag" fill="${posC}">${tag}</text>
    <text x="${x}" y="${baseY}" text-anchor="middle" class="word">${txt}</text>
  </g>`;
                    });

                    // Draw arcs
                    arcs.forEach(a => {
                        try {
                            const start = Math.max(0, Math.min(words.length - 1, parseInt(a.start, 10)));
                            const end = Math.max(0, Math.min(words.length - 1, parseInt(a.end, 10)));
                            if (isNaN(start) || isNaN(end) || start === end) return;
                            const x1 = xs[start];
                            const x2 = xs[end];
                            const span = Math.max(1, Math.abs(end - start));
                            const peak = baseY - (arcUnit * (span + 1));
                            const d = `M ${x1} ${baseY-10} C ${x1} ${peak}, ${x2} ${peak}, ${x2} ${baseY-10}`;
                            const label = esc(depHuman(a.label || ''));
                            const color = getDepColor(a.label);
                            // Place label at mid-point
                            const xm = (x1 + x2) / 2;
                            const ym = peak - 8;
                            svg += `
  <g class="dep-arc" data-start="${start}" data-end="${end}">
    <path d="${d}" stroke="${color}" marker-end="url(#arrow-grey)"/>
    <text x="${xm}" y="${ym}" text-anchor="middle">${label}</text>
  </g>`;
                        } catch (e) { /* ignore arc errors */ }
                    });

                    svg += `\n  </g>\n</svg>`;
                    $(containerSel).html(svg);

                    // Interactions: highlight tokens connected by an arc on hover
                    const $svg = $(containerSel).find('svg');
                    $svg.find('.dep-arc').on('mouseenter', function(){
                        const s = parseInt($(this).attr('data-start'), 10);
                        const e = parseInt($(this).attr('data-end'), 10);
                        $svg.find(`.dep-token[data-idx="${s}"]`).addClass('highlight');
                        $svg.find(`.dep-token[data-idx="${e}"]`).addClass('highlight');
                    }).on('mouseleave', function(){
                        $svg.find('.dep-token').removeClass('highlight');
                    });

                    // Add zoom/pan toolbar if not present
                    const $container = $(containerSel);
                    if ($container.find('.dep-toolbar').length === 0) {
                        const toolbar = `
                          <div class="dep-toolbar" style="display:flex; gap:8px; margin-bottom:6px; align-items:center;">
                            <button class="dep-zoom-out" title="${i18nLabel('zoomOut','Zoom out')}" style="padding:4px 8px;">−</button>
                            <button class="dep-zoom-in" title="${i18nLabel('zoomIn','Zoom in')}" style="padding:4px 8px;">+</button>
                            <button class="dep-zoom-reset" title="${i18nLabel('reset','Reset')}" style="padding:4px 8px;">${i18nLabel('reset','Reset')}</button>
                          </div>`;
                        $container.prepend(toolbar);
                    }

                    // Pan/zoom behavior using transform on .dep-viewport
                    const $vp = $svg.find('g.dep-viewport');
                    const state = { scale: 1, tx: 0, ty: initialOffsetY, panning: false, lx: 0, ly: 0, scheduled: false };
                    const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
                    const apply = () => {
                        $vp.attr('transform', `translate(${state.tx},${state.ty}) scale(${state.scale})`);
                        state.scheduled = false;
                    };
                    const minScale = 0.05, maxScale = 100; // almost "infinite" zoom range

                    apply();

                    // Wheel zoom
                    $svg.on('wheel', function(e){
                        e.preventDefault();
                        const delta = e.originalEvent.deltaY;
                        const factor = delta > 0 ? 0.9 : 1.1;
                        const rect = this.getBoundingClientRect();
                        const cx = e.clientX - rect.left;
                        const cy = e.clientY - rect.top;
                        const s1 = state.scale;
                        const s2 = clamp(s1 * factor, minScale, maxScale);
                        const px = (cx - state.tx) / s1;
                        const py = (cy - state.ty) / s1;
                        state.tx = cx - px * s2;
                        state.ty = cy - py * s2;
                        state.scale = s2;
                        if (!state.scheduled) {
                            state.scheduled = true;
                            requestAnimationFrame(apply);
                        }
                    });
                    // Drag pan
                    $svg.on('mousedown', function(e){
                        e.preventDefault();
                        state.panning = true; state.lx = e.clientX; state.ly = e.clientY; $svg.css('cursor','grabbing');
                    });
                    $(document).on('mousemove.depPan', function(e){
                        if (!state.panning) return;
                        e.preventDefault();
                        // Panning speed is adaptive to feel more responsive when zoomed in.
                        // The multiplier increases more aggressively as the scale factor grows.
                        const adaptiveMultiplier = 1.5 * Math.max(1, state.scale * 0.75);
                        const dx = (e.clientX - state.lx) * adaptiveMultiplier;
                        const dy = (e.clientY - state.ly) * adaptiveMultiplier;
                        state.lx = e.clientX;
                        state.ly = e.clientY;
                        state.tx += dx;
                        state.ty += dy;
                        if (!state.scheduled) {
                            state.scheduled = true;
                            requestAnimationFrame(apply);
                        }
                    });
                    $(document).on('mouseup.depPan', function(){ if (state.panning) { state.panning = false; $svg.css('cursor','grab'); } });
                    $svg.on('mouseleave', function(){ if (state.panning) { state.panning = false; $svg.css('cursor','grab'); } });

                    // Buttons
                    const zoomAroundPoint = (cx, cy, factor) => {
                        const s1 = state.scale;
                        const s2 = clamp(s1 * factor, minScale, maxScale);
                        const px = (cx - state.tx) / s1;
                        const py = (cy - state.ty) / s1;
                        state.tx = cx - px * s2;
                        state.ty = cy - py * s2;
                        state.scale = s2;
                        apply();
                    };
                    $container.find('.dep-zoom-in').off('click').on('click', function(){
                        const rect = $svg[0].getBoundingClientRect();
                        zoomAroundPoint(rect.width/2, rect.height/2, 1.2);
                    });
                    $container.find('.dep-zoom-out').off('click').on('click', function(){
                        const rect = $svg[0].getBoundingClientRect();
                        zoomAroundPoint(rect.width/2, rect.height/2, 1/1.2);
                    });
                    $container.find('.dep-zoom-reset').off('click').on('click', function(){ state.scale = 1; state.tx = 0; state.ty = 0; apply(); });
                } catch (e) {
                    console.warn('Simple dependency renderer failed:', e);
                    $(containerSel).html(`<p class="text-secondary" style="color:#65676b">${i18nLabel('dependencyVisFailed','Dependency visualization failed.')}</p>`);
                }
            };

            if (!hasWrong && !hasCorrect) {
                $('#dep-wrong, #dep-correct').html(`<p class="text-secondary" style="color:#65676b">${i18nLabel('noDepDataGlobal','No dependency data available. Run Google NLP to populate tokens.')}</p>`);
            } else {
                if (hasWrong) {
                    renderSimpleDep('#dep-wrong', wrong);
                } else {
                    $('#dep-wrong').html(`<p class="text-secondary" style="color:#65676b">${i18nLabel('noDepDataWrong','No dependency data for wrong text.')}</p>`);
                }
                if (hasCorrect) {
                    renderSimpleDep('#dep-correct', correct);
                } else {
                    $('#dep-correct').html(`<p class="text-secondary" style="color:#65676b">${i18nLabel('noDepDataCorrect','No dependency data for correct text.')}</p>`);
                }
            }
        }
    } else {
        // Legacy simple format
        if (!output || (!output.conclusion && (!output.inconsistencies || output.inconsistencies.length === 0))) {
            container.html('<p><strong>Analysis:</strong> No analysis available.</p>');
            return;
        }
        const conclusionHtml = output.conclusion ? `<p class=\"analysis-conclusion\">${output.conclusion}</p>` : '';
        let inconsistenciesHtml = '';
        if (Array.isArray(output.inconsistencies) && output.inconsistencies.length > 0) {
            inconsistenciesHtml = '<ul class=\"analysis-list\">' + output.inconsistencies.map(it => `<li>${it}</li>`).join('') + '</ul>';
        }
        const pairIdAttr = container.attr('data-pair-id') || '';
        container.html(`
            <div class=\"analysis-card\" data-pair-id=\"${pairIdAttr}\">\n                <div class=\"analysis-card-header\">\n                    <div class=\"title\"><i class=\"fas fa-chart-line\"></i> ${i18nLabel('nlpAnalysisTitle','NLP Analysis')}</div>\n                    <div class=\"actions\">\n                        <button class=\"analysis-refresh\" title=\"${i18nLabel('refreshTooltip','Refresh')}\"><i class=\"fas fa-sync\"></i></button>\n                        <button class=\"analysis-collapse\" title=\"${i18nLabel('collapseExpandTooltip','Collapse/Expand')}\"><i class=\"fas fa-chevron-up\"></i></button>\n                    </div>\n                </div>\n                <div class=\"analysis-card-body\">\n                    ${conclusionHtml}\n                    ${inconsistenciesHtml}\n                </div>\n            </div>
        `);
    }

    // Bind actions
    container.find('.analysis-collapse').off('click').on('click', function() {
        const card = container.find('.analysis-card');
        card.toggleClass('collapsed');
        const isCollapsed = card.hasClass('collapsed');
        localStorage.setItem('nlpAnalysisCollapsed', isCollapsed);
        const icon = $(this).find('i');
        if (isCollapsed) {
            icon.removeClass('fa-chevron-up').addClass('fa-chevron-down');
        } else {
            icon.removeClass('fa-chevron-down').addClass('fa-chevron-up');
        }
    });

    // Restore collapsed state from localStorage
    const isCollapsed = localStorage.getItem('nlpAnalysisCollapsed') === 'true';
    if (isCollapsed) {
        const card = container.find('.analysis-card');
        card.addClass('collapsed');
        const icon = container.find('.analysis-collapse i');
        icon.removeClass('fa-chevron-up').addClass('fa-chevron-down');
    }
    container.find('.analysis-refresh').off('click').on('click', function() {
        const pid = container.attr('data-pair-id');
        const btn = $(this);
        const icon = btn.find('i');
        if (pid) {
            btn.prop('disabled', true);
            icon.addClass('fa-spin');
            const req = loadLinguisticAnalysis(parseInt(pid, 10), true);
            try { loadNerAnalysis(parseInt(pid, 10), true); } catch (e) {}
            const done = () => { icon.removeClass('fa-spin'); btn.prop('disabled', false); };
            if (req && typeof req.always === 'function') {
                req.always(done);
            } else {
                done();
            }
        }
    });
}

function loadLinguisticAnalysis(pairId, forceRefresh=false) {
    nlpConclusion = null;
    const container = $('.analysis-output');
    const existingCard = container.find('.analysis-card');
    container.attr('data-pair-id', pairId);
    if (existingCard.length) {
        existingCard.find('.analysis-card-body').html(`<p class="analysis-conclusion">${i18nLabel('refreshingAnalysis','Refreshing analysis...')}</p>`);
    } else {
    container.html(`<div class="analysis-card"><div class="analysis-card-header"><div class="title"><i class="fas fa-chart-line"></i> ${i18nLabel('nlpAnalysisTitle','NLP Analysis')}</div><div class="actions"><button class="analysis-refresh" title="${i18nLabel('refreshTooltip','Refresh')}"><i class="fas fa-sync"></i></button><button class="analysis-collapse" title="${i18nLabel('collapseExpandTooltip','Collapse/Expand')}"><i class="fas fa-chevron-up"></i></button></div></div><div class="analysis-card-body"><p class="analysis-conclusion">${i18nLabel('loadingAnalysis','Loading analysis...')}</p></div></div>`);
    }
    // Use AI enrichment only on manual refresh to save RPM; default loads use heuristics only
    const qs = forceRefresh ? '?refresh=1&ai=1&debug=1' : '?ai=1';
    return $.ajax({
        url: `/api/linguistic_analysis/${encodeURIComponent(projectName)}/${pairId}${qs}`,
        type: 'GET',
        success: function(result) {
            // Normalize response shape
            nlpConclusion = result && result.response ? result.response : result;
            renderLinguisticAnalysis(nlpConclusion);
        },
        error: function(xhr, status, error) {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) ? xhr.responseJSON.error : 'Could not load analysis.';
            console.error('Error loading analysis:', error, msg);
            container.html(`<p><strong>Analysis:</strong> ${msg}</p>`);
        }
    });
}

function loadNerAnalysis(pairId, forceRefresh=false) {
    const qs = forceRefresh ? '?refresh=1' : '';
    return $.ajax({
        url: `/api/ner_analysis/${encodeURIComponent(projectName)}/${pairId}${qs}`,
        type: 'GET',
        success: function(result) {
            window.nerAnalysisData = result;
            const container = $('.analysis-output');
            const tabsHeader = container.find('.analysis-tabs');
            const hasNerBtn = tabsHeader.find('.analysis-tab-btn[data-tab="ner"]').length > 0;
            const nerHtml = renderNerAnalysis(result);
            // If the analysis card is already rendered/cached and lacks the NER tab, inject it incrementally
            if (tabsHeader.length && !hasNerBtn) {
                // 1) Add the NER tab button
                const nerBtn = $(`<button class="analysis-tab-btn" data-tab="ner">${i18nLabel('tabNer','NER')}</button>`);
                tabsHeader.append(nerBtn);
                // 2) Add the NER tab content container
                const body = container.find('.analysis-card-body');
                if (body.find('.analysis-tab-content[data-tab="ner"]').length === 0) {
                    body.append(`<div class="analysis-tab-content" data-tab="ner">${nerHtml}</div>`);
                }
                // 3) Bind click handler for the new button (mirror existing behavior)
                nerBtn.on('click', function() {
                    const tab = $(this).data('tab');
                    container.find('.analysis-tab-btn').removeClass('active');
                    $(this).addClass('active');
                    container.find('.analysis-tab-content').removeClass('active');
                    container.find(`.analysis-tab-content[data-tab="${tab}"]`).addClass('active');
                });
            } else {
                // If NER tab is already there (e.g., from bundled payload), update its content with qualitative enrichments
                const nerPane = container.find('.analysis-tab-content[data-tab="ner"]');
                if (nerPane.length) {
                    nerPane.html(nerHtml);
                } else if (nlpConclusion) {
                    // As a fallback, re-render to integrate NER
                    renderLinguisticAnalysis(nlpConclusion);
                }
            }
        },
        error: function(xhr, status, error) {
            console.error('Error loading NER analysis:', error);
        }
    });
}

function renderNerAnalysis(output) {
    const normalized = output && output.ner_analysis ? output.ner_analysis : {};
    const renderNerTable = (data) => {
        if (!Array.isArray(data) || data.length === 0) {
            return `<p class="text-secondary" style="color:#65676b">${i18nLabel('noFindings','No findings.')}</p>`;
        }
        let table = `<table class="ner-table"><thead><tr><th>${i18nLabel('colName','Name')}</th><th>${i18nLabel('colType','Type')}</th><th>${i18nLabel('colContent','Content')}</th></tr></thead><tbody>`;
        data.forEach(entity => {
            const name = entity && entity.name != null ? String(entity.name) : '';
            const typ = entity && entity.type != null ? String(entity.type) : '';
            const content = entity && entity.content != null ? String(entity.content) : '';
            table += `<tr><td>${name}</td><td>${typ}</td><td>${content}</td></tr>`;
        });
        table += '</tbody></table>';
        return table;
    };

    let qualitativeHtml = '';
    if (normalized.qualitative_analysis) {
        const qa = normalized.qualitative_analysis;
        const findings = (Array.isArray(qa.findings) ? qa.findings : []);
        const findingsList = findings.length
            ? '<ul class="analysis-list">' + findings.map(f => {
                const lbl = (f && f.label) ? String(f.label) : '';
                const explHtml = md.render(String((f && f.explanation) ? f.explanation : ''));
                return `<li>${lbl ? `<strong>${lbl}</strong>:` : ''}<div>${explHtml}</div></li>`;
              }).join('') + '</ul>'
            : `<p class="text-secondary" style="color:#65676b">${i18nLabel('noFindings','No findings.')}</p>`;
        qualitativeHtml = `
            <div class="qualitative-ner-analysis">
                ${qa.summary ? `<div>${md.render(String(qa.summary))}</div>` : ''}
                <h5>${i18nLabel('divergenceFindings','Divergence Findings')}</h5>
                ${findingsList}
                ${qa.interpretation ? `<h5>${i18nLabel('interdisciplinaryInterpretation','Interdisciplinary Interpretation')}</h5><div>${md.render(String(qa.interpretation))}</div>` : ''}
            </div>
        `;
    }

    const wrongHtml = renderNerTable(normalized.wrong || []);
    const correctHtml = renderNerTable(normalized.correct || []);
    return `
        <div class="ner-container">
            ${qualitativeHtml}
            <h5>${i18nLabel('wrongText','Wrong Text')}</h5>
            ${wrongHtml}
            <h5>${i18nLabel('correctText','Correct Text')}</h5>
            ${correctHtml}
        </div>
    `;
}

function loadChatHistory(pairId) {
    const chatHistory = $('#chat-history');
    chatHistory.empty();

    $.ajax({
        url: `/api/chat_history/${encodeURIComponent(projectName)}/${pairId}`,
        type: 'GET',
        success: function(history) {
            history.forEach(function(message) {
                const formattedMessage = md.render(message.message);
                const messageClass = message.sender === 'user' ? 'user' : 'ai';
                let messageHtml = `<div class="chat-message ${messageClass}">${messageClass === 'user' ? `<p>${formattedMessage}</p>` : ''}</div>`;

                if (messageClass === 'ai') {
                    const messageId = `ai-message-${message.id}`; // Assuming message has a unique ID
                    messageHtml = `
                        <div class="chat-message ai" id="${messageId}">
                            <div class="ai-content">${formattedMessage}</div>
                            <button class="add-to-notes-btn" data-message-id="${messageId}">
                                <i class="fas fa-plus"></i> <span>Add to Notes</span>
                            </button>
                        </div>`;
                }
                chatHistory.append(messageHtml);
            });
            chatHistory.scrollTop(chatHistory[0].scrollHeight);
        },
        error: function(xhr, status, error) {
            console.error('Error loading chat history:', error);
            chatHistory.append(`<div class="chat-message ai"><p>Could not load chat history.</p></div>`);
        }
    });
}

function loadNotes(pairId) {
    const notesList = $('#notes-list');
    notesList.empty();

    $.ajax({
        url: `/api/notes/${encodeURIComponent(projectName)}/${pairId}`,
        type: 'GET',
        success: function(notes) {
            notes.forEach(function(note) {
                const noteItem = $(`
                    <div class="note-item" data-content="${escape(note.content)}">
                        <div class="note-item-header">
                            <h5>${note.title}</h5>
                            <div class="note-item-actions">
                                <button class="edit-note-btn" data-id="${note.id}" data-title="${note.title}"><i class="fas fa-edit"></i></button>
                                <button class="delete-note-btn" data-id="${note.id}"><i class="fas fa-trash"></i></button>
                            </div>
                        </div>
                        <div class="note-item-content"></div>
                    </div>
                `);
                noteItem.find('.note-item-content').html(note.content);
                notesList.append(noteItem);
            });
        },
        error: function(xhr, status, error) {
            console.error('Error loading notes:', error);
            notesList.append('<p>Could not load notes.</p>');
        }
    });
}





$(document).ready(function () {
    
    // Note Editor Modal
    const noteModal = $('#note-editor-modal');

    // Initialize Quill editor for notes
    noteQuillEditor = new Quill('#note-quill-editor', {
        theme: 'snow',
        modules: {
            toolbar: [
                [{ 'header': [1, 2, false] }],
                ['bold', 'italic', 'underline'],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                ['clean']
            ]
        }
    });

    // Open modal to add a new note
    $('#add-note-btn').on('click', function() {
        $('#note-modal-title').text('Create Note');
        $('#note-id-input').val('');
        $('#note-title-input').val('');
        // Clear editor content properly
        if (noteQuillEditor && noteQuillEditor.setContents) {
            noteQuillEditor.setContents([]);
        } else {
            noteQuillEditor.root.innerHTML = '';
        }
        $('#note-editor-modal').addClass('show');
    });

    // Open modal to edit an existing note
    $('#notes-list').on('click', '.edit-note-btn', function() {
        const noteId = $(this).data('id');
        const noteTitle = $(this).data('title');
        const noteContent = $(this).closest('.note-item').data('content');

        $('#note-modal-title').text('Edit Note');
        $('#note-id-input').val(noteId);
        $('#note-title-input').val(noteTitle);
        // Paste full HTML content so lists and formatting are preserved in the editor
        const htmlContent = unescape(noteContent);
        if (noteQuillEditor && noteQuillEditor.clipboard && noteQuillEditor.clipboard.dangerouslyPasteHTML) {
            noteQuillEditor.clipboard.dangerouslyPasteHTML(htmlContent);
        } else {
            noteQuillEditor.root.innerHTML = htmlContent;
        }
        $('#note-editor-modal').addClass('show');
    });

    // Save or update a note
    $('#save-note-btn').on('click', function() {
        const noteId = $('#note-id-input').val();
        const title = $('#note-title-input').val().trim();
        const content = noteQuillEditor.root.innerHTML;
        const currentPairId = selectedElementPairId || (textPairs.length > 0 ? textPairs[0].id : null);

        if (!title) {
            Swal.fire('Missing title', 'Please enter a title for the note.', 'warning');
            return;
        }
        if (!currentPairId) {
            Swal.fire('Unavailable', 'Cannot save note, no text pair selected.', 'warning');
            return;
        }

        const url = noteId ? `/api/notes/${noteId}` : '/api/notes';
        const method = noteId ? 'PUT' : 'POST';
        const data = {
            project_name: projectName,
            pair_id: currentPairId,
            title: title,
            content: content
        };

        $.ajax({
            url: url,
            type: method,
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function() {
                $('#note-editor-modal').removeClass('show');
                loadNotes(currentPairId);
            },
            error: function(xhr, status, error) {
                console.error('Error saving note:', error);
                Swal.fire('Error', 'Error saving note. Please try again.', 'error');
            }
        });
    });

    // Delete a note
    $('#notes-list').on('click', '.delete-note-btn', function() {
        const noteId = $(this).data('id');
        const currentPairId = selectedElementPairId || (textPairs.length > 0 ? textPairs[0].id : null);

        Swal.fire({
            title: 'Delete this note?',
            text: 'This action cannot be undone.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Delete',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                $.ajax({
                    url: `/api/notes/${encodeURIComponent(projectName)}/${noteId}`,
                    type: 'DELETE',
                    success: function() {
                        loadNotes(currentPairId);
                        Swal.fire('Deleted', 'The note has been deleted.', 'success');
                    },
                    error: function(xhr, status, error) {
                        console.error('Error deleting note:', error);
                        Swal.fire('Error', 'Error deleting note. Please try again.', 'error');
                    }
                });
            }
        });
    });

    // Close note modal
    $('.close-note-modal').on('click', function() {
        $('#note-editor-modal').removeClass('show');
    });

    // AI Chat Functionality
    const chatHistory = $('#chat-history');
    const scrollToBottomBtn = $('#scroll-to-bottom-btn');

        function handleAutoTagPlanRequest(instruction) {
        const chatHistory = $('#chat-history');
        const userMessageHtml = `<div class="chat-message user"><p>${instruction}</p></div>`;
        chatHistory.append(userMessageHtml);
        chatHistory.scrollTop(chatHistory[0].scrollHeight);
        $('#chat-input-field').val('');

        chatHistory.append(`
            <div class="chat-message ai" id="typing-indicator">
                <div class="typing-indicator-container">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        `);
        chatHistory.scrollTop(chatHistory[0].scrollHeight);

        var projectName = getUrlParameter('project_name');

        const currentPairId = selectedElementPairId || (textPairs.length > 0 ? textPairs[0].id : null);
        if (currentPairId === null) {
            $('#typing-indicator').remove();
            const errorMessageHtml = `<div class="chat-message ai error-message"><p>Please select a text pair first.</p></div>`;
            chatHistory.append(errorMessageHtml);
            return;
        }
        const pairData = textPairs.find(p => p.id === currentPairId);
        const wrongText = pairData ? pairData.error_text : '';
        const correctText = pairData ? pairData.corrected_text : '';

        fetch('/api/auto_tag/plan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                project_name: projectName,
                instruction: instruction,
                wrong_text: wrongText,
                correct_text: correctText,
                model_name: selectedModel
            }),
        })
        .then(response => response.json())
        .then(plan => {
            $('#typing-indicator').remove();
            if (plan.error) {
                const errorMessageHtml = `<div class="chat-message ai error-message"><p>${plan.error}</p></div>`;
                chatHistory.append(errorMessageHtml);
            } else {
                renderPlanCard(plan);
            }
            chatHistory.scrollTop(chatHistory[0].scrollHeight);
        })
        .catch(error => {
            $('#typing-indicator').remove();
            console.error('Error fetching auto-tag plan:', error);
            const errorMessageHtml = `<div class="chat-message ai error-message"><p>An error occurred while generating the plan.</p></div>`;
            chatHistory.append(errorMessageHtml);
            chatHistory.scrollTop(chatHistory[0].scrollHeight);
        });
    }

    function renderPlanCard(plan) {
        const isRunnable = plan.machine_readable_plan && plan.machine_readable_plan.is_runnable;
        const startButton = isRunnable ? `<button class="plan-btn start-tagging-btn">${i18nLabel('Start Tagging', 'Start Tagging')}</button>` : '';
        const randomId = Math.random().toString(36).substring(7);
        const planCardHtml = `
            <div class="chat-message ai plan-card" data-instruction="${plan.instruction}">
                <div class="plan-card-header">
                    <i class="fas fa-tasks"></i>
                    <h4>${i18nLabel('Auto-Tagging Plan', 'Auto-Tagging Plan')}</h4>
                </div>
                <div class="plan-card-body">
                    <p>${plan.description}</p>
                    <div class="plan-details">
                        <span>${i18nLabel('Tag to apply:', 'Tag to apply:')} <strong class="tag-badge">${plan.tag_to_apply}</strong></span>
                    </div>
                    <div class="autotag-target-selector" style="margin-top: 10px;">
                        <span style="margin-right: 10px;">${i18nLabel('Please select the text to tag:', 'Please select the text to tag:')}</span>
                        <label><input type="radio" name="autotag-target-${randomId}" value="wrong_text" checked> ${i18nLabel('wrongText', 'Wrong Text')}</label>
                        <label style="margin-left: 10px;"><input type="radio" name="autotag-target-${randomId}" value="correct_text"> ${i18nLabel('correctText', 'Correct Text')}</label>
                        <label style="margin-left: 10px;"><input type="radio" name="autotag-target-${randomId}" value="both"> ${i18nLabel('Both', 'Both')}</label>
                    </div>
                </div>
                <div class="plan-card-actions">
                    <button class="plan-btn edit-plan-btn">${i18nLabel('Edit', 'Edit')}</button>
                    ${startButton}
                </div>
                <div class="plan-card-status"></div>
            </div>
        `;
        const chatHistory = $('#chat-history');
        chatHistory.append(planCardHtml);
        chatHistory.scrollTop(chatHistory[0].scrollHeight);

        $('.edit-plan-btn').last().on('click', function() {
            const planCard = $(this).closest('.plan-card');
            const instruction = planCard.data('instruction');
            $('#chat-input-field').val(instruction).focus();
            planCard.remove();
        });

        if (isRunnable) {
            $('.start-tagging-btn').last().on('click', function() {
                const planCard = $(this).closest('.plan-card');
                const targetText = planCard.find('input[name^="autotag-target"]:checked').val();
                const currentPairId = selectedElementPairId || (textPairs.length > 0 ? textPairs[0].id : null);
                if (currentPairId === null) {
                    Swal.fire('Error', 'Please select a text pair first.', 'error');
                    return;
                }

                $(this).text(i18nLabel('Starting...', 'Starting...')).prop('disabled', true);

                fetch('/api/auto_tag/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        project_name: projectName,
                        plan: plan,
                        pair_id: currentPairId,
                        target_text: targetText
                    }),
                })
                .then(response => response.json())
                .then(result => {
                    if (result.error) {
                        planCard.find('.plan-card-status').html(`<p class="error-message">Error: ${result.error}</p>`);
                        $(this).text(i18nLabel('Start Tagging', 'Start Tagging')).prop('disabled', false);
                    } else {
                        planCard.find('.plan-card-actions').html(`<span class="tagging-inprogress"><i class="fas fa-spinner fa-spin"></i> ${i18nLabel('Tagging in progress...', 'Tagging in progress...')}</span>`);
                        pollJobStatus(planCard, result.job_id);
                    }
                })
                .catch(error => {
                    console.error('Error executing auto-tag plan:', error);
                    planCard.find('.plan-card-status').html(`<p class="error-message">An unexpected error occurred.</p>`);
                    $(this).text(i18nLabel('Start Tagging', 'Start Tagging')).prop('disabled', false);
                });
            });
        }
    }

    function pollJobStatus(planCard, jobId) {
        const interval = setInterval(() => {
            fetch(`/api/auto_tag/status/${jobId}?project_name=${encodeURIComponent(projectName)}`)
                .then(response => response.json())
                .then(job => {
                    if (job.status === 'SUCCESS' || job.status === 'FAILURE' || job.status === 'SUCCESS_NO_ANNOTATIONS') {
                        clearInterval(interval);
                        let resultMessage = '';
                        if (job.status === 'SUCCESS') {
                            const result = JSON.parse(job.result);
                            const message = i18nLabel('Tagging Complete: {count} annotations created.', 'Tagging Complete: {count} annotations created.').replace('{count}', result.annotations_created);
                            resultMessage = `<span class="tagging-complete"><i class="fas fa-check-circle"></i> ${message}</span>`;
                            // Refresh annotations overlay and tags list in UI
                            if (typeof loadAndDisplayAnnotations === 'function') {
                                loadAndDisplayAnnotations();
                            }
                            if (typeof loadTags === 'function') {
                                loadTags();
                            }
                        } else if (job.status === 'SUCCESS_NO_ANNOTATIONS') {
                            const result = JSON.parse(job.result);
                            const detail = result.detail || i18nLabel('No annotations created.', 'No annotations created.');
                            const message = i18nLabel('Auto-tagging finished: {detail}', 'Auto-tagging finished: {detail}').replace('{detail}', detail);
                            resultMessage = `<span class="tagging-complete"><i class="fas fa-exclamation-triangle"></i> ${message}</span>`;
                            // Still refresh annotations and tags in case something changed
                            if (typeof loadAndDisplayAnnotations === 'function') {
                                loadAndDisplayAnnotations();
                            }
                            if (typeof loadTags === 'function') {
                                loadTags();
                            }
                        } else { // job.status === 'FAILURE'
                            const result = JSON.parse(job.result);
                            const message = i18nLabel('Tagging Failed: {error}', 'Tagging Failed: {error}').replace('{error}', result.error);
                            resultMessage = `<p class="error-message">${message}</p>`;
                        }
                        planCard.find('.plan-card-actions').html(resultMessage);
                    }
                })
                .catch(error => {
                    clearInterval(interval);
                    console.error('Error polling job status:', error);
                    planCard.find('.plan-card-actions').html(`<p class="error-message">${i18nLabel('Error checking job status.', 'Error checking job status.')}</p>`);
                });
        }, 2000); // Poll every 2 seconds
    }

    $('#send-chat-btn').on('click', function() {
        const activeTool = $('#chat-input-container').data('active-tool');
        const message = $('#chat-input-field').val().trim();

        if (!message) return;

        if (activeTool === 'auto-tag') {
            handleAutoTagPlanRequest(message);
        } else {
            sendChatMessage();
        }
    });

    $('#chat-input-field').on('keypress', function(e) {
        if (e.which === 13) { // Enter key
            e.preventDefault();
            const activeTool = $('#chat-input-container').data('active-tool');
            const message = $('#chat-input-field').val().trim();

            if (!message) return;

            if (activeTool === 'auto-tag') {
                handleAutoTagPlanRequest(message);
            } else {
                sendChatMessage(selectedModel);
            }
        }
    });

    // Show/hide scroll-to-bottom button
    chatHistory.on('scroll', function() {
        if (chatHistory.scrollTop() + chatHistory.innerHeight() < chatHistory[0].scrollHeight - 100) {
            scrollToBottomBtn.addClass('visible');
        } else {
            scrollToBottomBtn.removeClass('visible');
        }
    });

    // Scroll to bottom on button click
    scrollToBottomBtn.on('click', function() {
        chatHistory.animate({ scrollTop: chatHistory[0].scrollHeight }, 300);
    });
    
    // Initial application of visual tags when the page loads
    applyVisualTags();

    

    // Initialize model selector UI on first load
    try {
        $('.model-btn').removeClass('active');
        $(`.model-btn[data-model="${selectedModel}"]`).addClass('active');
    } catch(e){}

    // Tab functionality
    $('.tab-link').click(function() {
        var tabName = $(this).data('tab');

        $('.tab-content').removeClass('active');
        $('#' + tabName).addClass('active');

        $('.tab-link').removeClass('active');
        $(this).addClass('active');
    });

    // Model selector behavior
    $(document).on('click', '.model-btn', function(){
        const model = $(this).data('model');
        if (!model) return;
        selectedModel = String(model);
        try { localStorage.setItem('ea_model', selectedModel); } catch(e){}
        $('.model-btn').removeClass('active');
        $(this).addClass('active');
        // Re-run analysis for current pair on model change (force refresh)
        try {
            const currentPairId = selectedElementPairId || (textPairs && textPairs.length ? textPairs[0].id : null);
            if (currentPairId) {
                loadLinguisticAnalysis(currentPairId, true);
            }
        } catch (_) {}
    });

    // Helper to clear any current selection highlight and reset Selected Text
    function clearSelectedTextSelection() {
        try {
            $('.text-card span').removeClass('selected-text-highlight');
            $('.text-card .annotation-span').removeClass('selected-annotation-highlight');
            selectedElementText = '';
            selectedElementType = null;
            selectedElementPosWrong = null;
            selectedElementPosCorrect = null;
            selectedElementPosDiff = null;
            selectedElementPairId = null;
            $('.selected-text-content').text('');
            $('.selected-text').hide();
            updateTagCheckboxesForSelectedElement();
        } catch (e) {}
    }

    // Handle click events on text spans for selection and tagging
    $('#left-panel').on('click', '.text-card', function(e) {
        const target = $(e.target);
        
        // Check if the click was on an annotation span or within one
        const annotationSpan = target.closest('.annotation-span');

        if (annotationSpan.length > 0) {
            // Clear previous only when we will highlight
            $('.text-card span').removeClass('selected-text-highlight');
            $('.text-card .annotation-span').removeClass('selected-annotation-highlight');
            // --- A tagged portion was clicked ---
            // Highlight the innermost annotation that was clicked
            annotationSpan.addClass('selected-annotation-highlight');

            // Update selected text display to show the whole annotation's text
            selectedElementText = annotationSpan.text();
            $('.selected-text-content').text(`"${selectedElementText}"`);
            $('.selected-text').show();

            // Clear data attributes since a tag is selected, not a specific element
            selectedElementType = null;
            selectedElementPosWrong = null;
            selectedElementPosCorrect = null;
            selectedElementPosDiff = null;
            // Infer current pair id from containing result card
            let pid = null;
            const host = annotationSpan.closest('[id^="result_wrong_"], [id^="result_correct_"], [id^="result_diff_"]');
            if (host && host.length) {
                const m = host.attr('id').match(/_(\d+)$/);
                if (m) pid = parseInt(m[1], 10);
            }
            if (!pid && typeof textPairs !== 'undefined' && textPairs.length) pid = textPairs[0].id;
            selectedElementPairId = pid || null;

        } else if (target.is('span') && target.data('pos-wrong') !== undefined) {
            // Only enable exploration selection when exploreSelectionActive is true
            if (!exploreSelectionActive) {
                clearSelectedTextSelection();
                return;
            }
            // Clear previous only when we will highlight
            $('.text-card span').removeClass('selected-text-highlight');
            $('.text-card .annotation-span').removeClass('selected-annotation-highlight');
            // --- A regular, untagged span was clicked (Exploration Mode) ---
            const posWrong = target.data('pos-wrong');
            const posCorrect = target.data('pos-correct');
            const posDiff = target.data('pos-diff');
            const pairId = target.data('pair-id');

            // Add highlight to all matching spans
            $(`span[data-pos-wrong="${posWrong}"][data-pos-correct="${posCorrect}"][data-pos-diff="${posDiff}"][data-pair-id="${pairId}"]`).addClass('selected-text-highlight');

            // Update selected text display in the center panel
            selectedElementText = target.text();
            $('.selected-text-content').text(`"${selectedElementText}"`);
            $('.selected-text').show();

            // Store data attributes for tagging
            selectedElementType = target.data('type');
            selectedElementPosWrong = posWrong;
            selectedElementPosCorrect = posCorrect;
            selectedElementPosDiff = posDiff;
            selectedElementPairId = pairId;
        } else {
            // Clicked in the text area but not on an annotation or token span
            clearSelectedTextSelection();
        }

        // Update checkboxes for the current selection state
        updateTagCheckboxesForSelectedElement();
    });

    // Handle change event for tag checkboxes
    $('.tag-list').on('change', 'input[type="checkbox"]:not(.tag-checkbox)', function() {
        if (selectedElementPairId === null) {
            Swal.fire('Select text', 'Please select a text element first.', 'info');
            $(this).prop('checked', !this.checked); // Revert checkbox state
            return;
        }

        const tagName = $(this).val();
        const isActive = this.checked;

        const data = {
            name: tagName,
            active: isActive,
            elementText: selectedElementText,
            elementType: selectedElementType,
            elementPosWrong: selectedElementPosWrong,
            elementPosCorrect: selectedElementPosCorrect,
            elementPosDiff: selectedElementPosDiff,
            elementDataPairId: selectedElementPairId,
            project_name: projectName
        };

        sendHighlightData('/update_highlight', data);
    });

    // Handle new tag creation
    $('#add-tag-btn').on('click', function() {
        $('#tag-modal-title').text('Add New Tag');
        $('#tag-id-input').val('');
        $('#tag-name-input').val('');
        $('#tag-description-input').val('');
        $('#parent-tag-select').val('');
        loadParentTags();
        $('#add-edit-tag-modal').addClass('show');
    });

    // Handle edit tag button click
    $('#project-tags-list').on('click', '.edit-tag-btn', function() {
        const tagId = $(this).data('id');
        const tagName = $(this).data('name');
        const tagDescription = $(this).data('description');
        const tagColor = $(this).data('color');
        const parentTagId = $(this).closest('ul').closest('li').data('tag-id');

        $('#tag-modal-title').text('Edit Tag');
        $('#tag-id-input').val(tagId);
        $('#tag-name-input').val(tagName);
        $('#tag-description-input').val(tagDescription);
        $('#tag-color-input').val(tagColor);
        loadParentTags(tagId, parentTagId); // Pass current tag's ID and its parent's ID
        $('#add-edit-tag-modal').addClass('show');
    });

    // Handle save tag button click
    $('#save-tag-btn').on('click', function() {
        const tagId = $('#tag-id-input').val();
        const tagName = $('#tag-name-input').val().trim();
        const tagDescription = $('#tag-description-input').val().trim();
        const parentTagId = $('#parent-tag-select').val();
        const tagColor = $('#tag-color-input').val();

        if (tagName === '') {
            Swal.fire('Missing name', 'Please enter a tag name.', 'warning');
            return;
        }

        const url = tagId ? `/api/tags/${tagId}` : '/api/tags';
        const method = tagId ? 'PUT' : 'POST';

        const data = {
            name: tagName,
            description: tagDescription,
            project_name: projectName,
            parent_tag_id: parentTagId || null,
            color: tagColor
        };

        $.ajax({
            url: url,
            type: method,
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(response) {
                console.log('Tag saved successfully:', response);
                $('#add-edit-tag-modal').removeClass('show');
                loadTags(); // Reload tags to display the new/updated one
            },
            error: function(xhr, status, error) {
                console.error('Error saving tag:', error);
                Swal.fire('Error', 'Error saving tag. Please try again.', 'error');
            }
        });
    });

    // Function to load parent tags into the select dropdown
    function loadParentTags(excludeTagId = null, selectedParentId = null) {
        $.ajax({
            url: `/api/tags?project_name=${encodeURIComponent(projectName)}`,
            type: 'GET',
            success: function(tags) {
                const parentTagSelect = $('#parent-tag-select');
                parentTagSelect.empty().append('<option value="">None</option>');
                tags.forEach(tag => {
                    if (tag.id !== excludeTagId) {
                        const option = $(`<option value="${tag.id}">${tag.name}</option>`);
                        if (tag.id === selectedParentId) {
                            option.prop('selected', true);
                        }
                        parentTagSelect.append(option);
                    }
                });
            },
            error: function(xhr, status, error) {
                console.error('Error loading parent tags:', error);
            }
        });
    }

    // Close modal
    $('.close-modal-edit').on('click', function() {
        $('#add-edit-tag-modal').removeClass('show');
    });

    // Function to load tags from the server and display them hierarchically
function loadTags() {
    $.ajax({
        url: `/api/tags?project_name=${encodeURIComponent(projectName)}`,
        type: 'GET',
        success: function(tags) {
            window.allTagsCache = tags || [];
            // Keep active visibility filters only for tags that still exist
            try {
                const available = new Set((tags || []).map(t => String(t.id)));
                visibleTags = new Set([...visibleTags].filter(id => available.has(String(id))));
            } catch (e) {}
            const q = ($('#new-tag-name').val() || '').trim().toLowerCase();
            renderTags(q);
            // After tags are reloaded, purge any highlights for deleted tags and refresh visuals
            try { purgeRemovedHighlightsAndRefresh(); } catch (e) {}
            // Re-apply filters after (re)rendering the list
            try { updateAnnotationVisibility(); } catch (e) {}
        },
        error: function(xhr, status, error) {
            console.error('Error loading tags:', error);
        }
    });
}

function renderTags(query) {
    const tagList = $('#project-tags-list');
    tagList.empty();
    const tags = Array.isArray(window.allTagsCache) ? window.allTagsCache.slice() : [];
    const tagsById = {};
    tags.forEach(tag => { tagsById[tag.id] = Object.assign({}, tag, { children: [] }); });

    const roots = [];
    tags.forEach(tag => {
        const t = tagsById[tag.id];
        if (tag.parent_tag_id && tagsById[tag.parent_tag_id]) {
            tagsById[tag.parent_tag_id].children.push(t);
        } else {
            roots.push(t);
        }
    });

    function filterTree(nodes, q) {
        if (!q) return nodes;
        const out = [];
        nodes.forEach(n => {
            const name = String(n.name || '').toLowerCase();
            const children = filterTree(n.children || [], q);
            const matched = name.includes(q);
            if (matched || (children && children.length)) {
                const copy = Object.assign({}, n, { children: children });
                out.push(copy);
            }
        });
        return out;
    }

    const filteredRoots = filterTree(roots, (query || '').toLowerCase());

    function buildTagTree(nodes, parentElement) {
        const ul = $('<ul class="tag-group">');
        nodes.forEach(tag => {
            const isActive = visibleTags.has(String(tag.id));
            const iconCls = isActive ? 'fa-eye' : 'fa-eye-slash';
            const activeCls = isActive ? 'active' : '';
            const li = $(`<li data-tag-id="${tag.id}">`);
            li.html(`
                <div class="tag-content">
                    <input type="checkbox" class="tag-checkbox modification-checkbox" data-tag-id="${tag.id}" style="display: none;">
                    <span class="tag-color-indicator" style="background-color: ${tag.color};"></span>
                    <span>${tag.name}</span>
                    <div class="tag-actions">
                        <button class="edit-tag-btn" data-id="${tag.id}" data-name="${tag.name}" data-description="${tag.description || ''}" data-color="${tag.color}"><i class="fas fa-edit"></i></button>
                        <button class="tag-visibility-toggle ${activeCls}" data-tag-id="${tag.id}" title="${isActive ? 'Filtering by this tag' : 'Show only this tag'}"><i class="fas ${iconCls}"></i></button>
                        <button class="delete-tag-btn" data-id="${tag.id}"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `);
            const nestedUl = $('<ul class="tag-group"></ul>');
            if (tag.children && tag.children.length) {
                buildTagTree(tag.children, nestedUl);
            }
            li.append(nestedUl);
            ul.append(li);
        });
        parentElement.append(ul);
    }

    buildTagTree(filteredRoots, tagList);

    // Preserve active state for visibility toggles based on current filters
    $('.tag-visibility-toggle').each(function() {
        const tid = String($(this).data('tag-id'));
        const isActive = visibleTags.has(tid);
        $(this).toggleClass('active', isActive);
        const iconEl = $(this).find('i');
        if (iconEl && iconEl.length) iconEl.attr('class', `fas ${isActive ? 'fa-eye' : 'fa-eye-slash'}`);
    }).on('click', toggleTagVisibility);
    // Ensure explore-mode toggle reflects current state (icons/colors)
    updateVisibilityToggleUI();

    // Initialize SortableJS on every group
    const tagGroups = document.querySelectorAll('.tag-group');
    tagGroups.forEach(group => {
        new Sortable(group, {
            group: 'tags',
            animation: 150,
            onEnd: function (evt) {
                const tagId = $(evt.item).data('tag-id');
                const newParentTagId = $(evt.to).closest('li').data('tag-id') || null;
                $.ajax({
                    url: `/api/tags/${tagId}`,
                    type: 'PUT',
                    contentType: 'application/json',
                    data: JSON.stringify({ project_name: projectName, parent_tag_id: newParentTagId }),
                    success: function(response) {
                        console.log('Tag hierarchy updated successfully:', response);
                        loadTags();
                    },
                    error: function(xhr, status, error) {
                        console.error('Error updating tag hierarchy:', error);
                        Swal.fire('Error', 'Error updating tag hierarchy. Please try again.', 'error');
                    }
                });
            }
        });
    });
}



// Remove stale manual highlights (highlightsData) whose tags were deleted
function purgeRemovedHighlightsAndRefresh() {
    try {
        const tags = Array.isArray(window.allTagsCache) ? window.allTagsCache : [];
        const valid = new Set(tags.map(t => String(t.name || '')));
        if (Array.isArray(window.highlightsData)) {
            window.highlightsData = window.highlightsData.filter(h => valid.has(String(h.name || '')));
        }
        // Re-apply manual highlights and annotation overlays
        if (typeof applyVisualTags === 'function') applyVisualTags();
        if (typeof loadAndDisplayAnnotations === 'function') loadAndDisplayAnnotations();
    } catch (e) {
        // No-op
    }
}

// Handle delete tag button click
$('#project-tags-list').on('click', '.delete-tag-btn', function() {
    const tagId = $(this).data('id');
    Swal.fire({
        title: 'Delete this tag?',
        text: 'This will remove the tag from the project.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel'
    }).then((result) => {
        if (result.isConfirmed) {
            $.ajax({
                url: `/api/tags/${tagId}?project_name=${encodeURIComponent(projectName)}`,
                type: 'DELETE',
                success: function(response) {
                    console.log('Tag deleted successfully:', response);
                    loadTags();
                    const currentPairId = selectedElementPairId || (textPairs.length > 0 ? textPairs[0].id : null);
                    if (currentPairId) {
                        showElementsByPairId(currentPairId, wrongData, correctData, diffData);
                    }
                    Swal.fire('Deleted', 'The tag has been deleted.', 'success');
                },
                error: function(xhr, status, error) {
                    console.error('Error deleting tag:', error);
                    Swal.fire('Error', 'Error deleting tag. Please try again.', 'error');
                }
            });
        }
    });
});

    // Handle "Select All" checkbox change
    $('#select-all-tags-checkbox').on('change', function() {
        const isChecked = $(this).prop('checked');
        $('#project-tags-list .tag-checkbox').prop('checked', isChecked).trigger('change');
    });

    // Handle individual tag checkbox change
    $('#project-tags-list').on('change', '.tag-checkbox', function() {
        const anyChecked = $('#project-tags-list .tag-checkbox:checked').length > 0;
        $('#delete-selected-tags-btn').prop('disabled', !anyChecked);

        const allChecked = $('#project-tags-list .tag-checkbox').length === $('#project-tags-list .tag-checkbox:checked').length;
        $('#select-all-tags-checkbox').prop('checked', allChecked);
    });

    // Handle "Delete Selected" button click
    $('#delete-selected-tags-btn').on('click', function() {
        const selectedTagIds = $('#project-tags-list .tag-checkbox:checked').map(function() {
            return $(this).data('tag-id');
        }).get();

        if (selectedTagIds.length === 0) {
            Swal.fire('No tags selected', 'Please select tags to delete.', 'info');
            return;
        }

        Swal.fire({
            title: `Delete ${selectedTagIds.length} tags?`,
            text: 'This action cannot be undone.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Delete',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                $.ajax({
                    url: '/api/tags/batch_delete',
                    type: 'DELETE',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        project_name: projectName,
                        tag_ids: selectedTagIds
                    }),
                    success: function(response) {
                        console.log('Tags deleted successfully:', response);
                        loadTags();
                        loadAndDisplayAnnotations();
                        Swal.fire('Deleted', 'The selected tags have been deleted.', 'success');
                    },
                    error: function(xhr, status, error) {
                        console.error('Error deleting tags:', error);
                        Swal.fire('Error', 'Error deleting tags. Please try again.', 'error');
                    }
                });
            }
        });
    });

    // Load tags on page load
    loadTags();

    // Live filter for tags/codes
    $('#new-tag-name').on('input', function() {
        const q = ($(this).val() || '').trim().toLowerCase();
        if (window.allTagsCache) {
            renderTags(q);
        }
    });

    // Toggle tag modification view
    $('#modify-tags-btn').on('click', function() {
        $('#tag-modification-container').toggle();
        if ($('#tag-modification-container').is(':visible')) {
            $('.modification-checkbox').show();
            // Indicate active state on pen
            $(this).addClass('active');
        } else {
            $('.modification-checkbox').hide();
            $(this).removeClass('active');
        }
    });

    // Explore mode toggle: show/hide eye visibility controls next to the pen
    $('#explore-tags-btn').on('click', function() {
        $('.tag-library').toggleClass('explore-active');
        updateVisibilityToggleUI();
    });

    // Notes Report is rendered in Tag Report page; no sidebar fetch here

    // Context menu for tagging
    const contextMenu = $('#tag-context-menu');
    const modal = $('#tagging-modal');
    const removeTagModal = $('#remove-tag-modal');
    let selectionInfo = {};

    $('#left-panel').on('contextmenu', '.text-card', function(e) {
        e.preventDefault();

        const selection = window.getSelection();
        if (selection.rangeCount === 0) return;

        const range = selection.getRangeAt(0);
        const textCard = e.currentTarget;

        // Ensure the selection is within the clicked text-card
        if (!textCard.contains(range.commonAncestorContainer)) {
            return;
        }

        const preCaretRange = document.createRange();
        preCaretRange.selectNodeContents(textCard);
        preCaretRange.setEnd(range.startContainer, range.startOffset);
        const startOffset = preCaretRange.toString().length;
        const endOffset = startOffset + range.toString().length;

        const idParts = $(textCard).attr('id').split('_');
        const rawType = idParts[1];
        const canonicalType = (function(t){
            if (t === 'wrong') return 'error_text';
            if (t === 'correct') return 'corrected_text';
            if (t === 'diff') return 'diff_text';
            return t;
        })(rawType);
        let clickedAnnotationId = null;
        try {
            const targetEl = e.target instanceof Element ? e.target : null;
            const annEl = targetEl ? targetEl.closest('.annotation-span') : null;
            if (annEl && annEl.dataset && annEl.dataset.annotationId) {
                clickedAnnotationId = parseInt(annEl.dataset.annotationId, 10);
            }
        } catch (_) {}

        selectionInfo = {
            element: textCard,
            dataType: rawType,
            canonicalType: canonicalType,
            pairId: idParts[2],
            text: selection.toString(),
            range: range,
            startOffset: startOffset,
            endOffset: endOffset,
            isCollapsed: selection.isCollapsed,
            annotationId: clickedAnnotationId
        };

        // Always show both options
        $('#add-tag-option').show();
        $('#remove-tag-option').show();

        contextMenu.css({ top: e.pageY, left: e.pageX }).show();
    });

    $(document).on('click', function() {
        contextMenu.hide();
    });

    $('#add-tag-option').on('click', function() {
        if (selectionInfo.isCollapsed || !selectionInfo.text) {
            Swal.fire('Select text', 'Please select some text to tag.', 'info');
            return;
        }
        loadTagsIntoModal();
        $('#tagging-modal').addClass('show');
    });

    $('#remove-tag-option').on('click', function() {
        handleRemoveTag();
    });

    $('.close-modal').on('click', function() {
        $('#tagging-modal').removeClass('show');
    });

    $('.close-remove-tag-modal').on('click', function() {
        $('#remove-tag-modal').removeClass('show');
    });

    function handleRemoveTag() {
        var projectName = getUrlParameter('project_name');
        if (selectionInfo && selectionInfo.annotationId) {
            removeAnnotation(selectionInfo.annotationId);
            return;
        }
        $.ajax({
            url: `/api/annotations?project_name=${encodeURIComponent(projectName)}`,
            type: 'GET',
            success: function(response) {
                const allAnnotations = response.annotations;
                const clickedOffset = selectionInfo.startOffset;

                const typesToMatch = new Set([String(selectionInfo.dataType || ''), String(selectionInfo.canonicalType || '')]);
                const overlappingAnnotations = allAnnotations.filter(ann =>
                    ann.pair_id == selectionInfo.pairId &&
                    typesToMatch.has(String(ann.data_type || '')) &&
                    clickedOffset >= ann.start_offset && clickedOffset < ann.end_offset
                );

                if (overlappingAnnotations.length === 0) {
                    Swal.fire('No tag', 'No tag found at this position.', 'info');
                } else if (overlappingAnnotations.length === 1) {
                    removeAnnotation(overlappingAnnotations[0].id);
                } else {
                    const removeTagList = $('#remove-tag-list');
                    removeTagList.empty();
                    overlappingAnnotations.sort((a, b) => a.start_offset - b.start_offset || b.end_offset - a.end_offset);
                    overlappingAnnotations.forEach(ann => {
                        const li = $(`<li>
                            <div class="tag-info">
                                <span class="tag-color-indicator" style="background-color: ${ann.tag_color};"></span>
                                <span class="tag-name">${ann.tag_name}</span>
                            </div>
                            <button class="delete-annotation-btn" data-id="${ann.id}"><i class="fas fa-trash"></i></button>
                        </li>`);
                        removeTagList.append(li);
                    });
                    $('#remove-tag-modal').addClass('show');
                }
            },
            error: function(xhr, status, error) {
                console.error("Error fetching annotations for removal:", error);
                Swal.fire('Error', 'Could not fetch tags for removal. Please try again.', 'error');
            }
        });
    }

    $('#remove-tag-list').on('click', '.delete-annotation-btn', function() {
        const annotationId = $(this).data('id');
        removeAnnotation(annotationId);
        $('#remove-tag-modal').removeClass('show');
    });

    function removeAnnotation(annotationId) {
        Swal.fire({
            title: 'Remove this tag?',
            text: 'This will remove the selected annotation.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Remove',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (!result.isConfirmed) return;

            $.ajax({
                url: `/api/annotations/${annotationId}?project_name=${encodeURIComponent(projectName)}`,
                type: 'DELETE',
                success: function(response) {
                    console.log('Annotation removed successfully:', response);
                    const currentPairId = selectionInfo.pairId || (textPairs.length > 0 ? textPairs[0].id : null);
                    if (currentPairId) {
                        showElementsByPairId(parseInt(currentPairId, 10), wrongData, correctData, diffData);
                    }
                    Swal.fire('Removed', 'The annotation has been removed.', 'success');
                },
                error: function(xhr, status, error) {
                    console.error('Error removing annotation:', error);
                    Swal.fire('Error', 'Error removing annotation. Please try again.', 'error');
                }
            });
        });
    }

    function loadTagsIntoModal() {
        $.ajax({
            url: `/api/tags?project_name=${encodeURIComponent(projectName)}`,
            type: 'GET',
            success: function(tags) {
                const modalTagList = $('#modal-tag-list');
                modalTagList.empty();
                const tagsById = {};
                tags.forEach(tag => {
                    tagsById[tag.id] = tag;
                    tag.children = [];
                });

                const rootTags = [];
                tags.forEach(tag => {
                    if (tag.parent_tag_id) {
                        tagsById[tag.parent_tag_id].children.push(tag);
                    } else {
                        rootTags.push(tag);
                    }
                });

                function buildTagTree(tags, parentElement, level) {
                    const ul = $('<ul>');
                    tags.forEach(tag => {
                        const li = $('<li>');
                        li.html(`<div style="margin-left: ${level * 20}px;"><input type="radio" name="tag" value="${tag.id}"> ${tag.name}</div>`);
                        if (tag.children.length > 0) {
                            buildTagTree(tag.children, li, level + 1);
                        }
                        ul.append(li);
                    });
                    parentElement.append(ul);
                }

                buildTagTree(rootTags, modalTagList, 0);
            },
            error: function(xhr, status, error) {
                console.error('Error loading tags for modal:', error);
            }
        });
    }

    $('#save-annotation-btn').on('click', function() {
    console.log("'Save Annotation' button clicked.");

    const selectedTagId = $('input[name="tag"]:checked').val();
    if (!selectedTagId) {
        Swal.fire('Select a tag', 'Please select a tag.', 'info');
        return;
    }
    console.log("Selected Tag ID:", selectedTagId);

    const data = {
        project_name: projectName,
        pair_id: selectionInfo.pairId,
        data_type: selectionInfo.dataType,
        start_offset: selectionInfo.startOffset,
        end_offset: selectionInfo.endOffset,
        tag_id: selectedTagId,
        text: selectionInfo.text
    };

    console.log("Preparing to send annotation data:", data);

    $.ajax({
        url: '/api/annotate_text',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            console.log('Annotation saved successfully via AJAX:', response);
            $('#tagging-modal').removeClass('show');
            // Re-render the view to show the new annotation
            showElementsByPairId(parseInt(selectionInfo.pairId, 10), wrongData, correctData, diffData);
        },
        error: function(xhr, status, error) {
            console.error('Error saving annotation:', error);
            Swal.fire('Error', 'Error saving annotation. Please try again.', 'error');
        }
    });
});


});

function addAiResponseToNotes(messageId) {
    const button = $(`[data-message-id="${messageId}"]`);
    const originalIcon = button.find('i').attr('class');
    const originalText = button.find('span').text();

    // Start loading animation
    button.find('i').removeClass().addClass('fas fa-spinner fa-spin');
    button.find('span').text('Adding...');
    button.prop('disabled', true);

    // Extract only the AI message content as rendered HTML, excluding any buttons or wrappers
    const contentContainer = $(`#${messageId} .ai-content`);
    const messageContent = contentContainer.length ? contentContainer.html().trim() : $(`#${messageId}`).html().replace(/<button.*>.*<\/button>/gs, '').trim();
    const currentPairId = selectedElementPairId || (textPairs.length > 0 ? textPairs[0].id : null);

    if (!currentPairId) {
        Swal.fire('Unavailable', 'Cannot save note, no text pair selected.', 'warning');
        // Revert button state
        button.find('i').removeClass().addClass(originalIcon);
        button.find('span').text(originalText);
        button.prop('disabled', false);
        return;
    }

    const data = {
        project_name: projectName,
        pair_id: currentPairId,
        title: 'AI Response',
        content: messageContent
    };

    $.ajax({
        url: '/api/notes',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function() {
            loadNotes(currentPairId);
            // Final "Added!" state
            button.find('i').removeClass().addClass('fas fa-check');
            button.find('span').text('Added!');
            button.addClass('added');
        },
        error: function(xhr, status, error) {
            console.error('Error saving note:', error);
            Swal.fire('Error', 'Error saving note. Please try again.', 'error');
            // Revert button state on error
            button.find('i').removeClass().addClass(originalIcon);
            button.find('span').text(originalText);
            button.prop('disabled', false);
        }
    });
}

$(document).ready(function () {
    // ... (existing ready function code)

    $('#chat-history').on('click', '.add-to-notes-btn', function() {
        const messageId = $(this).data('message-id');
        addAiResponseToNotes(messageId);
    });
});

// --- Annotations overlay rendering ---
function loadAndDisplayAnnotations() {
    var projectName = getUrlParameter('project_name');
    // Determine current pair ID from DOM if available
    let currentPairId = null;
    const wrongEl = document.querySelector('[id^="result_wrong_"]');
    const correctEl = document.querySelector('[id^="result_correct_"]');
    if (wrongEl) {
        const m = wrongEl.id.match(/result_wrong_(\d+)/);
        if (m) currentPairId = parseInt(m[1], 10);
    }
    if (!currentPairId && correctEl) {
        const m = correctEl.id.match(/result_correct_(\d+)/);
        if (m) currentPairId = parseInt(m[1], 10);
    }
    if (!currentPairId && typeof textPairs !== 'undefined' && textPairs.length) {
        currentPairId = textPairs[0].id;
    }
    if (!currentPairId) return;

    $.ajax({
        url: `/api/annotations?project_name=${encodeURIComponent(projectName)}&limit=100000&offset=0&sort_by=start_offset&tag_name=&data_type=&search_query=`,
        type: 'GET',
        success: function(res) {
            const anns = (res && res.annotations) ? res.annotations : [];
            const byType = { error_text: [], corrected_text: [], diff_text: [] };
            anns.forEach(a => {
                if (a.pair_id === currentPairId || String(a.pair_id) === String(currentPairId)) {
                    let t = (a.data_type || '').toString().toLowerCase();
                    if (t === 'wrong') t = 'error_text';
                    if (t === 'correct') t = 'corrected_text';
                    if (t === 'diff') t = 'diff_text';
                    if (t === 'error_text' || t === 'corrected_text' || t === 'diff_text') {
                        byType[t].push(a);
                    }
                }
            });
            // Sort by start then end desc to avoid nested wrap conflicts
            Object.keys(byType).forEach(k => byType[k].sort((a,b)=> a.start_offset - b.start_offset || b.end_offset - a.end_offset));

            const containers = {
                error_text: document.getElementById(`result_wrong_${currentPairId}`),
                corrected_text: document.getElementById(`result_correct_${currentPairId}`),
                diff_text: document.getElementById(`result_diff_${currentPairId}`)
            };
            for (const dtype of ['error_text','corrected_text','diff_text']) {
                const root = containers[dtype];
                if (!root) continue;
                // Remove existing overlays
                unwrapAnnotationSpans(root);
                // Apply new overlays using Range-based wrapping to preserve true nesting
                const annsForType = byType[dtype].slice().sort((a,b)=> b.start_offset - a.start_offset || a.end_offset - b.end_offset);
                annsForType.forEach(a => {
                    try { wrapAnnotationRange(root, a); } catch (e) { /* ignore one-off failures */ }
                });
            }
            // Re-apply any active tag visibility filters after rendering
            try { updateAnnotationVisibility(); } catch (e) {}
        },
        error: function(err) {
            console.error('Failed to load annotations:', err);
        }
    });
}

function unwrapAnnotationSpans(root) {
    try {
        const spans = root.querySelectorAll('span.annotation-span');
        spans.forEach(s => {
            const parent = s.parentNode;
            while (s.firstChild) parent.insertBefore(s.firstChild, s);
            parent.removeChild(s);
        });
    } catch (e) {}
}

function wrapAnnotationRange(root, annotation) {
    // Find start and end text nodes by absolute offsets within root's textContent
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    let charIndex = 0;
    let startNode=null, startOffset=0, endNode=null, endOffset=0;
    for (const node of textNodes) {
        const nodeLen = node.textContent.length;
        const nodeStart = charIndex;
        const nodeEnd = charIndex + nodeLen;
        if (!startNode && nodeEnd > annotation.start_offset) {
            startNode = node;
            startOffset = Math.max(0, annotation.start_offset - nodeStart);
        }
        if (!endNode && nodeEnd >= annotation.end_offset) {
            endNode = node;
            endOffset = Math.max(0, annotation.end_offset - nodeStart);
            break;
        }
        charIndex = nodeEnd;
    }
    if (!startNode || !endNode) return;
    const range = document.createRange();
    range.setStart(startNode, startOffset);
    range.setEnd(endNode, endOffset);

    // Determine underline offset stacking based on existing spans within this fragment
    const frag = range.cloneContents();
    const existing = frag.querySelectorAll('.annotation-span');
    let maxOffset = 0;
    existing.forEach(s => {
        const off = parseInt((s.style.textUnderlineOffset || '0').toString().replace('px',''), 10);
        if (!isNaN(off) && off > maxOffset) maxOffset = off;
    });
    const newOffset = maxOffset + 3;

    const span = document.createElement('span');
    span.className = 'annotation-span';
    span.setAttribute('data-annotation-id', annotation.id);
    if (annotation.tag_id != null) span.setAttribute('data-tag-id', String(annotation.tag_id));
    const color = annotation.tag_color || '#ffd54f';
    span.style.textDecoration = 'underline';
    span.style.textDecorationColor = color;
    span.style.textDecorationStyle = annotation.parent_tag_id ? 'dashed' : 'solid';
    span.style.textDecorationThickness = '2px';
    span.style.textUnderlineOffset = `${newOffset}px`;
    span.title = annotation.tag_name || '';
    try {
        range.surroundContents(span);
    } catch (e) {
        if (e instanceof DOMException && e.name === 'InvalidStateError') {
            const extracted = range.extractContents();
            span.appendChild(extracted);
            range.insertNode(span);
        } else {
            throw e;
        }
    }
}

function hexToRgba(hex, alpha) {
    try {
        hex = String(hex).replace('#','');
        if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
        const num = parseInt(hex, 16);
        const r = (num >> 16) & 255;
        const g = (num >> 8) & 255;
        const b = num & 255;
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    } catch (e) { return 'rgba(255, 213, 79, 0.35)'; }
}

function wrapTextRanges(root, ranges) {
    if (!ranges || !ranges.length) return;
    // Build a TreeWalker over text nodes
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    let node; let offset = 0;
    let idx = 0;
    // Defensive copy sorted by start
    ranges = ranges.slice().sort((a,b)=> a.start - b.start || b.end - a.end);
    while ((node = walker.nextNode()) && idx < ranges.length) {
        const textLen = node.nodeValue.length;
        const nodeStart = offset;
        const nodeEnd = offset + textLen;
        // Process any ranges that intersect this node
        while (idx < ranges.length) {
            const r = ranges[idx];
            if (r.end <= nodeStart) { idx++; continue; }
            if (r.start >= nodeEnd) break; // next text node
            // intersecting
            const innerStart = Math.max(0, r.start - nodeStart);
            const innerEnd = Math.min(textLen, r.end - nodeStart);
            // Split text node if needed
            const before = node.nodeValue.slice(0, innerStart);
            const mid = node.nodeValue.slice(innerStart, innerEnd);
            const after = node.nodeValue.slice(innerEnd);
            // If nothing to wrap, avoid spinning; advance appropriately
            if (!mid) {
                if (r.end <= nodeEnd) { idx++; continue; }
                // Range continues beyond this node; move to next text node
                break;
            }
            const span = document.createElement('span');
            span.className = 'annotation-span';
            const color = r.color || '#ffd54f';
            // Render as underline with offset so nested annotations "stack"
            span.style.textDecoration = 'underline';
            span.style.textDecorationColor = color;
            span.style.textDecorationStyle = (r.dashed ? 'dashed' : 'solid');
            span.style.textDecorationThickness = '2px';
            // Compute nesting based on current ancestors
            let nesting = 0; let parentEl = node.parentNode;
            while (parentEl && parentEl !== root) {
                if (parentEl.classList && parentEl.classList.contains('annotation-span')) nesting++;
                parentEl = parentEl.parentNode;
            }
            span.style.textUnderlineOffset = `${(nesting + 1) * 3}px`;
            span.title = r.tag || '';
            if (r.tag_id != null) {
                try { span.setAttribute('data-tag-id', String(r.tag_id)); } catch (_) {}
            }
            span.textContent = mid;
            const parent = node.parentNode;
            const frag = document.createDocumentFragment();
            if (before) frag.appendChild(document.createTextNode(before));
            frag.appendChild(span);
            node.nodeValue = after; // replace current node with tail, insert frag before
            parent.insertBefore(frag, node);
            // Update for potential additional overlaps within the same original node
            // Adjust offset for remaining part 'after' remains in 'node'
            // Do not advance walker; continue to check this node again as nodeStart changes not needed
            // Move to next range if fully consumed within this node
            if (r.end <= nodeEnd) {
                idx++;
            } else {
                // Range continues into next text node; handle remainder there
                break;
            }
        }
        offset = nodeEnd;
    }
}

function computeDisplayRange(rootText, ann) {
    try {
        const startHint = Number(ann.start_offset) || 0;
        const needle = (ann.text || '').toString();
        if (!needle) return null;
        const rootLower = rootText.toLowerCase();
        const needleLower = needle.toLowerCase();
        // Gather all occurrences
        const indices = [];
        let idx = rootLower.indexOf(needleLower, 0);
        while (idx !== -1) {
            indices.push(idx);
            idx = rootLower.indexOf(needleLower, idx + 1);
        }
        if (!indices.length) {
            // Fallback: try trimming spaces in needle
            const n2 = needleLower.trim().replace(/\s+/g, ' ');
            const r2 = rootLower.replace(/\s+/g, ' ');
            let j = r2.indexOf(n2);
            if (j !== -1) {
                return { start: j, end: j + n2.length };
            }
            // As last resort, use DB offsets
            const end = Number(ann.end_offset) || startHint + Math.max(needle.length, 1);
            return { start: startHint, end: end };
        }
        // Choose the occurrence whose start is closest to the hint
        let best = indices[0];
        let bestDist = Math.abs(indices[0] - startHint);
        for (let i = 1; i < indices.length; i++) {
            const d = Math.abs(indices[i] - startHint);
            if (d < bestDist) { best = indices[i]; bestDist = d; }
        }
        return { start: best, end: best + needleLower.length };
    } catch (e) {
        return null;
    }
}
