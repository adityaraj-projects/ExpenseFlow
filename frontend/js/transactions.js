/**
 * ExpenseFlow - Transactions Management Controller
 */

let currentPage = 1;
let currentFilters = {
  search: '',
  type: '',
  category_id: '',
  start_date: '',
  end_date: '',
  sort_by: 'date',
  sort_order: 'desc'
};
let categoriesList = [];
let editingTransactionId = null;

document.addEventListener('DOMContentLoaded', async () => {
  Auth.initAppShell('transactions');
  await loadCategories();
  initFilters();
  initModals();
  await loadTransactions();
});

async function loadCategories() {
  try {
    categoriesList = await ApiClient.get('/categories');
    const filterSelect = document.getElementById('filter-category');
    const modalSelect = document.getElementById('modal-tx-category');

    const options = categoriesList.map(c => `
      <option value="${c.id}">${escapeHtml(c.name)} (${c.type})</option>
    `).join('');

    if (filterSelect) {
      filterSelect.innerHTML = `<option value="">All Categories</option>` + options;
    }
    if (modalSelect) {
      modalSelect.innerHTML = options;
    }
  } catch (err) {
    console.error('Failed to load categories:', err);
  }
}

async function loadTransactions(page = 1) {
  currentPage = page;
  const tbody = document.getElementById('transactions-tbody');
  const emptyState = document.getElementById('tx-empty-state');
  const user = Auth.getCurrentUser();
  const currency = user ? user.currency : 'INR';

  tbody.innerHTML = Array.from({ length: 6 }).map(() => `
    <tr>
      <td><div class="skeleton" style="height: 16px; width: 75px; border-radius: 4px;"></div></td>
      <td><div class="skeleton" style="height: 16px; width: 180px; border-radius: 4px;"></div></td>
      <td><div class="skeleton" style="height: 16px; width: 90px; border-radius: 4px;"></div></td>
      <td><div class="skeleton" style="height: 20px; width: 55px; border-radius: 10px;"></div></td>
      <td style="text-align: right;"><div class="skeleton" style="height: 16px; width: 80px; border-radius: 4px; margin-left: auto;"></div></td>
      <td style="text-align: right;"><div class="skeleton" style="height: 24px; width: 50px; border-radius: 4px; margin-left: auto;"></div></td>
    </tr>
  `).join('');

  try {
    const params = {
      page: currentPage,
      page_size: 15,
      ...currentFilters
    };

    const res = await ApiClient.get('/transactions', params);

    // Update Filter Aggregates Summary Bar
    document.getElementById('summary-filtered-income').textContent = formatCurrency(res.total_income, currency);
    document.getElementById('summary-filtered-expense').textContent = formatCurrency(res.total_expense, currency);
    const net = Number(res.total_income) - Number(res.total_expense);
    const netEl = document.getElementById('summary-filtered-net');
    netEl.textContent = formatCurrency(net, currency);
    netEl.className = net >= 0 ? 'amount-income' : 'amount-expense';

    // Render Table Rows
    if (!res.items || res.items.length === 0) {
      tbody.innerHTML = '';
      if (emptyState) emptyState.style.display = 'flex';
      renderPagination(0, 0, 15);
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    tbody.innerHTML = res.items.map(tx => {
      const isIncome = tx.type === 'income';
      const amountClass = isIncome ? 'amount-income' : 'amount-expense';
      const prefix = isIncome ? '+' : '-';
      const badgeClass = isIncome ? 'badge-income' : 'badge-expense';
      const catName = tx.category ? tx.category.name : 'General';
      const catColor = tx.category ? tx.category.color : '#6366F1';

      return `
        <tr>
          <td style="white-space: nowrap; font-size: 0.8125rem; color: var(--text-muted);">
            ${formatDate(tx.transaction_date)}
          </td>
          <td>
            <span style="font-weight: 600; color: var(--text-main);">${escapeHtml(tx.description)}</span>
          </td>
          <td>
            <span style="display: inline-flex; align-items: center; gap: 0.4rem; font-weight: 600;">
              <span style="width: 10px; height: 10px; border-radius: 50%; background-color: ${catColor};"></span>
              ${escapeHtml(catName)}
            </span>
          </td>
          <td>
            <span class="badge ${badgeClass}">${tx.type}</span>
          </td>
          <td class="${amountClass}" style="text-align: right; font-weight: 700; font-size: 0.9375rem;">
            ${prefix}${formatCurrency(tx.amount, currency)}
          </td>
          <td style="text-align: right;">
            <div style="display: inline-flex; gap: 0.35rem;">
              <button class="btn-icon btn-ghost" onclick="openEditModal(${tx.id})" title="Edit Transaction">
                ${getSvgIcon('edit')}
              </button>
              <button class="btn-icon btn-ghost" onclick="confirmDeleteTx(${tx.id}, '${escapeHtml(tx.description)}')" title="Delete" style="color: var(--danger);">
                ${getSvgIcon('trash')}
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    renderPagination(res.total, res.page, res.page_size);

  } catch (err) {
    showToast('Failed to load transactions: ' + err.message, 'error');
  }
}

function renderPagination(total, page, pageSize) {
  const infoEl = document.getElementById('pagination-info');
  const prevBtn = document.getElementById('prev-page-btn');
  const nextBtn = document.getElementById('next-page-btn');
  const totalPages = Math.ceil(total / pageSize) || 1;

  if (infoEl) {
    const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const end = Math.min(total, page * pageSize);
    infoEl.textContent = `Showing ${start}–${end} of ${total} transactions (Page ${page} of ${totalPages})`;
  }

  if (prevBtn) {
    prevBtn.disabled = page <= 1;
    prevBtn.onclick = () => { if (page > 1) loadTransactions(page - 1); };
  }

  if (nextBtn) {
    nextBtn.disabled = page >= totalPages;
    nextBtn.onclick = () => { if (page < totalPages) loadTransactions(page + 1); };
  }
}

function initFilters() {
  const searchInput = document.getElementById('search-input');
  const typeFilter = document.getElementById('filter-type');
  const catFilter = document.getElementById('filter-category');
  const sortFilter = document.getElementById('filter-sort');
  const resetBtn = document.getElementById('reset-filters-btn');

  if (searchInput) {
    searchInput.addEventListener('input', debounce((e) => {
      currentFilters.search = e.target.value.trim();
      loadTransactions(1);
    }, 350));
  }

  if (typeFilter) {
    typeFilter.addEventListener('change', (e) => {
      currentFilters.type = e.target.value;
      loadTransactions(1);
    });
  }

  if (catFilter) {
    catFilter.addEventListener('change', (e) => {
      currentFilters.category_id = e.target.value;
      loadTransactions(1);
    });
  }

  if (sortFilter) {
    sortFilter.addEventListener('change', (e) => {
      const [by, order] = e.target.value.split('-');
      currentFilters.sort_by = by;
      currentFilters.sort_order = order;
      loadTransactions(1);
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      currentFilters = {
        search: '',
        type: '',
        category_id: '',
        start_date: '',
        end_date: '',
        sort_by: 'date',
        sort_order: 'desc'
      };
      if (searchInput) searchInput.value = '';
      if (typeFilter) typeFilter.value = '';
      if (catFilter) catFilter.value = '';
      if (sortFilter) sortFilter.value = 'date-desc';
      loadTransactions(1);
      showToast('Filters reset', 'info');
    });
  }
}

function initModals() {
  const modalOverlay = document.getElementById('tx-modal');
  const openAddBtn = document.getElementById('open-add-tx-btn');
  const closeBtns = document.querySelectorAll('#close-modal-btn, #cancel-modal-btn');
  const form = document.getElementById('tx-form');
  const typeRadios = document.querySelectorAll('input[name="tx-type"]');

  window.openQuickAddModal = () => openAddModal();

  if (openAddBtn) {
    openAddBtn.addEventListener('click', () => openAddModal());
  }

  closeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modalOverlay.classList.remove('active');
    });
  });

  typeRadios.forEach(radio => {
    radio.addEventListener('change', (e) => {
      filterModalCategoriesByType(e.target.value);
    });
  });

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('save-modal-btn');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';

      const type = document.querySelector('input[name="tx-type"]:checked').value;
      const amount = parseFloat(document.getElementById('modal-tx-amount').value);
      const category_id = parseInt(document.getElementById('modal-tx-category').value);
      const description = document.getElementById('modal-tx-desc').value.trim();
      const transaction_date = document.getElementById('modal-tx-date').value;

      try {
        if (editingTransactionId) {
          await ApiClient.put(`/transactions/${editingTransactionId}`, {
            type,
            amount,
            category_id,
            description,
            transaction_date
          });
          showToast('Transaction updated successfully!', 'success');
        } else {
          await ApiClient.post('/transactions', {
            type,
            amount,
            category_id,
            description,
            transaction_date
          });
          showToast('Transaction added successfully!', 'success');
        }

        modalOverlay.classList.remove('active');
        await loadTransactions(currentPage);
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Transaction';
      }
    });
  }
}

function filterModalCategoriesByType(txType) {
  const modalSelect = document.getElementById('modal-tx-category');
  if (!modalSelect) return;

  const filtered = categoriesList.filter(c => c.type === 'both' || c.type === txType);
  modalSelect.innerHTML = filtered.map(c => `
    <option value="${c.id}">${escapeHtml(c.name)}</option>
  `).join('');
}

function openAddModal() {
  editingTransactionId = null;
  document.getElementById('modal-title').textContent = 'Add Transaction';
  document.getElementById('tx-form').reset();
  document.getElementById('modal-tx-date').value = formatDateInput();
  document.querySelector('input[name="tx-type"][value="expense"]').checked = true;
  filterModalCategoriesByType('expense');
  document.getElementById('tx-modal').classList.add('active');
}

async function openEditModal(txId) {
  try {
    const tx = await ApiClient.get(`/transactions/${txId}`);
    editingTransactionId = tx.id;
    document.getElementById('modal-title').textContent = 'Edit Transaction';

    const radio = document.querySelector(`input[name="tx-type"][value="${tx.type}"]`);
    if (radio) radio.checked = true;

    filterModalCategoriesByType(tx.type);
    document.getElementById('modal-tx-category').value = tx.category_id;
    document.getElementById('modal-tx-amount').value = tx.amount;
    document.getElementById('modal-tx-desc').value = tx.description;
    document.getElementById('modal-tx-date').value = tx.transaction_date;

    document.getElementById('tx-modal').classList.add('active');
  } catch (err) {
    showToast('Failed to load transaction details: ' + err.message, 'error');
  }
}

async function confirmDeleteTx(txId, description) {
  if (confirm(`Are you sure you want to delete transaction "${description}"? This action cannot be undone.`)) {
    try {
      await ApiClient.delete(`/transactions/${txId}`);
      showToast('Transaction deleted successfully.', 'success');
      await loadTransactions(currentPage);
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
