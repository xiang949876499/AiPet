# 小红书 / 抖音内容发布完善设计

> 日期：2026-06-23 | 状态：设计完成，待实施

## 背景

当前系统已经有 `ContentItem`、内容模板、内容日历和本地发布状态。`ContentItem` 记录了平台、标题、正文、话题、图片提示词、排期时间、互动数据和发布状态，但 `/content/calendar` 的发布动作仍然是本地状态更新，没有平台适配层、素材状态、失败原因或外部链接记录。

用户计划后续额外提供生图接口，因此本轮不绑定具体生图服务。系统需要先把内容从“可生成”推进到“可发布、可追踪、可接接口”的产品状态。

## 目标

- 小红书、抖音、朋友圈内容可以在工作台中生成、预览、排期、准备素材、标记发布或调用平台适配器发布。
- 生图能力通过稳定接口预留，当前实现提供占位适配器，不消耗外部服务。
- 小红书/抖音真实发布能力通过 publisher adapter 预留，默认 disabled，避免误发和平台风控风险。
- 页面上清楚展示每条内容的发布状态、素材状态、失败原因、外部链接和互动回填入口。
- 保留半自动工作流：复制文案、下载/查看素材、人工发布、回填链接与互动数据。

## 非目标

- 不实现真实小红书/抖音发帖 API 调用。
- 不接入真实生图接口。
- 不做账号 OAuth、Cookie 托管、自动登录或绕过平台风控。
- 不做视频生成、剪辑或自动上传成片。

## 方案

采用“半自动工作台 + 可插拔发布适配层”：

1. **内容模型增强**
   - 在 `ContentItem` 上增加外部发布和素材字段：`publish_mode`、`external_url`、`external_post_id`、`publish_error`、`asset_status`、`asset_url`、`asset_error`。
   - 沿用 `image_prompt` 作为生图输入，不新增复杂媒体表，避免过早建模。

2. **生图接口边界**
   - 新增 `content_engine/assets.py`。
   - 定义 `ImageGenerationRequest`、`ImageGenerationResult` 和 `ImageGenerator` 协议。
   - 提供 `PlaceholderImageGenerator`，只把 `asset_status` 置为 `placeholder_ready`，并把图片提示词保留给人工或后续接口使用。
   - 后续用户提供接口时，只需要新增一个 adapter，并由配置切换。

3. **发布接口边界**
   - 新增 `content_engine/publishing.py`。
   - 定义 `PublishRequest`、`PublishResult` 和 `PublisherAdapter` 协议。
   - 提供 `ManualPublisher`、`DisabledPublisher`、`MockPublisher`。
   - 小红书和抖音默认走 `DisabledPublisher`，返回清晰错误：真实发布未配置，请人工发布或配置 adapter。
   - 朋友圈默认可走手动发布完成流。

4. **工作台交互**
   - `/content/calendar` 展示素材状态、发布模式、外部链接、失败原因。
   - 新增动作：
     - 准备素材：根据 `image_prompt` 调用当前图片适配器。
     - 复制/人工发布后标记：记录外部链接和发布时间。
     - 调用适配器发布：仅当 adapter enabled 时自动发布，否则记录失败原因。
     - 回填互动：记录点赞、评论、分享、咨询数。

5. **安全与风控**
   - 所有真实外部发布默认关闭。
   - 任何未配置平台凭证、未配置 adapter、素材未准备完成的情况，都不自动发帖。
   - 发布失败要写入 `publish_error`，页面可见。

## 状态机

内容状态：

- `draft`：草稿已生成。
- `asset_ready`：素材提示词或占位素材已准备。
- `scheduled`：已有排期但未发布。
- `published`：人工标记或 adapter 发布成功。
- `failed`：adapter 调用失败或平台未配置。

素材状态：

- `not_requested`：未准备素材。
- `placeholder_ready`：已生成可交给生图接口的提示词。
- `ready`：真实素材已生成并有 `asset_url`。
- `failed`：生图失败并有 `asset_error`。

## 测试策略

- 单元测试覆盖 `content_engine.assets` 的占位生图结果。
- 单元测试覆盖 `content_engine.publishing` 的 manual、disabled、mock adapter。
- Web 集成测试覆盖内容日历页面显示素材/发布状态。
- Web 集成测试覆盖准备素材、人工标记发布、disabled adapter 失败、互动回填。
- 回归测试运行 `uv run pytest tests/test_content_engine tests/test_web/test_operations.py -q`，最后运行 `uv run pytest tests/ -q`。

## 实施顺序

1. 模型字段和数据库兼容迁移。
2. 生图占位 adapter。
3. 发布 adapter 抽象和服务函数。
4. Web 路由动作。
5. 内容日历 UI。
6. 测试与文档收口。

## 后续接真实接口时的接入点

- 生图：实现 `ImageGenerator.generate(request)`，返回 `asset_url` 或错误。
- 小红书/抖音发布：实现 `PublisherAdapter.publish(request)`，返回 `external_post_id`、`external_url`、`raw_response`。
- 配置：通过环境变量或店铺配置选择 adapter，不改变页面和业务流程。
