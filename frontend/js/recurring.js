/**
 * ExpenseFlow - Recurring Transactions Controller
 */

const RecurringPage = {
  activeStatus: 'all',
  categories: [],
  recurringList: [],

  async init() {
    Auth.initAppShell('recurring');
    await this.loadCategories();
    await this.loadRecurring();
    this.initBackdropListeners();

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('action') === 'new') {
      this.openCreateModal();
    }
  },

  initBackdropListeners() {
    const modal = document.getElementById('recurring-modal');
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) RecurringPage.closeModal();
      });
    }
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        RecurringPage.closeModal();
      }
    });
  },

  async loadCategories() {
    try {
      this.categories = await ApiClient.get('/categories');
      this.populateCategorySelect('expense');
    } catch (e) {
      console.error('Failed to load categories:', e);
    }
  },

  populateCategorySelect(type = 'expense') {
    const select = document.getElementById('rec-category');
    if (!select) return;

    const targetType = (type || 'expense').toLowerCase();
    const filtered = (this.categories || []).filter(c => {
      const cType = (c.type || '').toLowerCase();
      return cType === 'both' || cType === targetType;
    });

    if (filtered.length === 0) {
      select.innerHTML = `<option value="">No ${targetType} categories</option>`;
      return;
    }

    select.innerHTML = '<option value="">Select Category</option>' +
      filtered.map(c => `<option value="${c.id}">${this.escapeHtml(c.name)}</option>`).join('');
  },

  onTypeChange() {
    const type = document.getElementById('rec-type').value;
    this.populateCategorySelect(type);
  },

  async loadRecurring() {
    const tbody = document.getElementById('recurring-tbody');
    const mobileList = document.getElementById('recurring-mobile-list');

    try {
      let url = '/recurring-transactions';
      if (this.activeStatus !== 'all') {
        url += `?status=${this.activeStatus}`;
      }
      this.recurringList = await ApiClient.get(url);
      this.render();
    } catch (e) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--danger); padding: 2rem;">Failed to load recurring templates.</td></tr>`;
      if (mobileList) mobileList.innerHTML = `<div class="card" style="text-align: center; color: var(--danger); padding: 2rem;">Failed to load recurring templates.</div>`;
    }
  },

  render() {
    const tbody = document.getElementById('recurring-tbody');
    const mobileList = document.getElementById('recurring-mobile-list');

    if (!this.recurringList || this.recurringList.length === 0) {
      const emptyHtml = `
        <div style="text-align: center; padding: 3rem 1rem;">
          <div style="width: 48px; height: 48px; margin: 0 auto 0.75rem; border-radius: var(--radius-full); background: var(--primary-light); color: var(--primary); display: flex; align-items: center; justify-content: center;">
            ${getSvgIcon('recurring')}
          </div>
          <h3 style="font-size: 1rem; margin-bottom: 0.25rem; color: var(--text-main);">No Recurring Transactions</h3>
          <p style="font-size: 0.8125rem; color: var(--text-secondary); max-width: 380px; margin: 0 auto 1.25rem;">
            Automate repeat expenses like rent, utilities, subscriptions, or salaries.
          </p>
          <button class="btn btn-primary btn-sm" onclick="RecurringPage.openCreateModal()">
            ${getSvgIcon('plus')} Add Recurring Template
          </button>
        </div>
      `;

      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="7" style="padding: 0;">${emptyHtml}</td></tr>`;
      }
      if (mobileList) {
        mobileList.innerHTML = emptyHtml;
      }
      return;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Desktop table view
    if (tbody) {
      tbody.innerHTML = this.recurringList.map(r => {
        const nextDate = new Date(r.next_occurrence_date);
        const isDue = nextDate <= today && r.status === 'active';
        const formattedDate = formatDate(r.next_occurrence_date);
        const cat = r.category;
        const isExpense = r.type === 'expense';
        const amountClass = isExpense ? 'amount-expense' : 'amount-income';
        const amountPrefix = isExpense ? '-' : '+';

        let statusBadge = '';
        if (r.status === 'active') {
          statusBadge = `<span class="badge" style="background: var(--success-light); color: var(--success);">Active</span>`;
        } else {
          statusBadge = `<span class="badge" style="background: var(--warning-light); color: var(--warning);">Paused</span>`;
        }

        return `
          <tr>
            <td>
              <div style="font-weight: 600; color: var(--text-main);">${this.escapeHtml(r.description)}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">${r.payment_method || 'Other'}</div>
            </td>
            <td>
              ${cat ? `<span class="badge" style="background: ${cat.color}22; color: ${cat.color};">${this.escapeHtml(cat.name)}</span>` : '—'}
            </td>
            <td>
              <span class="badge" style="background: var(--bg-hover); color: var(--text-secondary); text-transform: capitalize;">${r.frequency}</span>
            </td>
            <td class="${amountClass}">
              ${amountPrefix}${formatCurrency(r.amount)}
            </td>
            <td>
              <div style="font-weight: 600; color: ${isDue ? 'var(--danger)' : 'var(--text-main)'};">
                ${formattedDate}
              </div>
              ${isDue ? '<span style="font-size: 0.6875rem; color: var(--danger); font-weight: 700;">Due for processing</span>' : ''}
            </td>
            <td>${statusBadge}</td>
            <td style="text-align: right;">
              <div style="display: inline-flex; align-items: center; gap: 0.375rem;">
                <button class="icon-btn" onclick="RecurringPage.togglePauseResume(${r.id}, '${r.status}')" title="${r.status === 'active' ? 'Pause' : 'Resume'}">
                  ${r.status === 'active' ? getSvgIcon('pause') : getSvgIcon('play')}
                </button>
                <button class="icon-btn" onclick="RecurringPage.openEditModal(${r.id})" title="Edit template">
                  ${getSvgIcon('edit')}
                </button>
                <button class="icon-btn" style="color: var(--danger);" onclick="RecurringPage.deleteRecurring(${r.id})" title="Delete template">
                  ${getSvgIcon('trash')}
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    // Mobile card list view
    if (mobileList) {
      mobileList.innerHTML = this.recurringList.map(r => {
        const nextDate = new Date(r.next_occurrence_date);
        const isDue = nextDate <= today && r.status === 'active';
        const formattedDate = formatDate(r.next_occurrence_date);
        const cat = r.category;
        const isExpense = r.type === 'expense';
        const amountClass = isExpense ? 'amount-expense' : 'amount-income';
        const amountPrefix = isExpense ? '-' : '+';

        let statusBadge = '';
        if (r.status === 'active') {
          statusBadge = `<span class="badge" style="background: var(--success-light); color: var(--success);">Active</span>`;
        } else {
          statusBadge = `<span class="badge" style="background: var(--warning-light); color: var(--warning);">Paused</span>`;
        }

        return `
          <div class="recurring-card-item">
            <div class="recurring-card-header">
              <div>
                <h4 style="font-size: 0.9375rem; font-weight: 700; color: var(--text-main); margin: 0 0 0.25rem 0;">${this.escapeHtml(r.description)}</h4>
                <div style="display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
                  ${cat ? `<span class="badge" style="background: ${cat.color}22; color: ${cat.color};">${this.escapeHtml(cat.name)}</span>` : ''}
                  <span class="badge" style="background: var(--bg-hover); color: var(--text-secondary); text-transform: capitalize;">${r.frequency}</span>
                  ${statusBadge}
                </div>
              </div>
              <div class="${amountClass}" style="font-size: 1.0625rem; font-weight: 800;">
                ${amountPrefix}${formatCurrency(r.amount)}
              </div>
            </div>

            <div class="recurring-card-body">
              <div>
                <span style="color: var(--text-muted); font-size: 0.75rem;">Next: </span>
                <strong style="color: ${isDue ? 'var(--danger)' : 'var(--text-main)'}; font-size: 0.8125rem;">${formattedDate}</strong>
                ${isDue ? ' <span style="color: var(--danger); font-size: 0.6875rem; font-weight: 700;">(Due)</span>' : ''}
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">${r.payment_method || 'Other'}</div>
            </div>

            <div class="recurring-card-actions">
              <button class="btn btn-secondary btn-sm" onclick="RecurringPage.togglePauseResume(${r.id}, '${r.status}')">
                ${r.status === 'active' ? 'Pause' : 'Resume'}
              </button>
              <button class="icon-btn" onclick="RecurringPage.openEditModal(${r.id})" title="Edit template">
                ${getSvgIcon('edit')}
              </button>
              <button class="icon-btn" style="color: var(--danger);" onclick="RecurringPage.deleteRecurring(${r.id})" title="Delete template">
                ${getSvgIcon('trash')}
              </button>
            </div>
          </div>
        `;
      }).join('');
    }
  },

  filterStatus(status, btn) {
    this.activeStatus = status;
    document.querySelectorAll('.toolbar .report-time-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    this.loadRecurring();
  },

  async openCreateModal() {
    if (!this.categories || this.categories.length === 0) {
      await this.loadCategories();
    }
    document.getElementById('recurring-modal-title').textContent = 'Create Recurring Transaction';
    document.getElementById('recurring-id').value = '';
    document.getElementById('rec-type').value = 'expense';
    this.populateCategorySelect('expense');
    document.getElementById('rec-amount').value = '';
    document.getElementById('rec-desc').value = '';
    document.getElementById('rec-method').value = 'Bank Transfer';
    document.getElementById('rec-frequency').value = 'monthly';
    document.getElementById('rec-start-date').value = formatDateInput(new Date());
    const modal = document.getElementById('recurring-modal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  },

  async openEditModal(id) {
    if (!this.categories || this.categories.length === 0) {
      await this.loadCategories();
    }
    const r = this.recurringList.find(item => item.id === id);
    if (!r) return;

    document.getElementById('recurring-modal-title').textContent = 'Edit Recurring Rule';
    document.getElementById('recurring-id').value = r.id;
    document.getElementById('rec-type').value = r.type;
    this.populateCategorySelect(r.type);
    document.getElementById('rec-amount').value = r.amount;
    document.getElementById('rec-desc').value = r.description;
    document.getElementById('rec-category').value = r.category_id;
    document.getElementById('rec-method').value = r.payment_method || 'Other';
    document.getElementById('rec-frequency').value = r.frequency;
    document.getElementById('rec-start-date').value = r.next_occurrence_date;
    const modal = document.getElementById('recurring-modal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  },

  closeModal() {
    const modal = document.getElementById('recurring-modal');
    if (modal) {
      modal.style.display = 'none';
      modal.classList.remove('active');
    }
  },

  async saveRecurring(e) {
    if (e && e.preventDefault) e.preventDefault();
    const submitBtn = document.getElementById('recurring-submit-btn');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';
    }

    try {
      const id = document.getElementById('recurring-id').value;
      const type = document.getElementById('rec-type').value;
      const amountVal = document.getElementById('rec-amount').value.trim();
      const desc = document.getElementById('rec-desc').value.trim();
      const categoryId = document.getElementById('rec-category').value;
      const method = document.getElementById('rec-method').value;
      const frequency = document.getElementById('rec-frequency').value;
      const startDate = document.getElementById('rec-start-date').value;

      if (!desc || !amountVal || !categoryId || !startDate) {
        showToast('Please fill all required fields.', 'error');
        return;
      }

      const parsedAmount = parseFloat(amountVal);
      if (isNaN(parsedAmount) || parsedAmount <= 0) {
        showToast('Please enter an amount greater than zero.', 'error');
        return;
      }

      const payload = {
        type,
        amount: parsedAmount,
        description: desc,
        category_id: parseInt(categoryId),
        payment_method: method,
        frequency,
        start_date: startDate
      };

      if (id) {
        await ApiClient.put(`/recurring-transactions/${id}`, {
          type,
          amount: parsedAmount,
          description: desc,
          category_id: parseInt(categoryId),
          payment_method: method,
          frequency,
          next_occurrence_date: startDate
        });
        showToast('Recurring rule updated successfully', 'success');
      } else {
        await ApiClient.post('/recurring-transactions', payload);
        showToast('Recurring rule created successfully', 'success');
      }
      RecurringPage.closeModal();
      await RecurringPage.loadRecurring();
    } catch (err) {
      showToast(`Error: ${err.message || 'Could not save recurring rule'}`, 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Rule';
      }
    }
  },

  async togglePauseResume(id, currentStatus) {
    const endpoint = currentStatus === 'active' ? `/recurring-transactions/${id}/pause` : `/recurring-transactions/${id}/resume`;
    try {
      await ApiClient.patch(endpoint, {});
      showToast(currentStatus === 'active' ? 'Rule paused' : 'Rule resumed', 'info');
      await this.loadRecurring();
    } catch (e) {
      showToast('Failed to update status', 'error');
    }
  },

  async deleteRecurring(id) {
    if (!confirm('Are you sure you want to delete this recurring rule? Existing generated transactions will not be deleted.')) return;
    try {
      await ApiClient.delete(`/recurring-transactions/${id}`);
      showToast('Recurring rule deleted', 'success');
      await this.loadRecurring();
    } catch (e) {
      showToast('Failed to delete rule', 'error');
    }
  },

  async processDueNow() {
    try {
      const res = await ApiClient.post('/recurring-transactions/process-now', {});
      showToast(res.message || 'Due transactions processed', 'success');
      await this.loadRecurring();
    } catch (e) {
      showToast('Failed to process recurring transactions', 'error');
    }
  },

  escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
};

window.RecurringPage = RecurringPage;

document.addEventListener('DOMContentLoaded', () => {
  RecurringPage.init();
});
