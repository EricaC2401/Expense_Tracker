// Navigation + period management + initialization

const pages = {
  dashboard: { title: 'Dashboard', action: 'Add expense', pills: true },
  expenses:  { title: 'Expenses', action: 'Add expense', pills: false },
  income:    { title: 'Income', action: 'Add income', pills: false },
  tax:       { title: 'Tax', action: 'Add tax due', pills: false },
  finance:   { title: 'Finance snapshot', action: '', pills: false },
  recurring: { title: 'Recurring', action: 'New template', pills: false },
  reports:   { title: 'Reports', action: '', pills: false },
  import:    { title: 'Import', action: '', pills: false },
  export:    { title: 'Export', action: '', pills: false },
};

const TAX_DEFAULT_START_DATE = '2021-04-01';

let currentPage = 'dashboard';
let currentPeriodMode = 'Month';
let currentPeriodOptions = [];
let customPeriod = {
  start: toISODate(TRACKING_START_DATE),
  end: toISODate(new Date()),
};
const selectedPeriodKeys = {};
let expenseMetadata = null;
let expensePeriodMode = 'Month';
let expensePeriodOptions = [];
const expenseSelectedPeriodKeys = {};
let expenseCustomPeriod = {
  start: toISODate(monthStartDate(todayDate().getFullYear(), todayDate().getMonth())),
  end: toISODate(todayDate()),
};
let currentExpenseRows = [];
let editingExpenseId = null;
let incomeMetadata = null;
let incomePeriodMode = 'Financial year';
let incomePeriodOptions = [];
const incomeSelectedPeriodKeys = {};
let incomeCustomPeriod = {
  start: toISODate(getFinancialYearStart(todayDate())),
  end: toISODate(todayDate()),
};
let currentIncomeRows = [];
let editingIncomeId = null;
let taxMetadata = null;
let taxPeriodMode = 'Custom';
let taxPeriodOptions = [];
const taxSelectedPeriodKeys = {};
let taxCustomPeriod = {
  start: TAX_DEFAULT_START_DATE,
  end: toISODate(todayDate()),
};
let currentTaxRows = [];
let editingTaxId = null;
let financeSnapshotRows = [];
let editingFinanceSnapshotId = null;
let financeHistoryRows = [];
let currentFinanceOverview = null;
let financeDetailsSort = { key: 'updated_at', direction: 'desc' };
let financeHistorySort = { key: 'updated_at', direction: 'desc' };
const FINANCE_TABLE_PREVIEW_LIMIT = 6;
let categoryCatalog = [];
let categoryGroups = [];
let categoryManagerAvailable = true;
let reportCurrency = 'GBP';
let reportCategoryChartType = 'bar';
let reportLivingChartType = 'bar';
let reportTrendChartType = 'line';
let reportCategoryChart = null;
let reportLivingChart = null;
let reportTrendChart = null;
let currentReportsData = null;

function normalizeText(value) {
  return String(value || '').trim().replace(/\s+/g, ' ');
}

function getFinanceSortValue(entry, key) {
  const value = entry?.[key];
  if (value === null || value === undefined) return null;
  if (key === 'snapshot_date' || key === 'updated_at') {
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
  if (key === 'balance' || key === 'related_record_amount' || key === 'previous_balance' || key === 'signed_related_amount') {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  }
  return String(value).toLowerCase();
}

function deriveFinanceHistoryRows(entries) {
  const accountGroups = new Map();
  entries.forEach((entry) => {
    const key = `${entry.institution}|||${entry.account}|||${entry.currency}`;
    if (!accountGroups.has(key)) accountGroups.set(key, []);
    accountGroups.get(key).push(entry);
  });

  const derivedById = new Map();
  accountGroups.forEach((rows) => {
    const ordered = [...rows].sort((left, right) => {
      const leftTime = Date.parse(left.updated_at || left.snapshot_date || '') || 0;
      const rightTime = Date.parse(right.updated_at || right.snapshot_date || '') || 0;
      if (leftTime !== rightTime) return leftTime - rightTime;
      return Number(left.id || 0) - Number(right.id || 0);
    });

    let previousBalance = null;
    ordered.forEach((entry) => {
      const currentBalance = Number(entry.balance);
      const signedRelatedAmount = previousBalance === null || !Number.isFinite(currentBalance)
        ? null
        : currentBalance - previousBalance;
      derivedById.set(entry.id, {
        ...entry,
        previous_balance: previousBalance,
        signed_related_amount: signedRelatedAmount,
      });
      previousBalance = Number.isFinite(currentBalance) ? currentBalance : previousBalance;
    });
  });

  return entries.map((entry) => derivedById.get(entry.id) || {
    ...entry,
    previous_balance: null,
    signed_related_amount: null,
  });
}

function sortFinanceRows(rows, sortState) {
  const multiplier = sortState.direction === 'asc' ? 1 : -1;
  return [...rows].sort((left, right) => {
    const leftValue = getFinanceSortValue(left, sortState.key);
    const rightValue = getFinanceSortValue(right, sortState.key);

    if (leftValue === null && rightValue === null) return 0;
    if (leftValue === null) return 1;
    if (rightValue === null) return -1;
    if (leftValue < rightValue) return -1 * multiplier;
    if (leftValue > rightValue) return 1 * multiplier;

    const leftId = Number(left?.id || 0);
    const rightId = Number(right?.id || 0);
    return (rightId - leftId) * multiplier;
  });
}

function updateSortableHeaderLabels(tableBodyId, sortState) {
  const tbody = document.getElementById(tableBodyId);
  const table = tbody?.closest('table');
  if (!table) return;

  table.querySelectorAll('th.sortable-col').forEach((th) => {
    const baseLabel = th.dataset.baseLabel || th.textContent.replace(/^[↓↑]\s*/, '').trim();
    th.dataset.baseLabel = baseLabel;

    const onclickValue = th.getAttribute('onclick') || '';
    const match = onclickValue.match(/'([^']+)'/);
    const key = match ? match[1] : '';
    const arrow = key === sortState.key ? (sortState.direction === 'desc' ? '↓ ' : '↑ ') : '';
    th.textContent = `${arrow}${baseLabel}`;
  });
}

function setFinanceDetailsSort(key) {
  financeDetailsSort = financeDetailsSort.key === key
    ? { key, direction: financeDetailsSort.direction === 'desc' ? 'asc' : 'desc' }
    : { key, direction: 'desc' };
  renderFinanceSnapshot(financeSnapshotRows, currentFinanceOverview);
}

function setFinanceHistorySort(key) {
  financeHistorySort = financeHistorySort.key === key
    ? { key, direction: financeHistorySort.direction === 'desc' ? 'asc' : 'desc' }
    : { key, direction: 'desc' };
  renderFinanceHistory(financeHistoryRows);
}

function todayDate() {
  return new Date();
}

function monthStartDate(year, monthIndex) {
  return new Date(year, monthIndex, 1);
}

function buildMonthOptions() {
  const today = todayDate();
  const options = [];
  let cursor = monthStartDate(today.getFullYear(), today.getMonth());

  while (cursor >= TRACKING_START_DATE) {
    const start = monthStartDate(cursor.getFullYear(), cursor.getMonth());
    const monthEnd = lastDayOfMonth(cursor.getFullYear(), cursor.getMonth());
    const isCurrentMonth = cursor.getFullYear() === today.getFullYear() && cursor.getMonth() === today.getMonth();
    const end = isCurrentMonth ? today : monthEnd;
    options.push({
      key: `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}`,
      label: monthLabel(cursor),
      start: toISODate(start),
      end: toISODate(end),
    });
    cursor = monthStartDate(cursor.getFullYear(), cursor.getMonth() - 1);
  }

  return options;
}

function buildFinancialYearOptions() {
  const today = todayDate();
  const currentStart = getFinancialYearStart(today);
  const options = [];

  for (let startYear = currentStart.getFullYear(); startYear >= 2021; startYear -= 1) {
    const start = new Date(startYear, 3, 6);
    const nominalEnd = new Date(startYear + 1, 3, 5);
    const isCurrentFinancialYear = startYear === currentStart.getFullYear();
    const end = isCurrentFinancialYear ? today : nominalEnd;
    options.push({
      key: `fy-${startYear}`,
      label: `${startYear}/${String(startYear + 1).slice(-2)}`,
      start: toISODate(start),
      end: toISODate(end),
    });
  }

  return options;
}

function buildCalendarYearOptions() {
  const today = todayDate();
  const options = [];

  for (let year = today.getFullYear(); year >= 2021; year -= 1) {
    const isCurrentYear = year === today.getFullYear();
    options.push({
      key: `cy-${year}`,
      label: String(year),
      start: `${year}-01-01`,
      end: isCurrentYear ? toISODate(today) : `${year}-12-31`,
    });
  }

  return options;
}

function buildPeriodOptions(mode) {
  if (mode === 'Month') return buildMonthOptions();
  if (mode === 'Financial year') return buildFinancialYearOptions();
  if (mode === 'Calendar year') return buildCalendarYearOptions();
  return [];
}

function formatDateRangeText(startISO, endISO) {
  return `${formatDisplayDate(parseISODate(startISO))} to ${formatDisplayDate(parseISODate(endISO))}`;
}

function currentPeriodTitle() {
  if (currentPeriodMode === 'Custom') {
    return 'Custom range';
  }

  const selected = getSelectedPeriodOption();
  return selected ? selected.label : currentPeriodMode;
}

function syncPeriodSelector() {
  const wrap = document.getElementById('period-selector-wrap');
  const select = document.getElementById('period-selector');
  const customWrap = document.getElementById('custom-period-wrap');
  const customStart = document.getElementById('custom-start-date');
  const customEnd = document.getElementById('custom-end-date');
  if (!wrap || !select || !customWrap || !customStart || !customEnd) return;

  const pageConfig = pages[currentPage];
  if (!pageConfig?.pills) {
    currentPeriodOptions = [];
    wrap.style.display = 'none';
    customWrap.style.display = 'none';
    return;
  }

  const minDate = toISODate(TRACKING_START_DATE);
  const maxDate = toISODate(todayDate());
  customStart.min = minDate;
  customStart.max = maxDate;
  customEnd.min = minDate;
  customEnd.max = maxDate;

  if (currentPeriodMode === 'Custom') {
    currentPeriodOptions = [];
    wrap.style.display = 'none';
    customWrap.style.display = 'flex';
    customStart.value = customPeriod.start;
    customEnd.value = customPeriod.end;
    return;
  }

  customWrap.style.display = 'none';
  currentPeriodOptions = buildPeriodOptions(currentPeriodMode);
  wrap.style.display = 'flex';

  const savedKey = selectedPeriodKeys[currentPeriodMode];
  const activeKey = currentPeriodOptions.some(option => option.key === savedKey)
    ? savedKey
    : currentPeriodOptions[0]?.key;

  select.innerHTML = currentPeriodOptions
    .map(option => `<option value="${option.key}">${option.label}</option>`)
    .join('');

  if (activeKey) {
    select.value = activeKey;
    selectedPeriodKeys[currentPeriodMode] = activeKey;
  }
}

function getSelectedPeriodOption() {
  if (currentPeriodMode === 'Custom') return null;
  const key = selectedPeriodKeys[currentPeriodMode];
  return currentPeriodOptions.find(option => option.key === key) || currentPeriodOptions[0] || null;
}

function getPeriodDates(mode) {
  if (mode === 'Custom') {
    return { start: customPeriod.start, end: customPeriod.end };
  }

  const selectedOption = getSelectedPeriodOption();
  if (selectedOption) {
    return { start: selectedOption.start, end: selectedOption.end };
  }

  return { start: toISODate(TRACKING_START_DATE), end: toISODate(todayDate()) };
}

function getLatestExpenseDate() {
  if (!expenseMetadata?.latest_transaction_date) return todayDate();
  return parseISODate(expenseMetadata.latest_transaction_date);
}

function getAllKnownGroups() {
  const groups = new Set([
    ...categoryGroups,
    ...(expenseMetadata?.groups || []),
    'Living',
    'TaxPayment',
  ].map(normalizeText).filter(Boolean));
  return [...groups].sort((a, b) => a.localeCompare(b));
}

const PINNED_CATEGORIES = {
  'Living': ['Food', 'Snacks', 'Drink', 'Groceries'],
};

function getCategoryEntriesForGroup(groupName) {
  const normalizedGroup = normalizeText(groupName);
  const entries = categoryCatalog
    .filter(entry => normalizeText(entry.group_name) === normalizedGroup && entry.is_active !== false);

  const pinned = PINNED_CATEGORIES[groupName] || [];
  if (pinned.length) {
    const pinnedSet = new Set(pinned.map(c => c.toLowerCase()));
    const top = pinned
      .map(name => entries.find(e => e.category.toLowerCase() === name.toLowerCase()))
      .filter(Boolean);
    const rest = entries
      .filter(e => !pinnedSet.has(e.category.toLowerCase()))
      .sort((a, b) => a.category.localeCompare(b.category));
    return { top, others: rest, all: [...top, ...rest] };
  }

  const byUsageDesc = entries.slice().sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0));
  const top5 = byUsageDesc.slice(0, 5);
  const rest = byUsageDesc.slice(5).sort((a, b) => a.category.localeCompare(b.category));

  return { top: top5, others: rest, all: [...top5, ...rest] };
}

function setCategoryManagerAvailability(isAvailable, message = '') {
  categoryManagerAvailable = isAvailable;
}

async function buildFallbackCategoryCatalog() {
  try {
    const expenses = await apiGet('/expenses');
    const counts = {};
    for (const exp of expenses) {
      const cat = (exp.category || '').trim();
      const grp = (exp.group || '').trim();
      if (!cat) continue;
      const key = `${grp}\t${cat}`;
      counts[key] = (counts[key] || 0) + 1;
    }
    let id = -1;
    return Object.entries(counts).map(([key, count]) => {
      const [group_name, category] = key.split('\t');
      return { id: id--, category, group_name, usage_count: count, is_active: true };
    });
  } catch {
    return [];
  }
}

function populateExpenseGroupOptions() {
  const formGroupSelect = document.getElementById('exp-group');
  const filterGroupSelect = document.getElementById('expense-group-filter');
  const groups = getAllKnownGroups();

  if (formGroupSelect) {
    const selectedGroup = formGroupSelect.value || 'Living';
    formGroupSelect.innerHTML = groups.map(group => `<option>${group}</option>`).join('');
    formGroupSelect.value = groups.includes(selectedGroup) ? selectedGroup : (groups[0] || 'Living');
  }

  if (filterGroupSelect) {
    const selectedGroup = filterGroupSelect.value || 'All groups';
    filterGroupSelect.innerHTML = ['All groups', ...groups].map(group => `<option>${group}</option>`).join('');
    filterGroupSelect.value = ['All groups', ...groups].includes(selectedGroup) ? selectedGroup : 'All groups';
  }
}

function populateExpenseCategoryOptions(preserveValue = true) {
  const hiddenInput = document.getElementById('exp-category');
  const visibleInput = document.getElementById('exp-category-input');
  const dropdown = document.getElementById('exp-category-dropdown');
  const groupSelect = document.getElementById('exp-group');
  if (!hiddenInput || !visibleInput || !dropdown || !groupSelect) return;

  const currentValue = hiddenInput.value;
  const { top, others, all } = getCategoryEntriesForGroup(groupSelect.value);

  _buildCategoryDropdown(dropdown, top, others, hiddenInput, visibleInput);

  if (preserveValue && currentValue && all.some(e => e.category === currentValue)) {
    hiddenInput.value = currentValue;
    visibleInput.value = currentValue;
  } else if (all.length) {
    hiddenInput.value = all[0].category;
    visibleInput.value = all[0].category;
  } else {
    hiddenInput.value = '';
    visibleInput.value = '';
  }
}

function _buildCategoryDropdown(dropdown, top, others, hiddenInput, visibleInput, filter = '') {
  const needle = filter.trim().toLowerCase();
  const filterFn = entry => !needle || entry.category.toLowerCase().includes(needle);
  const filteredTop = top.filter(filterFn);
  const filteredOthers = others.filter(filterFn);

  let html = `<div class="searchable-select-search" style="position:relative">
    <i class="ti ti-search"></i>
    <input type="text" placeholder="Search categories…" id="exp-category-search" value="${filter.replace(/"/g, '&quot;')}">
  </div>`;

  if (!filteredTop.length && !filteredOthers.length) {
    html += `<div class="searchable-select-empty">No categories found</div>`;
  } else {
    if (filteredTop.length) {
      if (top.length + others.length > 5) {
        html += `<div class="searchable-select-divider">Most used</div>`;
      }
      filteredTop.forEach(entry => {
        const sel = hiddenInput.value === entry.category ? ' selected' : '';
        html += `<div class="searchable-select-option${sel}" data-value="${entry.category}">${entry.category}</div>`;
      });
    }
    if (filteredOthers.length) {
      if (filteredTop.length && top.length + others.length > 5) {
        html += `<div class="searchable-select-divider">Others (A–Z)</div>`;
      }
      filteredOthers.forEach(entry => {
        const sel = hiddenInput.value === entry.category ? ' selected' : '';
        html += `<div class="searchable-select-option${sel}" data-value="${entry.category}">${entry.category}</div>`;
      });
    }
  }

  dropdown.innerHTML = html;

  dropdown.querySelectorAll('.searchable-select-option').forEach(opt => {
    opt.addEventListener('mousedown', e => {
      e.preventDefault();
      hiddenInput.value = opt.dataset.value;
      visibleInput.value = opt.dataset.value;
      dropdown.classList.remove('open');
      visibleInput.blur();
    });
  });

  const searchBox = dropdown.querySelector('#exp-category-search');
  if (searchBox) {
    searchBox.addEventListener('input', () => {
      const groupSelect = document.getElementById('exp-group');
      const { top: t, others: o } = getCategoryEntriesForGroup(groupSelect.value);
      _buildCategoryDropdown(dropdown, t, o, hiddenInput, visibleInput, searchBox.value);
      const newSearch = dropdown.querySelector('#exp-category-search');
      if (newSearch) {
        newSearch.focus();
        newSearch.selectionStart = newSearch.selectionEnd = newSearch.value.length;
      }
    });
    searchBox.addEventListener('mousedown', e => e.stopPropagation());
  }
}

function openCategoryManager() {
  const overlay = document.getElementById('catmgr-overlay');
  if (!overlay) return;
  overlay.classList.add('open');
  renderCategoryManagerBody();
}

function closeCategoryManager() {
  const overlay = document.getElementById('catmgr-overlay');
  if (overlay) overlay.classList.remove('open');
  setCategoryManagerStatus();
}

function renderCategoryManagerBody() {
  const body = document.getElementById('catmgr-body');
  if (!body) return;

  const groups = getAllKnownGroups();
  const editable = categoryManagerAvailable;
  let html = '';

  for (const group of groups) {
    const { all: entries } = getCategoryEntriesForGroup(group);
    html += `<div class="catmgr-group">`;
    html += `<div class="catmgr-group-header">
      <div class="catmgr-group-name">${group}</div>
      ${editable ? `<button class="catmgr-add-btn" type="button" onclick="addCategoryRow('${group.replace(/'/g, "\\'")}')">+ Add tag</button>` : ''}
    </div>`;

    if (!entries.length) {
      html += `<div class="catmgr-empty">No categories yet.</div>`;
    } else {
      for (const entry of entries) {
        const esc = entry.category.replace(/"/g, '&quot;');
        const escSq = entry.category.replace(/'/g, "\\'");
        html += `<div class="catmgr-row" data-id="${entry.id}" data-original="${esc}">
          <input type="text" value="${esc}" id="catmgr-name-${entry.id}" ${editable ? '' : 'readonly'}>
          <div class="catmgr-row-preview">${categoryChip(entry.category, entry.group_name)}</div>
          <div class="catmgr-row-count">${entry.usage_count || 0} used</div>
          ${editable ? `<div class="catmgr-row-actions">
            <button class="catmgr-row-btn save" type="button" title="Save rename" onclick="renameCategoryRow(${entry.id})"><i class="ti ti-check"></i></button>
            <button class="catmgr-row-btn danger" type="button" title="Delete" onclick="deleteCategoryRow(${entry.id}, '${escSq}')"><i class="ti ti-trash"></i></button>
          </div>` : ''}
        </div>`;
      }
    }

    html += `</div>`;
  }

  if (!editable) {
    html += `<div style="margin-top:14px;padding:10px 14px;background:#f0f4ff;border:1px solid #c7d2fe;border-radius:8px;font-size:12px;color:#3730a3">
      Editing is unavailable until the category catalog migration is applied in Supabase.
    </div>`;
  }

  body.innerHTML = html;
}

async function loadCategoryCatalog(forceRefresh = false) {
  if (categoryCatalog.length && !forceRefresh) {
    return;
  }

  try {
    const data = await apiGet('/categories');
    categoryCatalog = data.categories || [];
    categoryGroups = data.groups || [];
    if (typeof setCategoryColorsFromEntries === 'function') {
      setCategoryColorsFromEntries(categoryCatalog);
    }
    setCategoryManagerAvailability(true);
  } catch (error) {
    categoryCatalog = await buildFallbackCategoryCatalog();
    categoryGroups = expenseMetadata?.groups || [];
    if (typeof setCategoryColorsFromEntries === 'function') {
      setCategoryColorsFromEntries(categoryCatalog);
    }
    setCategoryManagerAvailability(
      false,
      'Category manager is unavailable until the latest Supabase SQL migration is applied.',
    );
  }
  populateExpenseGroupOptions();
  populateExpenseCategoryOptions(false);
}

function buildExpenseMonthOptions(latestExpenseDate) {
  const options = [];
  let cursor = monthStartDate(latestExpenseDate.getFullYear(), latestExpenseDate.getMonth());
  const firstMonth = monthStartDate(TRACKING_START_DATE.getFullYear(), TRACKING_START_DATE.getMonth());

  while (cursor >= firstMonth) {
    const start = monthStartDate(cursor.getFullYear(), cursor.getMonth());
    const nominalEnd = lastDayOfMonth(cursor.getFullYear(), cursor.getMonth());
    const isLatestMonth =
      cursor.getFullYear() === latestExpenseDate.getFullYear()
      && cursor.getMonth() === latestExpenseDate.getMonth();
    options.push({
      key: `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}`,
      label: monthLabel(cursor),
      start: toISODate(start),
      end: toISODate(isLatestMonth ? latestExpenseDate : nominalEnd),
    });
    cursor = monthStartDate(cursor.getFullYear(), cursor.getMonth() - 1);
  }

  return options;
}

function buildExpenseFinancialYearOptions(latestExpenseDate) {
  const latestFinancialYearStart = getFinancialYearStart(latestExpenseDate);
  const options = [];

  for (let startYear = latestFinancialYearStart.getFullYear(); startYear >= 2021; startYear -= 1) {
    const start = new Date(startYear, 3, 6);
    const nominalEnd = new Date(startYear + 1, 3, 5);
    const isLatestFinancialYear = startYear === latestFinancialYearStart.getFullYear();
    options.push({
      key: `fy-${startYear}`,
      label: `${startYear}/${String(startYear + 1).slice(-2)}`,
      start: toISODate(start),
      end: toISODate(isLatestFinancialYear ? latestExpenseDate : nominalEnd),
    });
  }

  return options;
}

function buildExpenseCalendarYearOptions(latestExpenseDate) {
  const options = [];

  for (let year = latestExpenseDate.getFullYear(); year >= 2021; year -= 1) {
    const isLatestYear = year === latestExpenseDate.getFullYear();
    options.push({
      key: `cy-${year}`,
      label: String(year),
      start: `${year}-01-01`,
      end: isLatestYear ? toISODate(latestExpenseDate) : `${year}-12-31`,
    });
  }

  return options;
}

function buildExpensePeriodOptions(mode, latestExpenseDate) {
  if (mode === 'Month') return buildExpenseMonthOptions(latestExpenseDate);
  if (mode === 'Financial year') return buildExpenseFinancialYearOptions(latestExpenseDate);
  if (mode === 'Calendar year') return buildExpenseCalendarYearOptions(latestExpenseDate);
  return [];
}

function getLatestIncomeDate() {
  if (!incomeMetadata?.latest_income_date) return todayDate();
  return parseISODate(incomeMetadata.latest_income_date);
}

function buildIncomePeriodOptions(mode, latestIncomeDate) {
  if (mode === 'Month') return buildExpenseMonthOptions(latestIncomeDate);
  if (mode === 'Financial year') return buildExpenseFinancialYearOptions(latestIncomeDate);
  if (mode === 'Calendar year') return buildExpenseCalendarYearOptions(latestIncomeDate);
  return [];
}

function syncIncomePeriodSelector() {
  const timeframeSelect = document.getElementById('income-timeframe-filter');
  const customRange = document.getElementById('income-custom-range');
  const customStart = document.getElementById('income-custom-start');
  const customEnd = document.getElementById('income-custom-end');
  if (!timeframeSelect || !customRange || !customStart || !customEnd) return;

  const latestIncomeDate = getLatestIncomeDate();
  const minDate = toISODate(TRACKING_START_DATE);
  const maxDate = toISODate(latestIncomeDate);
  customStart.min = minDate;
  customStart.max = maxDate;
  customEnd.min = minDate;
  customEnd.max = maxDate;

  if (incomePeriodMode === 'Custom') {
    incomePeriodOptions = [];
    timeframeSelect.style.display = 'none';
    customRange.style.display = 'flex';
    if (!incomeCustomPeriod.start || incomeCustomPeriod.start < minDate) {
      incomeCustomPeriod.start = minDate;
    }
    if (!incomeCustomPeriod.end || incomeCustomPeriod.end > maxDate) {
      incomeCustomPeriod.end = maxDate;
    }
    if (incomeCustomPeriod.start > incomeCustomPeriod.end) {
      incomeCustomPeriod.start = incomeCustomPeriod.end;
    }
    customStart.value = incomeCustomPeriod.start;
    customEnd.value = incomeCustomPeriod.end;
    return;
  }

  timeframeSelect.style.display = '';
  customRange.style.display = 'none';
  incomePeriodOptions = buildIncomePeriodOptions(incomePeriodMode, latestIncomeDate);

  const savedKey = incomeSelectedPeriodKeys[incomePeriodMode];
  const activeKey = incomePeriodOptions.some(option => option.key === savedKey)
    ? savedKey
    : incomePeriodOptions[0]?.key;

  timeframeSelect.innerHTML = incomePeriodOptions
    .map(option => `<option value="${option.key}">${option.label}</option>`)
    .join('');

  if (activeKey) {
    timeframeSelect.value = activeKey;
    incomeSelectedPeriodKeys[incomePeriodMode] = activeKey;
  }
}

function getSelectedIncomePeriodOption() {
  const key = incomeSelectedPeriodKeys[incomePeriodMode];
  return incomePeriodOptions.find(option => option.key === key) || incomePeriodOptions[0] || null;
}

function getIncomePeriodDates() {
  if (incomePeriodMode === 'Custom') {
    return { start: incomeCustomPeriod.start, end: incomeCustomPeriod.end };
  }

  const selectedOption = getSelectedIncomePeriodOption();
  if (selectedOption) {
    return { start: selectedOption.start, end: selectedOption.end };
  }

  const latestIncomeDate = getLatestIncomeDate();
  return {
    start: toISODate(monthStartDate(latestIncomeDate.getFullYear(), latestIncomeDate.getMonth())),
    end: toISODate(latestIncomeDate),
  };
}

function syncIncomeCustomPeriodFromInputs() {
  const customStart = document.getElementById('income-custom-start');
  const customEnd = document.getElementById('income-custom-end');
  if (!customStart || !customEnd) return;

  const latestIncomeDate = getLatestIncomeDate();
  const minDate = toISODate(TRACKING_START_DATE);
  const maxDate = toISODate(latestIncomeDate);
  let start = customStart.value || minDate;
  let end = customEnd.value || maxDate;

  if (start < minDate) start = minDate;
  if (end > maxDate) end = maxDate;
  if (start > end) {
    if (document.activeElement === customStart) {
      end = start;
      customEnd.value = end;
    } else {
      start = end;
      customStart.value = start;
    }
  }

  incomeCustomPeriod = { start, end };
  customStart.value = start;
  customEnd.value = end;
}

function getLatestTaxDate() {
  if (!taxMetadata?.latest_tax_date) return todayDate();
  return parseISODate(taxMetadata.latest_tax_date);
}

function buildTaxPeriodOptions(mode, latestTaxDate) {
  if (mode === 'Month') return buildExpenseMonthOptions(latestTaxDate);
  if (mode === 'Financial year') return buildExpenseFinancialYearOptions(latestTaxDate);
  if (mode === 'Calendar year') return buildExpenseCalendarYearOptions(latestTaxDate);
  return [];
}

function syncTaxPeriodSelector() {
  const timeframeSelect = document.getElementById('tax-timeframe-filter');
  const customRange = document.getElementById('tax-custom-range');
  const customStart = document.getElementById('tax-custom-start');
  const customEnd = document.getElementById('tax-custom-end');
  if (!timeframeSelect || !customRange || !customStart || !customEnd) return;

  const latestTaxDate = getLatestTaxDate();
  const minDate = TAX_DEFAULT_START_DATE;
  const maxDate = toISODate(latestTaxDate);
  customStart.min = minDate;
  customStart.max = maxDate;
  customEnd.min = minDate;
  customEnd.max = maxDate;

  if (taxPeriodMode === 'Custom') {
    taxPeriodOptions = [];
    timeframeSelect.style.display = 'none';
    customRange.style.display = 'flex';
    if (!taxCustomPeriod.start || taxCustomPeriod.start < minDate) {
      taxCustomPeriod.start = minDate;
    }
    if (!taxCustomPeriod.end || taxCustomPeriod.end > maxDate) {
      taxCustomPeriod.end = maxDate;
    }
    if (taxCustomPeriod.start > taxCustomPeriod.end) {
      taxCustomPeriod.start = taxCustomPeriod.end;
    }
    customStart.value = taxCustomPeriod.start;
    customEnd.value = taxCustomPeriod.end;
    return;
  }

  timeframeSelect.style.display = '';
  customRange.style.display = 'none';
  taxPeriodOptions = buildTaxPeriodOptions(taxPeriodMode, latestTaxDate);

  const savedKey = taxSelectedPeriodKeys[taxPeriodMode];
  const activeKey = taxPeriodOptions.some(option => option.key === savedKey)
    ? savedKey
    : taxPeriodOptions[0]?.key;

  timeframeSelect.innerHTML = taxPeriodOptions
    .map(option => `<option value="${option.key}">${option.label}</option>`)
    .join('');

  if (activeKey) {
    timeframeSelect.value = activeKey;
    taxSelectedPeriodKeys[taxPeriodMode] = activeKey;
  }
}

function getSelectedTaxPeriodOption() {
  const key = taxSelectedPeriodKeys[taxPeriodMode];
  return taxPeriodOptions.find(option => option.key === key) || taxPeriodOptions[0] || null;
}

function getTaxPeriodDates() {
  if (taxPeriodMode === 'Custom') {
    return { start: taxCustomPeriod.start, end: taxCustomPeriod.end };
  }

  const selectedOption = getSelectedTaxPeriodOption();
  if (selectedOption) {
    return { start: selectedOption.start, end: selectedOption.end };
  }

  const latestTaxDate = getLatestTaxDate();
  return {
    start: toISODate(monthStartDate(latestTaxDate.getFullYear(), latestTaxDate.getMonth())),
    end: toISODate(latestTaxDate),
  };
}

function syncTaxCustomPeriodFromInputs() {
  const customStart = document.getElementById('tax-custom-start');
  const customEnd = document.getElementById('tax-custom-end');
  if (!customStart || !customEnd) return;

  const latestTaxDate = getLatestTaxDate();
  const minDate = TAX_DEFAULT_START_DATE;
  const maxDate = toISODate(latestTaxDate);
  let start = customStart.value || minDate;
  let end = customEnd.value || maxDate;

  if (start < minDate) start = minDate;
  if (end > maxDate) end = maxDate;
  if (start > end) {
    if (document.activeElement === customStart) {
      end = start;
      customEnd.value = end;
    } else {
      start = end;
      customStart.value = start;
    }
  }

  taxCustomPeriod = { start, end };
  customStart.value = start;
  customEnd.value = end;
}

function syncExpensePeriodSelector() {
  const periodSelect = document.getElementById('expense-period-filter');
  const timeframeSelect = document.getElementById('expense-timeframe-filter');
  const customRange = document.getElementById('expense-custom-range');
  const customStart = document.getElementById('expense-custom-start');
  const customEnd = document.getElementById('expense-custom-end');
  if (!periodSelect || !timeframeSelect || !customRange || !customStart || !customEnd) return;

  const latestExpenseDate = getLatestExpenseDate();
  const minDate = toISODate(TRACKING_START_DATE);
  const maxDate = toISODate(latestExpenseDate);
  customStart.min = minDate;
  customStart.max = maxDate;
  customEnd.min = minDate;
  customEnd.max = maxDate;

  if (expensePeriodMode === 'Custom') {
    expensePeriodOptions = [];
    timeframeSelect.style.display = 'none';
    customRange.style.display = 'flex';
    if (!expenseCustomPeriod.start || expenseCustomPeriod.start < minDate) {
      expenseCustomPeriod.start = minDate;
    }
    if (!expenseCustomPeriod.end || expenseCustomPeriod.end > maxDate) {
      expenseCustomPeriod.end = maxDate;
    }
    if (expenseCustomPeriod.start > expenseCustomPeriod.end) {
      expenseCustomPeriod.start = expenseCustomPeriod.end;
    }
    customStart.value = expenseCustomPeriod.start;
    customEnd.value = expenseCustomPeriod.end;
    return;
  }

  timeframeSelect.style.display = '';
  customRange.style.display = 'none';
  expensePeriodOptions = buildExpensePeriodOptions(expensePeriodMode, latestExpenseDate);

  const savedKey = expenseSelectedPeriodKeys[expensePeriodMode];
  const activeKey = expensePeriodOptions.some(option => option.key === savedKey)
    ? savedKey
    : expensePeriodOptions[0]?.key;

  timeframeSelect.innerHTML = expensePeriodOptions
    .map(option => `<option value="${option.key}">${option.label}</option>`)
    .join('');

  if (activeKey) {
    timeframeSelect.value = activeKey;
    expenseSelectedPeriodKeys[expensePeriodMode] = activeKey;
  }
}

function getSelectedExpensePeriodOption() {
  const key = expenseSelectedPeriodKeys[expensePeriodMode];
  return expensePeriodOptions.find(option => option.key === key) || expensePeriodOptions[0] || null;
}

function getExpensePeriodDates() {
  if (expensePeriodMode === 'Custom') {
    return { start: expenseCustomPeriod.start, end: expenseCustomPeriod.end };
  }

  const selectedOption = getSelectedExpensePeriodOption();
  if (selectedOption) {
    return { start: selectedOption.start, end: selectedOption.end };
  }

  const latestExpenseDate = getLatestExpenseDate();
  return {
    start: toISODate(monthStartDate(latestExpenseDate.getFullYear(), latestExpenseDate.getMonth())),
    end: toISODate(latestExpenseDate),
  };
}

function populateExpenseFilterOptions() {
  const categorySelect = document.getElementById('expense-cat-filter');
  const paymentSelect = document.getElementById('expense-payment-filter');
  const categoryFormSelect = document.getElementById('exp-category');

  if (!categorySelect || !paymentSelect || !categoryFormSelect) return;

  const catalogCategories = categoryCatalog.map(entry => entry.category).filter(Boolean);
  const metadataCategories = expenseMetadata?.categories || [];
  const categories = [...new Set([...catalogCategories, ...metadataCategories])].sort((a, b) => a.localeCompare(b));
  const paymentMethods = expenseMetadata?.payment_methods || [];

  categorySelect.innerHTML = ['All categories', ...categories]
    .map(option => `<option>${option}</option>`)
    .join('');
  paymentSelect.innerHTML = ['All payment methods', ...paymentMethods]
    .map(option => `<option>${option}</option>`)
    .join('');
}

function syncExpenseCustomPeriodFromInputs() {
  const customStart = document.getElementById('expense-custom-start');
  const customEnd = document.getElementById('expense-custom-end');
  if (!customStart || !customEnd) return;

  const latestExpenseDate = getLatestExpenseDate();
  const minDate = toISODate(TRACKING_START_DATE);
  const maxDate = toISODate(latestExpenseDate);
  let start = customStart.value || minDate;
  let end = customEnd.value || maxDate;

  if (start < minDate) start = minDate;
  if (end > maxDate) end = maxDate;
  if (start > end) {
    if (document.activeElement === customStart) {
      end = start;
      customEnd.value = end;
    } else {
      start = end;
      customStart.value = start;
    }
  }

  expenseCustomPeriod = { start, end };
  customStart.value = start;
  customEnd.value = end;
}

function renderExpensesTable(transactions) {
  const tbody = document.getElementById('expense-tbody');
  if (!tbody) return;
  const renderGroupChip = typeof groupChip === 'function'
    ? groupChip
    : (name => name || '—');
  currentExpenseRows = transactions;

  const totalGbp = transactions.reduce(
    (sum, transaction) => sum + (parseFloat(transaction.amount_gbp) || 0),
    0,
  );
  const totalHkd = transactions.reduce(
    (sum, transaction) => sum + (parseFloat(transaction.amount_hkd) || 0),
    0,
  );
  updateExpenseTableSummary({
    count: transactions.length,
    totalGbp,
    totalHkd,
  });

  if (!transactions.length) {
    tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:#8492a6;padding:20px">No expenses match the selected period.</td></tr>';
    return;
  }

  tbody.innerHTML = transactions
    .map(transaction => {
      const amountHkd = transaction.amount_hkd ? `HK$${fmtAmt(transaction.amount_hkd)}` : '—';
      const paymentMethod = transaction.payment_method || '—';
      const notes = transaction.notes || '';
      const taxDeductable = transaction.tax_deductable ? '✓' : '';
      return `<tr>
        <td><input type="checkbox"></td>
        <td>${transaction.transaction_date}</td>
        <td>${transaction.description}</td>
        <td>${categoryChip(transaction.category, transaction.group)}</td>
        <td>${renderGroupChip(transaction.group)}</td>
        <td style="font-weight:600">${fmtGBP(transaction.amount_gbp)}</td>
        <td>${amountHkd}</td>
        <td style="text-align:center">${taxDeductable}</td>
        <td>${paymentMethod}</td>
        <td>${notes}</td>
        <td>
          <div class="row-actions">
            <button class="btn-inline" type="button" onclick="editExpense(${transaction.id})">Edit</button>
            <button class="btn-inline danger" type="button" onclick="deleteExpense(${transaction.id})">Delete</button>
          </div>
        </td>
      </tr>`;
    })
    .join('');
}

function updateExpenseTableSummary({ count, totalGbp, totalHkd }) {
  const countEl = document.getElementById('expense-table-count');
  const totalEl = document.getElementById('expense-table-total');
  if (!countEl || !totalEl) return;

  countEl.textContent = `Showing ${count} expense(s).`;
  const totalParts = [`GBP ${fmtAmt(totalGbp)}`];
  if (totalHkd > 0) {
    totalParts.push(`HKD ${fmtAmt(totalHkd)}`);
  }
  totalEl.textContent = `Total: ${totalParts.join(' | ')}`;
}

function populateIncomeFilterOptions() {
  const sourceSelect = document.getElementById('income-source-filter');
  const currencySelect = document.getElementById('income-currency-filter');
  const accountSelect = document.getElementById('income-account-filter');
  if (!sourceSelect || !currencySelect || !accountSelect) return;

  const sources = incomeMetadata?.sources || [];
  const currencies = incomeMetadata?.currencies || [];
  const accounts = incomeMetadata?.payment_accounts || [];

  sourceSelect.innerHTML = ['All sources', ...sources].map(option => `<option>${option}</option>`).join('');
  currencySelect.innerHTML = ['All currencies', ...currencies].map(option => `<option>${option}</option>`).join('');
  accountSelect.innerHTML = ['All accounts', ...accounts].map(option => `<option>${option}</option>`).join('');
}

function updateIncomeTableSummary({ count, totalGbp, totalOriginal }) {
  const countEl = document.getElementById('income-table-count');
  const totalEl = document.getElementById('income-table-total');
  if (!countEl || !totalEl) return;

  countEl.textContent = `Showing ${count} income item(s).`;
  totalEl.textContent = `Total: GBP ${fmtAmt(totalGbp)} | Gross ${fmtAmt(totalOriginal)}`;
}

function renderIncomeStatus(message, color = '#8492a6') {
  const tbody = document.getElementById('income-tbody');
  if (!tbody) return;
  currentIncomeRows = [];
  updateIncomeTableSummary({ count: 0, totalGbp: 0, totalOriginal: 0 });
  tbody.innerHTML = `<tr><td colspan="12" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
}

function renderIncomeTable(incomes) {
  const tbody = document.getElementById('income-tbody');
  if (!tbody) return;
  currentIncomeRows = incomes;

  const totalGbp = incomes.reduce((sum, income) => sum + (parseFloat(income.gross_amount_gbp) || parseFloat(income.gross_amount) || 0), 0);
  const totalOriginal = incomes.reduce((sum, income) => sum + (parseFloat(income.gross_amount) || 0), 0);
  updateIncomeTableSummary({ count: incomes.length, totalGbp, totalOriginal });

  if (!incomes.length) {
    tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:#8492a6;padding:20px">No income matches the selected period.</td></tr>';
    return;
  }

  tbody.innerHTML = incomes.map(income => {
    const grossGbp = income.gross_amount_gbp ? fmtGBP(income.gross_amount_gbp) : '—';
    const fxRate = income.fx_rate_to_gbp || '—';
    const account = income.payment_account || '—';
    const notes = income.notes || '';
    const taxable = income.is_taxable ? '✓' : '';
    return `<tr>
      <td><input type="checkbox"></td>
      <td>${income.income_date}</td>
      <td>${income.description}</td>
      <td>${income.source}</td>
      <td>${income.currency}</td>
      <td style="font-weight:600">${fmtAmt(income.gross_amount)}</td>
      <td>${grossGbp}</td>
      <td>${fxRate}</td>
      <td style="text-align:center">${taxable}</td>
      <td>${account}</td>
      <td>${notes}</td>
      <td>
        <div class="row-actions">
          <button class="btn-inline" type="button" onclick="editIncome(${income.id})">Edit</button>
          <button class="btn-inline danger" type="button" onclick="deleteIncome(${income.id})">Delete</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function setIncomeFormStatus(message = '', type = '') {
  let statusEl = document.getElementById('income-form-status');
  if (!statusEl) {
    const actions = document.querySelector('#sec-income .form-actions');
    if (!actions) return;
    statusEl = document.createElement('div');
    statusEl.id = 'income-form-status';
    statusEl.className = 'form-status';
    actions.parentNode.insertBefore(statusEl, actions);
  }
  statusEl.textContent = message;
  statusEl.className = type ? `form-status ${type}` : 'form-status';
}

function updateIncomeMetrics(incomes, taxEntries, dates) {
  const grossIncomeGbp = incomes.reduce((sum, income) => sum + (parseFloat(income.gross_amount_gbp) || parseFloat(income.gross_amount) || 0), 0);
  const totalTax = taxEntries.reduce((sum, entry) => sum + (parseFloat(entry.amount_gbp) || 0), 0);
  const afterTax = grossIncomeGbp - totalTax;

  document.getElementById('mc-gross-income').textContent = fmtGBP(grossIncomeGbp);
  document.getElementById('mc-gross-income-sub').textContent = formatDateRangeText(dates.start, dates.end);
  document.getElementById('mc-tax-due').textContent = fmtGBP(totalTax);
  document.getElementById('mc-after-tax').textContent = fmtGBP(afterTax);
}

function clearIncomeForm() {
  editingIncomeId = null;
  document.getElementById('inc-date').value = toISODate(todayDate());
  document.getElementById('inc-desc').value = '';
  document.getElementById('inc-source').value = '';
  document.getElementById('inc-currency').value = 'GBP';
  document.getElementById('inc-amount').value = '';
  document.getElementById('inc-gbp').value = '';
  document.getElementById('inc-fx').value = '';
  document.getElementById('inc-account').value = '';
  document.getElementById('inc-taxable').checked = true;
  setIncomeFormStatus();
  updateIncomeSaveButton();
}

function updateIncomeSaveButton() {
  const buttons = document.querySelectorAll('#sec-income .btn-primary');
  const saveButton = buttons[buttons.length - 1];
  if (!saveButton) return;
  saveButton.innerHTML = editingIncomeId === null
    ? '<i class="ti ti-check"></i>Save income'
    : '<i class="ti ti-device-floppy"></i>Update income';
}

function buildIncomePayloadFromForm() {
  return {
    income_date: document.getElementById('inc-date').value,
    description: document.getElementById('inc-desc').value.trim(),
    source: document.getElementById('inc-source').value.trim(),
    currency: document.getElementById('inc-currency').value,
    gross_amount: (document.getElementById('inc-amount').value || '0').trim(),
    gross_amount_gbp: document.getElementById('inc-gbp').value.trim() || null,
    fx_rate_to_gbp: document.getElementById('inc-fx').value.trim() || null,
    is_taxable: document.getElementById('inc-taxable').checked,
    payment_account: document.getElementById('inc-account').value || null,
    notes: null,
  };
}

function populateTaxFilterOptions() {
  const taxPeriodSelect = document.getElementById('tax-period-name-filter');
  if (!taxPeriodSelect) return;
  const taxPeriods = taxMetadata?.tax_periods || [];
  taxPeriodSelect.innerHTML = ['All periods', ...taxPeriods].map(option => `<option>${option}</option>`).join('');
}

function updateTaxTableSummary({ count, totalGbp }) {
  const countEl = document.getElementById('tax-table-count');
  const totalEl = document.getElementById('tax-table-total');
  if (!countEl || !totalEl) return;
  countEl.textContent = `Showing ${count} tax entry(s).`;
  totalEl.textContent = `Total: GBP ${fmtAmt(totalGbp)}`;
}

function renderTaxStatus(message, color = '#8492a6') {
  const tbody = document.getElementById('tax-tbody');
  if (!tbody) return;
  currentTaxRows = [];
  updateTaxTableSummary({ count: 0, totalGbp: 0 });
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
}

function renderTaxTable(entries) {
  const tbody = document.getElementById('tax-tbody');
  if (!tbody) return;
  currentTaxRows = entries;
  const totalGbp = entries.reduce((sum, entry) => sum + (parseFloat(entry.amount_gbp) || 0), 0);
  updateTaxTableSummary({ count: entries.length, totalGbp });

  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8492a6;padding:20px">No tax entries match the selected period.</td></tr>';
    return;
  }

  tbody.innerHTML = entries.map(entry => `<tr>
    <td><input type="checkbox"></td>
    <td>${entry.tax_date}</td>
    <td>${entry.tax_period}</td>
    <td style="font-weight:600">${fmtGBP(entry.amount_gbp)}</td>
    <td>${entry.notes || ''}</td>
    <td>
      <div class="row-actions">
        <button class="btn-inline" type="button" onclick="editTaxDue(${entry.id})">Edit</button>
        <button class="btn-inline danger" type="button" onclick="deleteTaxDue(${entry.id})">Delete</button>
      </div>
    </td>
  </tr>`).join('');
}

function updateTaxMetrics(entries, dates) {
  const totalGbp = entries.reduce((sum, entry) => sum + (parseFloat(entry.amount_gbp) || 0), 0);
  const average = entries.length ? totalGbp / entries.length : 0;
  document.getElementById('mc-tax-total').textContent = fmtGBP(totalGbp);
  document.getElementById('mc-tax-total-sub').textContent = formatDateRangeText(dates.start, dates.end);
  document.getElementById('mc-tax-count').textContent = String(entries.length);
  document.getElementById('mc-tax-average').textContent = fmtGBP(average);
}

function setTaxFormStatus(message = '', type = '') {
  const statusEl = document.getElementById('tax-form-status');
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = type ? `form-status ${type}` : 'form-status';
}

function updateTaxSaveButton() {
  const saveButton = document.getElementById('tax-save-btn');
  if (!saveButton) return;
  saveButton.innerHTML = editingTaxId === null
    ? '<i class="ti ti-check"></i>Save tax due'
    : '<i class="ti ti-device-floppy"></i>Update tax due';
}

function clearTaxForm() {
  editingTaxId = null;
  document.getElementById('tax-date').value = toISODate(todayDate());
  document.getElementById('tax-period').value = '';
  document.getElementById('tax-amount').value = '';
  document.getElementById('tax-notes').value = '';
  setTaxFormStatus();
  updateTaxSaveButton();
}

function buildTaxPayloadFromForm() {
  return {
    tax_date: document.getElementById('tax-date').value,
    tax_period: document.getElementById('tax-period').value.trim(),
    amount_gbp: (document.getElementById('tax-amount').value || '0').trim(),
    notes: document.getElementById('tax-notes').value.trim() || null,
  };
}

function renderFinanceSnapshotStatus(message, color = '#8492a6') {
  const detailsTbody = document.getElementById('finance-details-tbody');
  const leftTbody = document.getElementById('finance-summary-left');
  const rightTbody = document.getElementById('finance-summary-right');
  const bottomTbody = document.getElementById('finance-summary-bottom');
  const lowerLeftTbody = document.getElementById('finance-summary-lower-left');
  const lowerRightTbody = document.getElementById('finance-summary-lower-right');
  if (detailsTbody) {
    detailsTbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
  }
  if (leftTbody) leftTbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
  if (rightTbody) rightTbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
  if (bottomTbody) bottomTbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
  if (lowerLeftTbody) lowerLeftTbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
  if (lowerRightTbody) lowerRightTbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
}

function renderFinanceSnapshot(entries, overview = null) {
  const detailsTbody = document.getElementById('finance-details-tbody');
  const leftTbody = document.getElementById('finance-summary-left');
  const rightTbody = document.getElementById('finance-summary-right');
  const bottomTbody = document.getElementById('finance-summary-bottom');
  const lowerLeftTbody = document.getElementById('finance-summary-lower-left');
  const lowerRightTbody = document.getElementById('finance-summary-lower-right');
  if (!detailsTbody || !leftTbody || !rightTbody || !bottomTbody || !lowerLeftTbody || !lowerRightTbody) return;
  financeSnapshotRows = entries;
  currentFinanceOverview = overview;
  updateSortableHeaderLabels('finance-details-tbody', financeDetailsSort);

  if (!entries.length) {
    renderFinanceSnapshotStatus('No finance snapshot data yet.');
    document.getElementById('mc-fin-gbp').textContent = '—';
    document.getElementById('mc-fin-gbp-sub').textContent = 'GBP — | HKD —';
    document.getElementById('mc-fin-hkd').textContent = '—';
    document.getElementById('mc-fin-hkd-sub').textContent = 'GBP — | HKD —';
    document.getElementById('mc-fin-rate').textContent = '—';
    return;
  }

  const currencyTotals = overview?.currency_totals || [];
  const scenarioTotals = overview?.scenario_totals || [];
  const fxRates = overview?.fx_rates_to_hkd || {};
  const sortedEntries = sortFinanceRows(entries, financeDetailsSort);

  detailsTbody.innerHTML = sortedEntries.map(entry => `<tr>
    <td>${entry.snapshot_date}</td>
    <td>${entry.updated_at || '—'}</td>
    <td>${entry.institution}</td>
    <td>${entry.account}</td>
    <td>${entry.currency}</td>
    <td style="font-weight:600">${fmtAmt(entry.balance)}</td>
    <td>${entry.account_type || ''}</td>
    <td>${entry.notes || ''}</td>
    <td>
      <div class="row-actions">
        <button class="btn-inline" type="button" onclick="editFinanceSnapshot(${entry.id})">Edit</button>
        <button class="btn-inline danger" type="button" onclick="deleteFinanceSnapshot(${entry.id})">Delete</button>
      </div>
    </td>
  </tr>`).join('');

  const excluding = scenarioTotals.find(row => row.scenario === "Excluding Mum's Time D");
  const including = scenarioTotals.find(row => row.scenario === "Including Mum's Time D");
  const mumsTimeDRow = currencyTotals.find(row => row.currency === "Mum's Time D");
  const baseCurrencyRows = currencyTotals.filter(row => row.currency !== "Mum's Time D");
  const midpoint = Math.ceil(baseCurrencyRows.length / 2);
  const leftRows = baseCurrencyRows.slice(0, midpoint);
  const rightRows = baseCurrencyRows.slice(midpoint);

  leftTbody.innerHTML = leftRows.map(row => `<tr><td>${row.currency}</td><td style="font-weight:600">${fmtAmt(row.balance)}</td></tr>`).join('');
  rightTbody.innerHTML = rightRows.map(row => `<tr><td>${row.currency}</td><td style="font-weight:600">${fmtAmt(row.balance)}</td></tr>`).join('');
  bottomTbody.innerHTML = mumsTimeDRow
    ? `<tr><td>Mum's Time Deposit</td><td style="font-weight:600">${fmtAmt(mumsTimeDRow.balance)}</td></tr>`
    : '';
  lowerLeftTbody.innerHTML = [
    excluding ? `<tr><td>Excl. Mum's Time D (GBP)</td><td style="font-weight:600">${fmtAmt(excluding.total_gbp)}</td></tr>` : '',
    including ? `<tr><td>Incl. Mum's Time D (GBP)</td><td style="font-weight:600">${fmtAmt(including.total_gbp)}</td></tr>` : '',
  ].filter(Boolean).join('');
  lowerRightTbody.innerHTML = [
    excluding ? `<tr><td>Excl. Mum's Time D (HKD)</td><td style="font-weight:600">${fmtAmt(excluding.total_hkd)}</td></tr>` : '',
    including ? `<tr><td>Incl. Mum's Time D (HKD)</td><td style="font-weight:600">${fmtAmt(including.total_hkd)}</td></tr>` : '',
  ].filter(Boolean).join('');

  if (excluding) {
    document.getElementById('mc-fin-gbp').textContent = fmtGBP(excluding.total_gbp);
    document.getElementById('mc-fin-gbp-sub').textContent = `GBP ${fmtAmt(excluding.total_gbp)} | HKD ${fmtAmt(excluding.total_hkd)}`;
  }
  if (including) {
    document.getElementById('mc-fin-hkd').textContent = fmtGBP(including.total_gbp);
    document.getElementById('mc-fin-hkd-sub').textContent = `GBP ${fmtAmt(including.total_gbp)} | HKD ${fmtAmt(including.total_hkd)}`;
  }
  document.getElementById('mc-fin-rate').textContent = fxRates.GBP || overview?.rate_gbp_hkd || '—';

  document.getElementById('fx-rate-gbp').value = fxRates.GBP || '';
  document.getElementById('fx-rate-eur').value = fxRates.EUR || '';
  document.getElementById('fx-rate-usd').value = fxRates.USD || '';
  document.getElementById('fx-rate-jpy').value = fxRates.JPY || '';
  document.getElementById('fx-rate-cad').value = fxRates.CAD || '';
}

function clearFinanceForm() {
  editingFinanceSnapshotId = null;
  document.getElementById('fin-date').value = toISODate(todayDate());
  document.getElementById('fin-inst').value = '';
  document.getElementById('fin-acct').value = '';
  document.getElementById('fin-currency').value = 'GBP';
  document.getElementById('fin-balance').value = '';
  document.getElementById('fin-type').value = '';
  document.getElementById('fin-notes').value = '';
  setFinanceFormStatus();
  updateFinanceSaveButton();
}

function setFinanceFormStatus(message = '', type = '') {
  const statusEl = document.getElementById('finance-form-status');
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = type ? `form-status ${type}` : 'form-status';
}

function setFinanceFxStatus(message = '', type = '') {
  const statusEl = document.getElementById('finance-fx-status');
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = type ? `form-status ${type}` : 'form-status';
}

function renderFinanceHistoryStatus(message, color = '#8492a6') {
  const tbody = document.getElementById('finance-history-tbody');
  if (!tbody) return;
  financeHistoryRows = [];
  updateSortableHeaderLabels('finance-history-tbody', financeHistorySort);
  tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
}

function renderFinanceHistory(entries) {
  const tbody = document.getElementById('finance-history-tbody');
  if (!tbody) return;
  financeHistoryRows = entries;
  updateSortableHeaderLabels('finance-history-tbody', financeHistorySort);

  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:#8492a6;padding:20px">No balance history for the selected range.</td></tr>';
    return;
  }

  const derivedEntries = deriveFinanceHistoryRows(entries);
  const sortedEntries = sortFinanceRows(derivedEntries, financeHistorySort);

  tbody.innerHTML = sortedEntries.map(entry => `<tr>
    <td>${entry.snapshot_date}</td>
    <td>${entry.updated_at || '—'}</td>
    <td>${entry.institution}</td>
    <td>${entry.account}</td>
    <td>${entry.currency}</td>
    <td style="font-weight:600">${fmtAmt(entry.balance)}</td>
    <td>${entry.previous_balance === null || entry.previous_balance === undefined ? '' : fmtAmt(entry.previous_balance)}</td>
    <td>${entry.related_record_item || ''}</td>
    <td>${entry.signed_related_amount === null || entry.signed_related_amount === undefined ? '' : fmtAmt(entry.signed_related_amount)}</td>
    <td>${entry.account_type || ''}</td>
    <td>${entry.notes || ''}</td>
  </tr>`).join('');
}

function populateFinanceHistoryAccountOptions(entries) {
  const select = document.getElementById('finance-history-account-filter');
  if (!select) return;
  const selectedValue = select.value || 'All bank accounts';
  const accounts = [...new Set(entries.map(entry => `${entry.institution} / ${entry.account} / ${entry.currency}`))].sort((a, b) => a.localeCompare(b));
  select.innerHTML = ['All bank accounts', ...accounts].map(option => `<option>${option}</option>`).join('');
  select.value = ['All bank accounts', ...accounts].includes(selectedValue) ? selectedValue : 'All bank accounts';
}

function updateFinanceSaveButton() {
  const saveButton = document.getElementById('finance-save-btn');
  if (!saveButton) return;
  saveButton.innerHTML = editingFinanceSnapshotId === null
    ? '<i class="ti ti-check"></i>Save entry'
    : '<i class="ti ti-device-floppy"></i>Update entry';
}

async function saveFinanceSnapshot() {
  const payload = {
    snapshot_date: document.getElementById('fin-date').value,
    institution: document.getElementById('fin-inst').value.trim(),
    account: document.getElementById('fin-acct').value.trim(),
    currency: document.getElementById('fin-currency').value,
    balance: (document.getElementById('fin-balance').value || '0').trim(),
    account_type: document.getElementById('fin-type').value.trim() || null,
    notes: document.getElementById('fin-notes').value.trim() || null,
  };

  if (!payload.snapshot_date || !payload.institution || !payload.account || !payload.balance) {
    setFinanceFormStatus('Please complete snapshot date, institution, account, currency, and balance.', 'error');
    return;
  }

  try {
    if (editingFinanceSnapshotId === null) {
      await apiPost('/finance/snapshot', payload);
      clearFinanceForm();
      setFinanceFormStatus('Finance snapshot saved.', 'success');
    } else {
      const updatedId = editingFinanceSnapshotId;
      await apiPut(`/finance/snapshot/${editingFinanceSnapshotId}`, payload);
      clearFinanceForm();
      setFinanceFormStatus(`Snapshot #${updatedId} updated.`, 'success');
    }
    await loadFinancePage();
  } catch (error) {
    setFinanceFormStatus(`Finance snapshot save error: ${error.message}`, 'error');
  }
}

function editFinanceSnapshot(entryId) {
  const entry = financeSnapshotRows.find(row => row.id === entryId);
  if (!entry) return;
  editingFinanceSnapshotId = entryId;
  document.getElementById('fin-date').value = entry.snapshot_date || '';
  document.getElementById('fin-inst').value = entry.institution || '';
  document.getElementById('fin-acct').value = entry.account || '';
  document.getElementById('fin-currency').value = entry.currency || 'GBP';
  document.getElementById('fin-balance').value = entry.balance || '';
  document.getElementById('fin-type').value = entry.account_type || '';
  document.getElementById('fin-notes').value = entry.notes || '';
  setFinanceFormStatus(`Editing snapshot #${entryId}.`, 'success');
  updateFinanceSaveButton();
  document.getElementById('fin-inst').scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.getElementById('fin-inst').focus();
}

async function deleteFinanceSnapshot(entryId) {
  const confirmed = window.confirm(`Delete finance snapshot #${entryId}? This cannot be undone.`);
  if (!confirmed) return;

  try {
    await apiDelete(`/finance/snapshot/${entryId}`);
    if (editingFinanceSnapshotId === entryId) {
      clearFinanceForm();
    }
    setFinanceFormStatus(`Snapshot #${entryId} deleted.`, 'success');
    await loadFinancePage();
  } catch (error) {
    setFinanceFormStatus(`Finance snapshot delete error: ${error.message}`, 'error');
  }
}

// ── Transfers & exchange records ──

let currentTransferType = 'conversion';
let exchangeRecords = [];

function switchTransferType(type, btn) {
  currentTransferType = type;
  document.getElementById('xfer-conversion-form').style.display = type === 'conversion' ? '' : 'none';
  document.getElementById('xfer-transfer-form').style.display = type === 'transfer' ? '' : 'none';
  document.querySelectorAll('#xfer-type-control .seg-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('xfer-save-btn').innerHTML = type === 'conversion'
    ? '<i class="ti ti-check"></i>Save currency exchange'
    : '<i class="ti ti-check"></i>Save bank transfer';
  updateTransferRatePreview();
  setTransferFormStatus();
}

function populateTransferAccountSelects(entries) {
  const accounts = entries.map(e => ({
    label: `${e.institution} / ${e.account} / ${e.currency}`,
    institution: e.institution, account: e.account, currency: e.currency,
  }));
  const unique = [...new Map(accounts.map(a => [a.label, a])).values()].sort((a, b) => a.label.localeCompare(b.label));
  const optionsHtml = unique.map(a => `<option value="${a.label}">${a.label}</option>`).join('');

  ['xfer-from-account', 'xfer-to-account', 'xfer-t-from-account', 'xfer-t-to-account'].forEach(id => {
    const sel = document.getElementById(id);
    if (sel) sel.innerHTML = optionsHtml;
  });
}

function setTransferFormStatus(msg = '', type = '') {
  const el = document.getElementById('xfer-form-status');
  if (!el) return;
  el.textContent = msg;
  el.className = type ? `form-status ${type}` : 'form-status';
}

function updateTransferRatePreview() {
  const preview = document.getElementById('xfer-rate-preview');
  if (!preview) return;
  if (currentTransferType === 'transfer') {
    preview.textContent = '';
    return;
  }
  const fromAmt = parseFloat(document.getElementById('xfer-from-amount')?.value);
  const toAmt = parseFloat(document.getElementById('xfer-to-amount')?.value);
  if (fromAmt > 0 && toAmt > 0) {
    const rate = toAmt / fromAmt;
    preview.textContent = `Implied rate: ${rate.toFixed(6)}`;
  } else {
    preview.textContent = '';
  }
}

function clearTransferForm() {
  document.getElementById('xfer-date').value = toISODate(todayDate());
  document.getElementById('xfer-from-amount').value = '';
  document.getElementById('xfer-to-amount').value = '';
  document.getElementById('xfer-fee').value = '';
  document.getElementById('xfer-notes').value = '';
  document.getElementById('xfer-t-date').value = toISODate(todayDate());
  document.getElementById('xfer-t-amount').value = '';
  document.getElementById('xfer-t-notes').value = '';
  document.getElementById('xfer-rate-preview').textContent = '';
  setTransferFormStatus();
}

function _parseAccountLabel(label) {
  const parts = label.split(' / ');
  return { institution: parts[0], account: parts[1], currency: parts[2] || parts[1] };
}

async function saveTransferOrExchange() {
  try {
    let payload;
    if (currentTransferType === 'conversion') {
      const date = document.getElementById('xfer-date').value;
      const from = _parseAccountLabel(document.getElementById('xfer-from-account').value);
      const to = _parseAccountLabel(document.getElementById('xfer-to-account').value);
      const fromAmt = document.getElementById('xfer-from-amount').value;
      const toAmt = document.getElementById('xfer-to-amount').value;
      const fee = document.getElementById('xfer-fee').value || null;
      const notes = document.getElementById('xfer-notes').value || null;
      if (!date || !fromAmt || !toAmt) {
        setTransferFormStatus('Date, paid amount, and received amount are required.', 'error');
        return;
      }
      payload = {
        exchange_date: date,
        from_institution: from.institution, from_account: from.account, from_currency: from.currency, from_amount: fromAmt,
        to_institution: to.institution, to_account: to.account, to_currency: to.currency, to_amount: toAmt,
        fee_amount: fee, notes,
      };
    } else {
      const date = document.getElementById('xfer-t-date').value;
      const from = _parseAccountLabel(document.getElementById('xfer-t-from-account').value);
      const to = _parseAccountLabel(document.getElementById('xfer-t-to-account').value);
      const amount = document.getElementById('xfer-t-amount').value;
      const notes = document.getElementById('xfer-t-notes').value || null;
      if (!date || !amount) {
        setTransferFormStatus('Date and amount are required.', 'error');
        return;
      }
      payload = {
        exchange_date: date,
        from_institution: from.institution, from_account: from.account, from_currency: from.currency, from_amount: amount,
        to_institution: to.institution, to_account: to.account, to_currency: to.currency, to_amount: amount,
        fee_amount: null, notes,
      };
    }
    await apiPost('/exchange', payload);
    setTransferFormStatus('Saved successfully.', 'success');
    clearTransferForm();
    await loadExchangeHistory();
    await loadFinancePage();
  } catch (error) {
    setTransferFormStatus(`Error: ${error.message}`, 'error');
  }
}

async function deleteExchangeRecord(id) {
  if (!window.confirm('Delete this exchange/transfer record?')) return;
  try {
    await apiDelete(`/exchange/${id}`);
    await loadExchangeHistory();
    await loadFinancePage();
  } catch (error) {
    setTransferFormStatus(`Delete error: ${error.message}`, 'error');
  }
}

async function loadExchangeHistory() {
  const tbody = document.getElementById('xfer-history-tbody');
  const countEl = document.getElementById('xfer-history-count');
  if (!tbody) return;
  try {
    exchangeRecords = await apiGet('/exchange');
    if (countEl) countEl.textContent = `${exchangeRecords.length} record${exchangeRecords.length !== 1 ? 's' : ''}`;
    if (!exchangeRecords.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#8492a6;padding:20px">No exchange or transfer records yet.</td></tr>';
      return;
    }
    tbody.innerHTML = exchangeRecords.map(r => {
      const fromLabel = `${r.from_institution} / ${r.from_account}`;
      const toLabel = `${r.to_institution} / ${r.to_account}`;
      const isSameCurrency = r.from_currency === r.to_currency;
      const rate = isSameCurrency ? '—' : r.display_rate_value ? parseFloat(r.display_rate_value).toFixed(4) : '—';
      const fee = r.fee_amount ? fmtGBP(parseFloat(r.fee_amount)) : '—';
      return `<tr>
        <td>${formatDisplayDate(parseISODate(r.exchange_date))}</td>
        <td>${fromLabel}<div style="font-size:10px;color:#8492a6">${r.from_currency}</div></td>
        <td>${fmtAmt(parseFloat(r.from_amount), r.from_currency)}</td>
        <td>${toLabel}<div style="font-size:10px;color:#8492a6">${r.to_currency}</div></td>
        <td>${fmtAmt(parseFloat(r.to_amount), r.to_currency)}</td>
        <td>${rate}</td>
        <td>${fee}</td>
        <td>${r.notes || ''}</td>
        <td><div class="row-actions"><button class="btn-inline danger" onclick="deleteExchangeRecord(${r.id})">Delete</button></div></td>
      </tr>`;
    }).join('');
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#c0392b;padding:20px">Error loading exchange records: ${error.message}</td></tr>`;
  }
}

async function loadFinancePage() {
  renderFinanceSnapshotStatus('Loading finance snapshot…');
  try {
    const overview = await apiGet('/finance/overview');
    renderFinanceSnapshot(overview.entries || [], overview);
    populateFinanceHistoryAccountOptions(overview.entries || []);
    populateTransferAccountSelects(overview.entries || []);
    const today = todayDate();
    const monthStart = monthStartDate(today.getFullYear(), today.getMonth());
    const historyStart = document.getElementById('finance-history-start');
    const historyEnd = document.getElementById('finance-history-end');
    if (historyStart && !historyStart.value) historyStart.value = toISODate(monthStart);
    if (historyEnd && !historyEnd.value) historyEnd.value = toISODate(today);
    clearTransferForm();
    await Promise.all([loadFinanceHistory(), loadExchangeHistory()]);
  } catch (error) {
    renderFinanceSnapshotStatus(`Finance snapshot load error: ${error.message}`, '#c0392b');
    renderFinanceHistoryStatus(`Finance history load error: ${error.message}`, '#c0392b');
  }
}

function buildManualFinanceFxRatesPayload() {
  const ratesToHkd = {
    GBP: (document.getElementById('fx-rate-gbp').value || '').trim(),
    HKD: '1.0000',
    EUR: (document.getElementById('fx-rate-eur').value || '').trim(),
    USD: (document.getElementById('fx-rate-usd').value || '').trim(),
    JPY: (document.getElementById('fx-rate-jpy').value || '').trim(),
    CAD: (document.getElementById('fx-rate-cad').value || '').trim(),
  };

  for (const [currency, value] of Object.entries(ratesToHkd)) {
    const numeric = Number(value);
    if (!(numeric > 0)) {
      throw new Error(`Please enter a valid ${currency} to HKD rate.`);
    }
    ratesToHkd[currency] = numeric.toFixed(4);
  }

  return ratesToHkd;
}

async function saveManualFinanceFxRates() {
  try {
    const ratesToHkd = buildManualFinanceFxRatesPayload();
    const result = await apiPut('/finance/fx-rates', {
      rates_to_hkd: ratesToHkd,
      source: 'Manual',
    });
    const savedRates = result.rates_to_hkd || ratesToHkd;
    document.getElementById('fx-rate-gbp').value = savedRates.GBP || '';
    document.getElementById('fx-rate-eur').value = savedRates.EUR || '';
    document.getElementById('fx-rate-usd').value = savedRates.USD || '';
    document.getElementById('fx-rate-jpy').value = savedRates.JPY || '';
    document.getElementById('fx-rate-cad').value = savedRates.CAD || '';
    setFinanceFxStatus('Manual FX rates saved.', 'success');
    await loadFinancePage();
  } catch (error) {
    setFinanceFxStatus(`FX rate save error: ${error.message}`, 'error');
  }
}

async function saveFinanceFxRates() {
  try {
    const response = await fetch('https://api.frankfurter.dev/v2/rates?base=GBP&quotes=HKD,USD,EUR,CAD,JPY');
    if (!response.ok) {
      throw new Error(`Frankfurter request failed: ${response.status}`);
    }
    const payload = await response.json();
    const rates = Array.isArray(payload)
      ? Object.fromEntries(payload.map((row) => [row.quote, row.rate]))
      : (payload?.rates || {});
    const hkdPerGbp = Number(rates.HKD || 0);
    const usdPerGbp = Number(rates.USD || 0);
    const eurPerGbp = Number(rates.EUR || 0);
    const cadPerGbp = Number(rates.CAD || 0);
    const jpyPerGbp = Number(rates.JPY || 0);

    if (!(hkdPerGbp > 0 && usdPerGbp > 0 && eurPerGbp > 0 && cadPerGbp > 0 && jpyPerGbp > 0)) {
      throw new Error('Frankfurter returned incomplete FX data.');
    }

    const ratesToHkd = {
      GBP: hkdPerGbp.toFixed(4),
      HKD: '1.0000',
      USD: (hkdPerGbp / usdPerGbp).toFixed(4),
      EUR: (hkdPerGbp / eurPerGbp).toFixed(4),
      CAD: (hkdPerGbp / cadPerGbp).toFixed(4),
      JPY: (hkdPerGbp / jpyPerGbp).toFixed(4),
    };

    const result = await apiPut('/finance/fx-rates', {
      rates_to_hkd: ratesToHkd,
      source: 'Frankfurter',
    });
    const savedRates = result.rates_to_hkd || ratesToHkd;
    document.getElementById('fx-rate-gbp').value = savedRates.GBP || '';
    document.getElementById('fx-rate-eur').value = savedRates.EUR || '';
    document.getElementById('fx-rate-usd').value = savedRates.USD || '';
    document.getElementById('fx-rate-jpy').value = savedRates.JPY || '';
    document.getElementById('fx-rate-cad').value = savedRates.CAD || '';
    setFinanceFxStatus('FX rates updated from Frankfurter.', 'success');
    await loadFinancePage();
  } catch (error) {
    setFinanceFxStatus(`FX rate update error: ${error.message}`, 'error');
  }
}

async function loadFinanceHistory() {
  const startInput = document.getElementById('finance-history-start');
  const endInput = document.getElementById('finance-history-end');
  const accountSelect = document.getElementById('finance-history-account-filter');
  if (!startInput || !endInput || !accountSelect) return;

  const params = new URLSearchParams();
  if (startInput.value) params.set('start_date', startInput.value);
  if (endInput.value) params.set('end_date', endInput.value);
  if (accountSelect.value && accountSelect.value !== 'All bank accounts') {
    const [institution, account, currency] = accountSelect.value.split(' / ');
    if (institution) params.set('institution', institution);
    if (account) params.set('account', account);
    if (currency) params.set('currency', currency);
  }

  renderFinanceHistoryStatus('Loading balance history…');
  try {
    const entries = await apiGet('/finance/snapshot/history?' + params.toString());
    renderFinanceHistory(entries);
  } catch (error) {
    renderFinanceHistoryStatus(`Finance history load error: ${error.message}`, '#c0392b');
  }
}

function renderExpensesStatus(message, color = '#8492a6') {
  const tbody = document.getElementById('expense-tbody');
  if (!tbody) return;
  currentExpenseRows = [];
  updateExpenseTableSummary({ count: 0, totalGbp: 0, totalHkd: 0 });
  tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;color:${color};padding:20px">${message}</td></tr>`;
}

function setExpenseFormStatus(message = '', type = '') {
  const statusEl = document.getElementById('expense-form-status');
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = type ? `form-status ${type}` : 'form-status';
}

function updateExpenseSaveButton() {
  const saveButton = document.getElementById('expense-save-btn');
  if (!saveButton) return;
  saveButton.innerHTML = editingExpenseId === null
    ? '<i class="ti ti-check"></i>Save expense'
    : '<i class="ti ti-device-floppy"></i>Update expense';
}

function clearExpenseForm() {
  editingExpenseId = null;
  document.getElementById('exp-date').value = toISODate(todayDate());
  document.getElementById('exp-desc').value = '';
  document.getElementById('exp-group').value = 'Living';
  populateExpenseCategoryOptions(false);
  document.getElementById('exp-gbp').value = '';
  document.getElementById('exp-hkd').value = '';
  document.getElementById('exp-payment').value = '';
  document.getElementById('exp-notes').value = '';
  document.getElementById('exp-tax').checked = false;
  setExpenseFormStatus();
  updateExpenseSaveButton();
}

function buildExpensePayloadFromForm() {
  return {
    transaction_date: document.getElementById('exp-date').value,
    description: document.getElementById('exp-desc').value.trim(),
    category: document.getElementById('exp-category').value,
    group: document.getElementById('exp-group').value,
    amount_gbp: (document.getElementById('exp-gbp').value || '0').trim(),
    amount_hkd: document.getElementById('exp-hkd').value.trim() || null,
    tax_deductable: document.getElementById('exp-tax').checked,
    payment_method: document.getElementById('exp-payment').value || null,
    notes: document.getElementById('exp-notes').value.trim() || null,
  };
}

async function saveExpense() {
  const payload = buildExpensePayloadFromForm();
  if (!payload.transaction_date || !payload.description || !payload.category || !payload.amount_gbp) {
    setExpenseFormStatus('Please complete date, description, category, and amount.', 'error');
    return;
  }

  try {
    if (editingExpenseId === null) {
      await apiPost('/expenses', payload);
      clearExpenseForm();
      setExpenseFormStatus('Expense saved.', 'success');
    } else {
      await apiPut(`/expenses/${editingExpenseId}`, payload);
      const updatedExpenseId = editingExpenseId;
      clearExpenseForm();
      setExpenseFormStatus(`Expense #${updatedExpenseId} updated.`, 'success');
    }
    expenseMetadata = null;
    await loadExpensesPage(true);
  } catch (error) {
    setExpenseFormStatus(`Could not save expense: ${error.message}`, 'error');
  }
}

async function editExpense(expenseId) {
  const transaction = currentExpenseRows.find(row => row.id === expenseId)
    || await apiGet(`/expenses/${expenseId}`);
  editingExpenseId = expenseId;
  document.getElementById('exp-date').value = transaction.transaction_date;
  document.getElementById('exp-desc').value = transaction.description || '';
  document.getElementById('exp-group').value = transaction.group || 'Living';
  populateExpenseCategoryOptions(false);
  document.getElementById('exp-category').value = transaction.category || '';
  document.getElementById('exp-category-input').value = transaction.category || '';
  document.getElementById('exp-gbp').value = transaction.amount_gbp || '';
  document.getElementById('exp-hkd').value = transaction.amount_hkd || '';
  document.getElementById('exp-payment').value = transaction.payment_method || '';
  document.getElementById('exp-notes').value = transaction.notes || '';
  document.getElementById('exp-tax').checked = Boolean(transaction.tax_deductable);
  setExpenseFormStatus(`Editing expense #${expenseId}.`, 'success');
  updateExpenseSaveButton();
  document.getElementById('exp-desc').scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.getElementById('exp-desc').focus();
}

async function deleteExpense(expenseId) {
  const confirmed = window.confirm(`Delete expense #${expenseId}? This cannot be undone.`);
  if (!confirmed) return;

  try {
    await apiDelete(`/expenses/${expenseId}`);
    if (editingExpenseId === expenseId) {
      clearExpenseForm();
    }
    setExpenseFormStatus(`Expense #${expenseId} deleted.`, 'success');
    expenseMetadata = null;
    await loadExpensesPage(true);
  } catch (error) {
    setExpenseFormStatus(`Could not delete expense: ${error.message}`, 'error');
  }
}

function setCategoryManagerStatus(message = '', type = '') {
  const statusEl = document.getElementById('category-manage-status');
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = type ? `form-status ${type}` : 'form-status';
}

function addCategoryRow(groupName) {
  const groupEl = [...document.querySelectorAll('.catmgr-group')].find(el =>
    el.querySelector('.catmgr-group-name')?.textContent === groupName
  );
  if (!groupEl) return;

  const emptyMsg = groupEl.querySelector('.catmgr-empty');
  if (emptyMsg) emptyMsg.remove();

  const row = document.createElement('div');
  row.className = 'catmgr-row new-row';
  row.innerHTML = `
    <input type="text" placeholder="New category name…" id="catmgr-new-input" autofocus>
    <div class="catmgr-row-actions">
      <button class="catmgr-row-btn save" type="button" title="Save" onclick="saveNewCategory('${groupName.replace(/'/g, "\\'")}', this)"><i class="ti ti-check"></i></button>
      <button class="catmgr-row-btn danger" type="button" title="Cancel" onclick="this.closest('.catmgr-row').remove()"><i class="ti ti-x"></i></button>
    </div>`;
  groupEl.appendChild(row);

  const input = row.querySelector('input');
  input.focus();
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') saveNewCategory(groupName, row.querySelector('.save'));
    if (e.key === 'Escape') row.remove();
  });
}

async function saveNewCategory(groupName, btnEl) {
  const row = btnEl.closest('.catmgr-row');
  const input = row.querySelector('input');
  const category = normalizeText(input.value);
  if (!category) { input.focus(); return; }

  try {
    await apiPost('/categories', { group_name: groupName, category });
    await loadCategoryCatalog(true);
    populateExpenseCategoryOptions(false);
    renderCategoryManagerBody();
    setCategoryManagerStatus(`Added "${category}" to ${groupName}.`, 'success');
  } catch (error) {
    setCategoryManagerStatus(`Could not add: ${error.message}`, 'error');
  }
}

async function renameCategoryRow(categoryId) {
  const input = document.getElementById(`catmgr-name-${categoryId}`);
  const row = input?.closest('.catmgr-row');
  if (!input || !row) return;

  const newName = normalizeText(input.value);
  const original = row.dataset.original;
  if (!newName) { input.focus(); return; }
  if (newName === original) { setCategoryManagerStatus('No changes.', ''); return; }

  try {
    await apiPut(`/categories/${categoryId}`, { category: newName });
    await loadCategoryCatalog(true);
    populateExpenseCategoryOptions(false);
    renderCategoryManagerBody();
    setCategoryManagerStatus(`Renamed "${original}" → "${newName}".`, 'success');
  } catch (error) {
    setCategoryManagerStatus(`Could not rename: ${error.message}`, 'error');
  }
}

async function deleteCategoryRow(categoryId, categoryName) {
  if (!window.confirm(`Delete "${categoryName}"? Existing expenses keep their saved category text.`)) return;

  try {
    await apiDelete(`/categories/${categoryId}`);
    await loadCategoryCatalog(true);
    populateExpenseCategoryOptions(false);
    renderCategoryManagerBody();
    setCategoryManagerStatus(`Deleted "${categoryName}".`, 'success');
  } catch (error) {
    setCategoryManagerStatus(`Could not delete: ${error.message}`, 'error');
  }
}

async function loadExpensesPage(forceRefresh = false) {
  if (!expenseMetadata || forceRefresh) {
    try {
      expenseMetadata = await apiGet('/expenses/meta');
    } catch (error) {
      renderExpensesStatus(`Expense load error: ${error.message}`, '#c0392b');
      return;
    }

    populateExpenseFilterOptions();
    const latestExpenseDate = getLatestExpenseDate();
    const currentMonthStart = monthStartDate(latestExpenseDate.getFullYear(), latestExpenseDate.getMonth());
    expenseCustomPeriod = {
      start: toISODate(currentMonthStart),
      end: toISODate(latestExpenseDate),
    };
    syncExpensePeriodSelector();
  }

  await loadCategoryCatalog(forceRefresh);

  if (!expenseMetadata?.latest_transaction_date) {
    updatePeriodHint({ start: toISODate(TRACKING_START_DATE), end: toISODate(todayDate()) });
    renderExpensesTable([]);
    return;
  }

  return loadExpenses();
}

async function loadExpenses() {
  const periodSelect = document.getElementById('expense-period-filter');
  const timeframeSelect = document.getElementById('expense-timeframe-filter');
  const searchInput = document.getElementById('expense-search');
  const categorySelect = document.getElementById('expense-cat-filter');
  const groupSelect = document.getElementById('expense-group-filter');
  const paymentSelect = document.getElementById('expense-payment-filter');

  if (!periodSelect || !timeframeSelect || !searchInput || !categorySelect || !groupSelect || !paymentSelect) {
    return;
  }

  expensePeriodMode = periodSelect.value;
  if (!expensePeriodOptions.length) {
    syncExpensePeriodSelector();
  }
  expenseSelectedPeriodKeys[expensePeriodMode] = timeframeSelect.value;
  const dates = getExpensePeriodDates();

  const searchValue = searchInput.value.trim();
  const selectedCategory = categorySelect.value;
  const selectedGroup = groupSelect.value;
  const selectedPaymentMethod = paymentSelect.value;

  updatePeriodHint(dates);
  renderExpensesStatus('Loading expenses…');

  const params = new URLSearchParams({
    start_date: dates.start,
    end_date: dates.end,
  });
  if (selectedCategory !== 'All categories') params.set('category', selectedCategory);
  if (selectedGroup !== 'All groups') params.set('group', selectedGroup);
  if (selectedPaymentMethod !== 'All payment methods') params.set('payment_method', selectedPaymentMethod);
  if (searchValue) params.set('search', searchValue);

  try {
    const transactions = await apiGet('/expenses?' + params.toString());
    renderExpensesTable(transactions);
  } catch (error) {
    renderExpensesStatus(`Expense load error: ${error.message}`, '#c0392b');
  }
}

async function saveIncome() {
  const payload = buildIncomePayloadFromForm();
  if (!payload.income_date || !payload.description || !payload.source || !payload.gross_amount) {
    setIncomeFormStatus('Please complete date, description, source, and amount.', 'error');
    return;
  }

  try {
    if (editingIncomeId === null) {
      await apiPost('/income', payload);
      clearIncomeForm();
      setIncomeFormStatus('Income saved.', 'success');
    } else {
      const updatedIncomeId = editingIncomeId;
      await apiPut(`/income/${editingIncomeId}`, payload);
      clearIncomeForm();
      setIncomeFormStatus(`Income #${updatedIncomeId} updated.`, 'success');
    }
    incomeMetadata = null;
    await loadIncomePage(true);
  } catch (error) {
    setIncomeFormStatus(`Could not save income: ${error.message}`, 'error');
  }
}

async function editIncome(incomeId) {
  const income = currentIncomeRows.find(row => row.id === incomeId);
  if (!income) return;
  editingIncomeId = incomeId;
  document.getElementById('inc-date').value = income.income_date;
  document.getElementById('inc-desc').value = income.description || '';
  document.getElementById('inc-source').value = income.source || '';
  document.getElementById('inc-currency').value = income.currency || 'GBP';
  document.getElementById('inc-amount').value = income.gross_amount || '';
  document.getElementById('inc-gbp').value = income.gross_amount_gbp || '';
  document.getElementById('inc-fx').value = income.fx_rate_to_gbp || '';
  document.getElementById('inc-account').value = income.payment_account || '';
  document.getElementById('inc-taxable').checked = Boolean(income.is_taxable);
  setIncomeFormStatus(`Editing income #${incomeId}.`, 'success');
  updateIncomeSaveButton();
  document.getElementById('inc-desc').scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.getElementById('inc-desc').focus();
}

async function deleteIncome(incomeId) {
  const confirmed = window.confirm(`Delete income #${incomeId}? This cannot be undone.`);
  if (!confirmed) return;

  try {
    await apiDelete(`/income/${incomeId}`);
    if (editingIncomeId === incomeId) {
      clearIncomeForm();
    }
    setIncomeFormStatus(`Income #${incomeId} deleted.`, 'success');
    incomeMetadata = null;
    await loadIncomePage(true);
  } catch (error) {
    setIncomeFormStatus(`Could not delete income: ${error.message}`, 'error');
  }
}

async function loadIncomePage(forceRefresh = false) {
  if (!incomeMetadata || forceRefresh) {
    try {
      incomeMetadata = await apiGet('/income/meta');
    } catch (error) {
      renderIncomeStatus(`Income load error: ${error.message}`, '#c0392b');
      return;
    }

    populateIncomeFilterOptions();
    const latestIncomeDate = getLatestIncomeDate();
    const currentMonthStart = monthStartDate(latestIncomeDate.getFullYear(), latestIncomeDate.getMonth());
    incomeCustomPeriod = {
      start: toISODate(currentMonthStart),
      end: toISODate(latestIncomeDate),
    };
    syncIncomePeriodSelector();
  }

  if (!incomeMetadata?.latest_income_date) {
    updatePeriodHint({ start: toISODate(TRACKING_START_DATE), end: toISODate(todayDate()) });
    renderIncomeTable([]);
    return;
  }

  return loadIncome();
}

async function loadIncome() {
  const periodSelect = document.getElementById('income-period-filter');
  const timeframeSelect = document.getElementById('income-timeframe-filter');
  const searchInput = document.getElementById('income-search');
  const sourceSelect = document.getElementById('income-source-filter');
  const currencySelect = document.getElementById('income-currency-filter');
  const accountSelect = document.getElementById('income-account-filter');
  const taxableSelect = document.getElementById('income-taxable-filter');

  if (!periodSelect || !timeframeSelect || !searchInput || !sourceSelect || !currencySelect || !accountSelect || !taxableSelect) {
    return;
  }

  incomePeriodMode = periodSelect.value;
  if (!incomePeriodOptions.length) {
    syncIncomePeriodSelector();
  }
  incomeSelectedPeriodKeys[incomePeriodMode] = timeframeSelect.value;
  const dates = getIncomePeriodDates();
  updatePeriodHint(dates);
  renderIncomeStatus('Loading income…');

  const params = new URLSearchParams({
    start_date: dates.start,
    end_date: dates.end,
  });
  if (searchInput.value.trim()) params.set('search', searchInput.value.trim());
  if (sourceSelect.value !== 'All sources') params.set('source', sourceSelect.value);
  if (currencySelect.value !== 'All currencies') params.set('currency', currencySelect.value);
  if (accountSelect.value !== 'All accounts') params.set('payment_account', accountSelect.value);
  if (taxableSelect.value !== 'All income') params.set('taxable', taxableSelect.value);

  try {
    const [incomes, taxEntries] = await Promise.all([
      apiGet('/income?' + params.toString()),
      apiGet('/tax-due'),
    ]);
    const filteredTaxEntries = taxEntries.filter(entry => entry.tax_date >= dates.start && entry.tax_date <= dates.end);
    renderIncomeTable(incomes);
    updateIncomeMetrics(incomes, filteredTaxEntries, dates);
  } catch (error) {
    renderIncomeStatus(`Income load error: ${error.message}`, '#c0392b');
  }
}

async function saveTaxDue() {
  const payload = buildTaxPayloadFromForm();
  if (!payload.tax_date || !payload.tax_period || !payload.amount_gbp) {
    setTaxFormStatus('Please complete date, tax period, and amount.', 'error');
    return;
  }

  try {
    if (editingTaxId === null) {
      await apiPost('/tax-due', payload);
      clearTaxForm();
      setTaxFormStatus('Tax due saved.', 'success');
    } else {
      const updatedTaxId = editingTaxId;
      await apiPut(`/tax-due/${editingTaxId}`, payload);
      clearTaxForm();
      setTaxFormStatus(`Tax due #${updatedTaxId} updated.`, 'success');
    }
    taxMetadata = null;
    await loadTaxPage(true);
  } catch (error) {
    setTaxFormStatus(`Could not save tax due: ${error.message}`, 'error');
  }
}

function editTaxDue(entryId) {
  const entry = currentTaxRows.find(row => row.id === entryId);
  if (!entry) return;
  editingTaxId = entryId;
  document.getElementById('tax-date').value = entry.tax_date;
  document.getElementById('tax-period').value = entry.tax_period || '';
  document.getElementById('tax-amount').value = entry.amount_gbp || '';
  document.getElementById('tax-notes').value = entry.notes || '';
  setTaxFormStatus(`Editing tax due #${entryId}.`, 'success');
  updateTaxSaveButton();
  document.getElementById('tax-period').scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.getElementById('tax-period').focus();
}

async function deleteTaxDue(entryId) {
  const confirmed = window.confirm(`Delete tax due #${entryId}? This cannot be undone.`);
  if (!confirmed) return;

  try {
    await apiDelete(`/tax-due/${entryId}`);
    if (editingTaxId === entryId) {
      clearTaxForm();
    }
    setTaxFormStatus(`Tax due #${entryId} deleted.`, 'success');
    taxMetadata = null;
    await loadTaxPage(true);
  } catch (error) {
    setTaxFormStatus(`Could not delete tax due: ${error.message}`, 'error');
  }
}

async function loadTaxPage(forceRefresh = false) {
  if (!taxMetadata || forceRefresh) {
    try {
      taxMetadata = await apiGet('/tax-due/meta');
    } catch (error) {
      renderTaxStatus(`Tax load error: ${error.message}`, '#c0392b');
      return;
    }

    populateTaxFilterOptions();
    const latestTaxDate = getLatestTaxDate();
    taxCustomPeriod = {
      start: TAX_DEFAULT_START_DATE,
      end: toISODate(latestTaxDate),
    };
    syncTaxPeriodSelector();
  }

  if (!taxMetadata?.latest_tax_date) {
    updatePeriodHint({ start: toISODate(TRACKING_START_DATE), end: toISODate(todayDate()) });
    renderTaxTable([]);
    return;
  }

  return loadTaxDue();
}

async function loadTaxDue() {
  const periodSelect = document.getElementById('tax-period-filter');
  const timeframeSelect = document.getElementById('tax-timeframe-filter');
  const searchInput = document.getElementById('tax-search');
  const taxPeriodSelect = document.getElementById('tax-period-name-filter');

  if (!periodSelect || !timeframeSelect || !searchInput || !taxPeriodSelect) {
    return;
  }

  taxPeriodMode = periodSelect.value;
  if (!taxPeriodOptions.length) {
    syncTaxPeriodSelector();
  }
  taxSelectedPeriodKeys[taxPeriodMode] = timeframeSelect.value;
  const dates = getTaxPeriodDates();
  updatePeriodHint(dates);
  renderTaxStatus('Loading tax due…');

  const params = new URLSearchParams({
    start_date: dates.start,
    end_date: dates.end,
  });
  if (searchInput.value.trim()) params.set('search', searchInput.value.trim());
  if (taxPeriodSelect.value !== 'All periods') params.set('tax_period', taxPeriodSelect.value);

  try {
    const entries = await apiGet('/tax-due?' + params.toString());
    renderTaxTable(entries);
    updateTaxMetrics(entries, dates);
  } catch (error) {
    renderTaxStatus(`Tax load error: ${error.message}`, '#c0392b');
  }
}

function updatePeriodHint(dates) {
  document.getElementById('period-hint').textContent = formatDateRangeText(dates.start, dates.end);
}

function nav(id, el) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav').forEach(n => n.classList.remove('active'));
  document.getElementById('sec-' + id).classList.add('active');
  if (el) el.classList.add('active');

  const p = pages[id];
  document.getElementById('page-title').textContent = p.title;
  document.getElementById('top-btn-label').textContent = p.action;
  document.getElementById('top-btn').style.display = p.action ? 'flex' : 'none';
  document.getElementById('period-pills').style.display = p.pills ? 'flex' : 'none';

  currentPage = id;
  syncPeriodSelector();
  loadPageData(id);
}

function setPeriod(el, mode) {
  document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  currentPeriodMode = mode;
  syncPeriodSelector();
  loadPageData(currentPage);
}

function loadPageData(page) {
  if (page === 'dashboard') {
    const dates = getPeriodDates(currentPeriodMode);
    updatePeriodHint(dates);
    loadDashboard(currentPeriodMode, dates.start, dates.end);
    return;
  }
  if (page === 'expenses') {
    loadExpensesPage();
    return;
  }
  if (page === 'income') {
    loadIncomePage();
    return;
  }
  if (page === 'tax') {
    loadTaxPage();
    return;
  }
  if (page === 'finance') {
    loadFinancePage();
    return;
  }
  if (page === 'recurring') {
    loadRecurringPage();
    return;
  }
  if (page === 'reports') {
    loadReports();
  }
}

function syncCustomPeriodFromInputs() {
  const startInput = document.getElementById('custom-start-date');
  const endInput = document.getElementById('custom-end-date');
  if (!startInput || !endInput) return;

  let start = startInput.value || toISODate(TRACKING_START_DATE);
  let end = endInput.value || toISODate(todayDate());

  if (start < toISODate(TRACKING_START_DATE)) start = toISODate(TRACKING_START_DATE);
  if (end > toISODate(todayDate())) end = toISODate(todayDate());
  if (start > end) {
    if (document.activeElement === startInput) {
      end = start;
      endInput.value = end;
    } else {
      start = end;
      startInput.value = start;
    }
  }

  customPeriod = { start, end };
  startInput.value = start;
  endInput.value = end;
}

function getLatestReportDate() {
  if (!expenseMetadata?.latest_transaction_date) return todayDate();
  return parseISODate(expenseMetadata.latest_transaction_date);
}

function getReportDates() {
  const periodSelect = document.getElementById('report-period-filter');
  const mode = periodSelect?.value || 'Financial year';
  const latestDate = getLatestReportDate();

  if (mode === 'Month') {
    return {
      start: toISODate(monthStartDate(latestDate.getFullYear(), latestDate.getMonth())),
      end: toISODate(latestDate),
    };
  }

  if (mode === 'Calendar year') {
    return {
      start: `${latestDate.getFullYear()}-01-01`,
      end: toISODate(latestDate),
    };
  }

  return {
    start: toISODate(getFinancialYearStart(latestDate)),
    end: toISODate(latestDate),
  };
}

function populateReportFilterOptions() {
  const groupSelect = document.getElementById('report-group-filter');
  const categorySelect = document.getElementById('report-cat-filter');
  if (!groupSelect || !categorySelect) return;

  const currentGroup = groupSelect.value || 'All groups';
  const currentCategory = categorySelect.value || 'All categories';
  const groups = ['All groups', ...(expenseMetadata?.groups || [])];
  const categories = ['All categories', ...(expenseMetadata?.categories || [])];

  groupSelect.innerHTML = groups.map(option => `<option>${option}</option>`).join('');
  categorySelect.innerHTML = categories.map(option => `<option>${option}</option>`).join('');

  groupSelect.value = groups.includes(currentGroup) ? currentGroup : 'All groups';
  categorySelect.value = categories.includes(currentCategory) ? currentCategory : 'All categories';
}

function buildReportQueryParams() {
  const dates = getReportDates();
  const params = new URLSearchParams({
    start_date: dates.start,
    end_date: dates.end,
  });
  const group = document.getElementById('report-group-filter')?.value || 'All groups';
  const category = document.getElementById('report-cat-filter')?.value || 'All categories';

  if (group !== 'All groups') params.set('group', group);
  if (category !== 'All categories') params.set('category', category);

  return { dates, params };
}

function setReportMetricValue(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderReportsLoading(message = 'Loading…') {
  setReportMetricValue('mc-rpt-gbp', '—');
  setReportMetricValue('mc-rpt-hkd', '—');
  setReportMetricValue('mc-rpt-count', '—');
  document.getElementById('cat-table-body').innerHTML = `<tr><td colspan="3" style="text-align:center;color:#8492a6;padding:12px">${message}</td></tr>`;
  document.getElementById('liv-table-body').innerHTML = `<tr><td colspan="3" style="text-align:center;color:#8492a6;padding:12px">${message}</td></tr>`;
  document.getElementById('largest-tbody').innerHTML = `<tr><td colspan="6" style="text-align:center;color:#8492a6;padding:12px">${message}</td></tr>`;
  document.getElementById('trend-hint').textContent = message;
}

function renderReportsError(message) {
  renderReportsLoading(message);
}

function renderReportCategoryTable(bodyId, rows, currency) {
  const tbody = document.getElementById(bodyId);
  if (!tbody) return;

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#8492a6;padding:12px">No data for this selection.</td></tr>';
    return;
  }

  const key = currency === 'HKD' ? 'amount_hkd' : 'amount_gbp';
  const total = rows.reduce((sum, row) => sum + (parseFloat(row[key]) || 0), 0);
  tbody.innerHTML = rows.map(row => {
    const amount = parseFloat(row[key]) || 0;
    const percentage = total > 0 ? ((amount / total) * 100).toFixed(1) : '0.0';
    const label = row.category || 'Uncategorised';
    return `<tr>
      <td>${label}</td>
      <td>${currency === 'HKD' ? fmtAmt(amount) : fmtGBP(amount)}</td>
      <td>${percentage}%</td>
    </tr>`;
  }).join('');
}

function renderCategoryChart(rows) {
  const key = reportCurrency === 'HKD' ? 'amount_hkd' : 'amount_gbp';
  const labels = rows.map(row => row.category || 'Uncategorised');
  const amounts = rows.map(row => parseFloat(row[key]) || 0);
  const colors = rows.map(row => getCatColor(row.category));
  const barWrap = document.getElementById('cat-bar-wrap');
  const pieWrap = document.getElementById('cat-pie-wrap');
  const canvas = document.getElementById(reportCategoryChartType === 'pie' ? 'cat-pie' : 'hbar');

  barWrap.style.display = reportCategoryChartType === 'bar' ? '' : 'none';
  pieWrap.style.display = reportCategoryChartType === 'pie' ? '' : 'none';
  if (reportCategoryChart) reportCategoryChart.destroy();
  if (!labels.length) return;

  reportCategoryChart = new Chart(canvas, {
    type: reportCategoryChartType === 'pie' ? 'pie' : 'bar',
    data: {
      labels,
      datasets: [{
        data: amounts,
        backgroundColor: colors,
        borderWidth: reportCategoryChartType === 'pie' ? 1 : 0,
        borderColor: '#fff',
        borderRadius: reportCategoryChartType === 'bar' ? 6 : 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: reportCategoryChartType === 'bar' ? 'y' : 'x',
      plugins: { legend: { display: reportCategoryChartType === 'pie', position: 'right' } },
      scales: reportCategoryChartType === 'bar'
        ? {
            x: { grid: { color: '#f0f1f5' }, ticks: { callback: v => reportCurrency === 'HKD' ? `${Math.round(v)}` : `£${Math.round(v)}` } },
            y: { grid: { display: false } },
          }
        : {},
    },
  });
}

function renderLivingChart(rows) {
  const labels = rows.map(row => row.category || 'Other');
  const amounts = rows.map(row => parseFloat(row.amount_gbp) || 0);
  const colors = rows.map(row => getCatColor(row.category));
  const barWrap = document.getElementById('liv-bar-wrap');
  const pieWrap = document.getElementById('liv-pie-wrap');
  const canvas = document.getElementById(reportLivingChartType === 'pie' ? 'liv-pie' : 'living-bar');

  barWrap.style.display = reportLivingChartType === 'bar' ? '' : 'none';
  pieWrap.style.display = reportLivingChartType === 'pie' ? '' : 'none';
  if (reportLivingChart) reportLivingChart.destroy();
  if (!labels.length) return;

  reportLivingChart = new Chart(canvas, {
    type: reportLivingChartType === 'pie' ? 'pie' : 'bar',
    data: {
      labels,
      datasets: [{
        data: amounts,
        backgroundColor: colors,
        borderWidth: reportLivingChartType === 'pie' ? 1 : 0,
        borderColor: '#fff',
        borderRadius: reportLivingChartType === 'bar' ? 6 : 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: reportLivingChartType === 'bar' ? 'y' : 'x',
      plugins: { legend: { display: reportLivingChartType === 'pie', position: 'right' } },
      scales: reportLivingChartType === 'bar'
        ? {
            x: { grid: { color: '#f0f1f5' }, ticks: { callback: v => `£${Math.round(v)}` } },
            y: { grid: { display: false } },
          }
        : {},
    },
  });
}

function renderTrendChart(rows) {
  const canvas = document.getElementById('trend');
  if (reportTrendChart) reportTrendChart.destroy();

  const labels = rows.map(row => row.month);
  const amounts = rows.map(row => parseFloat(row.amount_gbp) || 0);
  document.getElementById('trend-hint').textContent = rows.length
    ? 'Monthly expense total over time.'
    : 'No trend data for this selection.';
  document.getElementById('trend-legend').innerHTML = rows.length
    ? `<span class="chip" style="background:${hexToRgba('#5B6C9E', 0.14)};border-color:${hexToRgba('#5B6C9E', 0.22)};color:#5B6C9E">GBP expenses</span>`
    : '';

  if (!labels.length) return;

  reportTrendChart = new Chart(canvas, {
    type: reportTrendChartType,
    data: {
      labels,
      datasets: [{
        label: 'Expenses',
        data: amounts,
        borderColor: '#5B6C9E',
        backgroundColor: hexToRgba('#5B6C9E', 0.2),
        fill: reportTrendChartType === 'line',
        tension: 0.3,
        borderRadius: reportTrendChartType === 'bar' ? 6 : 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: '#f0f1f5' }, ticks: { callback: v => `£${Math.round(v)}` } },
      },
    },
  });
}

function renderLargestExpenses(rows) {
  const tbody = document.getElementById('largest-tbody');
  if (!tbody) return;

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8492a6;padding:12px">No expenses match the selected report filters.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(row => `<tr>
    <td>${row.date}</td>
    <td>${row.description}</td>
    <td>${row.category}</td>
    <td>${row.group}</td>
    <td>${fmtGBP(row.amount_gbp)}</td>
    <td>${row.amount_hkd ? fmtAmt(row.amount_hkd) : '—'}</td>
  </tr>`).join('');
}

function renderReports(data, dates) {
  currentReportsData = data;
  updatePeriodHint(dates);
  setReportMetricValue('mc-rpt-gbp', fmtGBP(data.summary.total_gbp));
  setReportMetricValue('mc-rpt-hkd', fmtAmt(data.summary.total_hkd));
  setReportMetricValue('mc-rpt-count', String(data.summary.transaction_count));
  renderReportCategoryTable('cat-table-body', data.categorySpending, reportCurrency);
  renderReportCategoryTable('liv-table-body', data.livingClassification, 'GBP');
  renderCategoryChart(data.categorySpending);
  renderLivingChart(data.livingClassification);
  renderTrendChart(data.monthlyTrend);
  renderLargestExpenses(data.largestExpenses);
}

async function loadReports() {
  if (!expenseMetadata) {
    try {
      expenseMetadata = await apiGet('/expenses/meta');
    } catch (error) {
      renderReportsError(`Report load error: ${error.message}`);
      return;
    }
  }

  populateReportFilterOptions();
  const { dates, params } = buildReportQueryParams();
  renderReportsLoading('Loading reports…');

  try {
    const [summary, categorySpending, livingClassification, monthlyTrend, largestExpenses] = await Promise.all([
      apiGet(`/reports/summary?${params}`),
      apiGet(`/reports/category-spending?${params}`),
      apiGet(`/reports/living-classification?${params}`),
      apiGet(`/reports/monthly-trend?${params}`),
      apiGet(`/reports/largest-expenses?${params}`),
    ]);

    renderReports({
      summary,
      categorySpending,
      livingClassification,
      monthlyTrend,
      largestExpenses,
    }, dates);
  } catch (error) {
    renderReportsError(`Report load error: ${error.message}`);
  }
}

function switchCatType(type, button) {
  reportCategoryChartType = type;
  button.closest('.seg-control')?.querySelectorAll('.seg-btn').forEach(btn => btn.classList.remove('active'));
  button.classList.add('active');
  if (currentReportsData) renderCategoryChart(currentReportsData.categorySpending);
}

function setCurrency(currency, button) {
  reportCurrency = currency;
  button.closest('.seg-control')?.querySelectorAll('.seg-btn').forEach(btn => btn.classList.remove('active'));
  button.classList.add('active');
  if (currentReportsData) {
    renderReportCategoryTable('cat-table-body', currentReportsData.categorySpending, reportCurrency);
    renderCategoryChart(currentReportsData.categorySpending);
  }
}

function switchLivType(type, button) {
  reportLivingChartType = type;
  button.closest('.seg-control')?.querySelectorAll('.seg-btn').forEach(btn => btn.classList.remove('active'));
  button.classList.add('active');
  if (currentReportsData) renderLivingChart(currentReportsData.livingClassification);
}

function switchTrend(type, button) {
  reportTrendChartType = type;
  button.closest('.seg-control')?.querySelectorAll('.seg-btn').forEach(btn => btn.classList.remove('active'));
  button.classList.add('active');
  if (currentReportsData) renderTrendChart(currentReportsData.monthlyTrend);
}

// Initialize
// ── Recurring page ──

const CATEGORY_ICONS = {
  'Housing': { icon: 'ti-home-2', bg: '#FEF0E6', color: '#C4590A' },
  'Rent': { icon: 'ti-home-2', bg: '#FEF0E6', color: '#C4590A' },
  'Subscriptions': { icon: 'ti-device-tv', bg: '#EDE9FE', color: '#6D28D9' },
  'Bills': { icon: 'ti-bolt', bg: '#FEF9C3', color: '#A16207' },
  'Groceries': { icon: 'ti-shopping-cart', bg: '#ECFDF5', color: '#047857' },
  'Transport': { icon: 'ti-car', bg: '#DBEAFE', color: '#1D4ED8' },
  'Food': { icon: 'ti-tools-kitchen-2', bg: '#FEF0E6', color: '#C4590A' },
  'Insurance': { icon: 'ti-shield-check', bg: '#FEF0E6', color: '#C4590A' },
  'Car Related: Annual': { icon: 'ti-car', bg: '#FEF0E6', color: '#C4590A' },
  'Car Related: Fuel': { icon: 'ti-gas-station', bg: '#DBEAFE', color: '#1D4ED8' },
  'Healthcare': { icon: 'ti-heart-plus', bg: '#FCE7F3', color: '#BE185D' },
};
const DEFAULT_ICON = { icon: 'ti-circle', bg: '#F1F5F9', color: '#64748B' };

function getRecurringIcon(category) {
  return CATEGORY_ICONS[category] || DEFAULT_ICON;
}

function ordinalDay(n) {
  const s = ['th','st','nd','rd'], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

let recurringExpenses = [];
let recurringIncomes = [];
let editingRecExpenseId = null;
let editingRecIncomeId = null;

async function loadRecurringPage() {
  try {
    if (!expenseMetadata) {
      try { expenseMetadata = await apiGet('/expenses/meta'); } catch {}
    }
    await loadCategoryCatalog();
    const [expenses, incomes] = await Promise.all([
      apiGet('/recurring/expenses'),
      apiGet('/recurring/income'),
    ]);
    recurringExpenses = expenses;
    recurringIncomes = incomes;
    renderRecurringMetrics();
    renderRecurringExpenseGrid();
    renderRecurringIncomeGrid();
    populateRecurringCategorySelect();
  } catch (error) {
    console.error('Failed to load recurring page:', error);
  }
}

function renderRecurringMetrics() {
  const activeExpenses = recurringExpenses.filter(e => e.is_active);
  const activeIncomes = recurringIncomes.filter(i => i.is_active);
  const totalExpense = activeExpenses.reduce((s, e) => s + parseFloat(e.amount_gbp || 0), 0);
  const totalIncome = activeIncomes.reduce((s, i) => s + parseFloat(i.gross_amount || i.amount_gbp || 0), 0);

  document.getElementById('mc-rec-expense').textContent = fmtGBP(totalExpense);
  document.getElementById('mc-rec-income').textContent =
    activeIncomes.some(i => i.currency && i.currency !== 'GBP')
      ? fmtAmt(totalIncome, activeIncomes[0]?.currency || 'GBP')
      : fmtGBP(totalIncome);
  document.getElementById('mc-rec-count').textContent = activeExpenses.length + activeIncomes.length;
  document.getElementById('mc-rec-count-sub').textContent =
    `${recurringExpenses.length} expense${recurringExpenses.length !== 1 ? 's' : ''} · ${recurringIncomes.length} income`;
}

function renderRecurringExpenseGrid() {
  const grid = document.getElementById('rec-expense-grid');
  if (!grid) return;

  if (!recurringExpenses.length) {
    grid.innerHTML = '<div style="grid-column:1/-1;font-size:12px;color:#8492a6">No recurring expenses yet.</div>';
    return;
  }

  grid.innerHTML = recurringExpenses.map(e => {
    const ic = getRecurringIcon(e.category);
    const statusDot = e.is_active ? '<span class="dot-green"></span> Active' : '<span class="dot-amber"></span> Paused';
    return `<div class="rec-card" data-id="${e.id}">
      <div class="rec-icon" style="background:${ic.bg}"><i class="ti ${ic.icon}" style="color:${ic.color}"></i></div>
      <div class="rec-info">
        <div class="rec-name">${e.description}</div>
        <div class="rec-sub">${ordinalDay(e.day_of_month)} · ${e.category} · ${statusDot}</div>
      </div>
      <div class="rec-amt">
        <div class="rec-amt-val">${fmtGBP(parseFloat(e.amount_gbp))}</div>
        <div class="rec-amt-freq">/month</div>
      </div>
      <div class="rec-card-actions">
        <button class="catmgr-row-btn" title="Edit" onclick="editRecExpense(${e.id})"><i class="ti ti-pencil"></i></button>
        <button class="catmgr-row-btn danger" title="Toggle" onclick="toggleRecExpense(${e.id}, ${!e.is_active})"><i class="ti ${e.is_active ? 'ti-player-pause' : 'ti-player-play'}"></i></button>
      </div>
    </div>`;
  }).join('');
}

function renderRecurringIncomeGrid() {
  const grid = document.getElementById('rec-income-grid');
  if (!grid) return;

  if (!recurringIncomes.length) {
    grid.innerHTML = '<div style="grid-column:1/-1;font-size:12px;color:#8492a6">No recurring income yet.</div>';
    return;
  }

  grid.innerHTML = recurringIncomes.map(i => {
    const ic = { icon: 'ti-coins', bg: '#ECFDF5', color: '#047857' };
    const statusDot = i.is_active ? '<span class="dot-green"></span> Active' : '<span class="dot-amber"></span> Paused';
    const amt = i.currency === 'GBP' ? fmtGBP(parseFloat(i.gross_amount)) : fmtAmt(parseFloat(i.gross_amount), i.currency);
    return `<div class="rec-card" data-id="${i.id}">
      <div class="rec-icon" style="background:${ic.bg}"><i class="ti ${ic.icon}" style="color:${ic.color}"></i></div>
      <div class="rec-info">
        <div class="rec-name">${i.description}</div>
        <div class="rec-sub">${ordinalDay(i.day_of_month)} · ${i.source} · ${i.currency} · ${statusDot}</div>
      </div>
      <div class="rec-amt">
        <div class="rec-amt-val">${amt}</div>
        <div class="rec-amt-freq">/month</div>
      </div>
      <div class="rec-card-actions">
        <button class="catmgr-row-btn" title="Edit" onclick="editRecIncome(${i.id})"><i class="ti ti-pencil"></i></button>
        <button class="catmgr-row-btn danger" title="Toggle" onclick="toggleRecIncome(${i.id}, ${!i.is_active})"><i class="ti ${i.is_active ? 'ti-player-pause' : 'ti-player-play'}"></i></button>
      </div>
    </div>`;
  }).join('');
}

function populateRecurringCategorySelect() {
  const sel = document.getElementById('rec-category');
  if (!sel) return;
  const catalogCats = categoryCatalog.map(e => e.category).filter(Boolean);
  const metaCats = expenseMetadata?.categories || [];
  const cats = [...new Set([...catalogCats, ...metaCats])].sort();
  const current = sel.value;
  sel.innerHTML = cats.map(c => `<option>${c}</option>`).join('');
  if (current && cats.includes(current)) sel.value = current;
}

function clearRecurringExpenseForm() {
  editingRecExpenseId = null;
  document.getElementById('rec-desc').value = '';
  document.getElementById('rec-category').value = '';
  document.getElementById('rec-amount').value = '';
  document.getElementById('rec-day').value = '1';
  document.getElementById('rec-start').value = toISODate(todayDate());
  document.getElementById('rec-end').value = '';
  setRecExpFormStatus();
  updateRecExpSaveButton();
}

function clearRecurringIncomeForm() {
  editingRecIncomeId = null;
  document.getElementById('rec-inc-desc').value = '';
  document.getElementById('rec-inc-source').value = '';
  document.getElementById('rec-inc-currency').value = 'GBP';
  document.getElementById('rec-inc-amount').value = '';
  document.getElementById('rec-inc-day').value = '1';
  document.getElementById('rec-inc-account').value = '';
  document.getElementById('rec-inc-start').value = toISODate(todayDate());
  document.getElementById('rec-inc-end').value = '';
  setRecIncFormStatus();
  updateRecIncSaveButton();
}

function clearRecurringForm() {
  clearRecurringExpenseForm();
  clearRecurringIncomeForm();
}

function setRecExpFormStatus(msg = '', type = '') {
  const el = document.getElementById('rec-exp-form-status');
  if (!el) return;
  el.textContent = msg;
  el.className = type ? `form-status ${type}` : 'form-status';
}

function setRecIncFormStatus(msg = '', type = '') {
  const el = document.getElementById('rec-inc-form-status');
  if (!el) return;
  el.textContent = msg;
  el.className = type ? `form-status ${type}` : 'form-status';
}

function updateRecExpSaveButton() {
  const btn = document.getElementById('rec-exp-save-btn');
  if (!btn) return;
  btn.innerHTML = editingRecExpenseId
    ? '<i class="ti ti-device-floppy"></i>Update template'
    : '<i class="ti ti-check"></i>Create template';
}

function updateRecIncSaveButton() {
  const btn = document.getElementById('rec-inc-save-btn');
  if (!btn) return;
  btn.innerHTML = editingRecIncomeId
    ? '<i class="ti ti-device-floppy"></i>Update template'
    : '<i class="ti ti-check"></i>Create template';
}

async function saveRecurringExpense() {
  const desc = document.getElementById('rec-desc').value.trim();
  const category = document.getElementById('rec-category').value;
  const amount = document.getElementById('rec-amount').value;
  const day = document.getElementById('rec-day').value;
  const startDate = document.getElementById('rec-start').value;
  const endDate = document.getElementById('rec-end').value || null;

  if (!desc || !amount) {
    setRecExpFormStatus('Description and amount are required.', 'error');
    return;
  }

  const payload = {
    description: desc, category,
    amount_gbp: amount, day_of_month: parseInt(day) || 1,
    start_date: startDate, end_date: endDate,
    is_active: true, tax_deductable: false, payment_method: '', notes: '',
  };

  try {
    if (editingRecExpenseId) {
      await apiPut(`/recurring/expenses/${editingRecExpenseId}`, payload);
      setRecExpFormStatus('Template updated.', 'success');
    } else {
      await apiPost('/recurring/expenses', payload);
      setRecExpFormStatus('Template created.', 'success');
    }
    clearRecurringExpenseForm();
    await loadRecurringPage();
  } catch (error) {
    setRecExpFormStatus(`Error: ${error.message}`, 'error');
  }
}

async function saveRecurringIncome() {
  const desc = document.getElementById('rec-inc-desc').value.trim();
  const source = document.getElementById('rec-inc-source').value.trim();
  const currency = document.getElementById('rec-inc-currency').value;
  const amount = document.getElementById('rec-inc-amount').value;
  const day = document.getElementById('rec-inc-day').value;
  const account = document.getElementById('rec-inc-account').value || null;
  const startDate = document.getElementById('rec-inc-start').value;
  const endDate = document.getElementById('rec-inc-end').value || null;

  if (!desc || !amount || !source) {
    setRecIncFormStatus('Description, source, and amount are required.', 'error');
    return;
  }

  const payload = {
    description: desc, source, currency,
    gross_amount: amount, day_of_month: parseInt(day) || 1,
    payment_account: account, start_date: startDate, end_date: endDate,
    is_active: true, is_taxable: true, notes: '',
  };

  try {
    if (editingRecIncomeId) {
      await apiPut(`/recurring/income/${editingRecIncomeId}`, payload);
      setRecIncFormStatus('Template updated.', 'success');
    } else {
      await apiPost('/recurring/income', payload);
      setRecIncFormStatus('Template created.', 'success');
    }
    clearRecurringIncomeForm();
    await loadRecurringPage();
  } catch (error) {
    setRecIncFormStatus(`Error: ${error.message}`, 'error');
  }
}

function editRecExpense(id) {
  const item = recurringExpenses.find(e => e.id === id);
  if (!item) return;
  editingRecExpenseId = id;
  document.getElementById('rec-desc').value = item.description;
  document.getElementById('rec-category').value = item.category;
  document.getElementById('rec-amount').value = item.amount_gbp;
  document.getElementById('rec-day').value = item.day_of_month;
  document.getElementById('rec-start').value = item.start_date;
  document.getElementById('rec-end').value = item.end_date || '';
  setRecExpFormStatus(`Editing "${item.description}"`, 'success');
  updateRecExpSaveButton();
  document.getElementById('rec-desc').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function toggleRecExpense(id, newState) {
  const item = recurringExpenses.find(e => e.id === id);
  if (!item) return;
  try {
    await apiPut(`/recurring/expenses/${id}`, {
      ...item,
      is_active: newState,
    });
    await loadRecurringPage();
  } catch (error) {
    setRecurringFormStatus(`Error: ${error.message}`, 'error');
  }
}

function editRecIncome(id) {
  const item = recurringIncomes.find(i => i.id === id);
  if (!item) return;
  editingRecIncomeId = id;
  document.getElementById('rec-inc-desc').value = item.description;
  document.getElementById('rec-inc-source').value = item.source || '';
  document.getElementById('rec-inc-currency').value = item.currency || 'GBP';
  document.getElementById('rec-inc-amount').value = item.gross_amount;
  document.getElementById('rec-inc-day').value = item.day_of_month;
  document.getElementById('rec-inc-account').value = item.payment_account || '';
  document.getElementById('rec-inc-start').value = item.start_date;
  document.getElementById('rec-inc-end').value = item.end_date || '';
  setRecIncFormStatus(`Editing "${item.description}"`, 'success');
  updateRecIncSaveButton();
  document.getElementById('rec-inc-desc').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function toggleRecIncome(id, newState) {
  const item = recurringIncomes.find(i => i.id === id);
  if (!item) return;
  try {
    await apiPut(`/recurring/income/${id}`, {
      ...item,
      is_active: newState,
    });
    await loadRecurringPage();
  } catch (error) {
    setRecurringFormStatus(`Error: ${error.message}`, 'error');
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('period-selector').addEventListener('change', event => {
    selectedPeriodKeys[currentPeriodMode] = event.target.value;
    loadPageData(currentPage);
  });

  document.getElementById('custom-start-date').addEventListener('change', () => {
    syncCustomPeriodFromInputs();
    loadPageData(currentPage);
  });

  document.getElementById('custom-end-date').addEventListener('change', () => {
    syncCustomPeriodFromInputs();
    loadPageData(currentPage);
  });

  document.getElementById('expense-period-filter').addEventListener('change', event => {
    expensePeriodMode = event.target.value;
    syncExpensePeriodSelector();
    loadExpenses();
  });

  document.getElementById('expense-timeframe-filter').addEventListener('change', event => {
    expenseSelectedPeriodKeys[expensePeriodMode] = event.target.value;
    loadExpenses();
  });

  document.getElementById('expense-search').addEventListener('input', () => {
    loadExpenses();
  });

  document.getElementById('expense-cat-filter').addEventListener('change', () => {
    loadExpenses();
  });

  document.getElementById('expense-group-filter').addEventListener('change', () => {
    loadExpenses();
  });

  document.getElementById('expense-payment-filter').addEventListener('change', () => {
    loadExpenses();
  });

  document.getElementById('exp-group').addEventListener('change', () => {
    populateExpenseCategoryOptions(false);
  });

  const catInput = document.getElementById('exp-category-input');
  const catDropdown = document.getElementById('exp-category-dropdown');
  const catWrap = document.getElementById('exp-category-wrap');
  if (catInput && catDropdown && catWrap) {
    catInput.addEventListener('click', () => {
      const isOpen = catDropdown.classList.contains('open');
      if (isOpen) {
        catDropdown.classList.remove('open');
      } else {
        const groupSelect = document.getElementById('exp-group');
        const { top, others } = getCategoryEntriesForGroup(groupSelect.value);
        _buildCategoryDropdown(catDropdown, top, others,
          document.getElementById('exp-category'), catInput, '');
        catDropdown.classList.add('open');
        setTimeout(() => {
          const searchBox = catDropdown.querySelector('#exp-category-search');
          if (searchBox) searchBox.focus();
        }, 0);
      }
    });
    document.addEventListener('mousedown', e => {
      if (!catWrap.contains(e.target)) {
        catDropdown.classList.remove('open');
      }
    });
  }

  document.getElementById('catmgr-overlay')?.addEventListener('mousedown', e => {
    if (e.target === e.currentTarget) closeCategoryManager();
  });

  document.getElementById('expense-custom-start').addEventListener('change', () => {
    syncExpenseCustomPeriodFromInputs();
    loadExpenses();
  });

  document.getElementById('expense-custom-end').addEventListener('change', () => {
    syncExpenseCustomPeriodFromInputs();
    loadExpenses();
  });

  document.getElementById('income-period-filter').addEventListener('change', event => {
    incomePeriodMode = event.target.value;
    syncIncomePeriodSelector();
    loadIncome();
  });

  document.getElementById('income-timeframe-filter').addEventListener('change', event => {
    incomeSelectedPeriodKeys[incomePeriodMode] = event.target.value;
    loadIncome();
  });

  document.getElementById('income-search').addEventListener('input', () => {
    loadIncome();
  });

  document.getElementById('income-source-filter').addEventListener('change', () => {
    loadIncome();
  });

  document.getElementById('income-currency-filter').addEventListener('change', () => {
    loadIncome();
  });

  document.getElementById('income-account-filter').addEventListener('change', () => {
    loadIncome();
  });

  document.getElementById('income-taxable-filter').addEventListener('change', () => {
    loadIncome();
  });

  document.getElementById('income-custom-start').addEventListener('change', () => {
    syncIncomeCustomPeriodFromInputs();
    loadIncome();
  });

  document.getElementById('income-custom-end').addEventListener('change', () => {
    syncIncomeCustomPeriodFromInputs();
    loadIncome();
  });

  document.getElementById('tax-period-filter').addEventListener('change', event => {
    taxPeriodMode = event.target.value;
    syncTaxPeriodSelector();
    loadTaxDue();
  });

  document.getElementById('tax-timeframe-filter').addEventListener('change', event => {
    taxSelectedPeriodKeys[taxPeriodMode] = event.target.value;
    loadTaxDue();
  });

  document.getElementById('tax-search').addEventListener('input', () => {
    loadTaxDue();
  });

  document.getElementById('tax-period-name-filter').addEventListener('change', () => {
    loadTaxDue();
  });

  document.getElementById('tax-custom-start').addEventListener('change', () => {
    syncTaxCustomPeriodFromInputs();
    loadTaxDue();
  });

  document.getElementById('tax-custom-end').addEventListener('change', () => {
    syncTaxCustomPeriodFromInputs();
    loadTaxDue();
  });

  document.getElementById('report-period-filter').addEventListener('change', () => {
    loadReports();
  });

  document.getElementById('report-group-filter').addEventListener('change', () => {
    loadReports();
  });

  document.getElementById('report-cat-filter').addEventListener('change', () => {
    loadReports();
  });

  document.getElementById('finance-history-start').addEventListener('change', () => {
    loadFinanceHistory();
  });

  document.getElementById('finance-history-end').addEventListener('change', () => {
    loadFinanceHistory();
  });

  document.getElementById('xfer-from-amount')?.addEventListener('input', updateTransferRatePreview);
  document.getElementById('xfer-to-amount')?.addEventListener('input', updateTransferRatePreview);

  document.getElementById('finance-history-account-filter').addEventListener('change', () => {
    loadFinanceHistory();
  });

  clearExpenseForm();
  clearIncomeForm();
  clearTaxForm();
  clearFinanceForm();
  syncPeriodSelector();
  loadPageData('dashboard');
});
