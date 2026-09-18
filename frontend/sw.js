/**
 * ExpenseFlow - Production Progressive Web App Service Worker
 * Version: 1.0.0
 * 
 * Rules:
 * - Caches static application shell & offline view
 * - NEVER caches authenticated /api/ responses to protect user financial privacy
 * - Manages Web Push notifications & notification click routing
 * - Handles cache versioning and clean activation
 */

const CACHE_NAME = 'expenseflow-shell-v1.0.2';

const STATIC_SHELL_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  '/manifest.webmanifest',
  '/css/style.css',
  '/css/auth.css',
  '/css/dashboard.css',
  '/css/responsive.css',
  '/js/utils.js',
  '/js/toast.js',
  '/js/api.js',
  '/js/auth.js',
  '/js/notifications.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-512.png',
  '/icons/apple-touch-icon.png',
  '/icons/badge-72.png',
  '/icons/favicon.png'
];

// 1. Install Phase - Pre-cache the application shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_SHELL_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// 2. Activate Phase - Remove obsolete caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. Fetch Phase - Strict security isolation & graceful offline fallback
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // CRITICAL PRIVACY RULE: NEVER cache API calls. Pass directly to network.
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(() => {
        return new Response(
          JSON.stringify({
            detail: 'You are currently offline. Live operations require an internet connection.',
            offline: true
          }),
          {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
          }
        );
      })
    );
    return;
  }

  // HTML Navigation Requests (Pages)
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => {
          return caches.match(request).then(cached => {
            return cached || caches.match('/offline.html');
          });
        })
    );
    return;
  }

  // Static Scripts & Styles (JS, CSS) - Network First, Cache Fallback for instant updates
  if (url.pathname.endsWith('.js') || url.pathname.endsWith('.css')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.status === 200 && request.method === 'GET') {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => {
          return caches.match(request);
        })
    );
    return;
  }

  // Static Assets (Icons, Images, Manifest) - Cache First, Network Fallback
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;

      return fetch(request).then(response => {
        if (response.status === 200 && request.method === 'GET' && !url.origin.includes('chrome-extension')) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
        }
        return response;
      }).catch(() => {
        // Return nothing or fallback if fetch fails
      });
    })
  );
});

// 4. Web Push Notification Listener
self.addEventListener('push', event => {
  let data = {
    title: 'ExpenseFlow Alert',
    body: 'You have a new financial notification.',
    url: '/pages/dashboard.html'
  };

  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: '/icons/icon-192.png',
    badge: '/icons/badge-72.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/pages/dashboard.html'
    }
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// 5. Notification Click Handler - Focus or open the application
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/pages/dashboard.html';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (const client of windowClients) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
