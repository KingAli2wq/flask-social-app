(() => {
  const TOKEN_KEY = 'socialsphere:token';
  const USERNAME_KEY = 'socialsphere:username';
  const USER_ID_KEY = 'socialsphere:user_id';
  const THEME_KEY = 'socialsphere:theme';
  const CONVERSATIONS_KEY = 'socialsphere:conversations';
  const MEDIA_HISTORY_KEY = 'socialsphere:media-history';
  const FEED_BATCH_SIZE = 5;

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
    activeChatId: null,
    conversations: loadJson(CONVERSATIONS_KEY, {}),
    mediaHistory: loadJson(MEDIA_HISTORY_KEY, []),
    avatarCache: {}
  };

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
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    }
    if (username) {
      localStorage.setItem(USERNAME_KEY, username);
    }
    if (userId) {
      localStorage.setItem(USER_ID_KEY, userId);
    }
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
    const payload = contentType.includes('application/json') ? await response.json().catch(() => ({})) : await response.text();
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
    toast.innerHTML = `<div class="flex items-start gap-3"><span class="text-base">${iconForType(type)}</span><div class="flex-1">${message}</div><button class="text-xs opacity-70 hover:opacity-100">Close</button></div>`;
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
      case 'success':
        return '✅';
      case 'error':
        return '⚠';
      case 'warning':
        return '⚠';
      default:
        return 'ℹ';
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
    } else {
      authBtn.textContent = 'Login';
      authBtn.href = '/login';
      authBtn.classList.remove('border-emerald-500/40', 'text-emerald-300');
      authBtn.onclick = null;
    }
  }

  // Feed ------------------------------------------------------------------
  async function initFeedPage() {
    initThemeToggle();
    await loadFeed();
    setupComposer();
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
      } catch (err) {
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
        if (previewWrapper) {
          previewWrapper.classList.add('hidden');
        }
        await loadFeed(true);
      } catch (error) {
        showToast(error.message || 'Unable to publish post.', 'error');
      }
    });
  }

  async function loadFeed(forceRefresh = false) {
    const loading = document.getElementById('feed-loading');
    const empty = document.getElementById('feed-empty');
    const list = document.getElementById('feed-list');
    const loadMore = document.getElementById('feed-load-more');
    const countBadge = document.getElementById('feed-count');
    if (!list) return;

    if (loading) loading.classList.remove('hidden');
    if (empty) empty.classList.add('hidden');
    if (forceRefresh) {
      state.feedItems = [];
      state.feedCursor = 0;
      list.innerHTML = '';
    }

    try {
      const data = await apiFetch('/posts/feed');
      state.feedItems = Array.isArray(data.items) ? data.items : [];
      state.feedCursor = 0;
      list.innerHTML = '';
      await ensureAvatarCache(state.feedItems);
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
      if (loading) loading.classList.add('hidden');
    }
  }

  async function ensureAvatarCache(posts) {
    const { userId: currentUserId } = getAuth();
    const ids = new Set(posts.map(post => post.user_id).filter(Boolean));
    const fetches = Array.from(ids).map(async userId => {
      if (state.avatarCache[userId]) return;
      try {
        if (currentUserId && String(userId) === String(currentUserId)) {
          const me = await apiFetch('/auth/me');
          state.avatarCache[userId] = me.avatar_url || DEFAULT_AVATAR;
        } else {
          const profile = await apiFetch(`/profiles/${encodeURIComponent(userId)}`);
          state.avatarCache[userId] = profile.avatar_url || DEFAULT_AVATAR;
        }
      } catch (_err) {
        state.avatarCache[userId] = DEFAULT_AVATAR;
      }
    });
    await Promise.all(fetches);
  }

  function renderNextFeedBatch() {
    const list = document.getElementById('feed-list');
    const loadMore = document.getElementById('feed-load-more');
    if (!list) return;
    const { username } = getAuth();
    const slice = state.feedItems.slice(state.feedCursor, state.feedCursor + FEED_BATCH_SIZE);
    slice.forEach(post => {
      const avatarUrl = state.avatarCache[post.user_id] || DEFAULT_AVATAR;
      list.appendChild(createPostCard(post, username, avatarUrl));
    });
    state.feedCursor += slice.length;
    if (loadMore) {
      loadMore.classList.toggle('hidden', state.feedCursor >= state.feedItems.length);
    }
  }

  function createPostCard(post, currentUsername, avatarUrl) {
    const el = document.createElement('article');
    el.className = 'group rounded-3xl bg-slate-900/80 p-6 shadow-lg shadow-black/20 transition hover:-translate-y-1 hover:shadow-indigo-500/20 card-surface';
    const displayName = currentUsername && post.user_id === getAuth().userId ? `@${currentUsername}` : `User ${String(post.user_id).slice(0, 8)}`;
    const timestamp = formatDate(post.created_at);
    const media = post.media_url ? `<img src="${post.media_url}" class="mt-4 w-full rounded-2xl object-cover" alt="Post media">` : '';
    el.innerHTML = `
      <header class="flex items-center gap-4">
        <img src="${avatarUrl || DEFAULT_AVATAR}" class="h-12 w-12 rounded-full object-cover" />
        <div>
          <p class="text-sm font-semibold text-white dark:text-white">${displayName}</p>
          <p class="text-xs text-slate-400">${timestamp}</p>
        </div>
      </header>
      <p class="mt-4 whitespace-pre-line text-sm text-slate-200">${post.caption || ''}</p>
      ${media}
      <footer class="mt-6 flex flex-wrap items-center gap-3 text-sm text-slate-400">
        <button class="like-btn inline-flex items-center gap-2 rounded-full bg-slate-800/90 px-4 py-2 transition hover:bg-indigo-600 hover:text-white"><span>❤</span><span>Like</span></button>
        <button class="comment-btn inline-flex items-center gap-2 rounded-full bg-slate-800/90 px-4 py-2 transition hover:bg-indigo-600 hover:text-white"><span>💬</span><span>Comment</span></button>
        <button class="share-btn inline-flex items-center gap-2 rounded-full bg-slate-800/90 px-4 py-2 transition hover:bg-indigo-600 hover:text-white"><span>↗</span><span>Share</span></button>
      </footer>
    `;
    el.querySelectorAll('.like-btn, .comment-btn, .share-btn').forEach(btn => {
      btn.addEventListener('click', () => showToast('Action coming soon 🎉', 'info'));
    });
    return el;
  }

  // Authentication ---------------------------------------------------------
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

  // Profile ----------------------------------------------------------------
  async function initProfilePage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch (err) {
      return;
    }
    await loadProfileData();
    setupProfileForm();
  }

  async function loadProfileData() {
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
      const profile = await apiFetch('/auth/me');
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
      if (createdEl) createdEl.textContent = profile.created_at ? new Date(profile.created_at).getFullYear() : '—';
      if (avatarEl) {
        avatarEl.src = profile.avatar_url || DEFAULT_AVATAR;
        avatarEl.onerror = () => { avatarEl.src = DEFAULT_AVATAR; };
      }

      state.avatarCache[profile.id] = profile.avatar_url || DEFAULT_AVATAR;

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
          const avatarUrl = state.avatarCache[profile.id] || DEFAULT_AVATAR;
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
    const uploadInput = document.getElementById('profile-media');
    const avatarEl = document.getElementById('profile-avatar');

    if (uploadTrigger && uploadInput) {
      uploadTrigger.addEventListener('click', () => uploadInput.click());
      uploadInput.addEventListener('change', () => {
        const file = uploadInput.files && uploadInput.files[0];
        if (!file || !avatarEl) return;
        const reader = new FileReader();
        reader.onload = e => {
          avatarEl.src = e.target.result;
          showToast('Preview updated. Upload endpoint available via media page.', 'info');
        };
        reader.readAsDataURL(file);
      });
    }

    if (!saveButton || !form) return;
    saveButton.addEventListener('click', async event => {
      event.preventDefault();
      try {
        let avatarUrl = null;
        let keepExistingAvatar = true;

        if (uploadInput && uploadInput.files && uploadInput.files[0]) {
          const uploadData = new FormData();
          uploadData.append('file', uploadInput.files[0]);
          const uploadResult = await apiFetch('/media/upload', {
            method: 'POST',
            body: uploadData
          });
          avatarUrl = uploadResult.url || null;
          keepExistingAvatar = false;
        }

        if (keepExistingAvatar) {
          const meCurrent = await apiFetch('/auth/me');
          avatarUrl = meCurrent.avatar_url || DEFAULT_AVATAR;
        }

        const payload = {
          location: form.elements['location'].value || null,
          website: form.elements['website'].value || null,
          bio: form.elements['bio'].value || null,
          avatar_url: avatarUrl
        };

        await apiFetch('/profiles/me', {
          method: 'PUT',
          body: JSON.stringify(payload)
        });

        const me = await apiFetch('/auth/me');
        state.avatarCache[me.id] = me.avatar_url || DEFAULT_AVATAR;

        showToast('Profile updated successfully.', 'success');
        await loadProfileData();

      } catch (error) {
        if (feedback) {
          feedback.textContent = error.message || 'Failed to update profile.';
          feedback.classList.remove('hidden');
        }
      }
    });
  }

  // Messages ---------------------------------------------------------------
  async function initMessagesPage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch (err) {
      return;
    }
    renderConversationList();
    setupNewChatButton();
    setupMessageForm();
  }

  function renderConversationList() {
    const container = document.getElementById('conversation-list');
    if (!container) return;
    const entries = Object.keys(state.conversations);
    if (entries.length === 0) {
      container.innerHTML = '<p class="px-2 py-4 text-sm text-slate-400">No conversations yet. Start messaging to see them here.</p>';
      return;
    }
    container.innerHTML = '';
    entries.forEach(chatId => {
      const meta = state.conversations[chatId];
      const item = document.createElement('button');
      item.className = `w-full px-4 py-3 text-left transition hover:bg-indigo-500/10 ${state.activeChatId === chatId ? 'bg-indigo-500/10' : ''}`;
      item.innerHTML = `
        <div class="flex items-center justify-between text-sm text-white">
          <span>${chatId}</span>
          <span class="text-xs text-slate-400">${meta.updated || ''}</span>
        </div>
        <p class="mt-1 text-xs text-slate-400">${meta.preview || 'Start chatting'}</p>
      `;
      item.addEventListener('click', () => {
        state.activeChatId = chatId;
        saveJson(CONVERSATIONS_KEY, state.conversations);
        renderConversationList();
        loadChatThread(chatId);
      });
      container.appendChild(item);
    });
  }

  function setupNewChatButton() {
    const button = document.getElementById('new-chat');
    if (!button) return;
    button.addEventListener('click', () => {
      const chatId = prompt('Enter a new chat ID (e.g., team-alpha):');
      if (!chatId) return;
      if (!state.conversations[chatId]) {
        state.conversations[chatId] = { preview: 'New conversation', updated: formatDate(new Date().toISOString()) };
        saveJson(CONVERSATIONS_KEY, state.conversations);
      }
      state.activeChatId = chatId;
      renderConversationList();
      loadChatThread(chatId, true);
    });
  }

  function setupMessageForm() {
    const form = document.getElementById('message-form');
    const feedback = document.getElementById('message-feedback');
    if (!form) return;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const formData = new FormData(form);
      const content = String(formData.get('message') || '').trim();
      const chatId = String(formData.get('chat_id') || '').trim();
      const recipientId = String(formData.get('recipient_id') || '').trim();
      if (!content) {
        showToast('Message cannot be empty.', 'warning');
        return;
      }
      if (!chatId && !recipientId) {
        showToast('Provide either a chat ID or recipient ID.', 'warning');
        return;
      }
      const payload = {
        content,
        chat_id: chatId || null,
        recipient_id: recipientId || null,
        attachments: null
      };
      try {
        const response = await apiFetch('/messages/send', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        showToast('Message sent!', 'success');
        form.reset();
        const activeChat = response.chat_id || chatId;
        if (activeChat) {
          state.conversations[activeChat] = {
            preview: content.slice(0, 64),
            updated: formatDate(response.created_at)
          };
          state.activeChatId = activeChat;
          saveJson(CONVERSATIONS_KEY, state.conversations);
          renderConversationList();
          loadChatThread(activeChat, false, response);
        }
      } catch (error) {
        if (feedback) {
          feedback.textContent = error.message || 'Failed to send message';
          feedback.classList.remove('hidden');
        }
      }
    });
  }

  async function loadChatThread(chatId, clearThread = false, newMessage = null) {
    const header = document.getElementById('chat-header');
    const thread = document.getElementById('message-thread');
    if (!thread || !header) return;
    header.innerHTML = `
      <div>
        <h2 class="text-base font-semibold text-white">Chat: ${chatId}</h2>
        <p class="text-xs text-slate-400">Connected • ${new Date().toLocaleTimeString()}</p>
      </div>
      <span class="rounded-full bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">Online</span>
    `;
    if (clearThread) {
      thread.innerHTML = '';
    }
    try {
      const data = await apiFetch(`/messages/${encodeURIComponent(chatId)}`);
      const currentUser = getAuth().userId;
      thread.innerHTML = '';
      data.messages.forEach(msg => {
        thread.appendChild(createMessageBubble(msg, currentUser));
      });
      if (newMessage) {
        thread.appendChild(createMessageBubble(newMessage, currentUser));
      }
      thread.scrollTop = thread.scrollHeight;
    } catch (error) {
      showToast(error.message || 'Unable to load chat.', 'error');
    }
  }

  function createMessageBubble(message, currentUserId) {
    const el = document.createElement('div');
    const outbound = message.sender_id === currentUserId;
    el.className = `flex ${outbound ? 'justify-end' : 'justify-start'}`;
    el.innerHTML = `
      <div class="max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-lg ${outbound ? 'bg-indigo-600 text-white' : 'bg-slate-800/90 text-slate-100'}">
        <p class="whitespace-pre-line leading-relaxed">${message.content}</p>
        <span class="mt-2 block text-right text-xs text-white/70">${formatDate(message.created_at)}</span>
      </div>
    `;
    return el;
  }

  // Notifications ---------------------------------------------------------
  async function initNotificationsPage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch (err) {
      return;
    }
    await loadNotifications();
    const markButton = document.getElementById('notifications-mark');
    if (markButton) {
      markButton.addEventListener('click', async () => {
        try {
          await apiFetch('/notifications/mark-read', { method: 'POST' });
          showToast('Notifications marked as read.', 'success');
          await loadNotifications();
        } catch (error) {
          showToast(error.message || 'Unable to update notifications.', 'error');
        }
      });
    }
  }

  async function loadNotifications() {
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
        list.appendChild(createNotificationItem(notification));
      });
      if (count) count.textContent = `${unread} unread`;
      if (items.length === 0 && empty) empty.classList.remove('hidden');
      else if (empty) empty.classList.add('hidden');
    } catch (error) {
      showToast(error.message || 'Unable to load notifications.', 'error');
    } finally {
      if (loading) loading.classList.add('hidden');
    }
  }

  function createNotificationItem(notification) {
    const li = document.createElement('li');
    li.className = `card-surface rounded-2xl p-5 shadow-md shadow-black/10 transition hover:shadow-indigo-500/20 ${notification.read ? 'bg-slate-900/70' : 'bg-indigo-500/10 border border-indigo-400/30'}`;
    li.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="rounded-full bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-300">${notification.read ? 'Read' : 'New'}</span>
        <time class="text-xs text-slate-400">${formatDate(notification.created_at)}</time>
      </div>
      <p class="mt-3 text-sm text-slate-200">${notification.content}</p>
    `;
    return li;
  }

  // Media -----------------------------------------------------------------
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
        } catch (err) {
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
          if (preview) {
            preview.classList.add('hidden');
          }
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
      el.className = 'flex items-center justify-between rounded-2xl border border-slate-800/60 bg-slate-950/60 px-4 py-3 text-sm transition hover:border-indigo-500/60 hover:bg-indigo-500/10 card-surface';
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

  // Public API -------------------------------------------------------------
  window.UI = {
    apiFetch,
    getAuth,
    showToast,
    initFeedPage,
    initLoginPage,
    initRegisterPage,
    initProfilePage,
    initMessagesPage,
    initNotificationsPage,
    initMediaPage
  };

  document.addEventListener('DOMContentLoaded', initThemeToggle);
})();
