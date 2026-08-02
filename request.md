# 生成要求

- ha集成项目的DOMAIN=Tongwangas_Shandong
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


# token的保存和刷新机制

问1：refreshToken这个的7200是多少小时

需要保存的变量：ha里需要保存这3个变量和值 refreshToken、accessToken、token生成时间

token保存需要重启后也要能获取，如果只是ha缓存的话，ha系统重启可能会丢失，所以变量保存既需要保存在缓存中，也需要写入到本地文件。

本地保存文件规范：

保存根路径`/config/.storage/{DOMAIN}/{mobile}.json`

{DOMAIN}：ha集成的domain
{mobile}： 见后面getLoginUserInfo接口的response

## 变量保存时机

- 集成添加设备初始化时需要保存
- 执行refreshToken接口重新获取需要保存，此时需要确保refreshToken接口成功调用才进行保存
- 集成添加完成后，支持在集成页面重新配置 refreshToken、accessToken和sign



# 其他API请求和响应
1、不作特殊说明，requestHeader都是Authorization: Bearer {{access_token}}。

2、接口请求和响应中我对数据进行了脱敏处理，即*

3、接口成功响应的resultCode为字符串0
4、如果Token错误，`{"resultCode":"20001","resultMsg":"access token 过期"}`

## getLoginUserInfo 获取登录用户信息

响应中的mobile为前面提到的

https://weixin.shandongtowngas.com.cn/nv1/vcc-cbs/usersubs/getLoginUserInfo?timestamp={{$timestamp}}&sign=4CB2B6EB6A6231F86A1E57485B0EE232

```
{
    "realName": null,
    "headImg": null,
    "idcard": null,
    "resultCode": "0",
    "mobile": "***",
    "sensitiveMobile": "178****9",
    "userId": "****",
    "memberId": "***"
}
```

## 查询绑定户号列表

请求：https://weixin.shandongtowngas.com.cn/nv1/vcc-cbs/usersubs/queryBindList?isPay=N&orgId={{orgId}}&timestamp={{$timestamp}}&sign={{sign}}

响应（datas为数组，表示该用户下的所有户号信息）：
多个户号的deviceId使用`subsId`，deviceName使用`displayAddr`

```
{
    "datas": [
        {
            "subsId": "***",
            "subsCode": "***",
            "orgId": "***",
            "orgCode": "***",
            "name": "孙*",
            "displayAddr": "****01",
            "bound": null,
            "nickName": "自家",
            "subsType": "1",
            "role": null,
            "mobile": null,
            "defaultFlag": "Y",
            "resType": "12",
            "nbFlag": "Y"
        }
    ],
    "resultCode": "0"
}
```

## 获取费用信息 gasFeeBaseinfo

https://weixin.shandongtowngas.com.cn/nv1/vcc-cbs/charge/gasFeeBaseinfo?orgId={{orgId}}&subsId={{subsId}}&timestamp={{$timestamp}}&sign=30B3AC57703777B38DC033912EB8896A

获取feePayable、availableBalance（可用余额）、lastMeterReadingDate，生成传感器实体信息

响应：

```
{
    "feePayable": "0",
    "lastMeterReadingDate": "2026-08-02",
    "resultCode": "0",
    "availableBalance": "52.00"
}
```

## 用气记录接口

该接口生成两个传感器实体：

gasConsumptionTrendInfo和gasConsumptionInfo，两个传感器实体的名称你自己翻译，实体的值是固定值”图表“，根据接口的返回的数组中的信息，生成yaml格式属性，我用来生成图表

https://weixin.shandongtowngas.com.cn/nv1/vcc-cbs/carelessWorkorder/gasConsumptionDataQuery?subsId={{subsId}}&timestamp={{$timestamp}}&sign=50FB0BE38B6A314F38DE75C83A153AF3

响应：

```
{
    "gasConsumptionTrendInfo": [
        {
            "lastYearFlag": "Y",
            "yrMonth": "202501",
            "gasSum": "2"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202502",
            "gasSum": "9"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202503",
            "gasSum": "9"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202504",
            "gasSum": "5"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202505",
            "gasSum": "7"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202506",
            "gasSum": "8"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202507",
            "gasSum": "9"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202508",
            "gasSum": "8"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202509",
            "gasSum": "11"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202510",
            "gasSum": "9"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202511",
            "gasSum": "8"
        },
        {
            "lastYearFlag": "Y",
            "yrMonth": "202512",
            "gasSum": "8"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202601",
            "gasSum": "7"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202602",
            "gasSum": "12"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202603",
            "gasSum": "14"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202604",
            "gasSum": "10"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202605",
            "gasSum": "17"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202606",
            "gasSum": "42"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202607",
            "gasSum": "26"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202608",
            "gasSum": "0"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202609",
            "gasSum": "0"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202610",
            "gasSum": "0"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202611",
            "gasSum": "0"
        },
        {
            "lastYearFlag": "N",
            "yrMonth": "202612",
            "gasSum": "0"
        }
    ],
    "gasConsumptionInfo": [
        {
            "resTypeCategory": "0",
            "lastYearFlag": "N",
            "subsCode": "1970109576",
            "yrMonth": "202607",
            "meterCode": "152230600533",
            "money": "91",
            "gasSum": "26",
            "lastReading": "197",
            "currReading": "223",
            "readingDate": "2026-07-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "N",
            "subsCode": "1970109576",
            "yrMonth": "202606",
            "meterCode": "152230600533",
            "money": "147",
            "gasSum": "42",
            "lastReading": "155",
            "currReading": "197",
            "readingDate": "2026-06-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "N",
            "subsCode": "1970109576",
            "yrMonth": "202605",
            "meterCode": "152230600533",
            "money": "59.5",
            "gasSum": "17",
            "lastReading": "138",
            "currReading": "155",
            "readingDate": "2026-05-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "N",
            "subsCode": "1970109576",
            "yrMonth": "202604",
            "meterCode": "152230600533",
            "money": "35",
            "gasSum": "10",
            "lastReading": "128",
            "currReading": "138",
            "readingDate": "2026-04-22",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "N",
            "subsCode": "1970109576",
            "yrMonth": "202603",
            "meterCode": "152230600533",
            "money": "49",
            "gasSum": "14",
            "lastReading": "114",
            "currReading": "128",
            "readingDate": "2026-03-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "N",
            "subsCode": "1970109576",
            "yrMonth": "202602",
            "meterCode": "152230600533",
            "money": "42",
            "gasSum": "12",
            "lastReading": "102",
            "currReading": "114",
            "readingDate": "2026-02-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "N",
            "subsCode": "1970109576",
            "yrMonth": "202601",
            "meterCode": "152230600533",
            "money": "24.5",
            "gasSum": "7",
            "lastReading": "95",
            "currReading": "102",
            "readingDate": "2026-01-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202512",
            "meterCode": "152230600533",
            "money": "28",
            "gasSum": "8",
            "lastReading": "87",
            "currReading": "95",
            "readingDate": "2025-12-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202511",
            "meterCode": "152230600533",
            "money": "28",
            "gasSum": "8",
            "lastReading": "79",
            "currReading": "87",
            "readingDate": "2025-11-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202510",
            "meterCode": "152230600533",
            "money": "31.5",
            "gasSum": "9",
            "lastReading": "70",
            "currReading": "79",
            "readingDate": "2025-10-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202509",
            "meterCode": "152230600533",
            "money": "38.5",
            "gasSum": "11",
            "lastReading": "59",
            "currReading": "70",
            "readingDate": "2025-09-21",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202508",
            "meterCode": "152230600533",
            "money": "28",
            "gasSum": "8",
            "lastReading": "51",
            "currReading": "59",
            "readingDate": "2025-08-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202507",
            "meterCode": "152230600533",
            "money": "31.5",
            "gasSum": "9",
            "lastReading": "42",
            "currReading": "51",
            "readingDate": "2025-07-18",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202506",
            "meterCode": "152230600533",
            "money": "28",
            "gasSum": "8",
            "lastReading": "34",
            "currReading": "42",
            "readingDate": "2025-06-20",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202505",
            "meterCode": "152230600533",
            "money": "24.5",
            "gasSum": "7",
            "lastReading": "27",
            "currReading": "34",
            "readingDate": "2025-05-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202504",
            "meterCode": "152230600533",
            "money": "17.5",
            "gasSum": "5",
            "lastReading": "22",
            "currReading": "27",
            "readingDate": "2025-04-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202503",
            "meterCode": "152230600533",
            "money": "31.5",
            "gasSum": "9",
            "lastReading": "13",
            "currReading": "22",
            "readingDate": "2025-03-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202502",
            "meterCode": "152230600533",
            "money": "31.5",
            "gasSum": "9",
            "lastReading": "4",
            "currReading": "13",
            "readingDate": "2025-02-24",
            "rechargeDetails": null
        },
        {
            "resTypeCategory": "0",
            "lastYearFlag": "Y",
            "subsCode": "1970109576",
            "yrMonth": "202501",
            "meterCode": "152230600533",
            "money": "7",
            "gasSum": "2",
            "lastReading": "2",
            "currReading": "4",
            "readingDate": "2025-01-20",
            "rechargeDetails": null
        }
    ],
    "resultCode": "0"
}
```

## 查询阶梯气价



https://weixin.shandongtowngas.com.cn/nv1/vcc-cbs/charge/gasStepFee?orgId={{orgId}}&subsId={{subsId}}&timestamp={{$isoTimestamp}}&sign=312598B4BA35BF6502678C392348409C

buyamount为本期费用，生成传感器实体：本期费用

生成传感器实体：阶梯气价，把stepList中的信息都改成yaml的列表格式

响应：

```
{
    "datas": {
        "buyamount": "132",
        "stepList": [
            {
                "priceModel": null,
                "modelSeq": "1",
                "minMount": null,
                "maxMount": "216",
                "mountTrate": null,
                "price": "3.5",
                "discFactor": null,
                "effDate": null,
                "expDate": null,
                "priceCode": null,
                "stepName": "一阶气价"
            },
            {
                "priceModel": null,
                "modelSeq": "2",
                "minMount": null,
                "maxMount": "360",
                "mountTrate": null,
                "price": "4.1",
                "discFactor": null,
                "effDate": null,
                "expDate": null,
                "priceCode": null,
                "stepName": "二阶气价"
            },
            {
                "priceModel": null,
                "modelSeq": "3",
                "minMount": null,
                "maxMount": "-1",
                "mountTrate": null,
                "price": "5",
                "discFactor": null,
                "effDate": null,
                "expDate": null,
                "priceCode": null,
                "stepName": "三阶气价"
            }
        ]
    },
    "resultCode": "0"
}
```

# 其他

一、 关键问题解答

问1：refreshToken这个的7200是多少小时？

回答：7200 表示 7200 秒（即 2 小时）。

对开发的影响：2 小时的有效期限相对较短，因此集成在运行期间，不能等到 token 彻底失效才去刷新。建议采用“每次请求接口前/定时轮询前，判断 token生成时间 是否接近 2 小时（如超过 90 分钟），若接近则自动调用 refreshToken 接口”的策略，确保接口调用的稳定性。

二、 需要向你确认的细节问题（请回复确认）

orglist.json 文件的来源与存储方式

需求中提到“根据 orglist.json 提供下拉框...”。请问这个 orglist.json 文件是预先存放在集成根目录下（例如 custom_components/Tongwangas_Shandong/orglist.json），还是从远程/其它途径获取？

默认假设：我们将把 orglist.json 放在集成根目录下打包，配置流启动时直接读取该文件。请确认是否符合你的期望？

接口请求中的 sign 参数

在你提供的 API 示例中，如 getLoginUserInfo、gasFeeBaseinfo、gasStepFee 等，各自都有不同的 sign 值（例如 sign=30B3AC57703777B38DC033912EB8896A）。

确认项：这些 API 请求中的 sign 也是在 Postman 抓包时获取的静态值，还是说直接统一使用用户在 ConfigFlow 中输入的那个 sign 即可？

mobile.json 持久化存储与 HA 交互机制

需求指定存储路径为：/config/.storage/Tongwangas_Shandong/{mobile}.json。

HA 标准的存储机制推荐使用 Store helper 类（它会自动将数据持久化到 .storage/ 文件夹下）。

确认项：为了完全符合你指定的路径与格式（包含 {mobile} 动态文件名），我们将使用 Python 的 aiofiles / json 标准库在对应目录直接读写 .json 文件。请确认该方式是否满足要求？

实体（Sensors）划分与命名确认

根据你的需求描述，每个选中的户号（subsId）将作为一个 HA 设备（Device），其下包含以下传感器实体，请确认命名与逻辑是否符合预期：

应缴费用 (feePayable)：单位 CNY

可用余额 (availableBalance)：单位 CNY

上次抄表日期 (lastMeterReadingDate)：字符串/日期类型

本期费用 (buyamount)：来自阶梯气价接口，单位 CNY

阶梯气价 (stepList)：状态为 "正常"/当前阶梯，属性（attributes）中包含 YAML 格式的阶梯气价列表

用气趋势 (gasConsumptionTrendInfo)：状态固定为 "图表"，属性中包含 YAML 格式的趋势数据列表

用气明细 (gasConsumptionInfo)：状态固定为 "图表"，属性中包含 YAML 格式的用气记录列表

gasStepFee 接口的时间戳格式

你给出的 gasStepFee 请求 URL 中使用的是 timestamp={{$isoTimestamp}}，而其他接口为 timestamp={{$timestamp}}（毫秒级时间戳）。

确认项：gasStepFee 接口是否支持普通的 13 位毫秒时间戳，还是必须转换为 ISO 8601 时间戳字符串（如 2026-08-02T19:06:50.000Z）？

## 解答

1. orglist.json放在项目的集成根目录下，配置流启动时直接读取
2. 我的api示例中的sign参数不一样，你不用管，只需要配置集成的时候输入即可（如果后续有问题了，仍然可以在集成配置页面修改）
3. 使用HA 标准的存储机制推荐使用 Store helper 类（它会自动将数据持久化到 .storage/ 文件夹下）。
4. 实体划分与命名确认无问题
5. 时间戳格式使用普通的13位毫秒时间戳即可
6. 我额外增加一个诊断实体：刷新token这个button，按下后立即刷新token。该实体的属性中需要增加刷新时间 

