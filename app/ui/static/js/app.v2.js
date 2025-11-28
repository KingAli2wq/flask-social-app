(() => {
  const TOKEN_KEY = 'socialsphere:token';
  const USERNAME_KEY = 'socialsphere:username';
  const USER_ID_KEY = 'socialsphere:user_id';
  const THEME_KEY = 'socialsphere:theme';
  const MEDIA_HISTORY_KEY = 'socialsphere:media-history';
  const FEED_BATCH_SIZE = 5;
  const REALTIME_WS_PATH = '/ws/feed';
  const MESSAGES_WS_PREFIX = '/messages/ws';
  const NOTIFICATION_WS_PATH = '/notifications/ws';

  const palette = {
    success: 'bg-emerald-500/90 text-white shadow-emerald-500/30',
    error: 'bg-rose-500/90 text-white shadow-rose-500/30',
    warning: 'bg-amber-400 text-slate-900 shadow-amber-400/30',
    info: 'bg-slate-900/90 text-white shadow-slate-900/30'
  };

  const DEFAULT_AVATAR = '/assets/default-avatar.png';

  const state = {
    feedItems: [],
    feedCursor: 0,
    friends: [],
    incomingRequests: [],
    outgoingRequests: [],
    activeFriendId: null,
    activeFriendMeta: null,
    activeThreadLock: null,
    activeChatId: null,
    activeMessages: [],
    friendSearch: {
      query: '',
      results: [],
    },
    threadLoading: false,
    mediaHistory: loadJson(MEDIA_HISTORY_KEY, []),
    avatarCache: {},               // user_id -> resolved avatar URL
    currentProfileAvatar: null,    // raw URL from backend for current user
    feedRefreshHandle: null,
    feedLoading: false,
    feedSignature: null,
    realtime: {
      socket: null,
      reconnectHandle: null,
      retryDelay: 1000,
      pendingRefresh: false,
      pingHandle: null,
    },
    messageRealtime: {
      socket: null,
      chatId: null,
      reconnectHandle: null,
      retryDelay: 1000,
      pingHandle: null,
    },
    publicProfile: null,
    publicProfileStats: null,
    postRegistry: {},           // post_id -> post payload shown anywhere in UI
    postComments: {},           // post_id -> { items, loaded }
    messageReplyTarget: null,
    messageReplyElements: null,
    notifications: {
      unread: 0,
      pollHandle: null,
      socket: null,
      reconnectHandle: null,
      retryDelay: 1000,
      pingHandle: null,
      active: false,
    },
  };

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  function loadJson(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (err) {
      console.warn('Failed to parse storage for', key, err);
      return fallback;
    }
  }

  function saveJson(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (err) {
      console.warn('Failed to persist storage for', key, err);
    }
  }

  function getAuth() {
    return {
      token: localStorage.getItem(TOKEN_KEY),
      username: localStorage.getItem(USERNAME_KEY),
      userId: localStorage.getItem(USER_ID_KEY)
    };
  }

  function setAuth({ token, username, userId }) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    if (username) localStorage.setItem(USERNAME_KEY, username);
    if (userId) localStorage.setItem(USER_ID_KEY, userId);
  }

  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem(USER_ID_KEY);
  }

  async function apiFetch(path, options = {}) {
    const opts = { ...options };
    const headers = new Headers(options.headers || {});
    const { token } = getAuth();

    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    if (opts.body && !(opts.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    opts.headers = headers;

    const response = await fetch(path, opts);
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
      ? await response.json().catch(() => ({}))
      : await response.text();

    if (!response.ok) {
      const message = (payload && payload.detail) || response.statusText || 'Request failed';
      throw new Error(message);
    }
    return payload;
  }

  function ensureAuthenticated() {
    const { token } = getAuth();
    if (!token) {
      showToast('Sign in to continue.', 'warning');
      window.location.href = '/login';
      throw new Error('Authentication required');
    }
  }

  function showToast(message, type = 'info') {
    const root = document.getElementById('toast-root');
    if (!root) return;
    const tone = palette[type] || palette.info;
    const toast = document.createElement('div');
    toast.className = `pointer-events-auto w-full max-w-md rounded-2xl px-4 py-3 text-sm shadow-lg transition ${tone}`;
    toast.innerHTML = `
      <div class="flex items-start gap-3">
        <span class="text-base">${iconForType(type)}</span>
        <div class="flex-1">${message}</div>
        <button class="text-xs opacity-70 hover:opacity-100">Close</button>
      </div>
    `;
    const closeBtn = toast.querySelector('button');
    const remove = () => {
      toast.classList.add('opacity-0', 'translate-y-2');
      setTimeout(() => toast.remove(), 200);
    };
    closeBtn.addEventListener('click', remove);
    root.appendChild(toast);
    setTimeout(remove, 4200);
  }

  function iconForType(type) {
    switch (type) {
      case 'success': return '✅';
      case 'error': return '⚠';
      case 'warning': return '⚠';
      default: return 'ℹ';
    }
  }

  function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  // -----------------------------------------------------------------------
  // Theme / Navbar
  // -----------------------------------------------------------------------

  function applyStoredTheme() {
    const stored = localStorage.getItem(THEME_KEY) || 'dark';
    if (stored === 'light') {
      document.documentElement.classList.remove('dark');
      document.body.classList.add('light-theme');
    } else {
      document.documentElement.classList.add('dark');
      document.body.classList.remove('light-theme');
    }
  }

  function initThemeToggle() {
    applyStoredTheme();
    const btn = document.getElementById('theme-toggle');
    refreshNavAuthState();
    if (!btn || btn.dataset.bound === 'true') return;
    btn.dataset.bound = 'true';
    btn.addEventListener('click', () => {
      const isDark = document.documentElement.classList.toggle('dark');
      if (isDark) {
        document.body.classList.remove('light-theme');
        localStorage.setItem(THEME_KEY, 'dark');
        showToast('Dark mode enabled', 'info');
      } else {
        document.body.classList.add('light-theme');
        localStorage.setItem(THEME_KEY, 'light');
        showToast('Light mode enabled', 'info');
      }
    });
  }

  function refreshNavAuthState() {
    const authBtn = document.getElementById('nav-auth-btn');
    if (!authBtn) return;
    const { token, username } = getAuth();
    if (token) {
      authBtn.textContent = username ? `@${username}` : 'Logout';
      authBtn.href = '#';
      authBtn.classList.add('border-emerald-500/40', 'text-emerald-300');
      authBtn.onclick = event => {
        event.preventDefault();
        clearAuth();
        showToast('Signed out successfully.', 'info');
        refreshNavAuthState();
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/';
        }
      };
      startNotificationIndicator();
    } else {
      authBtn.textContent = 'Login';
      authBtn.href = '/login';
      authBtn.classList.remove('border-emerald-500/40', 'text-emerald-300');
      authBtn.onclick = null;
      stopNotificationIndicator();
    }
  }

  // -----------------------------------------------------------------------
  // Notification indicator + websocket
  // -----------------------------------------------------------------------

  function startNotificationIndicator() {
    if (typeof window === 'undefined') return;
    const { token } = getAuth();
    if (!token) return;
    const controller = state.notifications;
    if (controller.active) return;
    controller.active = true;
    refreshNotificationSummary();
    if (!controller.pollHandle) {
      controller.pollHandle = window.setInterval(() => {
        refreshNotificationSummary();
      }, 60000);
    }
    connectNotificationSocket();
  }

  function stopNotificationIndicator() {
    const controller = state.notifications;
    controller.active = false;
    if (controller.pollHandle) {
      clearInterval(controller.pollHandle);
      controller.pollHandle = null;
    }
    disconnectNotificationSocket();
    updateNotificationBadge(0);
  }

  async function refreshNotificationSummary() {
    const { token } = getAuth();
    if (!token) return;
    try {
      const summary = await apiFetch('/notifications/summary');
      updateNotificationBadge(summary.unread_count || 0);
    } catch (error) {
      console.warn('[notifications] summary fetch failed', error);
    }
  }

  function updateNotificationBadge(nextCount) {
    const controller = state.notifications;
    const value = Math.max(0, Number.isFinite(nextCount) ? Number(nextCount) : controller.unread || 0);
    controller.unread = value;
    const badge = document.getElementById('nav-notifications-indicator');
    if (!badge) return;
    if (value <= 0) {
      badge.textContent = '';
      badge.classList.add('hidden');
      return;
    }
    badge.textContent = value > 99 ? '99+' : String(value);
    badge.classList.remove('hidden');
  }

  function connectNotificationSocket() {
    if (typeof window === 'undefined' || typeof window.WebSocket === 'undefined') {
      return;
    }
    const { token } = getAuth();
    if (!token) return;
    const controller = state.notifications;
    if (controller.socket && controller.socket.readyState === WebSocket.OPEN) {
      return;
    }
    disconnectNotificationSocket();
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${window.location.host}${NOTIFICATION_WS_PATH}?token=${encodeURIComponent(token)}`;
    let socket;
    try {
      socket = new WebSocket(url);
    } catch (error) {
      console.warn('[notifications/ws] failed to create socket', error);
      scheduleNotificationSocketReconnect();
      return;
    }
    controller.socket = socket;
    socket.addEventListener('open', () => {
      controller.retryDelay = 1000;
      startNotificationPing();
    });
    socket.addEventListener('message', event => handleNotificationSocketMessage(event.data));
    socket.addEventListener('close', () => {
      clearNotificationPing();
      controller.socket = null;
      scheduleNotificationSocketReconnect();
    });
    socket.addEventListener('error', error => {
      console.warn('[notifications/ws] socket error', error);
      clearNotificationPing();
      try {
        socket.close();
      } catch (_) {
        /* noop */
      }
    });
  }

  function disconnectNotificationSocket() {
    const controller = state.notifications;
    if (controller.reconnectHandle) {
      clearTimeout(controller.reconnectHandle);
      controller.reconnectHandle = null;
    }
    clearNotificationPing();
    if (controller.socket) {
      try {
        controller.socket.close();
      } catch (_) {
        /* noop */
      }
      controller.socket = null;
    }
    controller.retryDelay = 1000;
  }

  function scheduleNotificationSocketReconnect() {
    const controller = state.notifications;
    if (!controller.active || controller.reconnectHandle) return;
    const delay = Math.min(controller.retryDelay, 30000);
    controller.reconnectHandle = window.setTimeout(() => {
      controller.reconnectHandle = null;
      if (!controller.active) return;
      controller.retryDelay = Math.min(controller.retryDelay * 2, 30000);
      connectNotificationSocket();
    }, delay);
  }

  function safeNotificationSocketSend(payload) {
    const socket = state.notifications.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    try {
      socket.send(payload);
    } catch (error) {
      console.warn('[notifications/ws] failed to send payload', error);
    }
  }

  function startNotificationPing(intervalMs = 45000) {
    clearNotificationPing();
    safeNotificationSocketSend('ping');
    state.notifications.pingHandle = window.setInterval(() => {
      safeNotificationSocketSend('ping');
    }, intervalMs);
  }

  function clearNotificationPing() {
    const handle = state.notifications.pingHandle;
    if (handle) {
      clearInterval(handle);
      state.notifications.pingHandle = null;
    }
  }

  function handleNotificationSocketMessage(raw) {
    let payload;
    try {
      payload = typeof raw === 'string' ? JSON.parse(raw) : JSON.parse(String(raw));
    } catch (error) {
      console.warn('[notifications/ws] failed to parse payload', error, raw);
      return;
    }
    const type = String(payload?.type || '').toLowerCase();
    switch (type) {
      case 'notification.created':
        handleIncomingNotification(payload.notification || null);
        break;
      case 'notification.read_all':
        updateNotificationBadge(0);
        syncNotificationsListReadState();
        break;
      case 'ready':
        break;
      case 'pong':
        break;
      default:
        break;
    }
  }

  function handleIncomingNotification(record) {
    if (!record) return;
    if (!record.read) {
      updateNotificationBadge(state.notifications.unread + 1);
    } else {
      refreshNotificationSummary();
    }
    injectNotificationIntoList(record);
    if (record.type === 'message.received') {
      showToast(record.content || 'New message received.', 'info');
    }
  }

  function injectNotificationIntoList(record) {
    const list = document.getElementById('notifications-list');
    if (!list) return;
    const empty = document.getElementById('notifications-empty');
    if (empty) empty.classList.add('hidden');
    const item = createNotificationItem(record);
    list.prepend(item);
    const count = document.getElementById('notifications-count');
    if (count) {
      count.textContent = `${Math.max(state.notifications.unread, 0)} unread`;
    }
  }

  function syncNotificationsListReadState() {
    const list = document.getElementById('notifications-list');
    if (!list) return;
    list.querySelectorAll('[data-notification-item]').forEach(item => {
      item.classList.remove('border', 'border-indigo-400/30', 'bg-indigo-500/10');
      item.classList.add('bg-slate-900/70');
      const status = item.querySelector('[data-notification-status]');
      if (status) {
        status.textContent = 'Read';
      }
    });
  }

  // -----------------------------------------------------------------------
  // Avatar helpers
  // -----------------------------------------------------------------------

  function resolveAvatarUrl(rawUrl) {
    if (typeof rawUrl !== 'string') {
      return DEFAULT_AVATAR;
    }

    const trimmed = rawUrl.trim();
    if (!trimmed) {
      return DEFAULT_AVATAR;
    }

    if (trimmed.startsWith('data:image')) {
      return trimmed;
    }

    if (shouldSkipCacheBuster(trimmed)) {
      return trimmed;
    }

    const cacheBuster = Date.now();
    return trimmed.includes('?')
      ? `${trimmed}&v=${cacheBuster}`
      : `${trimmed}?v=${cacheBuster}`;
  }

  function shouldSkipCacheBuster(url) {
    try {
      const parsed = new URL(url, window.location.origin);

      if (parsed.hostname.includes('digitaloceanspaces.com')) {
        return true;
      }

      const params = parsed.searchParams;

      return (
        params.has('X-Amz-Signature') ||
        params.has('X-Amz-Credential') ||
        params.has('X-Amz-Algorithm') ||
        params.has('AWSAccessKeyId')
      );
    } catch {
      return false;
    }
  }

  function applyAvatarToImg(img, rawUrl) {
    if (!img) return;

    console.log('[avatar] applyAvatarToImg for', img.id || img.dataset.userId, 'rawUrl =', rawUrl);

    if (!rawUrl) {
      img.src = DEFAULT_AVATAR;
      return;
    }

    const finalUrl = shouldSkipCacheBuster(rawUrl)
      ? rawUrl
      : resolveAvatarUrl(rawUrl);

    img.src = finalUrl;
  }

  function updateAvatarCacheEntry(userId, rawUrl) {
    if (!userId) return;

    if (!rawUrl || typeof rawUrl !== 'string' || !rawUrl.trim()) {
      return;
    }

    const key = String(userId);
    state.avatarCache[key] = resolveAvatarUrl(rawUrl);
  }

  function cacheProfile(profile) {
    if (!profile || !profile.id) return null;
    updateAvatarCacheEntry(profile.id, profile.avatar_url);
    return state.avatarCache[String(profile.id)];
  }

  function updateCurrentUserAvatarImages(rawUrl) {
    const avatars = document.querySelectorAll('[data-current-user-avatar]');
    avatars.forEach(img => applyAvatarToImg(img, rawUrl));
  }

  async function fetchCurrentUserProfile() {
    const { userId } = getAuth();

    if (!userId) {
      const me = await apiFetch('/auth/me');
      console.log('[auth/me] avatar_url:', me.avatar_url || '(none)');
      cacheProfile(me);
      state.currentProfileAvatar = me.avatar_url || null;
      updateCurrentUserAvatarImages(me.avatar_url);
      return me;
    }

    const profile = await apiFetch(`/profiles/by-id/${encodeURIComponent(userId)}`);
    console.log('[profiles/by-id] avatar_url:', profile.avatar_url || '(none)');
    cacheProfile(profile);
    state.currentProfileAvatar = profile.avatar_url || null;
    updateCurrentUserAvatarImages(profile.avatar_url);
    return profile;
  }

  // -----------------------------------------------------------------------
  // Feed
  // -----------------------------------------------------------------------

  async function initFeedPage() {
    initThemeToggle();
    await loadFeed();
    setupComposer();
    initRealtimeUpdates();
    startFeedAutoRefresh(15000);
  }

  function setupComposer() {
    const form = document.getElementById('composer-form');
    if (!form) return;
    const fileInput = form.querySelector('input[type="file"]');
    const previewWrapper = document.getElementById('media-preview');
    const previewImage = document.getElementById('media-preview-image');

    if (fileInput && previewWrapper && previewImage) {
      fileInput.addEventListener('change', () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) {
          previewWrapper.classList.add('hidden');
          previewImage.src = '';
          return;
        }
        const reader = new FileReader();
        reader.onload = e => {
          previewWrapper.classList.remove('hidden');
          previewImage.src = e.target.result;
        };
        reader.readAsDataURL(file);
      });
    }

    form.addEventListener('submit', async event => {
      event.preventDefault();
      try {
        ensureAuthenticated();
      } catch {
        return;
      }
      const formData = new FormData(form);
      const caption = formData.get('caption');
      if (!caption || String(caption).trim().length === 0) {
        showToast('Write something before publishing.', 'warning');
        return;
      }
      try {
        await apiFetch('/posts/', {
          method: 'POST',
          body: formData
        });
        showToast('Post published successfully.', 'success');
        form.reset();
        if (previewWrapper) previewWrapper.classList.add('hidden');
        await loadFeed({ forceRefresh: true });
      } catch (error) {
        showToast(error.message || 'Unable to publish post.', 'error');
      }
    });
  }

  function startFeedAutoRefresh(intervalMs = 0) {
    if (state.feedRefreshHandle) {
      clearInterval(state.feedRefreshHandle);
      state.feedRefreshHandle = null;
    }

    if (!intervalMs || intervalMs <= 0) {
      return;
    }

    state.feedRefreshHandle = window.setInterval(() => {
      const socket = state.realtime.socket;
      const hasLiveSocket = typeof WebSocket !== 'undefined' && socket && socket.readyState === WebSocket.OPEN;
      if (hasLiveSocket) {
        return;
      }
      loadFeed({ forceRefresh: true, silent: true, onlyOnChange: true }).catch(error => {
        console.warn('[feed] auto refresh failed', error);
      });
    }, intervalMs);

    window.addEventListener(
      'beforeunload',
      () => {
        if (state.feedRefreshHandle) {
          clearInterval(state.feedRefreshHandle);
          state.feedRefreshHandle = null;
        }
      },
      { once: true }
    );
  }

  function initRealtimeUpdates() {
    if (typeof window === 'undefined' || typeof window.WebSocket === 'undefined') {
      console.warn('[realtime] WebSocket unsupported; relying on polling');
      return;
    }
    if (state.realtime.socket) return;
    connectRealtimeFeed();
  }

  function connectRealtimeFeed() {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${window.location.host}${REALTIME_WS_PATH}`;
    if (state.realtime.reconnectHandle) {
      clearTimeout(state.realtime.reconnectHandle);
      state.realtime.reconnectHandle = null;
    }

    let socket;
    try {
      socket = new WebSocket(url);
    } catch (error) {
      console.warn('[realtime] failed to create socket', error);
      startFeedAutoRefresh(15000);
      scheduleRealtimeReconnect();
      return;
    }

    state.realtime.socket = socket;
    socket.addEventListener('open', () => {
      state.realtime.retryDelay = 1000;
      console.log('[realtime] connected');
      startFeedAutoRefresh(0);
      safeRealtimeSend({ type: 'hello', at: Date.now() });
      startRealtimePing();
    });
    socket.addEventListener('message', event => handleRealtimeMessage(event.data));
    socket.addEventListener('close', () => {
      clearRealtimePing();
      state.realtime.socket = null;
      startFeedAutoRefresh(15000);
      scheduleRealtimeReconnect();
    });
    socket.addEventListener('error', error => {
      console.warn('[realtime] socket error', error);
      clearRealtimePing();
      try {
        socket.close();
      } catch (_) {
        /* noop */
      }
    });
  }

  function safeRealtimeSend(payload) {
    const socket = state.realtime.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    try {
      socket.send(JSON.stringify(payload));
    } catch (error) {
      console.warn('[realtime] failed to send payload', error);
    }
  }

  function startRealtimePing(intervalMs = 30000) {
    clearRealtimePing();
    safeRealtimeSend({ type: 'ping', at: Date.now() });
    state.realtime.pingHandle = window.setInterval(() => {
      safeRealtimeSend({ type: 'ping', at: Date.now() });
    }, intervalMs);
  }

  function clearRealtimePing() {
    if (state.realtime.pingHandle) {
      clearInterval(state.realtime.pingHandle);
      state.realtime.pingHandle = null;
    }
  }

  function scheduleRealtimeReconnect() {
    if (state.realtime.reconnectHandle) return;
    const delay = Math.min(state.realtime.retryDelay, 30000);
    state.realtime.reconnectHandle = window.setTimeout(() => {
      state.realtime.reconnectHandle = null;
      state.realtime.retryDelay = Math.min(state.realtime.retryDelay * 2, 30000);
      connectRealtimeFeed();
    }, delay);
  }

  function handleRealtimeMessage(raw) {
    let payload;
    try {
      payload = typeof raw === 'string' ? JSON.parse(raw) : JSON.parse(String(raw));
    } catch (error) {
      console.warn('[realtime] failed to parse payload', error, raw);
      return;
    }

    switch ((payload?.type || '').toLowerCase()) {
      case 'post_created':
        requestRealtimeFeedRefresh();
        break;
      case 'ready':
        console.log('[realtime] server acknowledged subscription');
        break;
      case 'pong':
        break;
      default:
        break;
    }
  }

  function requestRealtimeFeedRefresh() {
    if (state.realtime.pendingRefresh) return;
    state.realtime.pendingRefresh = true;
    window.setTimeout(() => {
      state.realtime.pendingRefresh = false;
      loadFeed({ forceRefresh: true, silent: true, onlyOnChange: true }).catch(error => {
        console.warn('[realtime] feed refresh failed', error);
      });
    }, 250);
  }

  function computeFeedSignature(items) {
    if (!Array.isArray(items) || items.length === 0) {
      return `len:${items ? items.length : 0}`;
    }
    return items
      .map(item => `${item?.id ?? 'unknown'}:${item?.created_at ?? ''}:${item?.caption?.length ?? 0}:${item?.media_url ?? ''}`)
      .join('|');
  }

  async function loadFeed(options = {}) {
    const normalized = typeof options === 'boolean' ? { forceRefresh: options } : options;
    const { forceRefresh = false, silent = false, onlyOnChange = false } = normalized;

    const loading = document.getElementById('feed-loading');
    const empty = document.getElementById('feed-empty');
    const list = document.getElementById('feed-list');
    const loadMore = document.getElementById('feed-load-more');
    const countBadge = document.getElementById('feed-count');
    if (!list) return;

    if (state.feedLoading) return;
    state.feedLoading = true;

    if (!silent && loading) loading.classList.remove('hidden');
    if (!silent && empty) empty.classList.add('hidden');
    if (forceRefresh) {
      state.feedItems = [];
      state.feedCursor = 0;
      if (!silent) list.innerHTML = '';
    }

    try {
      const data = await apiFetch('/posts/feed');
      const incomingItems = Array.isArray(data.items) ? data.items : [];
      const newSignature = computeFeedSignature(incomingItems);

      if (onlyOnChange && state.feedSignature === newSignature) {
        return;
      }

      state.feedSignature = newSignature;
      state.feedItems = incomingItems;
      state.feedCursor = 0;
      list.innerHTML = '';
      await ensureAvatarCache(state.feedItems);
      if (state.feedItems.length) {
        const sample = state.feedItems[0];
        console.log(
          '[feed] sample author',
          sample.user_id,
          'avatar',
          state.avatarCache[String(sample.user_id)] || DEFAULT_AVATAR
        );
      }
      renderNextFeedBatch();
      if (countBadge) {
        countBadge.textContent = `${state.feedItems.length} posts`;
      }
      if (state.feedItems.length === 0 && empty) {
        empty.classList.remove('hidden');
      }
      if (loadMore) {
        loadMore.classList.toggle('hidden', state.feedItems.length <= FEED_BATCH_SIZE);
        loadMore.onclick = () => renderNextFeedBatch();
      }
    } catch (error) {
      showToast(error.message || 'Unable to load feed.', 'error');
    } finally {
      state.feedLoading = false;
      if (!silent && loading) loading.classList.add('hidden');
    }
  }

  async function ensureAvatarCache(posts) {
    const { userId: currentUserId } = getAuth();
    const idsNeedingFetch = [];

    posts.forEach(post => {
      if (!post || !post.user_id) return;
      const key = String(post.user_id);
      if (post.avatar_url) {
        updateAvatarCacheEntry(key, post.avatar_url);
      }
      if (!state.avatarCache[key]) {
        idsNeedingFetch.push(key);
      }
    });

    const uniqueIds = Array.from(new Set(idsNeedingFetch));
    const fetches = uniqueIds.map(async userId => {
      if (state.avatarCache[userId]) return;
      try {
        if (currentUserId && String(userId) === String(currentUserId)) {
          await fetchCurrentUserProfile();
          return;
        }
        const profile = await apiFetch(`/profiles/by-id/${encodeURIComponent(userId)}`);
        cacheProfile(profile);
      } catch (error) {
        console.warn('[avatar-cache] Failed to load profile for:', userId, error);
      }
    });
    await Promise.all(fetches);
  }

  function renderNextFeedBatch() {
    const list = document.getElementById('feed-list');
    const loadMore = document.getElementById('feed-load-more');
    if (!list) return;
    const authMeta = getAuth();
    const slice = state.feedItems.slice(state.feedCursor, state.feedCursor + FEED_BATCH_SIZE);
    slice.forEach(post => {
      updateAvatarCacheEntry(post.user_id, post.avatar_url);
      const cacheKey = post && post.user_id ? String(post.user_id) : null;
      const avatarUrl =
        (cacheKey && state.avatarCache[cacheKey]) ||
        resolveAvatarUrl(post.avatar_url) ||
        DEFAULT_AVATAR;
      list.appendChild(createPostCard(post, authMeta, avatarUrl));
    });
    state.feedCursor += slice.length;
    if (loadMore) {
      loadMore.classList.toggle('hidden', state.feedCursor >= state.feedItems.length);
    }
  }

  function syncFollowStateForUser(userId, isFollowing) {
    if (!userId) return;
    const key = String(userId);
    state.feedItems.forEach(item => {
      if (String(item.user_id) === key) {
        item.is_following_author = isFollowing;
      }
    });
    document.querySelectorAll(`[data-role="follow-button"][data-user-id="${key}"]`).forEach(button => {
      applyFollowButtonState(button, isFollowing);
    });
  }

  function applyFollowButtonState(button, isFollowing) {
    if (!button) return;
    button.dataset.following = isFollowing ? 'true' : 'false';
    const baseClasses = 'follow-toggle inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2';
    if (isFollowing) {
      button.className = `${baseClasses} border-emerald-400/70 bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/25`;
      button.innerHTML = '<span>✓</span><span>Following</span>';
    } else {
      button.className = `${baseClasses} border-indigo-500/60 bg-indigo-600 text-white hover:bg-indigo-500`;
      button.innerHTML = '<span>+</span><span>Follow</span>';
    }
  }

  async function submitFollowMutation(targetUserId, shouldFollow) {
    const endpoint = `/follows/${encodeURIComponent(targetUserId)}`;
    return apiFetch(endpoint, { method: shouldFollow ? 'POST' : 'DELETE' });
  }

  function applyPublicProfileStats(stats) {
    state.publicProfileStats = stats || null;
    const followerTargets = [
      document.getElementById('public-profile-followers'),
      document.getElementById('profile-followers-count')
    ];
    followerTargets.forEach(node => {
      if (!node) return;
      const fallback = node.dataset?.emptyLabel || '—';
      node.textContent = stats ? String(stats.followers_count ?? '0') : fallback;
    });

    const followingTargets = [
      document.getElementById('public-profile-following'),
      document.getElementById('profile-following-count')
    ];
    followingTargets.forEach(node => {
      if (!node) return;
      const fallback = node.dataset?.emptyLabel || '—';
      node.textContent = stats ? String(stats.following_count ?? '0') : fallback;
    });
  }

  function updatePostCountBadges() {
    const profileFeed = document.getElementById('profile-feed');
    if (profileFeed) {
      const total = profileFeed.querySelectorAll('article').length;
      const counter = document.getElementById('profile-post-count');
      if (counter) counter.textContent = String(total);
      const empty = document.getElementById('profile-feed-empty');
      if (empty) empty.classList.toggle('hidden', total > 0);
    }

    const publicFeed = document.getElementById('public-profile-posts');
    if (publicFeed) {
      const total = publicFeed.querySelectorAll('article').length;
      const badge = document.getElementById('public-profile-post-count');
      if (badge) badge.textContent = `${total} posts`;
      const empty = document.getElementById('public-profile-posts-empty');
      if (empty) empty.classList.toggle('hidden', total > 0);
    }
  }

  function prunePostFromCollections(postId) {
    if (!postId) return;
    const targetId = String(postId);
    const removalIndex = state.feedItems.findIndex(item => String(item.id) === targetId);
    state.feedItems = state.feedItems.filter(item => String(item.id) !== targetId);
    if (removalIndex !== -1 && state.feedCursor > removalIndex) {
      state.feedCursor = Math.max(state.feedCursor - 1, 0);
    }
    state.feedCursor = Math.min(state.feedCursor, state.feedItems.length);
    const countBadge = document.getElementById('feed-count');
    if (countBadge) {
      countBadge.textContent = `${state.feedItems.length} posts`;
    }
    const loadMore = document.getElementById('feed-load-more');
    if (loadMore) {
      loadMore.classList.toggle('hidden', state.feedCursor >= state.feedItems.length);
    }
  }

  function removePostCard(cardElement) {
    if (!cardElement) return;
    const parent = cardElement.parentElement;
    cardElement.classList.add('opacity-0', 'translate-y-2');
    window.setTimeout(() => {
      cardElement.remove();
      if (parent && parent.id === 'feed-list' && parent.children.length === 0) {
        const empty = document.getElementById('feed-empty');
        if (empty) empty.classList.remove('hidden');
      }
      updatePostCountBadges();
    }, 180);
  }

  async function handleDeletePost(post, cardElement, trigger) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!post?.id) {
      showToast('Missing post identifier.', 'error');
      return;
    }
    const confirmed = window.confirm('Delete this post? This cannot be undone.');
    if (!confirmed) return;
    if (trigger) {
      trigger.disabled = true;
      trigger.classList.add('opacity-60', 'cursor-not-allowed');
    }
    try {
      await apiFetch(`/posts/${encodeURIComponent(post.id)}`, { method: 'DELETE' });
      showToast('Post deleted.', 'success');
      prunePostFromCollections(post.id);
      removePostCard(cardElement);
    } catch (error) {
      showToast(error.message || 'Unable to delete post.', 'error');
      if (trigger) {
        trigger.disabled = false;
        trigger.classList.remove('opacity-60', 'cursor-not-allowed');
      }
    }
  }

  function registerPostInstance(post) {
    if (!post || !post.id) return;
    state.postRegistry[String(post.id)] = post;
  }

  function getCommentStore(postId) {
    if (!postId) return { items: [], loaded: false };
    const key = String(postId);
    if (!state.postComments[key]) {
      state.postComments[key] = { items: [], loaded: false };
    }
    return state.postComments[key];
  }

  function findCommentById(comments, targetId) {
    if (!Array.isArray(comments) || !targetId) return null;
    const key = String(targetId);
    for (const comment of comments) {
      if (String(comment.id) === key) return comment;
      const childMatch = findCommentById(comment.replies || [], targetId);
      if (childMatch) return childMatch;
    }
    return null;
  }

  function renderCommentList(postId, comments, container) {
    if (!container) return;
    container.innerHTML = '';
    const emptyState = container.parentElement?.querySelector('[data-role="comments-empty"]');
    const hasComments = Array.isArray(comments) && comments.length > 0;
    if (!hasComments) {
      if (emptyState) emptyState.classList.remove('hidden');
      return;
    }
    if (emptyState) emptyState.classList.add('hidden');
    comments.forEach(comment => {
      container.appendChild(createCommentBlock(postId, comment, 0));
    });
  }

  function createCommentBlock(postId, comment, depth) {
    const wrapper = document.createElement('div');
    wrapper.className = 'rounded-2xl border border-slate-800/70 bg-slate-950/60 p-4 shadow-sm shadow-black/10';
    wrapper.dataset.commentId = comment.id;
    if (depth > 0) {
      wrapper.style.marginLeft = `${Math.min(depth, 3) * 16}px`;
    }
    const avatarId = `comment-avatar-${comment.id}`;
    const author = comment.username ? `@${comment.username}` : 'User';
    const previewText = comment.content || '';
    wrapper.innerHTML = `
      <div class="flex items-start gap-3">
        <div class="h-8 w-8 flex-shrink-0 overflow-hidden rounded-full border border-slate-800/70 bg-slate-900/60">
          <img id="${avatarId}" alt="${author}" class="h-full w-full object-cover" />
        </div>
        <div class="flex-1">
          <div class="flex items-center justify-between text-xs text-slate-400">
            <span class="font-semibold text-slate-200">${author}</span>
            <time class="text-[11px]">${formatDate(comment.created_at)}</time>
          </div>
          <p class="mt-1 text-sm text-slate-200">${previewText}</p>
          <div class="mt-2 flex gap-3 text-[11px] text-indigo-200">
            <button type="button" data-role="comment-reply" class="hover:text-white">Reply</button>
          </div>
        </div>
      </div>
    `;
    const avatarNode = wrapper.querySelector(`#${avatarId}`);
    applyAvatarToImg(avatarNode, comment.avatar_url);
    const replyButton = wrapper.querySelector('[data-role="comment-reply"]');
    if (replyButton) {
      replyButton.addEventListener('click', () => {
        const panel = wrapper.closest('[data-role="comment-panel"]');
        beginCommentReply(postId, comment, panel);
      });
    }
    if (Array.isArray(comment.replies) && comment.replies.length) {
      const repliesContainer = document.createElement('div');
      repliesContainer.className = 'mt-3 space-y-3';
      comment.replies.forEach(reply => {
        repliesContainer.appendChild(createCommentBlock(postId, reply, depth + 1));
      });
      wrapper.appendChild(repliesContainer);
    }
    return wrapper;
  }

  async function loadCommentsForPost(postId, panel) {
    if (!panel || !postId) return;
    const list = panel.querySelector('[data-role="comment-list"]');
    const store = getCommentStore(postId);
    if (store.loaded) {
      renderCommentList(postId, store.items, list);
      return;
    }
    panel.classList.add('opacity-70');
    try {
      const response = await apiFetch(`/posts/${encodeURIComponent(postId)}/comments`);
      const fetched = Array.isArray(response.items) ? response.items : [];
      if (store.loaded && Array.isArray(store.items) && store.items.length) {
        const merged = new Map();
        store.items.forEach(item => {
          if (item?.id) {
            merged.set(String(item.id), item);
          }
        });
        fetched.forEach(item => {
          if (item?.id) {
            merged.set(String(item.id), item);
          }
        });
        store.items = Array.from(merged.values());
      } else {
        store.items = fetched;
      }
      store.loaded = true;
      renderCommentList(postId, store.items, list);
    } catch (error) {
      showToast(error.message || 'Unable to load comments.', 'error');
    } finally {
      panel.classList.remove('opacity-70');
    }
  }

  function beginCommentReply(postId, comment, panel) {
    if (!panel || !comment) return;
    const form = panel.querySelector('[data-role="comment-form"]');
    const pill = panel.querySelector('[data-role="comment-reply-pill"]');
    const usernameNode = panel.querySelector('[data-role="comment-reply-username"]');
    const previewNode = panel.querySelector('[data-role="comment-reply-preview"]');
    if (!form || !pill || !usernameNode) return;
    form.dataset.replyId = comment.id;
    usernameNode.textContent = comment.username ? `@${comment.username}` : 'this comment';
    if (previewNode) {
      const preview = (comment.content || '').trim();
      previewNode.textContent = preview ? preview.slice(0, 160) + (preview.length > 160 ? '…' : '') : 'No text available.';
    }
    pill.classList.remove('hidden');
    focusCommentInput(panel);
  }

  function resetCommentReply(panel) {
    if (!panel) return;
    const form = panel.querySelector('[data-role="comment-form"]');
    if (form) delete form.dataset.replyId;
    const pill = panel.querySelector('[data-role="comment-reply-pill"]');
    if (pill) pill.classList.add('hidden');
    const usernameNode = panel.querySelector('[data-role="comment-reply-username"]');
    if (usernameNode) usernameNode.textContent = '@commenter';
    const previewNode = panel.querySelector('[data-role="comment-reply-preview"]');
    if (previewNode) previewNode.textContent = '';
  }

  function appendCommentRecord(postId, comment) {
    const store = getCommentStore(postId);
    if (!store.loaded) {
      store.items.push(comment);
      return;
    }
    if (comment.parent_id) {
      const parent = findCommentById(store.items, comment.parent_id);
      if (!parent) {
        store.items.push(comment);
        return;
      }
      if (!Array.isArray(parent.replies)) parent.replies = [];
      parent.replies.push(comment);
    } else {
      store.items.push(comment);
    }
  }

  function updateCommentCountDisplays(postId, nextCount) {
    const value = typeof nextCount === 'number' ? nextCount : 0;
    document.querySelectorAll(`[data-role="comment-count"][data-post-id="${postId}"]`).forEach(node => {
      node.textContent = String(value);
    });
  }

  function applyLikeButtonState(button, isLiked, likeCount) {
    if (!button) return;
    const baseClasses = 'inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2';
    button.dataset.liked = isLiked ? 'true' : 'false';
    button.className = isLiked
      ? `${baseClasses} border-rose-500/40 bg-rose-500/20 text-rose-100 hover:bg-rose-500/30`
      : `${baseClasses} border-indigo-500/60 bg-slate-800/80 text-white hover:bg-indigo-600`;
    const label = button.querySelector('[data-role="like-label"]');
    const count = button.querySelector('[data-role="like-count"]');
    if (label) label.textContent = isLiked ? 'Liked' : 'Like';
    if (count) count.textContent = String(likeCount ?? 0);
  }

  function updateLikeButtonsForPost(postId, isLiked, likeCount) {
    document.querySelectorAll(`[data-role="like-button"][data-post-id="${postId}"]`).forEach(button => {
      applyLikeButtonState(button, isLiked, likeCount);
    });
  }

  function setPostEngagementSnapshot(snapshot) {
    if (!snapshot || !snapshot.post_id) return;
    const key = String(snapshot.post_id);
    const { like_count = 0, comment_count = 0, viewer_has_liked = false } = snapshot;
    const cached = state.postRegistry[key];
    if (cached) {
      cached.like_count = like_count;
      cached.comment_count = comment_count;
      cached.viewer_has_liked = viewer_has_liked;
    }
    state.feedItems.forEach(item => {
      if (String(item.id) === key) {
        item.like_count = like_count;
        item.comment_count = comment_count;
        item.viewer_has_liked = viewer_has_liked;
      }
    });
    updateLikeButtonsForPost(key, viewer_has_liked, like_count);
    updateCommentCountDisplays(key, comment_count);
  }

  async function togglePostLike(post, button) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!post?.id || !button || button.disabled) return;
    const shouldUnlike = button.dataset.liked === 'true';
    button.disabled = true;
    button.classList.add('opacity-70');
    try {
      const snapshot = await apiFetch(`/posts/${encodeURIComponent(post.id)}/likes`, {
        method: shouldUnlike ? 'DELETE' : 'POST'
      });
      setPostEngagementSnapshot(snapshot);
      post.viewer_has_liked = snapshot.viewer_has_liked;
      post.like_count = snapshot.like_count;
      if (!shouldUnlike) {
        showToast('Post liked.', 'success');
      }
    } catch (error) {
      showToast(error.message || 'Unable to update like.', 'error');
    } finally {
      button.disabled = false;
      button.classList.remove('opacity-70');
    }
  }

  function focusCommentInput(panel) {
    if (!panel) return;
    const textarea = panel.querySelector('textarea');
    if (textarea) {
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    }
  }

  function toggleCommentPanel(button, panel, post) {
    if (!button || !panel || !post?.id) return;
    const isOpen = button.dataset.open === 'true';
    const nextState = !isOpen;
    button.dataset.open = nextState ? 'true' : 'false';
    panel.classList.toggle('hidden', !nextState);
    const label = button.querySelector('[data-role="comment-toggle-label"]');
    if (label) label.textContent = nextState ? 'Hide' : 'Comment';
    if (nextState) {
      loadCommentsForPost(post.id, panel);
      focusCommentInput(panel);
    } else {
      resetCommentReply(panel);
    }
  }

  async function submitCommentForm(post, panel, form) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!post?.id || !panel || !form) return;
    const textarea = form.querySelector('textarea');
    const content = String(textarea?.value || '').trim();
    if (!content) {
      showToast('Write a comment before posting.', 'warning');
      return;
    }
    const submitButton = form.querySelector('button[type="submit"]');
    form.classList.add('opacity-70');
    if (submitButton) submitButton.disabled = true;
    try {
      const payload = {
        content,
        parent_id: form.dataset.replyId || null,
      };
      const comment = await apiFetch(`/posts/${encodeURIComponent(post.id)}/comments`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      appendCommentRecord(post.id, comment);
      const store = getCommentStore(post.id);
      store.loaded = true;
      const list = panel.querySelector('[data-role="comment-list"]');
      renderCommentList(post.id, store.items, list);
      if (textarea) textarea.value = '';
      resetCommentReply(panel);
      post.comment_count = (post.comment_count || 0) + 1;
      const snapshot = {
        post_id: post.id,
        like_count: typeof post.like_count === 'number' ? post.like_count : 0,
        comment_count: post.comment_count,
        viewer_has_liked: Boolean(post.viewer_has_liked),
      };
      setPostEngagementSnapshot(snapshot);
      showToast('Comment added.', 'success');
    } catch (error) {
      showToast(error.message || 'Unable to add comment.', 'error');
    } finally {
      form.classList.remove('opacity-70');
      if (submitButton) submitButton.disabled = false;
    }
  }

  function resetButtonListeners(buttonId) {
    const original = document.getElementById(buttonId);
    if (!original) return null;
    if (!original.parentNode) return original;
    const clone = original.cloneNode(true);
    original.parentNode.replaceChild(clone, original);
    return clone;
  }

  function createPostCard(post, currentUserMeta, avatarUrl) {
    const el = document.createElement('article');
    el.className =
      'group rounded-3xl bg-slate-900/80 p-6 shadow-lg shadow-black/20 transition hover:-translate-y-1 hover:shadow-indigo-500/20 card-surface';
    const postId = post?.id;
    const rawCurrentUsername = typeof currentUserMeta === 'string' ? currentUserMeta : currentUserMeta?.username;
    const currentUsername = rawCurrentUsername ? String(rawCurrentUsername).replace(/^@/, '') : null;
    const currentUserId = typeof currentUserMeta === 'object' ? currentUserMeta?.userId : null;
    const hasAuthToken = typeof currentUserMeta === 'object' && Boolean(currentUserMeta?.token);
    const normalizedPostUsername = post?.username ? String(post.username).replace(/^@/, '') : null;
    const isCurrentUser =
      (currentUserId && String(post.user_id) === String(currentUserId)) ||
      (currentUsername && normalizedPostUsername && currentUsername.toLowerCase() === normalizedPostUsername.toLowerCase());
    const displayName = post.username
      ? `@${normalizedPostUsername || post.username}`
      : isCurrentUser && currentUsername
      ? `@${currentUsername}`
      : `User ${String(post.user_id).slice(0, 8)}`;
    const timestamp = formatDate(post.created_at);
    const mediaUrl = typeof post.media_url === 'string' ? post.media_url.trim() : '';
    const media = mediaUrl
      ? `<img src="${mediaUrl}" class="mt-4 w-full rounded-2xl object-cover" alt="">`
      : '';
    const likeCount = typeof post.like_count === 'number' ? post.like_count : 0;
    const commentCount = typeof post.comment_count === 'number' ? post.comment_count : 0;
    const viewerHasLiked = Boolean(post.viewer_has_liked);
    const showFollowButton = Boolean(hasAuthToken && !isCurrentUser);
    const initialFollowing = Boolean(post.is_following_author);
    const followButtonMarkup = showFollowButton
      ? `<button data-role="follow-button" data-user-id="${post.user_id}" data-following="${initialFollowing ? 'true' : 'false'}"></button>`
      : '';
    const deleteButtonMarkup = isCurrentUser
      ? `<button
          data-role="delete-post"
          data-post-id="${post.id}"
          class="inline-flex items-center gap-2 rounded-full border border-rose-500/40 px-4 py-2 text-xs font-semibold text-rose-200 transition hover:border-rose-400 hover:bg-rose-500/10 hover:text-white"
        >
          <span aria-hidden="true">🗑</span>
          <span>Delete</span>
        </button>`
      : '';
    const commentPanelMarkup = postId
      ? `
        <section
          data-role="comment-panel"
          data-post-id="${postId}"
          class="mt-5 hidden rounded-2xl border border-slate-800/60 bg-slate-950/60 p-4 shadow-inner shadow-black/20"
        >
          <div data-role="comments-empty" class="text-sm text-slate-400">
            No comments yet. Be the first to say something nice.
          </div>
          <div data-role="comment-list" class="mt-4 space-y-3"></div>
          <form data-role="comment-form" class="mt-4 space-y-3">
            <div
              data-role="comment-reply-pill"
              class="hidden rounded-2xl border border-indigo-500/30 bg-indigo-500/5 px-3 py-2 text-xs text-indigo-100"
            >
              <div class="flex items-start justify-between gap-3">
                <div>
                  <p class="font-semibold text-indigo-200">
                    Replying to <span data-role="comment-reply-username" class="text-white">@commenter</span>
                  </p>
                  <p data-role="comment-reply-preview" class="mt-1 text-[11px] text-slate-300"></p>
                </div>
                <button
                  type="button"
                  data-role="comment-reply-cancel"
                  class="text-[11px] font-semibold text-indigo-200 transition hover:text-white"
                >
                  Cancel
                </button>
              </div>
            </div>
            <textarea
              data-role="comment-input"
              rows="3"
              class="w-full rounded-2xl border border-slate-800/70 bg-slate-900/80 p-3 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              placeholder="Share your thoughts…"
              required
            ></textarea>
            <div class="flex items-center justify-between gap-3">
              <button type="button" data-role="comment-reset" class="text-xs font-semibold text-slate-400 hover:text-white">
                Clear
              </button>
              <button
                type="submit"
                class="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
              >
                <span class="text-base">➤</span>
                <span>Post comment</span>
              </button>
            </div>
          </form>
        </section>
      `
      : '';
    el.innerHTML = `
      <header class="flex items-center gap-4">
        <div class="flex flex-1 items-center gap-4">
          <img data-role="post-avatar"
               data-user-id="${post.user_id}"
               src="${DEFAULT_AVATAR}"
               class="h-12 w-12 rounded-full object-cover"
               alt="Post avatar" />
          <div>
            <p class="text-sm font-semibold text-white dark:text-white">${displayName}</p>
            <p class="text-xs text-slate-400">${timestamp}</p>
          </div>
        </div>
        ${followButtonMarkup}
      </header>
      <p class="mt-4 whitespace-pre-line text-sm text-slate-200">${post.caption || ''}</p>
      ${media}
      <footer class="mt-6 flex flex-wrap items-center gap-3 text-sm text-slate-400">
        <button
          data-role="like-button"
          data-post-id="${post.id}"
          class="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold"
        >
          <span aria-hidden="true">❤</span>
          <span data-role="like-label">${viewerHasLiked ? 'Liked' : 'Like'}</span>
          <span data-role="like-count" class="text-[11px] text-slate-300">${likeCount}</span>
        </button>
        <button
          data-role="comment-toggle"
          data-post-id="${post.id}"
          data-open="false"
          class="inline-flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-800/80 px-4 py-2 text-xs font-semibold text-white transition hover:border-indigo-500/60 hover:bg-indigo-600"
        >
          <span aria-hidden="true">💬</span>
          <span data-role="comment-toggle-label">Comment</span>
          <span
            data-role="comment-count"
            data-post-id="${post.id}"
            class="text-[11px] text-slate-200"
          >${commentCount}</span>
        </button>
        <button class="share-btn inline-flex items-center gap-2 rounded-full bg-slate-800/90 px-4 py-2 transition hover:bg-indigo-600 hover:text-white"><span>↗</span><span>Share</span></button>
        ${deleteButtonMarkup}
      </footer>
      ${commentPanelMarkup}
    `;
    registerPostInstance(post);
    const avatarImg = el.querySelector('[data-role="post-avatar"]');
    applyAvatarToImg(avatarImg, avatarUrl);
    const followButton = el.querySelector('[data-role="follow-button"]');
    if (followButton) {
      applyFollowButtonState(followButton, initialFollowing);
      followButton.addEventListener('click', async event => {
        event.preventDefault();
        try {
          ensureAuthenticated();
        } catch {
          return;
        }
        if (followButton.disabled) return;
        const targetUserId = followButton.dataset.userId;
        const shouldFollow = followButton.dataset.following !== 'true';
        followButton.disabled = true;
        followButton.classList.add('opacity-70');
        try {
          const response = await submitFollowMutation(targetUserId, shouldFollow);
          const statusText = response?.status || (shouldFollow ? 'followed' : 'unfollowed');
          syncFollowStateForUser(targetUserId, shouldFollow);
          if (state.publicProfile && String(state.publicProfile.id) === String(targetUserId) && response) {
            applyPublicProfileStats(response);
          }
          if (statusText !== 'noop') {
            showToast(shouldFollow ? 'Followed user.' : 'Unfollowed user.', 'success');
          }
        } catch (error) {
          showToast(error.message || 'Unable to update follow state.', 'error');
          applyFollowButtonState(followButton, !shouldFollow);
        } finally {
          followButton.disabled = false;
          followButton.classList.remove('opacity-70');
        }
      });
    }
    const deleteButton = el.querySelector('[data-role="delete-post"]');
    if (deleteButton) {
      deleteButton.addEventListener('click', event => {
        event.preventDefault();
        handleDeletePost(post, el, deleteButton);
      });
    }
    const likeButton = el.querySelector('[data-role="like-button"]');
    if (likeButton) {
      applyLikeButtonState(likeButton, viewerHasLiked, likeCount);
      likeButton.addEventListener('click', event => {
        event.preventDefault();
        togglePostLike(post, likeButton);
      });
    }
    const commentToggle = el.querySelector('[data-role="comment-toggle"]');
    const commentPanel = el.querySelector('[data-role="comment-panel"]');
    if (commentToggle && commentPanel) {
      commentToggle.addEventListener('click', event => {
        event.preventDefault();
        toggleCommentPanel(commentToggle, commentPanel, post);
      });
      const commentForm = commentPanel.querySelector('[data-role="comment-form"]');
      if (commentForm) {
        commentForm.addEventListener('submit', event => {
          event.preventDefault();
          submitCommentForm(post, commentPanel, commentForm);
        });
        const resetButton = commentForm.querySelector('[data-role="comment-reset"]');
        if (resetButton) {
          resetButton.addEventListener('click', () => {
            const textarea = commentForm.querySelector('textarea');
            if (textarea) textarea.value = '';
            resetCommentReply(commentPanel);
          });
        }
      }
      const replyCancel = commentPanel.querySelector('[data-role="comment-reply-cancel"]');
      if (replyCancel) {
        replyCancel.addEventListener('click', () => resetCommentReply(commentPanel));
      }
    }
    const shareButton = el.querySelector('.share-btn');
    if (shareButton) {
      shareButton.addEventListener('click', () => showToast('Link copied! Share coming soon.', 'info'));
    }
    return el;
  }

  // -----------------------------------------------------------------------
  // Auth
  // -----------------------------------------------------------------------

  function initLoginPage() {
    initThemeToggle();
    const form = document.getElementById('login-form');
    const errorBox = document.getElementById('login-error');
    if (!form) return;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const formData = new FormData(form);
      const payload = {
        username: formData.get('username'),
        password: formData.get('password')
      };
      try {
        const response = await apiFetch('/auth/login', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        setAuth({ token: response.access_token, username: payload.username, userId: response.user_id });
        refreshNavAuthState();
        showToast('Welcome back! Redirecting to your feed.', 'success');
        window.location.href = '/';
      } catch (error) {
        if (errorBox) {
          errorBox.textContent = error.message || 'Login failed';
          errorBox.classList.remove('hidden');
        }
      }
    });
  }

  function initRegisterPage() {
    initThemeToggle();
    const form = document.getElementById('register-form');
    const errorBox = document.getElementById('register-error');
    if (!form) return;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const formData = new FormData(form);
      const payload = {
        username: formData.get('username'),
        email: formData.get('email') || null,
        password: formData.get('password')
      };
      try {
        const response = await apiFetch('/auth/register', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        setAuth({ token: response.access_token, username: payload.username, userId: response.user_id });
        refreshNavAuthState();
        showToast('Account created! Redirecting to your feed.', 'success');
        window.location.href = '/';
      } catch (error) {
        if (errorBox) {
          errorBox.textContent = error.message || 'Unable to register.';
          errorBox.classList.remove('hidden');
        }
      }
    });
  }

  // -----------------------------------------------------------------------
  // Profile
  // -----------------------------------------------------------------------

  async function initProfilePage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    await loadProfileData();
    setupProfileForm();
  }

  async function loadProfileData(prefetchedProfile = null) {
    const usernameEl = document.getElementById('profile-username');
    const bioEl = document.getElementById('profile-bio');
    const websiteEl = document.getElementById('profile-website');
    const locationEl = document.getElementById('profile-location');
    const createdEl = document.getElementById('profile-created');
    const postCountEl = document.getElementById('profile-post-count');
    const avatarEl = document.getElementById('profile-avatar');
    const feedList = document.getElementById('profile-feed');
    const feedLoading = document.getElementById('profile-feed-loading');
    const feedEmpty = document.getElementById('profile-feed-empty');

    try {
      const profile = prefetchedProfile || await fetchCurrentUserProfile();
      cacheProfile(profile);
      state.currentProfileAvatar = profile.avatar_url || null;

      try {
        const followStats = await apiFetch(`/follows/stats/${profile.id}`);
        applyPublicProfileStats(followStats);
      } catch (error) {
        console.warn('[profile] failed to load follow stats', error);
        applyPublicProfileStats(null);
      }

      const { username } = profile;
      if (usernameEl) usernameEl.textContent = `@${username}`;
      if (bioEl) bioEl.textContent = profile.bio || 'Add a short bio to introduce yourself.';
      if (locationEl) locationEl.textContent = profile.location || 'Location not set';
      if (websiteEl) {
        websiteEl.textContent = profile.website || 'Website';
        if (profile.website) {
          websiteEl.href = profile.website;
        } else {
          websiteEl.removeAttribute('href');
        }
      }
      if (createdEl) {
        createdEl.textContent = profile.created_at ? new Date(profile.created_at).getFullYear() : '—';
      }

      if (avatarEl) {
        const url = profile.avatar_url || state.currentProfileAvatar;
        applyAvatarToImg(avatarEl, url);
      }

      const form = document.getElementById('profile-form');
      if (form) {
        form.elements['bio'].value = profile.bio || '';
        form.elements['location'].value = profile.location || '';
        form.elements['website'].value = profile.website || '';
      }

      const feed = await apiFetch('/posts/feed');
      const filtered = (feed.items || []).filter(item => item.user_id === profile.id);
      if (postCountEl) postCountEl.textContent = filtered.length;
      if (feedLoading) feedLoading.classList.add('hidden');
      if (filtered.length === 0 && feedEmpty) feedEmpty.classList.remove('hidden');

      if (feedList) {
        feedList.innerHTML = '';
        filtered.forEach(post => {
          const avatarUrl =
            state.avatarCache[profile.id] ||
            resolveAvatarUrl(profile.avatar_url);
          feedList.appendChild(createPostCard(post, username, avatarUrl));
        });
      }
    } catch (error) {
      showToast(error.message || 'Failed to load profile.', 'error');
    }
  }

  function setupProfileForm() {
    const saveButton = document.getElementById('profile-save');
    const form = document.getElementById('profile-form');
    const feedback = document.getElementById('profile-feedback');
    const uploadTrigger = document.getElementById('profile-upload-trigger');
    const uploadInput = document.getElementById('avatar-file');
    const avatarEl = document.getElementById('profile-avatar');

    if (uploadTrigger && uploadInput) {
      uploadTrigger.addEventListener('click', () => uploadInput.click());
      uploadInput.addEventListener('change', () => {
        const file = uploadInput.files && uploadInput.files[0];
        if (!file || !avatarEl) return;
        const reader = new FileReader();
        reader.onload = e => {
          applyAvatarToImg(avatarEl, e.target.result);
        };
        reader.readAsDataURL(file);
      });
    }

    if (!saveButton || !form) return;

    saveButton.addEventListener('click', async event => {
      event.preventDefault();

      try {
        let avatarUrl = null;
        let changedAvatar = false;
        const avatarFileChosen = Boolean(
          uploadInput && uploadInput.files && uploadInput.files[0]
        );
        console.log('[profile] avatar file selected:', avatarFileChosen);

        if (avatarFileChosen) {
          const uploadData = new FormData();
          uploadData.append('file', uploadInput.files[0]);
          const uploadResult = await apiFetch('/media/upload', {
            method: 'POST',
            body: uploadData
          });
          avatarUrl = uploadResult.url || null;
          changedAvatar = !!avatarUrl;
          if (changedAvatar) {
            state.currentProfileAvatar = avatarUrl;
          }
          console.log('[profile] uploaded avatar url:', avatarUrl);
        }

        const payload = {
          location: form.elements['location'].value || null,
          website: form.elements['website'].value || null,
          bio: form.elements['bio'].value || null
        };

        if (changedAvatar) {
          payload.avatar_url = avatarUrl;
        } else {
          const authData = getAuth();
          const cached = authData?.userId
            ? state.avatarCache[String(authData.userId)]
            : null;
          payload.avatar_url = state.currentProfileAvatar || cached || null;
        }

        console.log('[profile] PUT /profiles/me payload:', payload);

        await apiFetch('/profiles/me', {
          method: 'PUT',
          body: JSON.stringify(payload)
        });

        const me = await fetchCurrentUserProfile();

        if (me && me.id) {
          state.avatarCache[String(me.id)] = resolveAvatarUrl(me.avatar_url);
        }

        const avatarNode = document.getElementById('profile-avatar');
        if (avatarNode) {
          applyAvatarToImg(avatarNode, me.avatar_url);
        }

        document
          .querySelectorAll('[data-role="post-avatar"][data-user-id]')
          .forEach(node => {
            if (String(node.dataset.userId) === String(me.id)) {
              applyAvatarToImg(node, me.avatar_url);
            }
          });

        if (uploadInput) {
          uploadInput.value = '';
        }

        showToast('Profile updated successfully.', 'success');
        await loadProfileData(me);
      } catch (error) {
        if (feedback) {
          feedback.textContent =
            error.message || 'Failed to update profile.';
          feedback.classList.remove('hidden');
        }
      }
    });
  }

  // -----------------------------------------------------------------------
  // Messages
  // -----------------------------------------------------------------------

  function initMessageReplyBanner() {
    if (state.messageReplyElements && state.messageReplyElements.initialized) {
      return state.messageReplyElements;
    }
    const banner = document.getElementById('message-reply-banner');
    const usernameNode = document.getElementById('message-reply-username');
    const previewNode = document.getElementById('message-reply-preview');
    const cancelButton = document.getElementById('message-reply-cancel');
    if (cancelButton && cancelButton.dataset.bound !== 'true') {
      cancelButton.dataset.bound = 'true';
      cancelButton.addEventListener('click', event => {
        event.preventDefault();
        clearMessageReplyTarget();
      });
    }
    state.messageReplyElements = {
      banner,
      usernameNode,
      previewNode,
      cancelButton,
      initialized: true,
    };
    return state.messageReplyElements;
  }

  function focusMessageComposer() {
    const textarea = document.querySelector('#message-form textarea[name="message"]');
    if (textarea) {
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    }
  }

  function setMessageReplyTarget(message) {
    if (!message || !message.id) return;
    const elements = initMessageReplyBanner();
    const authId = getAuth().userId;
    let username = message.sender_username;
    if (!username) {
      const isSelf = authId && String(message.sender_id) === String(authId);
      username = isSelf ? 'you' : 'this user';
    }
    const previewSource = message.is_deleted ? 'Message deleted' : (message.content || 'No preview available.');
    state.messageReplyTarget = {
      id: String(message.id),
      username,
      preview: previewSource,
    };
    if (elements.banner) elements.banner.classList.remove('hidden');
    if (elements.usernameNode) elements.usernameNode.textContent = `@${username}`;
    if (elements.previewNode) elements.previewNode.textContent = previewSource.slice(0, 160);
    focusMessageComposer();
  }

  function clearMessageReplyTarget() {
    state.messageReplyTarget = null;
    const elements = state.messageReplyElements;
    if (elements?.banner) elements.banner.classList.add('hidden');
    if (elements?.usernameNode) elements.usernameNode.textContent = '@friend';
    if (elements?.previewNode) elements.previewNode.textContent = '';
  }

  async function initMessagesPage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    window.addEventListener(
      'beforeunload',
      () => {
        disconnectMessageSocket();
      },
      { once: true }
    );
    setupMessageForm();
    await refreshFriendsDirectory();
  }

  async function refreshFriendsDirectory() {
    const container = document.getElementById('friend-list');
    if (container) container.classList.add('opacity-70');
    try {
      const data = await apiFetch('/friends/');
      state.friends = data.friends || [];
      state.incomingRequests = data.incoming_requests || [];
      state.outgoingRequests = data.outgoing_requests || [];
      renderFriendList();
      renderFriendRequests();
      reconcileActiveFriend();
    } catch (error) {
      showToast(error.message || 'Unable to load friends.', 'error');
      renderFriendList(true);
      renderFriendRequests(true);
    } finally {
      if (container) container.classList.remove('opacity-70');
    }
  }

  async function initPublicProfilePage(options = {}) {
    initThemeToggle();
    const username = options.username;
    if (!username) {
      showToast('Missing profile handle.', 'error');
      return;
    }
    await loadPublicProfile(username);
  }

  async function loadPublicProfile(username) {
    const loading = document.getElementById('public-profile-posts-loading');
    const empty = document.getElementById('public-profile-posts-empty');
    const list = document.getElementById('public-profile-posts');
    const countBadge = document.getElementById('public-profile-post-count');
    if (loading) loading.classList.remove('hidden');
    if (empty) empty.classList.add('hidden');
    if (list) list.innerHTML = '';

    try {
      const profile = await apiFetch(`/profiles/${encodeURIComponent(username)}`);
      state.publicProfile = profile;
      applyAvatarToImg(document.getElementById('public-profile-avatar'), profile.avatar_url);
      const usernameNode = document.getElementById('public-profile-username');
      if (usernameNode) usernameNode.textContent = `@${profile.username}`;
      const bioNode = document.getElementById('public-profile-bio');
      if (bioNode) bioNode.textContent = profile.bio || 'No bio provided yet.';
      const locationNode = document.getElementById('public-profile-location');
      if (locationNode) locationNode.textContent = profile.location || 'Unknown';
      const websiteNode = document.getElementById('public-profile-website');
      if (websiteNode) {
        if (profile.website) {
          websiteNode.textContent = profile.website;
          websiteNode.href = profile.website;
        } else {
          websiteNode.textContent = 'Not set';
          websiteNode.removeAttribute('href');
        }
      }

      let followStats = null;
      try {
        followStats = await apiFetch(`/follows/stats/${profile.id}`);
      } catch (error) {
        console.warn('[public-profile] failed to load follow stats', error);
      }
      if (followStats) {
        applyPublicProfileStats(followStats);
      }

      const followButton = resetButtonListeners('public-profile-follow-button');
      const authMeta = getAuth();
      const isSelf = authMeta?.userId && String(authMeta.userId) === String(profile.id);
      if (followButton) {
        if (isSelf) {
          followButton.classList.add('hidden');
        } else {
          followButton.classList.remove('hidden');
          followButton.dataset.userId = profile.id;
          applyFollowButtonState(followButton, Boolean(followStats?.is_following));
          followButton.addEventListener('click', async event => {
            event.preventDefault();
            try {
              ensureAuthenticated();
            } catch {
              return;
            }
            const shouldFollow = followButton.dataset.following !== 'true';
            followButton.disabled = true;
            followButton.classList.add('opacity-70');
            try {
              const response = await submitFollowMutation(profile.id, shouldFollow);
              if (response) {
                applyFollowButtonState(followButton, shouldFollow);
                syncFollowStateForUser(profile.id, shouldFollow);
                applyPublicProfileStats(response);
                showToast(
                  response.status === 'noop'
                    ? 'No changes made.'
                    : shouldFollow
                    ? 'Now following this user.'
                    : 'Unfollowed successfully.',
                  'success'
                );
              }
            } catch (error) {
              showToast(error.message || 'Unable to update follow state.', 'error');
            } finally {
              followButton.disabled = false;
              followButton.classList.remove('opacity-70');
            }
          });
        }
      }

      const postsResponse = await apiFetch(`/posts/by-user/${encodeURIComponent(username)}`);
      const posts = Array.isArray(postsResponse.items) ? postsResponse.items : [];
      if (countBadge) countBadge.textContent = `${posts.length} posts`;
      renderPublicProfilePosts(posts, profile);
      if (empty) empty.classList.toggle('hidden', posts.length !== 0);
    } catch (error) {
      showToast(error.message || 'Unable to load profile.', 'error');
    } finally {
      if (loading) loading.classList.add('hidden');
    }
  }

  function renderPublicProfilePosts(posts, profile) {
    const list = document.getElementById('public-profile-posts');
    if (!list) return;
    list.innerHTML = '';
    if (!posts.length) return;
    const authMeta = getAuth();
    posts.forEach(post => {
      updateAvatarCacheEntry(post.user_id, post.avatar_url || profile.avatar_url);
      const avatarUrl = state.avatarCache[String(post.user_id)] || resolveAvatarUrl(post.avatar_url || profile.avatar_url);
      list.appendChild(createPostCard(post, authMeta, avatarUrl));
    });
  }

  function reconcileActiveFriend() {
    const stillExists = state.friends.some(friend => String(friend.id) === String(state.activeFriendId));
    if (!stillExists) {
      state.activeFriendId = null;
      state.activeFriendMeta = null;
      state.activeThreadLock = null;
      state.activeChatId = null;
      state.activeMessages = [];
      disconnectMessageSocket();
      clearThreadView();
    }
    if (!state.activeFriendId && state.friends.length) {
      selectFriend(state.friends[0].id);
    } else {
      updateFriendSelection();
      updateRecipientHint();
      updateSendAvailability();
    }
  }

  function renderFriendList(showError = false) {
    const container = document.getElementById('friend-list');
    if (!container) return;
    container.innerHTML = '';
    if (showError) {
      container.innerHTML = '<p class="px-2 py-4 text-sm text-rose-300">Unable to load friends.</p>';
      return;
    }
    if (!state.friends.length) {
      container.innerHTML = '<p class="px-2 py-4 text-sm text-slate-400">No friends yet. Send a request to start chatting.</p>';
      return;
    }
    state.friends.forEach(friend => {
      const item = document.createElement('button');
      item.type = 'button';
      item.dataset.friendId = String(friend.id);
      item.className = `flex w-full items-center gap-3 px-3 py-3 text-left transition hover:bg-indigo-500/10 ${
        String(state.activeFriendId) === String(friend.id) ? 'bg-indigo-500/10' : ''
      }`;
      item.innerHTML = `
        <div class="relative h-10 w-10 flex-shrink-0 overflow-hidden rounded-full border border-slate-800/70 bg-slate-900/60">
          <img data-friend-avatar="${friend.id}" alt="${friend.username}" class="h-full w-full object-cover" />
        </div>
        <div class="flex-1">
          <p class="text-sm font-semibold text-slate-100">${friend.username}</p>
          <p class="text-[11px] uppercase tracking-wide text-slate-500">Lock ${shortenLock(friend.lock_code)}</p>
        </div>
      `;
      item.addEventListener('click', () => selectFriend(friend.id));
      container.appendChild(item);
      const avatarNode = item.querySelector(`[data-friend-avatar="${friend.id}"]`);
      applyAvatarToImg(avatarNode, friend.avatar_url);
    });
    updateFriendSelection();
  }

  function renderFriendRequests(showError = false) {
    const badge = document.getElementById('incoming-count');
    if (badge) {
      badge.textContent = showError ? '0' : String(state.incomingRequests.length);
    }
    renderRequestBucket('incoming-requests', state.incomingRequests, showError, true);
    renderRequestBucket('outgoing-requests', state.outgoingRequests, showError, false);
  }

  function renderRequestBucket(domId, items, showError, allowActions) {
    const container = document.getElementById(domId);
    if (!container) return;
    container.innerHTML = '';
    if (showError) {
      container.innerHTML = '<p class="text-xs text-rose-300">Unable to load requests.</p>';
      return;
    }
    if (!items.length) {
      container.innerHTML = `<p class="text-xs text-slate-500">${allowActions ? 'No pending requests.' : 'No outgoing requests.'}</p>`;
      return;
    }
    items.forEach(request => {
      const entry = document.createElement('div');
      entry.className = 'rounded-2xl border border-slate-800/60 bg-slate-950/60 p-3 text-xs text-slate-300 shadow-sm shadow-black/20';
      entry.innerHTML = `
        <p class="font-semibold text-white/90">${allowActions ? 'From' : 'To'} ${truncateId(allowActions ? request.sender_id : request.recipient_id)}</p>
        <p class="text-[11px] text-slate-500">${formatDate(request.created_at)}</p>
      `;
      if (allowActions) {
        const actions = document.createElement('div');
        actions.className = 'mt-2 flex gap-2';
        const accept = document.createElement('button');
        accept.type = 'button';
        accept.className = 'flex-1 rounded-full bg-emerald-500/20 px-3 py-1 text-[11px] font-semibold text-emerald-300 hover:bg-emerald-500/30';
        accept.textContent = 'Accept';
        accept.addEventListener('click', () => handleRequestAction(request.id, 'accept', accept));
        const decline = document.createElement('button');
        decline.type = 'button';
        decline.className = 'flex-1 rounded-full bg-rose-500/10 px-3 py-1 text-[11px] font-semibold text-rose-300 hover:bg-rose-500/20';
        decline.textContent = 'Decline';
        decline.addEventListener('click', () => handleRequestAction(request.id, 'decline', decline));
        actions.appendChild(accept);
        actions.appendChild(decline);
        entry.appendChild(actions);
      }
      container.appendChild(entry);
    });
  }

  function truncateId(value) {
    if (!value) return 'Unknown user';
    const str = String(value);
    return `${str.slice(0, 6)}…${str.slice(-4)}`;
  }

  function shortenLock(lock) {
    if (!lock) return '—';
    return `${lock.slice(0, 4)}…${lock.slice(-4)}`;
  }

  async function handleRequestAction(requestId, action, button) {
    if (button) button.disabled = true;
    try {
      const endpoint = action === 'accept' ? `/friends/requests/${requestId}/accept` : `/friends/requests/${requestId}/decline`;
      await apiFetch(endpoint, { method: 'POST' });
      showToast(action === 'accept' ? 'Friend added!' : 'Request declined.', 'success');
      await refreshFriendsDirectory();
    } catch (error) {
      showToast(error.message || 'Unable to update request.', 'error');
    } finally {
      if (button) button.disabled = false;
    }
  }

  function selectFriend(friendId) {
    if (!friendId) return;
    const sameFriend = String(state.activeFriendId) === String(friendId);
    if (sameFriend && state.threadLoading) {
      return;
    }
    if (!sameFriend) {
      state.activeChatId = null;
      state.activeMessages = [];
      disconnectMessageSocket();
      clearMessageReplyTarget();
    }
    state.activeFriendId = friendId;
    updateFriendSelection();
    updateRecipientHint();
    updateSendAvailability();
    loadDirectThread(friendId);
  }

  function updateFriendSelection() {
    document.querySelectorAll('[data-friend-id]').forEach(node => {
      if (String(node.dataset.friendId) === String(state.activeFriendId)) {
        node.classList.add('bg-indigo-500/10');
      } else {
        node.classList.remove('bg-indigo-500/10');
      }
    });
  }

  function updateRecipientHint() {
    const hint = document.getElementById('message-recipient');
    if (!hint) return;
    if (state.activeFriendMeta) {
      hint.textContent = `Securely messaging @${state.activeFriendMeta.username}`;
      hint.classList.remove('text-slate-500');
      hint.classList.add('text-indigo-300');
    } else {
      hint.textContent = 'Select a friend to unlock messaging.';
      hint.classList.remove('text-indigo-300');
      hint.classList.add('text-slate-500');
    }
  }

  function updateSendAvailability() {
    const button = document.getElementById('message-send');
    if (!button) return;
    const disabled = !state.activeFriendId;
    button.disabled = disabled;
    if (disabled) {
      button.classList.add('cursor-not-allowed', 'opacity-50');
    } else {
      button.classList.remove('cursor-not-allowed', 'opacity-50');
    }
  }

  async function loadDirectThread(friendId) {
    const thread = document.getElementById('message-thread');
    const header = document.getElementById('chat-header');
    if (!thread || !header) return;
    state.threadLoading = true;
    thread.classList.add('opacity-80');
    try {
      const data = await apiFetch(`/messages/direct/${friendId}`);
      state.activeFriendMeta = {
        id: data.friend_id,
        username: data.friend_username,
        avatar_url: data.friend_avatar_url
      };
      state.activeThreadLock = data.lock_code;
      state.activeChatId = data.chat_id || null;
      state.activeMessages = Array.isArray(data.messages) ? [...data.messages] : [];
      updateChatHeader();
      updateRecipientHint();
      renderMessageThread(state.activeMessages);
      connectMessageSocket(state.activeChatId);
    } catch (error) {
      showToast(error.message || 'Unable to load chat.', 'error');
    } finally {
      state.threadLoading = false;
      thread.classList.remove('opacity-80');
    }
  }

  function updateChatHeader() {
    const header = document.getElementById('chat-header');
    if (!header || !state.activeFriendMeta) {
      clearThreadView();
      return;
    }
    const { username, avatar_url } = state.activeFriendMeta;
    const lockSnippet = shortenLock(state.activeThreadLock);
    header.innerHTML = `
      <div class="flex items-center gap-3">
        <div class="h-12 w-12 overflow-hidden rounded-full border border-slate-800/70 bg-slate-900/60">
          <img id="active-friend-avatar" alt="${username}" class="h-full w-full object-cover" />
        </div>
        <div>
          <h2 class="text-base font-semibold text-white">@${username}</h2>
          <p class="text-xs text-slate-400">Secure lock ${lockSnippet}</p>
        </div>
      </div>
      <span id="lock-indicator" class="rounded-full bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">Lock ${lockSnippet}</span>
    `;
    const avatarNode = document.getElementById('active-friend-avatar');
    applyAvatarToImg(avatarNode, avatar_url);
  }

  function clearThreadView() {
    state.activeFriendMeta = null;
    state.activeThreadLock = null;
    state.activeChatId = null;
    state.activeMessages = [];
    disconnectMessageSocket();
    clearMessageReplyTarget();
    const header = document.getElementById('chat-header');
    const thread = document.getElementById('message-thread');
    if (header) {
      header.innerHTML = `
        <div>
          <h2 class="text-base font-semibold text-white">Select a conversation</h2>
          <p class="text-xs text-slate-500">Choose someone from the sidebar to start chatting.</p>
        </div>
        <span id="lock-indicator" class="rounded-full bg-slate-900/80 px-3 py-1 text-xs text-slate-400">Locked</span>
      `;
    }
    if (thread) {
      thread.innerHTML = `
        <div class="rounded-2xl border border-dashed border-slate-800/60 bg-slate-900/40 p-6 text-center text-sm text-slate-500">
          Messages will appear here once you select a chat.
        </div>
      `;
    }
    updateRecipientHint();
    updateSendAvailability();
  }

  function renderMessageThread(messages = state.activeMessages) {
    const thread = document.getElementById('message-thread');
    if (!thread) return;
    thread.innerHTML = '';
    const payload = Array.isArray(messages) ? messages : [];
    if (!payload.length) {
      thread.innerHTML = '<p class="text-center text-sm text-slate-500">No messages yet. Say hello!</p>';
      return;
    }
    const currentUser = getAuth().userId;
    payload.forEach(message => {
      thread.appendChild(createMessageBubble(message, currentUser));
    });
    thread.scrollTop = thread.scrollHeight;
  }

  function setupMessageForm() {
    const form = document.getElementById('message-form');
    const feedback = document.getElementById('message-feedback');
    if (!form) return;
    initMessageReplyBanner();
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const textarea = form.querySelector('textarea[name="message"]');
      const content = String(textarea?.value || '').trim();
      if (feedback) {
        feedback.classList.add('hidden');
        feedback.textContent = '';
      }
      if (!state.activeFriendId) {
        showToast('Select a friend to send a message.', 'warning');
        return;
      }
      if (!content) {
        showToast('Message cannot be empty.', 'warning');
        return;
      }
      try {
        const payload = {
          content,
          friend_id: state.activeFriendId,
          attachments: [],
          reply_to_id: state.messageReplyTarget?.id || null,
        };
        const message = await apiFetch('/messages/send', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        showToast('Message sent!', 'success');
        form.reset();
        clearMessageReplyTarget();
        handleIncomingMessage(message, { skipToast: true });
        focusMessageComposer();
      } catch (error) {
        if (feedback) {
          feedback.textContent = error.message || 'Failed to send message';
          feedback.classList.remove('hidden');
        }
      }
    });
  }

  function renderMessageReplyContext(replyTo, outbound) {
    if (!replyTo) return '';
    const author = replyTo.sender_username ? `@${replyTo.sender_username}` : 'This user';
    const text = replyTo.is_deleted ? 'Message deleted' : (replyTo.content || 'No preview available.');
    const baseClasses = outbound
      ? 'mb-3 rounded-2xl border border-white/20 bg-white/10 px-3 py-2 text-xs text-white/80'
      : 'mb-3 rounded-2xl border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-xs text-slate-200';
    return `
      <div class="${baseClasses}">
        <p class="text-[10px] uppercase tracking-wide opacity-80">${author}</p>
        <p class="mt-1 whitespace-pre-line text-xs opacity-90">${text.slice(0, 160)}</p>
      </div>
    `;
  }

  function createMessageBubble(message, currentUserId) {
    const el = document.createElement('div');
    const outbound = String(message.sender_id) === String(currentUserId);
    el.className = `flex ${outbound ? 'justify-end' : 'justify-start'}`;
    const bubble = document.createElement('div');
    bubble.className = `max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-lg ${
      outbound ? 'bg-indigo-600 text-white' : 'bg-slate-800/90 text-slate-100'
    }`;
    if (message.id) {
      bubble.dataset.messageId = String(message.id);
    }
    const replyMarkup = renderMessageReplyContext(message.reply_to, outbound);
    const bodyMarkup = message.is_deleted
      ? '<p class="italic text-white/80">Message deleted</p>'
      : `<p class="whitespace-pre-line leading-relaxed">${message.content || ''}</p>`;
    const timestamp = `<span class="mt-2 block text-right text-[11px] ${outbound ? 'text-white/80' : 'text-slate-400'}">${formatDate(
      message.created_at
    )}</span>`;
    const actions = !message.is_deleted
      ? `
        <div class="mt-3 flex items-center gap-3 text-[11px] ${outbound ? 'text-white/80' : 'text-slate-300'}">
          <button type="button" data-role="message-reply-trigger" class="font-semibold hover:text-white">
            Reply
          </button>
          ${
            outbound
              ? '<button type="button" data-role="message-delete" class="font-semibold hover:text-white">Delete</button>'
              : ''
          }
        </div>
      `
      : '';
    bubble.innerHTML = `${replyMarkup}${bodyMarkup}${timestamp}${actions}`;
    if (!message.is_deleted) {
      const replyButton = bubble.querySelector('[data-role="message-reply-trigger"]');
      if (replyButton) {
        replyButton.addEventListener('click', () => setMessageReplyTarget(message));
      }
      if (outbound) {
        const deleteButton = bubble.querySelector('[data-role="message-delete"]');
        if (deleteButton) {
          deleteButton.addEventListener('click', () => handleDeleteMessage(message, deleteButton));
        }
      }
    }
    el.appendChild(bubble);
    return el;
  }

  async function handleDeleteMessage(message, trigger) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!message?.id) return;
    const button = trigger || null;
    if (button) {
      button.disabled = true;
      button.classList.add('opacity-70');
    }
    try {
      const response = await apiFetch(`/messages/${encodeURIComponent(message.id)}`, {
        method: 'DELETE',
      });
      handleIncomingMessage(response, { skipToast: true });
      showToast('Message deleted.', 'success');
    } catch (error) {
      showToast(error.message || 'Unable to delete message.', 'error');
    } finally {
      if (button) {
        button.disabled = false;
        button.classList.remove('opacity-70');
      }
    }
  }

  function handleIncomingMessage(message, options = {}) {
    if (!message) return;
    const { skipToast = false } = options;
    const chatId = message.chat_id ? String(message.chat_id) : null;
    if (!chatId) return;
    const activeChatId = state.activeChatId ? String(state.activeChatId) : null;
    if (chatId && activeChatId && chatId === activeChatId) {
      const messageId = message.id ? String(message.id) : null;
      if (messageId) {
        const existingIndex = state.activeMessages.findIndex(item => String(item.id) === messageId);
        if (existingIndex >= 0) {
          state.activeMessages[existingIndex] = message;
        } else {
          state.activeMessages.push(message);
        }
      } else {
        state.activeMessages.push(message);
      }
      renderMessageThread();
      return;
    }
    if (!skipToast) {
      const text = message.is_deleted
        ? 'A message was removed in another conversation.'
        : 'New message received in another conversation.';
      showToast(text, 'info');
    }
  }

  function connectMessageSocket(chatId) {
    if (typeof window === 'undefined' || typeof window.WebSocket === 'undefined') {
      return;
    }
    if (!chatId) {
      disconnectMessageSocket();
      return;
    }
    const { token } = getAuth();
    if (!token) return;
    const controller = state.messageRealtime;
    if (
      controller.socket &&
      controller.chatId === chatId &&
      controller.socket.readyState === WebSocket.OPEN
    ) {
      return;
    }
    disconnectMessageSocket();
    controller.chatId = chatId;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${window.location.host}${MESSAGES_WS_PREFIX}/${encodeURIComponent(chatId)}?token=${encodeURIComponent(token)}`;
    let socket;
    try {
      socket = new WebSocket(url);
    } catch (error) {
      console.warn('[messages/ws] failed to open socket', error);
      scheduleMessageSocketReconnect();
      return;
    }
    controller.socket = socket;
    socket.addEventListener('open', () => {
      controller.retryDelay = 1000;
      startMessagePing();
    });
    socket.addEventListener('message', event => handleMessageSocketMessage(event.data));
    socket.addEventListener('close', () => {
      clearMessagePing();
      controller.socket = null;
      if (state.activeChatId && controller.chatId === state.activeChatId) {
        scheduleMessageSocketReconnect();
      }
    });
    socket.addEventListener('error', error => {
      console.warn('[messages/ws] socket error', error);
      clearMessagePing();
      try {
        socket.close();
      } catch (_) {
        /* noop */
      }
    });
  }

  function disconnectMessageSocket() {
    const controller = state.messageRealtime;
    if (controller.reconnectHandle) {
      clearTimeout(controller.reconnectHandle);
      controller.reconnectHandle = null;
    }
    clearMessagePing();
    if (controller.socket) {
      try {
        controller.socket.close();
      } catch (_) {
        /* noop */
      }
      controller.socket = null;
    }
    controller.chatId = null;
    controller.retryDelay = 1000;
  }

  function scheduleMessageSocketReconnect() {
    const controller = state.messageRealtime;
    if (!controller.chatId || controller.reconnectHandle) return;
    const delay = Math.min(controller.retryDelay, 30000);
    controller.reconnectHandle = window.setTimeout(() => {
      controller.reconnectHandle = null;
      controller.retryDelay = Math.min(controller.retryDelay * 2, 30000);
      connectMessageSocket(controller.chatId);
    }, delay);
  }

  function safeMessageSocketSend(payload) {
    const socket = state.messageRealtime.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    try {
      socket.send(payload);
    } catch (error) {
      console.warn('[messages/ws] failed to send payload', error);
    }
  }

  function startMessagePing(intervalMs = 45000) {
    clearMessagePing();
    safeMessageSocketSend('ping');
    state.messageRealtime.pingHandle = window.setInterval(() => {
      safeMessageSocketSend('ping');
    }, intervalMs);
  }

  function clearMessagePing() {
    const handle = state.messageRealtime.pingHandle;
    if (handle) {
      clearInterval(handle);
      state.messageRealtime.pingHandle = null;
    }
  }

  function handleMessageSocketMessage(raw) {
    let payload;
    try {
      payload = typeof raw === 'string' ? JSON.parse(raw) : JSON.parse(String(raw));
    } catch (error) {
      console.warn('[messages/ws] failed to parse payload', error, raw);
      return;
    }
    const type = String(payload?.type || '').toLowerCase();
    switch (type) {
      case 'message.created':
        handleIncomingMessage(payload.message || {});
        break;
      case 'message.deleted':
        handleIncomingMessage(payload.message || {}, { skipToast: true });
        break;
      case 'ready':
        break;
      case 'pong':
        break;
      default:
        break;
    }
  }

  // -----------------------------------------------------------------------
  // Friend search page
  // -----------------------------------------------------------------------

  async function initFriendSearchPage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    setupFriendSearchForm();
    const input = document.getElementById('friend-search-input');
    if (input) {
      input.focus();
    }
  }

  function setupFriendSearchForm() {
    const form = document.getElementById('friend-search-form');
    const input = document.getElementById('friend-search-input');
    if (!form) return;
    form.addEventListener('submit', event => {
      event.preventDefault();
      const formData = new FormData(form);
      const query = String(formData.get('query') || input?.value || '').trim();
      performFriendSearch(query);
    });
  }

  async function performFriendSearch(query) {
    const feedback = document.getElementById('friend-search-feedback');
    if (feedback) {
      feedback.classList.add('hidden');
      feedback.textContent = '';
    }
    state.friendSearch.query = query;
    const container = document.getElementById('friend-search-results');
    if (!query || query.length < 2) {
      state.friendSearch.results = [];
      if (container) {
        container.innerHTML = '<div class="rounded-2xl border border-dashed border-slate-800/70 bg-slate-950/60 p-6 text-sm text-slate-400">Type at least two characters to search.</div>';
      }
      return;
    }
    if (container) {
      container.innerHTML = '<div class="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-6 text-sm text-slate-300">Searching…</div>';
    }
    try {
      const response = await apiFetch(`/friends/search/users?query=${encodeURIComponent(query)}`);
      state.friendSearch.results = response.results || [];
      renderFriendSearchResults();
    } catch (error) {
      if (feedback) {
        feedback.textContent = error.message || 'Unable to search right now.';
        feedback.classList.remove('hidden');
      }
      if (container) {
        container.innerHTML = '<div class="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-6 text-sm text-rose-200">Search failed. Try again.</div>';
      }
    }
  }

  function renderFriendSearchResults() {
    const container = document.getElementById('friend-search-results');
    if (!container) return;
    const results = state.friendSearch.results || [];
    if (!results.length) {
      container.innerHTML = '<div class="rounded-2xl border border-dashed border-slate-800/70 bg-slate-950/60 p-6 text-sm text-slate-400">No matching usernames yet.</div>';
      return;
    }
    container.innerHTML = '';
    results.forEach(result => {
      container.appendChild(createFriendSearchCard(result));
    });
  }

  function createFriendSearchCard(result) {
    const card = document.createElement('div');
    card.className = 'flex flex-col gap-4 rounded-2xl border border-slate-800/70 bg-slate-950/60 p-5 shadow-md shadow-black/10';
    const statusMeta = friendStatusDescriptor(result.status);
    card.innerHTML = `
      <div class="flex items-center gap-4">
        <div class="h-12 w-12 overflow-hidden rounded-full border border-slate-800/60 bg-slate-900/60">
          <img alt="${result.username}" class="h-full w-full object-cover" data-search-avatar="${result.id}" />
        </div>
        <div class="flex-1">
          <p class="text-sm font-semibold text-white">@${result.username}</p>
          <span class="mt-1 inline-flex items-center rounded-full px-2 py-0.5 text-[11px] ${statusMeta.className}">${statusMeta.label}</span>
        </div>
      </div>
      <p class="text-sm text-slate-400">${result.bio ? result.bio : 'No bio provided yet.'}</p>
    `;
    const avatarNode = card.querySelector(`[data-search-avatar="${result.id}"]`);
    applyAvatarToImg(avatarNode, result.avatar_url);

    const actionRow = document.createElement('div');
    actionRow.className = 'flex flex-wrap items-center gap-3';
    const profileLink = document.createElement('a');
    profileLink.href = `/people/${encodeURIComponent(result.username)}`;
    profileLink.className = 'rounded-full border border-slate-700/70 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-indigo-500 hover:text-indigo-200';
    profileLink.textContent = 'View profile';
    actionRow.appendChild(profileLink);
    card.appendChild(actionRow);

    if (result.status === 'available') {
      const action = document.createElement('button');
      action.type = 'button';
      action.className = 'rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow shadow-indigo-500/30 transition hover:bg-indigo-500 disabled:opacity-50';
      action.textContent = 'Send request';
      action.addEventListener('click', () => sendFriendRequestFromSearch(result.username, action));
      actionRow.appendChild(action);
    } else if (result.status === 'incoming') {
      const note = document.createElement('p');
      note.className = 'text-xs text-amber-200';
      note.textContent = 'This user already sent you a request — respond from Messages.';
      card.appendChild(note);
    } else if (result.status === 'outgoing') {
      const note = document.createElement('p');
      note.className = 'text-xs text-indigo-200';
      note.textContent = 'Request sent. Waiting for them to respond.';
      card.appendChild(note);
    } else if (result.status === 'friend') {
      const note = document.createElement('p');
      note.className = 'text-xs text-emerald-200';
      note.textContent = 'Already connected — chat from the Messages tab.';
      card.appendChild(note);
    }

    return card;
  }

  function friendStatusDescriptor(status) {
    switch (status) {
      case 'friend':
        return { label: 'Friends', className: 'bg-emerald-500/20 text-emerald-200' };
      case 'incoming':
        return { label: 'Request received', className: 'bg-amber-500/20 text-amber-100' };
      case 'outgoing':
        return { label: 'Request sent', className: 'bg-indigo-500/20 text-indigo-100' };
      case 'available':
        return { label: 'Not connected', className: 'bg-slate-800/60 text-slate-200' };
      case 'self':
      default:
        return { label: 'This is you', className: 'bg-slate-800/60 text-slate-300' };
    }
  }

  async function sendFriendRequestFromSearch(username, button) {
    if (!username) return;
    if (button) {
      button.disabled = true;
    }
    try {
      await apiFetch('/friends/requests', {
        method: 'POST',
        body: JSON.stringify({ username })
      });
      showToast(`Friend request sent to ${username}.`, 'success');
      const match = state.friendSearch.results.find(result => result.username === username);
      if (match) {
        match.status = 'outgoing';
      }
      renderFriendSearchResults();
    } catch (error) {
      showToast(error.message || 'Unable to send friend request.', 'error');
    } finally {
      if (button) {
        button.disabled = false;
      }
    }
  }

  // -----------------------------------------------------------------------
  // Notifications
  // -----------------------------------------------------------------------

  async function initNotificationsPage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    await loadNotifications({ autoMarkRead: true });
    const markButton = document.getElementById('notifications-mark');
    if (markButton) {
      markButton.addEventListener('click', async () => {
        try {
          await apiFetch('/notifications/mark-read', { method: 'POST' });
          showToast('Notifications marked as read.', 'success');
          updateNotificationBadge(0);
          await loadNotifications();
        } catch (error) {
          showToast(error.message || 'Unable to update notifications.', 'error');
        }
      });
    }
  }

  async function loadNotifications(options = {}) {
    const { autoMarkRead = false } = options;
    const loading = document.getElementById('notifications-loading');
    const list = document.getElementById('notifications-list');
    const empty = document.getElementById('notifications-empty');
    const count = document.getElementById('notifications-count');
    if (!list) return;
    if (loading) loading.classList.remove('hidden');
    try {
      const data = await apiFetch('/notifications/');
      list.innerHTML = '';
      const items = data.items || [];
      let unread = 0;
      items.forEach(notification => {
        if (!notification.read) unread += 1;
        if (autoMarkRead) {
          notification.read = true;
        }
        list.appendChild(createNotificationItem(notification));
      });
      if (count) {
        const displayUnread = autoMarkRead ? 0 : unread;
        count.textContent = `${displayUnread} unread`;
      }
      if (!autoMarkRead) {
        updateNotificationBadge(unread);
      }
      if (items.length === 0 && empty) empty.classList.remove('hidden');
      else if (empty) empty.classList.add('hidden');
      if (autoMarkRead && unread > 0) {
        try {
          await apiFetch('/notifications/mark-read', { method: 'POST' });
          updateNotificationBadge(0);
          syncNotificationsListReadState();
        } catch (error) {
          console.warn('[notifications] auto mark read failed', error);
        }
      }
    } catch (error) {
      showToast(error.message || 'Unable to load notifications.', 'error');
    } finally {
      if (loading) loading.classList.add('hidden');
    }
  }

  function createNotificationItem(notification) {
    const li = document.createElement('li');
    const isRead = Boolean(notification.read);
    li.className = `card-surface rounded-2xl p-5 shadow-md shadow-black/10 transition hover:shadow-indigo-500/20 ${
      isRead ? 'bg-slate-900/70' : 'bg-indigo-500/10 border border-indigo-400/30'
    }`;
    li.setAttribute('data-notification-item', 'true');
    li.innerHTML = `
      <div class="flex items-center justify-between">
        <span data-notification-status class="rounded-full bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-300">${
          isRead ? 'Read' : 'New'
        }</span>
        <time class="text-xs text-slate-400">${formatDate(notification.created_at)}</time>
      </div>
      <p class="mt-3 text-sm text-slate-200">${notification.content}</p>
    `;
    return li;
  }

  // -----------------------------------------------------------------------
  // Media
  // -----------------------------------------------------------------------

  function initMediaPage() {
    initThemeToggle();
    const fileInput = document.getElementById('media-file');
    const preview = document.getElementById('media-preview');
    const previewImg = document.getElementById('media-preview-img');
    const previewVideo = document.getElementById('media-preview-video');
    const form = document.getElementById('media-upload-form');
    const feedback = document.getElementById('media-upload-feedback');
    renderMediaHistory();

    if (fileInput) {
      fileInput.addEventListener('change', () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file || !preview) return;
        const isVideo = file.type.startsWith('video/');
        preview.classList.remove('hidden');
        if (isVideo) {
          previewVideo.classList.remove('hidden');
          previewImg.classList.add('hidden');
          const url = URL.createObjectURL(file);
          previewVideo.src = url;
        } else {
          previewImg.classList.remove('hidden');
          previewVideo.classList.add('hidden');
          const reader = new FileReader();
          reader.onload = e => {
            previewImg.src = e.target.result;
          };
          reader.readAsDataURL(file);
        }
      });
    }

    if (form) {
      form.addEventListener('submit', async event => {
        event.preventDefault();
        try {
          ensureAuthenticated();
        } catch {
          return;
        }
        const files = fileInput && fileInput.files;
        if (!files || files.length === 0) {
          showToast('Choose a file to upload.', 'warning');
          return;
        }
        const formData = new FormData();
        formData.append('file', files[0]);
        try {
          const result = await apiFetch('/media/upload', {
            method: 'POST',
            body: formData
          });
          showToast('Media uploaded successfully.', 'success');
          state.mediaHistory.unshift({ ...result, created_at: new Date().toISOString() });
          state.mediaHistory = state.mediaHistory.slice(0, 12);
          saveJson(MEDIA_HISTORY_KEY, state.mediaHistory);
          renderMediaHistory();
          form.reset();
          if (preview) preview.classList.add('hidden');
        } catch (error) {
          if (feedback) {
            feedback.textContent = error.message || 'Upload failed';
            feedback.classList.remove('hidden');
          }
        }
      });
    }
  }

  function renderMediaHistory() {
    const container = document.getElementById('media-upload-history');
    if (!container) return;
    if (!state.mediaHistory.length) {
      container.innerHTML = '<p class="text-slate-500">Upload files to view them here.</p>';
      return;
    }
    container.innerHTML = '';
    state.mediaHistory.forEach(item => {
      const el = document.createElement('a');
      el.href = item.url;
      el.target = '_blank';
      el.rel = 'noopener';
      el.className =
        'flex items-center justify-between rounded-2xl border border-slate-800/60 bg-slate-950/60 px-4 py-3 text-sm transition hover:border-indigo-500/60 hover:bg-indigo-500/10 card-surface';
      el.innerHTML = `
        <div class="flex flex-col">
          <span class="font-medium text-white">${item.key || 'Media asset'}</span>
          <span class="text-xs text-slate-400">${formatDate(item.created_at)}</span>
        </div>
        <span class="text-xs text-indigo-300">Open</span>
      `;
      container.appendChild(el);
    });
  }

  // -----------------------------------------------------------------------
  // Settings page
  // -----------------------------------------------------------------------

  function initSettingsPage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    // Placeholder wiring until backend endpoints are ready.
    const emailStatus = document.getElementById('settings-email-status');
    if (emailStatus) {
      emailStatus.textContent = 'Email verification coming soon';
    }
  }

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  window.UI = {
    apiFetch,
    getAuth,
    showToast,
    initFeedPage,
    initLoginPage,
    initRegisterPage,
    initProfilePage,
    initPublicProfilePage,
    initMessagesPage,
    initFriendSearchPage,
    initNotificationsPage,
    initMediaPage,
    initSettingsPage,
  };

  document.addEventListener('DOMContentLoaded', initThemeToggle);
})();
