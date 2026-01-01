/**
 * Privacy-first analytics tracker for supasuge.com
 *
 * - Respects Do Not Track (DNT)
 * - Visitor ID stored in a cookie (stable across site)
 *   - Generated as SHA256(random_bytes) hex
 * - Session ID stored in sessionStorage (per-tab)
 * - Tracks pageviews + heartbeat time-on-page
 */

(function () {
  'use strict';

  const DEBUG = false;

  function log(...args) { if (DEBUG) console.log('[Analytics]', ...args); }
  function warn(...args) { if (DEBUG) console.warn('[Analytics]', ...args); }

  function isDNTEnabled() {
    const dnt = navigator.doNotTrack || window.doNotTrack || navigator.msDoNotTrack;
    return dnt === '1' || dnt === 'yes';
  }

  if (isDNTEnabled()) {
    log('Do Not Track enabled - tracking disabled');
    return;
  }

  function getCookie(name) {
    const needle = name + '=';
    const parts = document.cookie.split(';');
    for (const part of parts) {
      const s = part.trim();
      if (s.startsWith(needle)) return decodeURIComponent(s.substring(needle.length));
    }
    return null;
  }

  function setCookie(name, value, days) {
    const maxAge = Math.floor(days * 24 * 60 * 60);
    const secure = window.location.protocol === 'https:' ? '; Secure' : '';
    // Lax is fine for a normal site; Strict can break legit nav flows.
    document.cookie =
      `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; SameSite=Lax${secure}`;
  }

  function bytesToHex(bytes) {
    let out = '';
    for (const b of bytes) out += b.toString(16).padStart(2, '0');
    return out;
  }

  async function sha256Hex(bytes) {
    // WebCrypto digest
    const buf = await crypto.subtle.digest('SHA-256', bytes);
    return bytesToHex(new Uint8Array(buf));
  }

  function uuidish() {
    // Good enough session identifier; doesn't need to be crypto-perfect
    if (window.crypto && window.crypto.getRandomValues) {
      const bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;

      const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
      return (
        hex.slice(0, 8) + '-' +
        hex.slice(8, 12) + '-' +
        hex.slice(12, 16) + '-' +
        hex.slice(16, 20) + '-' +
        hex.slice(20)
      );
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  class AnalyticsTracker {
    constructor() {
      this.visitorCookieName = 'analytics_vid';
      this.sessionKey = 'analytics_session';
      this.apiEndpoint = '/api/track/pageview';
      this.heartbeatEndpoint = '/api/track/heartbeat';

      this.heartbeatInterval = 30000;
      this.heartbeatTimer = null;

      this.startTime = Date.now();
      this.currentPageviewId = null;

      this.visitorId = null;
      this.sessionId = null;
    }

    getScreenDimensions() {
      return {
        width: window.screen ? window.screen.width : null,
        height: window.screen ? window.screen.height : null,
      };
    }

    getPostIdFromDom() {
      const article = document.querySelector('article[data-post-id]');
      if (!article) return null;
      const raw = article.getAttribute('data-post-id');
      if (!raw) return null;
      const n = parseInt(raw, 10);
      return Number.isFinite(n) && n > 0 ? n : null;
    }

    async getOrCreateVisitorId() {
      const existing = getCookie(this.visitorCookieName);
      if (existing && typeof existing === 'string' && existing.length >= 32) {
        return existing;
      }

      // Generate random bytes -> SHA256 hex
      const bytes = new Uint8Array(32);
      crypto.getRandomValues(bytes);
      const vid = await sha256Hex(bytes);

      // Persist for 365 days
      setCookie(this.visitorCookieName, vid, 365);
      return vid;
    }

    getOrCreateSessionId() {
      let sid = sessionStorage.getItem(this.sessionKey);
      if (!sid) {
        sid = uuidish();
        sessionStorage.setItem(this.sessionKey, sid);
        sessionStorage.setItem(this.sessionKey + '_start', Date.now().toString());
      }
      return sid;
    }

    async initIds() {
      this.visitorId = await this.getOrCreateVisitorId();
      this.sessionId = this.getOrCreateSessionId();
      log('Visitor:', this.visitorId);
      log('Session:', this.sessionId);
    }

    async trackPageview() {
      const postId = this.getPostIdFromDom();

      const data = {
        path: window.location.pathname,
        post_id: postId,
        session_id: this.sessionId,
        visitor_id: this.visitorId,
        referrer: document.referrer || null,
        screen: this.getScreenDimensions(),
        user_agent: navigator.userAgent,
        timestamp: new Date().toISOString(),
      };

      try {
        const response = await fetch(this.apiEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
          keepalive: true,
        });

        if (response.ok) {
          const result = await response.json();
          this.currentPageviewId = result.pageview_id;
          log('Pageview tracked:', this.currentPageviewId, 'post_id:', postId);
        } else {
          warn('Failed to track pageview:', response.status);
        }
      } catch (error) {
        warn('Error tracking pageview:', error);
      }
    }

    async sendHeartbeat() {
      if (!this.currentPageviewId) return;

      const timeSpent = Math.floor((Date.now() - this.startTime) / 1000);
      if (!Number.isFinite(timeSpent) || timeSpent < 0) return;

      const payload = {
        pageview_id: this.currentPageviewId,
        time_spent: timeSpent,
      };

      try {
        if (navigator.sendBeacon) {
          const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
          const ok = navigator.sendBeacon(this.heartbeatEndpoint, blob);
          if (ok) return;
        }
      } catch (_) {}

      try {
        await fetch(this.heartbeatEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          keepalive: true,
        });
      } catch (error) {
        warn('Error sending heartbeat:', error);
      }
    }

    startHeartbeat() {
      if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = setInterval(() => this.sendHeartbeat(), this.heartbeatInterval);
    }

    stopHeartbeat() {
      if (this.heartbeatTimer) {
        clearInterval(this.heartbeatTimer);
        this.heartbeatTimer = null;
      }
    }

    async init() {
      await this.initIds();
      await this.trackPageview();
      this.startHeartbeat();

      window.addEventListener('beforeunload', () => {
        this.sendHeartbeat();
        this.stopHeartbeat();
      });

      document.addEventListener('visibilitychange', () => {
        if (document.hidden) this.stopHeartbeat();
        else this.startHeartbeat();
      });
    }
  }

  async function boot() {
    try {
      const tracker = new AnalyticsTracker();
      await tracker.init();
    } catch (e) {
      warn('Tracker init failed:', e);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { boot(); });
  } else {
    boot();
  }
})();
