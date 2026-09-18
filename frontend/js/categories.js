/**
 * ExpenseFlow - Categories Management Controller
 */

let allCategories = [];
let activeTypeFilter = 'all';
let editingCategoryId = null;

const PRESET_COLORS = [
  '#4F46E5', '#0EA5E9', '#10B981', '#F59E0B', '#EF4444',
  '#8B5CF6', '#EC4899', '#14B8A6', '#84CC16', '#64748B'
];

document.addEventListener('DOMContentLoaded', async () => {
  Auth.initAppShell('categories');
  initColorPalette();
  initModals();
  initTabs();
  await loadCategories();
});

function initColorPalette() {
  const container = document.getElementById('color-swatches');
  if (!container) return;

  container.innerHTML = PRESET_COLORS.map(color => `
    <div
      class="color-swatch"
      data-color="${color}"
      style="width: 28px; height: 28px; border-radius: 50%; background-color: ${color}; cursor: pointer; border: 2px solid transparent;"
      onclick="selectColor('${color}')"
    ></div>
  `).join('');
}

function selectColor(color) {
  document.getElementById('cat-color-input').value = color;
  document.querySelectorAll('.color-swatch').forEach(el => {
    el.style.borderColor = el.dataset.color === color ? 'var(--text-main)' : 'transparent';
  });
}

function initTabs() {
  const tabs = document.querySelectorAll('.cat-tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeTypeFilter = tab.dataset.type;
      renderCategories();
    });
  });
}

async function loadCategories() {
  const container = document.getElementById('categories-grid');
  if (!container) return;
  container.innerHTML = Array.from({ length: 4 }).map(() => `
    <div class="card" style="display: flex; align-items: center; justify-content: space-between; padding: 1.25rem;">
      <div style="display: flex; align-items: center; gap: 0.875rem;">
        <div class="skeleton" style="width: 40px; height: 40px; border-radius: var(--radius-md);"></div>
        <div>
          <div class="skeleton" style="height: 16px; width: 100px; margin-bottom: 0.35rem;"></div>
          <div class="skeleton" style="height: 12px; width: 50px;"></div>
        </div>
      </div>
      <div class="skeleton" style="height: 24px; width: 50px; border-radius: 4px;"></div>
    </div>
  `).join('');

  try {
    allCategories = await ApiClient.get('/categories');
    renderCategories();
  } catch (err) {
    showToast('Failed to load categories: ' + err.message, 'error');
  }
}

function renderCategories() {
  const container = document.getElementById('categories-grid');
  const emptyState = document.getElementById('cat-empty-state');

  let filtered = allCategories;
  if (activeTypeFilter !== 'all') {
    filtered = allCategories.filter(c => c.type === activeTypeFilter || c.type === 'both');
  }

  if (!filtered || filtered.length === 0) {
    container.innerHTML = '';
    if (emptyState) emptyState.style.display = 'flex';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  container.innerHTML = filtered.map(c => {
    const isIncome = c.type === 'income';
    const isBoth = c.type === 'both';
    const badgeType = isIncome ? 'badge-income' : (isBoth ? 'badge-primary' : 'badge-expense');

    return `
      <div class="card" style="display: flex; align-items: center; justify-content: space-between; padding: 1.25rem;">
        <div style="display: flex; align-items: center; gap: 0.875rem;">
          <div style="width: 44px; height: 44px; border-radius: var(--radius-md); background-color: ${c.color}15; color: ${c.color}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>
          </div>
          <div>
            <div style="font-weight: 700; font-size: 1rem; color: var(--text-main);">${escapeHtml(c.name)}</div>
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 0.25rem;">
              <span class="badge ${badgeType}">${c.type}</span>
              ${c.is_default ? '<span style="font-size: 0.6875rem; color: var(--text-muted);">Default</span>' : ''}
            </div>
          </div>
        </div>

        <div style="display: flex; gap: 0.25rem;">
          <button class="btn-icon btn-ghost" onclick="openEditCategoryModal(${c.id})" title="Edit category">
            ${getSvgIcon('edit')}
          </button>
          <button class="btn-icon btn-ghost" onclick="confirmDeleteCategory(${c.id}, '${escapeHtml(c.name)}')" title="Delete category" style="color: var(--danger);">
            ${getSvgIcon('trash')}
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function initModals() {
  const modal = document.getElementById('cat-modal');
  const openBtn = document.getElementById('open-create-cat-btn');
  const closeBtns = document.querySelectorAll('#close-cat-modal, #cancel-cat-modal');
  const form = document.getElementById('cat-form');

  if (openBtn) {
    openBtn.addEventListener('click', () => {
      editingCategoryId = null;
      document.getElementById('cat-modal-title').textContent = 'Create Category';
      form.reset();
      selectColor('#4F46E5');
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
      const submitBtn = document.getElementById('save-cat-btn');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving...';

      const name = document.getElementById('cat-name-input').value.trim();
      const type = document.getElementById('cat-type-select').value;
      const color = document.getElementById('cat-color-input').value;

      try {
        if (editingCategoryId) {
          await ApiClient.put(`/categories/${editingCategoryId}`, { name, type, color });
          showToast('Category updated successfully!', 'success');
        } else {
          await ApiClient.post('/categories', { name, type, color });
          showToast('Category created successfully!', 'success');
        }

        modal.classList.remove('active');
        await loadCategories();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Category';
      }
    });
  }
}

function openEditCategoryModal(catId) {
  const cat = allCategories.find(c => c.id === catId);
  if (!cat) return;

  editingCategoryId = cat.id;
  document.getElementById('cat-modal-title').textContent = 'Edit Category';
  document.getElementById('cat-name-input').value = cat.name;
  document.getElementById('cat-type-select').value = cat.type;
  selectColor(cat.color || '#4F46E5');
  document.getElementById('cat-modal').classList.add('active');
}

async function confirmDeleteCategory(catId, catName) {
  if (confirm(`Are you sure you want to delete the category "${catName}"?`)) {
    try {
      await ApiClient.delete(`/categories/${catId}`);
      showToast('Category deleted successfully.', 'success');
      await loadCategories();
    } catch (err) {
      // Friendly message explaining linked transactions
      showToast(err.message, 'error', 'Cannot Delete Category');
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
