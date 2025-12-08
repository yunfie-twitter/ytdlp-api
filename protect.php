<?php
// ========== CORS ヘッダー設定（最初に実行）==========
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: ALLOW-FROM https://noctella.fun');
header('X-XSS-Protection: 1; mode=block');

// ========== Config を先に読み込む（session_start() 前）==========
require_once 'config.php';

// ========== session_start() の前に設定 ==========
ini_set('session.use_strict_mode', '1');
ini_set('session.cookie_httponly', '1');
ini_set('session.cookie_secure', '1');
ini_set('session.cookie_samesite', 'Strict');

if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

class LinkValidator {
    private $pdo;
    private $token;
    private const SESSION_TIMEOUT = 3600; // 1時間
    
    public function __construct() {
        global $pdo;
        $this->pdo = $pdo;
    }
    
    // Device Fingerprint を生成
    public function generateFingerprint() {
        $fingerprint_data = [
            'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? '',
            'accept_language' => $_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? '',
            'accept_encoding' => $_SERVER['HTTP_ACCEPT_ENCODING'] ?? '',
        ];
        
        return hash('sha256', json_encode($fingerprint_data) . FINGERPRINT_SALT);
    }
    
    // トークンを検証
    public function validateToken($token) {
        $this->token = preg_replace('/[^a-zA-Z0-9]/', '', $token);
        
        if (strlen($this->token) < 32) {
            return false;
        }
        
        try {
            $stmt = $this->pdo->prepare('
                SELECT * FROM tokens 
                WHERE token = :token 
                AND (expires_at > NOW())
                LIMIT 1
            ');
            $stmt->execute([':token' => hash('sha256', $this->token)]);
            $result = $stmt->fetch();
            
            return $result ?: false;
        } catch (PDOException $e) {
            return false;
        }
    }
    
    // ========== 複数タブ対策: セッション・タブID管理 ==========
    
    /**
     * 現在のタブ・セッションが有効かどうかを確認
     * 複数アクティブセッションがある場合は最新のみ許可
     */
    public function validateSessionAndTab($token_id, $fingerprint) {
        try {
            $tab_id = $this->getOrCreateTabId();
            
            // このトークン・デバイスの アクティブセッション を取得
            $stmt = $this->pdo->prepare('
                SELECT id, session_id, tab_id, created_at FROM active_sessions
                WHERE token_id = :token_id
                AND device_fp = :device_fp
                AND last_activity_at > DATE_SUB(NOW(), INTERVAL :timeout SECOND)
                ORDER BY last_activity_at DESC
            ');
            $stmt->execute([
                ':token_id' => $token_id,
                ':device_fp' => $fingerprint,
                ':timeout' => self::SESSION_TIMEOUT
            ]);
            
            $active_sessions = $stmt->fetchAll();
            
            // アクティブセッションが複数ある場合
            if (count($active_sessions) > 1) {
                // 最新のセッション以外を無効化
                $latest_session = $active_sessions[0];
                
                // 現在のセッションIDと合致するか確認
                if (session_id() !== $latest_session['session_id']) {
                    // 古いセッションからのアクセス → 拒否
                    return [
                        'valid' => false,
                        'reason' => 'session_hijacked'
                    ];
                }
                
                // 古いセッションを無効化
                $this->invalidateOldSessions($token_id, $fingerprint, $latest_session['id']);
            } elseif (count($active_sessions) === 1) {
                // セッションが1つある場合、それが現在のセッションか確認
                $session = $active_sessions[0];
                
                if (session_id() !== $session['session_id']) {
                    // 異なるセッション（新しいタブ）からのアクセス
                    // 古いセッションを無効化して新規作成
                    $this->invalidateSession($session['id']);
                    $this->createActiveSession($token_id, $fingerprint, $tab_id);
                    return ['valid' => true, 'new_session' => true];
                }
            } else {
                // セッションなし → 新規作成
                $this->createActiveSession($token_id, $fingerprint, $tab_id);
            }
            
            // セッションを更新（最後のアクティビティ時刻）
            $this->updateSessionActivity($token_id, $fingerprint);
            
            return ['valid' => true, 'new_session' => false];
            
        } catch (PDOException $e) {
            error_log('validateSessionAndTab error: ' . $e->getMessage());
            return ['valid' => false, 'reason' => 'database_error'];
        }
    }
    
    /**
     * タブIDを取得または生成
     * JavaScript で付与された tab_id を使用
     */
    private function getOrCreateTabId() {
        // POST/GET パラメータ または Cookie から tab_id を取得
        $tab_id = $_REQUEST['tab_id'] ?? $_COOKIE['tab_id'] ?? null;
        
        if (!$tab_id) {
            // 新規生成
            $tab_id = bin2hex(random_bytes(16));
        }
        
        // Cookie に保存（JavaScript でも保持される）
        setcookie(
            'tab_id',
            $tab_id,
            [
                'expires' => time() + 86400,
                'path' => '/',
                'httponly' => false,  // JavaScript からアクセス可能
                'secure' => true,
                'samesite' => 'Lax'
            ]
        );
        
        return $tab_id;
    }
    
    /**
     * アクティブセッションを新規作成
     */
    private function createActiveSession($token_id, $fingerprint, $tab_id) {
        try {
            $stmt = $this->pdo->prepare('
                INSERT INTO active_sessions 
                (token_id, session_id, tab_id, device_fp, created_at, last_activity_at)
                VALUES (:token_id, :session_id, :tab_id, :device_fp, NOW(), NOW())
            ');
            $stmt->execute([
                ':token_id' => $token_id,
                ':session_id' => session_id(),
                ':tab_id' => $tab_id,
                ':device_fp' => $fingerprint
            ]);
        } catch (PDOException $e) {
            error_log('createActiveSession error: ' . $e->getMessage());
        }
    }
    
    /**
     * 古いセッションを無効化
     */
    private function invalidateOldSessions($token_id, $fingerprint, $keep_session_id) {
        try {
            $stmt = $this->pdo->prepare('
                UPDATE active_sessions SET is_active = false
                WHERE token_id = :token_id
                AND device_fp = :device_fp
                AND id != :keep_session_id
            ');
            $stmt->execute([
                ':token_id' => $token_id,
                ':device_fp' => $fingerprint,
                ':keep_session_id' => $keep_session_id
            ]);
        } catch (PDOException $e) {
            error_log('invalidateOldSessions error: ' . $e->getMessage());
        }
    }
    
    /**
     * 特定セッションを無効化
     */
    private function invalidateSession($session_id) {
        try {
            $stmt = $this->pdo->prepare('
                UPDATE active_sessions SET is_active = false
                WHERE id = :id
            ');
            $stmt->execute([':id' => $session_id]);
        } catch (PDOException $e) {
            error_log('invalidateSession error: ' . $e->getMessage());
        }
    }
    
    /**
     * セッションのアクティビティ時刻を更新
     */
    private function updateSessionActivity($token_id, $fingerprint) {
        try {
            $stmt = $this->pdo->prepare('
                UPDATE active_sessions 
                SET last_activity_at = NOW()
                WHERE token_id = :token_id
                AND session_id = :session_id
                AND device_fp = :device_fp
            ');
            $stmt->execute([
                ':token_id' => $token_id,
                ':session_id' => session_id(),
                ':device_fp' => $fingerprint
            ]);
        } catch (PDOException $e) {
            error_log('updateSessionActivity error: ' . $e->getMessage());
        }
    }
    
    // ========== クッキー管理（従来のデバイスフィンガープリント） ==========
    
    /**
     * Cookie を確認・作成（初回のみ）
     */
    public function manageCookie($token_id, $fingerprint) {
        try {
            // すでに Cookie が存在するか確認
            $stmt = $this->pdo->prepare('
                SELECT * FROM cookies 
                WHERE token_id = :token_id 
                AND is_active = true
                LIMIT 1
            ');
            $stmt->execute([':token_id' => $token_id]);
            $cookie = $stmt->fetch();
            
            if (!$cookie) {
                // 初回アクセス - この Fingerprint で Cookie を作成
                return $this->createCookie($token_id, $fingerprint);
            }
            
            // 2回目以降 - Fingerprint が一致するか確認
            if ($cookie['device_fp'] !== $fingerprint) {
                // 異なるデバイスからのアクセス → 拒否
                return false;
            }
            
            // 有効期限をチェック
            $expiry_time = strtotime($cookie['expires_at']);
            $now = time();
            $hours_until_expiry = ($expiry_time - $now) / 3600;
            
            // 有効期限が24時間以内なら リフレッシュ
            if ($hours_until_expiry < 24) {
                $this->refreshCookie($cookie['id'], $fingerprint);
            }
            
            // Cookie を設定
            $this->setCookieValue($fingerprint, $cookie['expires_at']);
            return true;
            
        } catch (PDOException $e) {
            error_log('manageCookie error: ' . $e->getMessage());
            return false;
        }
    }
    
    /**
     * Cookie を新規作成（初回のみ）
     */
    private function createCookie($token_id, $fingerprint) {
        try {
            $expires_at = date('Y-m-d H:i:s', time() + (TOKEN_EXPIRY * 3600));
            
            $stmt = $this->pdo->prepare('
                INSERT INTO cookies (token_id, device_fp, expires_at, created_at)
                VALUES (:token_id, :device_fp, :expires_at, NOW())
            ');
            $stmt->execute([
                ':token_id' => $token_id,
                ':device_fp' => $fingerprint,
                ':expires_at' => $expires_at
            ]);
            
            $this->setCookieValue($fingerprint, $expires_at);
            return true;
        } catch (PDOException $e) {
            error_log('createCookie error: ' . $e->getMessage());
            return false;
        }
    }
    
    /**
     * Cookie をリフレッシュ（有効期限を延長）
     */
    private function refreshCookie($cookie_id, $fingerprint) {
        try {
            $expires_at = date('Y-m-d H:i:s', time() + (TOKEN_EXPIRY * 3600));
            
            $stmt = $this->pdo->prepare('
                UPDATE cookies 
                SET expires_at = :expires_at, last_refreshed_at = NOW()
                WHERE id = :id
            ');
            $stmt->execute([
                ':expires_at' => $expires_at,
                ':id' => $cookie_id
            ]);
            
            $this->setCookieValue($fingerprint, $expires_at);
            return true;
        } catch (PDOException $e) {
            error_log('refreshCookie error: ' . $e->getMessage());
            return false;
        }
    }
    
    /**
     * Cookie を実際に設定
     */
    private function setCookieValue($fingerprint, $expires_at) {
        setcookie(
            'device_fp',
            $fingerprint,
            [
                'expires' => strtotime($expires_at),
                'path' => '/',
                'secure' => true,
                'httponly' => true,
                'samesite' => 'Strict'
            ]
        );
    }
    
    /**
     * アクセスログ を記録
     */
    public function logAccess($token_id, $ip, $fingerprint, $success, $reason = null) {
        try {
            $stmt = $this->pdo->prepare('
                INSERT INTO access_logs (token_id, ip_address, device_fp, success, reason, accessed_at)
                VALUES (:token_id, :ip, :device_fp, :success, :reason, NOW())
            ');
            $stmt->execute([
                ':token_id' => $token_id,
                ':ip' => $ip,
                ':device_fp' => $fingerprint,
                ':success' => $success ? 1 : 0,
                ':reason' => $reason
            ]);
        } catch (PDOException $e) {
            error_log('logAccess error: ' . $e->getMessage());
        }
    }
}

// ========== メイン処理 ==========
$token = $_GET['token'] ?? null;

if (!$token) {
    http_response_code(400);
    die('Token required');
}

$validator = new LinkValidator();
$fingerprint = $validator->generateFingerprint();

// トークンを検証
$token_data = $validator->validateToken($token);

if (!$token_data) {
    http_response_code(403);
    die('Invalid or expired token');
}

// デバイスフィンガープリント検証
if (!$validator->manageCookie($token_data['id'], $fingerprint)) {
    $validator->logAccess($token_data['id'], $_SERVER['REMOTE_ADDR'], $fingerprint, false, 'different_device');
    http_response_code(403);
    die('Access denied. This token can only be accessed from the first device that used it.');
}

// ========== 複数タブ対策: セッション・タブID検証 ==========
$session_result = $validator->validateSessionAndTab($token_data['id'], $fingerprint);

if (!$session_result['valid']) {
    $validator->logAccess($token_data['id'], $_SERVER['REMOTE_ADDR'], $fingerprint, false, $session_result['reason']);
    http_response_code(403);
    
    if ($session_result['reason'] === 'session_hijacked') {
        die('Access denied. Another browser tab is already using this token.');
    } else {
        die('Access denied. Session validation failed.');
    }
}

$validator->logAccess($token_data['id'], $_SERVER['REMOTE_ADDR'], $fingerprint, true);

$iframe_url = $token_data['iframe_url'] ?? '';
?>
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Content</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            background: #fcfcf9;
        }
        iframe {
            width: 100%;
            height: 100vh;
            border: none;
        }
    </style>
</head>
<body>
    <iframe src="<?php echo htmlspecialchars($iframe_url, ENT_QUOTES, 'UTF-8'); ?>"></iframe>
    
    <script>
        /**
         * 複数タブ検出・管理
         * 別のタブでトークンが使用されていないか監視
         */
        (function() {
            const tabId = '<?php echo bin2hex(random_bytes(8)); ?>';
            const tokenHash = '<?php echo hash('sha256', $token); ?>';
            const storageKey = `token_${tokenHash}_active_tabs`;
            
            // 現在のタブを記録
            function registerTab() {
                const activeTabs = JSON.parse(localStorage.getItem(storageKey) || '{}');
                activeTabs[tabId] = Date.now();
                localStorage.setItem(storageKey, JSON.stringify(activeTabs));
            }
            
            // タブを削除
            function unregisterTab() {
                const activeTabs = JSON.parse(localStorage.getItem(storageKey) || '{}');
                delete activeTabs[tabId];
                localStorage.setItem(storageKey, JSON.stringify(activeTabs));
            }
            
            // 複数タブの存在を監視
            function checkMultipleTabs() {
                const activeTabs = JSON.parse(localStorage.getItem(storageKey) || '{}');
                const tabCount = Object.keys(activeTabs).length;
                
                if (tabCount > 1) {
                    // 複数タブが検出されたら警告
                    console.warn('Multiple tabs detected using this token');
                    // オプション: ページをリロード or 警告を表示
                    // location.reload();
                }
            }
            
            // 初期化
            registerTab();
            
            // 定期監視
            setInterval(checkMultipleTabs, 5000);
            
            // ページ離脱時にタブを削除
            window.addEventListener('beforeunload', unregisterTab);
        })();
    </script>
</body>
</html>
