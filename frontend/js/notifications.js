/**
 * ExpenseFlow - Notification Center & Web Push Controller
 */

const Notifications = {
  unreadCount: 0,
  isOpen: false,
  pollTimer: null,

  async init() {
    this.createDropdownShell();
    await this.fetchUnreadCount();
    // Refresh count periodically (every 60s)
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = setInterval(() => this.fetchUnreadCount(), 60000);
  },

  createDropdownShell() {
    if (document.getElementById('notif-dropdown-wrapper')) return;

    const headerActions = document.querySelector('.header-actions');
    if (!headerActions) return;

    const wrapper = document.createElement('div');
    wrapper.id = 'notif-dropdown-wrapper';
    wrapper.className = 'notif-wrapper';
    wrapper.innerHTML = `
      <button class="icon-btn notif-bell-btn" id="notif-bell-btn" aria-label="Notifications" title="Notifications">
        ${getSvgIcon('bell')}
        <span class="notif-badge" id="notif-badge" style="display: none;">0</span>
      </button>

      <div class="notif-dropdown" id="notif-dropdown" style="display: none;">
        <div class="notif-dropdown-header">
          <div class="notif-header-title">
            <h3>Notifications</h3>
            <span class="badge" id="notif-header-count">0 new</span>
          </div>
          <button class="btn-text" id="notif-mark-all-btn" onclick="Notifications.markAllAsRead()">
            Mark all read
          </button>
        </div>

        <div class="notif-list" id="notif-list">
          <div class="notif-empty">
            <p>Loading notifications...</p>
          </div>
        </div>

        <div class="notif-dropdown-footer">
          <a href="/pages/settings.html" class="notif-settings-link">
            ${getSvgIcon('settings')} Notification Settings
          </a>
        </div>
      </div>
    `;

    // Insert before quick-add button in header actions
    const quickAdd = document.getElementById('header-quick-add-btn');
    if (quickAdd) {
      headerActions.insertBefore(wrapper, quickAdd);
    } else {
      headerActions.appendChild(wrapper);
    }

    const bellBtn = document.getElementById('notif-bell-btn');
    if (bellBtn) {
      bellBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleDropdown();
      });
    }

    // Close on outside click
    document.addEventListener('click', (e) => {
      const dropdown = document.getElementById('notif-dropdown');
      const wrapper = document.getElementById('notif-dropdown-wrapper');
      if (this.isOpen && dropdown && wrapper && !wrapper.contains(e.target)) {
        this.closeDropdown();
      }
    });
  },

  toggleDropdown() {
    if (this.isOpen) {
      this.closeDropdown();
    } else {
      this.openDropdown();
    }
  },

  async openDropdown() {
    const dropdown = document.getElementById('notif-dropdown');
    if (!dropdown) return;
    dropdown.style.display = 'block';
    this.isOpen = true;
    await this.renderNotifications();
  },

  closeDropdown() {
    const dropdown = document.getElementById('notif-dropdown');
    if (!dropdown) return;
    dropdown.style.display = 'none';
    this.isOpen = false;
  },

  async fetchUnreadCount() {
    if (!Auth.isAuthenticated()) return;
    try {
      const res = await ApiClient.get('/notifications/unread-count');
      this.unreadCount = res.unread_count || 0;
      this.updateBadge();
    } catch (e) {
      // Quiet fail if offline
    }
  },

  updateBadge() {
    const badge = document.getElementById('notif-badge');
    const headerCount = document.getElementById('notif-header-count');
    if (badge) {
      if (this.unreadCount > 0) {
        badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
        badge.style.display = 'flex';
      } else {
        badge.style.display = 'none';
      }
    }
    if (headerCount) {
      headerCount.textContent = `${this.unreadCount} unread`;
    }
  },

  async renderNotifications() {
    const listEl = document.getElementById('notif-list');
    if (!listEl) return;

    try {
      const notifs = await ApiClient.get('/notifications?limit=25');
      if (!notifs || notifs.length === 0) {
        listEl.innerHTML = `
          <div class="notif-empty">
            <div class="notif-empty-icon">${getSvgIcon('check')}</div>
            <p>You're all caught up!</p>
            <span>No notifications at the moment.</span>
          </div>
        `;
        return;
      }

      listEl.innerHTML = notifs.map(n => {
        const timeAgo = this.formatTimeAgo(n.created_at);
        const iconType = n.type.includes('budget') ? 'budgets' : (n.type === 'reminder' ? 'reminders' : (n.type.includes('goal') ? 'goals' : 'alert'));
        const typeClass = n.type.includes('exceeded') ? 'danger' : (n.type.includes('warning') ? 'warning' : 'primary');

        return `
          <div class="notif-item ${n.is_read ? 'read' : 'unread'}" onclick="Notifications.handleNotificationClick(${n.id}, '${n.type}', ${n.reference_id})">
            <div class="notif-icon-badge ${typeClass}">
              ${getSvgIcon(iconType)}
            </div>
            <div class="notif-body">
              <div class="notif-title">${this.escapeHtml(n.title)}</div>
              <div class="notif-msg">${this.escapeHtml(n.message)}</div>
              <div class="notif-time">${timeAgo}</div>
            </div>
            ${!n.is_read ? '<span class="unread-dot"></span>' : ''}
          </div>
        `;
      }).join('');
    } catch (e) {
      listEl.innerHTML = `<div class="notif-empty"><p>Could not load notifications</p></div>`;
    }
  },

  async handleNotificationClick(id, type, refId) {
    try {
      await ApiClient.patch(`/notifications/${id}/read`, {});
      this.unreadCount = Math.max(0, this.unreadCount - 1);
      this.updateBadge();
    } catch (e) {}

    // Navigate to respective page if applicable
    if (type === 'reminder') {
      window.location.href = '/pages/reminders.html';
    } else if (type.includes('budget')) {
      window.location.href = '/pages/budgets.html';
    } else if (type.includes('goal')) {
      window.location.href = '/pages/goals.html';
    } else if (type === 'recurring_generated') {
      window.location.href = '/pages/transactions.html';
    } else {
      this.renderNotifications();
    }
  },

  async markAllAsRead() {
    try {
      await ApiClient.patch('/notifications/read-all', {});
      this.unreadCount = 0;
      this.updateBadge();
      showToast('All notifications marked as read', 'success');
      this.renderNotifications();
    } catch (e) {
      showToast('Failed to mark notifications as read', 'error');
    }
  },

  formatTimeAgo(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now - d) / 1000);

    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
    return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
  },

  escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  // Web Push Utilities
  async getPushStatus() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      return 'unsupported';
    }
    return Notification.permission;
  },

  async enableWebPush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      showToast('Push notifications are not supported in this browser.', 'warning');
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        showToast('Notification permission was denied or dismissed.', 'warning');
        return false;
      }

      const swReg = await navigator.serviceWorker.ready;
      const vapidRes = await ApiClient.get('/push/vapid-public-key');
      if (!vapidRes || !vapidRes.public_key) {
        showToast('Push service unavailable.', 'error');
        return false;
      }

      const applicationServerKey = urlBase64ToUint8Array(vapidRes.public_key);
      const subscription = await swReg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey
      });

      const subJson = subscription.toJSON();
      await ApiClient.post('/push/subscribe', {
        endpoint: subscription.endpoint,
        keys: {
          p256dh: subJson.keys.p256dh,
          auth: subJson.keys.auth
        },
        user_agent: navigator.userAgent
      });

      showToast('Push notifications enabled successfully!', 'success');
      return true;
    } catch (err) {
      console.error('Push error:', err);
      showToast(`Push subscription failed: ${err.message || 'Unknown error'}`, 'error');
      return false;
    }
  },

  async disableWebPush() {
    try {
      const swReg = await navigator.serviceWorker.ready;
      const sub = await swReg.pushManager.getSubscription();
      if (sub) {
        await ApiClient.delete(`/push/unsubscribe?endpoint=${encodeURIComponent(sub.endpoint)}`);
        await sub.unsubscribe();
      }
      showToast('Push notifications disabled on this device.', 'info');
      return true;
    } catch (err) {
      showToast('Failed to unsubscribe from push notifications.', 'error');
      return false;
    }
  }
};
