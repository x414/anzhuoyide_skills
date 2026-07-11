[English](./README.md)| [中文文档]

**anzhuoyide_skills**包括以下skill，适用于主流Agent（Claude Code, Codex, OpenClaw, Hermes等），并会不断丰富和完善：

**1. 两个开胃小菜：**

**video-summary-skill** ---分析总结音视频的内容，只需给出链接，即可输出高质量的分析总结

**libai-versify** ---以李白的风格、结合上下文根据需求作诗

更多详细介绍：https://mp.weixin.qq.com/s/nw-O3A5AMiyGbYGpAdSXPg

**2. 10亿Token迭代出的自动获取项目上下文的skill**（适用于任意类型的项目，无需任何特别授权，登录网页版飞书后即可自动进行）

**feishu-project-doc-analyse** ---自动搜索项目相关的飞书文档，分析内容，总结出高质量的项目报告，让Agent根据飞书文档全面获取项目的上下文。用法：“用feishu-project-doc-analyse分析xxx项目”

**feishu-project-chat-analyse** ---自动搜索项目相关的飞书群，分析对话内容，总结出高质量的项目报告，让Agent根据飞书群聊信息全面获取项目的上下文。用法：“用feishu-project-chat-analyse分析xxx项目”
*PS：尽管这两个skill中已经明确要求获取所有相关内容，但实际使用中，大模型有时还是有“惰性”，好在执行结果中它会提示“只提取了一部分的文档或者群聊”，那么再主动提示它继续提取就好了*

**作者公众号**：安卓一得，分享各种Agent实战经验，欢迎交流~
