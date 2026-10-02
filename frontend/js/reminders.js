/**
 * ExpenseFlow - Reminders Page Controller
 */

const RemindersPage = {
  activeStatus: 'upcoming',
  searchQuery: '',
  categories: [],
  reminders: [],
  snoozeTargetId: null,

  async init() {
    Auth.initAppShell('reminders');
    await this.loadCategories();
    await this.loadReminders();
    this.initBackdropListeners();

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('action') === 'new') {
      this.openCreateModal();
    }
  },

  initBackdropListeners() {
    const remModal = document.getElementById('reminder-modal');
    if (remModal) {
      remModal.addEventListener('click', (e) => {
        if (e.target === remModal) RemindersPage.closeModal();
      });
    }
    const snoozeModal = document.getElementById('snooze-modal');
    if (snoozeModal) {
      snoozeModal.addEventListener('click', (e) => {
        if (e.target === snoozeModal) RemindersPage.closeSnoozeModal();
      });
    }
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        RemindersPage.closeModal();
        RemindersPage.closeSnoozeModal();
      }
    });
  },

  async loadCategories() {
    try {
      this.categories = await ApiClient.get('/categories');
      const select = document.getElementById('rem-category');
      if (select) {
        select.innerHTML = '<option value="">-- None / General --</option>' +
          this.categories.map(c => `<option value="${c.id}">${this.escapeHtml(c.name)} (${c.type})</option>`).join('');
      }
    } catch (e) {
      console.error('Failed to load categories:', e);
    }
  },

  async loadReminders() {
    const container = document.getElementById('reminders-container');
    if (!container) return;

    try {
      let url = `/reminders?status=${this.activeStatus}`;
      if (this.searchQuery) {
        url += `&search=${encodeURIComponent(this.searchQuery)}`;
      }
      this.reminders = await ApiClient.get(url);
      this.render();
    } catch (e) {
      container.innerHTML = `
        <div class="card" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
          <p style="color: var(--danger);">Failed to load reminders. Please check your connection.</p>
        </div>
      `;
    }
  },

  render() {
    const container = document.getElementById('reminders-container');
    if (!container) return;

    if (!this.reminders || this.reminders.length === 0) {
      container.innerHTML = `
        <div class="card" style="grid-column: 1 / -1; text-align: center; padding: 3.5rem 1rem;">
          <div style="width: 56px; height: 56px; margin: 0 auto 1rem; border-radius: var(--radius-full); background: var(--primary-light); color: var(--primary); display: flex; align-items: center; justify-content: center;">
            ${getSvgIcon('reminders')}
          </div>
          <h3 style="margin-bottom: 0.5rem; color: var(--text-main);">No Reminders Found</h3>
          <p style="color: var(--text-secondary); max-width: 380px; margin: 0 auto 1.5rem; font-size: 0.875rem;">
            ${this.activeStatus === 'completed' ? 'You have no completed reminders yet.' : 'Stay ahead of your financial dues. Create reminders for rent, bills, or subscription fees.'}
          </p>
          <button class="btn btn-primary" onclick="RemindersPage.openCreateModal()">
            ${getSvgIcon('plus')} Add First Reminder
          </button>
        </div>
      `;
      return;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    container.innerHTML = this.reminders.map(r => {
      const rDate = new Date(r.reminder_date);
      const isPast = rDate < today && r.status === 'pending';
      const isToday = rDate.getTime() === today.getTime() && r.status === 'pending';
      const dayNum = rDate.getDate();
      const monthStr = rDate.toLocaleDateString('en-IN', { month: 'short' });
      const cat = r.category;
      const amtStr = r.amount ? formatCurrency(r.amount) : '';

      let statusBadge = '';
      if (r.status === 'completed') {
        statusBadge = `<span class="badge" style="background: var(--success-light); color: var(--success);">Completed</span>`;
      } else if (r.status === 'snoozed') {
        statusBadge = `<span class="badge" style="background: var(--warning-light); color: var(--warning);">Snoozed</span>`;
      } else if (isPast) {
        statusBadge = `<span class="badge" style="background: var(--danger-light); color: var(--danger);">Overdue</span>`;
      } else if (isToday) {
        statusBadge = `<span class="badge" style="background: var(--primary-light); color: var(--primary);">Due Today</span>`;
      }

      return `
        <div class="card reminder-card ${isPast ? 'overdue' : ''}">
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <div class="upcoming-date-badge">
                <span class="upcoming-date-day">${dayNum}</span>
                <span class="upcoming-date-month">${monthStr}</span>
              </div>
              <div>
                <h3 style="font-size: 0.9375rem; font-weight: 700; margin: 0 0 0.25rem 0; color: var(--text-main);">${this.escapeHtml(r.title)}</h3>
                <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                  ${cat ? `<span class="badge" style="background: ${cat.color}22; color: ${cat.color};">${cat.name}</span>` : ''}
                  ${r.recurrence !== 'once' ? `<span class="badge" style="background: var(--bg-hover); color: var(--text-secondary); text-transform: capitalize;">${r.recurrence}</span>` : ''}
                  ${statusBadge}
                </div>
              </div>
            </div>

            ${amtStr ? `<div style="font-size: 1.0625rem; font-weight: 800; color: var(--text-main);">${amtStr}</div>` : ''}
          </div>

          ${r.description ? `<p style="font-size: 0.8125rem; color: var(--text-secondary); margin: 0 0 0.875rem 0; line-height: 1.4;">${this.escapeHtml(r.description)}</p>` : ''}

          <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle);">
            <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; align-items: center; gap: 0.25rem;">
              ${getSvgIcon('clock')} ${r.reminder_time || 'All day'}
            </div>

            <div style="display: flex; align-items: center; gap: 0.375rem;">
              ${r.status !== 'completed' ? `
                <button class="btn btn-secondary btn-sm" onclick="RemindersPage.openSnoozeModal(${r.id})" title="Snooze reminder">
                  Snooze
                </button>
                <button class="btn btn-primary btn-sm" onclick="RemindersPage.completeReminder(${r.id})" title="Mark done">
                  ${getSvgIcon('check')} Done
                </button>
              ` : ''}
              <button class="icon-btn" onclick="RemindersPage.openEditModal(${r.id})" title="Edit reminder">
                ${getSvgIcon('edit')}
              </button>
              <button class="icon-btn" style="color: var(--danger);" onclick="RemindersPage.deleteReminder(${r.id})" title="Delete reminder">
                ${getSvgIcon('trash')}
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  },

  filterStatus(status, btn) {
    this.activeStatus = status;
    document.querySelectorAll('.toolbar .report-time-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    this.loadReminders();
  },

  onSearchInput: debounce(function(val) {
    RemindersPage.searchQuery = val;
    RemindersPage.loadReminders();
  }, 300),

  async openCreateModal() {
    if (!this.categories || this.categories.length === 0) {
      await this.loadCategories();
    }
    document.getElementById('reminder-modal-title').textContent = 'Create Reminder';
    document.getElementById('reminder-id').value = '';
    document.getElementById('rem-title').value = '';
    document.getElementById('rem-amount').value = '';
    document.getElementById('rem-category').value = '';
    document.getElementById('rem-date').value = formatDateInput(new Date());
    document.getElementById('rem-time').value = '09:00';
    document.getElementById('rem-recurrence').value = 'once';
    document.getElementById('rem-notify').checked = true;
    document.getElementById('rem-desc').value = '';
    const modal = document.getElementById('reminder-modal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  },

  async openEditModal(id) {
    if (!this.categories || this.categories.length === 0) {
      await this.loadCategories();
    }
    const r = this.reminders.find(item => item.id === id);
    if (!r) return;

    document.getElementById('reminder-modal-title').textContent = 'Edit Reminder';
    document.getElementById('reminder-id').value = r.id;
    document.getElementById('rem-title').value = r.title;
    document.getElementById('rem-amount').value = r.amount || '';
    document.getElementById('rem-category').value = r.category_id || '';
    document.getElementById('rem-date').value = r.reminder_date;
    document.getElementById('rem-time').value = r.reminder_time || '09:00';
    document.getElementById('rem-recurrence').value = r.recurrence;
    document.getElementById('rem-notify').checked = r.notification_enabled;
    document.getElementById('rem-desc').value = r.description || '';
    const modal = document.getElementById('reminder-modal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  },

  closeModal() {
    const modal = document.getElementById('reminder-modal');
    if (modal) {
      modal.style.display = 'none';
      modal.classList.remove('active');
    }
  },

  async saveReminder(e) {
    if (e && e.preventDefault) e.preventDefault();
    const submitBtn = document.getElementById('reminder-submit-btn');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';
    }

    try {
      const id = document.getElementById('reminder-id').value;
      const title = document.getElementById('rem-title').value.trim();
      const amountVal = document.getElementById('rem-amount').value.trim();
      const categoryId = document.getElementById('rem-category').value;
      const reminderDate = document.getElementById('rem-date').value;
      const reminderTime = document.getElementById('rem-time').value;
      const recurrence = document.getElementById('rem-recurrence').value;
      const notify = document.getElementById('rem-notify').checked;
      const description = document.getElementById('rem-desc').value.trim();

      if (!title || !reminderDate) {
        showToast('Title and Due Date are required', 'error');
        return;
      }

      let parsedAmount = null;
      if (amountVal !== '' && !isNaN(parseFloat(amountVal))) {
        parsedAmount = parseFloat(amountVal);
        if (parsedAmount < 0) {
          showToast('Amount must be positive or zero', 'error');
          return;
        }
      }

      let parsedCategoryId = null;
      if (categoryId && !isNaN(parseInt(categoryId))) {
        parsedCategoryId = parseInt(categoryId);
      }

      const payload = {
        title,
        amount: parsedAmount,
        category_id: parsedCategoryId,
        reminder_date: reminderDate,
        reminder_time: reminderTime || null,
        recurrence,
        notification_enabled: notify,
        description: description || null
      };

      if (id) {
        await ApiClient.put(`/reminders/${id}`, payload);
        showToast('Reminder updated successfully', 'success');
      } else {
        await ApiClient.post('/reminders', payload);
        showToast('Reminder created successfully', 'success');
      }
      RemindersPage.closeModal();
      await RemindersPage.loadReminders();
    } catch (err) {
      showToast(`Error: ${err.message || 'Could not save reminder'}`, 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Reminder';
      }
    }
  },

  async completeReminder(id) {
    try {
      await ApiClient.patch(`/reminders/${id}/complete`, {});
      showToast('Reminder marked as completed!', 'success');
      await this.loadReminders();
    } catch (e) {
      showToast('Failed to complete reminder', 'error');
    }
  },

  openSnoozeModal(id) {
    this.snoozeTargetId = id;
    const modal = document.getElementById('snooze-modal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.add('active');
    }
  },

  closeSnoozeModal() {
    this.snoozeTargetId = null;
    const modal = document.getElementById('snooze-modal');
    if (modal) {
      modal.style.display = 'none';
      modal.classList.remove('active');
    }
  },

  async confirmSnooze(days) {
    if (!this.snoozeTargetId) return;
    try {
      await ApiClient.patch(`/reminders/${this.snoozeTargetId}/snooze`, { days });
      showToast(`Reminder snoozed by ${days} day(s)`, 'info');
      this.closeSnoozeModal();
      await this.loadReminders();
    } catch (e) {
      showToast('Failed to snooze reminder', 'error');
    }
  },

  async deleteReminder(id) {
    if (!confirm('Are you sure you want to delete this reminder?')) return;
    try {
      await ApiClient.delete(`/reminders/${id}`);
      showToast('Reminder deleted', 'success');
      await this.loadReminders();
    } catch (e) {
      showToast('Failed to delete reminder', 'error');
    }
  },

  escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
};

window.RemindersPage = RemindersPage;

document.addEventListener('DOMContentLoaded', () => {
  RemindersPage.init();
});
