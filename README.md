# IPTV Cleaner

基于 IPTV-ORG 的自动检测与筛选方案。

功能：

- 自动获取 IPTV-ORG 中国大陆频道
- 自动获取 IPTV-ORG 香港频道
- 自动获取 IPTV-ORG 澳门频道
- 自动获取 IPTV-ORG 台湾频道
- 自动去重
- 自动检测可访问性
- 自动检测真实视频流
- 按地区输出 M3U
- GitHub Actions 自动更新
- 支持 IPTV 播放器直接订阅

---

# 项目结构

```text
.
├── .github
│   └── workflows
│       └── update.yml
├── check.py
├── requirements.txt
├── cleaned.m3u
└── README.md
```

---

# 数据来源

项目使用 IPTV-ORG 官方公开播放列表：

中国大陆

https://iptv-org.github.io/iptv/countries/cn.m3u

香港

https://iptv-org.github.io/iptv/countries/hk.m3u

澳门

https://iptv-org.github.io/iptv/countries/mo.m3u

台湾

https://iptv-org.github.io/iptv/countries/tw.m3u

---

# 工作流程

```text
IPTV-ORG
    ↓
下载频道列表
    ↓
频道去重
    ↓
HTTP检测
    ↓
视频分片检测
    ↓
输出有效频道
    ↓
生成 cleaned.m3u
    ↓
自动提交到仓库
```

---

# 频道分组

生成结果：

```text
# ===== 大陆 =====

CCTV
卫视
地方台

# ===== 香港 =====

RTHK
HOY
凤凰

# ===== 澳门 =====

澳视澳门
澳视资讯

# ===== 台湾 =====

公视
华视
中视
民视
TVBS
```

实际内容取决于 IPTV-ORG 当前收录情况。

---

# 检测逻辑

第一阶段：

```text
HTTP检测
```

判断：

```text
HTTP 200
```

进入下一步。

若返回：

```text
404
403
500
超时
```

直接剔除。

---

第二阶段：

```text
视频分片检测
```

解析 m3u8 播放列表，
取第一个分片并实际下载首块数据
（多码率 Master 列表会自动向下解析一层）。

判断：

```text
HTTP 200
且首块数据 >= 3000 字节
```

满足条件：

```text
保留
```

不满足：

```text
剔除
```

---

# 性能优化

当前配置：

```python
THREADS = 32

HTTP_TIMEOUT = (3, 5)

MIN_VALID_CHANNELS = 10
```

特点：

- 多线程并发检测
- 自动去重
- 优先淘汰无效频道

---

# GitHub Actions

自动运行时间：

```text
北京时间
06:00
18:00
```

也可以手动运行：

```text
Actions
↓
IPTV Cleaner
↓
Run workflow
```

---

# 部署步骤

## 1 创建仓库

例如：

```text
iptv-cleaner
```

---

## 2 上传文件

上传：

```text
check.py

requirements.txt

.github/workflows/update.yml
```

---

## 3 推送到 GitHub

```bash
git add .
git commit -m "init"
git push
```

---

## 4 启动 Action

进入：

```text
Actions
```

点击：

```text
Run workflow
```

首次运行会生成：

```text
cleaned.m3u
```

---

# 播放器使用

Raw 文件地址：

```text
https://raw.githubusercontent.com/你的用户名/你的仓库/main/cleaned.m3u
```

例如：

```text
https://raw.githubusercontent.com/abc/iptv-cleaner/main/cleaned.m3u
```

播放器添加：

名称：

```text
我的电视源
```

地址：

```text
https://raw.githubusercontent.com/abc/iptv-cleaner/main/cleaned.m3u
```

---

# 更新策略

当前策略：

```text
检测成功
↓
保留

检测失败
↓
删除
```

保护机制：

```text
有效频道总数低于 10
↓
判定为检测异常
↓
放弃写入并退出
↓
保留上一版本 cleaned.m3u
```

后续计划：

```text
连续3次失败
↓
删除

检测恢复
↓
自动恢复频道
```

---

# 已知问题

部分频道可能存在：

```text
地域限制

CDN限制

临时维护

夜间停播

短时失效
```

因此不保证所有频道长期有效。

---

# 后续规划

计划增加：

- state.json 缓存
- 连续失败计数
- 自动恢复频道
- EPG 节目单
- 频道 Logo
- Favorites 精选频道列表
- GitHub Pages 发布
- M3U8 健康度评分
- 历史可用率统计

---

# License

仅用于研究 IPTV 技术及公开播放列表处理流程。

不存储任何视频内容。

所有频道链接均来自第三方公开数据源。
