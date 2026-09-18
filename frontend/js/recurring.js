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
    const filtered = this.categories.filter(c => c.type === type || c.type === 'both');
    select.innerHTML = '<option value="">Select Category</option>' +
      filtered.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  },

  onTypeChange() {
    const type = document.getElementById('rec-type').value;
    this.populateCategorySelect(type);
  },

  async loadRecurring() {
    const tbody = document.getElementById('recurring-tbody');
    if (!tbody) return;

    try {
      let url = '/recurring-transactions';
      if (this.activeStatus !== 'all') {
        url += `?status=${this.activeStatus}`;
      }
      this.recurringList = await ApiClient.get(url);
      this.render();
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--danger); padding: 2rem;">Failed to load recurring templates.</td></tr>`;
    }
  },

  render() {
    const tbody = document.getElementById('recurring-tbody');
    if (!tbody) return;

    if (!this.recurringList || this.recurringList.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 3.5rem 1rem;">
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
          </td>
        </tr>
      `;
      return;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

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
            ${cat ? `<span class="badge" style="background: ${cat.color}22; color: ${cat.color};">${cat.name}</span>` : '—'}
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
  },

  filterStatus(status, btn) {
    this.activeStatus = status;
    document.querySelectorAll('.toolbar .report-time-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    this.loadRecurring();
  },

  openCreateModal() {
    document.getElementById('recurring-modal-title').textContent = 'Create Recurring Transaction';
    document.getElementById('recurring-id').value = '';
    document.getElementById('rec-type').value = 'expense';
    this.populateCategorySelect('expense');
    document.getElementById('rec-amount').value = '';
    document.getElementById('rec-desc').value = '';
    document.getElementById('rec-method').value = 'Bank Transfer';
    document.getElementById('rec-frequency').value = 'monthly';
    document.getElementById('rec-start-date').value = formatDateInput(new Date());
    document.getElementById('recurring-modal').style.display = 'flex';
  },

  openEditModal(id) {
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
    document.getElementById('recurring-modal').style.display = 'flex';
  },

  closeModal() {
    document.getElementById('recurring-modal').style.display = 'none';
  },

  async saveRecurring(e) {
    e.preventDefault();
    const id = document.getElementById('recurring-id').value;
    const type = document.getElementById('rec-type').value;
    const amountVal = document.getElementById('rec-amount').value;
    const desc = document.getElementById('rec-desc').value.trim();
    const categoryId = document.getElementById('rec-category').value;
    const method = document.getElementById('rec-method').value;
    const frequency = document.getElementById('rec-frequency').value;
    const startDate = document.getElementById('rec-start-date').value;

    if (!desc || !amountVal || !categoryId || !startDate) {
      showToast('Please fill all required fields.', 'error');
      return;
    }

    const payload = {
      type,
      amount: parseFloat(amountVal),
      description: desc,
      category_id: parseInt(categoryId),
      payment_method: method,
      frequency,
      start_date: startDate
    };

    try {
      if (id) {
        await ApiClient.put(`/recurring-transactions/${id}`, {
          type,
          amount: parseFloat(amountVal),
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
      this.closeModal();
      await this.loadRecurring();
    } catch (err) {
      showToast(`Error: ${err.message || 'Could not save recurring rule'}`, 'error');
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

document.addEventListener('DOMContentLoaded', () => {
  RecurringPage.init();
});
