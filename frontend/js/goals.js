/**
 * ExpenseFlow - Savings Goals Controller
 */

let allGoals = [];
let activeGoalActionId = null;
let editingGoalId = null;

document.addEventListener('DOMContentLoaded', async () => {
  Auth.initAppShell('goals');
  initModals();
  await loadGoals();
});

async function loadGoals() {
  const container = document.getElementById('goals-grid');
  const emptyState = document.getElementById('goals-empty-state');
  const user = Auth.getCurrentUser();
  const currency = user ? user.currency : 'INR';

  container.innerHTML = Array.from({ length: 3 }).map(() => `
    <div class="card" style="padding: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem;">
        <div class="skeleton" style="height: 18px; width: 140px;"></div>
        <div class="skeleton" style="height: 22px; width: 60px; border-radius: 12px;"></div>
      </div>
      <div class="skeleton" style="height: 14px; width: 100%; margin-bottom: 0.75rem;"></div>
      <div class="skeleton" style="height: 10px; width: 100%; border-radius: 999px; margin-bottom: 0.75rem;"></div>
      <div style="display: flex; justify-content: space-between; margin-bottom: 1.25rem;">
        <div class="skeleton" style="height: 12px; width: 60px;"></div>
        <div class="skeleton" style="height: 12px; width: 90px;"></div>
      </div>
      <div class="skeleton" style="height: 34px; width: 100%; border-radius: var(--radius-sm);"></div>
    </div>
  `).join('');

  try {
    allGoals = await ApiClient.get('/goals');

    // Update Top Summary Stats
    const totalTarget = allGoals.reduce((sum, g) => sum + Number(g.target_amount), 0);
    const totalSaved = allGoals.reduce((sum, g) => sum + Number(g.current_amount), 0);
    const completedCount = allGoals.filter(g => g.status === 'completed').length;

    document.getElementById('total-saved-kpi').textContent = formatCurrency(totalSaved, currency);
    document.getElementById('total-target-kpi').textContent = formatCurrency(totalTarget, currency);
    document.getElementById('goals-count-kpi').textContent = `${completedCount} of ${allGoals.length} completed`;

    if (!allGoals || allGoals.length === 0) {
      container.innerHTML = '';
      if (emptyState) emptyState.style.display = 'flex';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    container.innerHTML = allGoals.map(g => {
      const isCompleted = g.status === 'completed';
      const widthPct = Math.min(100, g.progress_percentage);

      return `
        <div class="card" style="display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
              <div>
                <h3 style="font-size: 1.125rem; font-weight: 700; color: var(--text-main);">${escapeHtml(g.name)}</h3>
                ${g.target_date ? `<span style="font-size: 0.75rem; color: var(--text-muted);">Target: ${formatDate(g.target_date)}</span>` : ''}
              </div>
              <span class="badge ${isCompleted ? 'badge-income' : 'badge-primary'}">
                ${isCompleted ? 'Completed' : 'In Progress'}
              </span>
            </div>

            ${g.description ? `<p style="font-size: 0.8125rem; color: var(--text-secondary); margin-bottom: 1.25rem;">${escapeHtml(g.description)}</p>` : ''}

            <!-- Progress Meter -->
            <div style="margin-bottom: 1.25rem;">
              <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 0.4rem; font-size: 0.8125rem;">
                <span style="color: var(--text-muted);">Saved: <strong style="color: var(--primary);">${formatCurrency(g.current_amount, currency)}</strong></span>
                <span style="color: var(--text-muted);">Target: <strong>${formatCurrency(g.target_amount, currency)}</strong></span>
              </div>

              <div class="progress-track" style="height: 10px;">
                <div class="progress-fill ${isCompleted ? 'safe' : 'safe'}" style="width: ${widthPct}%; background-color: ${isCompleted ? 'var(--success)' : 'var(--primary)'};"></div>
              </div>

              <div style="display: flex; justify-content: space-between; margin-top: 0.4rem; font-size: 0.75rem; color: var(--text-muted);">
                <span style="font-weight: 600;">${g.progress_percentage}% reached</span>
                <span>${isCompleted ? 'Goal Achieved! 🎉' : formatCurrency(g.remaining_amount, currency) + ' remaining'}</span>
              </div>
            </div>
          </div>

          <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 1rem; border-top: 1px solid var(--border-subtle); margin-top: 0.5rem;">
            <button type="button" class="btn btn-outline-primary btn-sm" onclick="openDepositModal(${g.id}, '${escapeHtml(g.name)}')">
              <span>+ Add / Withdraw Funds</span>
            </button>

            <div style="display: flex; gap: 0.25rem;">
              <button class="btn-icon btn-ghost" onclick="openEditGoalModal(${g.id})" title="Edit Goal">
                ${getSvgIcon('edit')}
              </button>
              <button class="btn-icon btn-ghost" onclick="confirmDeleteGoal(${g.id}, '${escapeHtml(g.name)}')" title="Delete Goal" style="color: var(--danger);">
                ${getSvgIcon('trash')}
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    showToast('Failed to load savings goals: ' + err.message, 'error');
  }
}

function initModals() {
  // Goal Modal (Create / Edit)
  const goalModal = document.getElementById('goal-modal');
  const openGoalBtn = document.getElementById('open-create-goal-btn');
  const closeGoalBtns = document.querySelectorAll('#close-goal-modal, #cancel-goal-modal');
  const goalForm = document.getElementById('goal-form');

  if (openGoalBtn) {
    openGoalBtn.addEventListener('click', () => {
      editingGoalId = null;
      document.getElementById('goal-modal-title').textContent = 'Create Savings Goal';
      document.getElementById('initial-amount-group').style.display = 'block';
      goalForm.reset();
      goalModal.classList.add('active');
    });
  }

  closeGoalBtns.forEach(btn => {
    btn.addEventListener('click', () => goalModal.classList.remove('active'));
  });

  if (goalForm) {
    goalForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('save-goal-btn');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';

      const name = document.getElementById('goal-name-input').value.trim();
      const target_amount = parseFloat(document.getElementById('goal-target-input').value);
      const target_date = document.getElementById('goal-date-input').value || null;
      const description = document.getElementById('goal-desc-input').value.trim() || null;

      try {
        if (editingGoalId) {
          await ApiClient.put(`/goals/${editingGoalId}`, {
            name,
            target_amount,
            target_date,
            description
          });
          showToast('Goal updated successfully!', 'success');
        } else {
          const initial_amount = parseFloat(document.getElementById('goal-initial-input').value) || 0.00;
          await ApiClient.post('/goals', {
            name,
            target_amount,
            initial_amount,
            target_date,
            description
          });
          showToast('Savings goal created!', 'success');
        }

        goalModal.classList.remove('active');
        await loadGoals();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Goal';
      }
    });
  }

  // Deposit/Withdrawal Modal
  const depositModal = document.getElementById('deposit-modal');
  const closeDepositBtns = document.querySelectorAll('#close-deposit-modal, #cancel-deposit-modal');
  const depositForm = document.getElementById('deposit-form');

  closeDepositBtns.forEach(btn => {
    btn.addEventListener('click', () => depositModal.classList.remove('active'));
  });

  if (depositForm) {
    depositForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('save-deposit-btn');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Processing...';

      const action = document.querySelector('input[name="funds-action"]:checked').value;
      const amount = parseFloat(document.getElementById('deposit-amount-input').value);

      try {
        await ApiClient.post(`/goals/${activeGoalActionId}/deposit`, {
          amount,
          action
        });

        showToast(`Successfully ${action === 'deposit' ? 'deposited' : 'withdrawn'} funds!`, 'success');
        depositModal.classList.remove('active');
        await loadGoals();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Confirm Transaction';
      }
    });
  }
}

function openEditGoalModal(goalId) {
  const goal = allGoals.find(g => g.id === goalId);
  if (!goal) return;

  editingGoalId = goal.id;
  document.getElementById('goal-modal-title').textContent = 'Edit Savings Goal';
  document.getElementById('initial-amount-group').style.display = 'none';
  document.getElementById('goal-name-input').value = goal.name;
  document.getElementById('goal-target-input').value = goal.target_amount;
  document.getElementById('goal-date-input').value = goal.target_date || '';
  document.getElementById('goal-desc-input').value = goal.description || '';
  document.getElementById('goal-modal').classList.add('active');
}

function openDepositModal(goalId, goalName) {
  activeGoalActionId = goalId;
  document.getElementById('deposit-modal-title').textContent = `Manage Funds: ${goalName}`;
  document.getElementById('deposit-form').reset();
  document.getElementById('deposit-modal').classList.add('active');
}

async function confirmDeleteGoal(goalId, goalName) {
  if (confirm(`Are you sure you want to delete savings goal "${goalName}"?`)) {
    try {
      await ApiClient.delete(`/goals/${goalId}`);
      showToast('Goal deleted.', 'success');
      await loadGoals();
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
