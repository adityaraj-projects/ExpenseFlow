/**
 * ExpenseFlow - Reusable Toast Notification System
 */

function getOrCreateToastContainer() {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  return container;
}

/**
 * Show a modern floating toast notification
 * @param {string} message - Body text
 * @param {'success'|'error'|'info'|'warning'} type - Toast type
 * @param {string|null} title - Optional title header
 * @param {number} duration - Auto dismiss time in ms (default 4000)
 */
function showToast(message, type = 'info', title = null, duration = 4000) {
  const container = getOrCreateToastContainer();

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const defaultTitles = {
    success: 'Success',
    error: 'Error',
    warning: 'Notice',
    info: 'Information'
  };

  const headerTitle = title || defaultTitles[type] || 'Notification';
  const iconName = type === 'success' ? 'check' : (type === 'error' ? 'alert' : (type === 'warning' ? 'alert' : 'dashboard'));

  toast.innerHTML = `
    <div class="toast-icon">
      ${getSvgIcon(iconName)}
    </div>
    <div class="toast-content">
      <div class="toast-title">${headerTitle}</div>
      <div class="toast-message">${message}</div>
    </div>
    <button class="toast-close" aria-label="Close notification">&times;</button>
  `;

  // Dismiss button handler
  const closeBtn = toast.querySelector('.toast-close');
  closeBtn.addEventListener('click', () => removeToast(toast));

  // Auto dismiss timeout
  const timeoutId = setTimeout(() => {
    removeToast(toast);
  }, duration);

  container.appendChild(toast);

  function removeToast(el) {
    clearTimeout(timeoutId);
    el.classList.add('removing');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    // Fallback if animationend does not fire
    setTimeout(() => { if (el.parentNode) el.remove(); }, 300);
  }
}
