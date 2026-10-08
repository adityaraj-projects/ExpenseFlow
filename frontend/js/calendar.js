/**
 * ExpenseFlow - Calendar & Daily Finance Module
 * Fully integrated with application shell, real PhonePe statement data,
 * state synchronization, dynamic filtering, and monthly statement export.
 */

// Single Source of Truth for Calendar State
const _now = new Date();
const _urlParams = new URLSearchParams(window.location.search);
const _paramYear = parseInt(_urlParams.get('year'), 10);
const _paramMonth = parseInt(_urlParams.get('month'), 10);
const _paramDate = _urlParams.get('date');

let selectedYear = (!isNaN(_paramYear) && _paramYear >= 2000 && _paramYear <= 2100) ? _paramYear : _now.getFullYear();
let selectedMonth = (!isNaN(_paramMonth) && _paramMonth >= 1 && _paramMonth <= 12) ? _paramMonth : (_now.getMonth() + 1);
let selectedDate = _paramDate && /^\d{4}-\d{2}-\d{2}$/.test(_paramDate) ? _paramDate : formatDateInput(_now);

let currentMonthData = null;
let userCurrency = 'INR';
let calendarFilters = {
  type: '',
  source: '',
  category_id: ''
};

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Initialize Global App Shell (Sidebar, Header, Profile, Theme)
  Auth.initAppShell('calendar');

  const user = Auth.getCurrentUser();
  if (user && user.currency) {
    userCurrency = user.currency;
  }

  // 2. Initialize year dropdown (2020..2030) and synchronize month/year controls
  initYearSelector();
  syncMonthYearControls(selectedYear, selectedMonth);

  // 3. Immediately render initial calendar skeleton dates (1..31) before network request
  // so the grid is never blank or missing dates
  renderInitialGridSkeleton(selectedYear, selectedMonth);

  // 4. Attach event listeners
  initCalendarEventListeners();

  // 5. Load dynamic categories & real backend month data
  await loadCategories();
  await loadMonthData();
});

/**
 * Populate year selector dropdown with range 2020..2030
 */
function initYearSelector() {
  const yearSelect = document.getElementById('jump-year-select');
  if (!yearSelect) return;

  const startYear = 2020;
  const endYear = 2030;
  yearSelect.innerHTML = '';
  for (let y = startYear; y <= endYear; y++) {
    const opt = document.createElement('option');
    opt.value = String(y);
    opt.textContent = String(y);
    if (y === selectedYear) opt.selected = true;
    yearSelect.appendChild(opt);
  }
  yearSelect.value = String(selectedYear);
}

/**
 * Synchronize all month/year controls with single source of truth
 */
function syncMonthYearControls(year, month) {
  selectedYear = Number(year);
  selectedMonth = Number(month);

  const monthSelect = document.getElementById('jump-month-select');
  const yearSelect = document.getElementById('jump-year-select');
  const titleEl = document.getElementById('calendar-month-title');

  if (monthSelect) {
    monthSelect.value = String(selectedMonth);
  }
  if (yearSelect) {
    yearSelect.value = String(selectedYear);
  }
  if (titleEl) {
    titleEl.textContent = `${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}`;
  }
}

/**
 * Render initial days grid so date numbers are immediately visible
 */
function renderInitialGridSkeleton(year, month) {
  const gridEl = document.getElementById('calendar-days-grid');
  if (!gridEl) return;

  gridEl.innerHTML = '';

  const firstDay = new Date(year, month - 1, 1);
  let firstDayOfWeek = firstDay.getDay() - 1; // Mon = 0, Sun = 6
  if (firstDayOfWeek === -1) firstDayOfWeek = 6;

  for (let i = 0; i < firstDayOfWeek; i++) {
    const emptyCell = document.createElement('div');
    emptyCell.className = 'calendar-cell empty';
    gridEl.appendChild(emptyCell);
  }

  const daysInMonth = new Date(year, month, 0).getDate();
  const todayStr = formatDateInput(new Date());

  for (let d = 1; d <= daysInMonth; d++) {
    const dtStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const cell = document.createElement('div');
    cell.className = 'calendar-cell';
    cell.id = `cal-cell-${dtStr}`;
    cell.setAttribute('data-date', dtStr);
    cell.setAttribute('role', 'button');
    cell.setAttribute('tabindex', '0');
    cell.setAttribute('aria-label', `${d} ${MONTH_NAMES[month - 1]}`);

    if (dtStr === todayStr) {
      cell.classList.add('today');
    }
    if (dtStr === selectedDate) {
      cell.classList.add('selected');
    }

    cell.innerHTML = `
      <span class="cal-date-num">${d}</span>
      <div class="cal-indicators"></div>
    `;

    cell.addEventListener('click', () => selectDate(dtStr));
    gridEl.appendChild(cell);
  }

  // Trailing empty cells to fill the row
  const totalRendered = firstDayOfWeek + daysInMonth;
  const remainder = totalRendered % 7;
  if (remainder > 0) {
    const fillerCount = 7 - remainder;
    for (let i = 0; i < fillerCount; i++) {
      const emptyCell = document.createElement('div');
      emptyCell.className = 'calendar-cell empty';
      gridEl.appendChild(emptyCell);
    }
  }
}

/**
 * Initialize event listeners for navigation, filters, and actions
 */
function initCalendarEventListeners() {
  const prevBtn = document.getElementById('prev-month-btn');
  const nextBtn = document.getElementById('next-month-btn');
  const todayBtn = document.getElementById('today-btn');
  const monthSelect = document.getElementById('jump-month-select');
  const yearSelect = document.getElementById('jump-year-select');

  // Navigation handlers
  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      selectedMonth--;
      if (selectedMonth < 1) {
        selectedMonth = 12;
        selectedYear--;
      }
      syncMonthYearControls(selectedYear, selectedMonth);
      selectedDate = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}-01`;
      loadMonthData();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      selectedMonth++;
      if (selectedMonth > 12) {
        selectedMonth = 1;
        selectedYear++;
      }
      syncMonthYearControls(selectedYear, selectedMonth);
      selectedDate = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}-01`;
      loadMonthData();
    });
  }

  if (todayBtn) {
    todayBtn.addEventListener('click', () => {
      const now = new Date();
      selectedYear = now.getFullYear();
      selectedMonth = now.getMonth() + 1;
      selectedDate = formatDateInput(now);
      syncMonthYearControls(selectedYear, selectedMonth);
      loadMonthData();
    });
  }

  if (monthSelect) {
    monthSelect.addEventListener('change', (e) => {
      selectedMonth = parseInt(e.target.value, 10);
      syncMonthYearControls(selectedYear, selectedMonth);
      selectedDate = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}-01`;
      loadMonthData();
    });
  }

  if (yearSelect) {
    yearSelect.addEventListener('change', (e) => {
      selectedYear = parseInt(e.target.value, 10);
      syncMonthYearControls(selectedYear, selectedMonth);
      selectedDate = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}-01`;
      loadMonthData();
    });
  }

  // Filter handlers
  const filterType = document.getElementById('cal-filter-type');
  const filterSource = document.getElementById('cal-filter-source');
  const filterCategory = document.getElementById('cal-filter-category');
  const resetFiltersBtn = document.getElementById('cal-reset-filters-btn');

  if (filterType) {
    filterType.addEventListener('change', (e) => {
      calendarFilters.type = e.target.value;
      loadMonthData();
    });
  }

  if (filterSource) {
    filterSource.addEventListener('change', (e) => {
      calendarFilters.source = e.target.value;
      loadMonthData();
    });
  }

  if (filterCategory) {
    filterCategory.addEventListener('change', (e) => {
      calendarFilters.category_id = e.target.value;
      loadMonthData();
    });
  }

  if (resetFiltersBtn) {
    resetFiltersBtn.addEventListener('click', () => {
      calendarFilters = { type: '', source: '', category_id: '' };
      if (filterType) filterType.value = '';
      if (filterSource) filterSource.value = '';
      if (filterCategory) filterCategory.value = '';
      loadMonthData();
    });
  }

  // Monthly Summary & PDF Actions
  const viewSummaryBtn = document.getElementById('view-monthly-summary-btn');
  const generatePdfBtn = document.getElementById('generate-monthly-pdf-btn');

  if (viewSummaryBtn) {
    viewSummaryBtn.addEventListener('click', () => openMonthlySummaryModal());
  }

  if (generatePdfBtn) {
    generatePdfBtn.addEventListener('click', () => downloadMonthlyPdf());
  }

  // Modal actions
  const closeSummaryModalBtn = document.getElementById('close-summary-modal-btn');
  const summaryModalCloseAction = document.getElementById('summary-modal-close-action');
  const summaryModalPdfBtn = document.getElementById('summary-modal-pdf-btn');

  if (closeSummaryModalBtn) {
    closeSummaryModalBtn.addEventListener('click', closeMonthlySummaryModal);
  }
  if (summaryModalCloseAction) {
    summaryModalCloseAction.addEventListener('click', closeMonthlySummaryModal);
  }
  if (summaryModalPdfBtn) {
    summaryModalPdfBtn.addEventListener('click', () => downloadMonthlyPdf());
  }

  // Add for date button
  const addForDateBtn = document.getElementById('add-tx-this-date-btn');
  if (addForDateBtn) {
    addForDateBtn.addEventListener('click', () => {
      if (window.GlobalQuickAdd && typeof window.GlobalQuickAdd.open === 'function') {
        window.GlobalQuickAdd.open({ transaction_date: selectedDate });
      } else {
        window.location.href = `/pages/transactions.html?date=${selectedDate}`;
      }
    });
  }
}

/**
 * Load user categories for filter dropdown
 */
async function loadCategories() {
  try {
    const categories = await ApiClient.get('/categories');
    const select = document.getElementById('cal-filter-category');
    if (!select) return;

    select.innerHTML = '<option value="">All Categories</option>' + categories.map(c => `
      <option value="${c.id}">${escapeHtml(c.name)} (${c.type})</option>
    `).join('');
  } catch (err) {
    console.error('Failed to load categories for calendar:', err);
  }
}

/**
 * Fetch calendar data for selected month/year from backend
 */
async function loadMonthData() {
  try {
    syncMonthYearControls(selectedYear, selectedMonth);

    const params = {
      year: selectedYear,
      month: selectedMonth
    };
    if (calendarFilters.type) params.type = calendarFilters.type;
    if (calendarFilters.source) params.source = calendarFilters.source;
    if (calendarFilters.category_id) params.category_id = calendarFilters.category_id;

    const data = await ApiClient.get('/calendar/month', params);
    currentMonthData = data;

    // Update title
    const titleEl = document.getElementById('calendar-month-title');
    if (titleEl) {
      titleEl.textContent = `${data.month_name} ${data.year}`;
    }

    // Update Month KPIs
    const incEl = document.getElementById('month-kpi-income');
    const expEl = document.getElementById('month-kpi-expense');
    const netEl = document.getElementById('month-kpi-net');

    if (incEl) incEl.textContent = formatCurrency(data.total_income, userCurrency);
    if (expEl) expEl.textContent = formatCurrency(data.total_expense, userCurrency);
    if (netEl) {
      netEl.textContent = formatCurrency(data.net_balance, userCurrency);
      netEl.className = data.net_balance >= 0 ? 'cal-kpi-value amount-income' : 'cal-kpi-value amount-expense';
    }

    // Render Calendar Month Grid with real indicators
    renderCalendarGrid(data);

    // If currently selected date is in this month, retain it; otherwise select today or 1st day of month
    const curMonthPrefix = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`;
    if (!selectedDate || !selectedDate.startsWith(curMonthPrefix)) {
      const todayStr = formatDateInput(new Date());
      if (todayStr.startsWith(curMonthPrefix)) {
        selectedDate = todayStr;
      } else {
        selectedDate = `${curMonthPrefix}-01`;
      }
    }

    selectDate(selectedDate);

  } catch (err) {
    showToast('Failed to load calendar data: ' + err.message, 'error');
  }
}

/**
 * Render the interactive calendar grid with real activity indicators
 */
function renderCalendarGrid(data) {
  const gridEl = document.getElementById('calendar-days-grid');
  if (!gridEl) return;

  gridEl.innerHTML = '';

  const firstDay = new Date(selectedYear, selectedMonth - 1, 1);
  let firstDayOfWeek = firstDay.getDay() - 1; // Mon = 0, Sun = 6
  if (firstDayOfWeek === -1) firstDayOfWeek = 6;

  // Leading empty cells
  for (let i = 0; i < firstDayOfWeek; i++) {
    const emptyCell = document.createElement('div');
    emptyCell.className = 'calendar-cell empty';
    gridEl.appendChild(emptyCell);
  }

  const todayStr = formatDateInput(new Date());

  // Render active month days
  for (let d = 1; d <= data.days_in_month; d++) {
    const dtStr = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const dayEntry = data.days[dtStr] || { indicator: 'none', count: 0 };

    const cell = document.createElement('div');
    cell.className = 'calendar-cell';
    cell.id = `cal-cell-${dtStr}`;
    cell.setAttribute('data-date', dtStr);
    cell.setAttribute('role', 'button');
    cell.setAttribute('tabindex', '0');
    cell.setAttribute('aria-label', `${d} ${data.month_name}`);

    if (dtStr === todayStr) {
      cell.classList.add('today');
    }
    if (dtStr === selectedDate) {
      cell.classList.add('selected');
    }

    let indicatorHtml = '';
    if (dayEntry.indicator === 'both') {
      indicatorHtml = '<span class="cal-dot cal-dot-both" title="Income & Expense"></span>';
    } else if (dayEntry.indicator === 'income') {
      indicatorHtml = '<span class="cal-dot cal-dot-income" title="Income"></span>';
    } else if (dayEntry.indicator === 'expense') {
      indicatorHtml = '<span class="cal-dot cal-dot-expense" title="Expense"></span>';
    }

    cell.innerHTML = `
      <span class="cal-date-num">${d}</span>
      <div class="cal-indicators">
        ${indicatorHtml}
      </div>
    `;

    cell.addEventListener('click', () => selectDate(dtStr));
    gridEl.appendChild(cell);
  }

  // Trailing empty cells to fill the row
  const totalRendered = firstDayOfWeek + data.days_in_month;
  const remainder = totalRendered % 7;
  if (remainder > 0) {
    const fillerCount = 7 - remainder;
    for (let i = 0; i < fillerCount; i++) {
      const emptyCell = document.createElement('div');
      emptyCell.className = 'calendar-cell empty';
      gridEl.appendChild(emptyCell);
    }
  }
}

/**
 * Handle user selection of a specific calendar date
 */
function selectDate(dtStr) {
  selectedDate = dtStr;

  // Update grid visual selection
  const allCells = document.querySelectorAll('.calendar-cell');
  allCells.forEach(c => c.classList.remove('selected'));

  const activeCell = document.getElementById(`cal-cell-${dtStr}`);
  if (activeCell) {
    activeCell.classList.add('selected');
  }

  // Format date display (e.g. "5 October 2026")
  const parts = dtStr.split('-');
  const y = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10) - 1;
  const d = parseInt(parts[2], 10);
  const dateObj = new Date(y, m, d);

  const formattedDate = dateObj.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  });

  const headingEl = document.getElementById('selected-date-heading');
  const subtitleEl = document.getElementById('selected-date-subtitle');
  if (headingEl) headingEl.textContent = formattedDate;

  // Filter transactions for this day from current month dataset
  const dayTransactions = (currentMonthData && currentMonthData.transactions)
    ? currentMonthData.transactions.filter(t => t.transaction_date === dtStr)
    : [];

  // Calculate daily totals
  let dailyIncome = 0;
  let dailyExpense = 0;

  dayTransactions.forEach(t => {
    if (t.type === 'income') {
      dailyIncome += Number(t.amount);
    } else {
      dailyExpense += Number(t.amount);
    }
  });

  const dailyNet = dailyIncome - dailyExpense;

  // Render Daily Summary KPIs
  const dayIncEl = document.getElementById('day-income');
  const dayExpEl = document.getElementById('day-expense');
  const dayNetEl = document.getElementById('day-net');

  if (dayIncEl) dayIncEl.textContent = formatCurrency(dailyIncome, userCurrency);
  if (dayExpEl) dayExpEl.textContent = formatCurrency(dailyExpense, userCurrency);
  if (dayNetEl) {
    dayNetEl.textContent = formatCurrency(dailyNet, userCurrency);
    dayNetEl.className = dailyNet >= 0 ? 'day-stat-amount amount-income' : 'day-stat-amount amount-expense';
  }

  if (subtitleEl) {
    subtitleEl.textContent = `${dayTransactions.length} transaction${dayTransactions.length === 1 ? '' : 's'} recorded`;
  }

  // Render Daily Transaction List
  renderDailyTransactions(dayTransactions);
}

/**
 * Return styled HTML badge for transaction payment source
 */
function getSourceBadge(source) {
  const s = (source || '').toLowerCase().trim();
  if (s === 'phonepe') {
    return `<span class="source-badge source-badge-phonepe">📱 PhonePe</span>`;
  } else if (s === 'cash') {
    return `<span class="source-badge source-badge-cash">💵 Cash</span>`;
  } else if (s === 'bank') {
    return `<span class="source-badge source-badge-bank">🏦 Bank</span>`;
  } else {
    return `<span class="source-badge source-badge-manual">✍️ Manual</span>`;
  }
}

/**
 * Render individual transactions for the selected day
 */
function renderDailyTransactions(transactions) {
  const listEl = document.getElementById('daily-tx-list');
  const emptyEl = document.getElementById('day-empty-state');
  if (!listEl) return;

  if (!transactions || transactions.length === 0) {
    listEl.innerHTML = '';
    if (emptyEl) emptyEl.style.display = 'flex';
    return;
  }

  if (emptyEl) emptyEl.style.display = 'none';

  listEl.innerHTML = transactions.map(tx => {
    const isIncome = tx.type === 'income';
    const amountClass = isIncome ? 'amount-income' : 'amount-expense';
    const prefix = isIncome ? '+' : '-';
    const sourceBadge = getSourceBadge(tx.source);
    const timeStr = tx.transaction_time ? escapeHtml(tx.transaction_time) : 'Time not available';

    return `
      <div class="daily-tx-item">
        <div class="daily-tx-left">
          <div class="daily-tx-time">${timeStr}</div>
          <div class="daily-tx-desc" title="${escapeHtml(tx.description)}">${escapeHtml(tx.description)}</div>
          <div class="daily-tx-badges">
            <span style="display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.75rem; font-weight: 600; color: var(--text-secondary);">
              <span style="width: 8px; height: 8px; border-radius: 50%; background-color: ${tx.category_color || '#6366F1'};"></span>
              ${escapeHtml(tx.category_name || 'General')}
            </span>
            ${sourceBadge}
          </div>
        </div>
        <div class="daily-tx-right">
          <div class="daily-tx-amount ${amountClass}">${prefix}${formatCurrency(tx.amount, userCurrency)}</div>
          <div style="margin-top: 0.25rem;">
            <a href="/pages/transactions.html?search=${encodeURIComponent(tx.description)}" class="btn-ghost" style="font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; text-decoration: none;" title="View in Transactions">
              View
            </a>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Generate PDF financial statement for currently selected month and year
 */
async function downloadMonthlyPdf() {
  const btn = document.getElementById('generate-monthly-pdf-btn');
  const originalText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>Generating PDF...</span>';
  }

  try {
    const filename = `ExpenseFlow_Statement_${selectedYear}_${String(selectedMonth).padStart(2, '0')}.pdf`;
    await ApiClient.downloadFile('/reports/monthly-pdf', {
      month: selectedMonth,
      year: selectedYear
    }, filename);
    showToast(`Monthly statement for ${MONTH_NAMES[selectedMonth - 1]} ${selectedYear} downloaded successfully!`, 'success');
  } catch (err) {
    showToast('Failed to generate PDF: ' + err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }
}

/**
 * Open modal with detailed summary and smart insights for currently selected month and year
 */
async function openMonthlySummaryModal() {
  const modal = document.getElementById('monthly-summary-modal');
  const body = document.getElementById('summary-modal-body');
  const title = document.getElementById('summary-modal-title');
  const subtitle = document.getElementById('summary-modal-subtitle');

  if (!modal || !body) return;
  modal.classList.add('active');

  body.innerHTML = `
    <div class="loading-state" style="padding: 3rem; text-align: center;">
      <div class="spinner" style="margin: 0 auto 1rem;"></div>
      <p style="color: var(--text-secondary); font-size: 0.875rem;">Loading monthly summary...</p>
    </div>
  `;

  try {
    const res = await ApiClient.get('/reports/monthly-summary', {
      month: selectedMonth,
      year: selectedYear
    });

    if (title) title.textContent = `${res.month_name} ${res.year} Financial Summary`;
    if (subtitle) subtitle.textContent = `Comprehensive breakdown for ${res.month_name} ${res.year}`;

    const netClass = res.net_savings >= 0 ? 'amount-income' : 'amount-expense';

    body.innerHTML = `
      <!-- Summary KPIs -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem;">
        <div class="day-stat-card">
          <div class="day-stat-label">Total Income</div>
          <div class="day-stat-amount amount-income">${formatCurrency(res.total_income, userCurrency)}</div>
        </div>
        <div class="day-stat-card">
          <div class="day-stat-label">Total Expenses</div>
          <div class="day-stat-amount amount-expense">${formatCurrency(res.total_expense, userCurrency)}</div>
        </div>
        <div class="day-stat-card">
          <div class="day-stat-label">Net Savings</div>
          <div class="day-stat-amount ${netClass}">${formatCurrency(res.net_savings, userCurrency)}</div>
        </div>
        <div class="day-stat-card">
          <div class="day-stat-label">Savings Rate</div>
          <div class="day-stat-amount" style="color: var(--primary);">${res.savings_rate}%</div>
        </div>
      </div>

      <!-- Source Breakdown -->
      <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.75rem;">Payment Source Breakdown</h4>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem;">
        ${(res.source_breakdown || []).map(s => `
          <div style="background: var(--bg-subtle); border-radius: var(--radius-md); padding: 0.85rem; border: 1px solid var(--border-subtle);">
            <div style="font-weight: 700; font-size: 0.875rem; margin-bottom: 0.4rem;">${escapeHtml(s.label)}</div>
            <div style="font-size: 0.8rem; color: var(--text-muted); display: flex; justify-content: space-between; margin-bottom: 0.2rem;">
              <span>Income:</span>
              <strong class="amount-income">${formatCurrency(s.income, userCurrency)}</strong>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); display: flex; justify-content: space-between; margin-bottom: 0.2rem;">
              <span>Expenses:</span>
              <strong class="amount-expense">${formatCurrency(s.expense, userCurrency)}</strong>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-main); display: flex; justify-content: space-between; border-top: 1px solid var(--border-subtle); padding-top: 0.3rem; margin-top: 0.3rem;">
              <span>Net:</span>
              <strong>${formatCurrency(s.net, userCurrency)}</strong>
            </div>
          </div>
        `).join('')}
      </div>

      <!-- Top Spending Categories -->
      ${res.top_categories && res.top_categories.length > 0 ? `
        <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.75rem;">Top Spending Categories</h4>
        <div style="display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1.5rem;">
          ${res.top_categories.map(c => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.6rem 0.85rem; background: var(--bg-subtle); border-radius: var(--radius-md);">
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="width: 10px; height: 10px; border-radius: 50%; background-color: ${c.category_color};"></span>
                <span style="font-weight: 600; font-size: 0.875rem;">${escapeHtml(c.category_name)}</span>
              </div>
              <div style="text-align: right;">
                <strong style="font-size: 0.875rem;">${formatCurrency(c.amount, userCurrency)}</strong>
                <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 0.5rem;">(${c.percentage}%)</span>
              </div>
            </div>
          `).join('')}
        </div>
      ` : ''}

      <!-- Insights -->
      ${res.insights && res.insights.length > 0 ? `
        <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.75rem;">Smart Financial Insights</h4>
        <ul style="padding-left: 1.25rem; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6;">
          ${res.insights.map(i => `<li>${escapeHtml(i)}</li>`).join('')}
        </ul>
      ` : ''}
    `;

  } catch (err) {
    body.innerHTML = `
      <div style="padding: 2rem; text-align: center; color: var(--danger);">
        <p>Failed to load monthly summary: ${escapeHtml(err.message)}</p>
      </div>
    `;
  }
}

/**
 * Close Monthly Summary Modal
 */
function closeMonthlySummaryModal() {
  const modal = document.getElementById('monthly-summary-modal');
  if (modal) modal.classList.remove('active');
}

/**
 * Fallback HTML escaping
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
