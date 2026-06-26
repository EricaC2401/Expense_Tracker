// Shared formatting utilities
let categoryColors = {};
const TRACKING_START_DATE = new Date(2021, 3, 1);
const CHART_CATEGORY_PALETTE = [
  '#5B6C9E',
  '#7C8FB8',
  '#8E79B7',
  '#B07AA1',
  '#C47A7A',
  '#C6925B',
  '#C9B458',
  '#8DAA5B',
  '#5E9B73',
  '#5A9D8F',
  '#5D98B3',
  '#7A8DA8',
  '#9A8F80',
  '#7E7E92',
];
const DEFAULT_CATEGORY_COLOR_MAP = {
  housing: '#5B6C9E',
  'car related': '#7C8FB8',
  'car related: fuel': '#B07AA1',
  'car related: parking': '#7A8DA8',
  'car related: annual': '#C47A7A',
  'car related: one-off': '#C6925B',
  'car related: other': '#5A9D8F',
  transport: '#5D98B3',
  food: '#5E9B73',
  groceries: '#8DAA5B',
  'c groceries': '#5A9D8F',
  drink: '#C9B458',
  'eating out': '#C6925B',
  'eat out': '#C6925B',
  shopping: '#8E79B7',
  bills: '#C47A7A',
  subscriptions: '#B07AA1',
  subscription: '#B07AA1',
  healthcare: '#5D98B3',
  health: '#5D98B3',
  travel: '#7A8DA8',
  gift: '#C47A7A',
  dating: '#C6925B',
  exam: '#7A8DA8',
  visa: '#5B6C9E',
  'money transfer': '#7E7E92',
  'flight ticket': '#5D98B3',
  learning: '#B07AA1',
  'learning to drive': '#B07AA1',
  electronics: '#8E79B7',
  tax: '#C47A7A',
  trip: '#7A8DA8',
  necessaries: '#8DAA5B',
  'appearance related': '#C47A7A',
  lh: '#B07AA1',
  other: '#7E7E92',
  gathering: '#C6925B',
  clothing: '#C47A7A',
  snacks: '#8E79B7',
  uncategorised: '#7A8DA8',
  social: '#5E9B73',
  'all car expenses': '#7C8FB8',
};

function normalizeCategoryColorKey(value) {
  return String(value || '').trim().toLowerCase();
}

function buildCategoryColorKey(category, groupName = '') {
  return `${normalizeCategoryColorKey(groupName)}::${normalizeCategoryColorKey(category)}`;
}

function setCategoryColorsFromEntries(entries = []) {
  categoryColors = {};
  entries.forEach(entry => {
    const category = entry?.category;
    const groupName = entry?.group_name || entry?.group;
    const color = entry?.color;
    if (!category || !color) return;

    categoryColors[buildCategoryColorKey(category, groupName)] = color;

    const plainKey = buildCategoryColorKey(category);
    if (!categoryColors[plainKey]) {
      categoryColors[plainKey] = color;
    }
  });
}

async function loadCategoryColors() {
  try {
    const data = await apiGet('/categories');
    setCategoryColorsFromEntries(data.categories || []);
  } catch (e) { console.warn('Could not load category colors:', e); }
}

function getCatColor(name, groupName = '') {
  const normalizedName = normalizeCategoryColorKey(name);
  const storedColor =
    categoryColors[buildCategoryColorKey(name, groupName)]
    || categoryColors[buildCategoryColorKey(name)]
  if (storedColor) {
    return storedColor;
  }
  if (DEFAULT_CATEGORY_COLOR_MAP[normalizedName]) {
    return DEFAULT_CATEGORY_COLOR_MAP[normalizedName];
  }

  const fallbackIndex = Array.from(normalizedName).reduce((sum, char) => sum + char.charCodeAt(0), 0)
    % CHART_CATEGORY_PALETTE.length;
  return CHART_CATEGORY_PALETTE[fallbackIndex];
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1,3), 16);
  const g = parseInt(hex.slice(3,5), 16);
  const b = parseInt(hex.slice(5,7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function categoryChip(name, groupName = '') {
  const c = getCatColor(name, groupName);
  return `<span class="chip" style="background:${hexToRgba(c,0.14)};border-color:${hexToRgba(c,0.22)};color:${c}">${name}</span>`;
}

function getGroupColor(name) {
  const normalized = (name || '').trim().toLowerCase();
  if (normalized === 'living') return '#5D98B3';
  if (normalized === 'travel') return '#7A8DA8';
  if (normalized === 'taxpayment') return '#C47A7A';
  return '#7A8DA8';
}

function groupChip(name) {
  const c = getGroupColor(name);
  return `<span class="chip" style="background:${hexToRgba(c,0.14)};border-color:${hexToRgba(c,0.22)};color:${c}">${name}</span>`;
}

function fmtAmt(value) {
  const num = parseFloat(value) || 0;
  return num.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtGBP(value) { return '£' + fmtAmt(value); }

function getFinancialYearStart(d) {
  const dt = d instanceof Date ? d : new Date(d);
  if (dt.getMonth() > 3 || (dt.getMonth() === 3 && dt.getDate() >= 6)) {
    return new Date(dt.getFullYear(), 3, 6);
  }
  return new Date(dt.getFullYear() - 1, 3, 6);
}

function getFinancialYearEnd(d) {
  const start = getFinancialYearStart(d);
  return new Date(start.getFullYear() + 1, 3, 5);
}

function toISODate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function lastDayOfMonth(year, monthIndex) {
  return new Date(year, monthIndex + 1, 0);
}

function monthLabel(d) {
  return d.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
}

function formatDisplayDate(d) {
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function parseISODate(value) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}
