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

## 用气卡片（Lovelace）

集成附带一张零依赖的 Lovelace 卡片，展示可用余额 / 应缴费用 / 累计用气量、
用气卡片（本月用气 + 每日曲线）、用气阶梯、用气日历、年对比用气曲线、用气明细与日用气曲线。

**卡片随集成自动就绪：不需要手动复制文件，也不需要手动在仪表盘里添加 JS 资源。**

### 自动注册是怎么做的

集成加载时会做两件事：

1. 把集成自带的 `www/` 目录挂载为静态路径 `/tongwangas_shandong/`；
2. 把 `/tongwangas_shandong/tongwangas-shandong-card.js?v=<集成版本>` 登记为 Lovelace 资源。

登记方式按你的仪表盘资源模式自动分流：

| 资源模式 | 集成行为 | 效果 |
| --- | --- | --- |
| **storage**（默认） | 写入仪表盘资源表 | 可在 **设置** → **仪表盘** → 右上角 **⋮** → **资源** 中看到，按需加载，Cast 设备（Chromecast / Nest Hub）也能显示卡片 |
| **yaml** | 退回全局注入 | 与 `frontend.extra_module_url` 同款机制；所有面板都会加载该 JS，Cast 设备不加载 |

> 资源 URL 上的 `?v=` 是缓存穿透参数，HACS 升级集成后版本号变化，浏览器会自动拉取新卡片。
> 该资源由集成自动维护，请在「资源」列表中**不要手动删除**。

### 添加卡片

仪表盘 → 右下角 **编辑** → **+ 添加卡片** → 搜索 **港华燃气用气卡片** 直接添加，
或在「手动」中填入：

```yaml
type: custom:tongwangas-shandong-card
gs: "1111111111"    # 户号；留空则自动探测
title: 港华燃气
```

> 升级集成后若卡片外观没变化，强制刷新浏览器（Windows/Linux `Ctrl + Shift + R`，
> macOS `Cmd + Shift + R`）。

### 曾经手动添加过资源？

早期版本需要手动把 JS 复制到 `config/www/community/tongwangas-shandong/` 并手动添加资源。
如果照做过一次，请到 **设置** → **仪表盘** → **⋮** → **资源** 里**删除**那条
`/local/community/tongwangas-shandong/tongwangas-shandong-card.js`。
不删也能用（卡片自身做了重复注册保护），但同一份 JS 会被加载两次。

### 卡片不显示？

1. 打开 **设置** → **仪表盘** → **⋮** → **资源**，确认存在
   `/tongwangas_shandong/tongwangas-shandong-card.js?v=...`；不存在则**重启 Home Assistant**。
2. 重启后仍不显示，开启 debug 日志查看注册失败原因：

   ```yaml
   logger:
     logs:
       custom_components.tongwangas_shandong: debug
   ```

   日志中会输出 `已自动登记 Lovelace 卡片资源` 或具体的失败原因。
3. 确认浏览器已强制刷新（`Ctrl/Cmd + Shift + R`）。

功能明细、实体依赖与常见问题见
[卡片使用说明](tongwangas-shandong-card.md)。


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

## 仓库结构（开发参考）

```
custom_components/tongwangas_shandong/   # 集成本体 —— HACS 只会安装这个目录
├── manifest.json
├── frontend.py                          # 卡片自动注册（静态路径 + Lovelace 资源）
├── tongwangas-shandong-card.md          # 卡片使用说明
└── www/                                 # 卡片 JS，挂载为 /tongwangas_shandong/ 对外提供
    └── tongwangas-shandong-card.js
preview/                                 # 开发用预览页与截图，仅存于仓库，不随集成安装
hacs.json                                # HACS 仓库元信息
```

两条关键约定：

- **卡片 JS 必须放在 `custom_components/tongwangas_shandong/www/`，不能放仓库根目录。**
  HACS 安装「集成」类仓库时只复制 `custom_components/<domain>/` 这棵子树
  （源码见 HACS `HacsIntegrationRepository.localpath` / `content.path.remote`），
  仓库根目录的文件不会进入用户的 HA 配置目录，静态路径自然取不到文件。
  （根目录放 `www/` 是「插件 / 仪表盘」类仓库的约定 —— 那类仓库才由 HACS 把文件复制到
  `config/www/community/<仓库名>/`。）
- **`www/` 是公开目录**：其中每个文件都能通过 `/tongwangas_shandong/<文件名>` 直接访问，
  所以预览页、截图、开发脚本、说明文档一律放在集成外 —— 本仓库放根目录 `preview/`
  与集成根目录的 `tongwangas-shandong-card.md`。
