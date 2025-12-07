# yt-dlp Download API

🚀 **FastAPI、Redis、PostgreSQL、Docker で構築された高機能ビデオ/オーディオダウンロード API**

日本語版。このプロジェクトは yt-dlp を活用した、プロダクション対応の非同期ダウンロードシステムです。

---

## 📋 目次

- [yt-dlp Download API](#yt-dlp-download-api)
  - [📋 目次](#-目次)
  - [✨ 機能](#-機能)
  - [🏗️ システム構成](#️-システム構成)
  - [🚀 クイックスタート](#-クイックスタート)
  - [🔧 環境変数設定](#-環境変数設定)
  - [📚 API エンドポイント](#-api-エンドポイント)
  - [🔐 JWT 認証](#-jwt-認証)
  - [⚙️ 機能フラグ](#️-機能フラグ)
  - [🎬 GPU エンコーディング](#-gpu-エンコーディング)
  - [⚡ aria2 統合](#-aria2-統合)
  - [🦀 Deno JavaScript ランタイム](#-deno-javascript-ランタイム)
  - [📊 ジョブ管理とキュー](#-ジョブ管理とキュー)
  - [🐳 Docker でのデプロイ](#-docker-でのデプロイ)
  - [🔗 サポートされているサイト](#-サポートされているサイト)
  - [📝 ライセンス](#-ライセンス)

---

## ✨ 機能

### コア機能

- ✅ **複数フォーマット対応**: MP3、MP4、WebM、WAV、FLAC、AAC、高品質、音声のみ、映像のみ
- ✅ **非同期処理**: `asyncio.create_subprocess_exec` による非ブロッキングダウンロード
- ✅ **リアルタイム進捗追跡**: WebSocket またはポーリング API での進捗確認
- ✅ **キュー管理**: Redis を活用した同時ダウンロード数の制限
- ✅ **レート制限**: IP ベースのレート制限（`.env` で設定可能）
- ✅ **自動クリーンアップ**: 古い完了タスクの自動削除
- ✅ **MP3 タグ編集**: MP3 ファイルへのタイトルとサムネイル埋め込み
- ✅ **タスク キャンセル**: 実行中のダウンロードを停止
- ✅ **字幕ダウンロード**: 複数言語での字幕抽出
- ✅ **ビデオ情報 API**: ダウンロードなしでメタデータ取得
- ✅ **GPU エンコーディング対応**: NVENC / Intel QSV / VAAPI ハードウェアアクセラレーション
- ✅ **aria2 統合**: 高速外部ダウンローダー対応
- ✅ **Deno JavaScript ランタイム**: yt-dlp-ejs と Deno による拡張 JS エンジン対応

### 技術スタック

| コンポーネント | 説明 |
|---|---|
| **バックエンド** | FastAPI（非同期フレームワーク） |
| **データベース** | PostgreSQL（タスク永続化） |
| **キャッシュ/キュー** | Redis（レート制限、キュー管理） |
| **ダウンローダー** | yt-dlp + ffmpeg / GPU + aria2 |
| **コンテナ化** | Docker + Docker Compose |

---

## 🏗️ システム構成

```
ytdlp-api/
├── app/                      # FastAPI アプリケーション
│   ├── main.py              # FastAPI の初期化とルータ登録
│   ├── endpoints.py          # ダウンロード関連エンドポイント
│   ├── auth_endpoints.py     # 認証・API キー管理エンドポイント
│   ├── progress_endpoints.py # 進捗追跡エンドポイント
│   ├── metrics_endpoints.py  # メトリクス・統計エンドポイント
│   ├── performance_endpoints.py # パフォーマンスモニタリング
│   ├── error_responses.py    # エラーハンドリング
│   ├── models.py             # Pydantic モデル定義
│   └── routes/              # ルータ定義
├── core/                     # コア機能
│   ├── config.py            # 環境変数と設定管理
│   └── ...                  # その他のコア機能
├── services/                # ビジネスロジック層
│   ├── download_service.py  # ダウンロード処理
│   ├── queue_service.py     # キュー管理
│   └── ...                  # その他のサービス
├── infrastructure/          # インフラストラクチャ
│   ├── database.py          # データベース接続
│   ├── redis.py             # Redis クライアント
│   └── ...                  # その他のインフラ
├── examples/                # 使用例とクライアント実装
├── wiki/                    # ドキュメンテーション
├── main.py                  # エントリーポイント
├── requirements.txt         # Python 依存パッケージ
├── Dockerfile               # Docker イメージ定義
├── docker-compose.yml       # Docker Compose 設定
├── .env.example             # 環境変数テンプレート
└── README.md               # このファイル
```

---

## 🚀 クイックスタート

### 前提条件

- Docker と Docker Compose
- または Python 3.10+、PostgreSQL、Redis

### Docker Compose での起動

1. **リポジトリをクローン**

```bash
git clone https://github.com/yunfie-twitter/ytdlp-api.git
cd ytdlp-api
```

2. **環境変数を設定**

```bash
cp .env.example .env
# .env ファイルを編集して必要な設定を行う
```

3. **Docker Compose で起動**

```bash
docker-compose up -d
```

4. **API にアクセス**

```
http://localhost:8000
```

Swagger UI ドキュメント: `http://localhost:8000/docs`

### ローカル開発環境での起動

1. **Python 依存パッケージをインストール**

```bash
pip install -r requirements.txt
```

2. **Redis と PostgreSQL を起動**

```bash
# Redis
redis-server

# PostgreSQL（別ターミナル）
# インストール済みの PostgreSQL サーバーを起動
```

3. **.env ファイルを設定**

```bash
cp .env.example .env
# 開発環境に合わせて編集
```

4. **API を起動**

```bash
python main.py
```

---

## 🔧 環境変数設定

### API 設定

```env
HOST=0.0.0.0                    # バインドするホスト
PORT=8000                       # バインドするポート
RELOAD=false                    # 開発時に true で自動リロード
```

### CORS 設定

```env
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### データベース設定

```env
# SQLite（開発用）
DATABASE_URL=sqlite:///./download_tasks.db

# PostgreSQL（本番用）
DATABASE_URL=postgresql://user:password@localhost:5432/ytdlp_api
```

### Redis 設定

```env
REDIS_URL=redis://localhost:6379
```

### ダウンロード設定

```env
DOWNLOAD_DIR=./downloads        # ダウンロード保存先
MAX_CONCURRENT_DOWNLOADS=3      # 同時ダウンロード数
AUTO_DELETE_AFTER=604800        # 自動削除間隔（秒、デフォルト 7 日）
```

### レート制限

```env
RATE_LIMIT_PER_MINUTE=60        # 1分あたりのリクエスト数制限
```

### セキュリティ

```env
SECRET_KEY=your-secret-key-change-in-production
```

---

## 📚 API エンドポイント

### ダウンロード関連

#### 動画情報取得
```http
GET /api/video-info?url={video_url}
```

動画のメタデータをダウンロードなしで取得します。

**クエリパラメータ:**
- `url` (required): 動画の URL
- `language` (optional): 字幕言語（例: ja, en）

**レスポンス例:**
```json
{
  "url": "https://example.com/video",
  "title": "動画タイトル",
  "duration": 3600,
  "thumbnail": "https://example.com/thumb.jpg",
  "formats": [
    {"format_id": "18", "format": "video/mp4", "resolution": "360p"},
    {"format_id": "22", "format": "video/mp4", "resolution": "720p"}
  ]
}
```

#### ダウンロード開始
```http
POST /api/download
```

新しいダウンロードタスクを作成します。

**リクエストボディ:**
```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "format": "mp3",
  "quality": "best",
  "include_subtitles": true,
  "subtitle_languages": ["ja", "en"],
  "custom_format_id": null,
  "embed_metadata": true,
  "embed_thumbnail": true
}
```

**パラメータ説明:**
- `url` (required): ダウンロード対象の URL
- `format` (optional): `mp3`, `mp4`, `webm`, `wav`, `flac`, `aac`, `audio_only`, `video_only`、デフォルト: `mp3`
- `quality` (optional): `best`, `audio_best`、デフォルト: `best`
- `include_subtitles` (optional): 字幕を含めるか、デフォルト: `false`
- `subtitle_languages` (optional): 字幕言語リスト、デフォルト: `["auto"]`
- `custom_format_id` (optional): yt-dlp のカスタム format_id
- `embed_metadata` (optional): MP3 にメタデータを埋め込むか、デフォルト: `true`
- `embed_thumbnail` (optional): サムネイルを埋め込むか、デフォルト: `true`

**レスポンス:**
```json
{
  "task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "status": "queued",
  "created_at": "2024-01-15T10:30:00Z",
  "estimated_duration": "00:05:30"
}
```

#### ダウンロード状態確認（ポーリング）
```http
GET /api/status/{task_id}
```

**レスポンス:**
```json
{
  "task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "status": "downloading",
  "progress": {
    "percentage": 45.5,
    "downloaded_bytes": 45000000,
    "total_bytes": 100000000,
    "speed": 1000000,
    "eta": "00:01:30"
  },
  "filename": "video_title.mp3",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### WebSocket での進捗リアルタイム追跡
```websocket
WS /ws/progress/{task_id}
```

WebSocket で接続するとリアルタイム進捗情報が配信されます。

#### ファイルダウンロード
```http
GET /api/download/{task_id}
```

完了したタスクのファイルをダウンロード。

#### タスクキャンセル
```http
POST /api/cancel/{task_id}
```

実行中のダウンロードをキャンセルします。

#### タスク削除
```http
DELETE /api/delete/{task_id}
```

タスクと関連ファイルを削除します。

#### タスク一覧
```http
GET /api/tasks?status=completed&limit=20&offset=0
```

すべてのタスクを一覧表示します。

**クエリパラメータ:**
- `status` (optional): `queued`, `downloading`, `completed`, `failed`, `cancelled`
- `limit` (optional): 1 ページあたりのアイテム数、デフォルト: 20
- `offset` (optional): オフセット、デフォルト: 0

---

### キュー・メトリクス関連

#### キュー統計
```http
GET /api/queue/stats
```

**レスポンス:**
```json
{
  "queued": 5,
  "downloading": 2,
  "completed": 150,
  "failed": 3,
  "total_completed_today": 45,
  "average_speed": 2500000,
  "estimated_wait_time": "00:15:30"
}
```

#### パフォーマンス統計
```http
GET /api/metrics/performance
```

CPU、メモリ、ディスク使用率などのメトリクスを取得。

---

## 🔐 JWT 認証

### API キーの有効化

`.env` で以下を設定:

```env
ENABLE_JWT_AUTH=true
API_KEY_ISSUE_PASSWORD=your-secure-password
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DAYS=30
```

### API キーの発行

```http
POST /auth/issue-key
```

**リクエストボディ:**
```json
{
  "password": "your-secure-password"
}
```

**レスポンス:**
```json
{
  "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2024-02-14T10:30:00Z"
}
```

### API キーの使用

すべてのリクエストの `Authorization` ヘッダーに含めます:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

または、クエリパラメータ:

```http
GET /api/status/task_id?api_key=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### API キー管理

#### キーの有効化・無効化
```http
POST /auth/toggle-key/{key_id}
```

#### API キー一覧
```http
GET /auth/keys
```

---

## ⚙️ 機能フラグ

`.env` で個別機能の有効化・無効化が可能です:

```env
# ビデオ情報エンドポイント
ENABLE_FEATURE_VIDEO_INFO=true

# ダウンロードエンドポイント
ENABLE_FEATURE_DOWNLOAD=true

# ステータス確認エンドポイント
ENABLE_FEATURE_STATUS=true

# ファイルダウンロードエンドポイント
ENABLE_FEATURE_FILE_DOWNLOAD=true

# タスクキャンセル
ENABLE_FEATURE_CANCEL=true

# タスク削除
ENABLE_FEATURE_DELETE=true

# タスク一覧表示
ENABLE_FEATURE_LIST_TASKS=true

# 字幕ダウンロード
ENABLE_FEATURE_SUBTITLES=true

# サムネイル取得
ENABLE_FEATURE_THUMBNAIL=true

# キュー統計
ENABLE_FEATURE_QUEUE_STATS=true

# WebSocket サポート
ENABLE_FEATURE_WEBSOCKET=true

# MP3 メタデータ埋め込み
ENABLE_FEATURE_MP3_METADATA=true

# サムネイル埋め込み
ENABLE_FEATURE_THUMBNAIL_EMBED=true

# GPU エンコーディング
ENABLE_FEATURE_GPU_ENCODING=true

# aria2 ダウンローダー
ENABLE_FEATURE_ARIA2=true

# カスタムフォーマット選択
ENABLE_FEATURE_CUSTOM_FORMAT=true

# 画質選択
ENABLE_FEATURE_QUALITY_SELECTION=true

# プロキシサポート
ENABLE_FEATURE_PROXY=true

# Cookie サポート
ENABLE_FEATURE_COOKIES=true
```

不要な機能を無効化することで、攻撃面を減らせます。

---

## 🎬 GPU エンコーディング

ビデオをハードウェアアクセラレーションでエンコードし、CPU 使用率を大幅削減します。

### 設定方法

```env
ENABLE_GPU_ENCODING=true
GPU_ENCODER_TYPE=auto        # auto / nvenc / vaapi / qsv
GPU_ENCODER_PRESET=fast      # ultrafast / superfast / veryfast / faster / fast / medium / slow / slower
```

### エンコーダータイプ

| エンコーダー | 対応 GPU |
|---|---|
| **nvenc** | NVIDIA（GeForce RTX など） |
| **vaapi** | AMD、Intel 統合 GPU |
| **qsv** | Intel Quick Sync Video |
| **auto** | 自動検出 |

### 使用例

```bash
# リクエスト時にパラメータで指定
POST /api/download
{
  "url": "https://youtube.com/...",
  "format": "mp4",
  "use_gpu_encoding": true
}
```

---

## ⚡ aria2 統合

大規模ファイルを高速ダウンロードするため、aria2 統合が利用可能です。

### 前提条件

aria2c がインストールされていること:

```bash
# Ubuntu/Debian
sudo apt-get install aria2

# macOS
brew install aria2

# Docker イメージには自動的に含まれます
```

### 設定方法

```env
ENABLE_ARIA2=true
ARIA2_MAX_CONNECTIONS=4      # 並列接続数（推奨: 4-8）
ARIA2_SPLIT=4                # 同時分割ダウンロード数（推奨: 4）
```

### メリット

- **高速化**: 複数接続による並列ダウンロード
- **低レイテンシ**: 効率的な帯域幅利用
- **レジューム機能**: 中断したダウンロードを再開

---

## 🦀 Deno JavaScript ランタイム

yt-dlp-ejs を使用した拡張 JavaScript エンジンで、複雑なサイト対応を実現。

### 設定方法

```env
ENABLE_DENO=true
DENO_PATH=/usr/local/bin/deno  # Deno のパス（デフォルト値）
```

### Deno のインストール

```bash
# Linux/macOS
curl -fsSL https://deno.land/install.sh | sh

# Docker イメージには自動的に含まれます
```

### メリット

- **JavaScript 互換性向上**: yt-dlp-ejs で拡張サイト対応
- **エラー耐性**: Deno の強い型チェック
- **安全性**: サンドボックス化された実行環境

---

## 📊 ジョブ管理とキュー

### キュー管理

同時ダウンロード数は `MAX_CONCURRENT_DOWNLOADS` で制限されます。

```env
MAX_CONCURRENT_DOWNLOADS=3
```

超過分は Redis キューで管理され、順番に処理されます。

### 自動クリーンアップ

古い完了タスクは自動削除されます:

```env
AUTO_DELETE_AFTER=604800  # 7 日（秒単位）
```

### タスク情報の永続化

すべてのタスクは PostgreSQL に永続化され、サーバー再起動後も復旧可能です。

---

## 🐳 Docker でのデプロイ

### 単一コンテナでの起動

```bash
docker build -t ytdlp-api .
docker run -d \
  -p 8000:8000 \
  -v ./downloads:/app/downloads \
  -e DATABASE_URL=sqlite:///./download_tasks.db \
  ytdlp-api
```

### Docker Compose でのマルチコンテナ構成

```bash
docker-compose up -d
```

**docker-compose.yml** の例:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:password@postgres:5432/ytdlp
      REDIS_URL: redis://redis:6379
    volumes:
      - ./downloads:/app/downloads
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: ytdlp
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### 本番環境での注意事項

1. **SECRET_KEY を変更**

```env
SECRET_KEY=$(openssl rand -hex 32)
```

2. **CORS_ORIGINS を制限**

```env
CORS_ORIGINS=https://yourdomain.com
```

3. **API キーを有効化**

```env
ENABLE_JWT_AUTH=true
API_KEY_ISSUE_PASSWORD=your-secure-password
```

4. **不要な機能を無効化**

セキュリティのため、不要な機能フラグを false に設定。

5. **ログレベルを設定**

```env
LOG_LEVEL=info  # debug / info / warning / error
```

---

## 🔗 サポートされているサイト

yt-dlp に対応したすべてのサイトでダウンロード可能です。

主要サイト:
- YouTube
- Bilibili
- Twitter/X
- TikTok
- Instagram
- Vimeo
- Dailymotion
- 他数百のサイト

完全なサポートサイト一覧は[公式ドキュメント](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)を参照。

---

## 📝 ライセンス

このプロジェクトは Apache 2.0 ライセンスの下で公開されています。

詳細は [LICENSE](LICENSE) ファイルを参照してください。

---

## 📧 サポート・問題報告

問題や機能リクエストは [GitHub Issues](https://github.com/yunfie-twitter/ytdlp-api/issues) で報告してください。
