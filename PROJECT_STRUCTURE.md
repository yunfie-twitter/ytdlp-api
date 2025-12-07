# Project Structure

このドキュメントでは、ytdlp-api プロジェクトの整理された構造を説明します。

## ディレクトリ構成

```
ytdlp-api/
├── app/                          # FastAPI アプリケーション
│   ├── __init__.py
│   ├── main.py                   # FastAPI アプリケーションファクトリ
│   ├── models.py                 # Pydantic リクエスト/レスポンスモデル
│   └── routes/                   # API ルート (将来の拡張用)
│       └── __init__.py
│
├── core/                         # コア機能
│   ├── __init__.py
│   ├── config.py                 # 設定管理 (BaseSettings)
│   └── security.py               # セキュリティ関連 (レート制限など)
│
├── services/                     # ビジネスロジック
│   ├── __init__.py
│   ├── download_service.py       # yt-dlp ダウンロード処理
│   └── queue_worker.py           # キューワーカー
│
├── infrastructure/               # 外部サービス統合
│   ├── __init__.py
│   ├── database.py               # SQLAlchemy ORMとデータベース
│   ├── redis_manager.py          # Redis 接続と操作
│   └── websocket_manager.py      # WebSocket 接続管理
│
├── main.py                       # エントリーポイント
├── Dockerfile                    # Docker イメージ定義
├── docker-compose.yml            # Docker Compose 設定
├── requirements.txt              # Python 依存関係
├── .env.example                  # 環境変数テンプレート
├── README.md                     # プロジェクト説明
├── LICENSE                       # ライセンス
└── PROJECT_STRUCTURE.md          # このファイル
```

## パッケージの役割

### `app/` - FastAPI アプリケーション

**役割**: REST API の定義とエンドポイント管理

- `main.py`: FastAPI アプリケーションファクトリ
  - すべての API エンドポイントの定義
  - ミドルウェア の設定
  - スタートアップ/シャットダウン処理
  
- `models.py`: Pydantic モデル
  - リクエストバリデーション
  - レスポンス型定義
  - OpenAPI ドキュメント自動生成

- `routes/`: API ルート (モジュール化用)
  - 将来的にエンドポイントを分割できる構造

### `core/` - コア機能

**役割**: アプリケーション全体で使用される基本機能

- `config.py`: 設定管理
  - 環境変数からの設定読み込み (pydantic-settings)
  - 設定値のバリデーション
  - 型安全な設定アクセス
  
- `security.py`: セキュリティ機能
  - IP ベースのレート制限
  - 認証・認可機能 (将来の拡張)

### `services/` - ビジネスロジック

**役割**: 核となるビジネスロジックの実装

- `download_service.py`: ダウンロード機能
  - yt-dlp との連携
  - ビデオ情報取得
  - ダウンロード処理
  - MP3 タグ付け
  - サブタイトル取得
  
- `queue_worker.py`: キュー管理
  - ダウンロードキューの処理
  - 同時ダウンロード数の制御
  - 完了/失敗タスクのクリーンアップ

### `infrastructure/` - 外部サービス統合

**役割**: データベース、キャッシュ、通信などの外部サービス連携

- `database.py`: データベース
  - SQLAlchemy ORM 定義
  - DownloadTask モデル
  - データベース初期化・セッション管理
  
- `redis_manager.py`: Redis
  - 接続管理
  - キュー操作 (FIFO)
  - キャッシュ操作
  - WebSocket 接続管理
  
- `websocket_manager.py`: WebSocket
  - リアルタイム接続の管理
  - メッセージ配信

## 依存関係の流れ

```
main.py (エントリーポイント)
    ↓
app/main.py (FastAPI アプリケーション)
    ↓
├─→ core/config.py (設定)
├─→ core/security.py (セキュリティ)
├─→ app/models.py (リクエスト/レスポンス)
├─→ services/download_service.py (ダウンロード処理)
│       ↓
│       ├─→ infrastructure/database.py
│       ├─→ infrastructure/redis_manager.py
│       └─→ core/config.py
│
├─→ services/queue_worker.py (キューワーカー)
│       ↓
│       ├─→ services/download_service.py
│       ├─→ infrastructure/database.py
│       ├─→ infrastructure/redis_manager.py
│       └─→ core/config.py
│
└─→ infrastructure/ (データベース、Redis、WebSocket)
        ↓
        core/config.py
```

## 設定管理

設定は `core/config.py` で一元管理されます。

```python
from core.config import settings

# 設定の使用例
download_dir = settings.DOWNLOAD_DIR
max_concurrent = settings.MAX_CONCURRENT_DOWNLOADS
```

環境変数は `.env` ファイルで設定します:

```bash
DATABASE_URL=sqlite:///./test.db
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
SECRET_KEY=your-secret-key-here
```

## インポート例

### 適切なインポート

```python
# ✅ 良い例
from core.config import settings
from infrastructure.database import get_db, DownloadTask
from services.download_service import download_service
from infrastructure.redis_manager import redis_manager
```

### 避けるべきインポート

```python
# ❌ 悪い例 - 循環依存の可能性
from app.main import app  # services からのインポートは避ける
```

## スケーリング戦略

### 新しいサービスを追加する場合

1. `services/` に新しいサービスファイルを作成
2. 依存関係を注入する仕組みを整える
3. `app/main.py` で利用する

例:

```python
# services/email_service.py
class EmailService:
    async def send_notification(self, task_id: str):
        pass

email_service = EmailService()
```

### 新しいエンドポイントを追加する場合

1. エンドポイント関連のモデルを `app/models.py` に追加
2. `app/routes/` 配下に新しいルートファイルを作成 (オプション)
3. `app/main.py` でエンドポイントを定義

## テスト戦略

各パッケージの単位テスト:

```
tests/
├── test_core/
│   ├── test_config.py
│   └── test_security.py
├── test_services/
│   ├── test_download_service.py
│   └── test_queue_worker.py
├── test_infrastructure/
│   ├── test_database.py
│   ├── test_redis_manager.py
│   └── test_websocket_manager.py
└── test_app/
    └── test_main.py
```

## 移行ガイド (v1.0.2)

### 古い構造 → 新しい構造

| ファイル | 新しい場所 | 変更点 |
|---------|----------|--------|
| `main.py` | `app/main.py` | アプリケーション定義 |
| `config.py` | `core/config.py` | 設定管理 |
| `database.py` | `infrastructure/database.py` | DB接続 |
| `redis_manager.py` | `infrastructure/redis_manager.py` | Redis管理 |
| `websocket_manager.py` | `infrastructure/websocket_manager.py` | WS管理 |
| `download_service.py` | `services/download_service.py` | ダウンロード処理 |
| `queue_worker.py` | `services/queue_worker.py` | キュー処理 |
| `rate_limiter.py` | `core/security.py` | セキュリティ |

### インポート更新例

**変更前:**
```python
from config import settings
from database import get_db
from download_service import download_service
```

**変更後:**
```python
from core.config import settings
from infrastructure.database import get_db
from services.download_service import download_service
```

## ベストプラクティス

1. **単一責任**: 各モジュールは 1 つの役割に専念する
2. **依存性注入**: グローバル状態より依存性注入を優先
3. **型ヒント**: すべての関数に型ヒントを付与
4. **ロギング**: 適切なログレベルでログを出力
5. **エラーハンドリング**: 予期しないエラーも適切に処理
6. **テスト可能性**: サービスは単体テストできるように設計

---

**Version**: 1.0.2  
**Last Updated**: 2025-12-07
