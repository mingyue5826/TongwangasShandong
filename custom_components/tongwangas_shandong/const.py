"""山东港华燃气集成的常量定义。"""

import json
from pathlib import Path

DOMAIN = "tongwangas_shandong"

# ---- 前端卡片（Lovelace）----
# 集成自带卡片 JS，通过静态路径对外暴露，并在启动时自动登记为 Lovelace 资源，
# 用户无需手动复制文件或手动添加资源。详见 frontend.py。
FRONTEND_URL_BASE = "/tongwangas_shandong"          # 静态资源 URL 前缀
CARD_FILENAME = "tongwangas-shandong-card.js"       # 卡片 JS 文件名
CARD_URL = f"{FRONTEND_URL_BASE}/{CARD_FILENAME}"   # 卡片 JS 访问地址


def _read_integration_version() -> str:
    """从 manifest.json 读取集成版本号（用于卡片 URL 的缓存穿透参数）。"""
    try:
        with open(Path(__file__).parent / "manifest.json", encoding="utf-8") as file:
            return json.load(file).get("version") or "0.0.0"
    except Exception:  # noqa: BLE001 - 版本号读取失败不应影响集成加载
        return "0.0.0"


# 卡片资源 URL 会拼上 ?v=<该版本号>：升级集成后版本变化，浏览器不会继续用旧卡片缓存
INTEGRATION_VERSION = _read_integration_version()

# ---- Config Flow 配置项键名 ----
CONF_ORG_ID = "org_id"                     # 燃气公司ID
CONF_ORG_NAME = "org_name"                 # 燃气公司名称
CONF_ORG_CODE = "org_code"                 # 燃气公司编码
CONF_HOST = "host"                         # API域名（来自orglist.json）
CONF_ACCESS_TOKEN = "access_token"         # 访问令牌
CONF_REFRESH_TOKEN = "refresh_token"       # 刷新令牌
CONF_SIGN = "sign"                         # 签名（用户在ConfigFlow中输入）
CONF_TOKEN_CREATE_TIME = "token_create_time"  # token生成时间（时间戳）
CONF_MOBILE = "mobile"                     # 手机号（用于token文件命名）
CONF_USER_ID = "user_id"                   # 用户ID
CONF_SUBS = "subs"                         # 选中的户号信息列表
CONF_SUBS_IDS = "subs_ids"                 # 配置流中多选的户号ID列表
CONF_SCAN_INTERVAL = "scan_interval"       # 数据刷新间隔（秒）
CONF_TOKEN_REFRESH_INTERVAL = "token_refresh_interval"  # token刷新间隔（秒）

# ---- 默认值 ----
DEFAULT_SCAN_INTERVAL = 21600          # 数据刷新间隔：6小时
DEFAULT_TOKEN_REFRESH_INTERVAL = 1800  # token刷新间隔：30分钟（access_token有效期7200秒）
TOKEN_EXPIRES_IN = 7200                # access_token默认有效期（秒）
TOKEN_EXPIRY_BUFFER_SECS = 60          # 提前刷新缓冲时间（秒）

# ---- API路径 ----
OAUTH_PATH = "/vcc-oauth/oauth/authorize2"  # refreshToken接口路径
API_PATH = "/nv1/vcc-cbs"                   # 业务接口路径

# ---- User-Agent（模拟微信小程序客户端）----
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 NetType/WIFI "
    "MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090c33) "
    "XWEB/14315 Flue"
)
