// Dashboard page: fetch data and render
let showAllTopCategories = false;
let dashboardExpenseMixChart = null;
let dashboardIncomeMixChart = null;
let _lastDashboardData = null;

function getBasisRows(data) {
  const basis = typeof dashboardBasis !== 'undefined' ? dashboardBasis : 'paid';
  if (basis === 'used' && data.group_category_spending_used) {
    return data.group_category_spending_used;
  }
  return data.group_category_spending || data.category_spending || [];
}

const DASHBOARD_INCOME_MIX_COLORS = [
  '#5B6C9E',
  '#9FC55B',
  '#4DA7C7',
  '#274C7E',
  '#7C8FB8',
  '#C6925B',
  '#B07AA1',
  '#7E7E92',
];

async function loadDashboard(periodMode, startDate, endDate) {
  const params = new URLSearchParams({
    period_mode: periodMode || 'Financial Year',
  });
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);

  if (!classificationData.length) await loadClassifications();
  if (!incomeClassificationData) await loadIncomeClassifications();
  renderFinanceSnapshotLoading();
  const financePromise = loadDashboardFinanceSnapshot();

  let data;
  try {
    data = await apiGet('/reports/dashboard?' + params);
  } catch (e) {
    document.getElementById('dashboard-metrics-row1').innerHTML =
      `<div style="grid-column:1/-1;color:#c0392b;padding:12px">Dashboard error: ${e.message}</div>`;
    return;
  }

  _lastDashboardData = data;
  renderDashboardMetrics(data.metrics);
  renderTopCategories(data);
  renderExpenseBreakout(data);

  requestAnimationFrame(() => {
    try {
      renderDashboardOverviewChart(data.metrics);
    } catch (e) {
      renderDashboardChartError('dashboard-overview-chart', 'Income, expense, and saving', 'Could not load chart.');
      console.error('Dashboard overview chart error:', e);
    }

    try {
      renderExpenseMix(data);
    } catch (e) {
      renderDashboardChartError('dashboard-expense-mix', 'Expense mix', 'Could not load chart.');
      console.error('Dashboard expense mix error:', e);
    }

    try {
      renderIncomeMix(data.income_source_spending || []);
    } catch (e) {
      renderDashboardChartError('dashboard-income-mix', 'Income mix', 'Could not load chart.');
      console.error('Dashboard income mix error:', e);
    }
  });

  await financePromise;
}

function pctOfIncome(num, income) {
  const n = parseFloat(num) || 0;
  const d = parseFloat(income) || 0;
  if (d <= 0) return '';
  return ((n / d) * 100).toFixed(1) + '%';
}

function savingsRate(num, income) {
  return pctOfIncome(num, income);
}

function signedGBP(val) {
  const n = parseFloat(val) || 0;
  const sign = n >= 0 ? '+' : '-';
  return sign + '£' + fmtAmt(Math.abs(n));
}

function renderDashboardMetrics(m) {
  const income = m.gross_income_gbp;
  const ncf = parseFloat(m.net_cash_flow_gbp) || 0;

  // Row 1
  document.getElementById('mc-income').textContent = fmtGBP(m.gross_income_gbp);
  document.getElementById('mc-income-sub').textContent = document.getElementById('period-hint').textContent || 'Selected period';
  document.getElementById('mc-tax').textContent = '£' + fmtAmt(m.total_tax_amount_gbp);
  document.getElementById('mc-tax-sub').textContent = pctOfIncome(m.total_tax_amount_gbp, income);
  document.getElementById('mc-taxable-exp').textContent = '£' + fmtAmt(m.taxable_expense_gbp);
  document.getElementById('mc-taxable-exp-sub').textContent = pctOfIncome(m.taxable_expense_gbp, income);

  const ncfEl = document.getElementById('mc-cashflow');
  ncfEl.textContent = signedGBP(m.net_cash_flow_gbp);
  ncfEl.className = 'mc-value ' + (ncf >= 0 ? 'pos' : 'neg');
  document.getElementById('mc-cashflow-sub').textContent = pctOfIncome(m.net_cash_flow_gbp, income);

  // Row 2
  document.getElementById('mc-exp-used').textContent = '£' + fmtAmt(m.expense_used_ex_tax_gbp);
  document.getElementById('mc-exp-used-sub').textContent = pctOfIncome(m.expense_used_ex_tax_gbp, income);
  document.getElementById('mc-exp-paid').textContent = '£' + fmtAmt(m.expense_paid_ex_tax_gbp);
  document.getElementById('mc-exp-paid-sub').textContent = pctOfIncome(m.expense_paid_ex_tax_gbp, income);

  const savUsed = parseFloat(m.saving_used_gbp) || 0;
  const savUsedEl = document.getElementById('mc-sav-used');
  savUsedEl.textContent = '£' + fmtAmt(m.saving_used_gbp);
  savUsedEl.className = 'mc-value ' + (savUsed >= 0 ? 'pos' : 'neg');
  document.getElementById('mc-sav-used-sub').textContent = savingsRate(m.saving_used_gbp, income);

  const savPaid = parseFloat(m.saving_paid_gbp) || 0;
  const savPaidEl = document.getElementById('mc-sav-paid');
  savPaidEl.textContent = '£' + fmtAmt(m.saving_paid_gbp);
  savPaidEl.className = 'mc-value ' + (savPaid >= 0 ? 'pos' : 'neg');
  document.getElementById('mc-sav-paid-sub').textContent = savingsRate(m.saving_paid_gbp, income);

  // Tax Paid (FY total / 12)
  const taxPaidMonthly = parseFloat(m.tax_paid_monthly_gbp) || 0;
  const periodTaxPaid = parseFloat(m.period_tax_paid_gbp) || 0;
  document.getElementById('mc-tax-paid').textContent = '£' + fmtAmt(taxPaidMonthly);
  const taxPaidPct = pctOfIncome(taxPaidMonthly, income);
  document.getElementById('mc-tax-paid-sub').textContent = `${taxPaidPct || '0%'} | Tax paid this period: £${fmtAmt(periodTaxPaid)}`;

  // Cash Outflow = Expense Paid + actual tax paid this period
  const expPaid = parseFloat(m.expense_paid_ex_tax_gbp) || 0;
  const cashOutflow = expPaid + periodTaxPaid;
  document.getElementById('mc-cash-outflow').textContent = '£' + fmtAmt(cashOutflow);
  document.getElementById('mc-cash-outflow-sub').textContent = pctOfIncome(cashOutflow, income);
}

function renderDashboardOverviewChart(metrics) {
  const el = document.getElementById('dashboard-overview-chart');
  if (!el) return;

  const basis = typeof dashboardBasis !== 'undefined' ? dashboardBasis : 'paid';
  const expenseAmt = basis === 'used'
    ? (parseFloat(metrics.expense_used_ex_tax_gbp) || 0)
    : (parseFloat(metrics.expense_paid_ex_tax_gbp) || 0);
  const savingAmt = basis === 'used'
    ? (parseFloat(metrics.saving_used_gbp) || 0)
    : (parseFloat(metrics.saving_paid_gbp) || 0);
  const rows = [
    { label: 'Income', amount: parseFloat(metrics.gross_income_gbp) || 0, lightColor: '#C4DAF6', darkColor: '#5B93D3' },
    { label: 'Expense', amount: expenseAmt, lightColor: '#F7CB9E', darkColor: '#FEA13A' },
    { label: 'Tax Liability', amount: parseFloat(metrics.total_tax_amount_gbp) || 0, lightColor: '#E6B8B8', darkColor: '#C47A7A' },
    {
      label: 'Savings',
      amount: savingAmt,
      positiveLightColor: '#D5E7A7',
      positiveDarkColor: '#A8C95B',
      negativeLightColor: '#E6A3A0',
      negativeDarkColor: '#C85C56',
    },
  ];
  const maxPositive = rows.reduce((max, row) => row.amount > 0 ? Math.max(max, row.amount) : max, 0);
  const maxNegative = rows.reduce((max, row) => row.amount < 0 ? Math.max(max, Math.abs(row.amount)) : max, 0);
  const totalSpan = maxPositive + maxNegative;
  const zeroPosition = totalSpan > 0 ? (maxNegative / totalSpan) * 100 : 0;

  let html = '<div class="card-title"><i class="ti ti-chart-bar"></i>Income, expense, and saving</div>';
  if (totalSpan <= 0) {
    el.innerHTML = html + '<div class="dashboard-card-empty">No data for this selection.</div>';
    return;
  }

  html += '<div class="dashboard-compare">';
  rows.forEach((row) => {
    const isNegative = row.amount < 0;
    const sideMax = isNegative ? maxNegative : maxPositive;
    const ratio = sideMax > 0 ? Math.abs(row.amount) / sideMax : 0;
    const width = ratio > 0 ? Math.max((ratio * 100), 2) : 0;
    const lightColor = isNegative && row.negativeLightColor ? row.negativeLightColor : row.lightColor || row.positiveLightColor;
    const darkColor = isNegative && row.negativeDarkColor ? row.negativeDarkColor : row.darkColor || row.positiveDarkColor;
    const fillColor = blendHex(lightColor, darkColor, totalSpan > 0 ? Math.abs(row.amount) / totalSpan : 0);
    const fill = width > 0
      ? `<div class="dashboard-compare-fill" style="width:${width}%;background:${fillColor}"></div>`
      : '';
    html += `<div class="dashboard-compare-row">
      <div class="dashboard-compare-label">${row.label}</div>
      <div class="dashboard-compare-scale" style="--zero-position:${zeroPosition}%;">
        <div class="dashboard-compare-track"></div>
        <div class="dashboard-compare-zero"></div>
        <div class="dashboard-compare-half left" style="width:${zeroPosition}%;">${isNegative ? fill : ''}</div>
        <div class="dashboard-compare-half right" style="width:${100 - zeroPosition}%;">${!isNegative ? fill : ''}</div>
      </div>
      <div class="dashboard-compare-value">${fmtAmt(row.amount)}</div>
    </div>`;
  });
  html += '</div>';
  el.innerHTML = html;
}

function blendHex(lightHex, darkHex, ratio) {
  const clamped = Math.max(0, Math.min(1, ratio));
  const mixChannel = (start, end) => {
    const value = Math.round(start + ((end - start) * clamped));
    return value.toString(16).padStart(2, '0');
  };

  const light = lightHex.replace('#', '');
  const dark = darkHex.replace('#', '');

  return `#${mixChannel(parseInt(light.slice(0, 2), 16), parseInt(dark.slice(0, 2), 16))}${mixChannel(parseInt(light.slice(2, 4), 16), parseInt(dark.slice(2, 4), 16))}${mixChannel(parseInt(light.slice(4, 6), 16), parseInt(dark.slice(4, 6), 16))}`;
}

function renderExpenseMix(data) {
  const rows = getBasisRows(data);
  let mixRows;
  if (classificationData.length) {
    const totals = {};
    for (const row of rows) {
      const sg = getClassification(row.group || '', row.category || '');
      totals[sg] = (totals[sg] || 0) + (parseFloat(row.amount_gbp) || 0);
    }
    mixRows = classificationData
      .filter(cg => (totals[cg.name] || 0) > 0)
      .map(cg => ({ label: cg.name, amount: totals[cg.name] || 0, color: cg.color }));
  } else {
    mixRows = rows
      .filter(row => (parseFloat(row.amount_gbp) || 0) > 0)
      .map(row => ({ label: row.category || 'Uncategorised', amount: parseFloat(row.amount_gbp) || 0, color: getCatColor(row.category) }));
  }
  renderDashboardMixChart({
    cardId: 'dashboard-expense-mix',
    title: 'Expense mix',
    icon: 'ti-chart-donut',
    centerLabel: 'Expenses',
    rows: mixRows,
    chartKey: 'expense',
  });
}

function renderIncomeMix(rows) {
  renderDashboardMixChart({
    cardId: 'dashboard-income-mix',
    title: 'Income mix',
    icon: 'ti-chart-donut-3',
    centerLabel: 'Income',
    rows: rows
      .filter(row => (parseFloat(row.amount_gbp) || 0) > 0)
      .map((row, index) => ({
        label: row.source || 'Other',
        amount: parseFloat(row.amount_gbp) || 0,
        color: (typeof getIncomeSourceColor === 'function')
          ? getIncomeSourceColor(row.source) || DASHBOARD_INCOME_MIX_COLORS[index % DASHBOARD_INCOME_MIX_COLORS.length]
          : DASHBOARD_INCOME_MIX_COLORS[index % DASHBOARD_INCOME_MIX_COLORS.length],
      })),
    chartKey: 'income',
  });
}

function renderDashboardMixChart({ cardId, title, icon, centerLabel, rows, chartKey }) {
  const el = document.getElementById(cardId);
  if (!el) return;

  destroyDashboardMixChart(chartKey);

  const total = rows.reduce((sum, row) => sum + row.amount, 0);
  let html = `<div class="card-title"><i class="ti ${icon}"></i>${title}</div>`;
  if (!rows.length || total <= 0) {
    el.innerHTML = html + '<div class="dashboard-card-empty">No data for this selection.</div>';
    return;
  }

  const canvasId = `${cardId}-canvas`;
  const legendHtml = rows.map((row) => {
    return `<div class="dashboard-mix-legend-row">
      <span class="dashboard-mix-legend-dot" style="background:${row.color}"></span>
      <span class="dashboard-mix-legend-name">${row.label}</span>
    </div>`;
  }).join('');

  html += `<div class="dashboard-mix-grid">
    <div class="dashboard-mix-canvas">
      <canvas id="${canvasId}"></canvas>
      <div class="dashboard-mix-center">
        <div class="dashboard-mix-center-label">${centerLabel}</div>
        <div class="dashboard-mix-center-value">${fmtGBP(total)}</div>
      </div>
    </div>
    <div class="dashboard-mix-legend">${legendHtml}</div>
  </div>`;
  el.innerHTML = html;

  const canvas = document.getElementById(canvasId);
  const chart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: rows.map(row => row.label),
      datasets: [{
        data: rows.map(row => row.amount),
        backgroundColor: rows.map(row => row.color),
        borderColor: '#fff',
        borderWidth: 2,
        hoverOffset: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const value = parseFloat(ctx.raw) || 0;
              const pct = total > 0 ? Math.round((value / total) * 100) : 0;
              return `${ctx.label}: ${fmtGBP(value)} (${pct}%)`;
            },
          },
        },
      },
    },
  });

  if (chartKey === 'expense') {
    dashboardExpenseMixChart = chart;
  } else {
    dashboardIncomeMixChart = chart;
  }
}

function destroyDashboardMixChart(chartKey) {
  if (chartKey === 'expense' && dashboardExpenseMixChart) {
    dashboardExpenseMixChart.destroy();
    dashboardExpenseMixChart = null;
  }
  if (chartKey === 'income' && dashboardIncomeMixChart) {
    dashboardIncomeMixChart.destroy();
    dashboardIncomeMixChart = null;
  }
}

function renderDashboardChartError(cardId, title, message) {
  const el = document.getElementById(cardId);
  if (!el) return;
  el.innerHTML = `<div class="card-title">${title}</div><div style="font-size:12px;color:#c0392b">${message}</div>`;
}

function renderTopCategories(data) {
  const el = document.getElementById('dashboard-top-cats');
  const categories = getBasisRows(data);
  if (!categories || !categories.length) {
    el.innerHTML = '<div class="card-title"><i class="ti ti-flame"></i>Top categories<span class="ct-right">GBP 0.00</span></div><div style="font-size:12px;color:#8492a6">No data</div>';
    return;
  }

  const positiveRows = categories
    .filter(r => parseFloat(r.amount_gbp) > 0)
    .sort((a, b) => parseFloat(b.amount_gbp) - parseFloat(a.amount_gbp));
  const total = positiveRows.reduce((s, r) => s + parseFloat(r.amount_gbp), 0);
  const maxAmt = positiveRows.length ? parseFloat(positiveRows[0].amount_gbp) : 1;
  const visibleRows = showAllTopCategories ? positiveRows : positiveRows.slice(0, 5);
  const remaining = positiveRows.length - visibleRows.length;

  let html = `<div class="card-title"><i class="ti ti-flame"></i>Top categories<span class="ct-right">GBP ${fmtAmt(total)}</span></div>`;
  visibleRows.forEach((r, i) => {
    const amt = parseFloat(r.amount_gbp);
    const pct = total > 0 ? Math.round(amt / total * 100) : 0;
    const barW = maxAmt > 0 ? Math.round(amt / maxAmt * 100) : 0;
    const color = classificationData.length
      ? getClassificationColor(getClassification(r.group || '', r.category || ''))
      : getCatColor(r.category);
    html += `<div class="top-cat-row">
      <div class="top-cat-rank">${i + 1}</div>
      <div class="top-cat-bar-wrap">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px">
          <span class="top-cat-name"><span class="cat-dot" style="background:${color};display:inline-block;margin-right:5px"></span>${r.category}</span>
          <span class="top-cat-amt">GBP ${fmtAmt(r.amount_gbp)} · ${pct}%</span>
        </div>
        <div class="bar-track"><div class="bar-fill" style="width:${barW}%;background:${color}"></div></div>
      </div>
    </div>`;
  });
  if (positiveRows.length > 5) {
    const label = showAllTopCategories
      ? 'Show fewer'
      : `Show all items (${positiveRows.length})`;
    html += `<button class="top-cat-toggle" type="button" onclick="toggleTopCategories()">${label}</button>`;
  } else if (remaining > 0) {
    html += `<div class="top-cat-toggle">${remaining} more categor${remaining === 1 ? 'y' : 'ies'}</div>`;
  }
  el.innerHTML = html;
}

function renderFinanceSnapshotLoading() {
  const el = document.getElementById('dashboard-finance');
  if (!el) return;
  el.innerHTML = '<div class="card-title"><i class="ti ti-building-bank"></i>Finance snapshot</div><div style="font-size:12px;color:#8492a6">Loading...</div>';
}

function renderDashboardFinanceSnapshot(summary, totals) {
  const el = document.getElementById('dashboard-finance');
  let html = '<div class="card-title"><i class="ti ti-building-bank"></i>Finance snapshot</div>';

  if (!summary || !summary.length) {
    html += '<div style="font-size:12px;color:#8492a6">No finance data</div>';
    el.innerHTML = html;
    return;
  }

  summary.forEach(r => {
    html += `<div class="fin-row"><span class="fin-label">${r.currency}</span><span class="fin-bal">${fmtAmt(r.balance)}</span></div>`;
  });

  if (totals) {
    html += `<div class="fin-total"><span>Excl. Mum's Time D (GBP)</span><span>${fmtAmt(totals.total_gbp_excluding_mums_time_d)}</span></div>`;
    html += `<div class="fin-total"><span>Excl. Mum's Time D (HKD)</span><span>${fmtAmt(totals.total_hkd_excluding_mums_time_d)}</span></div>`;
    html += `<div class="fin-total"><span>Incl. Mum's Time D (GBP)</span><span>${fmtAmt(totals.total_gbp_including_mums_time_d)}</span></div>`;
    html += `<div class="fin-total"><span>Incl. Mum's Time D (HKD)</span><span>${fmtAmt(totals.total_hkd_including_mums_time_d)}</span></div>`;
    if (totals.rate_gbp_hkd) {
      html += `<div class="fin-total"><span>FX rate used (GBP/HKD)</span><span>${totals.rate_gbp_hkd}</span></div>`;
    }
  }
  el.innerHTML = html;
}

async function loadDashboardFinanceSnapshot() {
  try {
    const overview = await apiGet('/finance/overview');
    const excluding = (overview.scenario_totals || []).find((row) => row.scenario === "Excluding Mum's Time D");
    const including = (overview.scenario_totals || []).find((row) => row.scenario === "Including Mum's Time D");
    renderDashboardFinanceSnapshot(
      overview.currency_totals || [],
      {
        total_gbp_excluding_mums_time_d: excluding?.total_gbp,
        total_hkd_excluding_mums_time_d: excluding?.total_hkd,
        total_gbp_including_mums_time_d: including?.total_gbp,
        total_hkd_including_mums_time_d: including?.total_hkd,
        rate_gbp_hkd: overview.rate_gbp_hkd,
      },
    );
  } catch (e) {
    const el = document.getElementById('dashboard-finance');
    if (!el) return;
    el.innerHTML = `<div class="card-title"><i class="ti ti-building-bank"></i>Finance snapshot</div><div style="font-size:12px;color:#c0392b">Finance snapshot error: ${e.message}</div>`;
  }
}

function renderExpenseBreakout(data) {
  const el = document.getElementById('dashboard-breakout');
  const tax = parseFloat(data.displayed_tax_gbp) || 0;

  const basis = typeof dashboardBasis !== 'undefined' ? dashboardBasis : 'paid';
  const paidTotalExTax = parseFloat(data.total_expense_paid_gbp) || 0;
  const usedTotalExTax = parseFloat(data.total_expense_used_gbp) || 0;
  const totalExTax = basis === 'used' ? usedTotalExTax : paidTotalExTax;
  const totalInclTax = totalExTax + tax;

  function bkRow(label, val, color, isTotal) {
    const style = isTotal ? ' style="font-weight:600;border-top:1px solid #e8ecf4;padding-top:7px"' : '';
    const dot = color ? `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px;flex-shrink:0"></span>` : '';
    return `<div class="bk-row"${style}><span class="bk-type">${dot}${label}</span><span class="bk-gbp">${fmtGBP(val)}</span></div>`;
  }

  let html = '<div class="card-title"><i class="ti ti-receipt"></i>Expense breakout</div>';

  const basisRows = getBasisRows(data);
  if (classificationData.length && basisRows.length) {
    const superGroupTotals = {};
    for (const row of basisRows) {
      const sg = getClassification(row.group, row.category);
      superGroupTotals[sg] = (superGroupTotals[sg] || 0) + (parseFloat(row.amount_gbp) || 0);
    }

    for (const cg of classificationData) {
      if (cg.name === 'Tax') continue;
      const val = superGroupTotals[cg.name] || 0;
      html += bkRow(cg.name, val, cg.color, false);
    }
  } else {
    const b = data.expense_breakout || {};
    const regNonHousing = parseFloat(b.regular_non_housing_gbp) || 0;
    html += bkRow('Housing', parseFloat(b.housing_gbp) || 0, null, false);
    html += bkRow('Regular non-housing', regNonHousing, null, false);
    html += bkRow('Family', parseFloat(b.family_gbp) || 0, null, false);
    html += bkRow('UK Settlement', parseFloat(b.uk_settlement_gbp) || 0, null, false);
    html += bkRow('Large One-off', parseFloat(b.large_one_off_gbp) || 0, null, false);
    html += bkRow('Travel', parseFloat(b.travel_gbp) || 0, null, false);
  }

  html += bkRow('Total before tax', totalExTax, null, true);
  html += bkRow('Tax payment', tax, null, false);
  html += bkRow('Total including tax', totalInclTax, null, true);

  el.innerHTML = html;
}

window.toggleTopCategories = function() {
  showAllTopCategories = !showAllTopCategories;
  if (_lastDashboardData) {
    renderTopCategories(_lastDashboardData);
  }
};
