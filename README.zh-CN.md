# GlucoPI（控糖派）

[English](./README.md)

<p align="center">
  <img src="./docs/screenshots/glucopi-cover.png" alt="GlucoPI cover" width="220">
</p>

<p align="center">
  一个面向糖尿病健康管理的微信小程序，集成了数据记录、医患随访、实时聊天与短时血糖预测。
</p>

## 项目简介

GlucoPI（控糖派）是一个本科毕业设计项目，采用微信小程序前端和 FastAPI 后端的前后端分离架构，面向糖尿病患者的日常健康管理场景。

项目主要围绕三件事展开：

- 更方便地记录和查看血糖相关数据
- 支持患者与医生之间的持续沟通和随访
- 提供短时血糖预测与健康问答辅助能力

## 核心功能

- 微信小程序端的移动化健康管理体验
- 患者端与医生端双角色支持
- 血糖、饮食、胰岛素等健康数据记录
- 血糖趋势展示与短时预测
- 医患实时聊天与消息交互
- 基于大模型的健康助手能力

## 功能截图

<p align="center">
  <img src="./docs/screenshots/login-and-profile.png" alt="Login and profile" width="860">
</p>

<p align="center">
  <img src="./docs/screenshots/data-records.png" alt="Data records" width="860">
</p>

<p align="center">
  <img src="./docs/screenshots/glucose-trends.jpeg" alt="Glucose trends" width="240">
  <img src="./docs/screenshots/glucose-prediction.jpeg" alt="Glucose prediction" width="240">
</p>

<p align="center">
  <img src="./docs/screenshots/realtime-chat.png" alt="Real-time chat" width="520">
</p>

<p align="center">
  <img src="./docs/screenshots/doctor-followup.png" alt="Doctor follow-up" width="860">
</p>

## 仓库结构

```text
glucopi/
├─ backend/                # FastAPI 后端服务
├─ frontend/miniprogram/   # 微信小程序前端
└─ docs/                   # 截图与文档资源
```

## 技术栈

- 前端：微信小程序、JavaScript、LESS、TDesign Mini Program
- 后端：FastAPI、SQLAlchemy、Motor、MySQL、MongoDB
- AI / 预测：兼容 OpenAI 的 LLM 接口、PyTorch、NumPy、Pandas

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend/miniprogram
npm install
```

然后修改 `frontend/miniprogram/utils/api-config.js` 中的 HTTP 和 WebSocket 地址，再用微信开发者工具导入项目。

## 说明

- 当前仓库已经过 GitHub 上传前清理。
- `.env`、`node_modules`、`miniprogram_npm`、微信私有工程配置等本地文件已排除。
- 后端部分功能依赖数据库、模型检查点和外部服务密钥。

## 致谢与说明

本项目中的血糖预测部分参考了 [r-cui/GluPred](https://github.com/r-cui/GluPred) 仓库，即论文 “Personalised Short-Term Glucose Prediction via Recurrent Self-Attention Network” 的官方实现。

预测相关数据集使用的是 OhioT1DM 数据集。

## 许可

本项目采用 MIT License，详见 [LICENSE](./LICENSE)。
