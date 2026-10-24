const {createRequire} = require('module');
const sdenvRequire = createRequire(require.resolve('sdenv'));
const canvasPath = sdenvRequire.resolve('canvas');
require.cache[canvasPath] = {id: canvasPath, filename: canvasPath, loaded: true, exports: require('@napi-rs/canvas')};
const {jsdomFromText, jsdom, logger} = require('sdenv');
logger.level = 'off';
const fs = require('fs');
(async () => {
  let dom;
  try {
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const writes = [], errors = []
    let reloadCalled = false;
    class LocalResources extends jsdom.ResourceLoader {
      fetch(url) {
        const script = input.scripts.find(s => s.src === url);
        return script ? Promise.resolve(Buffer.from(script.code)) : null;
      }
    }
    dom = jsdomFromText(input.html, {
      url: input.pageUrl, referrer: input.pageUrl, runScripts: 'dangerously',
      resources: new LocalResources({userAgent: input.userAgent}),
      consoleConfig: {log(){},warn(){},info(){},error(e){errors.push(String(e));}},
      beforeParse(window, environment) {
        window.addEventListener('sdenv:exit', () => { reloadCalled = true; });
        for (const item of (input.cookie || '').split(/;\s*/)) {
          if (item.includes('=')) window.document.cookie = item;
        }
        for (const [key, value] of Object.entries({userAgent: input.userAgent,
          appVersion: input.userAgent.replace(/^Mozilla\//, ''), platform: 'Win32',
          language: 'zh-CN', languages: ['zh-CN', 'zh']})) {
          Object.defineProperty(window.navigator, key, {
            configurable: true, enumerable: true,
            get: environment.tools.setFuncNative(function() { return value; }, 'get ' + key)
          });
        }
        const cookie = Object.getOwnPropertyDescriptor(window.Document.prototype, 'cookie');
        Object.defineProperty(window.Document.prototype, 'cookie', {...cookie,
          set(value) { writes.push(String(value)); return cookie.set.call(this, value); }});
      }
    });
    await new Promise(resolve => setTimeout(resolve, 1800));
    const result = {ok: !errors.length, error: errors.join('; '), writes,
      cookieHeader: dom.window.document.cookie, reloadCalled, errors,
    };
    dom.window.close();
    process.stdout.write(JSON.stringify(result));
  } catch (error) {
    if (dom) dom.window.close();
    process.stdout.write(JSON.stringify({ok:false,error:String(error.stack)}));
    process.exitCode = 1;
  }
})();
