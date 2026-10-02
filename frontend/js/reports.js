/**
 * ExpenseFlow - Reports & Analytics Controller with Chart.js
 * Supports PhonePe vs Cash Channel Breakdown and PDF Statement Export
 */

let currentTimeframe = 'this_month';
let currentSource = 'all';
let reportTimelineChartInstance = null;
let reportExpenseChartInstance = null;
let reportIncomeChartInstance = null;

let cachedReportData = null;
let lastWidth = window.innerWidth;

document.addEventListener('DOMContentLoaded', async () => {
  Auth.initAppShell('reports');
  initTimeframeControls();
  initMonthlyExportModal();
  initSmartMonthlySummary();

  const handleDisplayUpdate = () => {
    if (cachedReportData) {
      const user = Auth.getCurrentUser();
      const currency = user ? user.currency : 'INR';
      renderTimelineChart(cachedReportData.time_series, currency);
      renderExpenseCategoryChart(cachedReportData.expense_categories, currency);
    }
  };

  window.addEventListener('themechange', handleDisplayUpdate);

  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      const currentWidth = window.innerWidth;
      if ((lastWidth <= 640 && currentWidth > 640) || (lastWidth > 640 && currentWidth <= 640)) {
        lastWidth = currentWidth;
        handleDisplayUpdate();
      }
    }, 200);
  });

  await loadReport();
});

function initTimeframeControls() {
  const buttons = document.querySelectorAll('.report-time-btn');
  const customRange = document.getElementById('custom-date-range');
  const applyCustomBtn = document.getElementById('apply-custom-dates');
  const sourceFilter = document.getElementById('rep-source-filter');

  // Default dates for custom input
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
  const startInput = document.getElementById('report-start-date');
  const endInput = document.getElementById('report-end-date');
  if (startInput) startInput.value = formatDateInput(firstDay);
  if (endInput) endInput.value = formatDateInput(today);

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTimeframe = btn.dataset.timeframe;

      if (currentTimeframe === 'custom') {
        if (customRange) customRange.style.display = 'flex';
      } else {
        if (customRange) customRange.style.display = 'none';
        loadReport();
      }
    });
  });

  if (applyCustomBtn) {
    applyCustomBtn.addEventListener('click', () => {
      loadReport();
    });
  }

  if (sourceFilter) {
    sourceFilter.addEventListener('change', (e) => {
      currentSource = e.target.value;
      loadReport();
    });
  }
}

async function loadReport() {
  const user = Auth.getCurrentUser();
  const currency = user ? user.currency : 'INR';

  try {
    const params = { timeframe: currentTimeframe };
    if (currentTimeframe === 'custom') {
      const startVal = document.getElementById('report-start-date')?.value;
      const endVal = document.getElementById('report-end-date')?.value;
      if (startVal) params.start_date = startVal;
      if (endVal) params.end_date = endVal;
    }
    if (currentSource && currentSource !== 'all') {
      params.source = currentSource;
    }

    const data = await ApiClient.get('/reports', params);
    cachedReportData = data;

    // 1. Render Summary KPI Cards
    const summary = data.summary;
    const incomeEl = document.getElementById('rep-income-val');
    const expenseEl = document.getElementById('rep-expense-val');
    const savingsEl = document.getElementById('rep-savings-val');
    const rateEl = document.getElementById('rep-rate-val');
    const dailyAvgEl = document.getElementById('rep-daily-avg-val');
    const txCountEl = document.getElementById('rep-tx-count-val');

    if (incomeEl) incomeEl.textContent = formatCurrency(summary.total_income, currency);
    if (expenseEl) expenseEl.textContent = formatCurrency(summary.total_expense, currency);
    if (savingsEl) savingsEl.textContent = formatCurrency(summary.net_savings, currency);
    if (rateEl) rateEl.textContent = `${summary.savings_rate}% savings rate`;
    if (dailyAvgEl) dailyAvgEl.textContent = formatCurrency(summary.daily_average_expense, currency);
    if (txCountEl) txCountEl.textContent = `${summary.transaction_count} records analyzed`;

    // 2. Render PhonePe vs Cash Channel Breakdown
    const pInc = Number(summary.phonepe_income || 0);
    const pExp = Number(summary.phonepe_expense || 0);
    const pNet = pInc - pExp;

    const cInc = Number(summary.cash_income || 0);
    const cExp = Number(summary.cash_expense || 0);
    const cNet = cInc - cExp;

    const pIncEl = document.getElementById('rep-phonepe-income');
    const pExpEl = document.getElementById('rep-phonepe-expense');
    const pNetEl = document.getElementById('rep-phonepe-net');

    const cIncEl = document.getElementById('rep-cash-income');
    const cExpEl = document.getElementById('rep-cash-expense');
    const cNetEl = document.getElementById('rep-cash-net');

    if (pIncEl) pIncEl.textContent = formatCurrency(pInc, currency);
    if (pExpEl) pExpEl.textContent = formatCurrency(pExp, currency);
    if (pNetEl) {
      pNetEl.textContent = (pNet >= 0 ? '+' : '') + formatCurrency(pNet, currency);
      pNetEl.className = pNet >= 0 ? 'channel-stat-val amount-income' : 'channel-stat-val amount-expense';
    }

    if (cIncEl) cIncEl.textContent = formatCurrency(cInc, currency);
    if (cExpEl) cExpEl.textContent = formatCurrency(cExp, currency);
    if (cNetEl) {
      cNetEl.textContent = (cNet >= 0 ? '+' : '') + formatCurrency(cNet, currency);
      cNetEl.className = cNet >= 0 ? 'channel-stat-val amount-income' : 'channel-stat-val amount-expense';
    }

    // 3. Render Timeline Chart (Income vs Expense)
    renderTimelineChart(data.time_series, currency);

    // 4. Render Expense Category Doughnut Chart
    renderExpenseCategoryChart(data.expense_categories, currency);

    // 5. Render Category Table Breakdowns
    renderCategoryTables(data.expense_categories, data.income_categories, currency);

  } catch (err) {
    showToast('Failed to generate report: ' + err.message, 'error');
  }
}

function renderTimelineChart(series, currency) {
  const ctx = document.getElementById('reportTimelineChart');
  const emptyState = document.getElementById('report-timeline-empty');
  if (!ctx || !series) return;

  if (reportTimelineChartInstance) {
    reportTimelineChartInstance.destroy();
    reportTimelineChartInstance = null;
  }

  // Check if series has any non-zero data
  const hasData = series.length > 0 && series.some(s => Number(s.income) > 0 || Number(s.expense) > 0);
  if (!hasData) {
    ctx.style.display = 'none';
    if (emptyState) emptyState.style.display = 'flex';
    return;
  }

  ctx.style.display = 'block';
  if (emptyState) emptyState.style.display = 'none';

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)';
  const textColor = isDark ? '#94A3B8' : '#64748B';

  reportTimelineChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: series.map(s => s.date_label),
      datasets: [
        {
          label: 'Income',
          data: series.map(s => Number(s.income)),
          backgroundColor: 'rgba(16, 185, 129, 0.85)',
          borderRadius: 4
        },
        {
          label: 'Expenses',
          data: series.map(s => Number(s.expense)),
          backgroundColor: 'rgba(239, 68, 68, 0.85)',
          borderRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { color: textColor, font: { weight: 600 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y, currency)}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: textColor }
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            callback: (val) => formatCurrency(val, currency)
          }
        }
      }
    }
  });
}

function renderExpenseCategoryChart(categories, currency) {
  const ctx = document.getElementById('reportCategoryChart');
  const emptyState = document.getElementById('report-category-empty');
  if (!ctx || !categories) return;

  if (reportExpenseChartInstance) {
    reportExpenseChartInstance.destroy();
    reportExpenseChartInstance = null;
  }

  if (categories.length === 0) {
    ctx.style.display = 'none';
    if (emptyState) emptyState.style.display = 'flex';
    return;
  }

  ctx.style.display = 'block';
  if (emptyState) emptyState.style.display = 'none';

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#F8FAFC' : '#1E293B';

  reportExpenseChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: categories.map(c => c.category_name),
      datasets: [{
        data: categories.map(c => Number(c.amount)),
        backgroundColor: categories.map(c => c.category_color),
        borderWidth: 2,
        borderColor: isDark ? '#1E293B' : '#FFFFFF'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: window.innerWidth < 640 ? 'bottom' : 'right',
          labels: { color: textColor, boxWidth: 12 }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${formatCurrency(ctx.parsed, currency)} (${categories[ctx.dataIndex].percentage}%)`
          }
        }
      },
      cutout: '65%'
    }
  });
}

function renderCategoryTables(expenseCats, incomeCats, currency) {
  const expTbody = document.getElementById('report-expense-tbody');
  const incTbody = document.getElementById('report-income-tbody');

  if (expTbody) {
    if (!expenseCats || expenseCats.length === 0) {
      expTbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No expenses in this period.</td></tr>`;
    } else {
      expTbody.innerHTML = expenseCats.map(c => `
        <tr>
          <td>
            <span style="display: inline-flex; align-items: center; gap: 0.5rem; font-weight: 600;">
              <span style="width: 10px; height: 10px; border-radius: 50%; background-color: ${c.category_color};"></span>
              ${escapeHtml(c.category_name)}
            </span>
          </td>
          <td>${c.transaction_count}</td>
          <td>${c.percentage}%</td>
          <td style="text-align: right; font-weight: 700; color: var(--danger);">${formatCurrency(c.amount, currency)}</td>
        </tr>
      `).join('');
    }
  }

  if (incTbody) {
    if (!incomeCats || incomeCats.length === 0) {
      incTbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No income in this period.</td></tr>`;
    } else {
      incTbody.innerHTML = incomeCats.map(c => `
        <tr>
          <td>
            <span style="display: inline-flex; align-items: center; gap: 0.5rem; font-weight: 600;">
              <span style="width: 10px; height: 10px; border-radius: 50%; background-color: ${c.category_color};"></span>
              ${escapeHtml(c.category_name)}
            </span>
          </td>
          <td>${c.transaction_count}</td>
          <td>${c.percentage}%</td>
          <td style="text-align: right; font-weight: 700; color: var(--success);">${formatCurrency(c.amount, currency)}</td>
        </tr>
      `).join('');
    }
  }
}

/* ==========================================================
   Monthly PDF Report Export Controller
   ========================================================== */
function initMonthlyExportModal() {
  const openBtn = document.getElementById('open-export-pdf-btn');
  const modal = document.getElementById('export-pdf-modal');
  const closeBtn = document.getElementById('close-export-pdf-btn');
  const cancelBtn = document.getElementById('cancel-export-pdf-btn');
  const form = document.getElementById('export-pdf-form');

  if (openBtn) {
    openBtn.addEventListener('click', () => {
      const today = new Date();
      const monthSelect = document.getElementById('export-month');
      const yearSelect = document.getElementById('export-year');
      if (monthSelect) monthSelect.value = today.getMonth() + 1;
      if (yearSelect) yearSelect.value = today.getFullYear();

      if (modal) modal.classList.add('active');
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      if (modal) modal.classList.remove('active');
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      if (modal) modal.classList.remove('active');
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('download-pdf-submit-btn');
      const month = parseInt(document.getElementById('export-month').value);
      const year = parseInt(document.getElementById('export-year').value);

      submitBtn.disabled = true;
      submitBtn.textContent = 'Generating PDF...';

      try {
        const filename = `ExpenseFlow_Statement_${year}_${String(month).padStart(2, '0')}.pdf`;
        await ApiClient.downloadFile('/reports/monthly-pdf', { month, year }, filename);

        showToast('Monthly financial statement downloaded successfully!', 'success');
        if (modal) modal.classList.remove('active');
      } catch (err) {
        showToast('Failed to export PDF: ' + err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>Download PDF
        `;
      }
    });
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

/**
 * FEATURE 1 — SMART MONTHLY FINANCIAL SUMMARY CONTROLLER
 */
function initSmartMonthlySummary() {
  const monthSelect = document.getElementById('summary-select-month');
  const yearSelect = document.getElementById('summary-select-year');
  const refreshBtn = document.getElementById('summary-refresh-btn');

  if (!monthSelect || !yearSelect) return;

  const now = new Date();
  monthSelect.value = String(now.getMonth() + 1);
  yearSelect.value = String(now.getFullYear());

  const triggerLoad = () => {
    const m = parseInt(monthSelect.value);
    const y = parseInt(yearSelect.value);
    loadSmartMonthlySummary(m, y);
  };

  monthSelect.addEventListener('change', triggerLoad);
  yearSelect.addEventListener('change', triggerLoad);
  if (refreshBtn) {
    refreshBtn.addEventListener('click', triggerLoad);
  }

  // Initial load
  triggerLoad();
}

async function loadSmartMonthlySummary(month, year) {
  const user = Auth.getCurrentUser();
  const currency = user ? user.currency : 'INR';

  try {
    const data = await ApiClient.get('/reports/monthly-summary', { month, year });

    // 1. KPIs
    const incEl = document.getElementById('sm-income');
    const incCountEl = document.getElementById('sm-income-count');
    const expEl = document.getElementById('sm-expense');
    const expCountEl = document.getElementById('sm-expense-count');
    const savingsEl = document.getElementById('sm-net-savings');
    const statusEl = document.getElementById('sm-savings-status');
    const rateEl = document.getElementById('sm-savings-rate');
    const rateBar = document.getElementById('sm-rate-bar');

    if (incEl) incEl.textContent = formatCurrency(data.total_income, currency);
    if (incCountEl) incCountEl.textContent = `${data.income_count} income transaction${data.income_count === 1 ? '' : 's'}`;

    if (expEl) expEl.textContent = formatCurrency(data.total_expense, currency);
    if (expCountEl) expCountEl.textContent = `${data.expense_count} expense transaction${data.expense_count === 1 ? '' : 's'}`;

    const net = Number(data.net_savings || 0);
    if (savingsEl) {
      savingsEl.textContent = (net > 0 ? '+' : '') + formatCurrency(net, currency);
      savingsEl.style.color = net > 0 ? 'var(--success)' : (net < 0 ? 'var(--danger)' : 'var(--text-main)');
    }
    if (statusEl) {
      statusEl.textContent = net > 0 ? 'Net Savings Surplus' : (net < 0 ? 'Deficit / Overspent' : 'Balanced');
      statusEl.style.color = net > 0 ? 'var(--success)' : (net < 0 ? 'var(--danger)' : 'var(--text-muted)');
    }

    const rate = Number(data.savings_rate || 0);
    if (rateEl) rateEl.textContent = `${rate.toFixed(1)}% savings rate`;
    if (rateBar) {
      const clampPct = Math.max(0, Math.min(100, rate));
      rateBar.style.width = `${clampPct}%`;
      rateBar.style.background = rate >= 20 ? 'var(--success)' : (rate > 0 ? 'var(--primary)' : 'var(--danger)');
    }

    // 2. Month-over-Month Comparison
    const comp = data.comparison;
    const headlineEl = document.getElementById('mom-headline-text');
    const iconEl = document.getElementById('mom-trend-icon');
    const expDiffEl = document.getElementById('mom-expense-diff');
    const incDiffEl = document.getElementById('mom-income-diff');
    const savDiffEl = document.getElementById('mom-savings-diff');

    if (headlineEl) headlineEl.textContent = comp.summary_message;
    if (iconEl) {
      if (comp.expense_change_direction === 'decreased' || comp.savings_change_direction === 'improved') {
        iconEl.textContent = '📈';
      } else if (comp.expense_change_direction === 'increased') {
        iconEl.textContent = '⚠️';
      } else {
        iconEl.textContent = '📊';
      }
    }

    if (expDiffEl) {
      if (comp.expense_change_pct !== null && comp.expense_change_pct !== undefined) {
        const sign = comp.expense_change_pct >= 0 ? '+' : '';
        expDiffEl.innerHTML = `<span style="color: ${comp.expense_change_pct <= 0 ? 'var(--success)' : 'var(--danger)'};">${sign}${comp.expense_change_pct}%</span> <small style="color: var(--text-muted);">(was ${formatCurrency(comp.prev_expense, currency)})</small>`;
      } else {
        expDiffEl.textContent = formatCurrency(data.total_expense, currency);
      }
    }

    if (incDiffEl) {
      if (comp.income_change_pct !== null && comp.income_change_pct !== undefined) {
        const sign = comp.income_change_pct >= 0 ? '+' : '';
        incDiffEl.innerHTML = `<span style="color: ${comp.income_change_pct >= 0 ? 'var(--success)' : 'var(--danger)'};">${sign}${comp.income_change_pct}%</span> <small style="color: var(--text-muted);">(was ${formatCurrency(comp.prev_income, currency)})</small>`;
      } else {
        incDiffEl.textContent = formatCurrency(data.total_income, currency);
      }
    }

    if (savDiffEl) {
      savDiffEl.innerHTML = `<span>${formatCurrency(data.net_savings, currency)}</span> <small style="color: var(--text-muted);">(was ${formatCurrency(comp.prev_net_savings, currency)})</small>`;
    }

    // 3. Top Categories
    const catListEl = document.getElementById('sm-top-categories-list');
    const catBadge = document.getElementById('sm-category-count-badge');
    if (catBadge) catBadge.textContent = `${data.top_categories.length} Categories`;

    if (catListEl) {
      if (!data.top_categories || data.top_categories.length === 0) {
        catListEl.innerHTML = '<div class="empty-state-sm" style="padding: 1.5rem; text-align: center; color: var(--text-muted);">No expense records in this month</div>';
      } else {
        catListEl.innerHTML = data.top_categories.map(cat => {
          return `
            <div class="sm-cat-row">
              <div class="sm-cat-header">
                <div class="sm-cat-info">
                  <span class="sm-cat-color-dot" style="background-color: ${escapeHtml(cat.category_color)};"></span>
                  <strong class="sm-cat-name">${escapeHtml(cat.category_name)}</strong>
                  <span class="sm-cat-count">${cat.transaction_count} tx</span>
                </div>
                <div class="sm-cat-amount">
                  <strong>${formatCurrency(cat.amount, currency)}</strong>
                  <small style="color: var(--text-muted); margin-left: 4px;">(${cat.percentage.toFixed(1)}%)</small>
                </div>
              </div>
              <div class="sm-cat-progress">
                <div class="sm-cat-bar" style="width: ${Math.min(100, Math.max(2, cat.percentage))}%; background-color: ${escapeHtml(cat.category_color)};"></div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // 4. Source Breakdown (PhonePe vs Cash)
    const channelContainer = document.getElementById('sm-channel-container');
    if (channelContainer) {
      channelContainer.innerHTML = data.source_breakdown.map(src => {
        const isPhonePe = src.source === 'phonepe';
        const badgeColor = isPhonePe ? '#7C3AED' : '#059669';
        const badgeBg = isPhonePe ? 'rgba(124, 58, 237, 0.12)' : 'rgba(16, 185, 129, 0.12)';
        const icon = isPhonePe ? '📱' : '💵';

        return `
          <div class="sm-channel-row">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span>${icon}</span>
                <strong style="color: var(--text-main); font-size: 0.9rem;">${escapeHtml(src.label)}</strong>
                <span class="badge" style="background: ${badgeBg}; color: ${badgeColor}; font-size: 0.75rem;">${src.total_count} tx</span>
              </div>
              <strong style="font-size: 0.95rem; color: var(--text-main);">${formatCurrency(src.expense, currency)}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.8125rem; color: var(--text-muted);">
              <span>Income: <b style="color: var(--success);">${formatCurrency(src.income, currency)}</b> (${src.income_count} tx)</span>
              <span>Expenses: <b style="color: var(--danger);">${formatCurrency(src.expense, currency)}</b> (${src.expense_count} tx)</span>
            </div>
          </div>
        `;
      }).join('');
    }

    // 5. Rule-based Financial Insights
    const insightsList = document.getElementById('sm-insights-list');
    if (insightsList) {
      if (!data.insights || data.insights.length === 0) {
        insightsList.innerHTML = '<li class="insight-item">No specific insights available for this period.</li>';
      } else {
        insightsList.innerHTML = data.insights.map(item => `
          <li class="insight-item">
            <span class="insight-bullet">✨</span>
            <span>${escapeHtml(item)}</span>
          </li>
        `).join('');
      }
    }

  } catch (err) {
    showToast('Failed to load monthly summary: ' + err.message, 'error');
  }
}
