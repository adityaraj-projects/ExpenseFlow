/**
 * ExpenseFlow - Reports & Analytics Controller with Chart.js
 */

let currentTimeframe = 'this_month';
let reportTimelineChartInstance = null;
let reportExpenseChartInstance = null;
let reportIncomeChartInstance = null;

let cachedReportData = null;

document.addEventListener('DOMContentLoaded', async () => {
  Auth.initAppShell('reports');
  initTimeframeControls();
  window.addEventListener('themechange', () => {
    if (cachedReportData) {
      const user = Auth.getCurrentUser();
      const currency = user ? user.currency : 'INR';
      renderTimelineChart(cachedReportData.time_series, currency);
      renderExpenseCategoryChart(cachedReportData.expense_categories, currency);
    }
  });
  await loadReport();
});

function initTimeframeControls() {
  const buttons = document.querySelectorAll('.report-time-btn');
  const customRange = document.getElementById('custom-date-range');
  const applyCustomBtn = document.getElementById('apply-custom-dates');

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

    // 2. Render Timeline Chart (Income vs Expense)
    renderTimelineChart(data.time_series, currency);

    // 3. Render Expense Category Doughnut Chart
    renderExpenseCategoryChart(data.expense_categories, currency);

    // 4. Render Category Table Breakdowns
    renderCategoryTables(data.expense_categories, data.income_categories, currency);

  } catch (err) {
    showToast('Failed to generate report: ' + err.message, 'error');
  }
}

function renderTimelineChart(series, currency) {
  const ctx = document.getElementById('reportTimelineChart');
  if (!ctx || !series) return;

  if (reportTimelineChartInstance) {
    reportTimelineChartInstance.destroy();
    reportTimelineChartInstance = null;
  }

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#94A3B8' : '#64748B';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.05)';

  const labels = series.map(s => s.date_label);
  const incomeData = series.map(s => Number(s.income));
  const expenseData = series.map(s => Number(s.expense));

  reportTimelineChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Income',
          data: incomeData,
          backgroundColor: '#10B981',
          hoverBackgroundColor: '#059669',
          borderRadius: 6,
          borderSkipped: false,
          barPercentage: 0.7,
          categoryPercentage: 0.8
        },
        {
          label: 'Expense',
          data: expenseData,
          backgroundColor: '#EF4444',
          hoverBackgroundColor: '#DC2626',
          borderRadius: 6,
          borderSkipped: false,
          barPercentage: 0.7,
          categoryPercentage: 0.8
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          align: 'end',
          labels: {
            color: textColor,
            usePointStyle: true,
            pointStyle: 'circle',
            boxWidth: 8,
            boxHeight: 8,
            padding: 16,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '600' }
          }
        },
        tooltip: {
          backgroundColor: isDark ? '#1E293B' : '#FFFFFF',
          titleColor: isDark ? '#F8FAFC' : '#0F172A',
          bodyColor: isDark ? '#CBD5E1' : '#334155',
          borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.08)',
          borderWidth: 1,
          padding: 12,
          boxPadding: 6,
          cornerRadius: 8,
          usePointStyle: true,
          titleFont: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '700' },
          bodyFont: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '500' },
          callbacks: {
            title: (items) => {
              if (!items || !items.length) return '';
              const idx = items[0].dataIndex;
              return series[idx]?.exact_date || items[0].label;
            },
            label: (ctx) => `  ${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y, currency)}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: textColor,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 11, weight: '500' },
            autoSkip: true,
            maxTicksLimit: 10,
            maxRotation: 0,
            minRotation: 0,
            autoSkipPadding: 16
          }
        },
        y: {
          grid: {
            color: gridColor,
            drawBorder: false
          },
          border: { dash: [4, 4] },
          ticks: {
            color: textColor,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
            callback: (val) => formatCurrency(val, currency)
          }
        }
      }
    }
  });
}

function renderExpenseCategoryChart(expenseCats, currency) {
  const ctx = document.getElementById('reportCategoryChart');
  if (!ctx) return;

  if (reportExpenseChartInstance) {
    reportExpenseChartInstance.destroy();
    reportExpenseChartInstance = null;
  }

  if (!expenseCats || expenseCats.length === 0) {
    ctx.style.display = 'none';
    return;
  }
  ctx.style.display = 'block';

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#E2E8F0' : '#334155';

  reportExpenseChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: expenseCats.map(c => c.category_name),
      datasets: [{
        data: expenseCats.map(c => Number(c.amount)),
        backgroundColor: expenseCats.map(c => c.category_color || '#6366F1'),
        borderColor: isDark ? '#1E293B' : '#FFFFFF',
        borderWidth: 2,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: textColor,
            usePointStyle: true,
            pointStyle: 'circle',
            boxWidth: 8,
            boxHeight: 8,
            padding: 12,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '600' }
          }
        },
        tooltip: {
          backgroundColor: isDark ? '#1E293B' : '#FFFFFF',
          titleColor: isDark ? '#F8FAFC' : '#0F172A',
          bodyColor: isDark ? '#CBD5E1' : '#334155',
          borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.08)',
          borderWidth: 1,
          padding: 12,
          boxPadding: 6,
          cornerRadius: 8,
          titleFont: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '700' },
          bodyFont: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '500' },
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${formatCurrency(ctx.parsed, currency)} (${expenseCats[ctx.dataIndex].percentage}%)`
          }
        }
      }
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
