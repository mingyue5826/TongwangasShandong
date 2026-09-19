# 生成要求

我现在要创建一个山东港华燃气项目的ha集成项目，项目名称为tongwangas_shandong，项目集成目录为custom_components/tongwangas_shandong。

你根据homeassistant的集成开发规范，生成一个符合要求的ha集成项目。

\HACS\TowngasHA\hztowngas\custom_components\hztowngas项目是一个符合homeassistant集成开发规范的项目，我也要参考他的规范，但是流程需要按我的要求处理

- ha集成项目的DOMAIN=tongwangas_shandong
- 不确定内容需要确认完成再生成，有问题先问，不要自作主张
- 确保符合homeassistant的集成开发规范
- api.py需要单独一个文件处理
- 重点内容需要增加中文注释，行内注释或行前注释均可，方法或者class的注释按标准即可
- 调用中用到的orgId，我需要复用orglist.json文件，用里面的orgId来处理

# 集成配置相关内容

配置顺序：
1. 根据orglist.json提供下拉框，下拉框展示信息为json列表中的orgName，value为orgId，选择后，该对象的所有信息都需要保存到ha，用于后续
2. 输入access_token、refresh_token、sign
3. 调用getLoginUserInfo接口获取接口响应中的mobile、userId，mobile用于Token本地存储文件名命名，见后续
4. 调用查询绑定户号列表接口queryBindList，该接口的datas是数组，能返回用户下的多个户号信息
5. 根据上述步骤的多个户号信息，用多选框来选择要添加的户号，每个户号为一个设备
6. 为每个户号生成详细的实体信息
7. 设备添加完成后，仍然可以点击配置进行向导配置

集成添加的config_flow支持配置access_token、refresh_token、sign

为了防止refreshToken失效，集成添加完成后，后续也要支持在集成页面中配置以上3个参数

# orglist.json 文件的来源与存储方式

orglist.json的读取方式以及config_flow的第一步选择区域参考这个项目的config_flow和api的host使用方式：
\HACS\TowngasHA\hztowngas\custom_components\hztowngas

orglist.json放在项目的集成根目录下，配置流启动时直接读取该文件。

该文件读取流程：
1. 配置流启动时，直接读取orglist.json文件
2. 从orglist.json文件中读取orgId、orgName、host信息
3. 用orgId、orgName填充下拉框，下拉框展示信息为orgName，value为orgId

host用于调用api的host

# token的保存和刷新机制

refreshToken过期时间：7200

需要保存的变量：ha里需要保存这3个变量和值 refreshToken、accessToken、token生成时间

token保存需要重启后也要能获取，如果只是ha缓存的话，ha系统重启可能会丢失，所以变量保存既需要保存在缓存中，也需要写入到本地文件。

本地保存文件规范：
HA 标准的存储机制推荐使用 Store helper 类（它会自动将数据持久化到 .storage/ 文件夹下）。
例如保存根路径`/config/.storage/tongwangas_shandong/{mobile}.json`
{mobile}： 见后面getLoginUserInfo接口的response

## 变量保存时机

- 集成添加设备初始化时需要保存
- 执行refreshToken接口重新获取需要保存，此时需要确保refreshToken接口成功调用才进行保存
- 集成添加完成后，支持在集成页面重新配置 refreshToken、accessToken和sign

# 实体（Sensors）划分与命名确认

每个选中的户号（subsId）将作为一个 HA 设备（Device），其下包含以下传感器实体：

- 应缴费用 (feePayable)：单位 CNY
- 可用余额 (availableBalance)：单位 CNY
- 上次抄表日期 (lastMeterReadingDate)：字符串/日期类型
- 本期费用 (buyamount)：来自阶梯气价接口，单位 CNY
- 阶梯气价 (stepList)：状态为 "正常"/当前阶梯，属性（attributes）中包含 YAML 格式的阶梯气价列表
- 用气趋势 (gasConsumptionTrendInfo)：状态固定为 "图表"，属性中包含 YAML 格式的趋势数据列表
- 用气明细 (gasConsumptionInfo)：状态固定为 "图表"，属性中包含 YAML 格式的用气记录列表
