/**
 * ExpenseFlow - Monthly Budgets Controller
 */

let selectedMonth = new Date().getMonth() + 1;
let selectedYear = new Date().getFullYear();
let expenseCategories = [];
let editingBudgetId = null;

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

document.addEventListener('DOMContentLoaded', async () => {
  Auth.initAppShell('budgets');
  initPeriodPickers();
  initModals();
  await loadExpenseCategories();
  await loadBudgets();
});

function initPeriodPickers() {
  const monthSelect = document.getElementById('budget-month-select');
  const yearSelect = document.getElementById('budget-year-select');

  if (monthSelect) {
    monthSelect.innerHTML = MONTH_NAMES.map((name, idx) => `
      <option value="${idx + 1}" ${idx + 1 === selectedMonth ? 'selected' : ''}>${name}</option>
    `).join('');

    monthSelect.addEventListener('change', (e) => {
      selectedMonth = parseInt(e.target.value);
      loadBudgets();
    });
  }

  if (yearSelect) {
    const currentYear = new Date().getFullYear();
    const years = [currentYear - 1, currentYear, currentYear + 1];
    yearSelect.innerHTML = years.map(y => `
      <option value="${y}" ${y === selectedYear ? 'selected' : ''}>${y}</option>
    `).join('');

    yearSelect.addEventListener('change', (e) => {
      selectedYear = parseInt(e.target.value);
      loadBudgets();
    });
  }
}

async function loadExpenseCategories() {
  try {
    const all = await ApiClient.get('/categories');
    expenseCategories = all.filter(c => c.type === 'expense' || c.type === 'both');
    const select = document.getElementById('budget-category-select');
    if (select) {
      select.innerHTML = expenseCategories.map(c => `
        <option value="${c.id}">${escapeHtml(c.name)}</option>
      `).join('');
    }
  } catch (err) {
    console.error('Failed to load categories:', err);
  }
}

async function loadBudgets() {
  const container = document.getElementById('budgets-grid');
  const emptyState = document.getElementById('budgets-empty-state');
  const user = Auth.getCurrentUser();
  const currency = user ? user.currency : 'INR';

  container.innerHTML = Array.from({ length: 3 }).map(() => `
    <div class="card" style="padding: 1.5rem;">
      <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.25rem;">
        <div class="skeleton" style="width: 40px; height: 40px; border-radius: var(--radius-md);"></div>
        <div style="flex: 1;">
          <div class="skeleton" style="height: 16px; width: 110px; margin-bottom: 0.35rem;"></div>
          <div class="skeleton" style="height: 12px; width: 70px;"></div>
        </div>
      </div>
      <div class="skeleton" style="height: 14px; width: 100%; margin-bottom: 0.75rem;"></div>
      <div class="skeleton" style="height: 10px; width: 100%; border-radius: 999px; margin-bottom: 0.75rem;"></div>
      <div style="display: flex; justify-content: space-between;">
        <div class="skeleton" style="height: 12px; width: 50px;"></div>
        <div class="skeleton" style="height: 12px; width: 80px;"></div>
      </div>
    </div>
  `).join('');

  try {
    const res = await ApiClient.get('/budgets', {
      month: selectedMonth,
      year: selectedYear
    });

    // Update Top Summary Cards
    document.getElementById('total-budget-val').textContent = formatCurrency(res.total_budget, currency);
    document.getElementById('total-spent-val').textContent = formatCurrency(res.total_spent, currency);
    const remEl = document.getElementById('total-remaining-val');
    remEl.textContent = formatCurrency(res.remaining, currency);
    remEl.style.color = res.remaining < 0 ? 'var(--danger)' : 'var(--success)';
    document.getElementById('budget-usage-badge').textContent = `${res.percentage_used}% used`;

    if (!res.items || res.items.length === 0) {
      container.innerHTML = '';
      if (emptyState) emptyState.style.display = 'flex';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    container.innerHTML = res.items.map(b => {
      const fillClass = b.status === 'exceeded' ? 'exceeded' : (b.status === 'warning' ? 'warning' : 'safe');
      const widthPct = Math.min(100, b.percentage_used);
      const isExceeded = b.status === 'exceeded';

      return `
        <div class="card" style="position: relative;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <div style="width: 40px; height: 40px; border-radius: var(--radius-md); background-color: ${b.category_color}18; color: ${b.category_color}; display: flex; align-items: center; justify-content: center;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path></svg>
              </div>
              <div>
                <h3 style="font-size: 1.0625rem; font-weight: 700; color: var(--text-main);">${escapeHtml(b.category_name)}</h3>
                <span style="font-size: 0.75rem; color: var(--text-muted);">${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}</span>
              </div>
            </div>

            <div style="display: flex; gap: 0.25rem;">
              <button class="btn-icon btn-ghost" onclick="openEditBudgetModal(${b.id}, ${b.budget_amount}, '${escapeHtml(b.category_name)}')" title="Edit budget">
                ${getSvgIcon('edit')}
              </button>
              <button class="btn-icon btn-ghost" onclick="confirmDeleteBudget(${b.id}, '${escapeHtml(b.category_name)}')" title="Delete budget" style="color: var(--danger);">
                ${getSvgIcon('trash')}
              </button>
            </div>
          </div>

          <div style="margin: 1.25rem 0;">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 0.4rem;">
              <span style="font-size: 0.8125rem; color: var(--text-muted);">Spent: <strong style="color: var(--text-main);">${formatCurrency(b.spent_amount, currency)}</strong></span>
              <span style="font-size: 0.8125rem; color: var(--text-muted);">Limit: <strong>${formatCurrency(b.budget_amount, currency)}</strong></span>
            </div>

            <div class="progress-track" style="height: 10px;">
              <div class="progress-fill ${fillClass}" style="width: ${widthPct}%;"></div>
            </div>

            <div style="display: flex; justify-content: space-between; margin-top: 0.5rem; font-size: 0.75rem;">
              <span style="font-weight: 600; color: ${isExceeded ? 'var(--danger)' : 'var(--text-secondary)'};">
                ${b.percentage_used}% used
              </span>
              <span style="font-weight: 600; color: ${isExceeded ? 'var(--danger)' : 'var(--success)'};">
                ${isExceeded ? 'Over limit by ' + formatCurrency(Math.abs(b.remaining_amount), currency) : formatCurrency(b.remaining_amount, currency) + ' remaining'}
              </span>
            </div>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    showToast('Failed to load budgets: ' + err.message, 'error');
  }
}

function initModals() {
  const modal = document.getElementById('budget-modal');
  const openBtn = document.getElementById('open-create-budget-btn');
  const closeBtns = document.querySelectorAll('#close-budget-modal, #cancel-budget-modal');
  const form = document.getElementById('budget-form');

  if (openBtn) {
    openBtn.addEventListener('click', () => {
      editingBudgetId = null;
      document.getElementById('budget-modal-title').textContent = 'Set Monthly Budget';
      document.getElementById('budget-cat-group').style.display = 'block';
      form.reset();
      modal.classList.add('active');
    });
  }

  closeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modal.classList.remove('active');
    });
  });

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('save-budget-btn');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';

      const amount = parseFloat(document.getElementById('budget-amount-input').value);

      try {
        if (editingBudgetId) {
          await ApiClient.put(`/budgets/${editingBudgetId}`, { amount });
          showToast('Budget amount updated successfully!', 'success');
        } else {
          const category_id = parseInt(document.getElementById('budget-category-select').value);
          await ApiClient.post('/budgets', {
            category_id,
            amount,
            month: selectedMonth,
            year: selectedYear
          });
          showToast('Monthly budget created successfully!', 'success');
        }

        modal.classList.remove('active');
        await loadBudgets();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Budget';
      }
    });
  }
}

function openEditBudgetModal(budgetId, currentAmount, categoryName) {
  editingBudgetId = budgetId;
  document.getElementById('budget-modal-title').textContent = `Edit Budget: ${categoryName}`;
  document.getElementById('budget-cat-group').style.display = 'none';
  document.getElementById('budget-amount-input').value = currentAmount;
  document.getElementById('budget-modal').classList.add('active');
}

async function confirmDeleteBudget(budgetId, categoryName) {
  if (confirm(`Remove monthly budget for "${categoryName}"? Existing transactions will NOT be affected.`)) {
    try {
      await ApiClient.delete(`/budgets/${budgetId}`);
      showToast('Budget deleted successfully.', 'success');
      await loadBudgets();
    } catch (err) {
      showToast(err.message, 'error');
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
