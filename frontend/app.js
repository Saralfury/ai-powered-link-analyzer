const urlInput = document.getElementById('urlInput');
const analyseBtn = document.getElementById('analyseBtn');
const loader = document.getElementById('loader');
const errorBox = document.getElementById('errorBox');
const successBox = document.getElementById('successBox');
const result = document.getElementById('result');

analyseBtn.addEventListener('click', async () => {
  const url = urlInput.value.trim();
  if (!url) return alert('Please enter a URL');

  result.style.display = 'none';
  errorBox.style.display = 'none';
  successBox.style.display = 'none';
  loader.style.display = 'block';
  analyseBtn.disabled = true;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);

  try {
    const resp = await fetch('/link-analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
      signal: controller.signal,
    });
    const data = await resp.json();

    if (!resp.ok || !data.success) {
      errorBox.textContent = (data.error && data.error.message) || data.detail || 'Analysis failed.';
      errorBox.style.display = 'block';
      return;
    }

    successBox.textContent = 'Analysis complete.';
    successBox.style.display = 'block';
    render(data);
  } catch (err) {
    if (err.name === 'AbortError') {
      errorBox.textContent = 'Request timed out. Please try again.';
    } else {
      errorBox.textContent = 'Network error: ' + err.message;
    }
    errorBox.style.display = 'block';
  } finally {
    clearTimeout(timeoutId);
    loader.style.display = 'none';
    analyseBtn.disabled = false;
  }
});

function render(data) {
  result.style.display = 'block';
  document.getElementById('resWebsite').textContent = data.website;
  document.getElementById('resBrand').textContent = data.brand.name;
  document.getElementById('resBrandSummary').textContent = data.brand.summary;

  const m = data.meta || {};
  const metaHtml = `
    <strong>Model:</strong> ${escapeHtml(m.model || '—')} •
    <strong>Provider:</strong> ${escapeHtml(m.provider || '—')} •
    <strong>Pages analysed:</strong> ${m.pages_analyzed || 1} •
    <strong>Cache hit:</strong> ${m.cached ? 'Yes' : 'No'} •
    <strong>Latency:</strong> ${m.latency_ms !== undefined ? m.latency_ms + ' ms' : '—'} •
    <strong>Tokens:</strong> ${m.input_tokens !== undefined ? m.input_tokens : '—'} in / ${m.output_tokens !== undefined ? m.output_tokens : '—'} out
  `;
  document.getElementById('resMeta').innerHTML = metaHtml;

  const a = data.analysis;

  // Competitor
  document.getElementById('compOverview').textContent = a.competitor_analysis.brand_overview;
  document.getElementById('compStrengths').innerHTML = (a.competitor_analysis.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');
  document.getElementById('compOpportunities').innerHTML = (a.competitor_analysis.opportunities || []).map(o => `<li>${escapeHtml(o)}</li>`).join('');
  const compBody = document.querySelector('#compTable tbody');
  compBody.innerHTML = (a.competitor_analysis.competitors || []).map(c => `
    <tr>
      <td><strong>${escapeHtml(c.name)}</strong> ${c.ai_suggested ? '<span class="tag inferred">AI-suggested</span>' : ''}</td>
      <td>${escapeHtml(c.overview || '-')}</td>
      <td>${(c.strengths || []).map(s => `<span class="tag">${escapeHtml(s)}</span>`).join('')}</td>
      <td>${(c.weaknesses_or_gaps || []).map(w => `<span class="tag">${escapeHtml(w)}</span>`).join('')}</td>
      <td><span class="tag">${escapeHtml(c.source || 'llm')}</span></td>
    </tr>
  `).join('');
  const compCompBody = document.querySelector('#compComparison tbody');
  compCompBody.innerHTML = (a.competitor_analysis.comparison_table || []).map(r => `
    <tr>
      <td><strong>${escapeHtml(r.field)}</strong></td>
      <td>${escapeHtml(r.your_brand || '-')}</td>
      <td>${escapeHtml(r.competitor || '-')}</td>
    </tr>
  `).join('');

  // Search queries
  const qBody = document.getElementById('queriesBody');
  qBody.innerHTML = (a.target_search_queries || []).map(q => `
    <tr>
      <td><strong>${escapeHtml(q.query)}</strong></td>
      <td>${(q.platforms || []).map(p => `<span class="tag">${escapeHtml(p)}</span>`).join('')}</td>
      <td>${escapeHtml(q.intent || '-')}</td>
      <td>${escapeHtml(q.business_relevance || '-')}</td>
      <td>${escapeHtml(q.target_audience || '-')}</td>
    </tr>
  `).join('');

  // SEO
  document.getElementById('seoPrimary').textContent = a.seo_improvements.primary_keyword;
  document.getElementById('seoTitle').textContent = a.seo_improvements.recommended_title;
  document.getElementById('seoMeta').textContent = a.seo_improvements.meta_description;
  document.getElementById('seoSecondary').innerHTML = (a.seo_improvements.secondary_keywords || []).map(k => `<li>${escapeHtml(k)}</li>`).join('');
  document.getElementById('seoLongtail').innerHTML = (a.seo_improvements.long_tail_keywords || []).map(k => `<li>${escapeHtml(k)}</li>`).join('');
  document.getElementById('seoContent').innerHTML = (a.seo_improvements.supporting_content || []).map(c => `<li>${escapeHtml(c)}</li>`).join('');

  // Services
  const sBody = document.getElementById('servicesBody');
  sBody.innerHTML = (a.top_services || []).map(s => `
    <tr>
      <td><strong>${escapeHtml(s.service_name)}</strong> ${s.inferred ? '<span class="tag inferred">Inferred</span>' : ''}</td>
      <td>${escapeHtml(s.description || '-')}</td>
      <td>${escapeHtml(s.target_industry || '-')}</td>
      <td>${escapeHtml(s.target_customer || '-')}</td>
      <td>${escapeHtml(s.main_benefit || '-')}</td>
      <td><span class="tag">${escapeHtml(s.source || 'llm')}</span></td>
    </tr>
  `).join('');

  // Audience
  const ta = a.target_audience;
  document.getElementById('audPrimary').innerHTML = (ta.primary_audience || []).map(x => `<li>${escapeHtml(x)}</li>`).join('');
  document.getElementById('audSecondary').innerHTML = (ta.secondary_audience || []).map(x => `<li>${escapeHtml(x)}</li>`).join('');
  document.getElementById('audIndustries').innerHTML = (ta.industry_segments || []).map(x => `<li>${escapeHtml(x)}</li>`).join('');
  document.getElementById('audBusiness').innerHTML = (ta.business_types || []).map(x => `<li>${escapeHtml(x)}</li>`).join('');
  document.getElementById('audNeeds').innerHTML = (ta.customer_needs || []).map(x => `<li>${escapeHtml(x)}</li>`).join('');
  document.getElementById('audChallenges').innerHTML = (ta.customer_challenges || []).map(x => `<li>${escapeHtml(x)}</li>`).join('');
  document.getElementById('audLocation').textContent = ta.location_focus ? 'Location focus: ' + ta.location_focus : '';

  document.getElementById('resDisclaimer').textContent = data.disclaimer || '';
  document.getElementById('rawJson').textContent = JSON.stringify(data, null, 2);
}

function escapeHtml(text) {
  if (text == null) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}
