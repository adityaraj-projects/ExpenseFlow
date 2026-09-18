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
      const pageTitles = {
        dashboard: 'Dashboard',
        transactions: 'Transactions',
        budgets: 'Monthly Budgets',
        reminders: 'Payment Reminders',
        recurring: 'Recurring Transactions',
        categories: 'Categories',
        goals: 'Savings Goals',
        reports: 'Reports & Analytics',
        profile: 'Account Profile',
        settings: 'Application Settings'
      };

      headerEl.innerHTML = `
        <div class="header-left">
          <button class="menu-toggle-btn" id="mobile-menu-btn" aria-label="Toggle navigation">
            ${getSvgIcon('menu')}
          </button>
          <h1 class="page-title">${pageTitles[activePage] || 'ExpenseFlow'}</h1>
        </div>

        <div class="header-actions">
          <button class="theme-toggle-btn" onclick="toggleTheme()" aria-label="Toggle theme">
            ${getSvgIcon('moon')}
          </button>
          <button class="btn btn-primary btn-sm" id="header-quick-add-btn" onclick="openQuickAddModal()">
            ${getSvgIcon('plus')}
            <span>Add Transaction</span>
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
        <span>Home</span>
      </a>
      <a href="/pages/transactions.html" class="mobile-nav-link ${activePage === 'transactions' ? 'active' : ''}">
        ${getSvgIcon('transactions')}
        <span>Records</span>
      </a>
      <a href="/pages/reminders.html" class="mobile-nav-link ${activePage === 'reminders' ? 'active' : ''}">
        ${getSvgIcon('reminders')}
        <span>Remind</span>
      </a>
      <a href="/pages/budgets.html" class="mobile-nav-link ${activePage === 'budgets' ? 'active' : ''}">
        ${getSvgIcon('budgets')}
        <span>Budgets</span>
      </a>
      <a href="/pages/reports.html" class="mobile-nav-link ${activePage === 'reports' ? 'active' : ''}">
        ${getSvgIcon('reports')}
        <span>Reports</span>
      </a>
    `;

    // Ensure theme icon reflects state
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    updateThemeIcon(currentTheme);

    // 4. Initialize PWA & Notifications
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

