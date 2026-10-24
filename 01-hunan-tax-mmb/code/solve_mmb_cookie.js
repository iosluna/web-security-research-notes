// 湖南税务 MMB 412 JS 挑战 Cookie 生成器
// stdin JSON: { jsPath, pageUrl, userAgent, cookie }
// stdout JSON: { ok, cookieHeader, writes, reloadCalled, href }
const fs = require('fs');
const vm = require('vm');

function readStdin() {
  return new Promise((resolve) => {
    let buf = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', d => buf += d);
    process.stdin.on('end', () => resolve(buf));
  });
}

function parseCookieString(cookie) {
  const map = new Map();
  String(cookie || '').split(/;\s*/).forEach(p => {
    if (!p) return;
    const i = p.indexOf('=');
    if (i <= 0) return;
    const k = p.slice(0, i).trim();
    const v = p.slice(i + 1).trim();
    if (!/^(path|expires|max-age|domain|samesite|secure|httponly)$/i.test(k)) {
      map.set(k, v);
    }
  });
  return map;
}
function serializeCookieMap(map) {
  return Array.from(map.entries()).map(([k, v]) => `${k}=${v}`).join('; ');
}

function makeCanvas() {
  return {
    width: 300, height: 150, style: {},
    getContext(type) {
      if (type === 'webgl' || type === 'experimental-webgl') return makeWebGL(this);
      return makeCtx2d(this);
    },
    toDataURL() { return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='; },
    addEventListener() {}, removeEventListener() {}, setAttribute() {}, getAttribute() { return null; }
  };
}
function makeCtx2d(canvas) {
  const ctx = {
    canvas,
    fillText() {}, strokeText() {}, fillRect() {}, strokeRect() {}, clearRect() {},
    beginPath() {}, closePath() {}, moveTo() {}, lineTo() {}, arc() {}, rect() {}, fill() {}, stroke() {},
    save() {}, restore() {}, translate() {}, rotate() {}, scale() {}, drawImage() {},
    measureText() { return { width: 42 }; },
    getImageData() { return { data: new Uint8ClampedArray(400) }; },
    putImageData() {}, createImageData() { return { data: new Uint8ClampedArray(400) }; },
    createLinearGradient() { return { addColorStop() {} }; },
    createRadialGradient() { return { addColorStop() {} }; },
    isPointInPath() { return false; },
  };
  return new Proxy(ctx, { get(t, p) { if (p in t) return t[p]; if (typeof p === 'string') return function(){}; } });
}
function makeWebGL(canvas) {
  const gl = {
    canvas,
    getParameter(p) {
      const vals = {
        7936: 'WebKit', 7937: 'WebKit WebGL', 7938: 'WebGL 1.0 (OpenGL ES 2.0 Chromium)',
        35724: 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)',
        3379: 16384, 3386: 32768, 34076: 16384, 34024: 16384,
        36347: 1024, 36348: 30, 34921: 16, 36349: 16, 34930: 16,
      };
      if (p === 37445) return 'Google Inc.';
      if (p === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)';
      return Object.prototype.hasOwnProperty.call(vals, p) ? vals[p] : 0;
    },
    getExtension(name) {
      if (name === 'WEBGL_debug_renderer_info') return { UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446 };
      return {};
    },
    getSupportedExtensions() { return ['WEBGL_debug_renderer_info', 'WEBGL_lose_context']; },
  };
  return new Proxy(gl, { get(t, p) { if (p in t) return t[p]; if (typeof p === 'string') return function(){ return 0; }; } });
}

function runChallenge({ jsPath, pageUrl, userAgent, cookie }) {
  let code = fs.readFileSync(jsPath, 'utf8');
  // 防御性补丁：若新版/Node toString 触发 OB 自防御死循环，内存中去掉该死循环；不修改源 JS 文件。
  code = code.replace(
    'for(var _=0,e=this.fnOvGV.length;_<e;_++)this.fnOvGV.push(Math.round(Math.random())),e=this.fnOvGV.length;return x(this.fnOvGV[0])',
    'return x(this.fnOvGV[0])'
  );

  const cookieMap = parseCookieString(cookie || '');
  const writes = [];
  let reloadCalled = false;
  const urlObj = new URL(pageUrl);

  function setCookie(v) {
    const s = String(v);
    writes.push(s);
    const first = s.split(';')[0];
    const i = first.indexOf('=');
    if (i > 0) cookieMap.set(first.slice(0, i), first.slice(i + 1));
  }

  const document = {
    referrer: '', title: '', characterSet: 'UTF-8', readyState: 'complete',
    domain: urlObj.hostname, URL: pageUrl,
    documentElement: { clientWidth: 1366, clientHeight: 768, style: {}, appendChild(c) { return c; } },
    head: { appendChild(c) { return c; }, removeChild(c) { return c; }, insertBefore(c) { return c; } },
    body: { clientWidth: 1366, clientHeight: 728, appendChild(c) { return c; }, removeChild(c) { return c; }, style: {} },
    createElement(tag) {
      tag = String(tag || '').toLowerCase();
      if (tag === 'canvas') return makeCanvas();
      if (tag === 'iframe') return { style: {}, contentWindow: window, sandbox: '', srcdoc: '', appendChild() {}, removeChild() {} };
      return {
        tagName: tag.toUpperCase(), style: {}, children: [], childNodes: [],
        appendChild(c) { return c; }, removeChild(c) { return c; }, insertBefore(c) { return c; },
        setAttribute(k, v) { this[k] = v; }, getAttribute(k) { return this[k] || null; },
        addEventListener() {}, removeEventListener() {},
        getContext() { return null; }, offsetWidth: 100, offsetHeight: 20,
        innerHTML: '', innerText: '', textContent: '',
      };
    },
    createTextNode(t) { return { textContent: String(t) }; },
    createEvent(type) { return { type, initEvent() {}, preventDefault() {}, stopPropagation() {} }; },
    getElementById() { return null; },
    getElementsByTagName(tag) {
      tag = String(tag || '').toLowerCase();
      if (tag === 'head') return [this.head];
      if (tag === 'body') return [this.body];
      return [];
    },
    getElementsByClassName() { return []; }, querySelector() { return null; }, querySelectorAll() { return []; },
    addEventListener() {}, removeEventListener() {},
  };
  Object.defineProperty(document, 'cookie', { get() { return serializeCookieMap(cookieMap); }, set(v) { setCookie(v); }, configurable: true });

  const location = {
    href: pageUrl, origin: urlObj.origin, protocol: urlObj.protocol, host: urlObj.host, hostname: urlObj.hostname,
    port: urlObj.port, pathname: urlObj.pathname, search: urlObj.search, hash: urlObj.hash,
    reload() { reloadCalled = true; },
    replace(v) { this.href = String(v); reloadCalled = true; },
    assign(v) { this.href = String(v); reloadCalled = true; },
    toString() { return this.href; },
  };
  const plugins = [{ name: 'Chrome PDF Plugin' }, { name: 'Chrome PDF Viewer' }, { name: 'Native Client' }];
  plugins.item = i => plugins[i] || null; plugins.namedItem = n => plugins.find(p => p.name === n) || null; plugins.refresh = () => {};
  const navigator = {
    userAgent, appName: 'Netscape', appCodeName: 'Mozilla', appVersion: '5.0 (Windows NT 10.0; Win64; x64)',
    platform: 'Win32', vendor: 'Google Inc.', productSub: '20030107', language: 'zh-CN', languages: ['zh-CN', 'zh', 'en'],
    cookieEnabled: true, onLine: true, webdriver: false, plugins,
    mimeTypes: [{ type: 'application/pdf' }], hardwareConcurrency: 8, deviceMemory: 8, maxTouchPoints: 0,
    javaEnabled() { return false; }, sendBeacon() { return true; },
    connection: { effectiveType: '4g', rtt: 50, downlink: 10, saveData: false },
  };
  const screen = { width: 1366, height: 768, availWidth: 1366, availHeight: 728, colorDepth: 24, pixelDepth: 24, orientation: { type: 'landscape-primary', angle: 0 } };
  const storage = { getItem() { return null; }, setItem() {}, removeItem() {}, clear() {}, key() { return null; }, length: 0 };
  const history = { length: 1, state: null, back() {}, forward() {}, go() {}, pushState() {}, replaceState() {} };

  const window = {
    document, navigator, location, screen, localStorage: storage, sessionStorage: storage, history,
    innerWidth: 1366, innerHeight: 728, outerWidth: 1366, outerHeight: 768, devicePixelRatio: 1,
    screenX: 0, screenY: 0, screenLeft: 0, screenTop: 0, scrollX: 0, scrollY: 0, pageXOffset: 0, pageYOffset: 0,
    name: '', frames: [], length: 0, closed: false,
    addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; },
    requestAnimationFrame(cb) { return setTimeout(cb, 16); }, cancelAnimationFrame(id) { clearTimeout(id); },
    setTimeout, clearTimeout, setInterval(fn, ms, ...args) { return setTimeout(() => { if (typeof fn === 'function') fn(...args); }, Math.min(ms || 0, 10)); }, clearInterval,
    Date, Math, JSON, Array, Object, String, Number, Boolean, RegExp, Error, TypeError, RangeError,
    Uint8Array, Uint8ClampedArray, Int8Array, Int16Array, Int32Array, Float32Array, Float64Array, ArrayBuffer, DataView,
    Map, Set, WeakMap, WeakSet, Promise, Proxy, Reflect, Symbol,
    btoa(s) { return Buffer.from(String(s), 'binary').toString('base64'); },
    atob(s) { return Buffer.from(String(s), 'base64').toString('binary'); },
    console: { log(){}, warn(){}, error(){}, info(){}, debug(){} },
    performance: { now() { return Date.now() % 100000; }, timing: { navigationStart: Date.now() }, getEntries(){ return []; }, getEntriesByType(){ return []; }, getEntriesByName(){ return []; } },
    XMLHttpRequest: function XMLHttpRequest() {}, Image: function Image() {}, Audio: function Audio() {}, DOMParser: function DOMParser() {},
    getComputedStyle() { return { getPropertyValue() { return ''; } }; },
    matchMedia(q) { return { matches: false, media: String(q || ''), addListener(){}, removeListener(){}, addEventListener(){}, removeEventListener(){}, onchange: null }; },
    open() { return null; }, close() {}, alert() {}, confirm() { return false; }, prompt() { return null; },
    chrome: { runtime: {}, app: {}, loadTimes(){ return {}; }, csi(){ return {}; } },
  };
  window.window = window.self = window.top = window.parent = window.globalThis = window;

  const sandbox = window; // 不使用 Proxy(has=true)，否则会导致该 OB 脚本在全局查找时卡死
  vm.runInNewContext(code, sandbox, { filename: jsPath, timeout: 30000 });
  return { ok: true, cookieHeader: serializeCookieMap(cookieMap), writes, reloadCalled, href: location.href };
}

(async () => {
  try {
    const input = JSON.parse(await readStdin() || '{}');
    const res = runChallenge(input);
    process.stdout.write(JSON.stringify(res, null, 2));
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: String(e && e.stack || e) }, null, 2));
    process.exitCode = 1;
  }
})();
