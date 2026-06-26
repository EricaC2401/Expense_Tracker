// Navigation + period management + initialization

const pages = {
  dashboard: { title: 'Dashboard', action: 'Add expense', pills: true },
  expenses:  { title: 'Expenses', action: 'Add expense', pills: false },
  income:    { title: 'Income', action: 'Add income', pills: false },
  tax:       { title: 'Tax', action: 'Add tax due', pills: false },
  finance:   { title: 'Finance snapshot', action: '', pills: false },
  recurring: { title: 'Recurring', action: 'New template', pills: false },
  reports:   { title: 'Reports', action: '', pills: true },
  import:    { title: 'Import', action: '', pills: false },
  export:    { title: 'Export', action: '', pills: false },
};

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
  start: '2021-04-01',
  end: toISODate(todayDate()),
};
let currentTaxRows = [];
let editingTaxId = null;
let categoryCatalog = [];
let categoryGroups = [];
let categoryManagerAvailable = true;

function normalizeText(value) {
  return String(value || '').trim().replace(/\s+/g, ' ');
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

function getCategoryEntriesForGroup(groupName) {
  const normalizedGroup = normalizeText(groupName);
  const groupedEntries = categoryCatalog
    .filter(entry => normalizeText(entry.group_name) === normalizedGroup && entry.is_active !== false)
    .sort((left, right) => {
      if ((right.usage_count || 0) !== (left.usage_count || 0)) {
        return (right.usage_count || 0) - (left.usage_count || 0);
      }
      return left.category.localeCompare(right.category);
    });

  if (groupedEntries.length) {
    return groupedEntries;
  }

  return categoryCatalog
    .filter(entry => entry.is_active !== false)
    .sort((left, right) => {
      if ((right.usage_count || 0) !== (left.usage_count || 0)) {
        return (right.usage_count || 0) - (left.usage_count || 0);
      }
      return left.category.localeCompare(right.category);
    });
}

function setCategoryManagerAvailability(isAvailable, message = '') {
  categoryManagerAvailable = isAvailable;
  const toggle = document.getElementById('category-manager-toggle');
  const panel = document.getElementById('category-manager-panel');
  const controls = [
    document.getElementById('category-manage-group'),
    document.getElementById('category-manage-select'),
    document.getElementById('category-manage-name'),
  ];

  if (toggle) {
    toggle.disabled = !isAvailable;
    toggle.title = isAvailable ? '' : message;
  }
  if (panel && !isAvailable) {
    panel.hidden = true;
  }
  controls.forEach(control => {
    if (control) control.disabled = !isAvailable;
  });
  setCategoryManagerStatus(message, message ? 'error' : '');
}

function buildFallbackCategoryCatalog(metadata = null) {
  const categories = metadata?.categories || [];
  return categories.map((category, index) => ({
    id: -(index + 1),
    category,
    group_name: '',
    usage_count: 0,
    is_active: true,
  }));
}

function populateExpenseGroupOptions() {
  const formGroupSelect = document.getElementById('exp-group');
  const manageGroupSelect = document.getElementById('category-manage-group');
  const filterGroupSelect = document.getElementById('expense-group-filter');
  const groups = getAllKnownGroups();

  if (formGroupSelect) {
    const selectedGroup = formGroupSelect.value || 'Living';
    formGroupSelect.innerHTML = groups.map(group => `<option>${group}</option>`).join('');
    formGroupSelect.value = groups.includes(selectedGroup) ? selectedGroup : (groups[0] || 'Living');
  }

  if (manageGroupSelect) {
    const selectedGroup = manageGroupSelect.value || (formGroupSelect ? formGroupSelect.value : 'Living');
    manageGroupSelect.innerHTML = groups.map(group => `<option>${group}</option>`).join('');
    manageGroupSelect.value = groups.includes(selectedGroup) ? selectedGroup : (groups[0] || 'Living');
  }

  if (filterGroupSelect) {
    const selectedGroup = filterGroupSelect.value || 'All groups';
    filterGroupSelect.innerHTML = ['All groups', ...groups].map(group => `<option>${group}</option>`).join('');
    filterGroupSelect.value = ['All groups', ...groups].includes(selectedGroup) ? selectedGroup : 'All groups';
  }
}

function populateExpenseCategoryOptions(preserveValue = true) {
  const categorySelect = document.getElementById('exp-category');
  const groupSelect = document.getElementById('exp-group');
  if (!categorySelect || !groupSelect) return;

  const currentValue = categorySelect.value;
  const entries = getCategoryEntriesForGroup(groupSelect.value);
  const values = entries.map(entry => entry.category);
  categorySelect.innerHTML = values.map(category => `<option>${category}</option>`).join('');

  if (preserveValue && currentValue) {
    categorySelect.value = values.includes(currentValue) ? currentValue : (values[0] || '');
    return;
  }

  categorySelect.value = values[0] || '';
}

function populateCategoryManagerOptions() {
  const manageGroupSelect = document.getElementById('category-manage-group');
  const manageSelect = document.getElementById('category-manage-select');
  const manageNameInput = document.getElementById('category-manage-name');
  if (!manageGroupSelect || !manageSelect || !manageNameInput) return;

  const entries = getCategoryEntriesForGroup(manageGroupSelect.value);
  manageSelect.innerHTML = entries
    .map(entry => `<option value="${entry.id}">${entry.category}${entry.usage_count ? ` (${entry.usage_count})` : ''}</option>`)
    .join('');

  if (entries.length) {
    manageSelect.value = String(entries[0].id);
    manageNameInput.value = entries[0].category;
  } else {
    manageNameInput.value = '';
  }

  renderCategoryManagerPreview();
}

function renderCategoryManagerPreview() {
  const manageGroupSelect = document.getElementById('category-manage-group');
  const manageSelect = document.getElementById('category-manage-select');
  const preview = document.getElementById('category-manage-preview');
  const count = document.getElementById('category-manage-count');
  if (!manageGroupSelect || !manageSelect || !preview || !count) return;

  const entries = getCategoryEntriesForGroup(manageGroupSelect.value);
  const activeId = String(manageSelect.value || '');
  count.textContent = `${entries.length} tag${entries.length === 1 ? '' : 's'}`;

  if (!entries.length) {
    preview.innerHTML = '<div class="category-manager-preview-empty">No categories in this group yet.</div>';
    return;
  }

  preview.innerHTML = entries
    .map(entry => {
      const isActive = String(entry.id) === activeId;
      return `
        <button
          class="category-manager-preview-item${isActive ? ' active' : ''}"
          type="button"
          onclick="selectCategoryManagerEntry(${entry.id})"
        >
          ${categoryChip(entry.category, entry.group_name)}
          <span class="category-manager-preview-item-count">${entry.usage_count || 0}</span>
        </button>
      `;
    })
    .join('');
}

function selectCategoryManagerEntry(categoryId) {
  const manageSelect = document.getElementById('category-manage-select');
  const manageNameInput = document.getElementById('category-manage-name');
  if (!manageSelect || !manageNameInput) return;

  manageSelect.value = String(categoryId);
  const selectedOption = manageSelect.selectedOptions[0];
  manageNameInput.value = selectedOption
    ? selectedOption.textContent.replace(/\s+\(\d+\)$/, '')
    : '';
  renderCategoryManagerPreview();
}

function toggleCategoryManager(forceState) {
  const panel = document.getElementById('category-manager-panel');
  const toggle = document.getElementById('category-manager-toggle');
  if (!panel || !toggle) return;
  if (!categoryManagerAvailable) return;

  const shouldOpen = typeof forceState === 'boolean' ? forceState : panel.hidden;
  panel.hidden = !shouldOpen;
  toggle.innerHTML = shouldOpen
    ? '<i class="ti ti-tags-off"></i>Hide categories'
    : '<i class="ti ti-tags"></i>Manage categories';

  if (shouldOpen) {
    renderCategoryManagerPreview();
  }
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
    categoryCatalog = buildFallbackCategoryCatalog(expenseMetadata);
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
  populateCategoryManagerOptions();
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
  const minDate = toISODate(TRACKING_START_DATE);
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
  const minDate = toISODate(TRACKING_START_DATE);
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

async function createCategory() {
  if (!categoryManagerAvailable) return;
  const groupName = normalizeText(document.getElementById('category-manage-group').value);
  const category = normalizeText(document.getElementById('category-manage-name').value);
  if (!groupName || !category) {
    setCategoryManagerStatus('Group and category name are required.', 'error');
    return;
  }

  try {
    await apiPost('/categories', { group_name: groupName, category });
    await loadCategoryCatalog(true);
    setCategoryManagerStatus(`Added ${category} to ${groupName}.`, 'success');
    document.getElementById('exp-group').value = groupName;
    populateExpenseCategoryOptions(false);
    toggleCategoryManager(true);
  } catch (error) {
    setCategoryManagerStatus(`Could not add category: ${error.message}`, 'error');
  }
}

async function renameCategory() {
  if (!categoryManagerAvailable) return;
  const categoryId = document.getElementById('category-manage-select').value;
  const category = normalizeText(document.getElementById('category-manage-name').value);
  if (!categoryId || !category) {
    setCategoryManagerStatus('Choose a category and enter the new name.', 'error');
    return;
  }

  try {
    await apiPut(`/categories/${categoryId}`, { category });
    await loadCategoryCatalog(true);
    expenseMetadata = null;
    await loadExpensesPage(true);
    setCategoryManagerStatus(`Renamed category to ${category}.`, 'success');
    populateExpenseCategoryOptions(false);
    toggleCategoryManager(true);
  } catch (error) {
    setCategoryManagerStatus(`Could not rename category: ${error.message}`, 'error');
  }
}

async function deleteCategory() {
  if (!categoryManagerAvailable) return;
  const manageSelect = document.getElementById('category-manage-select');
  const selectedText = manageSelect?.selectedOptions?.[0]?.textContent || 'this category';
  const categoryId = manageSelect?.value;
  if (!categoryId) {
    setCategoryManagerStatus('Choose a category to delete.', 'error');
    return;
  }

  const confirmed = window.confirm(`Delete ${selectedText} from the category list? Existing expenses will keep their saved category text.`);
  if (!confirmed) return;

  try {
    await apiDelete(`/categories/${categoryId}`);
    await loadCategoryCatalog(true);
    setCategoryManagerStatus(`Deleted ${selectedText}.`, 'success');
    populateExpenseCategoryOptions(false);
    toggleCategoryManager(true);
  } catch (error) {
    setCategoryManagerStatus(`Could not delete category: ${error.message}`, 'error');
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
    const currentMonthStart = monthStartDate(latestTaxDate.getFullYear(), latestTaxDate.getMonth());
    taxCustomPeriod = {
      start: toISODate(currentMonthStart),
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

// Initialize
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

  document.getElementById('category-manage-group').addEventListener('change', () => {
    populateCategoryManagerOptions();
  });

  document.getElementById('category-manage-select').addEventListener('change', event => {
    const selectedOption = event.target.selectedOptions[0];
    document.getElementById('category-manage-name').value = selectedOption
      ? selectedOption.textContent.replace(/\s+\(\d+\)$/, '')
      : '';
    renderCategoryManagerPreview();
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

  clearExpenseForm();
  clearIncomeForm();
  clearTaxForm();
  syncPeriodSelector();
  loadPageData('dashboard');
});
