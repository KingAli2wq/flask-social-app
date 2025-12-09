(() => {
  const TOKEN_KEY = 'socialsphere:token';
  const USERNAME_KEY = 'socialsphere:username';
  const USER_ID_KEY = 'socialsphere:user_id';
  const USER_ROLE_KEY = 'socialsphere:role';
  const THEME_KEY = 'socialsphere:theme';
  const MEDIA_HISTORY_KEY = 'socialsphere:media-history';
  const MEDIA_REEL_CACHE_KEY = 'socialsphere:media-reel-cache';
  const MEDIA_REEL_SCROLL_LOCK_MS = 320;
  const MEDIA_REEL_SKELETON_COUNT = 3;
  const STORY_VIEW_HISTORY_KEY = 'socialsphere:story-views';
  const POST_EDITOR_ROOT_ID = 'post-edit-overlay';
  const FEED_BATCH_SIZE = 5;
  const REALTIME_WS_PATH = '/ws/feed';
  const MESSAGES_WS_PREFIX = '/messages/ws';
  const NOTIFICATION_WS_PATH = '/notifications/ws';
  const POST_MEDIA_VIDEO_EXTENSIONS = new Set(['mp4', 'm4v', 'mov', 'webm', 'ogg', 'ogv', 'mkv']);
  const POST_MEDIA_IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'avif', 'heic', 'bmp']);
  const INVALID_POST_MEDIA_URL_STRINGS = new Set(['', 'null', 'none', 'undefined', 'post media']);
  const MESSAGE_ATTACHMENT_LIMIT = 5;
  const STORY_BACKGROUND_PRESETS = {
    solid: null,
    clear: null,
    sunset: 'linear-gradient(135deg, rgba(249,115,22,0.92), rgba(190,24,93,0.85))',
    ocean: 'linear-gradient(135deg, rgba(56,189,248,0.88), rgba(16,185,129,0.88))',
    aurora: 'linear-gradient(135deg, rgba(129,140,248,0.88), rgba(14,165,233,0.85))',
  };
  const SOCIAL_AI_MODES = {
    default: {
      label: 'Default',
      description: 'Friendly guidance',
      includeContext: true,
    },
    freaky: {
      label: 'Freaky',
      description: 'Playful chaos',
      includeContext: false,
    },
    deep: {
      label: 'Deep understanding',
      description: 'Structured analysis',
      includeContext: true,
    },
  };

  const palette = {
    success: 'bg-emerald-500/90 text-white shadow-emerald-500/30',
    error: 'bg-rose-500/90 text-white shadow-rose-500/30',
    warning: 'bg-amber-400 text-slate-900 shadow-amber-400/30',
    info: 'bg-slate-900/90 text-white shadow-slate-900/30'
  };

  const ROLE_STYLE_MAP = {
    owner: {
      text: 'text-rose-300',
      badge: 'border-rose-500/40 bg-rose-500/10 text-rose-200',
    },
    admin: {
      text: 'text-amber-200',
      badge: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
    },
    user: {
      text: 'text-slate-100',
      badge: 'border-slate-700/60 bg-slate-800/60 text-slate-200',
    },
  };
  const ROLE_BADGE_BASE = 'inline-flex items-center gap-1 rounded-full border font-semibold shadow-sm';
  const ROLE_BADGE_SIZE = {
    default: 'px-3 py-1 text-xs',
    compact: 'px-2 py-0.5 text-[11px]',
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
    groupChats: [],
    activeGroupId: null,
    activeGroupMeta: null,
    activeGroupLock: null,
    conversationMode: null,
    messageAttachments: [],
    friendSearch: {
      query: '',
      results: [],
    },
    threadLoading: false,
    mediaHistory: loadJson(MEDIA_HISTORY_KEY, []),
    stories: {
      items: [],
      loading: false,
      signature: null,
      viewHistory: loadJson(STORY_VIEW_HISTORY_KEY, {}),
      composer: {
        file: null,
        objectUrl: null,
        text: '',
        textColor: '#f8fafc',
        textBackground: '#0f172a',
        backgroundPreset: 'solid',
        textPosition: 'bottom-left',
        fontSize: 22,
      },
      modal: {
        root: null,
        form: null,
        fileInput: null,
        textInput: null,
        textColorInput: null,
        textBackgroundInput: null,
        backgroundButtons: [],
        positionButtons: [],
        fontSlider: null,
        fontLabel: null,
        previewImage: null,
        previewVideo: null,
        previewOverlay: null,
        feedback: null,
        submit: null,
      },
      viewer: {
        root: null,
        image: null,
        video: null,
        overlay: null,
        text: null,
        author: null,
        meta: null,
        prev: null,
        next: null,
        closeButtons: [],
        bucketIndex: 0,
        storyIndex: 0,
      },
    },
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
    postEditor: {
      root: null,
      form: null,
      captionInput: null,
      fileInput: null,
      removeMediaInput: null,
      mediaStatus: null,
      submitButton: null,
      errorNode: null,
      postId: null,
      originalCaption: '',
      escapeHandlerBound: false,
    },
    messageReplyTarget: null,
    messageReplyElements: null,
    groupModals: {
      create: {
        root: null,
        form: null,
        feedback: null,
        avatarInput: null,
        avatarPreview: null,
        membersInput: null,
      },
      invite: {
        root: null,
        form: null,
        feedback: null,
        title: null,
        membersInput: null,
      },
    },
    notifications: {
      unread: 0,
      pollHandle: null,
      socket: null,
      reconnectHandle: null,
      retryDelay: 1000,
      pingHandle: null,
      active: false,
    },
    settingsPage: {
      data: null,
      verificationCooldownHandle: null,
    },
    mediaReel: {
      items: [],
      loading: false,
      signature: null,
      fetchController: null,
      videoObserver: null,
      scrollEnhanced: false,
      brokenAssetIds: new Set(),
      brokenNoticeShown: false,
      fullscreen: {
        active: false,
        overlay: null,
        list: null,
        stage: null,
        counter: null,
        prev: null,
        next: null,
        currentIndex: 0,
        keyHandlerBound: false,
      },
    },
    mediaComments: {},
    moderation: {
      dashboard: null,
      viewerRole: 'user',
      viewerId: null,
      activeDataset: null,
      datasetSearchHandle: null,
      datasets: {
        users: { items: [], total: 0, skip: 0, limit: 25, search: '', filter: null },
        posts: { items: [], total: 0, skip: 0, limit: 25, search: '', filter: null },
        media: { items: [], total: 0, skip: 0, limit: 25, search: '', filter: null },
      },
      panel: {
        root: null,
        title: null,
        label: null,
        searchInput: null,
        pageLabel: null,
        tableContainer: null,
        emptyState: null,
        prevButton: null,
        nextButton: null,
      },
      modal: {
        root: null,
        title: null,
        label: null,
        body: null,
      },
      confirm: {
        root: null,
        title: null,
        message: null,
        accept: null,
        cancel: null,
        resolver: null,
      },
    },
    socialAi: {
      initialized: false,
      open: false,
      mode: 'default',
      sessionByMode: {},
      messagesByMode: {},
      loading: false,
      sending: false,
      error: null,
      documentHandlerBound: false,
      elements: {
        root: null,
        panel: null,
        thread: null,
        empty: null,
        loading: null,
        error: null,
        input: null,
        send: null,
        form: null,
        modeButton: null,
        modeMenu: null,
        modeMenuRoot: null,
      },
    },
  };

  const scrollLock = {
    count: 0,
    bodyOverflow: '',
    htmlOverflow: '',
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

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function getAuth() {
    return {
      token: localStorage.getItem(TOKEN_KEY),
      username: localStorage.getItem(USERNAME_KEY),
      userId: localStorage.getItem(USER_ID_KEY),
      role: localStorage.getItem(USER_ROLE_KEY)
    };
  }

  function setAuth({ token, username, userId, role }) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    if (username) localStorage.setItem(USERNAME_KEY, username);
    if (userId) localStorage.setItem(USER_ID_KEY, userId);
    if (role !== undefined) {
      if (role === null || role === undefined) {
        localStorage.removeItem(USER_ROLE_KEY);
      } else {
        localStorage.setItem(USER_ROLE_KEY, role);
      }
    }
  }

  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem(USER_ID_KEY);
    localStorage.removeItem(USER_ROLE_KEY);
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

  function truncateText(text, limit = 140) {
    if (!text) return '';
    const trimmed = String(text);
    return trimmed.length <= limit ? trimmed : `${trimmed.slice(0, limit - 1)}…`;
  }

  function normalizeRole(role) {
    const normalized = (role || '').toLowerCase();
    return normalized === 'owner' || normalized === 'admin' ? normalized : 'user';
  }

  function formatRoleLabel(role) {
    const normalized = normalizeRole(role);
    return normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }

  function roleAccentClass(role) {
    const normalized = normalizeRole(role);
    return ROLE_STYLE_MAP[normalized]?.text || ROLE_STYLE_MAP.user.text;
  }

  function roleBadgeClasses(role, { compact = false } = {}) {
    const normalized = normalizeRole(role);
    const palette = ROLE_STYLE_MAP[normalized] || ROLE_STYLE_MAP.user;
    const sizeClass = compact ? ROLE_BADGE_SIZE.compact : ROLE_BADGE_SIZE.default;
    return `${ROLE_BADGE_BASE} ${sizeClass} ${palette.badge}`.trim();
  }

  function renderRoleBadgeHtml(role, options = {}) {
    if (!role && !options.includeUser) return '';
    const normalized = normalizeRole(role);
    if (!options.includeUser && normalized === 'user') return '';
    const classes = roleBadgeClasses(normalized, { compact: Boolean(options.compact) });
    return `<span class="${classes}">${formatRoleLabel(normalized)}</span>`;
  }

  function createRoleBadge(role, options = {}) {
    if (!role && !options.includeUser) {
      const span = document.createElement('span');
      span.classList.add('hidden');
      return span;
    }
    const normalized = normalizeRole(role);
    if (!options.includeUser && normalized === 'user') {
      const span = document.createElement('span');
      span.classList.add('hidden');
      return span;
    }
    const badge = document.createElement('span');
    badge.className = roleBadgeClasses(normalized, { compact: Boolean(options.compact) });
    badge.textContent = formatRoleLabel(normalized);
    return badge;
  }

  function decorateLabelWithRole(label, role, options = {}) {
    const textClasses = options.textClasses || '';
    const accent = roleAccentClass(role);
    const badgeHtml = renderRoleBadgeHtml(role, { compact: options.compact !== false });
    const base = `<span class="${[textClasses, accent].filter(Boolean).join(' ').trim()}">${label}</span>`;
    if (!badgeHtml) {
      return base;
    }
    const gapClass = options.inlineGapClass || 'ml-2';
    return `${base}<span class="${gapClass}">${badgeHtml}</span>`;
  }

  function hasModeratorPrivileges(role) {
    const normalized = normalizeRole(role);
    return normalized === 'owner' || normalized === 'admin';
  }

  function updateNavRoleGates(role) {
    const normalized = normalizeRole(role);
    document.querySelectorAll('[data-role-gate]').forEach(link => {
      const requiredRaw = (link.dataset.requiresRole || '').split(',');
      const required = requiredRaw.map(item => item.trim().toLowerCase()).filter(Boolean);
      let allowed = required.length === 0;
      if (!allowed) {
        allowed = required.includes(normalized);
        if (!allowed && normalized === 'owner') {
          allowed = required.includes('admin');
        }
      }
      if (allowed) {
        link.classList.remove('hidden');
        link.removeAttribute('aria-hidden');
      } else {
        link.classList.add('hidden');
        link.setAttribute('aria-hidden', 'true');
      }
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
    initMobileNavToggle();
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
    const { token, username, role } = getAuth();
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
    updateNavRoleGates(role);
  }

  function initMobileNavToggle() {
    const toggle = document.getElementById('mobile-nav-toggle');
    const panel = document.getElementById('mobile-nav-panel');
    if (!toggle || !panel || toggle.dataset.bound === 'true') {
      return;
    }
    toggle.dataset.bound = 'true';
    const label = toggle.querySelector('[data-mobile-nav-label]');
    const openIcon = toggle.querySelector('[data-mobile-nav-icon="open"]');
    const closeIcon = toggle.querySelector('[data-mobile-nav-icon="close"]');

    const setState = next => {
      if (next) {
        panel.classList.remove('hidden');
      } else {
        panel.classList.add('hidden');
      }
      toggle.setAttribute('aria-expanded', next ? 'true' : 'false');
      if (label) {
        label.textContent = next ? 'Close' : 'Menu';
      }
      if (openIcon && closeIcon) {
        openIcon.classList.toggle('hidden', next);
        closeIcon.classList.toggle('hidden', !next);
      }
      toggle.dataset.open = next ? 'true' : 'false';
    };

    setState(false);

    toggle.addEventListener('click', () => {
      const isOpen = toggle.dataset.open === 'true';
      setState(!isOpen);
    });

    panel.querySelectorAll('a[href]').forEach(link => {
      link.addEventListener('click', () => setState(false));
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && toggle.dataset.open === 'true') {
        setState(false);
      }
    });

    document.addEventListener('click', event => {
      if (toggle.dataset.open !== 'true') return;
      if (panel.contains(event.target) || toggle.contains(event.target)) {
        return;
      }
      setState(false);
    });

    window.addEventListener('resize', () => {
      if (window.innerWidth >= 768 && toggle.dataset.open === 'true') {
        setState(false);
      }
    });
  }

  // -----------------------------------------------------------------------
  // Social AI Companion
  // -----------------------------------------------------------------------

  function normalizeSocialAiMode(mode) {
    const raw = (mode || '').toString().toLowerCase().trim();
    if (!raw) return 'default';
    const slug = raw.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    if (!slug) return 'default';
    if (slug === 'deep-understanding') return 'deep';
    return SOCIAL_AI_MODES[slug] ? slug : 'default';
  }

  function getSocialAiModeMeta(mode) {
    const key = normalizeSocialAiMode(mode);
    return { key, meta: SOCIAL_AI_MODES[key] || SOCIAL_AI_MODES.default };
  }

  function isSocialAiStreamingEnabled() {
    return Boolean(typeof window !== 'undefined' && window.ENABLE_LOCAL_LLM_STREAM);
  }

  function getSocialAiAdultConfirmation() {
    const overlayCheckbox = document.getElementById('social-ai-confirm-adult');
    if (overlayCheckbox) {
      return overlayCheckbox.checked;
    }
    const inlineCheckbox = document.getElementById('ai-confirm-adult');
    return inlineCheckbox ? inlineCheckbox.checked : false;
  }

  function createSocialAiTypingIndicator() {
    const indicator = document.createElement('span');
    indicator.className = 'ml-2 inline-flex items-center gap-1 text-xs text-slate-400 opacity-80';
    for (let i = 0; i < 3; i += 1) {
      const dot = document.createElement('span');
      dot.className = 'h-1.5 w-1.5 rounded-full bg-current opacity-70 animate-bounce';
      dot.style.animationDelay = `${i * 120}ms`;
      indicator.appendChild(dot);
    }
    return indicator;
  }

  function createSocialAiMessageNode({ role, content, streaming = false }) {
    const wrapper = document.createElement('div');
    const isAssistant = (role || '').toLowerCase() !== 'user';
    wrapper.className = `rounded-3xl border px-4 py-3 text-sm shadow-sm ${
      isAssistant
        ? 'border-slate-800/70 bg-slate-900/70 text-slate-100'
        : 'border-fuchsia-500/40 bg-fuchsia-500/15 text-white'
    }`;
    if (streaming && isAssistant) {
      wrapper.classList.add('chat-message--streaming');
    }
    const author = document.createElement('p');
    author.className = 'text-xs font-semibold uppercase tracking-wide opacity-70';
    author.textContent = isAssistant ? 'Social AI' : 'You';
    const body = document.createElement('p');
    body.className = 'mt-1 whitespace-pre-wrap text-sm';
    const textNode = document.createElement('span');
    textNode.textContent = content || '';
    body.appendChild(textNode);
    let typingIndicator = null;
    if (streaming && isAssistant) {
      typingIndicator = createSocialAiTypingIndicator();
      body.appendChild(typingIndicator);
    }
    wrapper.appendChild(author);
    wrapper.appendChild(body);
    return { wrapper, textNode, typingIndicator };
  }

  function scrollSocialAiThreadToBottom() {
    const thread = state.socialAi.elements.thread;
    if (thread) {
      thread.scrollTop = thread.scrollHeight;
    }
  }

  function appendSocialAiMessage(message, options = {}) {
    const controller = state.socialAi;
    const thread = controller.elements.thread;
    if (!thread) return null;
    if (controller.elements.empty) {
      controller.elements.empty.classList.add('hidden');
    }
    const node = createSocialAiMessageNode({
      role: message.role,
      content: message.content,
      streaming: Boolean(options.streaming),
    });
    thread.appendChild(node.wrapper);
    scrollSocialAiThreadToBottom();
    return node;
  }

  function createLocalSocialAiMessage(role, content = '') {
    return {
      id: `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      role,
      content,
      created_at: new Date().toISOString(),
    };
  }

  function buildSocialAiHistoryPayload(messages = []) {
    return messages
      .map(message => {
        const role = (message.role || '').toLowerCase() === 'user' ? 'user' : 'assistant';
        const content = (message.content || '').trim();
        if (!content) {
          return null;
        }
        return { role, content };
      })
      .filter(Boolean);
  }

  async function streamLocalAiReply({ message, mode, history = [], confirmedAdult = false, onChunk }) {
    const headers = new Headers({
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    });
    const auth = getAuth();
    if (auth.token) {
      headers.set('Authorization', `Bearer ${auth.token}`);
    }
    const payload = {
      message,
      mode,
      history,
      confirmed_adult: Boolean(confirmedAdult),
    };
    let response;
    try {
      response = await fetch('/ai/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });
    } catch (error) {
      throw new Error(error?.message || 'AI stream failed');
    }
    if (!response.ok) {
      throw new Error('AI stream failed');
    }
    if (!response.body || typeof response.body.getReader !== 'function') {
      throw new Error('Streaming is not supported in this browser.');
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let accumulated = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (!value) continue;
      const chunk = decoder.decode(value, { stream: true });
      if (!chunk) continue;
      accumulated += chunk;
      if (typeof onChunk === 'function') {
        onChunk(chunk, accumulated);
      }
    }
    return accumulated;
  }

  function initSocialAi() {
    const controller = state.socialAi;
    controller.elements.root = document.getElementById('social-ai-overlay');
    if (!controller.elements.root) {
      return;
    }
    controller.elements.panel = controller.elements.root.querySelector('[data-social-ai-panel]');
    controller.elements.thread = document.getElementById('social-ai-thread');
    controller.elements.empty = document.getElementById('social-ai-empty');
    controller.elements.loading = document.getElementById('social-ai-loading');
    controller.elements.error = document.getElementById('social-ai-error');
    controller.elements.input = document.getElementById('social-ai-input');
    controller.elements.send = document.getElementById('social-ai-send');
    controller.elements.form = document.getElementById('social-ai-form');
    controller.elements.modeButton = document.getElementById('social-ai-mode-button');
    controller.elements.modeMenu = document.getElementById('social-ai-mode-menu');
    controller.elements.modeMenuRoot = controller.elements.root.querySelector('[data-social-ai-mode-menu-root]');

    if (!controller.initialized) {
      controller.initialized = true;
      if (controller.elements.form) {
        controller.elements.form.addEventListener('submit', handleSocialAiSubmit);
      }
      if (controller.elements.root) {
        controller.elements.root.addEventListener('click', event => {
          if (event.target === controller.elements.root) {
            closeSocialAi();
          }
        });
      }
      document.querySelectorAll('[data-social-ai-close]').forEach(button => {
        if (button.dataset.bound === 'true') return;
        button.dataset.bound = 'true';
        button.addEventListener('click', event => {
          event.preventDefault();
          closeSocialAi();
        });
      });
      if (controller.elements.modeButton) {
        controller.elements.modeButton.addEventListener('click', event => {
          event.preventDefault();
          toggleSocialAiModeMenu();
        });
      }
      document.querySelectorAll('[data-social-ai-mode-option]').forEach(option => {
        if (option.dataset.bound === 'true') return;
        option.dataset.bound = 'true';
        option.addEventListener('click', event => {
          event.preventDefault();
          const mode = option.dataset.socialAiModeOption;
          setSocialAiMode(mode);
        });
      });
    }

    if (!controller.documentHandlerBound) {
      document.addEventListener('click', handleSocialAiDocumentClick);
      controller.documentHandlerBound = true;
    }

    bindSocialAiTriggers();
  }

  function bindSocialAiTriggers() {
    document.querySelectorAll('[data-social-ai-open]').forEach(trigger => {
      if (trigger.dataset.socialAiBound === 'true') return;
      trigger.dataset.socialAiBound = 'true';
      trigger.addEventListener('click', event => {
        event.preventDefault();
        openSocialAi(trigger.dataset.socialAiMode || null);
      });
    });
  }

  function handleSocialAiDocumentClick(event) {
    const controller = state.socialAi;
    if (!controller.open) return;
    const menuRoot = controller.elements.modeMenuRoot;
    if (!menuRoot) return;
    if (controller.elements.modeMenu && !controller.elements.modeMenu.classList.contains('hidden')) {
      if (!menuRoot.contains(event.target)) {
        toggleSocialAiModeMenu(false);
      }
    }
  }

  function openSocialAi(preferredMode = null) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!state.socialAi.initialized) {
      initSocialAi();
    }
    const controller = state.socialAi;
    const root = controller.elements.root;
    if (!root) return;
    controller.mode = normalizeSocialAiMode(preferredMode || controller.mode);
    controller.open = true;
    updateSocialAiModeLabel();
    root.classList.remove('hidden');
    lockBodyScroll();
    toggleSocialAiModeMenu(false);
    showSocialAiError('');
    if (controller.elements.input) {
      controller.elements.input.focus();
      const value = controller.elements.input.value;
      controller.elements.input.setSelectionRange(value.length, value.length);
    }
    const cache = controller.messagesByMode[controller.mode];
    if (Array.isArray(cache) && cache.length) {
      renderSocialAiMessages();
    } else if (Array.isArray(cache) && cache.length === 0) {
      renderSocialAiMessages();
    } else {
      controller.messagesByMode[controller.mode] = [];
      hydrateSocialAiHistory(controller.mode);
    }
  }

  function closeSocialAi() {
    const controller = state.socialAi;
    const root = controller.elements.root;
    if (!root || root.classList.contains('hidden')) return;
    controller.open = false;
    toggleSocialAiModeMenu(false);
    root.classList.add('hidden');
    unlockBodyScroll();
  }

  function toggleSocialAiModeMenu(force) {
    const controller = state.socialAi;
    const menu = controller.elements.modeMenu;
    if (!menu) return;
    const shouldOpen = typeof force === 'boolean' ? force : menu.classList.contains('hidden');
    menu.classList.toggle('hidden', !shouldOpen);
  }

  function updateSocialAiModeLabel() {
    const controller = state.socialAi;
    const labelNode = controller.elements.modeButton?.querySelector('[data-social-ai-mode-label]') || controller.elements.modeButton;
    if (!labelNode) return;
    const { meta } = getSocialAiModeMeta(controller.mode);
    if (labelNode.dataset && labelNode.dataset.socialAiModeLabel !== undefined) {
      labelNode.dataset.socialAiModeLabel = meta.label;
    }
    if (labelNode.textContent !== undefined) {
      labelNode.textContent = meta.label;
    }
  }

  function setSocialAiMode(mode) {
    const controller = state.socialAi;
    const normalized = normalizeSocialAiMode(mode);
    if (controller.mode === normalized) {
      toggleSocialAiModeMenu(false);
      return;
    }
    controller.mode = normalized;
    controller.error = null;
    updateSocialAiModeLabel();
    toggleSocialAiModeMenu(false);
    const cached = controller.messagesByMode[normalized];
    if (Array.isArray(cached)) {
      renderSocialAiMessages();
    } else {
      controller.messagesByMode[normalized] = [];
      hydrateSocialAiHistory(normalized, { forceRefresh: true });
    }
  }

  function setSocialAiLoading(isLoading) {
    const controller = state.socialAi;
    controller.loading = Boolean(isLoading);
    if (controller.elements.loading) {
      controller.elements.loading.classList.toggle('hidden', !controller.loading);
    }
  }

  function showSocialAiError(message) {
    const controller = state.socialAi;
    controller.error = message || '';
    const node = controller.elements.error;
    if (!node) return;
    if (controller.error) {
      node.textContent = controller.error;
      node.classList.remove('hidden');
    } else {
      node.textContent = '';
      node.classList.add('hidden');
    }
  }

  async function hydrateSocialAiHistory(mode, options = {}) {
    const controller = state.socialAi;
    if (!controller.elements.thread) return;
    const normalized = normalizeSocialAiMode(mode);
    const forceRefresh = Boolean(options.forceRefresh);
    setSocialAiLoading(true);
    showSocialAiError('');
    try {
      let sessionId = controller.sessionByMode[normalized] || null;
      if (!sessionId || forceRefresh) {
        const sessions = await apiFetch('/chatbot/sessions');
        if (Array.isArray(sessions)) {
          const match = sessions.find(item => normalizeSocialAiMode(item.persona) === normalized);
          sessionId = match ? match.session_id : null;
          controller.sessionByMode[normalized] = sessionId || null;
        }
      }
      if (sessionId) {
        const transcript = await apiFetch(`/chatbot/sessions/${encodeURIComponent(sessionId)}`);
        controller.sessionByMode[normalized] = transcript.session_id || sessionId;
        controller.messagesByMode[normalized] = Array.isArray(transcript.messages) ? transcript.messages : [];
      } else {
        controller.messagesByMode[normalized] = [];
      }
      renderSocialAiMessages();
    } catch (error) {
      showSocialAiError(error.message || 'Unable to load Social AI.');
    } finally {
      setSocialAiLoading(false);
    }
  }

  function renderSocialAiMessages() {
    const controller = state.socialAi;
    const thread = controller.elements.thread;
    if (!thread) return;
    const messages = controller.messagesByMode[controller.mode] || [];
    thread.innerHTML = '';
    const emptyState = controller.elements.empty;
    if (!messages.length) {
      if (emptyState) emptyState.classList.remove('hidden');
      return;
    }
    if (emptyState) emptyState.classList.add('hidden');
    messages.forEach(message => {
      const node = createSocialAiMessageNode({ role: message.role, content: message.content });
      thread.appendChild(node.wrapper);
    });
    scrollSocialAiThreadToBottom();
  }

  function handleSocialAiSubmit(event) {
    event.preventDefault();
    const controller = state.socialAi;
    if (controller.sending) return;
    const input = controller.elements.input;
    if (!input) return;
    const value = input.value.trim();
    if (!value) {
      showToast('Enter a prompt for Social AI.', 'warning');
      return;
    }
    sendSocialAiPrompt(value);
  }

  async function sendSocialAiPrompt(text) {
    const controller = state.socialAi;
    const meta = getSocialAiModeMeta(controller.mode);
    const sendButton = controller.elements.send;
    controller.sending = true;
    if (sendButton) {
      sendButton.disabled = true;
      sendButton.textContent = 'Sending…';
    }
    showSocialAiError('');
    if (controller.elements.input) {
      controller.elements.input.value = '';
    }
    if (!Array.isArray(controller.messagesByMode[meta.key])) {
      controller.messagesByMode[meta.key] = [];
    }
    const useStreaming = isSocialAiStreamingEnabled();
    if (!useStreaming) {
      const userMessage = createLocalSocialAiMessage('user', text);
      controller.messagesByMode[meta.key].push(userMessage);
      appendSocialAiMessage(userMessage);
    }
    try {
      if (useStreaming) {
        await sendSocialAiPromptStreaming(text, meta);
      } else {
        await sendSocialAiPromptViaApi(text, meta);
      }
    } catch (error) {
      showSocialAiError(error.message || 'Social AI is unavailable right now.');
    } finally {
      controller.sending = false;
      if (sendButton) {
        sendButton.disabled = false;
        sendButton.textContent = 'Send';
      }
    }
  }

  async function sendSocialAiPromptViaApi(text, meta) {
    const controller = state.socialAi;
    const payload = {
      message: text,
      session_id: controller.sessionByMode[meta.key] || null,
      persona: meta.key,
      include_public_context: meta.meta.includeContext !== false,
    };
    const response = await apiFetch('/chatbot/messages', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    controller.sessionByMode[meta.key] = response.session_id || controller.sessionByMode[meta.key] || null;
    controller.messagesByMode[meta.key] = Array.isArray(response.messages) ? response.messages : [];
    renderSocialAiMessages();
  }

  async function sendSocialAiPromptStreaming(text, meta) {
    const controller = state.socialAi;
    if (!Array.isArray(controller.messagesByMode[meta.key])) {
      controller.messagesByMode[meta.key] = [];
    }
    const thread = controller.elements.thread;
    if (!thread) {
      // Fallback to the legacy pathway if the DOM is not ready.
      await sendSocialAiPromptViaApi(text, meta);
      return;
    }
    const messages = controller.messagesByMode[meta.key];
    const historyPayload = buildSocialAiHistoryPayload(messages);
    const userMessage = createLocalSocialAiMessage('user', text);
    messages.push(userMessage);
    appendSocialAiMessage(userMessage);

    const assistantMessage = {
      ...createLocalSocialAiMessage('assistant', ''),
      streaming: true,
    };
    messages.push(assistantMessage);
    const assistantNode = appendSocialAiMessage(assistantMessage, { streaming: true }) || {};

    const handleChunk = chunk => {
      assistantMessage.content += chunk;
      if (assistantNode.textNode) {
        assistantNode.textNode.textContent = assistantMessage.content;
      }
      scrollSocialAiThreadToBottom();
    };

    try {
      const finalText = await streamLocalAiReply({
        message: text,
        mode: meta.key,
        history: historyPayload,
        confirmedAdult: getSocialAiAdultConfirmation(),
        onChunk: handleChunk,
      });
      assistantMessage.content = finalText;
      assistantMessage.streaming = false;
      if (assistantNode.textNode) {
        assistantNode.textNode.textContent = finalText;
      }
    } catch (error) {
      const fallback = error?.message || 'The AI request failed, please try again.';
      assistantMessage.content = fallback;
      assistantMessage.streaming = false;
      if (assistantNode.textNode) {
        assistantNode.textNode.textContent = fallback;
        assistantNode.textNode.classList.add('text-rose-200');
      }
      if (assistantNode.wrapper) {
        assistantNode.wrapper.classList.add('chat-message--error', 'border-rose-500/60');
      }
      throw error;
    } finally {
      if (assistantNode.typingIndicator && assistantNode.typingIndicator.parentNode) {
        assistantNode.typingIndicator.parentNode.removeChild(assistantNode.typingIndicator);
      }
      if (assistantNode.wrapper) {
        assistantNode.wrapper.classList.remove('chat-message--streaming');
      }
      scrollSocialAiThreadToBottom();
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
    const badges = document.querySelectorAll('[data-role="nav-notifications-indicator"]');
    if (!badges.length) return;
    badges.forEach(badge => {
      if (value <= 0) {
        badge.textContent = '';
        badge.classList.add('hidden');
      } else {
        badge.textContent = value > 99 ? '99+' : String(value);
        badge.classList.remove('hidden');
      }
    });
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
      setAuth({ username: me.username, userId: me.id, role: me.role || null });
      return me;
    }

    const profile = await apiFetch(`/profiles/by-id/${encodeURIComponent(userId)}`);
    console.log('[profiles/by-id] avatar_url:', profile.avatar_url || '(none)');
    cacheProfile(profile);
    state.currentProfileAvatar = profile.avatar_url || null;
    updateCurrentUserAvatarImages(profile.avatar_url);
    setAuth({ role: profile.role || null });
    return profile;
  }

  // -----------------------------------------------------------------------
  // Feed
  // -----------------------------------------------------------------------

  async function initFeedPage() {
    initThemeToggle();
    setupStoriesUI();
    await Promise.allSettled([loadStories(), loadFeed()]);
    setupComposer();
    initRealtimeUpdates();
    startFeedAutoRefresh(15000);
  }

  function setupStoriesUI() {
    setupStoryComposer();
    setupStoryViewer();
  }

  function cacheStoryModalElements() {
    const modal = state.stories.modal;
    if (!modal.root) {
      modal.root = document.getElementById('story-modal');
      modal.form = document.getElementById('story-form');
      modal.fileInput = document.getElementById('story-file-input');
      modal.textInput = document.getElementById('story-text-input');
      modal.textColorInput = document.getElementById('story-text-color');
      modal.textBackgroundInput = document.getElementById('story-text-background');
      modal.fontSlider = document.getElementById('story-font-size');
      modal.fontLabel = document.getElementById('story-font-size-label');
      modal.previewImage = document.getElementById('story-preview-image');
      modal.previewVideo = document.getElementById('story-preview-video');
      modal.previewOverlay = document.getElementById('story-preview-overlay');
      modal.feedback = document.getElementById('story-modal-feedback');
      modal.submit = document.getElementById('story-form-submit');
    }
    modal.backgroundButtons = Array.from(document.querySelectorAll('[data-story-bg]'));
    modal.positionButtons = Array.from(document.querySelectorAll('[data-story-position]'));
  }

  function cacheStoryViewerElements() {
    const viewer = state.stories.viewer;
    if (!viewer.root) {
      viewer.root = document.getElementById('story-viewer');
      viewer.image = document.getElementById('story-viewer-image');
      viewer.video = document.getElementById('story-viewer-video');
      viewer.text = document.getElementById('story-viewer-text');
      viewer.author = document.getElementById('story-viewer-author');
      viewer.meta = document.getElementById('story-viewer-meta');
      viewer.prev = document.getElementById('story-viewer-prev');
      viewer.next = document.getElementById('story-viewer-next');
    }
    viewer.closeButtons = Array.from(document.querySelectorAll('[data-story-viewer-close]'));
  }

  function setupStoryComposer() {
    cacheStoryModalElements();
    const modal = state.stories.modal;
    const triggers = [document.getElementById('story-create-button'), document.getElementById('story-self-pill')];
    triggers.forEach(trigger => {
      if (!trigger || trigger.dataset.bound === 'true') return;
      trigger.dataset.bound = 'true';
      trigger.addEventListener('click', () => openStoryModal());
    });

    if (!modal.root) return;

    if (modal.root.dataset.bound !== 'true') {
      modal.root.dataset.bound = 'true';
      modal.root.addEventListener('click', event => {
        if (event.target === modal.root) {
          closeStoryModal(true);
        }
      });
    }

    modal.root.querySelectorAll('[data-story-close]').forEach(button => {
      if (button.dataset.bound === 'true') return;
      button.dataset.bound = 'true';
      button.addEventListener('click', () => closeStoryModal(true));
    });

    if (modal.fileInput && modal.fileInput.dataset.bound !== 'true') {
      modal.fileInput.dataset.bound = 'true';
      modal.fileInput.addEventListener('change', () => {
        const file = modal.fileInput.files && modal.fileInput.files[0];
        handleStoryFileSelection(file || null);
      });
    }

    if (modal.textInput && modal.textInput.dataset.bound !== 'true') {
      modal.textInput.dataset.bound = 'true';
      modal.textInput.addEventListener('input', event => handleStoryTextInput(event.target.value));
    }

    if (modal.textColorInput && modal.textColorInput.dataset.bound !== 'true') {
      modal.textColorInput.dataset.bound = 'true';
      modal.textColorInput.addEventListener('input', event => handleStoryTextColorChange(event.target.value));
    }

    if (modal.textBackgroundInput && modal.textBackgroundInput.dataset.bound !== 'true') {
      modal.textBackgroundInput.dataset.bound = 'true';
      modal.textBackgroundInput.addEventListener('input', event => handleStoryBackgroundColorChange(event.target.value));
    }

    (modal.backgroundButtons || []).forEach(button => {
      if (button.dataset.bound === 'true') return;
      button.dataset.bound = 'true';
      button.addEventListener('click', () => handleStoryBackgroundPresetChange(button.dataset.storyBg || 'solid'));
    });

    (modal.positionButtons || []).forEach(button => {
      if (button.dataset.bound === 'true') return;
      button.dataset.bound = 'true';
      button.addEventListener('click', () => handleStoryPositionChange(button.dataset.storyPosition || 'bottom-left'));
    });

    if (modal.fontSlider && modal.fontSlider.dataset.bound !== 'true') {
      modal.fontSlider.dataset.bound = 'true';
      modal.fontSlider.addEventListener('input', event => handleStoryFontSizeChange(event.target.value));
    }

    if (modal.form && modal.form.dataset.bound !== 'true') {
      modal.form.dataset.bound = 'true';
      modal.form.addEventListener('submit', handleStorySubmit);
    }

    resetStoryComposer();
  }

  function setupStoryViewer() {
    cacheStoryViewerElements();
    const viewer = state.stories.viewer;
    if (!viewer.root) return;

    if (viewer.root.dataset.bound !== 'true') {
      viewer.root.dataset.bound = 'true';
      viewer.root.addEventListener('click', event => {
        if (event.target === viewer.root) {
          closeStoryViewer();
        }
      });
    }

    (viewer.closeButtons || []).forEach(button => {
      if (button.dataset.bound === 'true') return;
      button.dataset.bound = 'true';
      button.addEventListener('click', () => closeStoryViewer());
    });

    if (viewer.prev && viewer.prev.dataset.bound !== 'true') {
      viewer.prev.dataset.bound = 'true';
      viewer.prev.addEventListener('click', () => stepStory(-1));
    }

    if (viewer.next && viewer.next.dataset.bound !== 'true') {
      viewer.next.dataset.bound = 'true';
      viewer.next.addEventListener('click', () => stepStory(1));
    }
  }

  function openStoryModal() {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    cacheStoryModalElements();
    const modal = state.stories.modal.root;
    if (!modal) return;
    resetStoryComposer();
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    lockBodyScroll();
  }

  function closeStoryModal(reset = false) {
    const modal = state.stories.modal.root;
    if (!modal) return;
    const wasVisible = !modal.classList.contains('hidden');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    if (wasVisible) {
      unlockBodyScroll();
    }
    if (reset) {
      resetStoryComposer();
    }
  }

  function resetStoryComposer() {
    const composer = state.stories.composer;
    if (composer.objectUrl) {
      URL.revokeObjectURL(composer.objectUrl);
      composer.objectUrl = null;
    }
    composer.file = null;
    composer.text = '';
    composer.textColor = '#f8fafc';
    composer.textBackground = '#0f172a';
    composer.backgroundPreset = 'solid';
    composer.textPosition = 'bottom-left';
    composer.fontSize = 22;

    const modal = state.stories.modal;
    if (modal.form) {
      modal.form.reset();
    }
    if (modal.textColorInput) modal.textColorInput.value = composer.textColor;
    if (modal.textBackgroundInput) modal.textBackgroundInput.value = composer.textBackground;
    if (modal.fontSlider) modal.fontSlider.value = String(composer.fontSize);
    if (modal.fontLabel) modal.fontLabel.textContent = `${composer.fontSize}px`;
    if (modal.feedback) {
      modal.feedback.textContent = '';
      modal.feedback.classList.add('hidden');
    }
    if (modal.previewImage) {
      modal.previewImage.src = '';
      modal.previewImage.classList.add('hidden');
    }
    if (modal.previewVideo) {
      modal.previewVideo.pause?.();
      modal.previewVideo.src = '';
      modal.previewVideo.classList.add('hidden');
    }
    (modal.backgroundButtons || []).forEach(button => {
      const isActive = (button.dataset.storyBg || 'solid') === composer.backgroundPreset;
      button.classList.toggle('border-indigo-400', isActive);
      button.classList.toggle('bg-indigo-500/10', isActive);
      button.classList.toggle('text-white', isActive);
    });
    modal.positionButtons.forEach(button => {
      const isActive = (button.dataset.storyPosition || 'bottom-left') === composer.textPosition;
      button.classList.toggle('border-indigo-400', isActive);
      button.classList.toggle('text-white', isActive);
    });
    updateStoryPreview();
  }

  function handleStoryFileSelection(file) {
    const composer = state.stories.composer;
    const modal = state.stories.modal;
    if (composer.objectUrl) {
      URL.revokeObjectURL(composer.objectUrl);
      composer.objectUrl = null;
    }
    composer.file = null;
    if (!file) {
      if (modal.previewVideo) {
        modal.previewVideo.pause?.();
        modal.previewVideo.src = '';
        modal.previewVideo.classList.add('hidden');
      }
      if (modal.previewImage) {
        modal.previewImage.src = '';
        modal.previewImage.classList.add('hidden');
      }
      return;
    }

    composer.file = file;
    composer.objectUrl = URL.createObjectURL(file);
    const isVideo = (file.type || '').toLowerCase().startsWith('video/');
    if (isVideo) {
      if (modal.previewVideo) {
        modal.previewVideo.src = composer.objectUrl;
        modal.previewVideo.classList.remove('hidden');
        modal.previewVideo.play?.().catch(() => {
          /* ignore */
        });
      }
      if (modal.previewImage) {
        modal.previewImage.classList.add('hidden');
      }
    } else if (modal.previewImage) {
      modal.previewImage.src = composer.objectUrl;
      modal.previewImage.classList.remove('hidden');
      if (modal.previewVideo) {
        modal.previewVideo.pause?.();
        modal.previewVideo.src = '';
        modal.previewVideo.classList.add('hidden');
      }
    }
  }

  function handleStoryTextInput(value) {
    state.stories.composer.text = value || '';
    updateStoryPreview();
  }

  function handleStoryTextColorChange(value) {
    state.stories.composer.textColor = value || '#f8fafc';
    updateStoryPreview();
  }

  function handleStoryBackgroundColorChange(value) {
    state.stories.composer.backgroundPreset = 'solid';
    state.stories.composer.textBackground = value || '#0f172a';
    highlightStoryBackgroundButtons();
    updateStoryPreview();
  }

  function handleStoryBackgroundPresetChange(preset) {
    const key = preset || 'solid';
    state.stories.composer.backgroundPreset = key;
    if (key === 'solid') {
      const modal = state.stories.modal;
      state.stories.composer.textBackground = modal.textBackgroundInput?.value || '#0f172a';
    } else if (key === 'clear') {
      state.stories.composer.textBackground = null;
    } else {
      state.stories.composer.textBackground = STORY_BACKGROUND_PRESETS[key] || state.stories.composer.textBackground;
    }
    highlightStoryBackgroundButtons();
    updateStoryPreview();
  }

  function highlightStoryBackgroundButtons() {
    const modal = state.stories.modal;
    (modal.backgroundButtons || []).forEach(button => {
      const isActive = (button.dataset.storyBg || 'solid') === state.stories.composer.backgroundPreset;
      button.classList.toggle('border-indigo-400', isActive);
      button.classList.toggle('bg-indigo-500/10', isActive);
      button.classList.toggle('text-white', isActive);
    });
  }

  function handleStoryPositionChange(position) {
    state.stories.composer.textPosition = position || 'bottom-left';
    const modal = state.stories.modal;
    modal.positionButtons.forEach(button => {
      const isActive = (button.dataset.storyPosition || 'bottom-left') === state.stories.composer.textPosition;
      button.classList.toggle('border-indigo-400', isActive);
      button.classList.toggle('text-white', isActive);
    });
    updateStoryPreview();
  }

  function handleStoryFontSizeChange(nextSize) {
    const parsed = parseInt(nextSize, 10);
    const clamped = Number.isFinite(parsed) ? Math.min(48, Math.max(16, parsed)) : 22;
    state.stories.composer.fontSize = clamped;
    if (state.stories.modal.fontLabel) {
      state.stories.modal.fontLabel.textContent = `${clamped}px`;
    }
    updateStoryPreview();
  }

  function updateStoryPreview() {
    const overlay = state.stories.modal.previewOverlay;
    if (!overlay) return;
    const composer = state.stories.composer;
    const content = (composer.text || '').trim();
    const hasContent = Boolean(content);
    overlay.textContent = hasContent ? content : 'Add a quick note…';
    overlay.style.color = composer.textColor || '#f8fafc';
    overlay.style.fontSize = `${composer.fontSize}px`;
    overlay.style.background = 'none';
    overlay.style.backgroundImage = 'none';
    const backgroundValue = hasContent ? getStoryBackgroundValue() : '#1f2937';
    if (!hasContent) {
      overlay.style.backgroundColor = backgroundValue;
    } else if (backgroundValue === null) {
      overlay.style.backgroundColor = 'transparent';
    } else if (backgroundValue) {
      if (backgroundValue.startsWith('linear-gradient')) {
        overlay.style.backgroundImage = backgroundValue;
        overlay.style.backgroundColor = 'transparent';
      } else {
        overlay.style.backgroundColor = backgroundValue;
      }
    } else {
      overlay.style.backgroundColor = 'rgba(15,23,42,0.65)';
    }
    applyStoryOverlayPosition(overlay, composer.textPosition);
  }

  function getStoryBackgroundValue() {
    const composer = state.stories.composer;
    if (composer.backgroundPreset === 'clear') {
      return null;
    }
    if (composer.backgroundPreset && composer.backgroundPreset !== 'solid') {
      return STORY_BACKGROUND_PRESETS[composer.backgroundPreset] || composer.textBackground;
    }
    return composer.textBackground;
  }

  function applyStoryOverlayPosition(node, position) {
    if (!node) return;
    node.style.top = 'auto';
    node.style.bottom = 'auto';
    node.style.left = 'auto';
    node.style.right = 'auto';
    node.style.transform = 'none';
    const offset = '1.5rem';
    switch ((position || '').toLowerCase()) {
      case 'top-left':
        node.style.top = offset;
        node.style.left = offset;
        break;
      case 'top-right':
        node.style.top = offset;
        node.style.right = offset;
        break;
      case 'bottom-right':
        node.style.bottom = offset;
        node.style.right = offset;
        break;
      case 'center':
        node.style.top = '50%';
        node.style.left = '50%';
        node.style.transform = 'translate(-50%, -50%)';
        break;
      case 'bottom-left':
      default:
        node.style.bottom = offset;
        node.style.left = offset;
        break;
    }
  }

  async function handleStorySubmit(event) {
    event.preventDefault();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    const composer = state.stories.composer;
    const modal = state.stories.modal;
    if (!composer.file) {
      showToast('Choose a photo or short clip for your story.', 'warning');
      return;
    }
    if (modal.feedback) {
      modal.feedback.classList.add('hidden');
      modal.feedback.textContent = '';
    }
    if (modal.submit) {
      modal.submit.disabled = true;
      modal.submit.classList.add('opacity-70');
    }
    try {
      const uploaded = await uploadStoryMedia(composer.file);
      if (!uploaded?.id) {
        throw new Error('Upload failed.');
      }
      const backgroundPayload = getStoryBackgroundValue();
      await apiFetch('/stories/', {
        method: 'POST',
        body: JSON.stringify({
          media_asset_id: uploaded.id,
          text_overlay: composer.text || null,
          text_color: composer.textColor,
          text_background: backgroundPayload,
          text_position: composer.textPosition,
          text_font_size: composer.fontSize,
        }),
      });
      showToast('Story shared—followers can view it for 24 hours.', 'success');
      closeStoryModal(true);
      await loadStories({ force: true, silent: true });
    } catch (error) {
      if (modal.feedback) {
        modal.feedback.textContent = error.message || 'Unable to share story.';
        modal.feedback.classList.remove('hidden');
      }
      showToast(error.message || 'Unable to share story.', 'error');
    } finally {
      if (modal.submit) {
        modal.submit.disabled = false;
        modal.submit.classList.remove('opacity-70');
      }
    }
  }

  async function uploadStoryMedia(file) {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch('/media/upload?scope=stories', {
      method: 'POST',
      body: formData,
    });
  }

  async function loadStories(options = {}) {
    const normalized = typeof options === 'boolean' ? { force: options } : options;
    const { force = false, silent = false } = normalized;
    const list = document.getElementById('story-rail-items');
    if (!list || state.stories.loading) return;
    state.stories.loading = true;
    const loading = document.getElementById('story-loading');
    if (loading && !silent) loading.classList.remove('hidden');
    try {
      const response = await apiFetch('/stories/feed');
      const buckets = Array.isArray(response.items) ? response.items : [];
      const signature = buckets
        .map(bucket => `${bucket?.user?.id ?? 'anon'}:${bucket?.stories?.[0]?.id ?? 'none'}`)
        .join('|');
      if (!force && signature === state.stories.signature) {
        return;
      }
      state.stories.signature = signature;
      buckets.forEach(bucket => {
        bucket._viewed = Array.isArray(bucket?.stories)
          ? bucket.stories.every(story => isStoryViewed(story?.id))
          : false;
      });
      state.stories.items = buckets;
      sortStoryBuckets();
      renderStoryRail();
    } catch (error) {
      if (!silent) {
        showToast(error.message || 'Unable to load stories.', 'error');
      }
    } finally {
      state.stories.loading = false;
      if (loading) loading.classList.add('hidden');
    }
  }

  function renderStoryRail() {
    const list = document.getElementById('story-rail-items');
    if (!list) return;
    list.innerHTML = '';
    const empty = document.getElementById('story-empty');
    let hasStories = false;
    state.stories.items.forEach((bucket, bucketIndex) => {
      if (!bucket?.stories?.length) return;
      hasStories = true;
      const isViewed = Boolean(bucket._viewed);
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'group flex w-24 flex-col items-center gap-2 rounded-2xl bg-slate-900/40 p-2 text-center text-xs text-slate-300 transition hover:bg-slate-900/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400';
      if (isViewed) {
        chip.classList.add('opacity-70');
      }
      chip.addEventListener('click', () => openStoryViewer(bucketIndex, 0));
      const ring = document.createElement('div');
      ring.className = isViewed
        ? 'relative h-16 w-16 rounded-full bg-slate-800/80 p-[3px] shadow-inner shadow-black/50'
        : 'relative h-16 w-16 rounded-full bg-gradient-to-tr from-indigo-500 via-fuchsia-500 to-rose-500 p-[3px] shadow-lg shadow-indigo-900/40';
      const inner = document.createElement('div');
      inner.className = 'h-full w-full rounded-full bg-slate-950/80 p-[3px]';
      const avatar = document.createElement('img');
      avatar.src = resolveAvatarUrl(bucket.user?.avatar_url) || DEFAULT_AVATAR;
      avatar.alt = bucket.user?.username || 'Story avatar';
      avatar.className = 'h-full w-full rounded-full object-cover';
      inner.appendChild(avatar);
      ring.appendChild(inner);
      chip.appendChild(ring);
      const label = document.createElement('span');
      label.className = `max-w-[90px] truncate ${isViewed ? 'text-slate-500' : 'text-slate-100'}`;
      label.textContent = bucket.user?.display_name || bucket.user?.username || 'Story';
      chip.appendChild(label);
      list.appendChild(chip);
    });
    if (empty) {
      empty.classList.toggle('hidden', hasStories);
    }
    updateSelfStoryBadge();
  }

  function updateSelfStoryBadge() {
    const pill = document.getElementById('story-self-pill');
    if (!pill) return;
    const { userId } = getAuth();
    const hasStory = Boolean(
      userId &&
        state.stories.items.some(bucket => bucket?.user?.id && String(bucket.user.id) === String(userId) && bucket.stories?.length)
    );
    pill.classList.toggle('border-indigo-400', hasStory);
    pill.classList.toggle('text-indigo-200', hasStory);
    const status = pill.querySelector('[data-story-self-status]');
    if (status) {
      status.textContent = hasStory ? 'Live now' : 'Tap to add';
      status.classList.toggle('text-emerald-300', hasStory);
      status.classList.toggle('text-slate-500', !hasStory);
    }
  }

  function openStoryViewer(bucketIndex, storyIndex) {
    cacheStoryViewerElements();
    const viewer = state.stories.viewer;
    if (!viewer.root) return;
    viewer.bucketIndex = bucketIndex;
    viewer.storyIndex = storyIndex;
    renderStoryViewer();
    viewer.root.classList.remove('hidden');
    viewer.root.classList.add('flex');
    lockBodyScroll();
  }

  function closeStoryViewer() {
    const viewer = state.stories.viewer;
    if (!viewer.root) return;
    const wasVisible = !viewer.root.classList.contains('hidden');
    viewer.root.classList.add('hidden');
    viewer.root.classList.remove('flex');
    if (viewer.video) {
      viewer.video.pause?.();
      viewer.video.src = '';
    }
    if (viewer.image) {
      viewer.image.src = '';
    }
    if (wasVisible) {
      unlockBodyScroll();
    }
  }

  function stepStory(direction) {
    const next = findStoryNeighbor(direction);
    if (!next) {
      closeStoryViewer();
      return;
    }
    state.stories.viewer.bucketIndex = next.bucketIndex;
    state.stories.viewer.storyIndex = next.storyIndex;
    renderStoryViewer();
  }

  function renderStoryViewer() {
    const viewer = state.stories.viewer;
    const buckets = state.stories.items;
    if (!viewer.root || !Array.isArray(buckets) || !buckets.length) {
      closeStoryViewer();
      return;
    }
    const bucket = buckets[viewer.bucketIndex];
    if (!bucket || !bucket.stories?.length) {
      closeStoryViewer();
      return;
    }
    const story = bucket.stories[viewer.storyIndex];
    if (!story) {
      closeStoryViewer();
      return;
    }

    trackStoryView(bucket, story);

    const mediaKind = detectStoryMediaKind(story.media_content_type, story.media_url);
    if (mediaKind === 'video') {
      if (viewer.video) {
        viewer.video.src = story.media_url;
        viewer.video.classList.remove('hidden');
        viewer.video.play?.().catch(() => {
          /* noop */
        });
      }
      if (viewer.image) {
        viewer.image.classList.add('hidden');
        viewer.image.src = '';
      }
    } else if (viewer.image) {
      viewer.image.src = story.media_url;
      viewer.image.classList.remove('hidden');
      if (viewer.video) {
        viewer.video.pause?.();
        viewer.video.src = '';
        viewer.video.classList.add('hidden');
      }
    }

    if (viewer.text) {
      const overlayText = (story.text_overlay || '').trim();
      viewer.text.textContent = overlayText;
      viewer.text.style.display = overlayText ? 'inline-flex' : 'none';
      viewer.text.classList.toggle('hidden', !overlayText);
      viewer.text.style.color = story.text_color || '#f8fafc';
      const fontSize = story.text_font_size || 22;
      viewer.text.style.fontSize = `${fontSize}px`;
      viewer.text.style.background = 'none';
      viewer.text.style.backgroundImage = 'none';
      if (!overlayText) {
        viewer.text.style.backgroundColor = 'transparent';
      } else if (story.text_background === null) {
        viewer.text.style.backgroundColor = 'transparent';
      } else if (story.text_background) {
        if (story.text_background.startsWith('linear-gradient')) {
          viewer.text.style.backgroundImage = story.text_background;
          viewer.text.style.backgroundColor = 'transparent';
        } else {
          viewer.text.style.backgroundColor = story.text_background;
        }
      } else {
        viewer.text.style.backgroundColor = 'rgba(15,23,42,0.65)';
      }
      if (overlayText) {
        applyStoryOverlayPosition(viewer.text, story.text_position || 'bottom-left');
      }
    }

    if (viewer.author) {
      viewer.author.textContent = bucket.user?.display_name || bucket.user?.username || 'Story';
    }
    if (viewer.meta) {
      viewer.meta.textContent = `Posted ${formatDate(story.created_at)}`;
    }
    if (viewer.prev) {
      viewer.prev.disabled = !findStoryNeighbor(-1);
    }
    if (viewer.next) {
      viewer.next.disabled = !findStoryNeighbor(1);
    }
  }

  function findStoryNeighbor(direction) {
    const buckets = state.stories.items;
    if (!Array.isArray(buckets) || !buckets.length) return null;
    let bucketIndex = state.stories.viewer.bucketIndex;
    let storyIndex = state.stories.viewer.storyIndex + direction;

    if (direction < 0) {
      while (bucketIndex >= 0) {
        const stories = buckets[bucketIndex]?.stories || [];
        if (storyIndex >= 0 && storyIndex < stories.length) {
          return { bucketIndex, storyIndex };
        }
        bucketIndex -= 1;
        if (bucketIndex < 0) break;
        const prevStories = buckets[bucketIndex]?.stories || [];
        if (prevStories.length) {
          storyIndex = prevStories.length - 1;
          return { bucketIndex, storyIndex };
        }
      }
      return null;
    }

    while (bucketIndex < buckets.length) {
      const stories = buckets[bucketIndex]?.stories || [];
      if (storyIndex >= 0 && storyIndex < stories.length) {
        return { bucketIndex, storyIndex };
      }
      bucketIndex += 1;
      storyIndex = 0;
      if (bucketIndex >= buckets.length) break;
      const nextStories = buckets[bucketIndex]?.stories || [];
      if (nextStories.length) {
        return { bucketIndex, storyIndex };
      }
    }
    return null;
  }

  function detectStoryMediaKind(contentType, url) {
    if (typeof contentType === 'string' && contentType.toLowerCase().startsWith('video/')) {
      return 'video';
    }
    if (typeof contentType === 'string' && contentType.toLowerCase().startsWith('image/')) {
      return 'image';
    }
    const inferred = detectAttachmentType(url || '');
    return inferred === 'video' ? 'video' : 'image';
  }

  function ensureStoryViewHistory() {
    if (!state.stories.viewHistory || typeof state.stories.viewHistory !== 'object') {
      state.stories.viewHistory = {};
    }
  }

  function isStoryViewed(storyId) {
    if (!storyId) return false;
    ensureStoryViewHistory();
    return Boolean(state.stories.viewHistory[String(storyId)]);
  }

  function markStoryViewed(storyId) {
    if (!storyId) return;
    ensureStoryViewHistory();
    const key = String(storyId);
    if (state.stories.viewHistory[key]) {
      return;
    }
    state.stories.viewHistory[key] = Date.now();
    saveJson(STORY_VIEW_HISTORY_KEY, state.stories.viewHistory);
  }

  function trackStoryView(bucket, story) {
    if (!story?.id) return;
    markStoryViewed(story.id);
    if (!bucket || bucket._viewed) return;
    const fullyViewed = Array.isArray(bucket.stories) && bucket.stories.every(item => isStoryViewed(item?.id));
    if (fullyViewed) {
      bucket._viewed = true;
      sortStoryBuckets({ rerender: true });
    }
  }

  function getActiveViewerBucket() {
    const viewer = state.stories.viewer;
    if (!viewer?.root || viewer.root.classList.contains('hidden')) {
      return null;
    }
    return state.stories.items?.[viewer.bucketIndex] || null;
  }

  function sortStoryBuckets(options = {}) {
    if (!Array.isArray(state.stories.items) || state.stories.items.length === 0) return;
    const { rerender = false } = options;
    const activeBucket = getActiveViewerBucket();
    state.stories.items.sort((a, b) => {
      const viewedA = Number(Boolean(a?._viewed));
      const viewedB = Number(Boolean(b?._viewed));
      if (viewedA !== viewedB) {
        return viewedA - viewedB;
      }
      const latestA = Date.parse(a?.stories?.[0]?.created_at || '') || 0;
      const latestB = Date.parse(b?.stories?.[0]?.created_at || '') || 0;
      return latestB - latestA;
    });
    if (activeBucket) {
      const nextIndex = state.stories.items.indexOf(activeBucket);
      if (nextIndex >= 0) {
        state.stories.viewer.bucketIndex = nextIndex;
      }
    }
    if (rerender) {
      renderStoryRail();
    }
  }

  function setupComposer() {
    const form = document.getElementById('composer-form');
    if (!form) return;
    const fileInput = form.querySelector('input[type="file"]');
    const previewWrapper = document.getElementById('media-preview');
    const previewImage = document.getElementById('media-preview-image');
    const previewVideo = document.getElementById('media-preview-video');

    if (fileInput && previewWrapper && previewImage && previewVideo) {
      fileInput.addEventListener('change', () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) {
          previewWrapper.classList.add('hidden');
          previewImage.src = '';
          previewVideo.src = '';
          previewImage.classList.add('hidden');
          previewVideo.classList.add('hidden');
          return;
        }
        const isVideo = (file.type || '').startsWith('video/');
        previewWrapper.classList.remove('hidden');
        if (isVideo) {
          previewVideo.classList.remove('hidden');
          previewImage.classList.add('hidden');
          const url = URL.createObjectURL(file);
          previewVideo.src = url;
          previewVideo.play().catch(() => {
            /* ignore */
          });
        } else {
          previewImage.classList.remove('hidden');
          previewVideo.classList.add('hidden');
          const reader = new FileReader();
          reader.onload = e => {
            previewImage.src = e.target.result;
          };
          reader.readAsDataURL(file);
        }
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
        if (previewWrapper) {
          previewWrapper.classList.add('hidden');
          if (previewImage) {
            previewImage.src = '';
            previewImage.classList.add('hidden');
          }
          if (previewVideo) {
            previewVideo.pause?.();
            previewVideo.src = '';
            previewVideo.classList.add('hidden');
          }
        }
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
      if (typeof loadMediaReel === 'function') {
        loadMediaReel({ forceRefresh: true, silent: true }).catch(error => {
          console.warn('[media] failed to refresh reel after post deletion', error);
        });
      }
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

  function ensurePostEditorElements() {
    const controls = state.postEditor;
    if (controls.root) {
      return controls;
    }
    const root = document.createElement('div');
    root.id = POST_EDITOR_ROOT_ID;
    root.className = 'fixed inset-0 z-[999] hidden flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm';
    root.innerHTML = `
      <div class="w-full max-w-lg rounded-[32px] border border-slate-800/70 bg-slate-950/95 p-6 shadow-2xl shadow-black/40">
        <form data-role="post-edit-form" class="space-y-5">
          <header class="flex items-center justify-between">
            <div>
              <p class="text-lg font-semibold text-white">Edit post</p>
              <p class="text-xs text-slate-400">Update your caption or replace the media.</p>
            </div>
            <button type="button" data-role="post-edit-cancel" class="text-xs font-semibold text-slate-400 hover:text-white">Close</button>
          </header>
          <div class="space-y-2">
            <label class="text-sm font-semibold text-slate-200">Caption</label>
            <textarea data-role="post-edit-caption" rows="4" class="w-full rounded-2xl border border-slate-800/70 bg-slate-900/80 p-3 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"></textarea>
          </div>
          <div class="space-y-2">
            <label class="text-sm font-semibold text-slate-200">Replace media (optional)</label>
            <input data-role="post-edit-file" type="file" accept="image/*,video/*" class="w-full rounded-2xl border border-slate-800/70 bg-slate-900/80 text-sm text-slate-200 file:mr-4 file:cursor-pointer file:rounded-full file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-white file:hover:bg-indigo-500" />
            <p data-role="post-edit-media-status" class="text-xs text-slate-400">No media attached.</p>
          </div>
          <label class="flex items-center gap-2 text-xs text-slate-300">
            <input type="checkbox" data-role="post-edit-remove" class="h-4 w-4 rounded border-slate-700 bg-slate-900 text-indigo-500 focus:ring-indigo-500" />
            Remove current media
          </label>
          <div data-role="post-edit-error" class="hidden rounded-2xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-100"></div>
          <div class="flex items-center justify-end gap-3">
            <button type="button" data-role="post-edit-cancel" class="rounded-full border border-slate-700/60 px-4 py-2 text-xs font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white">Cancel</button>
            <button type="submit" data-role="post-edit-submit" class="rounded-full bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500">Save changes</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(root);
    const form = root.querySelector('[data-role="post-edit-form"]');
    const captionInput = root.querySelector('[data-role="post-edit-caption"]');
    const fileInput = root.querySelector('[data-role="post-edit-file"]');
    const removeMediaInput = root.querySelector('[data-role="post-edit-remove"]');
    const submitButton = root.querySelector('[data-role="post-edit-submit"]');
    const mediaStatus = root.querySelector('[data-role="post-edit-media-status"]');
    const errorNode = root.querySelector('[data-role="post-edit-error"]');
    const cancelButtons = root.querySelectorAll('[data-role="post-edit-cancel"]');
    cancelButtons.forEach(button => {
      button.addEventListener('click', event => {
        event.preventDefault();
        closePostEditor();
      });
    });
    root.addEventListener('click', event => {
      if (event.target === root) {
        closePostEditor();
      }
    });
    if (form) {
      form.addEventListener('submit', handlePostEditorSubmit);
    }
    if (!controls.escapeHandlerBound) {
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && state.postEditor.root && !state.postEditor.root.classList.contains('hidden')) {
          closePostEditor();
        }
      });
      controls.escapeHandlerBound = true;
    }
    controls.root = root;
    controls.form = form;
    controls.captionInput = captionInput;
    controls.fileInput = fileInput;
    controls.removeMediaInput = removeMediaInput;
    controls.mediaStatus = mediaStatus;
    controls.submitButton = submitButton;
    controls.errorNode = errorNode;
    return controls;
  }

  function openPostEditor(post) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!post || !post.id) return;
    const controls = ensurePostEditorElements();
    controls.postId = post.id;
    controls.originalCaption = post.caption || '';
    if (controls.captionInput) {
      controls.captionInput.value = post.caption || '';
    }
    if (controls.fileInput) {
      controls.fileInput.value = '';
    }
    if (controls.removeMediaInput) {
      controls.removeMediaInput.checked = false;
      controls.removeMediaInput.disabled = !post.media_url;
    }
    if (controls.mediaStatus) {
      controls.mediaStatus.textContent = post.media_url ? 'Media currently attached.' : 'No media attached.';
    }
    if (controls.errorNode) {
      controls.errorNode.classList.add('hidden');
      controls.errorNode.textContent = '';
    }
    controls.root.classList.remove('hidden');
    window.setTimeout(() => {
      if (controls.captionInput) {
        controls.captionInput.focus();
        controls.captionInput.setSelectionRange(controls.captionInput.value.length, controls.captionInput.value.length);
      }
    }, 10);
  }

  function closePostEditor() {
    const controls = state.postEditor;
    if (!controls.root) return;
    if (controls.form) {
      controls.form.reset();
    }
    if (controls.removeMediaInput) {
      controls.removeMediaInput.checked = false;
      controls.removeMediaInput.disabled = false;
    }
    if (controls.errorNode) {
      controls.errorNode.classList.add('hidden');
      controls.errorNode.textContent = '';
    }
    controls.postId = null;
    controls.originalCaption = '';
    controls.root.classList.add('hidden');
  }

  async function handlePostEditorSubmit(event) {
    event.preventDefault();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    const controls = state.postEditor.root ? state.postEditor : ensurePostEditorElements();
    if (!controls.postId) {
      return;
    }
    const captionValue = controls.captionInput ? controls.captionInput.value.trim() : '';
    const originalCaption = (controls.originalCaption || '').trim();
    const fileInput = controls.fileInput;
    const file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
    const removeMedia = Boolean(controls.removeMediaInput && controls.removeMediaInput.checked);
    const hasCaptionChange = Boolean(captionValue) && captionValue !== originalCaption;
    if (!hasCaptionChange && !file && !removeMedia) {
      const message = 'Make a change before saving your post.';
      if (controls.errorNode) {
        controls.errorNode.textContent = message;
        controls.errorNode.classList.remove('hidden');
      } else {
        showToast(message, 'warning');
      }
      return;
    }
    const formData = new FormData();
    if (hasCaptionChange) {
      formData.append('caption', captionValue);
    }
    if (file) {
      formData.append('file', file);
    }
    if (removeMedia) {
      formData.append('remove_media', 'true');
    }
    if (controls.submitButton) {
      controls.submitButton.disabled = true;
      controls.submitButton.classList.add('opacity-60', 'cursor-not-allowed');
    }
    if (controls.errorNode) {
      controls.errorNode.classList.add('hidden');
    }
    try {
      const updatedPost = await apiFetch(`/posts/${encodeURIComponent(controls.postId)}`, {
        method: 'PATCH',
        body: formData,
      });
      applyPostEditPatch(updatedPost);
      closePostEditor();
      showToast('Post updated.', 'success');
    } catch (error) {
      if (controls.errorNode) {
        controls.errorNode.textContent = error.message || 'Unable to update post.';
        controls.errorNode.classList.remove('hidden');
      } else {
        showToast(error.message || 'Unable to update post.', 'error');
      }
    } finally {
      if (controls.submitButton) {
        controls.submitButton.disabled = false;
        controls.submitButton.classList.remove('opacity-60', 'cursor-not-allowed');
      }
      if (fileInput) {
        fileInput.value = '';
      }
      if (controls.removeMediaInput) {
        controls.removeMediaInput.checked = false;
      }
    }
  }

  function applyPostEditPatch(updatedPost) {
    if (!updatedPost || !updatedPost.id) return;
    const key = String(updatedPost.id);
    const overrides = {
      caption: updatedPost.caption,
      media_url: updatedPost.media_url,
      media_asset_id: updatedPost.media_asset_id,
    };
    if (updatedPost.user_id) {
      overrides.user_id = updatedPost.user_id;
    }
    if (updatedPost.username) {
      overrides.username = updatedPost.username;
    }
    if (updatedPost.avatar_url) {
      overrides.avatar_url = updatedPost.avatar_url;
    }
    const existing =
      state.postRegistry[key] ||
      state.feedItems.find(item => String(item.id) === key) ||
      { id: updatedPost.id, user_id: updatedPost.user_id };
    const merged = { ...existing, ...overrides };
    state.postRegistry[key] = merged;
    state.feedItems = state.feedItems.map(item => (String(item.id) === key ? { ...item, ...overrides } : item));
    replacePostCardInstances(merged);
  }

  function replacePostCardInstances(post) {
    if (!post || !post.id) return;
    const postId = String(post.id);
    const nodes = document.querySelectorAll(`[data-post-card="${postId}"]`);
    if (!nodes.length) return;
    const authMeta = getAuth();
    const avatarUrl =
      state.avatarCache[String(post.user_id)] ||
      resolveAvatarUrl(post.avatar_url) ||
      DEFAULT_AVATAR;
    nodes.forEach(node => {
      const parent = node.parentElement;
      if (!parent) return;
      const replacement = createPostCard({ ...post }, authMeta, avatarUrl);
      parent.replaceChild(replacement, node);
    });
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
    const authorLabel = decorateLabelWithRole(author, comment.role, { compact: true, textClasses: 'font-semibold text-xs' });
    const previewText = comment.content || '';
    wrapper.innerHTML = `
      <div class="flex items-start gap-3">
        <div class="h-8 w-8 flex-shrink-0 overflow-hidden rounded-full border border-slate-800/70 bg-slate-900/60">
          <img id="${avatarId}" alt="${author}" class="h-full w-full object-cover" />
        </div>
        <div class="flex-1">
          <div class="flex items-center justify-between text-xs text-slate-400">
            <span class="flex flex-wrap items-center gap-2">${authorLabel}</span>
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

  function applyDislikeButtonState(button, isDisliked, dislikeCount) {
    if (!button) return;
    const baseClasses = 'inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2';
    button.dataset.disliked = isDisliked ? 'true' : 'false';
    button.className = isDisliked
      ? `${baseClasses} border-amber-400/60 bg-amber-500/20 text-amber-100 hover:bg-amber-500/30`
      : `${baseClasses} border-slate-700/60 bg-slate-800/80 text-white hover:border-rose-500/60 hover:bg-rose-600/70`;
    const label = button.querySelector('[data-role="dislike-label"]');
    const count = button.querySelector('[data-role="dislike-count"]');
    if (label) label.textContent = isDisliked ? 'Disliked' : 'Dislike';
    if (count) count.textContent = String(dislikeCount ?? 0);
  }

  function updateDislikeButtonsForPost(postId, isDisliked, dislikeCount) {
    document.querySelectorAll(`[data-role="dislike-button"][data-post-id="${postId}"]`).forEach(button => {
      applyDislikeButtonState(button, isDisliked, dislikeCount);
    });
  }

  function setPostEngagementSnapshot(snapshot) {
    if (!snapshot || !snapshot.post_id) return;
    const key = String(snapshot.post_id);
    const {
      like_count = 0,
      dislike_count = 0,
      comment_count = 0,
      viewer_has_liked = false,
      viewer_has_disliked = false,
    } = snapshot;
    const cached = state.postRegistry[key];
    if (cached) {
      cached.like_count = like_count;
      cached.comment_count = comment_count;
      cached.viewer_has_liked = viewer_has_liked;
      cached.dislike_count = dislike_count;
      cached.viewer_has_disliked = viewer_has_disliked;
    }
    state.feedItems.forEach(item => {
      if (String(item.id) === key) {
        item.like_count = like_count;
        item.comment_count = comment_count;
        item.viewer_has_liked = viewer_has_liked;
        item.dislike_count = dislike_count;
        item.viewer_has_disliked = viewer_has_disliked;
      }
    });
    updateLikeButtonsForPost(key, viewer_has_liked, like_count);
    updateDislikeButtonsForPost(key, viewer_has_disliked, dislike_count);
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
      post.viewer_has_disliked = snapshot.viewer_has_disliked;
      post.dislike_count = snapshot.dislike_count;
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

  async function togglePostDislike(post, button) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!post?.id || !button || button.disabled) return;
    const shouldUndislike = button.dataset.disliked === 'true';
    button.disabled = true;
    button.classList.add('opacity-70');
    try {
      const snapshot = await apiFetch(`/posts/${encodeURIComponent(post.id)}/dislikes`, {
        method: shouldUndislike ? 'DELETE' : 'POST'
      });
      setPostEngagementSnapshot(snapshot);
      post.viewer_has_disliked = snapshot.viewer_has_disliked;
      post.dislike_count = snapshot.dislike_count;
      post.viewer_has_liked = snapshot.viewer_has_liked;
      post.like_count = snapshot.like_count;
      if (!shouldUndislike) {
        showToast('Post disliked.', 'info');
      }
    } catch (error) {
      showToast(error.message || 'Unable to update dislike.', 'error');
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
        dislike_count: typeof post.dislike_count === 'number' ? post.dislike_count : 0,
        comment_count: post.comment_count,
        viewer_has_liked: Boolean(post.viewer_has_liked),
        viewer_has_disliked: Boolean(post.viewer_has_disliked),
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

  function extractFileExtension(url) {
    if (typeof url !== 'string' || !url.trim()) {
      return '';
    }
    const [clean] = url.split(/[?#]/);
    const segment = (clean || '').split('/').pop() || '';
    const dotIndex = segment.lastIndexOf('.');
    if (dotIndex === -1) {
      return '';
    }
    return segment.slice(dotIndex + 1).toLowerCase();
  }

  function inferPostMediaKind(post) {
    if (!post || typeof post !== 'object') {
      return null;
    }
    const typeCandidates = [
      post.media_content_type,
      post.content_type,
      post.mediaContentType,
      post.media?.content_type,
      post.media?.contentType,
    ];
    for (const candidate of typeCandidates) {
      if (typeof candidate !== 'string') continue;
      const normalized = candidate.trim().toLowerCase();
      if (!normalized) continue;
      if (normalized.startsWith('video/')) return 'video';
      if (normalized.startsWith('image/')) return 'image';
    }
    const url = typeof post.media_url === 'string' ? post.media_url : '';
    const ext = extractFileExtension(url);
    if (!ext) {
      return null;
    }
    if (POST_MEDIA_VIDEO_EXTENSIONS.has(ext)) {
      return 'video';
    }
    if (POST_MEDIA_IMAGE_EXTENSIONS.has(ext)) {
      return 'image';
    }
    return null;
  }

  function sanitizePostMediaUrl(value) {
    if (typeof value !== 'string') {
      return '';
    }
    const trimmed = value.trim();
    if (!trimmed) {
      return '';
    }
    const normalized = trimmed.toLowerCase();
    if (INVALID_POST_MEDIA_URL_STRINGS.has(normalized)) {
      return '';
    }
    return trimmed;
  }

  function buildPostMediaMarkup(post) {
    const url = sanitizePostMediaUrl(post?.media_url);
    if (!url) {
      return '';
    }
    const mediaKind = inferPostMediaKind(post);
    const containerClasses =
      'mt-4 aspect-[4/5] w-full overflow-hidden rounded-2xl border border-slate-800/50 bg-slate-950/70 flex items-center justify-center';
    if (mediaKind === 'video') {
      const posterAttr =
        typeof post?.media_preview_url === 'string' && post.media_preview_url.trim()
          ? ` poster="${post.media_preview_url.trim()}"`
          : '';
      return `
        <div class="${containerClasses}" data-role="post-media">
          <video
            class="h-full w-full object-contain bg-black"
            src="${url}"
            controls
            playsinline
            preload="metadata"${posterAttr}
          ></video>
        </div>
      `;
    }
    return `
      <div class="${containerClasses}" data-role="post-media">
        <img
          src="${url}"
          alt="Post media"
          loading="lazy"
          decoding="async"
          data-role="post-media-image"
          class="max-h-full max-w-full object-contain"
          onerror="this.dataset.failed='true'; var container=this.closest('[data-role=post-media]'); if(container){container.remove();}"
        />
      </div>
    `;
  }

  function createPostCard(post, currentUserMeta, avatarUrl) {
    const el = document.createElement('article');
    el.className =
      'group rounded-3xl bg-slate-900/80 p-6 shadow-lg shadow-black/20 transition hover:-translate-y-1 hover:shadow-indigo-500/20 card-surface';
    if (post?.id) {
      el.dataset.postCard = String(post.id);
    }
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
    const authorRole = post.author_role || post.role || null;
    const decoratedDisplayName = decorateLabelWithRole(displayName, authorRole, {
      compact: true,
      textClasses: 'text-sm font-semibold',
    });
    const timestamp = formatDate(post.created_at);
    const mediaSection = buildPostMediaMarkup(post);
    const likeCount = typeof post.like_count === 'number' ? post.like_count : 0;
    const dislikeCount = typeof post.dislike_count === 'number' ? post.dislike_count : 0;
    const commentCount = typeof post.comment_count === 'number' ? post.comment_count : 0;
    const viewerHasLiked = Boolean(post.viewer_has_liked);
    const viewerHasDisliked = Boolean(post.viewer_has_disliked);
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
    const editButtonMarkup = isCurrentUser
      ? `<button
          data-role="edit-post"
          data-post-id="${post.id}"
          class="inline-flex items-center gap-2 rounded-full border border-slate-700/60 px-4 py-2 text-xs font-semibold text-white transition hover:border-indigo-500/60 hover:bg-indigo-600"
        >
          <span aria-hidden="true">✎</span>
          <span>Edit</span>
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
            <div class="flex flex-wrap items-center gap-2">${decoratedDisplayName}</div>
            <p class="text-xs text-slate-400">${timestamp}</p>
          </div>
        </div>
        ${followButtonMarkup}
      </header>
      <p class="mt-4 whitespace-pre-line text-sm text-slate-200">${post.caption || ''}</p>
      ${mediaSection}
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
          data-role="dislike-button"
          data-post-id="${post.id}"
          class="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold"
        >
          <span aria-hidden="true">👎</span>
          <span data-role="dislike-label">${viewerHasDisliked ? 'Disliked' : 'Dislike'}</span>
          <span data-role="dislike-count" class="text-[11px] text-slate-300">${dislikeCount}</span>
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
        ${editButtonMarkup}
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
    const editButton = el.querySelector('[data-role="edit-post"]');
    if (editButton) {
      editButton.addEventListener('click', event => {
        event.preventDefault();
        openPostEditor(post);
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
    const dislikeButton = el.querySelector('[data-role="dislike-button"]');
    if (dislikeButton) {
      applyDislikeButtonState(dislikeButton, viewerHasDisliked, dislikeCount);
      dislikeButton.addEventListener('click', event => {
        event.preventDefault();
        togglePostDislike(post, dislikeButton);
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
        setAuth({
          token: response.access_token,
          username: payload.username,
          userId: response.user_id,
          role: response.role || null,
        });
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
        setAuth({
          token: response.access_token,
          username: payload.username,
          userId: response.user_id,
          role: response.role || null,
        });
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
    const displayNameEl = document.getElementById('profile-display-name');
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
      if (displayNameEl) displayNameEl.textContent = profile.display_name || username || 'Your name';
      if (usernameEl) usernameEl.textContent = username ? `@${username}` : '@username';
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
          const uploadResult = await apiFetch('/media/upload?scope=avatars', {
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
    setupAttachmentPicker();
    setupGroupChatControls();
    await Promise.all([refreshFriendsDirectory(), refreshGroupDirectory()]);
    ensureActiveConversation();
  }

  async function refreshFriendsDirectory() {
    const container = document.getElementById('friend-list');
    if (container) container.classList.add('opacity-70');
    try {
      const data = await apiFetch('/friends/');
      state.friends = data.friends || [];
      state.incomingRequests = data.incoming_requests || [];
      state.outgoingRequests = data.outgoing_requests || [];
      const friendCount = document.getElementById('friend-count');
      if (friendCount) {
        friendCount.textContent = `${state.friends.length} contacts`;
      }
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

  async function refreshGroupDirectory() {
    const container = document.getElementById('group-list');
    if (container) container.classList.add('opacity-70');
    try {
      const data = await apiFetch('/messages/groups');
      state.groupChats = Array.isArray(data) ? data : [];
      const groupCount = document.getElementById('group-count');
      if (groupCount) {
        groupCount.textContent = `${state.groupChats.length} active`;
      }
      renderGroupList();
      reconcileActiveGroup();
    } catch (error) {
      console.warn('[groups] failed to load', error);
      renderGroupList(true);
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
      if (state.conversationMode === 'direct') {
        state.activeThreadLock = null;
        state.activeChatId = null;
        state.activeMessages = [];
        state.conversationMode = state.activeGroupId ? 'group' : null;
        if (!state.conversationMode) {
          disconnectMessageSocket();
          clearThreadView();
        }
      }
    }
    if (!state.activeFriendId && state.friends.length && !state.conversationMode) {
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

  function renderGroupList(showError = false) {
    const container = document.getElementById('group-list');
    if (!container) return;
    container.innerHTML = '';
    if (showError) {
      container.innerHTML = '<p class="px-2 py-3 text-sm text-rose-300">Unable to load group chats.</p>';
      return;
    }
    if (!state.groupChats.length) {
      container.innerHTML = '<p class="px-2 py-3 text-sm text-slate-400">No group chats yet. Tap <strong>New group</strong> to get started.</p>';
      return;
    }
    state.groupChats.forEach(chat => {
      const item = document.createElement('button');
      item.type = 'button';
      item.dataset.groupId = String(chat.id);
      item.className = `flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition hover:bg-emerald-500/10 ${
        String(state.activeGroupId) === String(chat.id) && state.conversationMode === 'group' ? 'bg-emerald-500/10' : ''
      }`;
      const memberPreview = (chat.members || []).slice(0, 3).join(', ') || 'No members yet';
      const lockSnippet = chat.lock_code ? shortenLock(chat.lock_code) : 'secure';
      item.innerHTML = `
        <div class="relative h-10 w-10 flex-shrink-0 overflow-hidden rounded-2xl border border-slate-800/70 bg-slate-900/60">
          <img data-group-avatar="${chat.id}" alt="${chat.name}" class="h-full w-full object-cover" />
        </div>
        <div class="flex-1">
          <p class="text-sm font-semibold text-slate-100">${escapeHtml(chat.name)}</p>
          <p class="text-[11px] text-slate-500">${escapeHtml(memberPreview)}</p>
        </div>
        <span class="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-200">Lock ${lockSnippet}</span>
      `;
      item.addEventListener('click', () => selectGroup(chat.id));
      container.appendChild(item);
      const avatarNode = item.querySelector(`[data-group-avatar="${chat.id}"]`);
      applyAvatarToImg(avatarNode, chat.avatar_url);
    });
    updateGroupSelection();
  }

  function reconcileActiveGroup() {
    const stillExists = state.groupChats.some(chat => String(chat.id) === String(state.activeGroupId));
    if (!stillExists) {
      state.activeGroupId = null;
      state.activeGroupMeta = null;
      state.activeGroupLock = null;
      if (state.conversationMode === 'group') {
        state.activeChatId = null;
        state.activeMessages = [];
        state.conversationMode = state.activeFriendId ? 'direct' : null;
        if (!state.conversationMode) {
          disconnectMessageSocket();
          clearThreadView();
        }
      }
    }
    if (!state.activeGroupId && state.groupChats.length && !state.conversationMode) {
      selectGroup(state.groupChats[0].id);
    } else {
      updateGroupSelection();
      updateRecipientHint();
      updateSendAvailability();
    }
  }

  function ensureActiveConversation() {
    if (state.conversationMode === 'direct' && state.activeFriendId) {
      return;
    }
    if (state.conversationMode === 'group' && state.activeGroupId) {
      return;
    }
    if (state.activeFriendId) {
      selectFriend(state.activeFriendId);
      return;
    }
    if (state.activeGroupId) {
      selectGroup(state.activeGroupId);
      return;
    }
    if (state.friends.length) {
      selectFriend(state.friends[0].id);
      return;
    }
    if (state.groupChats.length) {
      selectGroup(state.groupChats[0].id);
      return;
    }
    clearThreadView();
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
      state.messageAttachments = [];
      renderAttachmentPreview();
    }
    state.activeFriendId = friendId;
    state.activeGroupId = null;
    state.activeGroupMeta = null;
    state.activeGroupLock = null;
    state.conversationMode = 'direct';
    updateFriendSelection();
    updateGroupSelection();
    updateRecipientHint();
    updateSendAvailability();
    loadDirectThread(friendId);
  }

  function selectGroup(groupId) {
    if (!groupId) return;
    const sameGroup = String(state.activeGroupId) === String(groupId);
    if (sameGroup && state.threadLoading) {
      return;
    }
    if (!sameGroup) {
      state.activeChatId = null;
      state.activeMessages = [];
      disconnectMessageSocket();
      clearMessageReplyTarget();
      state.messageAttachments = [];
      renderAttachmentPreview();
    }
    state.activeGroupId = groupId;
    state.activeFriendId = null;
    state.activeFriendMeta = null;
    state.activeThreadLock = null;
    state.conversationMode = 'group';
    updateGroupSelection();
    updateFriendSelection();
    updateRecipientHint();
    updateSendAvailability();
    loadGroupThread(groupId);
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

  function updateGroupSelection() {
    document.querySelectorAll('[data-group-id]').forEach(node => {
      if (String(node.dataset.groupId) === String(state.activeGroupId) && state.conversationMode === 'group') {
        node.classList.add('bg-emerald-500/10');
      } else {
        node.classList.remove('bg-emerald-500/10');
      }
    });
  }

  function updateRecipientHint() {
    const hint = document.getElementById('message-recipient');
    if (!hint) return;
    if (state.conversationMode === 'group' && state.activeGroupMeta) {
      hint.textContent = `Messaging ${state.activeGroupMeta.name}`;
      hint.classList.remove('text-slate-500');
      hint.classList.add('text-emerald-200');
    } else if (state.activeFriendMeta) {
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
    const hasTarget = state.conversationMode === 'group' ? Boolean(state.activeGroupId) : Boolean(state.activeFriendId);
    const disabled = !hasTarget;
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
      primeMessageSenders(state.activeMessages);
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

  async function loadGroupThread(groupId) {
    const thread = document.getElementById('message-thread');
    const header = document.getElementById('chat-header');
    if (!thread || !header) return;
    state.threadLoading = true;
    thread.classList.add('opacity-80');
    try {
      const detail = await apiFetch(`/messages/groups/${encodeURIComponent(groupId)}`);
      state.activeGroupMeta = {
        id: detail.id,
        name: detail.name,
        members: detail.members || [],
        avatar_url: detail.avatar_url || null,
        owner_id: detail.owner_id || null,
      };
      state.activeGroupLock = detail.lock_code;
      state.activeGroupId = detail.id;
      state.activeChatId = detail.id ? String(detail.id) : null;
      const messages = await apiFetch(`/messages/${encodeURIComponent(detail.id)}`);
      state.activeMessages = Array.isArray(messages.messages) ? [...messages.messages] : [];
      primeMessageSenders(state.activeMessages);
      state.conversationMode = 'group';
      updateChatHeader();
      updateRecipientHint();
      renderMessageThread(state.activeMessages);
      connectMessageSocket(state.activeChatId);
    } catch (error) {
      showToast(error.message || 'Unable to load group.', 'error');
    } finally {
      state.threadLoading = false;
      thread.classList.remove('opacity-80');
    }
  }

  function updateChatHeader() {
    const header = document.getElementById('chat-header');
    if (!header) return;
    if (state.conversationMode === 'group' && state.activeGroupMeta) {
      const { name, avatar_url, members } = state.activeGroupMeta;
      const lockSnippet = shortenLock(state.activeGroupLock);
      const memberText = (members || []).slice(0, 4).join(', ') || 'No members yet';
      header.innerHTML = `
        <div class="flex items-center gap-3">
          <div class="h-12 w-12 overflow-hidden rounded-2xl border border-slate-800/70 bg-slate-900/60">
            <img id="active-group-avatar" alt="${escapeHtml(name)}" class="h-full w-full object-cover" />
          </div>
          <div>
            <h2 class="text-base font-semibold text-white">${escapeHtml(name)}</h2>
            <p class="text-xs text-slate-400">${escapeHtml(memberText)}</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <button id="group-invite-trigger" type="button" class="rounded-full border border-emerald-400/40 px-3 py-1 text-xs font-semibold text-emerald-200 transition hover:border-emerald-300">
            Invite
          </button>
          <span id="lock-indicator" class="rounded-full bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">Lock ${lockSnippet}</span>
        </div>
      `;
      const avatarNode = document.getElementById('active-group-avatar');
      applyAvatarToImg(avatarNode, avatar_url);
      const inviteTrigger = document.getElementById('group-invite-trigger');
      if (inviteTrigger && inviteTrigger.dataset.bound !== 'true') {
        inviteTrigger.dataset.bound = 'true';
        inviteTrigger.addEventListener('click', openGroupInviteModal);
      }
      return;
    }
    if (state.conversationMode === 'direct' && state.activeFriendMeta) {
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
      return;
    }
    clearThreadView();
  }

  function clearThreadView() {
    state.conversationMode = null;
    state.activeFriendId = null;
    state.activeFriendMeta = null;
    state.activeGroupId = null;
    state.activeGroupMeta = null;
    state.activeThreadLock = null;
    state.activeGroupLock = null;
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
    primeMessageSenders(payload);
    payload.forEach(message => {
      thread.appendChild(createMessageBubble(message, currentUser));
    });
    thread.scrollTop = thread.scrollHeight;
  }

  function primeMessageSender(message) {
    if (!message || !message.sender_id || !message.sender_avatar_url) {
      return;
    }
    updateAvatarCacheEntry(message.sender_id, message.sender_avatar_url);
  }

  function primeMessageSenders(records) {
    if (!Array.isArray(records)) {
      return;
    }
    records.forEach(primeMessageSender);
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
      const targetingGroup = state.conversationMode === 'group';
      const targetingFriend = state.conversationMode === 'direct';
      if (!targetingGroup && !targetingFriend) {
        showToast('Select a conversation to send a message.', 'warning');
        return;
      }
      if (targetingFriend && !state.activeFriendId) {
        showToast('Select a friend to send a message.', 'warning');
        return;
      }
      if (targetingGroup && !state.activeGroupId) {
        showToast('Select a group chat to send a message.', 'warning');
        return;
      }
      const hasAttachments = state.messageAttachments.length > 0;
      if (!content && !hasAttachments) {
        showToast('Share a note or attach a file first.', 'warning');
        return;
      }
      try {
        const payload = {
          content,
          friend_id: targetingFriend ? state.activeFriendId : null,
          chat_id: targetingGroup ? state.activeChatId : null,
          attachments: state.messageAttachments.map(item => item.url),
          reply_to_id: state.messageReplyTarget?.id || null,
        };
        const message = await apiFetch('/messages/send', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        showToast('Message sent!', 'success');
        form.reset();
        clearMessageReplyTarget();
        state.messageAttachments = [];
        renderAttachmentPreview();
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

  function setupAttachmentPicker() {
    const input = document.getElementById('message-attachment-input');
    const trigger = document.getElementById('message-attachment-trigger');
    if (!input || !trigger) return;
    trigger.addEventListener('click', () => input.click());
    input.addEventListener('change', async () => {
      const files = Array.from(input.files || []);
      if (!files.length) return;
      try {
        await handleAttachmentSelection(files);
      } finally {
        input.value = '';
      }
    });
    renderAttachmentPreview();
  }

  async function handleAttachmentSelection(files) {
    for (const file of files) {
      if (state.messageAttachments.length >= MESSAGE_ATTACHMENT_LIMIT) {
        showToast(`You can attach up to ${MESSAGE_ATTACHMENT_LIMIT} files.`, 'warning');
        break;
      }
      try {
        const url = await uploadMessageAsset(file);
        state.messageAttachments.push({
          url,
          name: file.name || file.type || 'attachment',
          type: detectAttachmentType(file.name || file.type || url),
        });
        renderAttachmentPreview();
      } catch (error) {
        showToast(error.message || 'Unable to upload attachment.', 'error');
        break;
      }
    }
  }

  function renderAttachmentPreview() {
    const preview = document.getElementById('message-attachment-preview');
    if (!preview) return;
    preview.innerHTML = '';
    if (!state.messageAttachments.length) {
      preview.classList.add('hidden');
      return;
    }
    preview.classList.remove('hidden');
    state.messageAttachments.forEach((attachment, index) => {
      const chip = document.createElement('div');
      chip.className = 'flex items-center gap-2 rounded-2xl border border-slate-800/60 bg-slate-950/60 px-3 py-1 text-xs text-slate-200';
      const icon = attachment.type === 'image' ? '🖼' : attachment.type === 'video' ? '🎬' : '📎';
      chip.innerHTML = `
        <span>${icon} ${escapeHtml(truncateText(attachment.name, 28))}</span>
        <button type="button" data-attachment-index="${index}" class="text-[11px] text-rose-300 transition hover:text-rose-100">Remove</button>
      `;
      const removeButton = chip.querySelector('button');
      removeButton.addEventListener('click', () => removeAttachment(index));
      preview.appendChild(chip);
    });
  }

  function removeAttachment(index) {
    state.messageAttachments.splice(index, 1);
    renderAttachmentPreview();
  }

  async function uploadMessageAsset(file, scope = 'messages') {
    const formData = new FormData();
    formData.append('file', file);
    const targetScope = scope || 'messages';
    const response = await apiFetch(`/media/upload?scope=${encodeURIComponent(targetScope)}`, {
      method: 'POST',
      body: formData,
    });
    if (!response?.url) {
      throw new Error('Upload failed.');
    }
    return response.url;
  }

  function detectAttachmentType(source) {
    if (!source) return 'file';
    const normalized = source.toLowerCase();
    const withoutQuery = normalized.split('?')[0];
    const parts = withoutQuery.split('.');
    const ext = parts.length > 1 ? parts.pop() : '';
    if (ext && POST_MEDIA_VIDEO_EXTENSIONS.has(ext)) return 'video';
    if (ext && POST_MEDIA_IMAGE_EXTENSIONS.has(ext)) return 'image';
    return 'file';
  }

  function setupGroupChatControls() {
    cacheGroupModals();
    const trigger = document.getElementById('group-create-trigger');
    if (trigger && trigger.dataset.bound !== 'true') {
      trigger.dataset.bound = 'true';
      trigger.addEventListener('click', () => toggleGroupCreateModal(true));
    }
    const create = state.groupModals.create;
    if (create.root && create.root.dataset.bound !== 'true') {
      create.root.dataset.bound = 'true';
      create.root.addEventListener('click', event => {
        if (event.target === create.root) {
          toggleGroupCreateModal(false);
        }
      });
    }
    create.root?.querySelectorAll('[data-group-create-close]').forEach(node => {
      if (node.dataset.bound === 'true') return;
      node.dataset.bound = 'true';
      node.addEventListener('click', () => toggleGroupCreateModal(false));
    });
    if (create.form && create.form.dataset.bound !== 'true') {
      create.form.dataset.bound = 'true';
      create.form.addEventListener('submit', handleGroupCreateSubmit);
    }
    if (create.avatarInput && create.avatarInput.dataset.bound !== 'true') {
      create.avatarInput.dataset.bound = 'true';
      create.avatarInput.addEventListener('change', () => updateGroupAvatarPreview());
    }
    const avatarTrigger = document.getElementById('group-avatar-trigger');
    if (avatarTrigger && avatarTrigger.dataset.bound !== 'true') {
      avatarTrigger.dataset.bound = 'true';
      avatarTrigger.addEventListener('click', () => create.avatarInput?.click());
    }
    const avatarClear = document.getElementById('group-avatar-clear');
    if (avatarClear && avatarClear.dataset.bound !== 'true') {
      avatarClear.dataset.bound = 'true';
      avatarClear.addEventListener('click', () => clearGroupAvatar());
    }

    const invite = state.groupModals.invite;
    if (invite.root && invite.root.dataset.bound !== 'true') {
      invite.root.dataset.bound = 'true';
      invite.root.addEventListener('click', event => {
        if (event.target === invite.root) {
          toggleGroupInviteModal(false);
        }
      });
    }
    invite.root?.querySelectorAll('[data-group-invite-close]').forEach(node => {
      if (node.dataset.bound === 'true') return;
      node.dataset.bound = 'true';
      node.addEventListener('click', () => toggleGroupInviteModal(false));
    });
    if (invite.form && invite.form.dataset.bound !== 'true') {
      invite.form.dataset.bound = 'true';
      invite.form.addEventListener('submit', handleGroupInviteSubmit);
    }
  }

  function cacheGroupModals() {
    const create = state.groupModals.create;
    if (!create.root) {
      create.root = document.getElementById('group-create-modal');
      create.form = document.getElementById('group-create-form');
      create.feedback = document.getElementById('group-create-feedback');
      create.avatarInput = document.getElementById('group-avatar-input');
      create.avatarPreview = document.getElementById('group-avatar-preview');
      create.membersInput = document.getElementById('group-members');
    }
    const invite = state.groupModals.invite;
    if (!invite.root) {
      invite.root = document.getElementById('group-invite-modal');
      invite.form = document.getElementById('group-invite-form');
      invite.feedback = document.getElementById('group-invite-feedback');
      invite.title = document.getElementById('group-invite-title');
      invite.membersInput = document.getElementById('group-invite-members');
    }
  }

  function toggleGroupCreateModal(show) {
    cacheGroupModals();
    const modal = state.groupModals.create.root;
    if (!modal) return;
    if (show) {
      resetGroupCreateForm();
      modal.classList.remove('hidden');
      lockBodyScroll();
    } else {
      const wasVisible = !modal.classList.contains('hidden');
      modal.classList.add('hidden');
      if (wasVisible) {
        unlockBodyScroll();
      }
    }
  }

  function toggleGroupInviteModal(show) {
    cacheGroupModals();
    const modal = state.groupModals.invite.root;
    if (!modal) return;
    if (show) {
      state.groupModals.invite.membersInput.value = '';
      if (state.groupModals.invite.feedback) {
        state.groupModals.invite.feedback.classList.add('hidden');
      }
      modal.classList.remove('hidden');
      lockBodyScroll();
    } else {
      const wasVisible = !modal.classList.contains('hidden');
      modal.classList.add('hidden');
      if (wasVisible) {
        unlockBodyScroll();
      }
    }
  }

  function resetGroupCreateForm() {
    const create = state.groupModals.create;
    create.form?.reset();
    if (create.feedback) {
      create.feedback.classList.add('hidden');
      create.feedback.textContent = '';
    }
    if (create.avatarPreview) {
      create.avatarPreview.src = DEFAULT_AVATAR;
    }
    if (create.avatarInput) {
      create.avatarInput.value = '';
    }
  }

  function updateGroupAvatarPreview() {
    const create = state.groupModals.create;
    const file = create.avatarInput?.files && create.avatarInput.files[0];
    if (!file) {
      clearGroupAvatar();
      return;
    }
    const reader = new FileReader();
    reader.onload = event => {
      if (create.avatarPreview) {
        create.avatarPreview.src = event.target?.result || DEFAULT_AVATAR;
      }
    };
    reader.readAsDataURL(file);
  }

  function clearGroupAvatar() {
    const create = state.groupModals.create;
    if (create.avatarPreview) {
      create.avatarPreview.src = DEFAULT_AVATAR;
    }
    if (create.avatarInput) {
      create.avatarInput.value = '';
    }
  }

  async function handleGroupCreateSubmit(event) {
    event.preventDefault();
    const create = state.groupModals.create;
    if (!create.form) return;
    const feedback = create.feedback;
    if (feedback) {
      feedback.classList.add('hidden');
      feedback.textContent = '';
    }
    const formData = new FormData(create.form);
    const name = String(formData.get('group-name') || '').trim();
    const members = parseUsernames(String(formData.get('group-members') || ''));
    if (!name || name.length < 3) {
      if (feedback) {
        feedback.textContent = 'Choose a name with at least three characters.';
        feedback.classList.remove('hidden');
      }
      return;
    }
    let avatarUrl = null;
    const avatarFile = create.avatarInput?.files && create.avatarInput.files[0];
    create.form.classList.add('opacity-70');
    const submitButton = create.form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    try {
      if (avatarFile) {
        avatarUrl = await uploadMessageAsset(avatarFile, 'avatars');
      }
      const payload = {
        name,
        members,
        avatar_url: avatarUrl,
      };
      const response = await apiFetch('/messages/groups', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      showToast('Group chat created.', 'success');
      toggleGroupCreateModal(false);
      await refreshGroupDirectory();
      if (response?.id) {
        state.activeGroupId = response.id;
        selectGroup(response.id);
      }
    } catch (error) {
      if (feedback) {
        feedback.textContent = error.message || 'Unable to create group right now.';
        feedback.classList.remove('hidden');
      }
    } finally {
      create.form.classList.remove('opacity-70');
      if (submitButton) submitButton.disabled = false;
    }
  }

  function parseUsernames(raw) {
    return (raw || '')
      .split(/[,\n]/)
      .map(value => value.replace(/^@/, '').trim())
      .filter(Boolean);
  }

  function openGroupInviteModal() {
    if (!state.activeGroupId || !state.activeGroupMeta) {
      showToast('Select a group first.', 'warning');
      return;
    }
    cacheGroupModals();
    const invite = state.groupModals.invite;
    if (!invite.root) return;
    invite.root.dataset.groupId = String(state.activeGroupId);
    if (invite.title) {
      invite.title.textContent = state.activeGroupMeta.name;
    }
    if (invite.feedback) {
      invite.feedback.classList.add('hidden');
      invite.feedback.textContent = '';
    }
    if (invite.membersInput) {
      invite.membersInput.value = '';
      invite.membersInput.focus();
    }
    toggleGroupInviteModal(true);
  }

  async function handleGroupInviteSubmit(event) {
    event.preventDefault();
    const invite = state.groupModals.invite;
    if (!invite.form) return;
    const targetGroupId = invite.root?.dataset.groupId || state.activeGroupId;
    if (!targetGroupId) {
      showToast('Select a group first.', 'warning');
      return;
    }
    const usernames = parseUsernames(invite.membersInput?.value || '');
    if (!usernames.length) {
      if (invite.feedback) {
        invite.feedback.textContent = 'Enter at least one username.';
        invite.feedback.classList.remove('hidden');
      }
      return;
    }
    invite.form.classList.add('opacity-70');
    const submitButton = invite.form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    try {
      const response = await apiFetch(`/messages/groups/${encodeURIComponent(targetGroupId)}/members`, {
        method: 'POST',
        body: JSON.stringify({ members: usernames }),
      });
      showToast('Invitations sent.', 'success');
      toggleGroupInviteModal(false);
      if (response?.id) {
        state.activeGroupMeta = {
          id: response.id,
          name: response.name,
          members: response.members || [],
          avatar_url: response.avatar_url || null,
          owner_id: response.owner_id || null,
        };
        state.activeGroupLock = response.lock_code;
        state.groupChats = state.groupChats.map(chat => (String(chat.id) === String(response.id) ? response : chat));
        renderGroupList();
        updateChatHeader();
      }
    } catch (error) {
      if (invite.feedback) {
        invite.feedback.textContent = error.message || 'Unable to send invites right now.';
        invite.feedback.classList.remove('hidden');
      }
    } finally {
      invite.form.classList.remove('opacity-70');
      if (submitButton) submitButton.disabled = false;
    }
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

  function renderMessageAttachments(attachments, outbound) {
    if (!attachments || !attachments.length) return '';
    const borderClass = outbound ? 'border-white/20' : 'border-slate-700/60';
    return `
      <div class="mt-3 space-y-2">
        ${attachments.map(url => renderSingleAttachment(url, borderClass)).join('')}
      </div>
    `;
  }

  function renderSingleAttachment(url, borderClass) {
    const safeUrl = escapeHtml(url);
    const type = detectAttachmentType(url);
    if (type === 'image') {
      return `
        <a href="${safeUrl}" target="_blank" rel="noopener" class="block overflow-hidden rounded-2xl border ${borderClass}">
          <img src="${safeUrl}" alt="Attachment" class="h-auto w-full object-cover" loading="lazy" />
        </a>
      `;
    }
    if (type === 'video') {
      return `
        <video controls class="w-full rounded-2xl border ${borderClass} bg-black/40" preload="metadata">
          <source src="${safeUrl}" />
          <a href="${safeUrl}" target="_blank" rel="noopener">View video</a>
        </video>
      `;
    }
    return `
      <a href="${safeUrl}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 rounded-2xl border ${borderClass} px-3 py-2 text-[11px] font-semibold">
        📎 Download file
      </a>
    `;
  }

  function createMessageBubble(message, currentUserId) {
    const outbound = String(message.sender_id) === String(currentUserId);
    const senderKey = message.sender_id ? String(message.sender_id) : null;
    const cachedAvatar = senderKey ? state.avatarCache[senderKey] : null;
    const avatarSource = cachedAvatar || (message.sender_avatar_url ? resolveAvatarUrl(message.sender_avatar_url) : DEFAULT_AVATAR);
    const identityName = outbound
      ? 'You'
      : message.sender_display_name ||
        (message.sender_username ? `@${message.sender_username}` : 'Unknown sender');
    const container = document.createElement('div');
    container.className = `mb-5 flex items-start gap-3 ${outbound ? 'flex-row-reverse' : ''}`;

    const avatarWrapper = document.createElement('div');
    avatarWrapper.className = 'mt-0.5 flex-shrink-0';
    const avatarImg = document.createElement('img');
    avatarImg.className = 'h-10 w-10 rounded-full border border-slate-800/70 object-cover shadow-sm';
    avatarImg.alt = identityName;
    avatarImg.src = avatarSource || DEFAULT_AVATAR;
    avatarWrapper.appendChild(avatarImg);

    const bubbleShell = document.createElement('div');
    bubbleShell.className = 'flex max-w-[75%] flex-col';
    if (outbound) {
      bubbleShell.classList.add('items-end', 'text-right');
    } else {
      bubbleShell.classList.add('items-start', 'text-left');
    }

    const bubble = document.createElement('div');
    bubble.className = `w-full rounded-2xl px-4 py-3 text-sm shadow-lg ${
      outbound ? 'bg-indigo-600 text-white' : 'bg-slate-800/90 text-slate-100'
    }`;
    if (message.id) {
      bubble.dataset.messageId = String(message.id);
    }

    const safeIdentity = escapeHtml(identityName);
    const usernameMarkup = message.sender_username
      ? `<span class="text-[10px] font-normal normal-case opacity-80">@${escapeHtml(message.sender_username)}</span>`
      : '';
    const identityMarkup = `
      <div class="mb-2 flex ${outbound ? 'justify-end text-white/80' : 'justify-start text-emerald-200'} gap-2 text-[11px] font-semibold uppercase tracking-wide">
        <span>${safeIdentity}</span>
        ${usernameMarkup}
      </div>
    `;
    const replyMarkup = renderMessageReplyContext(message.reply_to, outbound);
    const bodyMarkup = message.is_deleted
      ? '<p class="italic text-white/80">Message deleted</p>'
      : (message.content
          ? `<p class="whitespace-pre-line leading-relaxed">${message.content || ''}</p>`
          : '');
    const attachmentsMarkup = renderMessageAttachments(message.attachments, outbound);
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
    bubble.innerHTML = `${identityMarkup}${replyMarkup}${bodyMarkup}${attachmentsMarkup}${timestamp}${actions}`;

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

    bubbleShell.appendChild(bubble);
    container.appendChild(avatarWrapper);
    container.appendChild(bubbleShell);
    return container;
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
    primeMessageSender(message);
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

  const MEDIA_REEL_DEFAULT_LIMIT = 40;

  function computeMediaSignature(items) {
    if (!Array.isArray(items) || items.length === 0) {
      return `len:${items ? items.length : 0}`;
    }
    return items
      .map(item => `${item?.id ?? 'unknown'}:${item?.like_count ?? 0}:${item?.dislike_count ?? 0}:${item?.comment_count ?? 0}:${item?.created_at ?? ''}`)
      .join('|');
  }

  function requestMediaAssetVerification(assetId) {
    if (!assetId) return;
    const { token } = getAuth();
    if (!token) {
      return;
    }
    apiFetch(`/media/${encodeURIComponent(assetId)}/verify`, { method: 'POST' }).catch(error => {
      console.warn('[media] verification request failed', error);
    });
  }

  function removeMediaAssetFromState(assetId) {
    if (!assetId) return;
    const key = String(assetId);
    const before = state.mediaReel.items.length;
    state.mediaReel.items = state.mediaReel.items.filter(item => String(item.id) !== key);
    if (state.mediaReel.items.length === before) {
      return;
    }
    state.mediaReel.signature = computeMediaSignature(state.mediaReel.items);
    renderFullMediaReel();
    persistMediaReelCache(state.mediaReel.items, state.mediaReel.signature);
  }

  function handleMediaAssetElementError(asset, context = 'reel') {
    if (!asset || !asset.id) return;
    const key = String(asset.id);
    if (!state.mediaReel.brokenAssetIds) {
      state.mediaReel.brokenAssetIds = new Set();
    }
    if (state.mediaReel.brokenAssetIds.has(key)) {
      return;
    }
    state.mediaReel.brokenAssetIds.add(key);
    console.warn('[media] removing broken asset from context', context, key);
    removeMediaAssetFromState(key);
    requestMediaAssetVerification(key);
    if (!state.mediaReel.brokenNoticeShown) {
      state.mediaReel.brokenNoticeShown = true;
      showToast('Some uploads failed to load and were removed.', 'warning');
    }
  }

  function bindMediaElementErrorHandlers(node, asset, context) {
    if (!node) return;
    const handler = () => handleMediaAssetElementError(asset, context);
    node.addEventListener('error', handler, { once: true });
    if (node.tagName === 'VIDEO') {
      node.addEventListener('stalled', handler, { once: true });
      node.addEventListener('abort', handler, { once: true });
    }
  }

  function createMediaElementForAsset(asset, { variant = 'reel' } = {}) {
    const isVideo = typeof asset.content_type === 'string' && asset.content_type.startsWith('video/');
    if (isVideo) {
      const video = document.createElement('video');
      video.dataset.assetId = asset.id;
      video.dataset.mediaRole = variant === 'fullscreen' ? 'fullscreen-video' : 'reel-video';
      video.preload = 'metadata';
      video.playsInline = true;
      video.controls = true;
      video.className = variant === 'fullscreen'
        ? 'max-h-[78vh] w-full max-w-4xl rounded-[32px] border border-slate-800/80 bg-black object-contain'
        : 'h-full w-full object-contain bg-black';
      if (variant === 'reel') {
        video.loop = true;
        video.muted = true;
      }
      video.dataset.src = asset.url;
      bindMediaElementErrorHandlers(video, asset, variant);
      return video;
    }
    const img = document.createElement('img');
    img.src = asset.url;
    img.alt = 'Media item';
    img.loading = 'lazy';
    img.decoding = 'async';
    img.className = variant === 'fullscreen'
      ? 'max-h-[78vh] w-full max-w-4xl rounded-[32px] border border-slate-800/80 bg-black object-contain'
      : 'max-h-full max-w-full object-contain';
    bindMediaElementErrorHandlers(img, asset, variant);
    return img;
  }

  function getMediaCommentStore(assetId) {
    if (!assetId) return { items: [], loaded: false };
    const key = String(assetId);
    if (!state.mediaComments[key]) {
      state.mediaComments[key] = { items: [], loaded: false };
    }
    return state.mediaComments[key];
  }

  function applyMediaLikeButtonState(button, isLiked, likeCount) {
    if (!button) return;
    const baseClasses = 'inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2';
    button.dataset.liked = isLiked ? 'true' : 'false';
    button.className = isLiked
      ? `${baseClasses} border-emerald-400/70 bg-emerald-500/10 text-emerald-100 hover:bg-emerald-500/20`
      : `${baseClasses} border-slate-700/60 bg-slate-900/70 text-white hover:border-emerald-400/60 hover:text-emerald-100`;
    const label = button.querySelector('[data-media-role="like-label"]');
    const count = button.querySelector('[data-media-role="like-count"]');
    if (label) label.textContent = isLiked ? 'Liked' : 'Like';
    if (count) count.textContent = String(likeCount ?? 0);
  }

  function applyMediaDislikeButtonState(button, isDisliked, dislikeCount) {
    if (!button) return;
    const baseClasses = 'inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2';
    button.dataset.disliked = isDisliked ? 'true' : 'false';
    button.className = isDisliked
      ? `${baseClasses} border-amber-400/70 bg-amber-500/15 text-amber-50`
      : `${baseClasses} border-slate-700/60 bg-slate-900/70 text-white hover:border-amber-400/60 hover:text-amber-200`;
    const label = button.querySelector('[data-media-role="dislike-label"]');
    const count = button.querySelector('[data-media-role="dislike-count"]');
    if (label) label.textContent = isDisliked ? 'Disliked' : 'Dislike';
    if (count) count.textContent = String(dislikeCount ?? 0);
  }

  function updateMediaLikeButtonsForAsset(assetId, isLiked, likeCount) {
    document.querySelectorAll(`[data-media-role="like-button"][data-media-id="${assetId}"]`).forEach(button => {
      applyMediaLikeButtonState(button, isLiked, likeCount);
    });
  }

  function updateMediaDislikeButtonsForAsset(assetId, isDisliked, dislikeCount) {
    document.querySelectorAll(`[data-media-role="dislike-button"][data-media-id="${assetId}"]`).forEach(button => {
      applyMediaDislikeButtonState(button, isDisliked, dislikeCount);
    });
  }

  function updateMediaCommentCountDisplays(assetId, nextCount) {
    const value = typeof nextCount === 'number' ? nextCount : 0;
    document.querySelectorAll(`[data-media-role="comment-count"][data-media-id="${assetId}"]`).forEach(node => {
      node.textContent = String(value);
    });
  }

  function setMediaReelEngagementSnapshot(snapshot) {
    if (!snapshot || !snapshot.media_asset_id) return;
    const key = String(snapshot.media_asset_id);
    state.mediaReel.items.forEach(item => {
      if (String(item.id) === key) {
        item.like_count = snapshot.like_count;
        item.dislike_count = snapshot.dislike_count;
        item.comment_count = snapshot.comment_count;
        item.viewer_has_liked = snapshot.viewer_has_liked;
        item.viewer_has_disliked = snapshot.viewer_has_disliked;
      }
    });
    updateMediaLikeButtonsForAsset(key, snapshot.viewer_has_liked, snapshot.like_count);
    updateMediaDislikeButtonsForAsset(key, snapshot.viewer_has_disliked, snapshot.dislike_count);
    updateMediaCommentCountDisplays(key, snapshot.comment_count);
  }

  async function toggleMediaLike(asset, button) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!asset?.id || !button || button.disabled) return;
    const shouldUnlike = button.dataset.liked === 'true';
    button.disabled = true;
    button.classList.add('opacity-70');
    try {
      const snapshot = await apiFetch(`/media/${encodeURIComponent(asset.id)}/likes`, {
        method: shouldUnlike ? 'DELETE' : 'POST'
      });
      setMediaReelEngagementSnapshot(snapshot);
      asset.viewer_has_liked = snapshot.viewer_has_liked;
      asset.like_count = snapshot.like_count;
      asset.viewer_has_disliked = snapshot.viewer_has_disliked;
      asset.dislike_count = snapshot.dislike_count;
      if (!shouldUnlike) {
        showToast('Media liked.', 'success');
      }
    } catch (error) {
      showToast(error.message || 'Unable to update like.', 'error');
    } finally {
      button.disabled = false;
      button.classList.remove('opacity-70');
    }
  }

  async function toggleMediaDislike(asset, button) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!asset?.id || !button || button.disabled) return;
    const shouldUndislike = button.dataset.disliked === 'true';
    button.disabled = true;
    button.classList.add('opacity-70');
    try {
      const snapshot = await apiFetch(`/media/${encodeURIComponent(asset.id)}/dislikes`, {
        method: shouldUndislike ? 'DELETE' : 'POST'
      });
      setMediaReelEngagementSnapshot(snapshot);
      asset.viewer_has_disliked = snapshot.viewer_has_disliked;
      asset.dislike_count = snapshot.dislike_count;
      asset.viewer_has_liked = snapshot.viewer_has_liked;
      asset.like_count = snapshot.like_count;
      if (!shouldUndislike) {
        showToast('Media disliked.', 'info');
      }
    } catch (error) {
      showToast(error.message || 'Unable to update dislike.', 'error');
    } finally {
      button.disabled = false;
      button.classList.remove('opacity-70');
    }
  }

  function appendMediaCommentRecord(assetId, comment) {
    const store = getMediaCommentStore(assetId);
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

  function renderMediaCommentList(assetId, comments, container) {
    if (!container) return;
    container.innerHTML = '';
    const emptyState = container.parentElement?.querySelector('[data-media-role="comments-empty"]');
    const hasComments = Array.isArray(comments) && comments.length > 0;
    if (!hasComments) {
      if (emptyState) emptyState.classList.remove('hidden');
      return;
    }
    if (emptyState) emptyState.classList.add('hidden');
    comments.forEach(comment => {
      container.appendChild(createMediaCommentBlock(assetId, comment, 0));
    });
  }

  function createMediaCommentBlock(assetId, comment, depth) {
    const wrapper = document.createElement('div');
    wrapper.className = 'rounded-2xl border border-slate-800/70 bg-slate-950/60 p-4 shadow-sm shadow-black/10';
    wrapper.dataset.mediaCommentId = comment.id;
    if (depth > 0) {
      wrapper.style.marginLeft = `${Math.min(depth, 3) * 16}px`;
    }
    const avatarId = `media-comment-avatar-${comment.id}`;
    const author = comment.username ? `@${comment.username}` : 'User';
    const authorLabel = decorateLabelWithRole(author, comment.role, { compact: true, textClasses: 'font-semibold text-xs' });
    wrapper.innerHTML = `
      <div class="flex items-start gap-3">
        <div class="h-8 w-8 flex-shrink-0 overflow-hidden rounded-full border border-slate-800/70 bg-slate-900/60">
          <img id="${avatarId}" alt="${author}" class="h-full w-full object-cover" />
        </div>
        <div class="flex-1">
          <div class="flex items-center justify-between text-xs text-slate-400">
            <span class="flex flex-wrap items-center gap-2">${authorLabel}</span>
            <time class="text-[11px]">${formatDate(comment.created_at)}</time>
          </div>
          <p class="mt-1 text-sm text-slate-200">${comment.content || ''}</p>
          <div class="mt-2 flex gap-3 text-[11px] text-indigo-200">
            <button type="button" data-media-role="comment-reply" class="hover:text-white">Reply</button>
          </div>
        </div>
      </div>
    `;
    const avatarNode = wrapper.querySelector(`#${avatarId}`);
    applyAvatarToImg(avatarNode, comment.avatar_url);
    const replyButton = wrapper.querySelector('[data-media-role="comment-reply"]');
    if (replyButton) {
      replyButton.addEventListener('click', () => {
        const panel = wrapper.closest('[data-media-role="comment-panel"]');
        beginMediaCommentReply(assetId, comment, panel);
      });
    }
    if (Array.isArray(comment.replies) && comment.replies.length) {
      const repliesContainer = document.createElement('div');
      repliesContainer.className = 'mt-3 space-y-3';
      comment.replies.forEach(reply => {
        repliesContainer.appendChild(createMediaCommentBlock(assetId, reply, depth + 1));
      });
      wrapper.appendChild(repliesContainer);
    }
    return wrapper;
  }

  function resetMediaCommentReply(panel) {
    if (!panel) return;
    const form = panel.querySelector('[data-media-role="comment-form"]');
    if (form) delete form.dataset.replyId;
    const pill = panel.querySelector('[data-media-role="comment-reply-pill"]');
    if (pill) pill.classList.add('hidden');
    const usernameNode = panel.querySelector('[data-media-role="comment-reply-username"]');
    if (usernameNode) usernameNode.textContent = '@commenter';
    const previewNode = panel.querySelector('[data-media-role="comment-reply-preview"]');
    if (previewNode) previewNode.textContent = '';
  }

  function beginMediaCommentReply(assetId, comment, panel) {
    if (!panel || !comment) return;
    const form = panel.querySelector('[data-media-role="comment-form"]');
    const pill = panel.querySelector('[data-media-role="comment-reply-pill"]');
    const usernameNode = panel.querySelector('[data-media-role="comment-reply-username"]');
    const previewNode = panel.querySelector('[data-media-role="comment-reply-preview"]');
    if (!form || !pill || !usernameNode) return;
    form.dataset.replyId = comment.id;
    usernameNode.textContent = comment.username ? `@${comment.username}` : 'this comment';
    if (previewNode) {
      const preview = (comment.content || '').trim();
      previewNode.textContent = preview ? preview.slice(0, 160) + (preview.length > 160 ? '…' : '') : 'No text available.';
    }
    pill.classList.remove('hidden');
    const textarea = panel.querySelector('textarea');
    if (textarea) {
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    }
  }

  async function loadCommentsForMediaAsset(assetId, panel) {
    if (!panel || !assetId) return;
    const list = panel.querySelector('[data-media-role="comment-list"]');
    const store = getMediaCommentStore(assetId);
    if (store.loaded) {
      renderMediaCommentList(assetId, store.items, list);
      return;
    }
    panel.classList.add('opacity-70');
    try {
      const response = await apiFetch(`/media/${encodeURIComponent(assetId)}/comments`);
      const fetched = Array.isArray(response.items) ? response.items : [];
      store.items = fetched;
      store.loaded = true;
      renderMediaCommentList(assetId, store.items, list);
    } catch (error) {
      showToast(error.message || 'Unable to load comments.', 'error');
    } finally {
      panel.classList.remove('opacity-70');
    }
  }

  async function submitMediaCommentForm(asset, panel, form) {
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    if (!asset?.id || !panel || !form) return;
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
      const comment = await apiFetch(`/media/${encodeURIComponent(asset.id)}/comments`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      appendMediaCommentRecord(asset.id, comment);
      const store = getMediaCommentStore(asset.id);
      store.loaded = true;
      const list = panel.querySelector('[data-media-role="comment-list"]');
      renderMediaCommentList(asset.id, store.items, list);
      if (textarea) textarea.value = '';
      resetMediaCommentReply(panel);
      asset.comment_count = (asset.comment_count || 0) + 1;
      const snapshot = {
        media_asset_id: asset.id,
        like_count: typeof asset.like_count === 'number' ? asset.like_count : 0,
        dislike_count: typeof asset.dislike_count === 'number' ? asset.dislike_count : 0,
        comment_count: asset.comment_count,
        viewer_has_liked: Boolean(asset.viewer_has_liked),
        viewer_has_disliked: Boolean(asset.viewer_has_disliked),
      };
      setMediaReelEngagementSnapshot(snapshot);
      showToast('Comment added.', 'success');
    } catch (error) {
      showToast(error.message || 'Unable to add comment.', 'error');
    } finally {
      form.classList.remove('opacity-70');
      if (submitButton) submitButton.disabled = false;
    }
  }

  function toggleMediaCommentPanel(button, panel, asset) {
    if (!button || !panel || !asset?.id) return;
    const isOpen = button.dataset.open === 'true';
    const nextState = !isOpen;
    button.dataset.open = nextState ? 'true' : 'false';
    panel.classList.toggle('hidden', !nextState);
    const label = button.querySelector('[data-media-role="comment-toggle-label"]');
    if (label) label.textContent = nextState ? 'Hide' : 'Comment';
    if (nextState) {
      loadCommentsForMediaAsset(asset.id, panel);
      const textarea = panel.querySelector('textarea');
      if (textarea) {
        textarea.focus();
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);
      }
    } else {
      resetMediaCommentReply(panel);
    }
  }

  function hydrateMediaReelFromCache() {
    const cached = loadJson(MEDIA_REEL_CACHE_KEY, null);
    if (!cached || !Array.isArray(cached.items) || !cached.items.length) {
      return false;
    }
    state.mediaReel.items = cached.items;
    state.mediaReel.signature = cached.signature || null;
    renderFullMediaReel();
    return true;
  }

  function persistMediaReelCache(items, signature) {
    saveJson(MEDIA_REEL_CACHE_KEY, {
      items,
      signature,
      cached_at: Date.now(),
    });
  }

  function abortActiveMediaReelFetch() {
    if (state.mediaReel.fetchController) {
      try {
        state.mediaReel.fetchController.abort();
      } catch (_) {
        /* noop */
      }
      state.mediaReel.fetchController = null;
    }
  }

  function renderMediaReelSkeleton(count = MEDIA_REEL_SKELETON_COUNT) {
    const container = document.getElementById('media-reel');
    if (!container) return;
    container.innerHTML = '';
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < count; i += 1) {
      const card = document.createElement('article');
      card.className = 'snap-start rounded-[32px] border border-slate-800/40 bg-slate-950/40 p-6 animate-pulse';
      card.style.scrollSnapAlign = 'start';
      card.style.scrollSnapStop = 'always';
      card.innerHTML = `
        <div class="flex items-center gap-4">
          <div class="h-12 w-12 rounded-full bg-slate-800/70"></div>
          <div class="flex-1 space-y-2">
            <div class="h-3 w-32 rounded-full bg-slate-800/70"></div>
            <div class="h-3 w-24 rounded-full bg-slate-900/80"></div>
          </div>
        </div>
        <div class="mt-4 h-[60vh] w-full rounded-[24px] bg-slate-900/70"></div>
      `;
      fragment.appendChild(card);
    }
    container.appendChild(fragment);
  }

  function setupMediaReelScrollBehavior() {
    const container = document.getElementById('media-reel');
    if (!container || state.mediaReel.scrollEnhanced) return;
    state.mediaReel.scrollEnhanced = true;
    container.style.scrollBehavior = 'smooth';
    let wheelLocked = false;
    const scrollByStep = direction => {
      const step = container.clientHeight * 0.92 || 600;
      container.scrollBy({ top: direction * step, behavior: 'smooth' });
    };
    container.addEventListener(
      'wheel',
      event => {
        if (event.ctrlKey || Math.abs(event.deltaY) < 20) {
          return;
        }
        event.preventDefault();
        if (wheelLocked) return;
        wheelLocked = true;
        const direction = event.deltaY > 0 ? 1 : -1;
        scrollByStep(direction);
        window.setTimeout(() => {
          wheelLocked = false;
        }, MEDIA_REEL_SCROLL_LOCK_MS);
      },
      { passive: false }
    );
    container.addEventListener(
      'keydown',
      event => {
        if (event.defaultPrevented) return;
        if (event.key === 'ArrowDown' || event.key === 'PageDown') {
          event.preventDefault();
          scrollByStep(1);
        } else if (event.key === 'ArrowUp' || event.key === 'PageUp') {
          event.preventDefault();
          scrollByStep(-1);
        } else if (event.key === ' ' || event.key === 'Spacebar') {
          event.preventDefault();
          scrollByStep(event.shiftKey ? -1 : 1);
        }
      },
      { passive: false }
    );
  }

  function attachVideoSource(video, autoplay = false) {
    if (!video) return;
    if (video.dataset.src) {
      video.src = video.dataset.src;
      video.removeAttribute('data-src');
      video.load();
    }
    if (autoplay && typeof video.play === 'function') {
      video.play().catch(() => {
        /* Ignore autoplay failures */
      });
    }
  }

  function setupMediaReelVideoObserver() {
    if (state.mediaReel.videoObserver) {
      state.mediaReel.videoObserver.disconnect();
      state.mediaReel.videoObserver = null;
    }
    const videos = document.querySelectorAll('#media-reel [data-media-role="reel-video"]');
    if (!videos.length) {
      return;
    }
    if (typeof IntersectionObserver === 'undefined') {
      videos.forEach(video => attachVideoSource(video, true));
      return;
    }
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          const video = entry.target;
          if (entry.isIntersecting) {
            attachVideoSource(video, true);
          } else if (typeof video.pause === 'function') {
            try {
              video.pause();
              video.currentTime = 0;
            } catch (_) {
              /* noop */
            }
          }
        });
      },
      { threshold: 0.65 }
    );
    videos.forEach((video, index) => {
      if (index === 0) {
        attachVideoSource(video, true);
      }
      observer.observe(video);
    });
    state.mediaReel.videoObserver = observer;
  }

  async function loadMediaReel(options = {}) {
    const normalized = typeof options === 'boolean' ? { forceRefresh: options } : options;
    const { forceRefresh = false, silent = false } = normalized;
    const container = document.getElementById('media-reel');
    const loader = document.getElementById('media-reel-loader');
    const empty = document.getElementById('media-reel-empty');
    if (!container) return;
    if (state.mediaReel.loading) {
      abortActiveMediaReelFetch();
    }
    state.mediaReel.loading = true;
    if (!silent && loader) loader.classList.remove('hidden');
    if (empty) empty.classList.add('hidden');
    if (forceRefresh && !silent) {
      state.mediaReel.items = [];
      container.innerHTML = '';
    }
    if (forceRefresh) {
      state.mediaComments = {};
    }
    if (!silent && !state.mediaReel.items.length) {
      renderMediaReelSkeleton();
    }
    let controller = null;
    try {
      controller = new AbortController();
      state.mediaReel.fetchController = controller;
      const response = await apiFetch(`/media/feed?limit=${MEDIA_REEL_DEFAULT_LIMIT}`, {
        signal: controller.signal,
      });
      const items = Array.isArray(response.items) ? response.items : [];
      const signature = computeMediaSignature(items);
      const signatureChanged = state.mediaReel.signature !== signature;
      if (!forceRefresh && !signatureChanged) {
        return;
      }
      state.mediaReel.signature = signature;
      state.mediaReel.items = items;
      container.innerHTML = '';
      state.mediaComments = {};
      if (!items.length && empty) {
        empty.classList.remove('hidden');
      } else if (empty) {
        empty.classList.add('hidden');
      }
      renderFullMediaReel();
      persistMediaReelCache(items, signature);
    } catch (error) {
      if (error?.name === 'AbortError') {
        return;
      }
      showToast(error.message || 'Unable to load media feed.', 'error');
      if (empty) empty.classList.remove('hidden');
    } finally {
      state.mediaReel.loading = false;
      if (state.mediaReel.fetchController === controller) {
        state.mediaReel.fetchController = null;
      }
      if (loader) loader.classList.add('hidden');
    }
  }

  function renderFullMediaReel() {
    const container = document.getElementById('media-reel');
    if (!container) return;
    container.innerHTML = '';
    const fragment = document.createDocumentFragment();
    state.mediaReel.items.forEach(asset => {
      updateAvatarCacheEntry(asset.user_id, asset.avatar_url);
      fragment.appendChild(createMediaCard(asset));
    });
    container.appendChild(fragment);
    setupMediaReelScrollBehavior();
    setupMediaReelVideoObserver();
    syncMediaFullscreenToggleState();
    refreshMediaFullscreenContent();
  }

  function createMediaCard(asset) {
    const wrapper = document.createElement('article');
    wrapper.className = 'snap-start rounded-[32px] border border-slate-800/60 bg-slate-950/70 p-6 shadow-2xl shadow-black/40';
    wrapper.style.scrollSnapAlign = 'start';
    wrapper.style.scrollSnapStop = 'always';
    wrapper.dataset.mediaId = asset.id;
    const displayName = asset.display_name || asset.username || 'Unknown creator';
    const username = asset.username ? `@${asset.username}` : '';
    const creatorRole = asset.role || asset.author_role || null;
    const decoratedDisplayName = decorateLabelWithRole(displayName, creatorRole, {
      textClasses: 'text-base font-semibold leading-tight',
    });
    const normalizedCreatorRole = normalizeRole(creatorRole);
    const usernameClasses = ['font-semibold'];
    if (normalizedCreatorRole !== 'user') {
      usernameClasses.push(roleAccentClass(creatorRole));
    }
    const usernameLabel = username || 'Anonymous';
    const createdAt = formatDate(asset.created_at);
    const likeCount = typeof asset.like_count === 'number' ? asset.like_count : 0;
    const dislikeCount = typeof asset.dislike_count === 'number' ? asset.dislike_count : 0;
    const commentCount = typeof asset.comment_count === 'number' ? asset.comment_count : 0;
    const viewerHasLiked = Boolean(asset.viewer_has_liked);
    const viewerHasDisliked = Boolean(asset.viewer_has_disliked);
    wrapper.innerHTML = `
      <header class="flex items-center gap-4">
        <img data-media-role="avatar" data-user-id="${asset.user_id}" src="${DEFAULT_AVATAR}" class="h-12 w-12 rounded-full object-cover" alt="Creator avatar" />
        <div class="flex-1">
          <p class="leading-tight">${decoratedDisplayName}</p>
          <p class="text-xs text-slate-400">
            <span class="${usernameClasses.join(' ')}">${usernameLabel}</span>
            <span class="mx-2 text-slate-600" aria-hidden="true">•</span>
            <span>${createdAt}</span>
          </p>
        </div>
      </header>
      <div class="mt-4 aspect-[9/16] w-full overflow-hidden rounded-[24px] border border-slate-800/50 bg-black/70 flex items-center justify-center" data-media-role="asset-slot"></div>
      <footer class="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-400">
        <button data-media-role="like-button" data-media-id="${asset.id}" class="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold">
          <span aria-hidden="true">❤️</span>
          <span data-media-role="like-label">${viewerHasLiked ? 'Liked' : 'Like'}</span>
          <span data-media-role="like-count" class="text-[11px] text-slate-300">${likeCount}</span>
        </button>
        <button data-media-role="dislike-button" data-media-id="${asset.id}" class="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold">
          <span aria-hidden="true">👎</span>
          <span data-media-role="dislike-label">${viewerHasDisliked ? 'Disliked' : 'Dislike'}</span>
          <span data-media-role="dislike-count" class="text-[11px] text-slate-300">${dislikeCount}</span>
        </button>
        <button data-media-role="comment-toggle" data-media-id="${asset.id}" data-open="false" class="inline-flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-900/80 px-4 py-2 text-xs font-semibold text-white transition hover:border-indigo-500/60 hover:bg-indigo-600">
          <span aria-hidden="true">💬</span>
          <span data-media-role="comment-toggle-label">Comment</span>
          <span data-media-role="comment-count" data-media-id="${asset.id}" class="text-[11px] text-slate-200">${commentCount}</span>
        </button>
      </footer>
      <section data-media-role="comment-panel" data-media-id="${asset.id}" class="mt-4 hidden rounded-2xl border border-slate-800/60 bg-slate-950/60 p-4">
        <div data-media-role="comments-empty" class="text-sm text-slate-400">No comments yet. Spark the conversation.</div>
        <div data-media-role="comment-list" class="mt-4 space-y-3"></div>
        <form data-media-role="comment-form" class="mt-4 space-y-3">
          <div data-media-role="comment-reply-pill" class="hidden rounded-2xl border border-indigo-500/30 bg-indigo-500/5 px-3 py-2 text-xs text-indigo-100">
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="font-semibold text-indigo-200">
                  Replying to <span data-media-role="comment-reply-username" class="text-white">@commenter</span>
                </p>
                <p data-media-role="comment-reply-preview" class="mt-1 text-[11px] text-slate-300"></p>
              </div>
              <button type="button" data-media-role="comment-reply-cancel" class="text-[11px] font-semibold text-indigo-200 transition hover:text-white">Cancel</button>
            </div>
          </div>
          <textarea rows="3" class="w-full rounded-2xl border border-slate-800/70 bg-slate-900/80 p-3 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none" placeholder="Share your thoughts…" required></textarea>
          <div class="flex items-center justify-between gap-3">
            <button type="button" data-media-role="comment-reset" class="text-xs font-semibold text-slate-400 hover:text-white">Clear</button>
            <button type="submit" class="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500">
              <span class="text-base">➤</span>
              <span>Post comment</span>
            </button>
          </div>
        </form>
      </section>
    `;
    const avatarImg = wrapper.querySelector('[data-media-role="avatar"]');
    applyAvatarToImg(avatarImg, asset.avatar_url);
    const assetSlot = wrapper.querySelector('[data-media-role="asset-slot"]');
    if (assetSlot) {
      assetSlot.appendChild(createMediaElementForAsset(asset, { variant: 'reel' }));
    }
    const likeButton = wrapper.querySelector('[data-media-role="like-button"]');
    if (likeButton) {
      applyMediaLikeButtonState(likeButton, viewerHasLiked, likeCount);
      likeButton.addEventListener('click', event => {
        event.preventDefault();
        toggleMediaLike(asset, likeButton);
      });
    }
    const dislikeButton = wrapper.querySelector('[data-media-role="dislike-button"]');
    if (dislikeButton) {
      applyMediaDislikeButtonState(dislikeButton, viewerHasDisliked, dislikeCount);
      dislikeButton.addEventListener('click', event => {
        event.preventDefault();
        toggleMediaDislike(asset, dislikeButton);
      });
    }
    const commentToggle = wrapper.querySelector('[data-media-role="comment-toggle"]');
    const commentPanel = wrapper.querySelector('[data-media-role="comment-panel"]');
    if (commentToggle && commentPanel) {
      commentToggle.addEventListener('click', event => {
        event.preventDefault();
        toggleMediaCommentPanel(commentToggle, commentPanel, asset);
      });
      const form = commentPanel.querySelector('[data-media-role="comment-form"]');
      if (form) {
        form.addEventListener('submit', event => {
          event.preventDefault();
          submitMediaCommentForm(asset, commentPanel, form);
        });
        const resetBtn = commentPanel.querySelector('[data-media-role="comment-reset"]');
        if (resetBtn) {
          resetBtn.addEventListener('click', () => {
            const textarea = form.querySelector('textarea');
            if (textarea) textarea.value = '';
            resetMediaCommentReply(commentPanel);
          });
        }
        const cancelReply = commentPanel.querySelector('[data-media-role="comment-reply-cancel"]');
        if (cancelReply) {
          cancelReply.addEventListener('click', () => resetMediaCommentReply(commentPanel));
        }
      }
    }
    return wrapper;
  }

  function ensureMediaFullscreenElements() {
    const controller = state.mediaReel.fullscreen;
    if (controller.overlay && controller.list && controller.stage && controller.counter) {
      return controller;
    }
    let overlay = document.getElementById('media-fullscreen-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'media-fullscreen-overlay';
      overlay.className = 'fixed inset-0 z-[999] hidden bg-slate-950/95 text-white backdrop-blur-md opacity-0 transition-opacity duration-200';
      overlay.innerHTML = `
        <div class="flex h-full w-full flex-col bg-gradient-to-b from-slate-950/95 to-slate-900/90">
          <header class="flex items-center justify-between px-6 py-4 text-sm text-slate-300">
            <div>
              <p class="text-[11px] uppercase tracking-[0.3em] text-slate-500">Media reel</p>
              <p class="text-base font-semibold text-white">Fullscreen viewer</p>
            </div>
            <div class="flex items-center gap-3">
              <span data-media-fullscreen-counter class="text-xs text-slate-300">0 / 0</span>
              <button type="button" data-media-fullscreen-close class="rounded-full border border-slate-700/70 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-rose-500/60 hover:text-white">Close</button>
            </div>
          </header>
          <div class="relative flex-1 overflow-hidden" data-media-fullscreen-stage>
            <div data-media-fullscreen-track class="flex h-full w-full translate-x-0 items-stretch transition-transform duration-300 ease-out"></div>
            <button type="button" data-media-fullscreen-prev class="absolute left-4 top-1/2 -translate-y-1/2 rounded-full border border-slate-700/70 bg-slate-900/70 px-3 py-2 text-lg font-semibold text-white shadow-lg shadow-black/40 transition hover:border-indigo-500/70 hover:bg-indigo-600/80" aria-label="Previous media">‹</button>
            <button type="button" data-media-fullscreen-next class="absolute right-4 top-1/2 -translate-y-1/2 rounded-full border border-slate-700/70 bg-slate-900/70 px-3 py-2 text-lg font-semibold text-white shadow-lg shadow-black/40 transition hover:border-indigo-500/70 hover:bg-indigo-600/80" aria-label="Next media">›</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
    }

    controller.overlay = overlay;
    controller.list = overlay.querySelector('[data-media-fullscreen-track]');
    controller.stage = overlay.querySelector('[data-media-fullscreen-stage]');
    controller.counter = overlay.querySelector('[data-media-fullscreen-counter]');
    controller.prev = overlay.querySelector('[data-media-fullscreen-prev]');
    controller.next = overlay.querySelector('[data-media-fullscreen-next]');

    const closeButton = overlay.querySelector('[data-media-fullscreen-close]');
    if (closeButton && closeButton.dataset.bound !== 'true') {
      closeButton.dataset.bound = 'true';
      closeButton.addEventListener('click', event => {
        event.preventDefault();
        closeMediaFullscreen();
      });
    }

    if (overlay.dataset.bound !== 'true') {
      overlay.dataset.bound = 'true';
      overlay.addEventListener('click', event => {
        if (event.target === overlay) {
          closeMediaFullscreen();
        }
      });
    }

    if (controller.prev && controller.prev.dataset.bound !== 'true') {
      controller.prev.dataset.bound = 'true';
      controller.prev.addEventListener('click', event => {
        event.preventDefault();
        stepMediaFullscreen(-1);
      });
    }

    if (controller.next && controller.next.dataset.bound !== 'true') {
      controller.next.dataset.bound = 'true';
      controller.next.addEventListener('click', event => {
        event.preventDefault();
        stepMediaFullscreen(1);
      });
    }

    if (controller.stage && controller.stage.dataset.bound !== 'true') {
      controller.stage.dataset.bound = 'true';
      let wheelLocked = false;
      controller.stage.addEventListener(
        'wheel',
        event => {
          if (!state.mediaReel.fullscreen.active) return;
          if (Math.abs(event.deltaY) < 20) return;
          event.preventDefault();
          if (wheelLocked) return;
          wheelLocked = true;
          stepMediaFullscreen(event.deltaY > 0 ? 1 : -1);
          window.setTimeout(() => {
            wheelLocked = false;
          }, 360);
        },
        { passive: false }
      );
    }

    if (!controller.keyHandlerBound) {
      controller.keyHandlerBound = true;
      document.addEventListener('keydown', handleMediaFullscreenKeydown, true);
    }

    return controller;
  }

  function createMediaFullscreenSlide(asset, index) {
    const slide = document.createElement('section');
    slide.className = 'flex h-full w-full flex-shrink-0 flex-col items-center justify-center gap-6 px-6 py-10 text-center';
    slide.dataset.mediaId = asset.id || '';
    slide.dataset.index = String(index);
    const creator = escapeHtml(asset.display_name || asset.username || 'Unknown creator');
    const usernameLabel = asset.username ? `@${asset.username}` : '—';
    const safeUsername = escapeHtml(usernameLabel);
    const timestamp = formatDate(asset.created_at);
    const likeCount = typeof asset.like_count === 'number' ? asset.like_count : 0;
    const dislikeCount = typeof asset.dislike_count === 'number' ? asset.dislike_count : 0;
    const commentCount = typeof asset.comment_count === 'number' ? asset.comment_count : 0;
    slide.innerHTML = `
      <div class="flex w-full flex-1 items-center justify-center" data-media-role="asset-slot"></div>
      <div class="w-full max-w-3xl text-left text-sm text-slate-300">
        <p class="text-base font-semibold text-white">${creator}</p>
        <p class="text-xs text-slate-400">${safeUsername}</p>
        <p class="mt-1 text-[11px] text-slate-500">${timestamp}</p>
        <p class="mt-3 text-xs text-slate-400">❤️ ${likeCount} • 👎 ${dislikeCount} • 💬 ${commentCount}</p>
      </div>
    `;
    const assetSlot = slide.querySelector('[data-media-role="asset-slot"]');
    if (assetSlot) {
      assetSlot.appendChild(createMediaElementForAsset(asset, { variant: 'fullscreen' }));
    }
    return slide;
  }

  function buildMediaFullscreenSlides(startIndex = 0) {
    const controller = ensureMediaFullscreenElements();
    if (!controller.list) return;
    controller.list.innerHTML = '';
    const fragment = document.createDocumentFragment();
    state.mediaReel.items.forEach((asset, index) => {
      fragment.appendChild(createMediaFullscreenSlide(asset, index));
    });
    controller.list.appendChild(fragment);
    controller.currentIndex = 0;
    if (!state.mediaReel.items.length) {
      closeMediaFullscreen();
      syncMediaFullscreenToggleState();
      return;
    }
    goToMediaFullscreenIndex(Math.min(startIndex, state.mediaReel.items.length - 1));
  }

  function getVisibleMediaReelIndex() {
    const container = document.getElementById('media-reel');
    if (!container) return 0;
    const cards = Array.from(container.querySelectorAll('article[data-media-id]'));
    if (!cards.length) return 0;
    const containerRect = container.getBoundingClientRect();
    let closestIndex = 0;
    let shortestDistance = Number.POSITIVE_INFINITY;
    cards.forEach((card, index) => {
      const rect = card.getBoundingClientRect();
      const distance = Math.abs(rect.top - containerRect.top);
      if (distance < shortestDistance) {
        shortestDistance = distance;
        closestIndex = index;
      }
    });
    return closestIndex;
  }

  function openMediaFullscreen(startIndex = 0) {
    if (!state.mediaReel.items.length) {
      showToast('Upload media to view fullscreen.', 'info');
      return;
    }
    const controller = ensureMediaFullscreenElements();
    buildMediaFullscreenSlides(startIndex);
    state.mediaReel.fullscreen.active = true;
    if (controller.overlay) {
      controller.overlay.classList.remove('hidden');
      requestAnimationFrame(() => {
        controller.overlay.classList.remove('opacity-0');
        controller.overlay.classList.add('opacity-100');
      });
    }
    lockBodyScroll();
    syncMediaFullscreenToggleState();
    syncMediaFullscreenControls();
    syncMediaFullscreenCounter();
    syncMediaFullscreenPlayback();
  }

  function closeMediaFullscreen() {
    const controller = state.mediaReel.fullscreen;
    if (!controller.active) {
      controller.active = false;
      syncMediaFullscreenToggleState();
      return;
    }
    controller.active = false;
    if (controller.overlay) {
      controller.overlay.classList.remove('opacity-100');
      controller.overlay.classList.add('opacity-0');
      window.setTimeout(() => {
        controller.overlay?.classList.add('hidden');
      }, 200);
    }
    if (controller.list) {
      controller.list.querySelectorAll('video').forEach(video => {
        if (typeof video.pause === 'function') {
          try {
            video.pause();
          } catch (_) {
            /* noop */
          }
        }
      });
    }
    unlockBodyScroll();
    syncMediaFullscreenToggleState();
  }

  function toggleMediaFullscreen() {
    if (state.mediaReel.fullscreen.active) {
      closeMediaFullscreen();
      return;
    }
    openMediaFullscreen(getVisibleMediaReelIndex());
  }

  function goToMediaFullscreenIndex(targetIndex) {
    const controller = state.mediaReel.fullscreen;
    if (!controller.list || !state.mediaReel.items.length) return;
    const maxIndex = state.mediaReel.items.length - 1;
    const clamped = Math.max(0, Math.min(targetIndex, maxIndex));
    controller.currentIndex = clamped;
    controller.list.style.transform = `translateX(-${clamped * 100}%)`;
    syncMediaFullscreenControls();
    syncMediaFullscreenCounter();
    syncMediaFullscreenPlayback();
  }

  function stepMediaFullscreen(delta) {
    goToMediaFullscreenIndex(state.mediaReel.fullscreen.currentIndex + delta);
  }

  function syncMediaFullscreenControls() {
    const controller = state.mediaReel.fullscreen;
    const total = state.mediaReel.items.length;
    const atStart = controller.currentIndex <= 0;
    const atEnd = controller.currentIndex >= total - 1;
    if (controller.prev) {
      controller.prev.disabled = atStart;
      controller.prev.classList.toggle('opacity-40', atStart);
    }
    if (controller.next) {
      controller.next.disabled = atEnd;
      controller.next.classList.toggle('opacity-40', atEnd);
    }
  }

  function syncMediaFullscreenCounter() {
    const controller = state.mediaReel.fullscreen;
    if (!controller.counter) return;
    const total = state.mediaReel.items.length;
    if (!total) {
      controller.counter.textContent = '0 / 0';
      return;
    }
    controller.counter.textContent = `${controller.currentIndex + 1} / ${total}`;
  }

  function syncMediaFullscreenPlayback() {
    const controller = state.mediaReel.fullscreen;
    if (!controller.list) return;
    const videos = controller.list.querySelectorAll('video[data-media-role="fullscreen-video"]');
    videos.forEach((video, index) => {
      if (index === controller.currentIndex) {
        attachVideoSource(video, true);
      } else if (typeof video.pause === 'function') {
        try {
          video.pause();
          video.currentTime = 0;
        } catch (_) {
          /* noop */
        }
      }
    });
  }

  function handleMediaFullscreenKeydown(event) {
    if (!state.mediaReel.fullscreen.active) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeMediaFullscreen();
      return;
    }
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      stepMediaFullscreen(1);
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      stepMediaFullscreen(-1);
    }
  }

  function refreshMediaFullscreenContent() {
    if (!state.mediaReel.fullscreen.active) return;
    buildMediaFullscreenSlides(state.mediaReel.fullscreen.currentIndex);
  }

  function syncMediaFullscreenToggleState() {
    const toggle = document.getElementById('media-fullscreen-toggle');
    if (!toggle) return;
    const hasItems = state.mediaReel.items.length > 0;
    toggle.disabled = !hasItems;
    toggle.classList.toggle('opacity-50', !hasItems);
    toggle.classList.toggle('cursor-not-allowed', !hasItems);
    toggle.textContent = state.mediaReel.fullscreen.active ? 'Exit full screen' : 'Full screen';
  }

  function initMediaPage() {
    initThemeToggle();
    state.mediaReel.brokenNoticeShown = false;
    state.mediaReel.brokenAssetIds = new Set();
    const fileInput = document.getElementById('media-file');
    const preview = document.getElementById('media-preview');
    const previewImg = document.getElementById('media-preview-img');
    const previewVideo = document.getElementById('media-preview-video');
    const form = document.getElementById('media-upload-form');
    const feedback = document.getElementById('media-upload-feedback');
    const fullscreenToggle = document.getElementById('media-fullscreen-toggle');
    renderMediaHistory();
    syncMediaFullscreenToggleState();
    if (fullscreenToggle && fullscreenToggle.dataset.bound !== 'true') {
      fullscreenToggle.dataset.bound = 'true';
      fullscreenToggle.addEventListener('click', event => {
        event.preventDefault();
        toggleMediaFullscreen();
      });
    }
    const hydratedFromCache = hydrateMediaReelFromCache();
    setupMediaReelScrollBehavior();
    loadMediaReel({ forceRefresh: !hydratedFromCache }).catch(error => {
      console.warn('[media] failed to hydrate reel', error);
    });

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
          await loadMediaReel({ forceRefresh: true, silent: true });
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

  function toggleInteractiveState(element, disabled) {
    if (!element) return;
    element.disabled = disabled;
    element.classList.toggle('opacity-50', disabled);
    element.classList.toggle('pointer-events-none', disabled);
  }

  function clearVerificationCooldown() {
    if (state.settingsPage.verificationCooldownHandle) {
      clearInterval(state.settingsPage.verificationCooldownHandle);
      state.settingsPage.verificationCooldownHandle = null;
    }
  }

  function resetVerificationButton(button) {
    if (!button) return;
    clearVerificationCooldown();
    const baseLabel = button.dataset.label || 'Resend code';
    button.textContent = baseLabel;
    toggleInteractiveState(button, false);
  }

  function startVerificationCooldown(seconds) {
    const resendButton = document.getElementById('settings-resend-email');
    if (!resendButton) return;
    clearVerificationCooldown();
    const baseLabel = resendButton.dataset.label || resendButton.textContent || 'Resend code';
    resendButton.dataset.label = baseLabel;
    let remaining = Math.max(0, Math.floor(seconds || 0));
    if (remaining <= 0) {
      resetVerificationButton(resendButton);
      return;
    }
    toggleInteractiveState(resendButton, true);
    resendButton.textContent = `Resend (${remaining}s)`;
    state.settingsPage.verificationCooldownHandle = window.setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        resetVerificationButton(resendButton);
      } else {
        resendButton.textContent = `Resend (${remaining}s)`;
      }
    }, 1000);
  }

  function updateSettingsEmailStatus(data) {
    const badge = document.getElementById('settings-email-status');
    if (!badge) return;
    const baseClasses = 'mt-1 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs';
    if (!data.email) {
      badge.className = `${baseClasses} bg-rose-500/10 text-rose-200`;
      badge.innerHTML = '<span aria-hidden="true">⚠️</span><span>Add an email to secure your account.</span>';
      return;
    }
    if (data.email_verified) {
      badge.className = `${baseClasses} bg-emerald-500/10 text-emerald-300`;
      badge.innerHTML = '<span aria-hidden="true">✅</span><span>Email verified</span>';
      return;
    }
    const pendingCopy = data.email_verification_sent_at
      ? 'Check your inbox for the latest code.'
      : 'Verify your address to unlock alerts.';
    badge.className = `${baseClasses} bg-amber-500/10 text-amber-400`;
    badge.innerHTML = `<span aria-hidden="true">⚠️</span><span>${pendingCopy}</span>`;
  }

  function hydrateSettings(data) {
    if (!data) return;
    state.settingsPage.data = data;

    const nameInput = document.getElementById('settings-name');
    if (nameInput) nameInput.value = data.display_name || '';

    const usernameInput = document.getElementById('settings-username');
    if (usernameInput) usernameInput.value = data.username || '';

    const bioInput = document.getElementById('settings-bio');
    if (bioInput) bioInput.value = data.bio || '';

    const emailInput = document.getElementById('settings-email-input');
    if (emailInput) emailInput.value = data.email || '';

    const displayName = document.getElementById('settings-display-name');
    if (displayName) displayName.textContent = data.display_name || `@${data.username}`;

    const emailLabel = document.getElementById('settings-email');
    if (emailLabel) emailLabel.textContent = data.email || 'Add an email';

    const emailDmToggle = document.getElementById('settings-pref-email-dm');
    if (emailDmToggle) emailDmToggle.checked = Boolean(data.email_dm_notifications);

    const friendToggle = document.getElementById('settings-pref-friend-requests');
    if (friendToggle) friendToggle.checked = Boolean(data.allow_friend_requests);

    const dmToggle = document.getElementById('settings-pref-follower-dms');
    if (dmToggle) dmToggle.checked = Boolean(data.dm_followers_only);

    const verifyBtn = document.getElementById('settings-verify-email');
    if (verifyBtn) {
      const shouldDisable = !data.email || data.email_verified;
      toggleInteractiveState(verifyBtn, shouldDisable);
    }

    const resendBtn = document.getElementById('settings-resend-email');
    if (resendBtn) {
      if (!data.email || data.email_verified) {
        resetVerificationButton(resendBtn);
      } else if (!state.settingsPage.verificationCooldownHandle) {
        toggleInteractiveState(resendBtn, false);
        resendBtn.textContent = resendBtn.dataset.label || 'Resend code';
      }
    }

    const panel = document.getElementById('settings-verify-panel');
    if (panel) {
      if (!data.email || data.email_verified) {
        panel.classList.add('hidden');
        const codeInput = document.getElementById('settings-verify-code');
        if (codeInput) codeInput.value = '';
      } else if (data.email_verification_sent_at) {
        panel.classList.remove('hidden');
      } else {
        panel.classList.add('hidden');
      }
    }

    updateSettingsEmailStatus(data);
    refreshNavAuthState();
  }

  async function loadSettingsData() {
    try {
      const settings = await apiFetch('/settings/me');
      hydrateSettings(settings);
      setAuth({ username: settings.username });
    } catch (error) {
      showToast(error.message || 'Failed to load settings.', 'error');
    }
  }

  async function handleSettingsAvatarUpload(file) {
    if (!file) return;
    const avatarEl = document.getElementById('settings-avatar');
    if (avatarEl) {
      const reader = new FileReader();
      reader.onload = e => applyAvatarToImg(avatarEl, e.target.result);
      reader.readAsDataURL(file);
    }

    const payload = new FormData();
    payload.append('file', file);

    try {
      const uploadResult = await apiFetch('/media/upload?scope=avatars', {
        method: 'POST',
        body: payload
      });

      if (!uploadResult.url) {
        throw new Error('Upload failed.');
      }

      await apiFetch('/profiles/me', {
        method: 'PUT',
        body: JSON.stringify({ avatar_url: uploadResult.url })
      });

      await fetchCurrentUserProfile();
      applyAvatarToImg(avatarEl, uploadResult.url);
      showToast('Avatar updated successfully.', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to update avatar.', 'error');
    }
  }

  function bindPreferenceToggle(elementId, field) {
    const checkbox = document.getElementById(elementId);
    if (!checkbox || checkbox.dataset.bound === 'true') return;
    checkbox.dataset.bound = 'true';
    checkbox.addEventListener('change', () => handlePreferenceToggle(checkbox, field));
  }

  function bindSettingsEvents() {
    const logoutBtn = document.getElementById('settings-logout');
    if (logoutBtn && logoutBtn.dataset.bound !== 'true') {
      logoutBtn.dataset.bound = 'true';
      logoutBtn.addEventListener('click', () => {
        clearAuth();
        window.location.href = '/login';
      });
    }

    const profileSave = document.getElementById('settings-profile-save');
    if (profileSave && profileSave.dataset.bound !== 'true') {
      profileSave.dataset.bound = 'true';
      profileSave.addEventListener('click', handleSettingsProfileSave);
    }

    const contactSave = document.getElementById('settings-contact-save');
    if (contactSave && contactSave.dataset.bound !== 'true') {
      contactSave.dataset.bound = 'true';
      contactSave.addEventListener('click', handleSettingsContactSave);
    }

    const passwordForm = document.getElementById('settings-password-form');
    if (passwordForm && passwordForm.dataset.bound !== 'true') {
      passwordForm.dataset.bound = 'true';
      passwordForm.addEventListener('submit', handleSettingsPasswordSubmit);
    }

    bindPreferenceToggle('settings-pref-email-dm', 'email_dm_notifications');
    bindPreferenceToggle('settings-pref-friend-requests', 'allow_friend_requests');
    bindPreferenceToggle('settings-pref-follower-dms', 'dm_followers_only');

    const verifyBtn = document.getElementById('settings-verify-email');
    if (verifyBtn && verifyBtn.dataset.bound !== 'true') {
      verifyBtn.dataset.bound = 'true';
      verifyBtn.addEventListener('click', event => {
        event.preventDefault();
        handleEmailVerificationRequest(verifyBtn);
      });
    }

    const resendBtn = document.getElementById('settings-resend-email');
    if (resendBtn && resendBtn.dataset.bound !== 'true') {
      resendBtn.dataset.bound = 'true';
      resendBtn.dataset.label = resendBtn.textContent || 'Resend code';
      resendBtn.addEventListener('click', event => {
        event.preventDefault();
        handleEmailVerificationRequest(resendBtn);
      });
    }

    const verifySubmit = document.getElementById('settings-verify-submit');
    if (verifySubmit && verifySubmit.dataset.bound !== 'true') {
      verifySubmit.dataset.bound = 'true';
      verifySubmit.addEventListener('click', handleEmailVerificationConfirm);
    }

    const avatarTrigger = document.getElementById('settings-avatar-trigger');
    const avatarInput = document.getElementById('settings-avatar-file');
    if (avatarTrigger && avatarInput && avatarTrigger.dataset.bound !== 'true') {
      avatarTrigger.dataset.bound = 'true';
      avatarTrigger.addEventListener('click', event => {
        event.preventDefault();
        avatarInput.click();
      });
      avatarInput.addEventListener('change', async () => {
        const file = avatarInput.files && avatarInput.files[0];
        if (!file) return;
        await handleSettingsAvatarUpload(file);
        avatarInput.value = '';
      });
    }
  }

  async function handleSettingsProfileSave(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const nameInput = document.getElementById('settings-name');
    const usernameInput = document.getElementById('settings-username');
    const bioInput = document.getElementById('settings-bio');

    const usernameValue = (usernameInput && usernameInput.value ? usernameInput.value : '').trim().replace(/^@/, '');
    if (!usernameValue) {
      showToast('Username is required.', 'warning');
      return;
    }

    const payload = {
      display_name: nameInput && nameInput.value ? nameInput.value.trim() || null : null,
      username: usernameValue,
      bio: bioInput && bioInput.value ? bioInput.value.trim() || null : null,
    };

    toggleInteractiveState(button, true);
    try {
      const updated = await apiFetch('/settings/profile', {
        method: 'PATCH',
        body: JSON.stringify(payload)
      });
      hydrateSettings(updated);
      setAuth({ username: updated.username });
      showToast('Profile updated successfully.', 'success');
    } catch (error) {
      showToast(error.message || 'Unable to update profile.', 'error');
    } finally {
      toggleInteractiveState(button, false);
    }
  }

  async function handleSettingsContactSave(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const emailInput = document.getElementById('settings-email-input');
    const emailValue = (emailInput && emailInput.value ? emailInput.value : '').trim().toLowerCase();
    if (!emailValue) {
      showToast('Email cannot be empty.', 'warning');
      return;
    }

    toggleInteractiveState(button, true);
    try {
      const updated = await apiFetch('/settings/contact', {
        method: 'PATCH',
        body: JSON.stringify({ email: emailValue })
      });
      hydrateSettings(updated);
      showToast('Email updated successfully.', 'success');
    } catch (error) {
      showToast(error.message || 'Unable to update email.', 'error');
    } finally {
      toggleInteractiveState(button, false);
    }
  }

  async function handleSettingsPasswordSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = document.getElementById('settings-password-save');
    const current = form.elements['current_password']?.value || '';
    const next = form.elements['new_password']?.value || '';
    const confirm = form.elements['confirm_password']?.value || '';

    if (!current || !next || !confirm) {
      showToast('Fill in all password fields.', 'warning');
      return;
    }

    toggleInteractiveState(button, true);
    try {
      await apiFetch('/settings/password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: current,
          new_password: next,
          confirm_password: confirm,
        })
      });
      form.reset();
      showToast('Password updated successfully.', 'success');
    } catch (error) {
      showToast(error.message || 'Unable to update password.', 'error');
    } finally {
      toggleInteractiveState(button, false);
    }
  }

  async function handlePreferenceToggle(checkbox, field) {
    const desiredValue = checkbox.checked;
    try {
      const updated = await apiFetch('/settings/preferences', {
        method: 'PATCH',
        body: JSON.stringify({ [field]: desiredValue })
      });
      hydrateSettings(updated);
      showToast('Preference updated.', 'success');
    } catch (error) {
      checkbox.checked = !desiredValue;
      showToast(error.message || 'Unable to update preference.', 'error');
    }
  }

  async function handleEmailVerificationRequest(button) {
    if (!button) return;
    toggleInteractiveState(button, true);
    try {
      const result = await apiFetch('/settings/email/request', {
        method: 'POST'
      });
      if (result.cooldown_seconds) {
        startVerificationCooldown(result.cooldown_seconds);
      }
      if (result.expires_at) {
        showToast('Verification email sent.', 'success');
      } else {
        showToast('Please wait before requesting another code.', 'warning');
      }
      await loadSettingsData();
    } catch (error) {
      showToast(error.message || 'Unable to send verification email.', 'error');
    } finally {
      toggleInteractiveState(button, false);
    }
  }

  async function handleEmailVerificationConfirm(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const codeInput = document.getElementById('settings-verify-code');
    const code = (codeInput && codeInput.value ? codeInput.value : '').trim();
    if (code.length !== 6) {
      showToast('Enter the 6-digit code.', 'warning');
      return;
    }

    toggleInteractiveState(button, true);
    try {
      const updated = await apiFetch('/settings/email/confirm', {
        method: 'POST',
        body: JSON.stringify({ code })
      });
      if (codeInput) codeInput.value = '';
      hydrateSettings(updated);
      showToast('Email verified successfully.', 'success');
    } catch (error) {
      showToast(error.message || 'Invalid verification code.', 'error');
    } finally {
      toggleInteractiveState(button, false);
    }
  }

  async function initSettingsPage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    bindSettingsEvents();
    try {
      await fetchCurrentUserProfile();
    } catch (error) {
      console.warn('[settings] failed to hydrate avatar', error);
    }
    await loadSettingsData();
  }

  // -----------------------------------------------------------------------
  // Moderation
  // -----------------------------------------------------------------------

  const MODERATION_DATASET_META = {
    users: {
      title: 'All users',
      label: 'User directory',
      searchPlaceholder: 'Search username, email, or display name',
    },
    posts: {
      title: 'All posts',
      label: 'Post feed',
      searchPlaceholder: 'Search caption text',
    },
    media: {
      title: 'All media assets',
      label: 'Media library',
      searchPlaceholder: 'Search filename, URL, or creator',
    },
  };

  async function initModerationPage() {
    initThemeToggle();
    try {
      ensureAuthenticated();
    } catch {
      return;
    }
    const root = document.getElementById('moderation-root');
    const serverRole = root ? root.dataset.viewerRole || null : null;
    const { role, userId } = getAuth();
    const resolvedRole = (role || serverRole || 'user').toLowerCase();
    state.moderation.viewerRole = resolvedRole;
    state.moderation.viewerId = userId || null;
    cacheModerationNodes();
    bindModerationEvents();
    await loadModerationDashboard();
  }

  function cacheModerationNodes() {
    const panel = state.moderation.panel;
    panel.root = document.getElementById('moderation-dataset-panel');
    panel.title = document.getElementById('moderation-panel-title');
    panel.label = document.getElementById('moderation-panel-label');
    panel.searchInput = document.getElementById('moderation-panel-search');
    panel.pageLabel = document.getElementById('moderation-panel-page');
    panel.tableContainer = document.getElementById('moderation-panel-table');
    panel.emptyState = document.getElementById('moderation-panel-empty');
    panel.prevButton = document.getElementById('moderation-panel-prev');
    panel.nextButton = document.getElementById('moderation-panel-next');

    const modal = state.moderation.modal;
    modal.root = document.getElementById('moderation-detail-modal');
    modal.title = document.getElementById('moderation-detail-title');
    modal.label = document.getElementById('moderation-detail-label');
    modal.body = document.getElementById('moderation-detail-body');

    const confirm = state.moderation.confirm;
    confirm.root = document.getElementById('moderation-confirm-modal');
    confirm.title = document.getElementById('moderation-confirm-title');
    confirm.message = document.getElementById('moderation-confirm-message');
    confirm.accept = document.getElementById('moderation-confirm-accept');
    confirm.cancel = document.getElementById('moderation-confirm-cancel');
  }

  function bindModerationEvents() {
    document.querySelectorAll('[data-moderation-card]').forEach(card => {
      if (card.dataset.bound === 'true') return;
      card.dataset.bound = 'true';
      const handler = () => {
        const dataset = card.dataset.moderationCard;
        if (!dataset) return;
        openModerationDataset(dataset, {
          filter: card.dataset.moderationCardFilter || null,
          title: card.dataset.moderationCardTitle || null,
        });
      };
      card.addEventListener('click', handler);
      card.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          handler();
        }
      });
    });

    const refreshButton = document.getElementById('moderation-refresh');
    if (refreshButton && refreshButton.dataset.bound !== 'true') {
      refreshButton.dataset.bound = 'true';
      refreshButton.addEventListener('click', () => loadModerationDashboard());
    }

    const userTable = document.getElementById('moderation-user-table');
    if (userTable && userTable.dataset.bound !== 'true') {
      userTable.dataset.bound = 'true';
      userTable.addEventListener('change', event => {
        const select = event.target.closest('[data-mod-role-select]');
        if (!select) return;
        event.preventDefault();
        handleModerationRoleChange(select);
      });
    }

    const postTable = document.getElementById('moderation-post-table');
    if (postTable && postTable.dataset.bound !== 'true') {
      postTable.dataset.bound = 'true';
      postTable.addEventListener('click', event => {
        const button = event.target.closest('[data-mod-delete-post]');
        if (!button) return;
        event.preventDefault();
        const postId = button.dataset.postId;
        if (!postId) return;
        handleModerationPostDelete(postId, button);
      });
    }

    const panelClose = document.getElementById('moderation-panel-close');
    if (panelClose && panelClose.dataset.bound !== 'true') {
      panelClose.dataset.bound = 'true';
      panelClose.addEventListener('click', () => toggleModerationDatasetPanel(false));
    }

    const panelRoot = state.moderation.panel.root;
    if (panelRoot && panelRoot.dataset.bound !== 'true') {
      panelRoot.dataset.bound = 'true';
      panelRoot.addEventListener('click', event => {
        if (event.target === panelRoot) {
          toggleModerationDatasetPanel(false);
        }
      });
    }

    const searchInput = state.moderation.panel.searchInput;
    if (searchInput && searchInput.dataset.bound !== 'true') {
      searchInput.dataset.bound = 'true';
      searchInput.addEventListener('input', event => handleModerationPanelSearch(event.target.value));
    }

    const prevButton = state.moderation.panel.prevButton;
    if (prevButton && prevButton.dataset.bound !== 'true') {
      prevButton.dataset.bound = 'true';
      prevButton.addEventListener('click', () => paginateModerationDataset(-1));
    }

    const nextButton = state.moderation.panel.nextButton;
    if (nextButton && nextButton.dataset.bound !== 'true') {
      nextButton.dataset.bound = 'true';
      nextButton.addEventListener('click', () => paginateModerationDataset(1));
    }

    const tableContainer = state.moderation.panel.tableContainer;
    if (tableContainer && tableContainer.dataset.bound !== 'true') {
      tableContainer.dataset.bound = 'true';
      tableContainer.addEventListener('click', handleModerationDatasetAction);
      tableContainer.addEventListener('change', event => {
        const select = event.target.closest('[data-mod-role-select]');
        if (!select) return;
        event.preventDefault();
        handleModerationRoleChange(select);
      });
    }

    const detailClose = document.getElementById('moderation-detail-close');
    if (detailClose && detailClose.dataset.bound !== 'true') {
      detailClose.dataset.bound = 'true';
      detailClose.addEventListener('click', hideModerationDetailModal);
    }

    const detailRoot = state.moderation.modal.root;
    if (detailRoot && detailRoot.dataset.bound !== 'true') {
      detailRoot.dataset.bound = 'true';
      detailRoot.addEventListener('click', event => {
        if (event.target === detailRoot) {
          hideModerationDetailModal();
        }
      });
    }

    const confirmRoot = state.moderation.confirm.root;
    if (confirmRoot && confirmRoot.dataset.bound !== 'true') {
      confirmRoot.dataset.bound = 'true';
      confirmRoot.addEventListener('click', event => {
        if (event.target === confirmRoot) {
          finalizeModerationConfirm(false);
        }
      });
    }
  }

  function lockBodyScroll() {
    if (typeof document === 'undefined') return;
    if (scrollLock.count === 0) {
      scrollLock.bodyOverflow = document.body.style.overflow;
      scrollLock.htmlOverflow = document.documentElement.style.overflow;
      document.body.style.overflow = 'hidden';
      document.documentElement.style.overflow = 'hidden';
    }
    scrollLock.count += 1;
  }

  function unlockBodyScroll() {
    if (typeof document === 'undefined' || scrollLock.count === 0) return;
    scrollLock.count = Math.max(0, scrollLock.count - 1);
    if (scrollLock.count === 0) {
      document.body.style.overflow = scrollLock.bodyOverflow || '';
      document.documentElement.style.overflow = scrollLock.htmlOverflow || '';
      scrollLock.bodyOverflow = '';
      scrollLock.htmlOverflow = '';
    }
  }

  async function openModerationDataset(type, options = {}) {
    const meta = MODERATION_DATASET_META[type];
    if (!meta) return;
    const dataset = state.moderation.datasets[type];
    if (!dataset) return;
    const previousDataset = state.moderation.activeDataset;
    state.moderation.activeDataset = type;
    if (options.search !== undefined) {
      dataset.search = options.search.trim();
      dataset.skip = 0;
    }
    if (options.filter !== undefined) {
      dataset.filter = options.filter;
      dataset.skip = 0;
    }
    if (options.reset === true || previousDataset !== type) {
      dataset.skip = 0;
    }

    const panel = state.moderation.panel;
    if (panel.title) {
      panel.title.textContent = options.title || meta.title;
    }
    if (panel.label) {
      panel.label.textContent = meta.label;
    }
    if (panel.searchInput) {
      panel.searchInput.placeholder = meta.searchPlaceholder;
      panel.searchInput.value = dataset.search || '';
    }

    toggleModerationDatasetPanel(true);
    showModerationPanelLoading();
    try {
      await loadModerationDataset(type);
    } catch (error) {
      showToast(error.message || 'Unable to load dataset.', 'error');
      showModerationPanelError(error.message || 'Unable to load dataset.');
    }
  }

  function toggleModerationDatasetPanel(show) {
    const panelRoot = state.moderation.panel.root;
    if (!panelRoot) return;
    if (show) {
      const wasHidden = panelRoot.classList.contains('hidden');
      panelRoot.classList.remove('hidden');
      if (wasHidden) {
        lockBodyScroll();
      }
    } else {
      const wasVisible = !panelRoot.classList.contains('hidden');
      panelRoot.classList.add('hidden');
      state.moderation.activeDataset = null;
      if (wasVisible) {
        unlockBodyScroll();
      }
    }
  }

  function showModerationPanelLoading() {
    const container = state.moderation.panel.tableContainer;
    const emptyState = state.moderation.panel.emptyState;
    if (emptyState) emptyState.classList.add('hidden');
    if (container) {
      container.innerHTML = '<div class="rounded-2xl border border-slate-800/70 bg-slate-950/60 px-4 py-6 text-center text-sm text-slate-400">Loading…</div>';
    }
  }

  function showModerationPanelError(message) {
    const container = state.moderation.panel.tableContainer;
    const emptyState = state.moderation.panel.emptyState;
    if (container) {
      container.innerHTML = `<div class="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-6 text-center text-sm text-rose-100">${escapeHtml(message)}</div>`;
    }
    if (emptyState) emptyState.classList.add('hidden');
  }

  function handleModerationPanelSearch(rawValue) {
    const datasetKey = state.moderation.activeDataset;
    if (!datasetKey) return;
    const dataset = state.moderation.datasets[datasetKey];
    if (!dataset) return;
    dataset.search = (rawValue || '').trim();
    dataset.skip = 0;
    if (state.moderation.datasetSearchHandle) {
      clearTimeout(state.moderation.datasetSearchHandle);
    }
    state.moderation.datasetSearchHandle = setTimeout(() => {
      loadModerationDataset(datasetKey).catch(error => {
        showToast(error.message || 'Unable to refresh dataset.', 'error');
      });
      state.moderation.datasetSearchHandle = null;
    }, 320);
  }

  function paginateModerationDataset(delta) {
    const datasetKey = state.moderation.activeDataset;
    if (!datasetKey) return;
    const dataset = state.moderation.datasets[datasetKey];
    if (!dataset || !delta) return;
    const totalPages = dataset.total ? Math.ceil(dataset.total / dataset.limit) : null;
    const currentPage = Math.floor(dataset.skip / dataset.limit);
    const targetPage = currentPage + delta;
    if (targetPage < 0) return;
    if (totalPages !== null && targetPage >= totalPages) return;
    dataset.skip = Math.max(0, targetPage * dataset.limit);
    loadModerationDataset(datasetKey).catch(error => {
      showToast(error.message || 'Unable to change page.', 'error');
    });
  }

  function handleModerationDatasetAction(event) {
    const trigger = event.target.closest('[data-mod-action]');
    if (!trigger) return;
    event.preventDefault();
    const action = trigger.dataset.modAction;
    switch (action) {
      case 'view-user':
        openModerationUserDetail(trigger.dataset.userId);
        break;
      case 'delete-user':
        handleModerationUserDelete(trigger.dataset.userId, trigger);
        break;
      case 'view-post':
        openModerationPostDetail(trigger.dataset.postId);
        break;
      case 'delete-post':
        handleModerationPostDelete(trigger.dataset.postId, trigger);
        break;
      case 'view-media':
        openModerationMediaDetail(trigger.dataset.assetId);
        break;
      case 'delete-media':
        handleModerationMediaDelete(trigger.dataset.assetId, trigger);
        break;
      default:
        break;
    }
  }

  async function loadModerationDataset(type) {
    const dataset = state.moderation.datasets[type];
    if (!dataset) return [];
    const params = new URLSearchParams();
    params.set('skip', String(dataset.skip));
    params.set('limit', String(dataset.limit));
    if (dataset.search) {
      params.set('search', dataset.search);
    }
    if (dataset.filter === 'active') {
      params.set('active_only', '1');
    }

    const endpointMap = {
      users: '/moderation/users',
      posts: '/moderation/posts',
      media: '/moderation/media',
    };
    const endpoint = endpointMap[type];
    if (!endpoint) return [];
    const response = await apiFetch(`${endpoint}?${params.toString()}`);
    dataset.items = Array.isArray(response.items) ? response.items : [];
    dataset.total = typeof response.total === 'number' ? response.total : dataset.items.length;
    renderModerationDataset(type);
    return dataset.items;
  }

  function renderModerationDataset(type) {
    const dataset = state.moderation.datasets[type];
    const panel = state.moderation.panel;
    if (!dataset || !panel.tableContainer) return;
    const builderMap = {
      users: buildModerationUsersTable,
      posts: buildModerationPostsTable,
      media: buildModerationMediaTable,
    };
    const builder = builderMap[type];
    const hasRows = Boolean(dataset.items.length);
    if (!hasRows && panel.emptyState) {
      panel.emptyState.classList.remove('hidden');
    } else if (panel.emptyState) {
      panel.emptyState.classList.add('hidden');
    }
    panel.tableContainer.innerHTML = '';
    if (builder && hasRows) {
      panel.tableContainer.appendChild(builder(dataset.items));
    }

    const totalPages = Math.max(1, Math.ceil(Math.max(dataset.total, 1) / dataset.limit));
    const currentPage = Math.min(totalPages, Math.floor(dataset.skip / dataset.limit) + 1);
    if (panel.pageLabel) {
      panel.pageLabel.textContent = `Page ${currentPage} / ${totalPages}`;
    }
    if (panel.prevButton) {
      panel.prevButton.disabled = currentPage <= 1;
      panel.prevButton.classList.toggle('opacity-40', currentPage <= 1);
    }
    if (panel.nextButton) {
      panel.nextButton.disabled = currentPage >= totalPages;
      panel.nextButton.classList.toggle('opacity-40', currentPage >= totalPages);
    }
  }

  function buildModerationUsersTable(items) {
    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-slate-800/60 text-left text-sm text-slate-200';
    table.innerHTML = `
      <thead>
        <tr class="text-xs uppercase tracking-wider text-slate-400">
          <th class="px-4 py-2 font-medium">User</th>
          <th class="px-4 py-2 font-medium">Stats</th>
          <th class="px-4 py-2 font-medium">Role</th>
          <th class="px-4 py-2 font-medium text-right">Actions</th>
        </tr>
      </thead>
    `;
    const body = document.createElement('tbody');
    items.forEach(user => {
      const row = document.createElement('tr');
      row.className = 'border-b border-slate-800/60 last:border-0';
      const canEditRole = state.moderation.viewerRole === 'owner' && state.moderation.viewerId !== user.id;
      row.innerHTML = `
        <td class="px-4 py-3">
          <div class="flex items-center gap-3">
            <img src="${escapeHtml(user.avatar_url || DEFAULT_AVATAR)}" alt="avatar" class="h-10 w-10 rounded-full border border-slate-800/70 object-cover" />
            <div>
              <p class="font-semibold text-white">${escapeHtml(user.username ? `@${user.username}` : 'Unknown')}</p>
              <p class="text-xs text-slate-400">${escapeHtml(user.display_name || '—')}</p>
              <p class="text-[11px] text-slate-500">${escapeHtml(user.email || 'No email')}</p>
            </div>
          </div>
        </td>
        <td class="px-4 py-3 text-sm text-slate-300">
          <div>Posts: ${Number(user.post_count || 0).toLocaleString()}</div>
          <div>Media: ${Number(user.media_count || 0).toLocaleString()}</div>
          <div>Joined: ${user.created_at ? formatDate(user.created_at) : '—'}</div>
        </td>
        <td class="px-4 py-3">
          ${canEditRole ? `
            <select class="w-full rounded-2xl border border-slate-700/70 bg-slate-950/70 px-3 py-1 text-sm font-medium text-slate-100 focus:border-indigo-500/60 focus:outline-none" data-mod-role-select="true" data-user-id="${user.id}" data-previous-role="${(user.role || 'user').toLowerCase()}">
              ${buildRoleOptions((user.role || 'user').toLowerCase())}
            </select>
          ` : `${renderRoleBadgeHtml(user.role, { includeUser: true }) || '<span class="text-slate-500 text-xs">User</span>'}`}
        </td>
        <td class="px-4 py-3 text-right">
          <div class="flex flex-wrap items-center justify-end gap-2">
            <button type="button" class="rounded-full border border-slate-700/70 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-indigo-500/60" data-mod-action="view-user" data-user-id="${user.id}">View</button>
            ${state.moderation.viewerRole === 'owner' && state.moderation.viewerId !== user.id ? `<button type="button" class="rounded-full border border-rose-500/40 px-3 py-1 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/10" data-mod-action="delete-user" data-user-id="${user.id}">Delete</button>` : ''}
          </div>
        </td>
      `;
      body.appendChild(row);
    });
    table.appendChild(body);
    return table;
  }

  function buildModerationPostsTable(items) {
    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-slate-800/60 text-left text-sm text-slate-200';
    table.innerHTML = `
      <thead>
        <tr class="text-xs uppercase tracking-wider text-slate-400">
          <th class="px-4 py-2 font-medium">Author</th>
          <th class="px-4 py-2 font-medium">Caption</th>
          <th class="px-4 py-2 font-medium">Engagement</th>
          <th class="px-4 py-2 font-medium text-right">Actions</th>
        </tr>
      </thead>
    `;
    const body = document.createElement('tbody');
    items.forEach(post => {
      const row = document.createElement('tr');
      row.className = 'border-b border-slate-800/60 last:border-0';
      row.innerHTML = `
        <td class="px-4 py-3">
          <div class="flex flex-col gap-1">
            <span class="font-semibold text-white">${escapeHtml(post.username ? `@${post.username}` : 'Unknown')}</span>
            <span class="text-xs text-slate-400">${escapeHtml(post.display_name || 'No display')}</span>
            ${renderRoleBadgeHtml(post.role, { includeUser: true })}
          </div>
        </td>
        <td class="px-4 py-3 text-sm text-slate-200">
          ${escapeHtml(truncateText(post.caption || '', 200))}
          ${post.media_url ? `<div class="mt-2 text-xs text-indigo-300">Media attached</div>` : ''}
        </td>
        <td class="px-4 py-3 text-sm text-slate-300">
          <div>👍 ${Number(post.like_count || 0).toLocaleString()}</div>
          <div>👎 ${Number(post.dislike_count || 0).toLocaleString()}</div>
          <div>💬 ${Number(post.comment_count || 0).toLocaleString()}</div>
        </td>
        <td class="px-4 py-3 text-right">
          <div class="flex flex-wrap items-center justify-end gap-2">
            <button type="button" class="rounded-full border border-slate-700/70 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-indigo-500/60" data-mod-action="view-post" data-post-id="${post.id}">Preview</button>
            ${hasModeratorPrivileges(state.moderation.viewerRole) ? `<button type="button" class="rounded-full border border-rose-500/40 px-3 py-1 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/10" data-mod-action="delete-post" data-post-id="${post.id}">Delete</button>` : ''}
          </div>
        </td>
      `;
      body.appendChild(row);
    });
    table.appendChild(body);
    return table;
  }

  function buildModerationMediaTable(items) {
    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-slate-800/60 text-left text-sm text-slate-200';
    table.innerHTML = `
      <thead>
        <tr class="text-xs uppercase tracking-wider text-slate-400">
          <th class="px-4 py-2 font-medium">Preview</th>
          <th class="px-4 py-2 font-medium">Owner</th>
          <th class="px-4 py-2 font-medium">Engagement</th>
          <th class="px-4 py-2 font-medium text-right">Actions</th>
        </tr>
      </thead>
    `;
    const body = document.createElement('tbody');
    items.forEach(asset => {
      const isImage = (asset.content_type || '').startsWith('image/');
      const row = document.createElement('tr');
      row.className = 'border-b border-slate-800/60 last:border-0';
      row.innerHTML = `
        <td class="px-4 py-3">
          <div class="flex items-center gap-3">
            ${isImage ? `<img src="${escapeHtml(asset.url)}" alt="media" class="h-16 w-16 rounded-2xl border border-slate-800/70 object-cover" />` : '<div class="flex h-16 w-16 items-center justify-center rounded-2xl border border-slate-800/70 bg-slate-900/70 text-lg">🎞</div>'}
            <div>
              <p class="text-xs text-slate-400">${escapeHtml(asset.content_type || 'Unknown type')}</p>
              <p class="text-[11px] text-slate-500">${escapeHtml(asset.key || asset.url || '')}</p>
            </div>
          </div>
        </td>
        <td class="px-4 py-3">
          <div class="flex flex-col gap-1">
            <span class="font-semibold text-white">${escapeHtml(asset.username ? `@${asset.username}` : 'Unknown')}</span>
            <span class="text-xs text-slate-400">${escapeHtml(asset.display_name || 'No display')}</span>
            ${renderRoleBadgeHtml(asset.role, { includeUser: true })}
          </div>
        </td>
        <td class="px-4 py-3 text-sm text-slate-300">
          <div>👍 ${Number(asset.like_count || 0).toLocaleString()}</div>
          <div>👎 ${Number(asset.dislike_count || 0).toLocaleString()}</div>
          <div>💬 ${Number(asset.comment_count || 0).toLocaleString()}</div>
        </td>
        <td class="px-4 py-3 text-right">
          <div class="flex flex-wrap items-center justify-end gap-2">
            <button type="button" class="rounded-full border border-slate-700/70 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-indigo-500/60" data-mod-action="view-media" data-asset-id="${asset.id}">Preview</button>
            ${hasModeratorPrivileges(state.moderation.viewerRole) ? `<button type="button" class="rounded-full border border-rose-500/40 px-3 py-1 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/10" data-mod-action="delete-media" data-asset-id="${asset.id}">Delete</button>` : ''}
          </div>
        </td>
      `;
      body.appendChild(row);
    });
    table.appendChild(body);
    return table;
  }

  async function loadModerationDashboard(options = {}) {
    const { silent = false } = options;
    const loadingNode = document.getElementById('moderation-loading');
    const errorNode = document.getElementById('moderation-error');
    if (!silent && loadingNode) {
      loadingNode.classList.remove('hidden');
    }
    if (errorNode) {
      errorNode.classList.add('hidden');
    }
    try {
      const dashboard = await apiFetch('/moderation/dashboard');
      state.moderation.dashboard = dashboard;
      renderModerationStats(dashboard.stats || {});
      renderModerationUsers(dashboard.recent_users || []);
      renderModerationPosts(dashboard.recent_posts || []);
    } catch (error) {
      if (errorNode && !silent) {
        errorNode.textContent = error.message || 'Unable to load moderation data.';
        errorNode.classList.remove('hidden');
      } else {
        showToast(error.message || 'Unable to load moderation data.', 'error');
      }
    } finally {
      if (!silent && loadingNode) {
        loadingNode.classList.add('hidden');
      }
    }
  }

  function renderModerationStats(stats = {}) {
    const mapping = {
      'total-users': stats.total_users ?? 0,
      'active-last-24h': stats.active_last_24h ?? 0,
      'total-posts': stats.total_posts ?? 0,
      'total-media-assets': stats.total_media_assets ?? 0,
    };
    Object.entries(mapping).forEach(([key, value]) => {
      const node = document.querySelector(`[data-moderation-stat="${key}"]`);
      if (node) {
        node.textContent = Number(value).toLocaleString();
      }
    });
  }

  function renderModerationUsers(users = []) {
    const body = document.getElementById('moderation-user-body');
    const empty = document.getElementById('moderation-users-empty');
    if (!body) return;
    body.innerHTML = '';
    if (!users.length) {
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');
    users.forEach(user => {
      body.appendChild(buildModerationUserRow(user));
    });
  }

  function buildModerationUserRow(user) {
    const row = document.createElement('tr');
    row.className = 'border-b border-slate-800/60 last:border-0';
    row.dataset.userId = user.id;

    const identityCell = document.createElement('td');
    identityCell.className = 'px-4 py-3 align-top text-sm';
    const identityWrapper = document.createElement('div');
    identityWrapper.className = 'flex flex-col gap-1';
    const username = document.createElement('span');
    username.className = 'font-semibold text-white';
    username.textContent = user.username ? `@${user.username}` : 'Unknown user';
    const displayName = document.createElement('span');
    displayName.className = 'text-xs text-slate-400';
    displayName.textContent = user.display_name || 'No display name';
    identityWrapper.appendChild(username);
    identityWrapper.appendChild(displayName);
    const emailBadge = document.createElement('span');
    emailBadge.className = `mt-2 inline-flex max-w-max items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
      user.email_verified ? 'border border-emerald-500/40 bg-emerald-500/10 text-emerald-200' : 'border border-amber-400/40 bg-amber-400/10 text-amber-100'
    }`;
    emailBadge.textContent = user.email_verified ? 'Email verified' : 'Verification pending';
    identityWrapper.appendChild(emailBadge);
    identityCell.appendChild(identityWrapper);
    row.appendChild(identityCell);

    const roleCell = document.createElement('td');
    roleCell.className = 'px-4 py-3 align-middle';
    roleCell.appendChild(createRoleBadge(user.role));
    row.appendChild(roleCell);

    const postsCell = document.createElement('td');
    postsCell.className = 'px-4 py-3 text-center text-sm text-slate-200';
    postsCell.textContent = Number(user.post_count || 0).toLocaleString();
    row.appendChild(postsCell);

    const activityCell = document.createElement('td');
    activityCell.className = 'px-4 py-3 text-sm text-slate-300';
    activityCell.textContent = user.last_active_at ? formatDate(user.last_active_at) : '—';
    row.appendChild(activityCell);

    const controlsCell = document.createElement('td');
    controlsCell.className = 'px-4 py-3 text-right';
    if (state.moderation.viewerRole === 'owner') {
      const select = document.createElement('select');
      select.className = 'rounded-2xl border border-slate-700/70 bg-slate-950/70 px-3 py-1 text-sm font-medium text-slate-100 transition hover:border-indigo-500/60';
      select.dataset.modRoleSelect = 'true';
      select.dataset.userId = user.id;
      select.dataset.previousRole = (user.role || 'user').toLowerCase();
      ['owner', 'admin', 'user'].forEach(roleValue => {
        const option = document.createElement('option');
        option.value = roleValue;
        option.textContent = formatRoleLabel(roleValue);
        if (roleValue === select.dataset.previousRole) {
          option.selected = true;
        }
        select.appendChild(option);
      });
      if (state.moderation.viewerId === user.id) {
        select.disabled = true;
        select.title = 'You cannot change your own role here';
      }
      controlsCell.appendChild(select);
    } else {
      const note = document.createElement('span');
      note.className = 'text-xs text-slate-500';
      note.textContent = 'View only';
      controlsCell.appendChild(note);
    }
    row.appendChild(controlsCell);

    return row;
  }

  function renderModerationPosts(posts = []) {
    const body = document.getElementById('moderation-post-body');
    const empty = document.getElementById('moderation-posts-empty');
    if (!body) return;
    body.innerHTML = '';
    if (!posts.length) {
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');
    posts.forEach(post => {
      body.appendChild(buildModerationPostRow(post));
    });
  }

  function buildModerationPostRow(post) {
    const row = document.createElement('tr');
    row.className = 'border-b border-slate-800/60 last:border-0';
    row.dataset.postId = post.id;

    const authorCell = document.createElement('td');
    authorCell.className = 'px-4 py-3 align-top';
    const authorWrapper = document.createElement('div');
    authorWrapper.className = 'flex flex-col gap-1';
    const username = document.createElement('span');
    username.className = 'font-semibold text-white';
    username.textContent = post.username ? `@${post.username}` : 'Unknown user';
    const displayName = document.createElement('span');
    displayName.className = 'text-xs text-slate-400';
    displayName.textContent = post.display_name || 'No display name';
    authorWrapper.appendChild(username);
    authorWrapper.appendChild(displayName);
    authorWrapper.appendChild(createRoleBadge(post.role));
    authorCell.appendChild(authorWrapper);
    row.appendChild(authorCell);

    const captionCell = document.createElement('td');
    captionCell.className = 'max-w-xl px-4 py-3 text-sm text-slate-200';
    const captionText = document.createElement('p');
    captionText.textContent = truncateText(post.caption || '', 200);
    captionCell.appendChild(captionText);
    if (post.media_url) {
      const mediaLink = document.createElement('a');
      mediaLink.href = post.media_url;
      mediaLink.target = '_blank';
      mediaLink.rel = 'noopener';
      mediaLink.className = 'mt-2 inline-flex items-center gap-2 text-xs font-semibold text-indigo-300 hover:text-indigo-200';
      mediaLink.textContent = 'View media';
      captionCell.appendChild(mediaLink);
    }
    row.appendChild(captionCell);

    const metricsCell = document.createElement('td');
    metricsCell.className = 'px-4 py-3 text-sm text-slate-300';
    metricsCell.innerHTML = `
      <div>👍 ${post.like_count ?? 0}</div>
      <div>👎 ${post.dislike_count ?? 0}</div>
      <div>💬 ${post.comment_count ?? 0}</div>
    `;
    row.appendChild(metricsCell);

    const actionsCell = document.createElement('td');
    actionsCell.className = 'px-4 py-3 text-right';
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.dataset.modDeletePost = 'true';
    deleteButton.dataset.postId = post.id;
    deleteButton.className = 'rounded-full border border-rose-500/40 px-4 py-1.5 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/10';
    deleteButton.textContent = 'Delete';
    actionsCell.appendChild(deleteButton);
    row.appendChild(actionsCell);

    return row;
  }

  async function handleModerationRoleChange(select) {
    if (!select) return;
    const userId = select.dataset.userId;
    if (!userId) return;
    const previousRole = select.dataset.previousRole || 'user';
    const nextRole = select.value;
    if (!nextRole || previousRole === nextRole) return;
    select.disabled = true;
    try {
      await apiFetch(`/moderation/users/${encodeURIComponent(userId)}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role: nextRole })
      });
      select.dataset.previousRole = nextRole;
      showToast('Role updated successfully.', 'success');
      await loadModerationDashboard({ silent: true });
    } catch (error) {
      select.value = previousRole;
      showToast(error.message || 'Unable to update role.', 'error');
    } finally {
      select.disabled = false;
    }
  }

  async function handleModerationPostDelete(postId, button) {
    if (!postId) return;
    const confirmed = await showModerationConfirm({
      title: 'Delete post?',
      message: 'This will remove the post and any attached media asset.',
      confirmLabel: 'Delete post',
    });
    if (!confirmed) return;
    toggleInteractiveState(button, true);
    try {
      await apiFetch(`/moderation/posts/${encodeURIComponent(postId)}`, {
        method: 'DELETE'
      });
      showToast('Post removed successfully.', 'success');
      await loadModerationDashboard({ silent: true });
      if (state.moderation.activeDataset === 'posts') {
        await loadModerationDataset('posts');
      }
    } catch (error) {
      showToast(error.message || 'Unable to delete post.', 'error');
    } finally {
      toggleInteractiveState(button, false);
    }
  }

  async function openModerationUserDetail(userId) {
    if (!userId) return;
    showModerationDetailModal({
      title: 'User details',
      label: 'Profile review',
      body: '<p class="text-center text-slate-400">Loading profile…</p>',
    });
    try {
      const detail = await apiFetch(`/moderation/users/${encodeURIComponent(userId)}`);
      populateModerationUserDetail(detail);
    } catch (error) {
      showModerationDetailModal({
        title: 'User details',
        label: 'Profile review',
        body: `<p class="text-center text-rose-200">${escapeHtml(error.message || 'Unable to load profile.')}</p>`,
      });
    }
  }

  function populateModerationUserDetail(detail) {
    const modal = state.moderation.modal;
    if (!modal.body) return;
    const isOwner = state.moderation.viewerRole === 'owner';
    const disabledAttr = isOwner ? '' : 'disabled';
    const canEditRole = isOwner && state.moderation.viewerId !== detail.id;
    modal.body.innerHTML = `
      <div class="flex flex-col gap-4 md:flex-row md:items-start">
        <img src="${escapeHtml(detail.avatar_url || DEFAULT_AVATAR)}" alt="avatar" class="h-24 w-24 rounded-3xl border border-slate-800/70 object-cover" />
        <div class="flex-1 space-y-2">
          <p class="text-lg font-semibold text-white">${escapeHtml(detail.username ? `@${detail.username}` : 'Unknown user')}</p>
          <p class="text-sm text-slate-400">${escapeHtml(detail.display_name || 'No display name')}</p>
          <div class="text-xs text-slate-400">${renderRoleBadgeHtml(detail.role, { includeUser: true })}</div>
          <div class="grid grid-cols-2 gap-3 text-sm text-slate-300">
            <div class="rounded-2xl border border-slate-800/60 px-3 py-2">Posts<br><span class="text-lg font-semibold text-white">${Number(detail.post_count || 0).toLocaleString()}</span></div>
            <div class="rounded-2xl border border-slate-800/60 px-3 py-2">Media<br><span class="text-lg font-semibold text-white">${Number(detail.media_count || 0).toLocaleString()}</span></div>
            <div class="rounded-2xl border border-slate-800/60 px-3 py-2">Followers<br><span class="text-lg font-semibold text-white">${Number(detail.follower_count || 0).toLocaleString()}</span></div>
            <div class="rounded-2xl border border-slate-800/60 px-3 py-2">Following<br><span class="text-lg font-semibold text-white">${Number(detail.following_count || 0).toLocaleString()}</span></div>
          </div>
          ${isOwner ? `
            <div class="rounded-2xl border border-slate-800/60 bg-slate-950/60 px-4 py-3">
              <label class="block text-sm font-semibold text-slate-200">Role
                <select class="mt-1 w-full rounded-2xl border border-slate-700/70 bg-slate-950/70 px-3 py-2 text-sm font-medium text-slate-100 focus:border-indigo-500/60 focus:outline-none" data-mod-role-select="true" data-user-id="${detail.id}" data-previous-role="${(detail.role || 'user').toLowerCase()}" ${canEditRole ? '' : 'disabled title="You cannot change your own role"'}>
                  ${buildRoleOptions((detail.role || 'user').toLowerCase())}
                </select>
              </label>
              ${!canEditRole ? '<p class="mt-2 text-xs text-slate-500">You cannot change your own role.</p>' : ''}
            </div>
          ` : ''}
        </div>
      </div>
      <form data-user-edit-form class="mt-6 space-y-4">
        <div class="grid gap-4 md:grid-cols-2">
          ${buildModerationTextInput('Display name', 'display_name', detail.display_name, disabledAttr)}
          ${buildModerationTextInput('Avatar URL', 'avatar_url', detail.avatar_url, disabledAttr)}
          ${buildModerationTextInput('Email', 'email', detail.email, disabledAttr)}
          ${buildModerationTextInput('Location', 'location', detail.location, disabledAttr)}
          ${buildModerationTextInput('Website', 'website', detail.website, disabledAttr)}
        </div>
        <label class="block text-sm font-semibold text-slate-200">Bio
          <textarea name="bio" class="mt-1 w-full rounded-2xl border border-slate-800/70 bg-slate-950/60 p-3 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500/60 focus:outline-none" rows="4" ${disabledAttr}>${escapeHtml(detail.bio || '')}</textarea>
        </label>
        <div class="flex flex-col gap-3 text-sm text-slate-300 md:flex-row md:items-center">
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" name="allow_friend_requests" class="h-4 w-4 rounded border-slate-700/70 bg-transparent" ${detail.allow_friend_requests ? 'checked' : ''} ${disabledAttr} />
            Allow friend requests
          </label>
          <label class="inline-flex items-center gap-2">
            <input type="checkbox" name="dm_followers_only" class="h-4 w-4 rounded border-slate-700/70 bg-transparent" ${detail.dm_followers_only ? 'checked' : ''} ${disabledAttr} />
            DMs require following
          </label>
        </div>
        ${isOwner ? `
          <div class="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
            <button type="button" class="rounded-2xl border border-rose-500/40 px-4 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/10" data-user-delete>Delete account</button>
            <button type="submit" class="rounded-2xl border border-indigo-500/40 bg-indigo-500/10 px-6 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/20">Save changes</button>
          </div>
        ` : '<p class="rounded-2xl border border-slate-800/60 bg-slate-950/60 px-4 py-3 text-center text-sm text-slate-400">Only owners can edit profiles.</p>'}
      </form>
    `;
    attachModerationUserDetailEvents(detail);
  }

  function buildModerationTextInput(label, name, value, disabledAttr) {
    return `
      <label class="block text-sm font-semibold text-slate-200">${escapeHtml(label)}
        <input name="${name}" value="${escapeHtml(value || '')}" class="mt-1 w-full rounded-2xl border border-slate-800/70 bg-slate-950/60 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500/60 focus:outline-none" ${disabledAttr} />
      </label>
    `;
  }

  function buildRoleOptions(selectedRole) {
    const normalized = (selectedRole || 'user').toLowerCase();
    const editableRoles = ['admin', 'user'];
    if (normalized === 'owner' && !editableRoles.includes('owner')) {
      editableRoles.unshift('owner');
    }
    return editableRoles
      .map(role => `<option value="${role}" ${role === normalized ? 'selected' : ''} ${role === 'owner' ? 'disabled' : ''}>${formatRoleLabel(role)}</option>`)
      .join('');
  }

  function attachModerationUserDetailEvents(detail) {
    const modal = state.moderation.modal;
    if (!modal.body) return;
    const form = modal.body.querySelector('[data-user-edit-form]');
    if (form && state.moderation.viewerRole === 'owner') {
      form.addEventListener('submit', event => handleModerationUserUpdate(event, detail.id));
    }
    const deleteBtn = modal.body.querySelector('[data-user-delete]');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', () => handleModerationUserDelete(detail.id, deleteBtn));
    }
    const roleSelect = modal.body.querySelector('[data-mod-role-select]');
    if (roleSelect && state.moderation.viewerRole === 'owner') {
      roleSelect.addEventListener('change', () => handleModerationRoleChange(roleSelect));
    }
  }

  async function handleModerationUserUpdate(event, userId) {
    event.preventDefault();
    if (state.moderation.viewerRole !== 'owner') {
      showToast('Only owners can update profiles.', 'warning');
      return;
    }
    const form = event.currentTarget;
    const submitButton = form.querySelector('button[type="submit"]');
    const formData = new FormData(form);
    const payload = {};
    ['display_name', 'avatar_url', 'email', 'location', 'website', 'bio'].forEach(field => {
      const value = (formData.get(field) || '').toString();
      payload[field] = value.trim() ? value.trim() : null;
    });
    payload.allow_friend_requests = formData.get('allow_friend_requests') === 'on';
    payload.dm_followers_only = formData.get('dm_followers_only') === 'on';
    toggleInteractiveState(submitButton, true);
    try {
      const updated = await apiFetch(`/moderation/users/${encodeURIComponent(userId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      showToast('Profile updated.', 'success');
      populateModerationUserDetail(updated);
      if (state.moderation.activeDataset === 'users') {
        await loadModerationDataset('users');
      }
      await loadModerationDashboard({ silent: true });
    } catch (error) {
      showToast(error.message || 'Unable to update profile.', 'error');
    } finally {
      toggleInteractiveState(submitButton, false);
    }
  }

  async function handleModerationUserDelete(userId, button) {
    if (state.moderation.viewerRole !== 'owner') {
      showToast('Only owners can delete accounts.', 'warning');
      return;
    }
    if (state.moderation.viewerId === userId) {
      showToast('You cannot delete your own account.', 'warning');
      return;
    }
    const confirmed = await showModerationConfirm({
      title: 'Delete account?',
      message: 'This permanently removes the user, their posts, and media.',
      confirmLabel: 'Delete account',
    });
    if (!confirmed) return;
    if (button) toggleInteractiveState(button, true);
    try {
      await apiFetch(`/moderation/users/${encodeURIComponent(userId)}`, { method: 'DELETE' });
      showToast('User removed.', 'success');
      hideModerationDetailModal();
      if (state.moderation.activeDataset === 'users') {
        await loadModerationDataset('users');
      }
      await loadModerationDashboard({ silent: true });
    } catch (error) {
      showToast(error.message || 'Unable to delete user.', 'error');
    } finally {
      if (button) toggleInteractiveState(button, false);
    }
  }

  async function openModerationPostDetail(postId) {
    if (!postId) return;
    showModerationDetailModal({
      title: 'Post preview',
      label: 'Content inspection',
      body: '<p class="text-center text-slate-400">Loading post…</p>',
    });
    try {
      const detail = await apiFetch(`/moderation/posts/${encodeURIComponent(postId)}`);
      populateModerationPostDetail(detail);
    } catch (error) {
      showModerationDetailModal({
        title: 'Post preview',
        label: 'Content inspection',
        body: `<p class="text-center text-rose-200">${escapeHtml(error.message || 'Unable to load post.')}</p>`,
      });
    }
  }

  function populateModerationPostDetail(detail) {
    const modal = state.moderation.modal;
    if (!modal.body) return;
    const canEdit = hasModeratorPrivileges(state.moderation.viewerRole);
    modal.body.innerHTML = `
      <div class="space-y-3">
        <div class="flex items-center gap-3">
          <img src="${escapeHtml(detail.avatar_url || DEFAULT_AVATAR)}" alt="avatar" class="h-12 w-12 rounded-2xl border border-slate-800/70 object-cover" />
          <div>
            <p class="font-semibold text-white">${escapeHtml(detail.username ? `@${detail.username}` : 'Unknown')}</p>
            <p class="text-xs text-slate-400">${escapeHtml(detail.display_name || 'No display')}</p>
            ${renderRoleBadgeHtml(detail.role, { includeUser: true })}
          </div>
        </div>
        <p class="text-sm text-slate-300">Created ${detail.created_at ? formatDate(detail.created_at) : '—'}</p>
        <p class="rounded-2xl border border-slate-800/60 bg-slate-950/60 p-4 text-sm text-slate-100">${escapeHtml(detail.caption || '')}</p>
        ${detail.media_url ? `<a href="${escapeHtml(detail.media_url)}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 rounded-full border border-indigo-500/40 px-3 py-1 text-xs font-semibold text-indigo-200">Open media</a>` : ''}
      </div>
      ${canEdit ? `
        <form data-post-edit-form class="mt-6 space-y-4">
          <label class="block text-sm font-semibold text-slate-200">Caption
            <textarea name="caption" rows="4" class="mt-1 w-full rounded-2xl border border-slate-800/70 bg-slate-950/60 p-3 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500/60 focus:outline-none">${escapeHtml(detail.caption || '')}</textarea>
          </label>
          <label class="block text-sm font-semibold text-slate-200">Attach media asset ID
            <input name="media_asset_id" value="${escapeHtml(detail.media_asset_id || '')}" class="mt-1 w-full rounded-2xl border border-slate-800/70 bg-slate-950/60 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500/60 focus:outline-none" placeholder="Optional MediaAsset UUID" />
          </label>
          <label class="inline-flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" name="remove_media" class="h-4 w-4 rounded border-slate-700/70 bg-transparent" />
            Remove attached media
          </label>
          <div class="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
            <button type="button" class="rounded-2xl border border-rose-500/40 px-4 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/10" data-mod-action="delete-post" data-post-id="${detail.id}">Delete post</button>
            <button type="submit" class="rounded-2xl border border-indigo-500/40 bg-indigo-500/10 px-6 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/20">Save changes</button>
          </div>
        </form>
      ` : '<p class="mt-6 rounded-2xl border border-slate-800/60 bg-slate-950/60 px-4 py-3 text-center text-sm text-slate-400">Only admins or owners can edit posts.</p>'}
    `;
    if (canEdit) {
      const form = modal.body.querySelector('[data-post-edit-form]');
      if (form) {
        form.addEventListener('submit', event => handleModerationPostUpdate(event, detail.id));
      }
      const deleteBtn = modal.body.querySelector('[data-mod-action="delete-post"]');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', event => {
          event.preventDefault();
          handleModerationPostDelete(detail.id, deleteBtn);
        });
      }
    }
  }

  async function handleModerationPostUpdate(event, postId) {
    event.preventDefault();
    if (!hasModeratorPrivileges(state.moderation.viewerRole)) {
      showToast('Only admins or owners can edit posts.', 'warning');
      return;
    }
    const form = event.currentTarget;
    const submitButton = form.querySelector('button[type="submit"]');
    const formData = new FormData(form);
    const payload = {
      caption: ((formData.get('caption') || '').toString()).trim() || null,
      media_asset_id: ((formData.get('media_asset_id') || '').toString()).trim() || null,
      remove_media: formData.get('remove_media') === 'on',
    };
    toggleInteractiveState(submitButton, true);
    try {
      const updated = await apiFetch(`/moderation/posts/${encodeURIComponent(postId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      showToast('Post updated.', 'success');
      populateModerationPostDetail(updated);
      if (state.moderation.activeDataset === 'posts') {
        await loadModerationDataset('posts');
      }
      await loadModerationDashboard({ silent: true });
    } catch (error) {
      showToast(error.message || 'Unable to update post.', 'error');
    } finally {
      toggleInteractiveState(submitButton, false);
    }
  }

  async function openModerationMediaDetail(assetId) {
    if (!assetId) return;
    showModerationDetailModal({
      title: 'Media asset',
      label: 'Library preview',
      body: '<p class="text-center text-slate-400">Loading media…</p>',
    });
    try {
      const detail = await apiFetch(`/moderation/media/${encodeURIComponent(assetId)}`);
      populateModerationMediaDetail(detail);
    } catch (error) {
      showModerationDetailModal({
        title: 'Media asset',
        label: 'Library preview',
        body: `<p class="text-center text-rose-200">${escapeHtml(error.message || 'Unable to load media asset.')}</p>`,
      });
    }
  }

  function populateModerationMediaDetail(detail) {
    const modal = state.moderation.modal;
    if (!modal.body) return;
    const canModerate = hasModeratorPrivileges(state.moderation.viewerRole);
    const isImage = (detail.content_type || '').startsWith('image/');
    modal.body.innerHTML = `
      <div class="space-y-4">
        <div class="rounded-3xl border border-slate-800/70 bg-slate-950/70 p-4">
          ${isImage ? `<img src="${escapeHtml(detail.url)}" alt="media" class="mx-auto max-h-[320px] w-full rounded-2xl object-contain" />` : `<a href="${escapeHtml(detail.url)}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 rounded-full border border-indigo-500/40 px-4 py-2 text-sm font-semibold text-indigo-100">Open asset</a>`}
        </div>
        <div class="grid gap-3 text-sm text-slate-300 md:grid-cols-2">
          <div class="rounded-2xl border border-slate-800/60 px-3 py-2">Owner<br><span class="font-semibold text-white">${escapeHtml(detail.username ? `@${detail.username}` : 'Unknown')}</span></div>
          <div class="rounded-2xl border border-slate-800/60 px-3 py-2">Content type<br><span class="font-semibold text-white">${escapeHtml(detail.content_type || 'Unknown')}</span></div>
          <div class="rounded-2xl border border-slate-800/60 px-3 py-2">Bucket<br><span class="font-semibold text-white">${escapeHtml(detail.bucket || 'n/a')}</span></div>
          <div class="rounded-2xl border border-slate-800/60 px-3 py-2">Key<br><span class="font-mono text-xs text-slate-200">${escapeHtml(detail.key || 'n/a')}</span></div>
        </div>
        ${canModerate ? `
          <div class="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
            <a href="${escapeHtml(detail.url)}" target="_blank" rel="noopener" class="rounded-2xl border border-slate-700/60 px-4 py-2 text-sm font-semibold text-slate-200">Open in new tab</a>
            <button type="button" class="rounded-2xl border border-rose-500/40 px-4 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/10" data-media-delete>Delete asset</button>
          </div>
        ` : ''}
      </div>
    `;
    if (canModerate) {
      const deleteBtn = modal.body.querySelector('[data-media-delete]');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', () => handleModerationMediaDelete(detail.id, deleteBtn));
      }
    }
  }

  async function handleModerationMediaDelete(assetId, button) {
    if (!hasModeratorPrivileges(state.moderation.viewerRole)) {
      showToast('Only admins or owners can delete media.', 'warning');
      return;
    }
    const confirmed = await showModerationConfirm({
      title: 'Delete media asset?',
      message: 'This removes the file from storage and detaches it from posts.',
      confirmLabel: 'Delete media',
    });
    if (!confirmed) return;
    toggleInteractiveState(button, true);
    try {
      await apiFetch(`/moderation/media/${encodeURIComponent(assetId)}`, { method: 'DELETE' });
      showToast('Media deleted.', 'success');
      hideModerationDetailModal();
      if (state.moderation.activeDataset === 'media') {
        await loadModerationDataset('media');
      }
      await loadModerationDashboard({ silent: true });
    } catch (error) {
      showToast(error.message || 'Unable to delete media asset.', 'error');
    } finally {
      toggleInteractiveState(button, false);
    }
  }

  function showModerationDetailModal({ title, label, body }) {
    const modal = state.moderation.modal;
    if (!modal.root) return;
    const wasHidden = modal.root.classList.contains('hidden');
    if (modal.title && title) modal.title.textContent = title;
    if (modal.label && label) modal.label.textContent = label;
    if (modal.body && body !== undefined) modal.body.innerHTML = body;
    modal.root.classList.remove('hidden');
    if (wasHidden) {
      lockBodyScroll();
    }
  }

  function hideModerationDetailModal() {
    const modal = state.moderation.modal;
    if (modal.root && !modal.root.classList.contains('hidden')) {
      modal.root.classList.add('hidden');
      unlockBodyScroll();
    }
  }

  function showModerationConfirm(options) {
    const confirm = state.moderation.confirm;
    if (!confirm.root || !confirm.accept || !confirm.cancel || !confirm.title || !confirm.message) {
      const fallback = window.confirm(options.message || 'Are you sure?');
      return Promise.resolve(fallback);
    }
    confirm.title.textContent = options.title || 'Confirm action';
    confirm.message.textContent = options.message || 'Are you sure?';
    confirm.accept.textContent = options.confirmLabel || 'Confirm';
    const wasHidden = confirm.root.classList.contains('hidden');
    confirm.root.classList.remove('hidden');
    if (wasHidden) {
      lockBodyScroll();
    }
    return new Promise(resolve => {
      confirm.resolver = resolve;
      confirm.accept.onclick = () => finalizeModerationConfirm(true);
      confirm.cancel.onclick = () => finalizeModerationConfirm(false);
    });
  }

  function finalizeModerationConfirm(result) {
    const confirm = state.moderation.confirm;
    if (!confirm.resolver) return;
    if (!confirm.root.classList.contains('hidden')) {
      confirm.root.classList.add('hidden');
      unlockBodyScroll();
    }
    const resolver = confirm.resolver;
    confirm.resolver = null;
    confirm.accept.onclick = null;
    confirm.cancel.onclick = null;
    resolver(result);
  }

  // -----------------------------------------------------------------------
  // Inline AI Chat Widget
  // -----------------------------------------------------------------------

  let aiChatHistory = [];
  let aiCurrentMode = 'default';
  let aiConfirmedAdult = false;
  let aiChatSending = false;

  const aiChatElements = {
    container: null,
    log: null,
    input: null,
    send: null,
    modeSelect: null,
    confirmCheckbox: null,
  };

  function initInlineAiChat() {
    aiChatElements.container = document.getElementById('ai-chat-container');
    aiChatElements.log = document.getElementById('ai-chat-log');
    aiChatElements.input = document.getElementById('ai-chat-input');
    aiChatElements.send = document.getElementById('ai-chat-send');
    aiChatElements.modeSelect = document.getElementById('ai-mode-select');
    aiChatElements.confirmCheckbox = document.getElementById('ai-confirm-adult');

    if (!aiChatElements.container || !aiChatElements.input || !aiChatElements.send || !aiChatElements.log) {
      return;
    }

    if (aiChatElements.modeSelect) {
      aiCurrentMode = aiChatElements.modeSelect.value || aiCurrentMode;
      aiChatElements.modeSelect.addEventListener('change', () => {
        aiCurrentMode = aiChatElements.modeSelect.value || 'default';
      });
    }

    if (aiChatElements.confirmCheckbox) {
      aiConfirmedAdult = aiChatElements.confirmCheckbox.checked;
      aiChatElements.confirmCheckbox.addEventListener('change', () => {
        aiConfirmedAdult = aiChatElements.confirmCheckbox.checked;
      });
    }

    aiChatElements.send.addEventListener('click', handleInlineAiSend);
    aiChatElements.input.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleInlineAiSend();
      }
    });
  }

  async function sendInlineAiChatMessage(message) {
    const payload = {
      message,
      mode: aiCurrentMode,
      history: aiChatHistory,
      confirmed_adult: aiConfirmedAdult,
    };

    const response = await fetch('/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let errDetail = 'AI request failed.';
      try {
        const err = await response.json();
        if (err && typeof err === 'object') {
          if (typeof err.message === 'string') {
            errDetail = err.message;
          } else if (err.detail) {
            if (typeof err.detail === 'string') {
              errDetail = err.detail;
            } else if (typeof err.detail.message === 'string') {
              errDetail = err.detail.message;
            }
          }
        }
      } catch {
        // Ignore JSON parse errors and use default message
      }
      throw new Error(errDetail);
    }

    const data = await response.json();
    return data.reply;
  }

  function renderInlineAiMessage(role, content) {
    if (!aiChatElements.log) return;
    if (aiChatElements.log.dataset.aiFilled !== 'true') {
      aiChatElements.log.innerHTML = '';
      aiChatElements.log.dataset.aiFilled = 'true';
    }
    const wrapper = document.createElement('div');
    wrapper.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'}`;
    const bubble = document.createElement('div');
    const base = 'max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-lg shadow-black/20';
    if (role === 'user') {
      bubble.className = `${base} bg-indigo-500/20 text-indigo-50`;
    } else {
      bubble.className = `${base} bg-slate-800/80 text-slate-100`;
    }
    bubble.textContent = content;
    wrapper.appendChild(bubble);
    aiChatElements.log.appendChild(wrapper);
    aiChatElements.log.scrollTop = aiChatElements.log.scrollHeight;
  }

  function setInlineAiSending(sending) {
    aiChatSending = Boolean(sending);
    if (aiChatElements.send) {
      aiChatElements.send.disabled = aiChatSending;
      aiChatElements.send.classList.toggle('opacity-60', aiChatSending);
    }
  }

  async function handleInlineAiSend() {
    if (aiChatSending) return;
    const text = (aiChatElements.input?.value || '').trim();
    if (!text) return;

    aiChatHistory.push({ role: 'user', content: text });
    renderInlineAiMessage('user', text);
    aiChatElements.input.value = '';
    setInlineAiSending(true);

    try {
      const reply = await sendInlineAiChatMessage(text);
      aiChatHistory.push({ role: 'assistant', content: reply });
      renderInlineAiMessage('assistant', reply);
    } catch (error) {
      const message = error?.message || 'Sorry, the AI is unavailable right now.';
      renderInlineAiMessage('assistant', message);
    } finally {
      setInlineAiSending(false);
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
    initModerationPage,
  };

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const panelRoot = state.moderation.panel.root;
    if (panelRoot && !panelRoot.classList.contains('hidden')) {
      toggleModerationDatasetPanel(false);
    }
    const detailRoot = state.moderation.modal.root;
    if (detailRoot && !detailRoot.classList.contains('hidden')) {
      hideModerationDetailModal();
    }
    const confirmRoot = state.moderation.confirm.root;
    if (confirmRoot && !confirmRoot.classList.contains('hidden')) {
      finalizeModerationConfirm(false);
    }
    const socialOverlay = state.socialAi.elements.root;
    if (socialOverlay && !socialOverlay.classList.contains('hidden')) {
      closeSocialAi();
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    initThemeToggle();
    initSocialAi();
    initInlineAiChat();
  });
})();
