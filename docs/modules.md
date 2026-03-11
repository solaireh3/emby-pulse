# 功能模块说明（含使用方法与配置）

本页对 EmbyPulse 核心模块进行“怎么用 + 需要配置什么”的详细说明，适合新手与管理员快速上手。

> ✅ 提示：所有“系统设置”字段都对应 [系统设置页面](file:///C:/Users/Win10/Desktop/embystathub/templates/settings.html) 与 [通知与机器人页面](file:///C:/Users/Win10/Desktop/embystathub/templates/bot.html) 中的真实表单项，已按实际 UI 命名整理。

## 1. 全景仪表盘（Dashboard）

**功能说明**
- 展示当前并发播放、客户端类型、转码负荷
- 展示累计播放次数、播放时长与活跃用户
- 支持按天 / 周 / 月的趋势图

**如何使用**
1. 启动服务后打开首页即进入仪表盘
2. 选择时间维度查看趋势
3. 点击榜单可查看更多详情

**设置路径（系统设置页面）**
- 媒体服务器核心：`emby_host` / `emby_api_key` / `playback_data_mode`
- 隐藏黑名单：`hidden_users`

## 2. 缺集管理（Gap Management）

**功能说明**
- 扫描 Emby 剧集与 TMDB 数据，找出缺失集
- 可联动 MoviePilot 搜索资源并补全
- 可截胡下载器，仅下载缺失集

**如何使用**
1. 进入“缺集管理”页面
2. 点击“扫描缺集”并等待结果
3. 选择缺集条目进行“搜索 / 下发 / 截胡”操作

**设置路径（分两处）**
- 系统设置 → MoviePilot 自动化联控：`moviepilot_url` / `moviepilot_token` / `pulse_url`
- 缺集管理页面 → “底层接管配置”弹窗：`client_type` / `client_url` / `client_user` / `client_pass`

## 3. 追剧日历（TV Calendar）

**功能说明**
- 自动展示本周更新剧集
- 已入库可直达 Emby 播放
- 未入库可复制搜索指令

**如何使用**
1. 打开“追剧日历”页面
2. 点击日期查看更新内容
3. 绿色为已入库，红色为缺失

**设置路径（系统设置页面）**
- 无需额外配置（依赖 `emby_api_key` 与 TMDB 数据）

## 4. 求片系统（Request Center）

**功能说明**
- 用户提交电影 / 剧集 / 季度请求
- 管理员审核并流转状态
- 入库后自动闭环

**如何使用（用户）**
1. 打开求片页面
2. 搜索或输入片名提交
3. 在“我的请求”查看状态

**如何使用（管理员）**
1. 进入后台求片管理
2. 审核、下发或拒绝请求
3. 入库完成后自动更新状态

**设置路径（系统设置 / 通知与机器人页面）**
- 对外服务门户：`emby_public_url` / `client_download_url` / `welcome_message`
- Telegram 通道：`tg_bot_token` / `tg_chat_id`

## 5. 用户中心（User Center）

**功能说明**
- 查看用户资料、到期时间、备注
- 续期、禁用、重置等管理操作
- 用户活跃度与观影趋势

**如何使用**
1. 管理员进入“用户中心”
2. 点击某个用户查看详情
3. 进行续期、备注与状态调整

**设置路径（系统设置页面）**
- 媒体服务器核心：`emby_host` / `emby_api_key`

## 6. 数据洞察（Insights）

**功能说明**
- 用户画像与趣味成就
- 入驻溯源（真实注册天数）
- 媒体库画质结构盘点

**如何使用**
1. 打开“数据洞察”页面
2. 选择用户查看画像
3. 查看画质结构和低画质清单

**设置路径（系统设置页面）**
- 媒体服务器核心：`emby_api_key`

## 7. 映迹工坊（Report Generator）

**功能说明**
- 生成日报 / 周报 / 月报 / 年度总结
- 多主题风格，一键生成长图

**如何使用**
1. 进入“映迹工坊”
2. 选择报表周期与主题
3. 点击生成并下载

**设置路径（通知与机器人页面）**
- 推送场景总控：`enable_bot` / `enable_notify` / `enable_library_notify`
- Telegram 通道：`tg_bot_token` / `tg_chat_id`
- 企业微信(推送)：`wecom_corpid` / `wecom_agentid` / `wecom_corpsecret` / `wecom_touser`
- 企业微信 API 代理：`wecom_proxy_url`

## 8. 用户与邀请系统

**功能说明**
- 生成邀请链接（7 天 / 30 天 / 永久）
- 支持自助注册
- 到期锁定与批量续期

**如何使用**
1. 管理员进入邀请管理
2. 生成邀请链接并发送
3. 新用户通过链接注册

**设置路径（用户管理页面）**
- 用户管理 → 邀请管理
- 无需额外配置（默认基于 Emby 账号体系）

## 9. Telegram 机器人

**功能说明**
- 播放开始 / 停止推送
- 入库通知与海报发送
- 命令交互（/search /stats /check）

**如何使用**
1. 创建 Bot 并获取 Token
2. 配置 `tg_bot_token` 与 `tg_chat_id`
3. 机器人加入频道或群组

**设置路径（通知与机器人页面）**
- 推送场景总控：`enable_bot` / `enable_notify` / `enable_library_notify`
- Telegram 通道：`tg_bot_token` / `tg_chat_id`
- 企业微信(推送)：`wecom_corpid` / `wecom_agentid` / `wecom_corpsecret` / `wecom_touser`
- 企微交互指令回调：`wecom_token` / `wecom_aeskey`

## 10. 系统运维

**功能说明**
- 可视化管理 Emby 计划任务
- 手动触发、查看执行状态
- 智能缓存策略

**如何使用**
1. 进入“系统运维”页面
2. 查看任务列表与状态
3. 手动触发需要的任务

**设置路径（系统设置页面）**
- TMDB & 数据库体检：`tmdb_api_key` / `proxy_url`
- Webhook 安全凭证：`webhook_token`
