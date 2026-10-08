/**
 * ExpenseFlow - Authentication Manager & Shell Navigation Controller
 */

const Auth = {
  getToken() {
    return localStorage.getItem('expenseflow_token');
  },

  getCurrentUser() {
    try {
      const userJson = localStorage.getItem('expenseflow_user');
      return userJson ? JSON.parse(userJson) : null;
    } catch (e) {
      return null;
    }
  },

  setSession(token, user) {
    localStorage.setItem('expenseflow_token', token);
    localStorage.setItem('expenseflow_user', JSON.stringify(user));
  },

  clearSession() {
    localStorage.removeItem('expenseflow_token');
    localStorage.removeItem('expenseflow_user');
  },

  isAuthenticated() {
    return !!this.getToken();
  },

  requireAuth() {
    if (!this.isAuthenticated()) {
      window.location.href = '/pages/login.html';
    }
  },

  redirectIfAuthenticated() {
    if (this.isAuthenticated()) {
      window.location.href = '/pages/dashboard.html';
    }
  },

  async logout() {
    try {
      if (this.isAuthenticated()) {
        await ApiClient.post('/auth/logout', {});
      }
    } catch (e) {
      // Proceed with client side logout regardless of network status
    } finally {
      this.clearSession();
      window.location.href = '/pages/login.html';
    }
  },

  /**
   * Dynamically renders standard desktop sidebar, top header, and mobile navigation
   * @param {string} activePage - Name of the active page (e.g. 'dashboard', 'transactions')
   */
  initAppShell(activePage = 'dashboard') {
    this.requireAuth();

    const user = this.getCurrentUser() || { full_name: 'User', email: 'user@expenseflow.com', currency: 'INR' };
    const userInitials = user.full_name
      ? user.full_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()
      : 'EF';

    // 1. Render App Sidebar
    const sidebarEl = document.getElementById('app-sidebar');
    if (sidebarEl) {
      sidebarEl.innerHTML = `
        <div class="sidebar-header">
          <div class="brand-logo">EF</div>
          <div class="brand-name">Expense<span>Flow</span></div>
          <button class="sidebar-close-btn" id="sidebar-close-btn" aria-label="Close sidebar">&times;</button>
        </div>

        <nav class="sidebar-nav">
          <div class="nav-section-title">Menu</div>
          <a href="/pages/dashboard.html" class="nav-item ${activePage === 'dashboard' ? 'active' : ''}">
            ${getSvgIcon('dashboard')}
            <span>Dashboard</span>
          </a>
          <a href="/pages/transactions.html" class="nav-item ${activePage === 'transactions' ? 'active' : ''}">
            ${getSvgIcon('transactions')}
            <span>Transactions</span>
          </a>
          <a href="/pages/calendar.html" class="nav-item ${activePage === 'calendar' ? 'active' : ''}">
            ${getSvgIcon('calendar')}
            <span>Calendar</span>
          </a>
          <a href="/pages/budgets.html" class="nav-item ${activePage === 'budgets' ? 'active' : ''}">
            ${getSvgIcon('budgets')}
            <span>Budgets</span>
          </a>
          <a href="/pages/reminders.html" class="nav-item ${activePage === 'reminders' ? 'active' : ''}">
            ${getSvgIcon('reminders')}
            <span>Reminders</span>
          </a>
          <a href="/pages/recurring.html" class="nav-item ${activePage === 'recurring' ? 'active' : ''}">
            ${getSvgIcon('recurring')}
            <span>Recurring</span>
          </a>
          <a href="/pages/categories.html" class="nav-item ${activePage === 'categories' ? 'active' : ''}">
            ${getSvgIcon('categories')}
            <span>Categories</span>
          </a>
          <a href="/pages/goals.html" class="nav-item ${activePage === 'goals' ? 'active' : ''}">
            ${getSvgIcon('goals')}
            <span>Savings Goals</span>
          </a>
          <a href="/pages/reports.html" class="nav-item ${activePage === 'reports' ? 'active' : ''}">
            ${getSvgIcon('reports')}
            <span>Reports</span>
          </a>

          <div class="nav-section-title">Account</div>
          <a href="/pages/profile.html" class="nav-item ${activePage === 'profile' ? 'active' : ''}">
            ${getSvgIcon('profile')}
            <span>Profile</span>
          </a>
          <a href="/pages/settings.html" class="nav-item ${activePage === 'settings' ? 'active' : ''}">
            ${getSvgIcon('settings')}
            <span>Settings</span>
          </a>
          <a href="javascript:void(0)" onclick="Auth.logout()" class="nav-item">
            ${getSvgIcon('logout')}
            <span>Sign Out</span>
          </a>
        </nav>

        <button class="pwa-install-btn" id="pwa-install-sidebar-btn" onclick="PWA.promptInstall()">
          ${getSvgIcon('download')}
          <span>Install App</span>
        </button>

        <div class="sidebar-footer">
          <div class="user-mini-profile">
            <div class="user-avatar">${userInitials}</div>
            <div class="user-info">
              <span class="user-name">${user.full_name}</span>
              <span class="user-email">${user.email}</span>
            </div>
          </div>
        </div>
      `;
    }

    // 2. Render Top Header
    const headerEl = document.getElementById('app-header');
    if (headerEl) {
      const desktopTitles = {
        dashboard: 'Dashboard',
        transactions: 'Transactions',
        calendar: 'Daily Finance Calendar',
        budgets: 'Monthly Budgets',
        reminders: 'Payment Reminders',
        recurring: 'Recurring Transactions',
        categories: 'Categories',
        goals: 'Savings Goals',
        reports: 'Reports & Analytics',
        profile: 'Account Profile',
        settings: 'Application Settings'
      };

      const mobileTitles = {
        dashboard: 'Dashboard',
        transactions: 'Transactions',
        calendar: 'Calendar',
        budgets: 'Budgets',
        reminders: 'Reminders',
        recurring: 'Recurring',
        categories: 'Categories',
        goals: 'Goals',
        reports: 'Reports',
        profile: 'Profile',
        settings: 'Settings'
      };

      headerEl.innerHTML = `
        <div class="header-left">
          <button class="menu-toggle-btn" id="mobile-menu-btn" aria-label="Toggle navigation">
            ${getSvgIcon('menu')}
          </button>
          <h1 class="page-title">
            <span class="desktop-title-text">${desktopTitles[activePage] || 'ExpenseFlow'}</span>
            <span class="mobile-title-text">${mobileTitles[activePage] || 'ExpenseFlow'}</span>
          </h1>
        </div>

        <div class="header-actions">
          <button class="theme-toggle-btn" onclick="toggleTheme()" aria-label="Toggle theme" title="Toggle theme">
            ${getSvgIcon('moon')}
          </button>
          <button class="btn btn-primary btn-sm" id="header-quick-add-btn" onclick="GlobalQuickAdd.open()" aria-label="Quick Add" title="Quick Add">
            ${getSvgIcon('plus')}
            <span>Add</span>
          </button>
        </div>
      `;

      // Mobile menu toggle listeners
      const menuBtn = document.getElementById('mobile-menu-btn');
      const closeBtn = document.getElementById('sidebar-close-btn');
      const backdrop = document.getElementById('sidebar-backdrop');
      if (menuBtn && sidebarEl) {
        menuBtn.addEventListener('click', () => {
          sidebarEl.classList.toggle('open');
          if (backdrop) backdrop.classList.toggle('active');
        });
      }
      if (closeBtn && sidebarEl) {
        closeBtn.addEventListener('click', () => {
          sidebarEl.classList.remove('open');
          if (backdrop) backdrop.classList.remove('active');
        });
      }
      if (backdrop && sidebarEl) {
        backdrop.addEventListener('click', () => {
          sidebarEl.classList.remove('open');
          backdrop.classList.remove('active');
        });
      }

      // Auto-close sidebar on mobile navigation
      const navLinks = sidebarEl.querySelectorAll('.sidebar-nav a');
      navLinks.forEach(link => {
        link.addEventListener('click', () => {
          if (window.innerWidth <= 768) {
            sidebarEl.classList.remove('open');
            if (backdrop) backdrop.classList.remove('active');
          }
        });
      });
    }

    // 3. Render Mobile Bottom Navigation
    let bottomNav = document.getElementById('mobile-bottom-nav');
    if (!bottomNav) {
      bottomNav = document.createElement('nav');
      bottomNav.id = 'mobile-bottom-nav';
      bottomNav.className = 'mobile-bottom-nav';
      document.body.appendChild(bottomNav);
    }
    bottomNav.innerHTML = `
      <a href="/pages/dashboard.html" class="mobile-nav-link ${activePage === 'dashboard' ? 'active' : ''}">
        ${getSvgIcon('dashboard')}
        <span>Dashboard</span>
      </a>
      <a href="/pages/transactions.html" class="mobile-nav-link ${activePage === 'transactions' ? 'active' : ''}">
        ${getSvgIcon('transactions')}
        <span>Transactions</span>
      </a>
      <a href="/pages/budgets.html" class="mobile-nav-link ${activePage === 'budgets' ? 'active' : ''}">
        ${getSvgIcon('budgets')}
        <span>Budgets</span>
      </a>
      <a href="/pages/goals.html" class="mobile-nav-link ${activePage === 'goals' ? 'active' : ''}">
        ${getSvgIcon('goals')}
        <span>Goals</span>
      </a>
      <button type="button" class="mobile-nav-link mobile-nav-more-btn ${['calendar', 'categories', 'reports', 'reminders', 'recurring', 'profile', 'settings'].includes(activePage) ? 'active' : ''}" id="mobile-more-btn" aria-label="Open more menu">
        ${getSvgIcon('more')}
        <span>More</span>
      </button>
    `;

    const moreBtn = document.getElementById('mobile-more-btn');
    if (moreBtn && sidebarEl) {
      moreBtn.addEventListener('click', (e) => {
        e.preventDefault();
        sidebarEl.classList.toggle('open');
        if (backdrop) backdrop.classList.toggle('active');
      });
    }

    // Ensure theme icon reflects state
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    updateThemeIcon(currentTheme);

    // 4. Initialize Quick Add, PWA & Notifications
    GlobalQuickAdd.init(activePage);
    PWA.init();
    if (typeof Notifications !== 'undefined') {
      Notifications.init();
    }
  }
};

/**
 * PWA Controller
 */
const PWA = {
  init() {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
          .then(reg => {
            // Service worker active
          })
          .catch(err => console.log('SW registration note:', err));
      });
    }

    // Capture install prompt
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      window.deferredPWAInstallPrompt = e;
      const btn = document.getElementById('pwa-install-sidebar-btn');
      if (btn && !this.isStandalone()) {
        btn.style.display = 'flex';
      }
    });

    window.addEventListener('appinstalled', () => {
      window.deferredPWAInstallPrompt = null;
      const btn = document.getElementById('pwa-install-sidebar-btn');
      if (btn) btn.style.display = 'none';
      if (typeof showToast === 'function') showToast('ExpenseFlow installed successfully!', 'success');
    });

    this.initOfflineBanner();
  },

  isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  },

  async promptInstall() {
    if (window.deferredPWAInstallPrompt) {
      window.deferredPWAInstallPrompt.prompt();
      const choice = await window.deferredPWAInstallPrompt.userChoice;
      if (choice.outcome === 'accepted') {
        const btn = document.getElementById('pwa-install-sidebar-btn');
        if (btn) btn.style.display = 'none';
      }
      window.deferredPWAInstallPrompt = null;
    } else {
      if (typeof showToast === 'function') {
        showToast('To install ExpenseFlow, open browser menu and select "Install App" or "Add to Home Screen".', 'info');
      }
    }
  },

  initOfflineBanner() {
    let banner = document.getElementById('offline-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'offline-banner';
      banner.className = 'offline-banner';
      banner.innerHTML = `${getSvgIcon('wifiOff')} You are currently offline. Live operations require an internet connection.`;
      document.body.prepend(banner);
    }

    const updateStatus = () => {
      if (!navigator.onLine) {
        banner.classList.add('active');
      } else {
        banner.classList.remove('active');
      }
    };

    window.addEventListener('online', updateStatus);
    window.addEventListener('offline', updateStatus);
    updateStatus();
  }
};

/**
 * Global Quick Add Controller
 */
const GlobalQuickAdd = {
  activePage: '',

  init(page) {
    this.activePage = page;
    this.injectModal();
  },

  injectModal() {
    if (document.getElementById('global-quick-add-modal')) return;

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'global-quick-add-modal';
    overlay.style.display = 'none';

    overlay.innerHTML = `
      <div class="modal-card quick-add-card" style="max-width: 440px; width: 100%;">
        <div class="modal-header" style="padding-bottom: 0.75rem;">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <div class="quick-add-badge-icon">
              ${getSvgIcon('plus')}
            </div>
            <div>
              <h3 class="modal-title" style="margin: 0; font-size: 1.125rem;">Quick Create</h3>
              <p style="margin: 0; font-size: 0.75rem; color: var(--text-muted);">Choose what you want to add</p>
            </div>
          </div>
          <button type="button" class="modal-close-btn" onclick="GlobalQuickAdd.close()" aria-label="Close modal">&times;</button>
        </div>

        <div class="quick-add-menu-list">
          <!-- 1. Add Expense -->
          <button type="button" class="quick-add-menu-item" onclick="GlobalQuickAdd.select('expense')">
            <div class="quick-add-item-icon" style="background: rgba(239, 68, 68, 0.12); color: #EF4444;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="7" y1="7" x2="17" y2="17"></line><polyline points="17 7 17 17 7 17"></polyline></svg>
            </div>
            <div class="quick-add-item-content">
              <span class="quick-add-item-title">Add Expense</span>
              <span class="quick-add-item-desc">Record spending, bills or purchases</span>
            </div>
            <span class="quick-add-item-arrow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </span>
          </button>

          <!-- 2. Add Income -->
          <button type="button" class="quick-add-menu-item" onclick="GlobalQuickAdd.select('income')">
            <div class="quick-add-item-icon" style="background: rgba(16, 185, 129, 0.12); color: #10B981;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="17" y1="17" x2="7" y2="7"></line><polyline points="7 17 7 7 17 7"></polyline></svg>
            </div>
            <div class="quick-add-item-content">
              <span class="quick-add-item-title">Add Income</span>
              <span class="quick-add-item-desc">Record salary, investments or deposits</span>
            </div>
            <span class="quick-add-item-arrow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </span>
          </button>

          <!-- 3. Add Reminder -->
          <button type="button" class="quick-add-menu-item" onclick="GlobalQuickAdd.select('reminder')">
            <div class="quick-add-item-icon" style="background: rgba(245, 158, 11, 0.12); color: #F59E0B;">
              ${getSvgIcon('reminders')}
            </div>
            <div class="quick-add-item-content">
              <span class="quick-add-item-title">Add Reminder</span>
              <span class="quick-add-item-desc">Schedule a due date for upcoming bills</span>
            </div>
            <span class="quick-add-item-arrow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </span>
          </button>

          <!-- 4. Add Recurring Rule -->
          <button type="button" class="quick-add-menu-item" onclick="GlobalQuickAdd.select('recurring')">
            <div class="quick-add-item-icon" style="background: rgba(99, 102, 241, 0.12); color: #6366F1;">
              ${getSvgIcon('recurring')}
            </div>
            <div class="quick-add-item-content">
              <span class="quick-add-item-title">Add Recurring Rule</span>
              <span class="quick-add-item-desc">Automate repeating subscriptions or income</span>
            </div>
            <span class="quick-add-item-arrow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </span>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        GlobalQuickAdd.close();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && overlay.classList.contains('active')) {
        GlobalQuickAdd.close();
      }
    });
  },

  open() {
    this.injectModal();
    const overlay = document.getElementById('global-quick-add-modal');
    if (overlay) {
      overlay.style.display = 'flex';
      overlay.classList.add('active');
    }
  },

  close() {
    const overlay = document.getElementById('global-quick-add-modal');
    if (overlay) {
      overlay.style.display = 'none';
      overlay.classList.remove('active');
    }
  },

  select(actionType) {
    this.close();

    if (actionType === 'expense') {
      if (this.activePage === 'dashboard') {
        const radio = document.querySelector('input[name="quick-tx-type"][value="expense"]');
        if (radio) {
          radio.checked = true;
          if (typeof populateCategoryDropdown === 'function') populateCategoryDropdown('expense');
        }
        const modal = document.getElementById('quick-add-modal');
        if (modal) modal.classList.add('active');
      } else if (this.activePage === 'transactions') {
        if (typeof openAddModal === 'function') openAddModal('expense');
      } else {
        window.location.href = '/pages/transactions.html?action=new-expense';
      }
    } else if (actionType === 'income') {
      if (this.activePage === 'dashboard') {
        const radio = document.querySelector('input[name="quick-tx-type"][value="income"]');
        if (radio) {
          radio.checked = true;
          if (typeof populateCategoryDropdown === 'function') populateCategoryDropdown('income');
        }
        const modal = document.getElementById('quick-add-modal');
        if (modal) modal.classList.add('active');
      } else if (this.activePage === 'transactions') {
        if (typeof openAddModal === 'function') openAddModal('income');
      } else {
        window.location.href = '/pages/transactions.html?action=new-income';
      }
    } else if (actionType === 'reminder') {
      if (this.activePage === 'reminders' && typeof RemindersPage !== 'undefined' && RemindersPage.openCreateModal) {
        RemindersPage.openCreateModal();
      } else {
        window.location.href = '/pages/reminders.html?action=new';
      }
    } else if (actionType === 'recurring') {
      if (this.activePage === 'recurring' && typeof RecurringPage !== 'undefined' && RecurringPage.openCreateModal) {
        RecurringPage.openCreateModal();
      } else {
        window.location.href = '/pages/recurring.html?action=new';
      }
    }
  }
};

window.GlobalQuickAdd = GlobalQuickAdd;
window.openQuickAddModal = () => GlobalQuickAdd.open();

