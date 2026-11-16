# Cloud Run 部署

后端镜像见 `backend/Dockerfile`。Cloud Run 是无状态容器，**SQLite 和本地 `data/`
目录会在实例重启后丢失**，正式部署请使用 Cloud SQL PostgreSQL；文件上传目前仍落本地
磁盘，需要长期保存时要接对象存储（尚未实现）。

## 1. 准备 Cloud SQL PostgreSQL

```bash
gcloud sql instances create kaogong-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=asia-east1

gcloud sql databases create kaogong --instance=kaogong-db
gcloud sql users set-password postgres --instance=kaogong-db --password='换成强密码'
```

## 2. 构建并部署

在仓库根目录执行：

```bash
gcloud run deploy kaogong-backend \
  --source backend \
  --region asia-east1 \
  --allow-unauthenticated \
  --add-cloudsql-instances PROJECT_ID:asia-east1:kaogong-db \
  --set-env-vars APP_SECRET_KEY='换成随机长字符串' \
  --set-env-vars MOCK_LLM=0 \
  --set-env-vars CORS_ORIGINS='https://你的前端域名' \
  --set-env-vars DATABASE_URL='postgresql+asyncpg://postgres:密码@/kaogong?host=/cloudsql/PROJECT_ID:asia-east1:kaogong-db'
```

部署完成后记下服务 URL，例如
`https://kaogong-backend-xxxxx.a.run.app`。

## 3. 前端

前端是独立的 Next.js 应用，可部署到 Vercel 或 Cloud Run：

```bash
NEXT_PUBLIC_API_BASE_URL=https://kaogong-backend-xxxxx.a.run.app
```

把前端域名加入后端的 `CORS_ORIGINS`。SSE 通过标准 HTTP 流式返回，Cloud Run 支持；
如前置 CDN，需要关闭响应缓冲。

## 4. 本地验证镜像

```bash
docker build -t kaogong-backend backend
docker run --rm -p 8080:8080 \
  -e MOCK_LLM=1 \
  -e APP_SECRET_KEY=dev-secret-change-me \
  kaogong-backend
```

打开 <http://localhost:8080/api/health> 应返回 `{"status":"ok"}`。

## 5. 注意事项

- 多用户目前是“本地学习者档案”，没有登录鉴权；公网部署前务必加认证（如 IAP 或自建登录）。
- 图片 OCR 在 Linux 镜像里没有 macOS Vision，会回退 tesseract；中文识别需要镜像内安装
  `tesseract-ocr-chi-sim`。
- 音频转写复用 LLM 的 Base URL / API Key 调用 `/audio/transcriptions`；也可在镜像里
  安装 `faster-whisper` 做本地转写。
- 上传资料默认写在容器本地磁盘，Cloud Run 实例缩容后会丢失，后续接 GCS。
