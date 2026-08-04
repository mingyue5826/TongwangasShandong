# 山东港华燃气（TongwangasShandong）
![山东港华燃气](custom_components/tongwangas_shandong/brand/logo.png)

## 安装集成

### 方式一：HACS

[![Open your Home Assistant instance and add this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mingyue5826&repository=TongwangasShandong&category=integration)

点上面的按钮一键添加，或者手动操作：

1. 在 Home Assistant 中打开 **HACS**。
2. 进入 **集成** → 右上角菜单（⋮）→ **自定义仓库**。
3. 添加仓库 `https://github.com/mingyue5826/TongwangasShandong`，类别选 **集成（Integration）**。
4. 在 **山东港华燃气** 卡片中点击 **下载**。
5. 按提示 **重启** Home Assistant。

### 方式二：手动安装

1. 将 Release 中的文件解压后复制到 Home Assistant 配置目录下：

   `config/custom_components/tongwangas_shandong/`

2. **重启** Home Assistant。

## 添加设备

1. 打开 **设置** → **设备与服务** → **添加集成**。
2. 搜索 **山东港华燃气**（或 **TongwangasShandong**）并选择。
3. 选择所在区域的 **燃气公司**（下拉框从 orglist.json 读取）。
4. 输入以下信息（信息获取方式见 [信息获取方式](#信息获取方式)）：
   - access_token
   - refresh_token
   - sign
5. 勾选要添加的一个或多个 **户号**，完成向导。

### 实体说明

每个户号作为一个设备，包含以下实体：

**传感器**

| 实体 | 说明 | 单位 |
| --- | --- | --- |
| 应缴费用 | 当前应缴费用 | 元 |
| 可用余额 | 账户可用余额 | 元 |
| 上次抄表日期 | 上次抄表时间 | - |
| 本期费用 | 本期气费 | 元 |
| 阶梯气价 | 当前阶梯气价状态 | - |
| 用气趋势 | 月度用气趋势数据（attributes.graph） | - |
| 用气明细 | 月度用气明细数据（attributes.graph） | - |

**按钮**

| 实体 | 说明 |
| --- | --- |
| 刷新数据 | 立即调用接口刷新数据 |
| 刷新 Token | 立即刷新 token 并刷新数据 |

## 信息获取方式

配置信息需要小程序抓包，建议用电脑端微信小程序进行抓包，手机抓包需要 root 或其他复杂方式。

1. 选择适合自己设备的架构和版本下载并安装 [Reqable](https://reqable.com/zh-CN/download/)。
2. 启动抓包工具。
3. 打开微信小程序，进入 **山东港华燃气**，用微信账号登录。
4. 在抓包工具中搜索 `https://weixin.shandongtowngas.com.cn/nv1/vcc-cbs/usersubs/getLoginUserInfo`。
5. 双击抓包结果，在右侧找到 **请求头** 和 **请求参数**。
6. 请求头中的 `Authorization: Bearer xxx` 的 `xxx` 即为 `access_token`。
7. 请求参数中的 `sign` 即为 `sign`。
8. 在抓包工具中搜索 `https://weixin.shandongtowngas.com.cn/vcc-oauth/oauth/authorize2/refreshToken`。
9. 请求参数中的 `refreshToken` 即为 `refresh_token`。

## Token 刷新机制

- 集成初始化时保存 token 到 HA 缓存和本地文件（`.storage/tongwangas_shandong/{mobile}.json`）。
- 每 30 分钟自动调用 refreshToken 接口刷新 token。
- 业务接口返回 `resultCode=20001`（access_token 过期）时自动刷新并重试。
- refreshToken 失效（`resultCode=90143`）时会提示重新认证，实体保持上次数据不变。

## 集成配置

添加集成后，可以在集成页面点击 **配置** 按钮重新配置：

- access_token
- refresh_token
- sign
- 数据刷新间隔（分钟）

## 问题反馈

如遇到问题，请提交 [Issue](https://github.com/mingyue5826/TongwangasShandong/issues)。

开启 debug 日志排查问题：

```yaml
logger:
  default: warning
  logs:
    custom_components.tongwangas_shandong: debug
```
