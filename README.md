# 文件说明
基于 Python Flask 的金融理财社区后端项目

# 技术概括
### 1. 后端框架
- Flask - 轻量级 Python Web 框架
- Flask-CORS - 处理前后端跨域请求
- Flask-SQLAlchemy - ORM 数据库操作工具
### 2. 数据库
- SQLite - 轻量级关系型数据库
- ORM 建模 - 使用 SQLAlchemy 进行数据模型设计
### 3. 安全认证
- JWT (JSON Web Token) - 无状态身份认证
- Werkzeug - 密码加密与校验
- 装饰器鉴权 - 接口级别的权限控制
### 4. AI 集成
- OpenAI SDK - 集成 DeepSeek 大语言模型
- 流式响应 - 支持 SSE 实时推送

# 核心模块

1. 设计并搭建基于 Flask 的 RESTful API 架构，负责从用户注册登录、资产管理到社区互动等 10+ 个核心接口的开发。

2. 深度集成 DeepSeek 大模型，利用 SSE (Server-Sent Events) 流式传输技术 实现 AI 理财助手的秒级响应，优化了长文本生成的交互体验。

3. 设计关系型数据库模型 (ORM)，独立完成用户、资产记录、社区帖子等多表关联查询逻辑，并编写数据初始化脚本（Seed Script）确保开发环境数据一致性。

4. 实现基于 JWT 的登录鉴权体系，通过自定义 Python 装饰器（Decorator）实现路由级别的权限校验，保障了金融数据的访问安全。

5. 处理跨域 (CORS) 与响应头优化，针对移动端环境配置了 keep-alive 与 no-cache，解决了流式数据传输中的卡顿与缓存干扰问题。
