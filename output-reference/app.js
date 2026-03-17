// ISP Chart Viewer — app.js
// Interactive charts from AEMO ISP workbook JSON data

// ---------------------------------------------------------------------------
// Constants (ported from generate_charts.py)
// ---------------------------------------------------------------------------

const RELEASES = [
  {
    id: '2026_ISP_draft',
    label: '2026 ISP Draft',
    scenarios: ['step_change', 'accelerated_transition', 'slower_growth'],
    defaultCdp: 'CDP1',
    odp: 'CDP4 (ODP)',
  },
  {
    id: '2024_ISP_final',
    label: '2024 ISP Final',
    scenarios: ['step_change', 'progressive_change', 'green_energy_exports'],
    defaultCdp: 'CDP1',
    odp: 'CDP14',
  },
  {
    id: '2022_ISP_final',
    label: '2022 ISP Final',
    scenarios: ['step_change', 'progressive_change', 'slow_change', 'hydrogen_superpower'],
    defaultCdp: 'CDP2',
    odp: 'CDP12',
  },
];

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

const COMPARE_DASHES = {
  '2026_ISP_draft': [],
  '2024_ISP_final': [8, 4],
  '2022_ISP_final': [2, 4],
};

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

// DOM refs
const selRelease  = document.getElementById('sel-release');
const selScenario = document.getElementById('sel-scenario');
const selPathway  = document.getElementById('sel-pathway');
const selRegion   = document.getElementById('sel-region');
const btnCompare  = document.getElementById('btn-compare');
const chartGrid   = document.getElementById('chart-grid');

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

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadData(releaseId, scenario) {
  const key = `${releaseId}/${scenario}`;
  if (cache.has(key)) return cache.get(key);
  const resp = await fetch(`${releaseId}/${scenario}.json`);
  const data = await resp.json();
  cache.set(key, data);
  return data;
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
        x: { title: { display: true, text: 'Financial Year Starting' } },
        y: { stacked: true, title: { display: true, text: unit } },
      },
      plugins: {
        tooltip: { mode: 'index', intersect: false },
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
      },
      interaction: { mode: 'index', intersect: false },
    },
  });
  charts.push(chart);
}

function makeCostChart(canvasId, series, divisor, unit) {
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
        x: { stacked: true, title: { display: true, text: 'Financial Year Starting' } },
        y: { stacked: true, title: { display: true, text: unit } },
      },
      plugins: {
        tooltip: { mode: 'index', intersect: false },
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
      },
      interaction: { mode: 'index', intersect: false },
    },
  });
  charts.push(chart);
}

function makeEmissionsChart(canvasId, emData, divisor, unit) {
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
        x: { title: { display: true, text: 'Financial Year Starting' } },
        y: { title: { display: true, text: unit } },
      },
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false },
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
  const release = RELEASES.find(r => r.id === selRelease.value);
  const scenario = selScenario.value;
  const pathway = selPathway.value;
  const region = selRegion.value;

  showLoading(true);
  destroyCharts();

  try {
    const data = await loadData(release.id, scenario);

    // Update pathway selector if needed
    const pathways = getPathways(data);
    if (selPathway.options.length !== pathways.length ||
        selPathway.options[0]?.value !== pathways[0]) {
      populateSelect(selPathway, pathways.map(p => ({ value: p, label: p })));
      if (pathways.includes(pathway)) {
        selPathway.value = pathway;
      } else {
        selPathway.value = release.defaultCdp;
      }
    }

    const activePath = selPathway.value;

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

  try {
    const allData = await Promise.all(
      RELEASES.map(r => loadData(r.id, 'step_change'))
    );

    // Generation comparison
    renderComparisonChart('chart-energy', 'energy', allData, 'Generation');
    // Capacity comparison
    renderComparisonChart('chart-capacity', 'capacity', allData, 'Capacity');
    // Emissions comparison
    renderEmissionsComparison('chart-emissions', allData);
    // Hide cost card
    document.getElementById('card-cost').style.display = 'none';

  } catch (err) {
    console.error('Failed to load comparison data:', err);
  }

  showLoading(false);
  updateHash();
}

function renderComparisonChart(canvasId, type, allData, typeLabel) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  const datasets = [];
  const groups = COMPARE_GROUPS[type];
  const divisor = TYPE_CONFIG[type].divisor;
  const unit = TYPE_CONFIG[type].unit;

  // Collect all years across releases for labels
  let allYearsSet = new Set();

  for (let ri = 0; ri < RELEASES.length; ri++) {
    const release = RELEASES[ri];
    const data = allData[ri];
    const series = extractSeries(data, type, '_all', release.defaultCdp);

    for (const [groupName, fuelTechs] of Object.entries(groups)) {
      const grouped = sumGroup(series, fuelTechs);
      if (!grouped) continue;
      grouped.years.forEach(y => allYearsSet.add(y));
      const scaled = grouped.values.map(v => v / divisor);

      datasets.push({
        label: `${groupName} (${release.label})`,
        data: grouped.years.map((y, i) => ({ x: y.toString(), y: scaled[i] })),
        borderColor: COMPARE_COLORS[groupName],
        borderDash: COMPARE_DASHES[release.id],
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
        x: { title: { display: true, text: 'Financial Year Starting' } },
        y: { title: { display: true, text: unit } },
      },
      plugins: {
        tooltip: { mode: 'index', intersect: false },
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } },
      },
      interaction: { mode: 'index', intersect: false },
    },
  });
  charts.push(chart);
}

function renderEmissionsComparison(canvasId, allData) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  const datasets = [];
  const divisor = TYPE_CONFIG.emissions.divisor;
  const unit = TYPE_CONFIG.emissions.unit;
  let allYearsSet = new Set();

  for (let ri = 0; ri < RELEASES.length; ri++) {
    const release = RELEASES[ri];
    const data = allData[ri];
    const em = extractEmissions(data, '_all', release.defaultCdp);
    if (!em) continue;
    em.years.forEach(y => allYearsSet.add(y));
    const scaled = em.values.map(v => v / divisor);

    datasets.push({
      label: release.label,
      data: em.years.map((y, i) => ({ x: y.toString(), y: scaled[i] })),
      borderColor: '#E15759',
      borderDash: COMPARE_DASHES[release.id],
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
        x: { title: { display: true, text: 'Financial Year Starting' } },
        y: { title: { display: true, text: unit } },
      },
      plugins: {
        tooltip: { mode: 'index', intersect: false },
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

function populateSelect(select, options) {
  select.innerHTML = '';
  for (const opt of options) {
    const el = document.createElement('option');
    el.value = opt.value;
    el.textContent = opt.label;
    select.appendChild(el);
  }
}

function onReleaseChange() {
  const release = RELEASES.find(r => r.id === selRelease.value);
  populateSelect(selScenario, release.scenarios.map(s => ({
    value: s, label: formatScenario(s),
  })));
  // Reset pathway to default for this release
  populateSelect(selPathway, [{ value: release.defaultCdp, label: release.defaultCdp }]);
  selPathway.value = release.defaultCdp;

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

function onCompareToggle() {
  compareMode = !compareMode;
  btnCompare.classList.toggle('active', compareMode);

  // Toggle control visibility
  selScenario.parentElement.style.display = compareMode ? 'none' : '';
  selPathway.parentElement.style.display = compareMode ? 'none' : '';
  selRegion.parentElement.style.display = compareMode ? 'none' : '';

  if (compareMode) {
    renderComparison();
  } else {
    resetChartCards(['Generation', 'Capacity', 'Emissions', 'Cost (NEM-wide)']);
    document.getElementById('card-cost').style.display = '';
    chartGrid.className = 'chart-grid';
    renderNormal();
  }
}

// ---------------------------------------------------------------------------
// URL hash state
// ---------------------------------------------------------------------------

function updateHash() {
  const params = new URLSearchParams();
  if (compareMode) {
    params.set('compare', 'true');
  } else {
    params.set('release', selRelease.value);
    params.set('scenario', selScenario.value);
    params.set('pathway', selPathway.value);
    params.set('region', selRegion.value);
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

function init() {
  // Populate release selector (2026 first = default)
  populateSelect(selRelease, RELEASES.map(r => ({ value: r.id, label: r.label })));

  // Populate region selector
  populateSelect(selRegion, Object.entries(REGION_LABELS).map(([v, l]) => ({ value: v, label: l })));

  // Read hash for initial state
  const hash = readHash();

  if (hash.release && RELEASES.some(r => r.id === hash.release)) {
    selRelease.value = hash.release;
  }
  // else default is first option = 2026_ISP_draft

  const release = RELEASES.find(r => r.id === selRelease.value);

  // Populate scenarios for selected release
  populateSelect(selScenario, release.scenarios.map(s => ({
    value: s, label: formatScenario(s),
  })));
  if (hash.scenario && release.scenarios.includes(hash.scenario)) {
    selScenario.value = hash.scenario;
  }

  // Set initial pathway (will be updated after data loads)
  populateSelect(selPathway, [{ value: release.defaultCdp, label: release.defaultCdp }]);
  if (hash.pathway) {
    // Add the hash pathway as an option temporarily; renderNormal will fix it
    const opt = document.createElement('option');
    opt.value = hash.pathway;
    opt.textContent = hash.pathway;
    selPathway.appendChild(opt);
    selPathway.value = hash.pathway;
  }

  if (hash.region && REGION_LABELS[hash.region]) {
    selRegion.value = hash.region;
  }

  // Wire up events
  selRelease.addEventListener('change', onReleaseChange);
  selScenario.addEventListener('change', onScenarioChange);
  selPathway.addEventListener('change', onPathwayChange);
  selRegion.addEventListener('change', onRegionChange);
  btnCompare.addEventListener('click', onCompareToggle);

  // Initial render
  if (hash.compare) {
    onCompareToggle();
  } else {
    renderNormal();
  }
}

document.addEventListener('DOMContentLoaded', init);
