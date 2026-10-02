/**
 * ExpenseFlow - Transactions Management Controller
 * Includes PhonePe PDF Statement Import & Cash/Manual Transactions
 */

let currentPage = 1;
let currentFilters = {
  search: '',
  type: '',
  category_id: '',
  source: '',
  start_date: '',
  end_date: '',
  sort_by: 'date',
  sort_order: 'desc'
};
let categoriesList = [];
let editingTransactionId = null;
let parsedStatementData = null;

document.addEventListener('DOMContentLoaded', async () => {
  Auth.initAppShell('transactions');
  await loadCategories();
  initFilters();
  initModals();
  initImportStatementModal();
  await loadTransactions();
  checkUrlActions();
});

function checkUrlActions() {
  const urlParams = new URLSearchParams(window.location.search);
  const action = urlParams.get('action');
  if (action === 'new-expense') {
    openAddModal('expense');
  } else if (action === 'new-income') {
    openAddModal('income');
  } else if (action === 'new') {
    openAddModal('expense');
  } else if (action === 'import') {
    openImportModal();
  }
}

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
  const mobileList = document.getElementById('transactions-mobile-list');
  const emptyState = document.getElementById('tx-empty-state');
  const user = Auth.getCurrentUser();
  const currency = user ? user.currency : 'INR';

  // Desktop table skeleton
  if (tbody) {
    tbody.innerHTML = Array.from({ length: 6 }).map(() => `
      <tr>
        <td><div class="skeleton" style="height: 16px; width: 85px; border-radius: 4px;"></div></td>
        <td><div class="skeleton" style="height: 16px; width: 170px; border-radius: 4px;"></div></td>
        <td><div class="skeleton" style="height: 16px; width: 90px; border-radius: 4px;"></div></td>
        <td><div class="skeleton" style="height: 20px; width: 70px; border-radius: 10px;"></div></td>
        <td><div class="skeleton" style="height: 20px; width: 55px; border-radius: 10px;"></div></td>
        <td style="text-align: right;"><div class="skeleton" style="height: 16px; width: 80px; border-radius: 4px; margin-left: auto;"></div></td>
        <td style="text-align: right;"><div class="skeleton" style="height: 24px; width: 50px; border-radius: 4px; margin-left: auto;"></div></td>
      </tr>
    `).join('');
  }

  // Mobile card list skeleton
  if (mobileList) {
    mobileList.innerHTML = Array.from({ length: 4 }).map(() => `
      <div class="tx-card skeleton-card" style="height: 110px;"></div>
    `).join('');
  }

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

    // Handle Empty State
    if (!res.items || res.items.length === 0) {
      if (tbody) tbody.innerHTML = '';
      if (mobileList) mobileList.innerHTML = '';
      if (emptyState) emptyState.style.display = 'flex';
      renderPagination(0, 0, 15);
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    // Render Table Rows (Desktop)
    if (tbody) {
      tbody.innerHTML = res.items.map(tx => {
        const isIncome = tx.type === 'income';
        const amountClass = isIncome ? 'amount-income' : 'amount-expense';
        const prefix = isIncome ? '+' : '-';
        const badgeClass = isIncome ? 'badge-income' : 'badge-expense';
        const catName = tx.category ? tx.category.name : 'General';
        const catColor = tx.category ? tx.category.color : '#6366F1';
        const isPhonePe = (tx.source || '').toLowerCase() === 'phonepe';
        const sourceBadge = isPhonePe
          ? `<span class="source-badge source-badge-phonepe">📱 PhonePe</span>`
          : `<span class="source-badge source-badge-cash">💵 Cash</span>`;

        const timeHtml = tx.transaction_time
          ? `<div style="font-size: 0.725rem; color: var(--text-muted); margin-top: 2px;">${escapeHtml(tx.transaction_time)}</div>`
          : '';

        return `
          <tr>
            <td style="white-space: nowrap; font-size: 0.8125rem; color: var(--text-muted);">
              ${formatDate(tx.transaction_date)}
              ${timeHtml}
            </td>
            <td>
              <span style="font-weight: 600; color: var(--text-main);">${escapeHtml(tx.description)}</span>
              ${tx.external_transaction_id ? `<div style="font-size: 0.7rem; color: var(--text-muted); font-family: monospace;">ID: ${escapeHtml(tx.external_transaction_id)}</div>` : ''}
            </td>
            <td>
              <span style="display: inline-flex; align-items: center; gap: 0.4rem; font-weight: 600;">
                <span style="width: 10px; height: 10px; border-radius: 50%; background-color: ${catColor};"></span>
                ${escapeHtml(catName)}
              </span>
            </td>
            <td>
              ${sourceBadge}
            </td>
            <td>
              <span class="badge ${badgeClass}">${tx.type}</span>
            </td>
            <td class="${amountClass}" style="text-align: right; font-weight: 700; font-size: 0.9375rem;">
              ${prefix}${formatCurrency(tx.amount, currency)}
            </td>
            <td style="text-align: right;">
              <div style="display: inline-flex; gap: 0.35rem;">
                <button class="btn-icon btn-ghost" onclick="openEditModal(${tx.id})" title="Edit Transaction" aria-label="Edit">
                  ${getSvgIcon('edit')}
                </button>
                <button class="btn-icon btn-ghost" onclick="confirmDeleteTx(${tx.id}, '${escapeHtml(tx.description)}')" title="Delete" aria-label="Delete" style="color: var(--danger);">
                  ${getSvgIcon('trash')}
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    // Render Mobile Cards (Mobile <= 768px)
    if (mobileList) {
      mobileList.innerHTML = res.items.map(tx => {
        const isIncome = tx.type === 'income';
        const amountClass = isIncome ? 'amount-income' : 'amount-expense';
        const prefix = isIncome ? '+' : '-';
        const badgeClass = isIncome ? 'badge-income' : 'badge-expense';
        const catName = tx.category ? tx.category.name : 'General';
        const catColor = tx.category ? tx.category.color : '#6366F1';
        const isPhonePe = (tx.source || '').toLowerCase() === 'phonepe';
        const sourceBadge = isPhonePe
          ? `<span class="source-badge source-badge-phonepe">📱 PhonePe</span>`
          : `<span class="source-badge source-badge-cash">💵 Cash</span>`;

        return `
          <div class="tx-card">
            <div class="tx-card-top">
              <div style="min-width: 0; flex: 1;">
                <div class="tx-card-category" style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                  <span style="display: inline-flex; align-items: center; gap: 0.35rem;">
                    <span style="width: 8px; height: 8px; border-radius: 50%; background-color: ${catColor}; flex-shrink: 0;"></span>
                    <span>${escapeHtml(catName)}</span>
                  </span>
                  ${sourceBadge}
                </div>
                <div class="tx-card-desc">${escapeHtml(tx.description)}</div>
                ${tx.external_transaction_id ? `<div style="font-size: 0.7rem; color: var(--text-muted); font-family: monospace; margin-top: 2px;">ID: ${escapeHtml(tx.external_transaction_id)}</div>` : ''}
              </div>
              <div class="tx-card-amount-wrap">
                <div class="tx-card-amount ${amountClass}">${prefix}${formatCurrency(tx.amount, currency)}</div>
                <span class="badge ${badgeClass}" style="margin-top: 0.25rem;">${tx.type}</span>
              </div>
            </div>
            <div class="tx-card-meta">
              <div class="tx-card-date">
                ${getSvgIcon('clock')}
                <span>${formatDate(tx.transaction_date)}${tx.transaction_time ? ' • ' + escapeHtml(tx.transaction_time) : ''}</span>
              </div>
              <div class="tx-card-actions">
                <button class="tx-card-action-btn" onclick="openEditModal(${tx.id})" title="Edit" aria-label="Edit Transaction">
                  ${getSvgIcon('edit')}
                  <span>Edit</span>
                </button>
                <button class="tx-card-action-btn delete-btn" onclick="confirmDeleteTx(${tx.id}, '${escapeHtml(tx.description)}')" title="Delete" aria-label="Delete Transaction">
                  ${getSvgIcon('trash')}
                  <span>Delete</span>
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

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
  const sourceFilter = document.getElementById('filter-source');
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

  if (sourceFilter) {
    sourceFilter.addEventListener('change', (e) => {
      currentFilters.source = e.target.value;
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
        source: '',
        start_date: '',
        end_date: '',
        sort_by: 'date',
        sort_order: 'desc'
      };
      if (searchInput) searchInput.value = '';
      if (typeFilter) typeFilter.value = '';
      if (catFilter) catFilter.value = '';
      if (sourceFilter) sourceFilter.value = '';
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
      const source = document.querySelector('input[name="tx-source"]:checked')?.value || 'cash';
      const amount = parseFloat(document.getElementById('modal-tx-amount').value);
      const category_id = parseInt(document.getElementById('modal-tx-category').value);
      const description = document.getElementById('modal-tx-desc').value.trim();
      const transaction_date = document.getElementById('modal-tx-date').value;
      const transaction_time = document.getElementById('modal-tx-time')?.value?.trim() || null;

      try {
        if (editingTransactionId) {
          await ApiClient.put(`/transactions/${editingTransactionId}`, {
            type,
            source,
            amount,
            category_id,
            description,
            transaction_date,
            transaction_time
          });
          showToast('Transaction updated successfully!', 'success');
        } else {
          await ApiClient.post('/transactions', {
            type,
            source,
            amount,
            category_id,
            description,
            transaction_date,
            transaction_time
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

  const targetType = (txType || 'expense').toLowerCase();
  const filtered = (categoriesList || []).filter(c => {
    const cType = (c.type || '').toLowerCase();
    return cType === 'both' || cType === targetType;
  });

  if (filtered.length === 0) {
    modalSelect.innerHTML = `<option value="">No ${targetType} categories found</option>`;
    return;
  }

  modalSelect.innerHTML = filtered.map(c => `
    <option value="${c.id}">${escapeHtml(c.name)}</option>
  `).join('');
}

function openAddModal(defaultType = 'expense') {
  editingTransactionId = null;
  const isIncome = (defaultType || '').toLowerCase() === 'income';
  document.getElementById('modal-title').textContent = isIncome ? 'Add Income' : 'Add Expense';
  document.getElementById('tx-form').reset();
  document.getElementById('modal-tx-date').value = formatDateInput();
  if (document.getElementById('modal-tx-time')) {
    document.getElementById('modal-tx-time').value = '';
  }

  const radio = document.querySelector(`input[name="tx-type"][value="${isIncome ? 'income' : 'expense'}"]`);
  if (radio) radio.checked = true;

  const srcCash = document.querySelector('input[name="tx-source"][value="cash"]');
  if (srcCash) srcCash.checked = true;

  filterModalCategoriesByType(isIncome ? 'income' : 'expense');
  document.getElementById('tx-modal').classList.add('active');
}

async function openEditModal(txId) {
  try {
    const tx = await ApiClient.get(`/transactions/${txId}`);
    editingTransactionId = tx.id;
    document.getElementById('modal-title').textContent = 'Edit Transaction';

    const radio = document.querySelector(`input[name="tx-type"][value="${tx.type}"]`);
    if (radio) radio.checked = true;

    const sourceVal = (tx.source || 'cash').toLowerCase();
    const srcRadio = document.querySelector(`input[name="tx-source"][value="${sourceVal === 'phonepe' ? 'phonepe' : 'cash'}"]`);
    if (srcRadio) srcRadio.checked = true;

    filterModalCategoriesByType(tx.type);
    document.getElementById('modal-tx-category').value = tx.category_id;
    document.getElementById('modal-tx-amount').value = tx.amount;
    document.getElementById('modal-tx-desc').value = tx.description;
    document.getElementById('modal-tx-date').value = tx.transaction_date;
    if (document.getElementById('modal-tx-time')) {
      document.getElementById('modal-tx-time').value = tx.transaction_time || '';
    }

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

/* ==========================================================
   PhonePe Statement Import Controller
   ========================================================== */
function initImportStatementModal() {
  const openImportBtn = document.getElementById('open-import-modal-btn');
  const importModal = document.getElementById('import-modal');
  const closeImportBtn = document.getElementById('close-import-modal-btn');
  const cancelImportBtn = document.getElementById('import-cancel-btn');
  const choosePdfBtn = document.getElementById('choose-pdf-btn');
  const fileInput = document.getElementById('statement-file-input');
  const dropzone = document.getElementById('import-dropzone');
  const masterCheckbox = document.getElementById('prev-master-checkbox');
  const selectAllBtn = document.getElementById('prev-select-all-btn');
  const deselectAllBtn = document.getElementById('prev-deselect-all-btn');
  const confirmImportBtn = document.getElementById('confirm-import-btn');

  if (openImportBtn) {
    openImportBtn.addEventListener('click', openImportModal);
  }

  if (closeImportBtn) {
    closeImportBtn.addEventListener('click', closeImportModal);
  }

  if (cancelImportBtn) {
    cancelImportBtn.addEventListener('click', closeImportModal);
  }

  if (choosePdfBtn && fileInput) {
    choosePdfBtn.addEventListener('click', () => fileInput.click());
  }

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) handleStatementUpload(file);
    });
  }

  // Drag and drop handling
  if (dropzone) {
    ['dragenter', 'dragover'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-active');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-active');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      const file = e.dataTransfer.files[0];
      if (file) handleStatementUpload(file);
    });
  }

  // Master selection checkbox
  if (masterCheckbox) {
    masterCheckbox.addEventListener('change', (e) => {
      const checked = e.target.checked;
      toggleAllTransactions(checked);
    });
  }

  if (selectAllBtn) {
    selectAllBtn.addEventListener('click', () => toggleAllTransactions(true));
  }

  if (deselectAllBtn) {
    deselectAllBtn.addEventListener('click', () => toggleAllTransactions(false));
  }

  if (confirmImportBtn) {
    confirmImportBtn.addEventListener('click', confirmImportTransactions);
  }
}

function openImportModal() {
  parsedStatementData = null;
  const modal = document.getElementById('import-modal');
  const uploadStep = document.getElementById('import-upload-step');
  const previewStep = document.getElementById('import-preview-step');
  const dropzone = document.getElementById('import-dropzone');
  const uploadingState = document.getElementById('import-uploading-state');
  const fileInput = document.getElementById('statement-file-input');

  if (fileInput) fileInput.value = '';
  if (uploadStep) uploadStep.style.display = 'block';
  if (previewStep) previewStep.style.display = 'none';
  if (dropzone) dropzone.style.display = 'block';
  if (uploadingState) uploadingState.style.display = 'none';

  if (modal) modal.classList.add('active');
}

function closeImportModal() {
  const modal = document.getElementById('import-modal');
  if (modal) modal.classList.remove('active');
  parsedStatementData = null;
}

async function handleStatementUpload(file) {
  if (!file) return;

  // Validate format
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Only PDF files (.pdf) are supported. Please upload a valid PhonePe statement.', 'error');
    return;
  }

  // Validate size (15MB)
  if (file.size > 15 * 1024 * 1024) {
    showToast('File size exceeds the 15MB limit. Please upload a smaller PDF statement.', 'error');
    return;
  }

  const dropzone = document.getElementById('import-dropzone');
  const uploadingState = document.getElementById('import-uploading-state');

  if (dropzone) dropzone.style.display = 'none';
  if (uploadingState) uploadingState.style.display = 'block';

  try {
    const formData = new FormData();
    formData.append('file', file);

    const result = await ApiClient.postFormData('/statements/parse-phonepe', formData);
    parsedStatementData = result;

    renderImportPreview(result);

  } catch (err) {
    showToast(err.message, 'error');
    if (dropzone) dropzone.style.display = 'block';
    if (uploadingState) uploadingState.style.display = 'none';
  }
}

function renderImportPreview(data) {
  const uploadStep = document.getElementById('import-upload-step');
  const previewStep = document.getElementById('import-preview-step');
  const user = Auth.getCurrentUser();
  const currency = user ? user.currency : 'INR';

  if (uploadStep) uploadStep.style.display = 'none';
  if (previewStep) previewStep.style.display = 'flex';

  // Summary counts
  document.getElementById('prev-total-count').textContent = data.total_count;
  document.getElementById('prev-new-count').textContent = data.new_count;
  document.getElementById('prev-dup-count').textContent = data.duplicate_count;

  updateSelectedCount();

  const tbody = document.getElementById('import-preview-tbody');
  const mobileList = document.getElementById('import-preview-mobile-list');

  // Build category options for each type
  const expenseCatOptions = (data.user_categories || [])
    .filter(c => c.type === 'expense' || c.type === 'both')
    .map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
    .join('');

  const incomeCatOptions = (data.user_categories || [])
    .filter(c => c.type === 'income' || c.type === 'both')
    .map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
    .join('');

  // 1. Desktop Table
  if (tbody) {
    tbody.innerHTML = data.items.map((it, idx) => {
      const isIncome = it.type === 'income';
      const badgeClass = isIncome ? 'badge-income' : 'badge-expense';
      const amountClass = isIncome ? 'amount-income' : 'amount-expense';
      const catOptions = isIncome ? incomeCatOptions : expenseCatOptions;
      const statusBadge = it.is_duplicate
        ? `<span class="badge" style="background: rgba(245, 158, 11, 0.12); color: #D97706; font-size: 0.75rem; border: 1px solid rgba(245, 158, 11, 0.25);" title="${escapeHtml(it.duplicate_reason)}">Already Imported</span>`
        : `<span class="badge" style="background: rgba(16, 185, 129, 0.12); color: #059669; font-size: 0.75rem; border: 1px solid rgba(16, 185, 129, 0.25);">New</span>`;

      return `
        <tr class="${it.is_duplicate ? 'import-row-dup' : ''}">
          <td style="text-align: center;">
            <input type="checkbox"
                   id="prev-check-${idx}"
                   data-idx="${idx}"
                   ${it.is_selected ? 'checked' : ''}
                   ${it.is_duplicate ? 'disabled' : ''}
                   onchange="onPreviewItemCheckChange(${idx}, this.checked)"
                   style="cursor: ${it.is_duplicate ? 'not-allowed' : 'pointer'}; width: 16px; height: 16px;">
          </td>
          <td style="white-space: nowrap; font-size: 0.8125rem;">
            ${formatDate(it.transaction_date)}
            <div style="font-size: 0.7rem; color: var(--text-muted);">${escapeHtml(it.transaction_time || '')}</div>
          </td>
          <td>
            <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(it.description)}</div>
            ${it.external_transaction_id ? `<div style="font-size: 0.7rem; color: var(--text-muted); font-family: monospace;">ID: ${escapeHtml(it.external_transaction_id)}</div>` : ''}
          </td>
          <td>
            <span class="badge ${badgeClass}">${it.type}</span>
          </td>
          <td class="${amountClass}" style="text-align: right; font-weight: 700;">
            ${isIncome ? '+' : '-'}${formatCurrency(it.amount, currency)}
          </td>
          <td>
            <select class="form-select"
                    id="prev-cat-${idx}"
                    style="padding: 0.35rem 0.6rem; font-size: 0.8125rem;"
                    ${it.is_duplicate ? 'disabled' : ''}
                    onchange="onPreviewCategoryChange(${idx}, this.value)">
              ${catOptions}
            </select>
          </td>
          <td>
            ${statusBadge}
          </td>
        </tr>
      `;
    }).join('');

    // Pre-select suggested categories in desktop table
    data.items.forEach((it, idx) => {
      const selectEl = document.getElementById(`prev-cat-${idx}`);
      if (selectEl && it.suggested_category_id) {
        selectEl.value = it.suggested_category_id;
      }
    });
  }

  // 2. Mobile Cards
  if (mobileList) {
    mobileList.innerHTML = data.items.map((it, idx) => {
      const isIncome = it.type === 'income';
      const badgeClass = isIncome ? 'badge-income' : 'badge-expense';
      const amountClass = isIncome ? 'amount-income' : 'amount-expense';
      const catOptions = isIncome ? incomeCatOptions : expenseCatOptions;
      const statusBadge = it.is_duplicate
        ? `<span class="badge" style="background: rgba(245, 158, 11, 0.12); color: #D97706; font-size: 0.75rem; border: 1px solid rgba(245, 158, 11, 0.25);" title="${escapeHtml(it.duplicate_reason)}">Already Imported</span>`
        : `<span class="badge" style="background: rgba(16, 185, 129, 0.12); color: #059669; font-size: 0.75rem; border: 1px solid rgba(16, 185, 129, 0.25);">New</span>`;

      return `
        <div class="import-preview-card ${it.is_duplicate ? 'import-card-dup' : ''}">
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 0.75rem;">
            <div style="display: flex; align-items: center; gap: 0.65rem; min-width: 0; flex: 1;">
              <input type="checkbox"
                     id="prev-check-m-${idx}"
                     data-idx="${idx}"
                     ${it.is_selected ? 'checked' : ''}
                     ${it.is_duplicate ? 'disabled' : ''}
                     onchange="onPreviewItemCheckChange(${idx}, this.checked)"
                     style="cursor: ${it.is_duplicate ? 'not-allowed' : 'pointer'}; width: 18px; height: 18px; flex-shrink: 0;">
              <div style="min-width: 0;">
                <div style="font-weight: 700; font-size: 0.875rem; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                  ${escapeHtml(it.description)}
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">
                  ${formatDate(it.transaction_date)} • ${escapeHtml(it.transaction_time || '')}
                </div>
              </div>
            </div>
            <div style="text-align: right; flex-shrink: 0;">
              <div class="${amountClass}" style="font-weight: 800; font-size: 0.95rem;">
                ${isIncome ? '+' : '-'}${formatCurrency(it.amount, currency)}
              </div>
              <div style="margin-top: 2px;">${statusBadge}</div>
            </div>
          </div>

          <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-top: 0.75rem; padding-top: 0.65rem; border-top: 1px dashed var(--border-subtle);">
            <span style="font-size: 0.775rem; font-weight: 600; color: var(--text-secondary);">Category:</span>
            <select class="form-select"
                    id="prev-cat-m-${idx}"
                    style="max-width: 220px; font-size: 0.8125rem; padding: 0.35rem 0.5rem;"
                    ${it.is_duplicate ? 'disabled' : ''}
                    onchange="onPreviewCategoryChange(${idx}, this.value)">
              ${catOptions}
            </select>
          </div>
        </div>
      `;
    }).join('');

    // Pre-select suggested categories in mobile cards
    data.items.forEach((it, idx) => {
      const selectEl = document.getElementById(`prev-cat-m-${idx}`);
      if (selectEl && it.suggested_category_id) {
        selectEl.value = it.suggested_category_id;
      }
    });
  }
}

function onPreviewItemCheckChange(idx, isChecked) {
  if (!parsedStatementData || !parsedStatementData.items[idx]) return;
  parsedStatementData.items[idx].is_selected = isChecked;

  // Sync desktop and mobile checkboxes
  const dCheck = document.getElementById(`prev-check-${idx}`);
  const mCheck = document.getElementById(`prev-check-m-${idx}`);
  if (dCheck) dCheck.checked = isChecked;
  if (mCheck) mCheck.checked = isChecked;

  updateSelectedCount();
}

function onPreviewCategoryChange(idx, catId) {
  if (!parsedStatementData || !parsedStatementData.items[idx]) return;
  const numId = parseInt(catId);
  parsedStatementData.items[idx].category_id = numId;
  parsedStatementData.items[idx].suggested_category_id = numId;

  // Sync desktop and mobile selects
  const dSel = document.getElementById(`prev-cat-${idx}`);
  const mSel = document.getElementById(`prev-cat-m-${idx}`);
  if (dSel) dSel.value = numId;
  if (mSel) mSel.value = numId;
}

function toggleAllTransactions(select) {
  if (!parsedStatementData || !parsedStatementData.items) return;

  parsedStatementData.items.forEach((it, idx) => {
    // Duplicates are never selected
    if (!it.is_duplicate) {
      it.is_selected = select;
      const dCheck = document.getElementById(`prev-check-${idx}`);
      const mCheck = document.getElementById(`prev-check-m-${idx}`);
      if (dCheck) dCheck.checked = select;
      if (mCheck) mCheck.checked = select;
    }
  });

  const master = document.getElementById('prev-master-checkbox');
  if (master) master.checked = select;

  updateSelectedCount();
}

function updateSelectedCount() {
  if (!parsedStatementData || !parsedStatementData.items) return;
  const selectedCount = parsedStatementData.items.filter(it => it.is_selected && !it.is_duplicate).length;

  const countEl = document.getElementById('prev-selected-count');
  const btnCount = document.getElementById('import-btn-count');
  const confirmBtn = document.getElementById('confirm-import-btn');

  if (countEl) countEl.textContent = selectedCount;
  if (btnCount) btnCount.textContent = selectedCount;

  if (confirmBtn) {
    confirmBtn.disabled = selectedCount === 0;
  }
}

async function confirmImportTransactions() {
  if (!parsedStatementData || !parsedStatementData.items) return;

  const toImport = parsedStatementData.items.filter(it => it.is_selected && !it.is_duplicate);
  if (toImport.length === 0) {
    showToast('No transactions selected for import.', 'warning');
    return;
  }

  if (!confirm(`You are about to import ${toImport.length} transactions into ExpenseFlow. Proceed?`)) {
    return;
  }

  const confirmBtn = document.getElementById('confirm-import-btn');
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Importing...';
  }

  try {
    const payload = {
      transactions: toImport.map(it => ({
        transaction_date: it.transaction_date,
        transaction_time: it.transaction_time,
        type: it.type,
        amount: it.amount,
        description: it.description,
        category_id: it.category_id || it.suggested_category_id,
        external_transaction_id: it.external_transaction_id,
        external_utr: it.external_utr,
        source: 'phonepe'
      }))
    };

    const res = await ApiClient.post('/statements/import-phonepe', payload);
    showToast(res.message, 'success');

    closeImportModal();
    await loadTransactions(1);

  } catch (err) {
    showToast('Import failed: ' + err.message, 'error');
  } finally {
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = `Import Selected (<span id="import-btn-count">${toImport.length}</span>)`;
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
