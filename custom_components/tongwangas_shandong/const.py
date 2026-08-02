"""山东港华燃气集成的常量定义."""

# 集成唯一标识 Domain
DOMAIN = "tongwangas_shandong"

# 配置键名
CONF_ORG_INFO = "org_info"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SIGN = "sign"
CONF_SELECTED_SUBS = "selected_subs"
CONF_MOBILE = "mobile"
CONF_USER_ID = "user_id"

# 接口基础路径定义
BASE_URL = "https://weixin.shandongtowngas.com.cn"

# API 相对路径
URL_REFRESH_TOKEN = "/vcc-oauth/oauth/authorize2/refreshToken"
URL_GET_USER_INFO = "/nv1/vcc-cbs/usersubs/getLoginUserInfo"
URL_QUERY_BIND_LIST = "/nv1/vcc-cbs/usersubs/queryBindList"
URL_GAS_FEE_BASE = "/nv1/vcc-cbs/charge/gasFeeBaseinfo"
URL_GAS_CONSUMPTION = "/nv1/vcc-cbs/carelessWorkorder/gasConsumptionDataQuery"
URL_GAS_STEP_FEE = "/nv1/vcc-cbs/charge/gasStepFee"