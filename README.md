
# DeepSeek-Mermaid PCB Art
<a href="https://github.com/alsunmengy/DeepSeek-PCB-Art/stargazers"><img src="https://raw.githubusercontent.com/alsunmengy/DeepSeek-PCB-Art/main/.github/badges/star-banner.svg" alt="点一下 Star" height="60"></a>
<br>
<a href="https://github.com/alsunmengy"><img src="https://raw.githubusercontent.com/alsunmengy/DeepSeek-PCB-Art/main/.github/badges/follow-me.svg" alt="关注我" height="60"></a>

## Star History

[![Star history](https://raw.githubusercontent.com/alsunmengy/DeepSeek-PCB-Art/main/.github/star-history/chart.svg)](https://github.com/alsunmengy/DeepSeek-PCB-Art/stargazers)
<img src="https://whale-star.whale-star.workers.dev/?repo=alsunmengy/DeepSeek-PCB-Art" alt="star 大肥鱼" width="600" />
图作者【ZipZipPipe的个人空间-哔哩哔哩】 https://b23.tv/oK72DdM

PCB作者【Alsun梦游的个人空间-哔哩哔哩】 https://b23.tv/ZnkaGRq


> 🐳 DeepSeek 人鱼少女 艺术纪念PCB，嘉立创EDA开源硬件项目，双面艺术丝印，无电气功能，纯收藏向工艺板。

## ⚠️ 购买 / 获赠前必读

> **这块板子不是商品，开源也不是卖货。** 在想要一块、或者打算买 / 收下之前，请先看完这条说明：
> **必读说明**：[关于我做出来的 PCB：赠送 / 售卖 / 开源](https://b23.tv/tJhAZ84)
>
> - **开源协议**：CC BY-NC-SA 4.0 —— 个人可免费下载、学习、修改、自己打样，**禁止商用**。真的要卖，最多也就像我这样收个成本价。
> - **赠送**：第一批打样板我留一张，线下送朋友几张，其余放闲鱼「到付」——用闲鱼只是为了不暴露收货地址，到手可以直接申请仅退款，闲鱼标价只当作打赏（现在 10 元，早期 5 元，因为总有人不付邮费让我垫付）。
> - **想买**：送完之后还有人要，我会再订一批。成本约 10 元一张，闲鱼含邮费 20 元（邮费我出）。
> - **图片出处**：有一部分来自网络、有一部分自制，README 里都标注了原作者与原帖。
> - **找到我**：闲鱼 `alsun梦游` ｜ GitHub [`alsunmengy`](https://github.com/alsunmengy) ｜ Star 可选，不点也能用。

## 📖 项目简介
本项目为**纯艺术纪念PCB**，不具备电路功能，无走线、无焊盘，仅利用PCB板厂工艺实现双面精美图案输出。
主题角色：DeepSeek 拟人化人鱼少女，正面为完整人设卡牌，背面为金线描比心少女形象，采用**彩色丝印 + 金色焊盘镀层**实现描边、Logo与文字信息，圆角卡片外形，可作为收藏摆件、挂件、桌面装饰。

板子规格：
- 工程软件：嘉立创EDA专业版
- 基板材质：FR-4
- 板厚：1.6mm
- 外形：圆角矩形卡片
- 工艺：双面彩色丝印，金属描边/Logo文字
- 功能：无电气电路，纯工艺艺术板

**工艺组合**
    - 彩色丝印承载彩色插画主体；
    - 焊盘阻焊层(白色)实现金属质感的Logo、角色档案文字、人物轮廓花边，区分普通丝印，成品有金属光泽；
**卡片圆角外形**，手感圆润，适合做桌面摆件、展示收藏。

'''完整开源工程，可直接导入嘉立创EDA，一键下单打样，也可自行修改图案、配色、文字进行二次创作。'''

## 📂 文件说明
```
DeepSeek-PCB-Art/
├─ 使用的文件/                          # 设计源素材（插画 / Logo 原图，可二次编辑）
├─ 男deek/                              # 男版设计素材
├─ LICENSE                             # 开源协议（CC BY-NC-SA 4.0，详见「开源协议」章节）
├─ README.md                           # 项目说明文档
└─ .gitignore
```

> 📦 工程源文件（`.epro2`）与 Gerber 压缩包统一在 [Releases](https://github.com/alsunmengy/DeepSeek-PCB-Art/releases) 页面下载。请优先选择标注「推荐」的最新版本，旧版本保留在 Releases 历史中。

## 🛠️ 使用方式
### 方式1：嘉立创EDA源工程
1. 打开嘉立创EDA专业版；
2. 文件 → 导入，选择从 [Releases](https://github.com/alsunmengy/DeepSeek-PCB-Art/releases) 下载的 `.epro2` 工程文件（推荐最新版「鱼2」/「MAN!!」）；
3. 核对：板厚、丝印工艺、阻焊层颜色（白色）；
4. 直接提交打样。

> ⚠️ 重要打样提醒
> 1. 需要在下单页开启**彩色丝印工艺**
> 2. 阻焊层选择**白色**，Logo、文字、轮廓依靠镀层实现金属效果；
> 3. 本板无任何器件、无电气网络，下单时忽略“无走线”告警；
> 4. 彩色丝印存在轻微色彩偏差属于工厂正常现象。

### 方式2：Gerber生产文件
在 [Releases](https://github.com/alsunmengy/DeepSeek-PCB-Art/releases) 下载对应版本的 Gerber 压缩包（推荐 `Gerber_PCB1_2026-10-11.zip`）提交 PCB 工厂生产，注意和工厂确认支持**双面彩色丝印+沉金/镀金**工艺。

## 📋 打样参数（嘉立创下单页参考值）

板子为 2 层竖向圆角卡片，下单时逐项核对下表即可：

| 参数 | 取值 |
|------|------|
| 板材类别 | FR-4 |
| 板子尺寸 | 6 cm × 10 cm |
| 板子层数 | 2 层 |
| 板子数量 | 按需选择（常见 5 / 10 片） |
| 成品板厚 | 1.6 mm（也可以更薄） |
| 外层铜厚 | 1 oz |
| 阻焊颜色 | 白色 |
| 字符颜色 | 黑色 |
| 阻焊覆盖 | 过孔盖油 |
| 焊盘喷镀 | 沉金（金色，1 u"，收费项） |
| 最小孔径 | 0.3 mm |
| 线路测试 | AOI 全测 + 飞针全测 |
| 交期 | 正常 3 天 |

> 💡 **彩色丝印**与**沉金**是本板效果的关键项（详见上方「重要打样提醒」）；其余为嘉立创默认选项，下单页如与本表有出入，以页面实际显示为准。

## 🎨 修改二次创作
你可以自由修改：
- 替换正反面插画素材；
- 修改角色档案文本、Logo排版；
- 修改板子尺寸、圆角大小；
- 调整镀层颜色、配色方案。

二次分发请遵守开源协议。

## 📜 开源协议
[![CC BY-NC-SA 4.0](https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

本项目采用 **CC BY-NC-SA 4.0** 协议开源。

> 📢 **2026-09-26 协议更新**：开源协议不变，新增有限商用许可——允许制作实体复制品并售卖，但单件销售**利润率不得超过 20%**；非偏远地区（包邮）情况下，正常售价应在 **20 元以内**。

- ✅ 允许：查看、学习、修改、本地打样、非商用分享、个人自用、无偿赠与；
- ✅ 允许：**有限商业性制作与销售**（须同时满足下方附加条款全部条件）；
- ❌ 禁止：规模化、系统化商业生产或分销；用于广告、品牌推广、商业引流；
- ℹ️ 衍生修改版本需要沿用相同开源协议，并注明原项目来源。

### 附加许可条款（CC BY-NC-SA 4.0 + 附加许可条款）

自2026年9月26日00:00起，本作品授权协议由 CC BY-NC-SA 4.0 调整为"CC BY-NC-SA 4.0 + 附加许可条款"。本次调整仅扩展使用场景，不改变原协议项下署名（BY）、非商业性使用（NC）及相同方式共享（SA）三项核心要求。


## 🖼️ 预览
正面：DeepSeek人鱼少女收藏卡牌，含人设档案、金色Logo
背面：金色描边比心少女同人插画

## 📌 致谢
- 插画：同人爱好者创作
- PCB制作平台：嘉立创EDA


## README由deepseek/豆包/我共同编写
