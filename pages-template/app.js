// ISP Chart Viewer — app.js
// Interactive charts from AEMO ISP workbook JSON data

// ---------------------------------------------------------------------------
// Chart.js defaults
// ---------------------------------------------------------------------------
Chart.defaults.font.family = '"DM Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
Chart.defaults.scales.category = Chart.defaults.scales.category || {};

// ---------------------------------------------------------------------------
// Constants (ported from build.py)
// ---------------------------------------------------------------------------

let RELEASES = []; // populated from releases.json at init

const DETAIL_TECHS = {
  energy: [
    { id: 'coal_black',          label: 'Black coal',          color: '#251C00' },
    { id: 'coal_brown',          label: 'Brown coal',          color: '#675B42' },
    { id: 'gas_ccgt',            label: 'Mid-merit gas',       color: '#ED9C2C' },
    { id: 'gas_ocgt',            label: 'Flexible gas',        color: '#F0AC4A' },
    { id: 'gas_ccgt_ccs',        label: 'Gas with CCS',        color: '#F1AB4B' },
    { id: 'hydro',               label: 'Hydro',               color: '#ACE9FE' },
    { id: 'wind',                label: 'Wind',                color: '#246D36' },
    { id: 'wind_offshore',       label: 'Offshore wind',       color: '#53AD69' },
    { id: 'solar_utility',       label: 'Utility-scale solar', color: '#FECE00' },
    { id: 'solar_rooftop',       label: 'Rooftop solar',       color: '#FFEB5C' },
    { id: 'bioenergy',           label: 'Bioenergy',           color: '#069FAF' },
    { id: 'battery_discharging', label: 'Battery',             color: '#3145CE' },
  ],
  capacity: [
    { id: 'coal_black',    label: 'Black coal',          color: '#251C00' },
    { id: 'coal_brown',    label: 'Brown coal',          color: '#675B42' },
    { id: 'gas_ccgt',      label: 'Mid-merit gas',       color: '#ED9C2C' },
    { id: 'gas_ocgt',      label: 'Flexible gas',        color: '#F0AC4A' },
    { id: 'gas_ccgt_ccs',  label: 'Gas with CCS',        color: '#F1AB4B' },
    { id: 'hydro',         label: 'Hydro',               color: '#ACE9FE' },
    { id: 'wind',          label: 'Wind',                color: '#246D36' },
    { id: 'wind_offshore', label: 'Offshore wind',       color: '#53AD69' },
    { id: 'solar_utility', label: 'Utility-scale solar', color: '#FECE00' },
    { id: 'solar_rooftop', label: 'Rooftop solar',       color: '#FFEB5C' },
    { id: 'bioenergy',     label: 'Bioenergy',           color: '#069FAF' },
    { id: 'battery',       label: 'Battery',             color: '#3145CE' },
  ],
};

const COMPARE_GROUPS = {
  energy: {
    Coal:    ['coal_black', 'coal_brown'],
    Gas:     ['gas_ccgt', 'gas_ocgt', 'gas_ccgt_ccs', 'gas_hydrogen'],
    Wind:    ['wind', 'wind_offshore'],
    Solar:   ['solar_utility', 'solar_rooftop', 'solar_thermal'],
    Battery: ['battery_discharging', 'battery_distributed_discharging', 'battery_VPP_discharging'],
    Hydro:   ['hydro'],
  },
  capacity: {
    Coal:    ['coal_black', 'coal_brown'],
    Gas:     ['gas_ccgt', 'gas_ocgt', 'gas_ccgt_ccs', 'gas_hydrogen'],
    Wind:    ['wind', 'wind_offshore'],
    Solar:   ['solar_utility', 'solar_rooftop', 'solar_thermal'],
    Battery: ['battery', 'battery_distributed', 'battery_VPP'],
    Hydro:   ['hydro'],
  },
};

const COMPARE_COLORS = {
  Coal: '#251C00', Gas: '#ED9C2C', Wind: '#246D36',
  Solar: '#FECE00', Battery: '#3145CE', Hydro: '#41B6E6',
};

// Dash patterns cycle for comparison mode (newest first = solid)
const DASH_PATTERNS = [[], [8, 4], [2, 4], [1, 3], [4, 2, 1, 2]];

function getCompareDash(releaseId) {
  // Releases are sorted oldest-first; newest gets solid line
  const idx = RELEASES.length - 1 - RELEASES.findIndex(r => r.id === releaseId);
  return DASH_PATTERNS[Math.min(idx, DASH_PATTERNS.length - 1)];
}

const COST_COLORS = {
  generator_capital:                      '#4E79A7',
  fuel:                                   '#F28E2B',
  fixed_operating_and_maintenance:        '#E15759',
  variable_operating_and_maintenance:     '#76B7B2',
  flow_path_augmentation:                 '#59A14F',
  flow_path_capital:                      '#59A14F',
  flow_path_operations_and_maintenance:   '#8CD17D',
  rez_augmentation:                       '#B6992D',
  rez_capital:                            '#B6992D',
  rez_operations_and_maintenance:         '#D4C26A',
  dsp_use:                                '#FF9DA7',
  emissions_cost:                         '#9C755F',
  distribution_capital:                   '#BAB0AC',
  distribution_operations_and_maintenance:'#D4C4BC',
  generator_retirement:                   '#FABFD2',
  system_security:                        '#D37295',
};

const REGION_LABELS = {
  _all: 'NEM', nsw1: 'NSW', qld1: 'QLD', sa1: 'SA', tas1: 'TAS', vic1: 'VIC',
};

const TYPE_CONFIG = {
  energy:    { unit: 'TWh', divisor: 1000 },
  capacity:  { unit: 'GW',  divisor: 1000 },
  emissions: { unit: 'MtCO₂e', divisor: 1000 },
  cost:      { unit: '$B',  divisor: 1_000_000 },
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const cache = new Map();
let charts = [];
let compareMode = false;
const enabledReleases = new Set();

// DOM refs
const selScenario = document.getElementById('sel-scenario');
const selPathway  = document.getElementById('sel-pathway');
const selRegion   = document.getElementById('sel-region');
const releaseBar  = document.getElementById('release-bar');
const chartGrid   = document.getElementById('chart-grid');

// Active release for normal mode
let activeReleaseId = null;
let lastActiveReleaseId = null;

// Tom Select instances (initialised in init())
let tsScenario, tsPathway, tsRegion;

// ---------------------------------------------------------------------------
// Data helpers
// ---------------------------------------------------------------------------

function extractSeries(data, type, region, pathway) {
  const results = new Map();
  for (const entry of data.data) {
    if (entry.type !== type || entry.region !== region || entry.pathway !== pathway) continue;
    const key = type === 'cost' ? entry.category : entry.fuel_tech;
    if (!key) continue;
    const startYear = parseInt(entry.projection.start.slice(0, 4));
    const values = entry.projection.data;
    const years = values.map((_, i) => startYear + i);
    results.set(key, { years, values });
  }
  return results;
}

function extractEmissions(data, region, pathway) {
  for (const entry of data.data) {
    if (entry.type !== 'emissions' || entry.region !== region || entry.pathway !== pathway) continue;
    if (entry.fuel_tech) continue;
    const startYear = parseInt(entry.projection.start.slice(0, 4));
    const values = entry.projection.data;
    const years = values.map((_, i) => startYear + i);
    return { years, values };
  }
  return null;
}

function sumGroup(series, fuelTechs) {
  let years = null, values = null;
  for (const ft of fuelTechs) {
    const s = series.get(ft);
    if (!s) continue;
    if (!years) {
      years = [...s.years];
      values = [...s.values];
    } else {
      for (let i = 0; i < s.years.length; i++) {
        const idx = years.indexOf(s.years[i]);
        if (idx !== -1) values[idx] += s.values[i];
      }
    }
  }
  return years ? { years, values } : null;
}

function getPathways(data) {
  const set = new Set();
  for (const entry of data.data) {
    if (entry.pathway) set.add(entry.pathway);
  }
  return [...set].sort((a, b) => {
    const na = parseInt(a.replace(/\D+/g, '')) || 9999;
    const nb = parseInt(b.replace(/\D+/g, '')) || 9999;
    return na - nb;
  });
}

function formatScenario(s) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function capDropdownHeight() {
  const dd = this.dropdown;
  if (!dd) return;
  const top = dd.getBoundingClientRect().top;
  dd.style.maxHeight = Math.max(150, window.innerHeight - top - 100) + 'px';
  dd.style.overflowY = 'auto';
}

function formatValue(v) {
  if (v == null) return '';
  const abs = Math.abs(v);
  return abs < 100 ? v.toFixed(1) : Math.round(v).toLocaleString();
}

const tooltipCallbacks = {
  label: ctx => `${ctx.dataset.label}: ${formatValue(ctx.parsed.y)}`,
};

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadData(releaseId, scenario) {
  const key = `${releaseId}/${scenario}`;
  if (cache.has(key)) return cache.get(key);
  const url = `${releaseId}/${scenario}.json`;
  try {
    const resp = await fetch(url);
    const data = await resp.json();
    cache.set(key, data);
    return data;
  } catch (e) {
    if (location.protocol === 'file:') {
      throw new Error(
        'Cannot load JSON via file://. Run: python3 serve.py'
      );
    }
    throw e;
  }
}

function pickDefaultPathway(pathways) {
  if (pathways.includes('default')) return 'default';
  if (pathways.includes('CDP1')) return 'CDP1';
  return pathways[0];
}

function showFileError(msg) {
  const grid = document.getElementById('chart-grid');
  let banner = document.getElementById('file-error');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'file-error';
    banner.style.cssText = 'grid-column:1/-1;padding:2rem;text-align:center;background:#fff3cd;border:1px solid #ffc107;border-radius:8px;font-size:1.1rem';
    grid.prepend(banner);
  }
  banner.innerHTML = `<strong>Error:</strong> ${msg.replace(/\n/g, '<br>')}`;
}

function showLoading(show) {
  document.querySelectorAll('.loading-overlay').forEach(el => {
    el.classList.toggle('hidden', !show);
  });
}

// ---------------------------------------------------------------------------
// Chart rendering
// ---------------------------------------------------------------------------

function destroyCharts() {
  charts.forEach(c => c.destroy());
  charts = [];
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function makeStackedChart(canvasId, title, series, techList, divisor, unit) {
  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  const datasets = [];
  let allYears = null;

  for (const tech of techList) {
    const s = series.get(tech.id);
    if (!s) continue;
    if (!allYears) allYears = s.years.map(y => y.toString());
    const scaled = s.values.map(v => v / divisor);
    // Check if all zero
    if (scaled.every(v => v === 0)) continue;
    datasets.push({
      label: tech.label,
      data: scaled,
      backgroundColor: hexToRgba(tech.color, 0.7),
      borderColor: tech.color,
      borderWidth: 1,
      fill: true,
      pointRadius: 0,
      tension: 0,
    });
  }

  if (!allYears) allYears = [];

  const chart = new Chart(ctx, {
    type: 'line',
    data: { labels: allYears, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 1.5,
      scales: {
        x: { title: { display: true, text: 'Financial Year Starting' }, ticks: { maxRotation: 90, minRotation: 90 } },
        y: { stacked: true, title: { display: true, text: unit } },
      },
      plugins: {
        tooltip: { mode: 'index', intersect: false, callbacks: tooltipCallbacks },
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
      },
      interaction: { mode: 'index', intersect: false },
    },
  });
  charts.push(chart);
}

function makeCostChart(canvasId, series, divisor, unit) {
  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  const datasets = [];
  let allYears = null;

  for (const [category, s] of series) {
    if (!allYears) allYears = s.years.map(y => y.toString());
    const scaled = s.values.map(v => v / divisor);
    if (scaled.every(v => v === 0)) continue;
    const color = COST_COLORS[category] || '#999';
    const label = category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    datasets.push({
      label,
      data: scaled,
      backgroundColor: hexToRgba(color, 0.8),
      borderColor: color,
      borderWidth: 1,
    });
  }

  if (!allYears) allYears = [];

  const chart = new Chart(ctx, {
    type: 'bar',
    data: { labels: allYears, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 1.5,
      scales: {
        x: { stacked: true, title: { display: true, text: 'Financial Year Starting' }, ticks: { maxRotation: 90, minRotation: 90 } },
        y: { stacked: true, title: { display: true, text: unit } },
      },
      plugins: {
        tooltip: { mode: 'index', intersect: false, callbacks: tooltipCallbacks },
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
      },
      interaction: { mode: 'index', intersect: false },
    },
  });
  charts.push(chart);
}

function makeEmissionsChart(canvasId, emData, divisor, unit) {
  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  if (!emData) {
    const chart = new Chart(ctx, {
      type: 'line',
      data: { labels: [], datasets: [] },
      options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1.5 },
    });
    charts.push(chart);
    return;
  }

  const years = emData.years.map(y => y.toString());
  const scaled = emData.values.map(v => v / divisor);

  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: years,
      datasets: [{
        label: 'Emissions',
        data: scaled,
        borderColor: '#E15759',
        backgroundColor: hexToRgba('#E15759', 0.1),
        fill: true,
        pointRadius: 2,
        tension: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 1.5,
      scales: {
        x: { title: { display: true, text: 'Financial Year Starting' }, ticks: { maxRotation: 90, minRotation: 90 } },
        y: { title: { display: true, text: unit } },
      },
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false, callbacks: tooltipCallbacks },
      },
      interaction: { mode: 'index', intersect: false },
    },
  });
  charts.push(chart);
}

// ---------------------------------------------------------------------------
// Normal mode render
// ---------------------------------------------------------------------------

async function renderNormal() {
  const release = RELEASES.find(r => r.id === activeReleaseId);
  const scenario = tsScenario.getValue();
  const pathway = tsPathway.getValue();
  const region = tsRegion.getValue();

  showLoading(true);
  destroyCharts();

  try {
    const data = await loadData(release.id, scenario);

    // Update pathway selector if needed
    const pathways = getPathways(data);
    const cdpNames = data.cdp_names || {};
    const currentOptions = Object.keys(tsPathway.options);
    if (currentOptions.length !== pathways.length ||
        currentOptions[0] !== pathways[0]) {
      populatePathwayTomSelect(tsPathway, pathways, cdpNames);
      if (pathways.includes(pathway)) {
        tsPathway.setValue(pathway, true);
      } else {
        tsPathway.setValue(pickDefaultPathway(pathways), true);
      }
    }

    const activePath = tsPathway.getValue();

    // Energy
    const energySeries = extractSeries(data, 'energy', region, activePath);
    makeStackedChart('chart-energy', 'Generation', energySeries,
      DETAIL_TECHS.energy, TYPE_CONFIG.energy.divisor, TYPE_CONFIG.energy.unit);

    // Capacity
    const capSeries = extractSeries(data, 'capacity', region, activePath);
    makeStackedChart('chart-capacity', 'Capacity', capSeries,
      DETAIL_TECHS.capacity, TYPE_CONFIG.capacity.divisor, TYPE_CONFIG.capacity.unit);

    // Emissions
    const emData = extractEmissions(data, region, activePath);
    makeEmissionsChart('chart-emissions', emData,
      TYPE_CONFIG.emissions.divisor, TYPE_CONFIG.emissions.unit);

    // Cost (always _all region)
    const costSeries = extractSeries(data, 'cost', '_all', activePath);
    makeCostChart('chart-cost', costSeries,
      TYPE_CONFIG.cost.divisor, TYPE_CONFIG.cost.unit);

  } catch (err) {
    console.error('Failed to load data:', err);
    showFileError(err.message);
  }

  showLoading(false);
  updateHash();
}

// ---------------------------------------------------------------------------
// Comparison mode render
// ---------------------------------------------------------------------------

async function renderComparison() {
  showLoading(true);
  destroyCharts();

  // Reset grid to standard 2x2
  chartGrid.className = 'chart-grid';

  // Restore standard 4-card layout
  resetChartCards(['Generation Comparison', 'Capacity Comparison', 'Emissions Comparison', '']);

  // Filter to only enabled releases
  const activeReleases = RELEASES.filter(r => enabledReleases.has(r.id));

  try {
    // Use the first scenario for each release in comparison mode
    const allData = await Promise.all(
      activeReleases.map(r => loadData(r.id, r.scenarios[0]))
    );

    // Generation comparison
    renderComparisonChart('chart-energy', 'energy', activeReleases, allData);
    // Capacity comparison
    renderComparisonChart('chart-capacity', 'capacity', activeReleases, allData);
    // Emissions comparison
    renderEmissionsComparison('chart-emissions', activeReleases, allData);
    // Hide cost card
    document.getElementById('card-cost').style.display = 'none';

  } catch (err) {
    console.error('Failed to load comparison data:', err);
  }

  showLoading(false);
  updateHash();
}

function renderComparisonChart(canvasId, type, releases, allData) {
  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  const datasets = [];
  const groups = COMPARE_GROUPS[type];
  const divisor = TYPE_CONFIG[type].divisor;
  const unit = TYPE_CONFIG[type].unit;

  // Collect all years across releases for labels
  let allYearsSet = new Set();

  for (let ri = 0; ri < releases.length; ri++) {
    const release = releases[ri];
    const data = allData[ri];
    const pathways = getPathways(data);
    const series = extractSeries(data, type, '_all', pickDefaultPathway(pathways));

    for (const [groupName, fuelTechs] of Object.entries(groups)) {
      const grouped = sumGroup(series, fuelTechs);
      if (!grouped) continue;
      grouped.years.forEach(y => allYearsSet.add(y));
      const scaled = grouped.values.map(v => v / divisor);

      datasets.push({
        label: `${groupName} (${release.label})`,
        data: grouped.years.map((y, i) => ({ x: y.toString(), y: scaled[i] })),
        borderColor: COMPARE_COLORS[groupName],
        borderDash: getCompareDash(release.id),
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
        tension: 0,
      });
    }
  }

  const years = [...allYearsSet].sort().map(y => y.toString());

  const chart = new Chart(ctx, {
    type: 'line',
    data: { labels: years, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 1.5,
      scales: {
        x: { title: { display: true, text: 'Financial Year Starting' }, ticks: { maxRotation: 90, minRotation: 90 } },
        y: { title: { display: true, text: unit } },
      },
      plugins: {
        tooltip: { mode: 'index', intersect: false, callbacks: tooltipCallbacks },
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } },
      },
      interaction: { mode: 'index', intersect: false },
    },
  });
  charts.push(chart);
}

function renderEmissionsComparison(canvasId, releases, allData) {
  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  const datasets = [];
  const divisor = TYPE_CONFIG.emissions.divisor;
  const unit = TYPE_CONFIG.emissions.unit;
  let allYearsSet = new Set();

  for (let ri = 0; ri < releases.length; ri++) {
    const release = releases[ri];
    const data = allData[ri];
    const pathways = getPathways(data);
    const em = extractEmissions(data, '_all', pickDefaultPathway(pathways));
    if (!em) continue;
    em.years.forEach(y => allYearsSet.add(y));
    const scaled = em.values.map(v => v / divisor);

    datasets.push({
      label: release.label,
      data: em.years.map((y, i) => ({ x: y.toString(), y: scaled[i] })),
      borderColor: '#E15759',
      borderDash: getCompareDash(release.id),
      borderWidth: 2,
      pointRadius: 0,
      fill: false,
      tension: 0,
    });
  }

  const years = [...allYearsSet].sort().map(y => y.toString());

  const chart = new Chart(ctx, {
    type: 'line',
    data: { labels: years, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 1.5,
      scales: {
        x: { title: { display: true, text: 'Financial Year Starting' }, ticks: { maxRotation: 90, minRotation: 90 } },
        y: { title: { display: true, text: unit } },
      },
      plugins: {
        tooltip: { mode: 'index', intersect: false, callbacks: tooltipCallbacks },
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
      },
      interaction: { mode: 'index', intersect: false },
    },
  });
  charts.push(chart);
}

function resetChartCards(titles) {
  const cards = [
    { card: 'card-energy', title: titles[0] },
    { card: 'card-capacity', title: titles[1] },
    { card: 'card-emissions', title: titles[2] },
    { card: 'card-cost', title: titles[3] },
  ];
  for (const { card, title } of cards) {
    const el = document.getElementById(card);
    el.style.display = title ? '' : 'none';
    const h3 = el.querySelector('h3');
    if (h3 && title) h3.textContent = title;
  }
}

// ---------------------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------------------

function populateTomSelect(ts, options) {
  ts.clear(true);
  ts.clearOptions();
  for (const opt of options) {
    ts.addOption(opt);
  }
  ts.refreshOptions(false);
}

function populatePathwayTomSelect(ts, pathways, cdpNames) {
  ts.clear(true);
  ts.clearOptions();
  // Detect ODP from cdp_names "(ODP)" marker or from pathway key
  let detectedOdp = null;
  for (const [key, desc] of Object.entries(cdpNames)) {
    if (desc && desc.includes('(ODP)')) { detectedOdp = key; break; }
  }
  for (const p of pathways) {
    const isOdp = p === detectedOdp || p.includes('(ODP)');
    const normalizedKey = p.replace(/\s*\(ODP\)\s*/g, '').trim();
    const desc = cdpNames[p] || cdpNames[normalizedKey] || '';
    const cleanText = normalizedKey;
    const cleanDesc = desc.replace(/\s*\(ODP\)\s*/g, '').trim();
    ts.addOption({ value: p, text: cleanText, desc: cleanDesc, isOdp });
  }
  ts.refreshOptions(false);
}

function onReleaseChange() {
  const release = RELEASES.find(r => r.id === activeReleaseId);
  populateTomSelect(tsScenario, release.scenarios.map(s => ({
    value: s, text: formatScenario(s),
  })));
  const defaultScenario = release.scenarios.includes('step_change') ? 'step_change' : release.scenarios[0];
  tsScenario.setValue(defaultScenario, true);

  // Reset pathway — will be populated from data in renderNormal
  tsPathway.clear(true);
  tsPathway.clearOptions();
  tsPathway.addOption({ value: 'default', text: 'default', desc: '', isOdp: false });
  tsPathway.setValue('default', true);

  if (!compareMode) renderNormal();
}

function onScenarioChange() {
  if (!compareMode) renderNormal();
}

function onPathwayChange() {
  if (!compareMode) renderNormal();
}

function onRegionChange() {
  if (!compareMode) renderNormal();
}

function syncReleaseButtons() {
  releaseBar.querySelectorAll('.release-btn').forEach(btn => {
    const id = btn.dataset.release;
    if (compareMode) {
      if (id === 'ALL') {
        btn.classList.add('active');
      } else {
        btn.classList.toggle('active', enabledReleases.has(id));
      }
    } else {
      btn.classList.toggle('active', id === activeReleaseId);
      // "All" button not active in normal mode
      if (id === 'ALL') btn.classList.remove('active');
    }
  });
}

function enterCompareMode() {
  compareMode = true;
  activeReleaseId = null;
  tsScenario.wrapper.closest('.control-group').style.display = 'none';
  tsRegion.wrapper.closest('.control-group').style.display = 'none';
  tsPathway.wrapper.closest('.controls-row').style.display = 'none';
  syncReleaseButtons();
  renderComparison();
}

function exitCompareMode(releaseId) {
  compareMode = false;
  activeReleaseId = releaseId || RELEASES[RELEASES.length - 1].id;
  tsScenario.wrapper.closest('.control-group').style.display = '';
  tsRegion.wrapper.closest('.control-group').style.display = '';
  tsPathway.wrapper.closest('.controls-row').style.display = '';
  resetChartCards(['Generation', 'Capacity', 'Emissions', 'Cost (NEM-wide)']);
  document.getElementById('card-cost').style.display = '';
  chartGrid.className = 'chart-grid';
  syncReleaseButtons();
  onReleaseChange();
}

function onReleaseBarClick(releaseId) {
  if (releaseId === 'ALL') {
    // Toggle compare mode on/off
    if (compareMode) {
      exitCompareMode(lastActiveReleaseId);
    } else {
      lastActiveReleaseId = activeReleaseId;
      RELEASES.forEach(r => enabledReleases.add(r.id));
      enterCompareMode();
    }
  } else if (compareMode) {
    // Toggle individual release in compare mode
    if (enabledReleases.has(releaseId)) {
      // Don't allow disabling the last one
      if (enabledReleases.size > 1) {
        enabledReleases.delete(releaseId);
      }
    } else {
      enabledReleases.add(releaseId);
    }
    syncReleaseButtons();
    renderComparison();
  } else {
    // Normal mode — mutually exclusive selection
    activeReleaseId = releaseId;
    syncReleaseButtons();
    onReleaseChange();
  }
}

function releaseShortLabel(label) {
  // "2024 ISP Draft" → "2024D", "2024 ISP Final" → "2024", "2018 ISP" → "2018"
  const m = label.match(/^(\d{4})\s+ISP\s*(.*)/i);
  if (!m) return label;
  const year = m[1];
  const suffix = m[2].trim().toLowerCase();
  if (suffix === 'draft') return year + 'D';
  return year;
}

// ---------------------------------------------------------------------------
// URL hash state
// ---------------------------------------------------------------------------

function updateHash() {
  const params = new URLSearchParams();
  if (compareMode) {
    params.set('compare', 'true');
  } else {
    params.set('release', activeReleaseId);
    params.set('scenario', tsScenario.getValue());
    params.set('pathway', tsPathway.getValue());
    params.set('region', tsRegion.getValue());
  }
  history.replaceState(null, '', '#' + params.toString());
}

function readHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  return {
    release: params.get('release'),
    scenario: params.get('scenario'),
    pathway: params.get('pathway'),
    region: params.get('region'),
    compare: params.get('compare') === 'true',
  };
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

async function init() {
  const hash = readHash();

  // Load releases manifest
  try {
    const resp = await fetch('releases.json');
    RELEASES = await resp.json();
  } catch (e) {
    console.error('Failed to load releases.json:', e);
    showFileError('Could not load releases.json. Run: python3 src/build.py all');
    return;
  }

  // Populate enabledReleases
  RELEASES.forEach(r => enabledReleases.add(r.id));

  // Build download links from releases
  const downloadNav = document.getElementById('download-links');
  for (const r of RELEASES) {
    const a = document.createElement('a');
    a.href = `${r.id}.zip`;
    a.textContent = `${r.id}.zip`;
    downloadNav.appendChild(a);
  }

  // Build release button bar (legend already in HTML)

  const allBtn = document.createElement('button');
  allBtn.className = 'release-btn release-btn-all';
  allBtn.dataset.release = 'ALL';
  allBtn.textContent = 'All';
  allBtn.addEventListener('click', () => onReleaseBarClick('ALL'));
  releaseBar.appendChild(allBtn);

  for (const r of RELEASES) {
    const btn = document.createElement('button');
    btn.className = 'release-btn';
    btn.dataset.release = r.id;
    btn.textContent = releaseShortLabel(r.label);
    btn.addEventListener('click', () => onReleaseBarClick(r.id));
    releaseBar.appendChild(btn);
  }

  // Set initial active release (default to last = newest)
  if (hash.compare) {
    activeReleaseId = null;
  } else {
    activeReleaseId = hash.release && RELEASES.some(r => r.id === hash.release)
      ? hash.release : RELEASES[RELEASES.length - 1].id;
  }

  const release = RELEASES.find(r => r.id === activeReleaseId) || RELEASES[RELEASES.length - 1];

  // Tom Select — Scenario (no search)
  tsScenario = new TomSelect(selScenario, {
    controlInput: null,
    dropdownParent: 'body',
    options: release.scenarios.map(s => ({ value: s, text: formatScenario(s) })),
    items: [hash.scenario && release.scenarios.includes(hash.scenario) ? hash.scenario : release.scenarios[0]],
    onChange: onScenarioChange,
    onDropdownOpen: capDropdownHeight,
  });

  // Tom Select — CDP pathway (custom rendering for descriptions + ODP pill)
  const initialCdp = hash.pathway || 'default';
  tsPathway = new TomSelect(selPathway, {
    dropdownParent: 'body',
    options: [{ value: initialCdp, text: initialCdp, desc: '', isOdp: false }],
    items: [initialCdp],
    searchField: ['text', 'desc'],
    render: {
      option: function(data, escape) {
        const odpPill = data.isOdp ? '<span class="odp-pill">ODP</span>' : '';
        const cdpLabel = data.isOdp
          ? '<span class="cdp-pill">' + escape(data.text) + '</span>'
          : escape(data.text);
        const desc = data.desc ? '<span class="cdp-desc">' + escape(data.desc) + '</span>' : '';
        return '<div class="cdp-option">' + cdpLabel + desc + odpPill + '</div>';
      },
      item: function(data, escape) {
        const odpPill = data.isOdp ? ' <span class="odp-pill">ODP</span>' : '';
        const cdpLabel = data.isOdp
          ? '<span class="cdp-pill">' + escape(data.text) + '</span>'
          : escape(data.text);
        return '<div class="cdp-item">' + cdpLabel + odpPill + '</div>';
      },
    },
    onChange: onPathwayChange,
    onDropdownOpen: capDropdownHeight,
  });

  // Tom Select — Region (no search)
  const regionOpts = Object.entries(REGION_LABELS).map(([v, l]) => ({ value: v, text: l }));
  tsRegion = new TomSelect(selRegion, {
    controlInput: null,
    dropdownParent: 'body',
    options: regionOpts,
    items: [hash.region && REGION_LABELS[hash.region] ? hash.region : '_all'],
    onChange: onRegionChange,
  });

  // Initial render
  if (hash.compare) {
    onReleaseBarClick('ALL');
  } else {
    syncReleaseButtons();
    renderNormal();
  }
}

document.addEventListener('DOMContentLoaded', init);
