<?php
declare(strict_types=1);
/* Zuhause SaaS · API de la app (una casa por cuenta).
   login · logout · load · save. El acceso depende del estado de la suscripción. */
require_once __DIR__ . '/lib/core.php';
require_once __DIR__ . '/lib/mp.php';

define('MAX_BYTES', 15 * 1024 * 1024);
cabeceras_seguras();
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
sesion('nc_sess');

function out(int $code, array $data): void { http_response_code($code); echo json_encode($data, JSON_UNESCAPED_UNICODE); exit; }
function body(): array {
  $raw = file_get_contents('php://input', false, null, 0, MAX_BYTES + 1);
  if ($raw === false || strlen($raw) > MAX_BYTES) out(413, ['error' => 'Datos demasiado grandes']);
  $j = json_decode($raw, true); return is_array($j) ? $j : [];
}

// CSRF: solo peticiones fetch del propio sitio (la cookie además es SameSite=Strict)
if (($_SERVER['HTTP_X_REQUESTED_WITH'] ?? '') !== 'fetch') out(400, ['error' => 'Petición inválida']);

try { $pdo = db(); } catch (Throwable $e) { error_log('db: ' . $e->getMessage()); out(500, ['error' => 'No se pudo conectar a la base de datos']); }

$action = (string)($_GET['action'] ?? '');

if ($action === 'login') {
  if ($_SERVER['REQUEST_METHOD'] !== 'POST') out(405, ['error' => 'Método no permitido']);
  $in = body(); $email = normalizar_email((string)($in['email'] ?? '')); $pass = (string)($in['password'] ?? '');
  if (freno_bloqueado('login', $email, 5, 15) || freno_bloqueado('login_ip', '', 40, 15)) out(429, ['error' => 'Demasiados intentos. Esperá unos minutos e intentá de nuevo.']);
  $st = $pdo->prepare('SELECT * FROM cuentas WHERE email = ?'); $st->execute([$email]); $c = $st->fetch();
  // se verifica siempre una clave (aunque el email no exista) para no revelar qué emails están registrados
  $ok = $c ? password_verify($pass, $c['pass_hash']) : (password_verify($pass, password_hash('relleno', PASSWORD_DEFAULT)) && false);
  if (!$ok) { freno_falla('login', $email); freno_falla('login_ip', ''); auditar($email ?: '-', 'login_fallido'); out(401, ['error' => 'Email o clave incorrectos']); }
  if (password_needs_rehash($c['pass_hash'], PASSWORD_DEFAULT)) $pdo->prepare('UPDATE cuentas SET pass_hash = ? WHERE id = ?')->execute([password_hash($pass, PASSWORD_DEFAULT), $c['id']]);
  freno_limpiar('login', $email);
  session_regenerate_id(true);
  $_SESSION['cid'] = (int)$c['id']; $_SESSION['sv'] = (int)$c['session_ver'];
  $pdo->prepare('UPDATE cuentas SET ultimo_login = ? WHERE id = ?')->execute([ahora(), $c['id']]);
  auditar($email, 'login');
  out(200, ['ok' => true]);
}
if ($action === 'logout') { $_SESSION = []; if (session_status() === PHP_SESSION_ACTIVE) session_destroy(); out(200, ['ok' => true]); }

// ---- desde acá hace falta sesión válida ----
$cid = (int)($_SESSION['cid'] ?? 0);
if ($cid <= 0) out(401, ['error' => 'auth']);
$st = $pdo->prepare('SELECT * FROM cuentas WHERE id = ?'); $st->execute([$cid]); $cuenta = $st->fetch();
if (!$cuenta || (int)$cuenta['session_ver'] !== (int)($_SESSION['sv'] ?? -1)) { $_SESSION = []; out(401, ['error' => 'auth']); }
$acc = cargar_acceso($pdo, $cuenta);

if ($acc['acceso'] === 'bloqueado') out(403, ['error' => 'bloqueado', 'acceso' => 'bloqueado', 'motivo' => $acc['motivo']]);

if ($action === 'load') {
  $st = $pdo->prepare('SELECT version, data FROM casa_estado WHERE cuenta_id = ?'); $st->execute([$cid]); $row = $st->fetch();
  $meta = ['acceso' => $acc['acceso'], 'motivo' => $acc['motivo'], 'hasta' => $acc['hasta'] ? date('Y-m-d', (int)$acc['hasta']) : null,
    'cuenta' => ['email' => $cuenta['email'], 'nombre' => $cuenta['nombre']], 'reactivar_url' => (string)cfg('SUSCRIBIRME_URL'),
    'prueba' => !empty($acc['prueba']), 'manual' => !empty($acc['manual']),
    'suscripcion' => $acc['sub'] ? ['estado' => $acc['sub']['estado'], 'proximo_cobro' => $acc['sub']['proximo_cobro'] ? substr((string)$acc['sub']['proximo_cobro'], 0, 10) : null] : null];
  if (!$row) out(200, $meta + ['version' => 0, 'data' => null]);
  out(200, $meta + ['version' => (int)$row['version'], 'data' => json_decode($row['data'], true)]);
}

if ($action === 'save') {
  if ($_SERVER['REQUEST_METHOD'] !== 'POST') out(405, ['error' => 'Método no permitido']);
  if ($acc['acceso'] !== 'activo') out(402, ['error' => 'Tu suscripción no está activa: podés ver y descargar tus datos, pero no modificarlos. Reactivala para seguir guardando.', 'acceso' => $acc['acceso']]);
  $in = body();
  if (!isset($in['data']) || !is_array($in['data'])) out(400, ['error' => 'Faltan datos']);
  $clientVersion = (int)($in['version'] ?? 0);
  $json = json_encode($in['data'], JSON_UNESCAPED_UNICODE);
  if ($json === false) out(400, ['error' => 'Datos inválidos']);
  $pdo->beginTransaction();
  try {
    $q = $pdo->prepare('SELECT version FROM casa_estado WHERE cuenta_id = ? FOR UPDATE'); $q->execute([$cid]); $cur = $q->fetchColumn();
    if ($cur === false) {
      $pdo->prepare('INSERT INTO casa_estado (cuenta_id, version, data, updated_at) VALUES (?, 1, ?, ?)')->execute([$cid, $json, ahora()]); $new = 1;
    } else {
      if ((int)$cur !== $clientVersion) { $pdo->rollBack(); out(409, ['error' => 'conflict', 'version' => (int)$cur]); }
      $new = (int)$cur + 1;
      $pdo->prepare('UPDATE casa_estado SET version = ?, data = ?, updated_at = ? WHERE cuenta_id = ?')->execute([$new, $json, ahora(), $cid]);
    }
    $pdo->prepare('INSERT INTO casa_respaldos (cuenta_id, version, data, created_at) VALUES (?,?,?,?)')->execute([$cid, $new, $json, ahora()]);
    $pdo->prepare('DELETE FROM casa_respaldos WHERE cuenta_id = ? AND version <= ?')->execute([$cid, max(0, $new - 30)]);
    $pdo->commit();
  } catch (Throwable $e) { if ($pdo->inTransaction()) $pdo->rollBack(); error_log('save: ' . $e->getMessage()); out(500, ['error' => 'No se pudo guardar']); }
  out(200, ['version' => $new]);
}
if ($action === 'cancelar') {
  if ($_SERVER['REQUEST_METHOD'] !== 'POST') out(405, ['error' => 'Método no permitido']);
  $sub = $acc['sub'];
  if (!$sub || $sub['estado'] !== 'authorized') out(400, ['error' => 'No tenés una suscripción activa para dar de baja.']);
  if (strpos((string)$sub['preapproval_id'], 'manual-') === 0) out(400, ['error' => 'Tu acceso es de cortesía o de prueba: no tiene cobros que cancelar.']);
  try { mp_cancelar_preapproval($pdo, (string)$sub['preapproval_id']); }
  catch (Throwable $e) { error_log('cancelar: ' . $e->getMessage()); out(502, ['error' => 'No se pudo dar de baja ahora. Probá de nuevo en unos minutos.']); }
  auditar((string)$cuenta['email'], 'baja_suscripcion', (string)$sub['preapproval_id']);
  out(200, ['ok' => true]);
}
out(404, ['error' => 'Acción desconocida']);