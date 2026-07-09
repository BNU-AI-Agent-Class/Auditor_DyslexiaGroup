# 小航阅读小伙伴 · 后端

帮助三、四年级阅读落后小朋友完成识读率测验，并推荐合适的书籍。

---

## 目录结构

```
backend/
├── main.py                    # FastAPI 主程序
├── xiaohang_agent_v2.py       # 核心 Agent 逻辑
├── agent.md                   # Agent 人设
├── skill_危机转介.md          # 危机转介 skill（置顶）
├── requirements.txt           # Python 依赖
├── .env                       # 环境变量配置
└── skills/
    └── skill_危机转介.md      # skills 版本（备用）
```

**数据文件**（在上级 `data/` 目录）：
```
data/
├── 覆盖率&识读率网页版/
│   ├── 3600字2020册数.xlsx
│   ├── 平衡语料库字频表计算用.xlsx
│   └── 抽取比例设置.xlsx
└── 识读率文本/
    ├── 3生活故事&神话寓言/
    ├── 4生活故事&神话寓言/
    ├── 5-1童话&诗歌/
    ├── 5-2生活故事&神话寓言/
    ├── 5-3生活故事&散文/
    └── 6-1生活故事&散文/
```

---

## 快速启动

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件，填入你的 DeepSeek API Key：

```bash
DEEPSEEK_API_KEY=sk-your-api-key-here
```

### 3. 启动服务

```bash
uvicorn main:app --reload --port 8000
```

### 4. 测试

```bash
# 健康检查
curl http://localhost:8000/api/health

# 对话测试
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": null, "message": "你好"}'
```

---

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/health` | GET | 健康检查 |
| `POST /api/chat` | POST | 对话 |
| `DELETE /api/session/{id}` | DELETE | 删除会话 |

### POST /api/chat

**请求：**
```json
{
  "session_id": null,
  "message": "你好"
}
```

**响应：**
```json
{
  "session_id": "abc123",
  "reply": "你好呀！我是你的阅读小伙伴...",
  "state": "ASK_SEMESTER",
  "meta": {"crisis": false}
}
```

---

## 危机检测

服务会在入口和出口各检测一次危机信号。触发红灯时返回转介话术：

> "我们先不读了，没关系的。如果你有需要，一定要告诉爸爸妈妈、老师或学校心理老师。也可以拨打心理援助热线：**400-161-9995**（24小时）。"

---

## MIT License

郑先隽，北京师范大学心理学部教授，人本 AI 设计与创新
