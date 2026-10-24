import base64
import json
import time
import uuid
import requests
import random
import hashlib
import urllib.request
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import ddddocr
from PIL import Image
from datetime import datetime, timedelta
import os

# ========== 配置区域 ==========
CTMY = "ABb+3gdb+qeG0b1CogVsT/7//UO0OaTz"
BASE_URL = "https://ljgk.envsc.cn/xxgkCaptcha"
DAYS_TO_CRAWL = 9  # 爬取近9天数据
OUTPUT_DIR = "爬取数据"  # 输出根目录
PROXY_API_URL = os.getenv("ENVSC_PROXY_API_URL", "")
PROXY_SIZE = 50
PROXY_STABILITY = 100
PROXY_TYPE = "damai_new"
PROXY_LIST = []
LAST_PROXY_UPDATE = 0
PROXY_UPDATE_INTERVAL = 300  # 代理列表更新间隔（秒）
REQUEST_TIMEOUT = 10  # 请求超时时间（秒）
MAX_RETRY = 3  # 最大重试次数


# =============================

# ------------------------------
# 代理相关函数（同步版本）
# ------------------------------
def build_proxy_url():
    """构造完整的API URL"""
    return f"{PROXY_API_URL}?size={PROXY_SIZE}&stability={PROXY_STABILITY}&type={PROXY_TYPE}"


def fetch_proxies_sync():
    """同步获取代理列表"""
    global PROXY_LIST, LAST_PROXY_UPDATE
    url = build_proxy_url()

    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        PROXY_LIST = []
        for proxy in data.get("proxyes", []):
            if "user" in proxy and proxy["user"]:
                proxy_str = "{}:{}@{}:{}".format(proxy["user"], proxy["password"], proxy["host"], proxy["port"])
            else:
                proxy_str = "{}:{}".format(proxy["host"], proxy["port"])
            PROXY_LIST.append(proxy_str)

        LAST_PROXY_UPDATE = time.time()
        print(f"代理列表已更新，共 {len(PROXY_LIST)} 个代理")
        return PROXY_LIST
    except Exception as e:
        print(f"获取代理列表失败: {e}")
        return PROXY_LIST


def get_random_proxy():
    """同步获取随机代理"""
    global PROXY_LIST, LAST_PROXY_UPDATE

    # 检查是否需要更新代理列表
    if time.time() - LAST_PROXY_UPDATE > PROXY_UPDATE_INTERVAL or not PROXY_LIST:
        fetch_proxies_sync()

    if not PROXY_LIST:
        print("警告：未获取到代理，将使用直连")
        return None

    proxy = random.choice(PROXY_LIST)
    return {"http": f"http://{proxy}", "https": f"http://{proxy}"}


# ------------------------------
# 滑块验证相关函数
# ------------------------------
CLIENT_UID = f"slider-{uuid.uuid4()}"


def get_captcha():
    url = f"{BASE_URL}/captcha/get"
    payload = {
        "captchaType": "blockPuzzle",
        "clientUid": CLIENT_UID,
        "ts": int(time.time() * 1000)
    }

    for retry in range(MAX_RETRY):
        try:
            proxies = get_random_proxy()
            resp = requests.post(url, json=payload, proxies=proxies, timeout=REQUEST_TIMEOUT).json()
            if resp.get("repCode") != "0000":
                raise Exception(f"获取验证码失败: {resp}")
            data = resp["repData"]
            with open("bg.png", "wb") as f:
                f.write(base64.b64decode(data["originalImageBase64"]))
            with open("slider.png", "wb") as f:
                f.write(base64.b64decode(data["jigsawImageBase64"]))
            img = Image.open("bg.png")
            actual_width = img.width
            return data["secretKey"], data["token"], actual_width
        except Exception as e:
            print(f"获取验证码失败 (重试 {retry + 1}/{MAX_RETRY}): {e}")
            if retry < MAX_RETRY - 1:
                time.sleep(0.1)
    raise Exception(f"获取验证码失败，已重试 {MAX_RETRY} 次")


def get_slide_distance():
    with open("bg.png", "rb") as f:
        bg = f.read()
    with open("slider.png", "rb") as f:
        slider = f.read()
    ocr = ddddocr.DdddOcr(det=False, ocr=False)
    result = ocr.slide_match(target_bytes=slider, background_bytes=bg, simple_target=True)
    x1 = result['target'][0]
    x2 = result['target'][2]
    return (x1 + x2) // 2


def generate_point_json(secret_key, distance):
    plain = json.dumps({"x": distance, "y": 5}, separators=(',', ':'))
    key = secret_key.encode('utf-8')
    cipher = AES.new(key, AES.MODE_ECB)
    ciphertext = cipher.encrypt(pad(plain.encode('utf-8'), AES.block_size))
    return base64.b64encode(ciphertext).decode('utf-8')


def verify_captcha(token, point_json, pas):
    url = f"https://ljgk.envsc.cn/xxgkCaptcha/checkKey"
    payload = {
        "captchaType": "blockPuzzle",
        "pointJson": point_json,
        "pas": pas,
        "token": token,
        "clientUid": CLIENT_UID,
        "ts": int(time.time() * 1000)
    }

    for retry in range(MAX_RETRY):
        try:
            proxies = get_random_proxy()
            response = requests.post(url, json=payload, proxies=proxies, timeout=REQUEST_TIMEOUT)
            resp = response.json()
            # print(f"验证码验证 - HTTP status: {response.status_code}, body: {response.text}")
            return resp.get("repCode") == "0000"
        except Exception as e:
            print(f"验证码验证失败 (重试 {retry + 1}/{MAX_RETRY}): {e}")
            if retry < MAX_RETRY - 1:
                time.sleep(0.1)
    return False


def solve_captcha():
    """执行滑块验证并返回token和滑块距离"""
    try:
        secret_key, token, actual_width = get_captcha()
        print(f"获取验证码 - secretKey: {secret_key}, token: {token}, 图片宽度: {actual_width}")

        raw_distance = get_slide_distance()
        scaled_distance = raw_distance * 310 / actual_width - 23
        print(f"滑块距离 - 原始: {raw_distance}, 缩放后: {scaled_distance}")

        pas = f"{int(scaled_distance)}@5"
        point_json = generate_point_json(secret_key, scaled_distance)

        if verify_captcha(token, point_json, pas):
            print("验证码验证成功")
            # print(token)
            return token, int(scaled_distance)
        else:
            print("验证码验证失败")
            return None, None
    except Exception as e:
        print(f"验证码处理异常: {e}")
        return None, None


def check_need_captcha(collection_date_str):
    """检查采集日期是否需要验证码（3天前包括3天）"""
    try:
        collection_date = datetime.strptime(collection_date_str, "%Y%m%d")
        today = datetime.now().date()
        collection_date = collection_date.date()
        days_diff = (today - collection_date).days
        return days_diff >= 3
    except ValueError:
        print(f"日期格式错误: {collection_date_str}")
        return False


# ------------------------------
# 请求重试函数（每次重试自动更换代理）
# ------------------------------
def make_request(method, url, headers=None, params=None, json=None, data=None):
    """
    通用请求函数，自动处理代理和重试
    只处理网络层面的重试（超时、连接错误、非200状态码）
    业务层面的数据验证由调用方自行判断

    :param method: 请求方法 ('GET' 或 'POST')
    :param url: 请求URL
    :param headers: 请求头
    :param params: GET参数
    :param json: POST JSON数据
    :param data: POST表单数据
    :return: 响应数据或None
    """
    for retry in range(MAX_RETRY):
        proxies = get_random_proxy()
        try:
            if method.upper() == 'GET':
                resp = requests.get(url, headers=headers, params=params, proxies=proxies, timeout=REQUEST_TIMEOUT)
            else:
                resp = requests.post(url, headers=headers, json=json, data=data, proxies=proxies,
                                     timeout=REQUEST_TIMEOUT)

            if resp.status_code == 200:
                try:
                    result_data = resp.json()
                    # print(f"[{method}] {url} 返回: {result_data}")
                    return result_data
                except:
                    print(f"[{method}] JSON解析失败，代理: {proxies}")
            else:
                print(f"[{method}] 请求失败，状态码: {resp.status_code}，代理: {proxies}")
        except Exception as e:
            print(f"[{method}] 请求失败 (重试 {retry + 1}/{MAX_RETRY}): {e}，代理: {proxies}")

        if retry < MAX_RETRY - 1:
            time.sleep(0.1)

    return None


def fetch_with_retry(url, headers=None, params=None):
    """带重试的GET请求函数（每次重试自动更换代理）"""
    try:
        result = make_request('GET', url, headers=headers, params=params)
        print(f"[GET] {url} 返回: {result}")
        return result
    except Exception as e:
        print(f"[GET] {url} 请求异常: {e}")
        return None


def post_with_retry(url, headers=None, json=None, data=None):
    """带重试的POST请求函数（每次重试自动更换代理）"""
    return make_request('POST', url, headers=headers, json=json, data=data)


def fetch_with_retry_and_validation(url, headers=None, params=None, validator=None):
    """
    带重试和业务验证的GET请求函数
    :param validator: 验证函数，接收响应数据，返回True表示验证通过，False表示需要重试
    :return: 验证通过的响应数据或None
    """
    for retry in range(MAX_RETRY):
        data = fetch_with_retry(url, headers=headers, params=params)

        # 如果有验证函数，进行业务验证
        if validator is not None:
            if validator(data):
                return data
            else:
                print(f"数据验证失败，继续重试 (重试 {retry + 1}/{MAX_RETRY})")
        else:
            return data

        if retry < MAX_RETRY - 1:
            time.sleep(0.1)

    return None


def fetch_with_retry(url, headers=None, params=None):
    """带重试的GET请求函数（每次重试自动更换代理）"""
    return make_request('GET', url, headers=headers, params=params)


def post_with_retry(url, headers=None, json=None, data=None):
    """带重试的POST请求函数（每次重试自动更换代理）"""
    return make_request('POST', url, headers=headers, json=json, data=data)


# ------------------------------
# 接口测试相关函数
# ------------------------------
def generate_tc(length=8):
    return ''.join(str(random.randint(0, 9)) for _ in range(length))


def generate_sign(ctmy, ts, tc):
    raw = ctmy + str(ts) + tc
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": "https://ljgk.envsc.cn/monitordata.html?v=20260126",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": "\"Chromium\";v=\"148\", \"Google Chrome\";v=\"148\", \"Not/A)Brand\";v=\"99\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\""
}


def fetch_all_data(pscode, mp_code, day, verifyid="", verifyx=""):
    """获取监控、炉温、工况数据，支持传入verifyid和verifyx，带业务验证和重试"""

    def build_params():
        """构建请求参数（每次调用都重新生成签名）"""
        ts = int(time.time() * 1000)
        tc = generate_tc(8)
        sgn = generate_sign(CTMY, ts, tc)
        return {
            "pscode": pscode,
            "outputcode": mp_code,
            "day": day,
            "SystemType": "C16A882D480E678F",
            "sgn": sgn,
            "ts": str(ts),
            "tc": tc,
            "verifyid": verifyid,
            "verifyx": str(verifyx),
            "verifyy": "5"
        }

    def needs_new_captcha(error_msg):
        """判断是否需要重新获取验证码"""
        keywords = ["验证", "captcha", "token", "invalid", "expired"]
        return any(keyword.lower() in str(error_msg).lower() for keyword in keywords)

    # 获取监控数据（验证ps_code不能为空，空列表也视为失败）
    url_monitor = "https://ljgk.envsc.cn/OutInterface/GetMonitorDataList.ashx"
    monitor_data = None

    for retry in range(MAX_RETRY):
        # 每次重试都重新构建参数（重新生成签名）
        base_params = build_params()

        try:
            monitor_data = fetch_with_retry(url_monitor, headers=headers, params=base_params)

            # 验证：必须是列表、不能为空、且每条数据的ps_code不能为空
            if isinstance(monitor_data, list) and len(monitor_data) > 0:
                if not any(not item.get("ps_code") for item in monitor_data):
                    break  # 验证通过，退出重试

            print(f"监控数据验证失败（列表为空或ps_code为空），重试 ({retry + 1}/{MAX_RETRY})")

            # 如果失败原因可能是验证码问题，尝试重新获取验证码
            if retry > 0 and verifyid:
                print(f"检测到验证失败，尝试重新获取验证码...")
                new_verifyid, new_verifyx = solve_captcha()
                if new_verifyid:
                    verifyid = new_verifyid
                    verifyx = new_verifyx
                    base_params["verifyid"] = verifyid
                    base_params["verifyx"] = str(verifyx)

        except Exception as e:
            error_str = str(e)
            print(f"监控数据请求异常 (重试 {retry + 1}/{MAX_RETRY}): {error_str}")

            # 如果是验证码相关错误，尝试重新获取
            if needs_new_captcha(error_str) and verifyid:
                print(f"检测到验证码错误，尝试重新获取...")
                new_verifyid, new_verifyx = solve_captcha()
                if new_verifyid:
                    verifyid = new_verifyid
                    verifyx = new_verifyx

        if retry < MAX_RETRY - 1:
            time.sleep(0.1)

    # 获取炉温数据（验证ps_code不能为空，空列表也视为失败）
    url_luwen = "https://ljgk.envsc.cn/OutInterface/GetLuWenDataList.ashx"
    luwen_data = None

    for retry in range(MAX_RETRY):
        # 每次重试都重新构建参数（重新生成签名）
        base_params = build_params()

        try:
            luwen_data = fetch_with_retry(url_luwen, headers=headers, params=base_params)

            # 验证：必须是列表、不能为空、且每条数据的ps_code不能为空
            if isinstance(luwen_data, list) and len(luwen_data) > 0:
                if not any(not item.get("ps_code") for item in luwen_data):
                    break  # 验证通过，退出重试

            print(f"炉温数据验证失败（列表为空或ps_code为空），重试 ({retry + 1}/{MAX_RETRY})")

            # 如果失败原因可能是验证码问题，尝试重新获取验证码
            if retry > 0 and verifyid:
                print(f"检测到验证失败，尝试重新获取验证码...")
                new_verifyid, new_verifyx = solve_captcha()
                if new_verifyid:
                    verifyid = new_verifyid
                    verifyx = new_verifyx
                    base_params["verifyid"] = verifyid
                    base_params["verifyx"] = str(verifyx)

        except Exception as e:
            error_str = str(e)
            print(f"炉温数据请求异常 (重试 {retry + 1}/{MAX_RETRY}): {error_str}")

            # 如果是验证码相关错误，尝试重新获取
            if needs_new_captcha(error_str) and verifyid:
                print(f"检测到验证码错误，尝试重新获取...")
                new_verifyid, new_verifyx = solve_captcha()
                if new_verifyid:
                    verifyid = new_verifyid
                    verifyx = new_verifyx

        if retry < MAX_RETRY - 1:
            time.sleep(0.1)

    # 获取工况数据
    url_gk = "https://ljgk.envsc.cn/OutInterface/GetGKDataList.ashx"
    gk_data = None

    for retry in range(MAX_RETRY):
        base_params = build_params()

        try:
            gk_data = fetch_with_retry(url_gk, headers=headers, params=base_params)

            # 工况数据不强制要求验证，只要返回数据即可
            if gk_data is not None:
                break

            print(f"工况数据获取失败，重试 ({retry + 1}/{MAX_RETRY})")

        except Exception as e:
            print(f"工况数据请求异常 (重试 {retry + 1}/{MAX_RETRY}): {e}")

        if retry < MAX_RETRY - 1:
            time.sleep(0.1)

    return monitor_data, luwen_data, gk_data, verifyid, verifyx


def main():
    # 初始化代理列表
    fetch_proxies_sync()

    # 获取企业列表
    ts = int(time.time() * 1000)
    tc = generate_tc(8)
    sgn = generate_sign(CTMY, ts, tc)
    url_list = "https://ljgk.envsc.cn/OutInterface/GetPSList.ashx"
    params_list = {
        "regionCode": "0",
        "psname": "",
        "SystemType": "C16A882D480E678F",
        "sgn": sgn,
        "ts": str(ts),
        "tc": tc,
    }

    data = fetch_with_retry(url_list, headers=headers, params=params_list)
    if not isinstance(data, list):
        print("获取企业列表失败，数据格式错误")
        return
    print(f"获取到 {len(data)} 家企业")

    company_url = "https://ljgk.envsc.cn/OutInterface/GetPSInfo.ashx"

    for item in data:
        ps_code = item.get("ps_code")
        if not ps_code:
            continue

        # 获取企业详情
        ts = int(time.time() * 1000)
        tc = generate_tc(8)
        sgn = generate_sign(CTMY, ts, tc)
        params_company = {
            "pscode": ps_code,
            "outputcode": "",
            "day": "",
            "SystemType": "C16A882D480E678F",
            "sgn": sgn,
            "ts": str(ts),
            "tc": tc
        }
        # 获取企业详情（验证企业名不能为空，带重试）
        company_info = None
        info = None
        for retry in range(MAX_RETRY):
            company_info = fetch_with_retry(company_url, headers=headers, params=params_company)
            if isinstance(company_info, list) and len(company_info) > 0:
                info = company_info[0]
                # 验证：企业名不能为空
                if info.get("ps_name"):
                    break
                print(f"企业详情验证失败，企业名为空，重试 ({retry + 1}/{MAX_RETRY})")
            else:
                print(f"获取企业详情失败，重试 ({retry + 1}/{MAX_RETRY})")
            if retry < MAX_RETRY - 1:
                time.sleep(0.1)

        if not info or not info.get("ps_name"):
            print(f"获取企业 {ps_code} 详情失败，跳过")
            continue

        # 获取焚烧炉列表
        burn_ts = int(time.time() * 1000)
        burn_tc = generate_tc(8)
        burn_sgn = generate_sign(CTMY, burn_ts, burn_tc)
        burn_params = {
            "pscode": ps_code,
            "outputcode": "",
            "day": "",
            "SystemType": "C16A882D480E678F",
            "sgn": burn_sgn,
            "ts": str(burn_ts),
            "tc": burn_tc
        }
        burn_list = fetch_with_retry("https://ljgk.envsc.cn/OutInterface/GetBurnList.ashx", headers=headers,
                                     params=burn_params)
        if not isinstance(burn_list, list):
            burn_list = []

        burners = []
        for burner in burn_list:
            burners.append({
                "焚烧炉名称": burner.get("boiler_name", "--"),
                "炉型": burner.get("boiler_type", "--"),
                "投产日期": burner.get("creater_time", "--"),
                "设计处理能力 (t/d)": burner.get("burn_ability", "--")
            })

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_info = {
            "企业名称": info.get("ps_name", "--"),
            "企业地址": info.get("address", "--"),
            "统一社会信息代码": info.get("credit_code", "--"),
            "行政区划": info.get("fullregion_name", "--"),
            "法人代表": info.get("corporation_name", "--"),
            "投产日期": info.get("manufacture_date", "--"),
            "信息公开负责人": info.get("environment_principal", "--"),
            "联系方式": info.get("link_info", "--"),
            "焚烧炉数": info.get("boiler_num", 0),
            "设计处理能力": info.get("burn_ability", "--"),
            "发电功率": info.get("electric_power", "--"),
            "焚烧炉信息": burners,
            "采集时间": now_str,
            "更新时间": now_str
        }

        # 保存企业信息
        company_name = info.get("ps_name", "未知企业").replace('/', '_').replace('\\', '_').replace(':', '_')
        company_dir = os.path.join(OUTPUT_DIR, company_name)
        os.makedirs(company_dir, exist_ok=True)

        # 保存企业基本信息
        company_info_path = os.path.join(company_dir, "企业信息.json")
        with open(company_info_path, 'w', encoding='utf-8') as f:
            json.dump(full_info, f, ensure_ascii=False, indent=2)
        print(f"企业信息已保存: {company_info_path}")

        # 计算监控数据最新日期
        now = datetime.now()
        if now.hour >= 13:
            latest_date = now - timedelta(days=1)  # 13点后取昨天
        else:
            latest_date = now - timedelta(days=2)  # 13点前取前天

        # 生成要爬取的日期列表
        crawl_dates = []
        for i in range(DAYS_TO_CRAWL):
            date = latest_date - timedelta(days=i)
            crawl_dates.append(date.strftime("%Y%m%d"))

        print(f"准备爬取 {DAYS_TO_CRAWL} 天数据，日期范围: {crawl_dates[-1]} 至 {crawl_dates[0]}")

        # 遍历日期爬取数据
        for day in crawl_dates:
            print(f"\n========== 正在处理日期: {day} ==========")

            # 检查是否需要验证码（每日期单独检查）
            verifyid = ""
            verifyx = ""
            if check_need_captcha(day):
                print(f"采集日期 {day} 是3天前（包括3天），触发验证码")

                # 添加验证码重试机制
                verifyid, verifyx = None, None
                captcha_retry_count = 0
                max_captcha_retries = 3  # 最大验证码重试次数

                while captcha_retry_count < max_captcha_retries:
                    verifyid, verifyx = solve_captcha()
                    if verifyid:
                        break  # 验证成功，退出重试

                    captcha_retry_count += 1
                    print(f"验证码验证失败，重试 ({captcha_retry_count}/{max_captcha_retries})")
                    time.sleep(0.1)  # 重试前等待0.5秒

                if not verifyid:
                    print(f"验证码验证失败，已重试 {max_captcha_retries} 次，跳过日期 {day}")
                    continue
            else:
                print(f"采集日期 {day} 未超过3天，无需验证码")

            # 遍历焚烧炉获取数据
            for burner in burn_list:
                mp_code = burner["mp_code"]
                boiler_name = burner["boiler_name"]

                # 获取三类数据（传入verifyid和verifyx）
                # fetch_all_data 现在返回5个值：monitor_data, luwen_data, gk_data, verifyid, verifyx
                # 如果重试过程中验证码被更新，会返回新的 verifyid 和 verifyx
                result = fetch_all_data(ps_code, mp_code, day, verifyid, verifyx)
                if len(result) == 5:
                    monitor_data, luwen_data, gk_data, verifyid, verifyx = result
                else:
                    # 兼容旧版本返回值
                    monitor_data, luwen_data, gk_data = result

                # 检查数据类型，防止接口返回错误码
                if not isinstance(monitor_data, list):
                    print(f"警告: 监控数据格式错误，跳过焚烧炉 {boiler_name}")
                    continue
                if not isinstance(luwen_data, list):
                    luwen_data = []
                if not isinstance(gk_data, list):
                    gk_data = []

                # 构建工况说明映射
                gk_map = {}
                for gk in gk_data:
                    date_str = gk.get("day")
                    if not date_str:
                        dt = gk.get("monitor_time", "")
                        date_str = dt.split()[0] if dt else ""
                    if date_str:
                        gk_map[date_str] = gk.get("gk_name", "") + gk.get("remark", "")

                # 处理日均值数据
                daily_map = {}
                for rec in monitor_data:
                    dt = rec.get("monitor_time", "")
                    date_str = dt.split()[0] if dt else ""
                    if not date_str:
                        continue
                    date_key = date_str.replace('-', '')
                    if date_str not in daily_map:
                        daily_map[date_str] = {
                            "监测日期": date_str,
                            "监测类型": "日均值",
                            "单位": "mg/m³",
                            "监测因子数据": [],
                            "说明": gk_map.get(date_key, "")
                        }
                    daily_map[date_str]["监测因子数据"].append({
                        "监测因子": rec.get("pollutant_name"),
                        "折算浓度": rec.get("strength"),
                        "标准值": rec.get("standard_value"),
                        "CEMS备注": rec.get("remark") or "--"
                    })
                daily_list = list(daily_map.values())

                # 处理炉温数据
                temp_list = []
                for item in luwen_data:
                    temp_list.append({
                        "监测时间": item.get("monitor_time"),
                        "监测温度": item.get("strength"),
                        "标准温度": item.get("standard_value"),
                        "单位": "℃",
                        "运行状态": item.get("gk_info"),
                        "创建时间": item.get("create_time"),
                        "更新时间": item.get("update_time"),
                        "异常原因": item.get("fault_info") or item.get("cems_info") or None,
                        "监测日期": item.get("day")
                    })

                collect_time = monitor_data[0].get("create_time") if monitor_data else datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S")
                update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                monitor_json = {
                    "企业名称": info["ps_name"],
                    "焚烧炉排放口名称": boiler_name,
                    "日均值": daily_list,
                    "炉膛温度": temp_list,
                    "采集时间": collect_time,
                    "更新时间": update_time,
                    "监控数据时间": day,
                }

                # 保存到本地文件夹
                date_dir = os.path.join(company_dir, day)
                os.makedirs(date_dir, exist_ok=True)

                # 清理锅炉名称中的非法字符
                safe_boiler_name = boiler_name.replace('/', '_').replace('\\', '_').replace(':', '_')
                file_path = os.path.join(date_dir, f"{safe_boiler_name}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(monitor_json, f, ensure_ascii=False, indent=2)
                print(f"数据已保存: {file_path}")


if __name__ == "__main__":
    main()
