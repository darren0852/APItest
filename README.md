# AI API Platform

马来西亚 AI API 中转站。前端使用 Next.js，后端使用 FastAPI，基础服务为 PostgreSQL + Redis。

## 本地启动

```bat
start.bat
```

`start.bat` 会启动 PostgreSQL、Redis、本地 mock supplier、FastAPI 和 Next.js，并执行一次前端生产构建。

## 生产部署

1. 在服务器只启动必要基础服务：

```bat
cd infra
docker compose up -d
```

`mock-provider` 有 `dev` profile，所以生产默认不会启动。

2. 启动后端前设置环境变量：

```ini
DB_USER=<database_user>
DB_PASS=<database_password>
DB_HOST=<database_host>
DB_PORT=5432
DB_NAME=apiplatform
REDIS_URL=redis://<redis-host>:6379/0
ENABLE_INTERNAL_MOCK=false
JWT_SECRET=<64-character-random-secret>
```

`JWT_SECRET` 必须替换。供应商 API Key 使用它加密保存；更换密钥前必须重新加密旧 Key。

3. 启动后端和前端：

```bat
cd apps\api
python -m uvicorn main:app --host 0.0.0.0 --port 8000

cd apps\web
npm ci
npm run build
npm run start
```

4. 到 Admin → 模型连接，为每个售卖模型配置上游模型 ID、上游 API Key、上游端点。

## 计费规则

钱包和账本内部使用 RM 8 位小数，用户界面显示 RM 两位。每笔请求按供应商 usage 计费：

```text
actual_cost =
  (输入Tokens - 缓存创建Tokens - 缓存读取Tokens) × 输入售价
  + 缓存读取Tokens × 缓存读取售价
  + 缓存创建Tokens × 缓存创建售价
  + 输出Tokens × 输出售价
```

OpenAI 协议读取 `prompt_tokens_details.cached_tokens`；Anthropic 协议的 `cache_read_input_tokens` 和 `cache_creation_input_tokens` 会被标准化后进入同一套结算。

## 自动验证

```bat
python -m pytest tests -q
npm run build
```
