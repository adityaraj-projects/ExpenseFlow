/**
 * ExpenseFlow - Dashboard Controller & Chart.js Visualizations
 */

let trendChartInstance = null;
let categoryChartInstance = null;
let userCategories = [];

let cachedDashboardData = null;

document.addEventListener('DOMContentLoaded', async () => {
  Auth.initAppShell('dashboard');
  window.addEventListener('themechange', () => {
    if (cachedDashboardData) {
      const user = Auth.getCurrentUser();
      const currency = user ? user.currency : 'INR';
      renderMonthlyTrendChart(cachedDashboardData.monthly_trend, currency);
      renderCategoryBreakdownChart(cachedDashboardData.category_breakdown, currency);
    }
  });
  await loadDashboardData();
  await loadCategoriesForQuickAdd();
  initQuickAddModal();
});

async function loadDashboardData() {
  try {
    const data = await ApiClient.get('/dashboard');
    cachedDashboardData = data;
    const user = Auth.getCurrentUser();
    const currency = user ? user.currency : 'INR';

    // 1. Render Summary KPI Cards
    const balEl = document.getElementById('kpi-balance');
    const incEl = document.getElementById('kpi-income');
    const expEl = document.getElementById('kpi-expense');
    const budEl = document.getElementById('kpi-budget-remaining');
    const budSubEl = document.getElementById('kpi-budget-sub');

    if (balEl) balEl.textContent = formatCurrency(data.summary.total_balance, currency);
    if (incEl) incEl.textContent = formatCurrency(data.summary.month_income, currency);
    if (expEl) expEl.textContent = formatCurrency(data.summary.month_expense, currency);

    const budgetRemaining = data.summary.month_budget_remaining;
    if (budEl) budEl.textContent = formatCurrency(budgetRemaining, currency);
    if (budSubEl) budSubEl.textContent = `${data.summary.budget_percentage_used}% of ${formatCurrency(data.summary.month_budget, currency)} limit`;

    // 2. Render Monthly Trend Chart
    renderMonthlyTrendChart(data.monthly_trend, currency);

    // 3. Render Expense by Category Doughnut Chart
    renderCategoryBreakdownChart(data.category_breakdown, currency);

    // 4. Render Recent Transactions Table
    renderRecentTransactions(data.recent_transactions, currency);

    // 5. Render Active Budgets Progress
    renderBudgetProgress(data.budget_progress, currency);

    // 6. Render Savings Goals Progress
    renderSavingsGoalsProgress(data.savings_goals, currency);

    // 7. Render Upcoming Reminders
    renderUpcomingReminders(data.upcoming_reminders || [], currency);

    // 8. Render Upcoming Recurring Rules
    renderUpcomingRecurring(data.upcoming_recurring || [], currency);

  } catch (err) {
    showToast('Failed to load dashboard data: ' + err.message, 'error');
  }
}

/**
 * Chart 1: Income vs Expense 6-Month Rolling Bar Chart
 */
function renderMonthlyTrendChart(trendItems, currency) {
  const ctx = document.getElementById('trendChart');
  if (!ctx || !trendItems) return;

  if (trendChartInstance) {
    trendChartInstance.destroy();
    trendChartInstance = null;
  }

  const labels = trendItems.map(item => item.period);
  const incomeData = trendItems.map(item => Number(item.income));
  const expenseData = trendItems.map(item => Number(item.expense));

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#94A3B8' : '#64748B';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.05)';

  trendChartInstance = new Chart(ctx, {
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
          barPercentage: 0.65,
          categoryPercentage: 0.75
        },
        {
          label: 'Expense',
          data: expenseData,
          backgroundColor: '#EF4444',
          hoverBackgroundColor: '#DC2626',
          borderRadius: 6,
          borderSkipped: false,
          barPercentage: 0.65,
          categoryPercentage: 0.75
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
            padding: 14,
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
            label: (context) => `  ${context.dataset.label}: ${formatCurrency(context.parsed.y, currency)}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: textColor,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 11, weight: '500' }
          }
        },
        y: {
          grid: { color: gridColor, drawBorder: false },
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

/**
 * Chart 2: Category Expense Breakdown Doughnut Chart
 */
function renderCategoryBreakdownChart(breakdownItems, currency) {
  const ctx = document.getElementById('categoryChart');
  if (!ctx) return;

  if (categoryChartInstance) {
    categoryChartInstance.destroy();
    categoryChartInstance = null;
  }

  const container = document.getElementById('category-empty-state');
  if (!breakdownItems || breakdownItems.length === 0) {
    ctx.style.display = 'none';
    if (container) container.style.display = 'flex';
    return;
  } else {
    ctx.style.display = 'block';
    if (container) container.style.display = 'none';
  }

  const labels = breakdownItems.map(item => item.category_name);
  const data = breakdownItems.map(item => Number(item.amount));
  const backgroundColors = breakdownItems.map(item => item.category_color || '#6366F1');

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#E2E8F0' : '#334155';

  categoryChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: backgroundColors,
        borderWidth: 2,
        borderColor: isDark ? '#1E293B' : '#FFFFFF',
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            boxWidth: 8,
            boxHeight: 8,
            usePointStyle: true,
            pointStyle: 'circle',
            padding: 14,
            color: textColor,
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
            label: (ctx) => ` ${ctx.label}: ${formatCurrency(ctx.parsed, currency)} (${breakdownItems[ctx.dataIndex].percentage}%)`
          }
        }
      }
    }
  });
}

/**
 * Render Recent Transactions Table
 */
function renderRecentTransactions(transactions, currency) {
  const tbody = document.getElementById('recent-transactions-tbody');
  const emptyState = document.getElementById('tx-empty-state');
  if (!tbody) return;

  if (!transactions || transactions.length === 0) {
    tbody.innerHTML = '';
    if (emptyState) emptyState.style.display = 'flex';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  tbody.innerHTML = transactions.map(tx => {
    const isIncome = tx.type === 'income';
    const amountClass = isIncome ? 'amount-income' : 'amount-expense';
    const prefix = isIncome ? '+' : '-';
    const badgeClass = isIncome ? 'badge-income' : 'badge-expense';
    const catName = tx.category ? tx.category.name : 'General';
    const catColor = tx.category ? tx.category.color : '#6366F1';

    return `
      <tr>
        <td>
          <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(tx.description)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${formatDate(tx.transaction_date)}</div>
        </td>
        <td>
          <span style="display: inline-flex; align-items: center; gap: 0.4rem; font-weight: 600;">
            <span style="width: 10px; height: 10px; border-radius: 50%; background-color: ${catColor}; display: inline-block;"></span>
            ${escapeHtml(catName)}
          </span>
        </td>
        <td>
          <span class="badge ${badgeClass}">${tx.type}</span>
        </td>
        <td class="${amountClass}" style="text-align: right; font-size: 0.9375rem;">
          ${prefix}${formatCurrency(tx.amount, currency)}
        </td>
      </tr>
    `;
  }).join('');
}

/**
 * Render Active Budgets in Sidebar Card
 */
function renderBudgetProgress(budgets, currency) {
  const container = document.getElementById('dashboard-budgets-list');
  if (!container) return;

  if (!budgets || budgets.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 1.5rem 0; color: var(--text-muted); font-size: 0.875rem;">
        No budgets set for this month.<br>
        <a href="/pages/budgets.html" style="font-weight: 600; margin-top: 0.5rem; display: inline-block;">+ Set Category Budget</a>
      </div>
    `;
    return;
  }

  container.innerHTML = budgets.map(b => {
    const fillClass = b.status === 'exceeded' ? 'exceeded' : (b.status === 'warning' ? 'warning' : 'safe');
    const widthPct = Math.min(100, b.percentage_used);

    return `
      <div style="margin-bottom: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; font-size: 0.8125rem;">
          <span style="font-weight: 600; color: var(--text-main); display: flex; align-items: center; gap: 0.4rem;">
            <span style="width: 8px; height: 8px; border-radius: 50%; background-color: ${b.category_color};"></span>
            ${escapeHtml(b.category_name)}
          </span>
          <span style="color: var(--text-muted); font-size: 0.75rem;">
            ${formatCurrency(b.spent_amount, currency)} / ${formatCurrency(b.budget_amount, currency)}
          </span>
        </div>
        <div class="progress-track">
          <div class="progress-fill ${fillClass}" style="width: ${widthPct}%;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 0.25rem; font-size: 0.6875rem; color: var(--text-muted);">
          <span>${b.percentage_used}% used</span>
          <span style="${b.remaining_amount <= 0 ? 'color: var(--danger); font-weight: 700;' : ''}">
            ${b.remaining_amount <= 0 ? 'Exceeded limit' : formatCurrency(b.remaining_amount, currency) + ' left'}
          </span>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Render Savings Goals Progress
 */
function renderSavingsGoalsProgress(goals, currency) {
  const container = document.getElementById('dashboard-goals-list');
  if (!container) return;

  if (!goals || goals.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 1.5rem 0; color: var(--text-muted); font-size: 0.875rem;">
        No active savings goals.<br>
        <a href="/pages/goals.html" style="font-weight: 600; margin-top: 0.5rem; display: inline-block;">+ Create Savings Goal</a>
      </div>
    `;
    return;
  }

  container.innerHTML = goals.map(g => {
    const isDone = g.status === 'completed';
    return `
      <div style="margin-bottom: 1.25rem; padding-bottom: 0.875rem; border-bottom: 1px solid var(--border-subtle);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
          <span style="font-size: 0.875rem; font-weight: 700; color: var(--text-main);">${escapeHtml(g.name)}</span>
          <span class="badge ${isDone ? 'badge-income' : 'badge-primary'}">${isDone ? 'Completed' : g.progress_percentage + '%'}</span>
        </div>
        <div class="progress-track" style="margin: 0.4rem 0;">
          <div class="progress-fill safe" style="width: ${Math.min(100, g.progress_percentage)}%;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted);">
          <span>Saved: ${formatCurrency(g.current_amount, currency)}</span>
          <span>Target: ${formatCurrency(g.target_amount, currency)}</span>
        </div>
      </div>
    `;
  }).join('');
}
const renderSavingsGoals = renderSavingsGoalsProgress;

/**
 * Render Upcoming Reminders Widget
 */
function renderUpcomingReminders(reminders, currency) {
  const container = document.getElementById('dashboard-reminders-list');
  if (!container) return;

  if (!reminders || reminders.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 1.5rem 0; color: var(--text-muted); font-size: 0.875rem;">
        No upcoming reminders.<br>
        <a href="/pages/reminders.html" style="font-weight: 600; margin-top: 0.5rem; display: inline-block;">+ Add Reminder</a>
      </div>
    `;
    return;
  }

  container.innerHTML = reminders.map(r => {
    const rDate = new Date(r.reminder_date);
    const day = rDate.getDate();
    const month = rDate.toLocaleDateString('en-IN', { month: 'short' });
    const amtStr = r.amount ? formatCurrency(r.amount, currency) : '';

    return `
      <div class="upcoming-item">
        <div class="upcoming-left">
          <div class="upcoming-date-badge">
            <span class="upcoming-date-day">${day}</span>
            <span class="upcoming-date-month">${month}</span>
          </div>
          <div class="upcoming-info">
            <h4>${escapeHtml(r.title)}</h4>
            <span>${r.category ? r.category.name : 'General'} • ${r.recurrence}</span>
          </div>
        </div>
        <div class="upcoming-right">
          ${amtStr ? `<div class="upcoming-amount">${amtStr}</div>` : ''}
          <span style="font-size: 0.6875rem; color: var(--text-muted);">${r.reminder_time || 'All day'}</span>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Render Upcoming Recurring Transactions Widget
 */
function renderUpcomingRecurring(recurring, currency) {
  const container = document.getElementById('dashboard-recurring-list');
  if (!container) return;

  if (!recurring || recurring.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 1.5rem 0; color: var(--text-muted); font-size: 0.875rem;">
        No recurring transactions active.<br>
        <a href="/pages/recurring.html" style="font-weight: 600; margin-top: 0.5rem; display: inline-block;">+ Set Up Recurring</a>
      </div>
    `;
    return;
  }

  container.innerHTML = recurring.map(rec => {
    const isExpense = rec.type === 'expense';
    const nextD = new Date(rec.next_occurrence_date);
    const day = nextD.getDate();
    const month = nextD.toLocaleDateString('en-IN', { month: 'short' });

    return `
      <div class="upcoming-item">
        <div class="upcoming-left">
          <div class="upcoming-date-badge">
            <span class="upcoming-date-day">${day}</span>
            <span class="upcoming-date-month">${month}</span>
          </div>
          <div class="upcoming-info">
            <h4>${escapeHtml(rec.description)}</h4>
            <span>${rec.category ? rec.category.name : 'General'} • ${rec.frequency}</span>
          </div>
        </div>
        <div class="upcoming-right">
          <div class="upcoming-amount" style="color: ${isExpense ? 'var(--danger)' : 'var(--success)'};">
            ${isExpense ? '-' : '+'}${formatCurrency(rec.amount, currency)}
          </div>
          <span style="font-size: 0.6875rem; color: var(--text-muted);">${rec.payment_method || 'Other'}</span>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Quick Add Modal Functionality
 */
async function loadCategoriesForQuickAdd() {
  try {
    userCategories = await ApiClient.get('/categories');
    populateCategoryDropdown('expense');
  } catch (err) {
    console.error('Error fetching categories for modal:', err);
  }
}

function populateCategoryDropdown(txType) {
  const select = document.getElementById('quick-tx-category');
  if (!select) return;

  const filtered = userCategories.filter(c => c.type === 'both' || c.type === txType);
  select.innerHTML = filtered.map(c => `
    <option value="${c.id}">${escapeHtml(c.name)}</option>
  `).join('');
}

function initQuickAddModal() {
  const modalOverlay = document.getElementById('quick-add-modal');
  const openBtns = document.querySelectorAll('#quick-add-btn, #header-quick-add-btn');
  const closeBtns = document.querySelectorAll('#close-quick-add, #cancel-quick-add');
  const form = document.getElementById('quick-add-form');
  const typeRadios = document.querySelectorAll('input[name="quick-tx-type"]');
  const dateInput = document.getElementById('quick-tx-date');

  if (dateInput) {
    dateInput.value = formatDateInput();
  }

  typeRadios.forEach(radio => {
    radio.addEventListener('change', (e) => {
      populateCategoryDropdown(e.target.value);
    });
  });

  window.openQuickAddModal = () => {
    modalOverlay.classList.add('active');
  };

  closeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modalOverlay.classList.remove('active');
    });
  });

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('save-quick-add');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';

      const type = document.querySelector('input[name="quick-tx-type"]:checked').value;
      const amount = parseFloat(document.getElementById('quick-tx-amount').value);
      const category_id = parseInt(document.getElementById('quick-tx-category').value);
      const description = document.getElementById('quick-tx-desc').value.trim();
      const transaction_date = document.getElementById('quick-tx-date').value;

      try {
        await ApiClient.post('/transactions', {
          type,
          amount,
          category_id,
          description,
          transaction_date
        });

        showToast(`${type === 'income' ? 'Income' : 'Expense'} recorded successfully!`, 'success');
        modalOverlay.classList.remove('active');
        form.reset();
        document.getElementById('quick-tx-date').value = formatDateInput();

        // Refresh dashboard metrics
        await loadDashboardData();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Transaction';
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
