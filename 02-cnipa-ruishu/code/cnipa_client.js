/*
 * 中国专利网瑞数挑战与接口请求。
 * 使用 sdenv 在 Node.js 内执行挑战脚本；不依赖浏览器自动化。
 */
const { jsdomFromUrl } = require('sdenv');

const BASE_URL = 'http://epub.cnipa.gov.cn/Gb';
const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36';

function waitForChallenge(dom, timeoutMs = 10000) {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs);
    dom.window.addEventListener('sdenv:exit', () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

function encodeForm(data) {
  const form = new URLSearchParams();
  for (const [key, value] of Object.entries(data)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      form.append(key, item);
    }
  }
  return form.toString();
}

function postWithChallenge(window, path, data) {
  return new Promise((resolve, reject) => {
    const xhr = new window.XMLHttpRequest();
    xhr.open('POST', path, true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.onreadystatechange = () => {
      if (xhr.readyState === 4) {
        resolve({ status: xhr.status, url: xhr.responseURL, body: xhr.responseText });
      }
    };
    xhr.onerror = () => reject(new Error('中国专利网接口请求失败'));
    xhr.send(encodeForm(data));
  });
}

async function indexQuery({ searchStr = '工具' } = {}) {
  const dom = await jsdomFromUrl(BASE_URL, {
    userAgent: USER_AGENT,
    consoleConfig: { error() {} },
  });

  try {
    await waitForChallenge(dom);
    // /Dxb/IndexPDQuery 是查询页面；实际数据提交到 IndexQuery。
    const response = await postWithChallenge(dom.window, '/Dxb/IndexQuery', {
      'indexSearchModel.searchStr': searchStr,
      'indexSearchModel.fmgb': ['true', 'false'],
      'indexSearchModel.fmsq': ['true', 'false'],
      'indexSearchModel.xxsq': ['true', 'false'],
      'indexSearchModel.wgsq': ['true', 'false'],
    });
    return {
      ...response,
      cookies: dom.cookieJar.getCookieStringSync(BASE_URL),
    };
  } finally {
    dom.window.close();
  }
}

if (require.main === module) {
  const [searchStr = '工具'] = process.argv.slice(2);
  indexQuery({ searchStr })
    .then((response) => {
      console.log(`status: ${response.status}`);
      console.log(`url: ${response.url}`);
      console.log(response.body);
      process.exitCode = response.status === 200 ? 0 : 2;
    })
    .catch((error) => {
      console.error(error.stack || error);
      process.exitCode = 1;
    });
}

module.exports = { indexQuery };
