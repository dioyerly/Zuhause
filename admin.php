<?php
declare(strict_types=1);
require_once __DIR__ . '/lib/paypal.php';
require_once __DIR__ . '/lib/export.php';
/* Panel del dueño: clientes, suscripciones, pagos, eventos de Mercado Pago, auditoría.
   NO muestra los datos de la casa de cada cliente (gastos, notas, etc.): solo cuenta y pago. */
sesion('nc_admin');
$pdo = db(); $adminEmail = normalizar_email((string)cfg('ADMIN_EMAIL')); $hash = (string)cfg('ADMIN_PASSWORD_HASH');
header('X-Robots-Tag: noindex');

function plata(int $cent, string $mon = 'ARS'): string { return ($mon === 'ARS' ? '$ ' : $mon . ' ') . number_format($cent / 100, 2, ',', '.'); }
function cuando(?string $s): string { return $s ? esc(substr($s, 0, 16)) : '—'; }
function redir(string $q = ''): void { header('Location: admin.php' . $q); exit; }

if (($_GET['salir'] ?? '') === '1' && isset($_SESSION['admin'])) { $_SESSION = []; session_destroy(); redir(); }

// ---------- login ----------
if (empty($_SESSION['admin']) || (time() - (int)($_SESSION['admin_t'] ?? 0)) > 8 * 3600) {
  unset($_SESSION['admin']);
  $err = '';
  if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    $e = normalizar_email((string)($_POST['email'] ?? '')); $p = (string)($_POST['clave'] ?? '');
    if (!csrf_ok()) $err = 'La sesión venció. Recargá la página.';
    elseif (freno_bloqueado('admin', '', 5, 15)) $err = 'Demasiados intentos. Esperá unos minutos.';
    elseif ($hash !== '' && $adminEmail !== '' && hash_equals($adminEmail, $e) && password_verify($p, $hash)) {
      session_regenerate_id(true); $_SESSION['admin'] = true; $_SESSION['admin_t'] = time(); freno_limpiar('admin', ''); auditar($e, 'admin_login'); redir();
    } else { freno_falla('admin', ''); auditar($e ?: '-', 'admin_login_fallido'); $err = 'Datos incorrectos.'; }
  }
  pagina('Panel · Zuhause', '<h1>Panel del dueño</h1>' . ($err ? '<div class="e">' . esc($err) . '</div>' : '')
    . '<form method="post" action="admin.php"><input type="hidden" name="csrf" value="' . esc(csrf_token()) . '"><label for="e">Email</label><input id="e" name="email" type="email" required autocomplete="username"><label for="c">Clave</label><input id="c" name="clave" type="password" required autocomplete="current-password"><button type="submit">Entrar</button></form>');
  exit;
}
$_SESSION['admin_t'] = time();

// ---------- descarga para el Centro de operaciones ----------
if (($_GET['descargar'] ?? '') === 'centro') {
  auditar($adminEmail, 'admin_exporta_centro');
  header('Content-Type: application/json; charset=utf-8'); header('Content-Disposition: attachment; filename="zuhause-eventos-' . date('Y-m-d') . '.json"'); header('Cache-Control: no-store');
  echo json_encode(eventos_centro($pdo), JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT); exit;
}

// ---------- acciones (POST + CSRF) ----------
$aviso = '';
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
  if (!csrf_ok()) { $aviso = '<div class="e">La sesión venció. Recargá la página.</div>'; }
  else {
    $a = (string)($_POST['a'] ?? ''); $cid = (int)($_POST['cuenta'] ?? 0);
    if ($a === 'override' && $cid > 0 && in_array($_POST['valor'] ?? '', ['auto', 'activo', 'bloqueado'], true)) {
      $pdo->prepare('UPDATE cuentas SET override = ?, session_ver = session_ver + IF(? = "bloqueado", 1, 0) WHERE id = ?')->execute([$_POST['valor'], $_POST['valor'], $cid]);
      auditar($adminEmail, 'admin_override', "cuenta $cid => " . $_POST['valor']); $aviso = '<div class="o">Acceso actualizado.</div>';
    } elseif ($a === 'link_clave' && $cid > 0) {
      $q = $pdo->prepare('SELECT email FROM cuentas WHERE id = ?'); $q->execute([$cid]); $em = $q->fetchColumn();
      if ($em) { $tok = crear_token_recuperacion($pdo, $cid, 60); auditar($adminEmail, 'admin_link_clave', "cuenta $cid");
        $aviso = '<div class="o">Link de un solo uso (1 hora) para ' . esc((string)$em) . ':<br><code style="word-break:break-all">' . esc(rtrim((string)cfg('APP_URL'), '/') . '/recuperar.php?t=' . $tok) . '</code></div>'; }
    } elseif ($a === 'resync') {
      $pre = (string)($_POST['pre'] ?? '');
      try { es_paypal($pre) ? pp_sync_suscripcion($pdo, $pre) : mp_sync_preapproval($pdo, $pre); auditar($adminEmail, 'admin_resync', $pre); $aviso = '<div class="o">Sincronizada con ' . (es_paypal($pre) ? 'PayPal' : 'Mercado Pago') . '.</div>'; }
      catch (Throwable $e) { $aviso = '<div class="e">No se pudo sincronizar: ' . esc($e->getMessage()) . '</div>'; }
    }
  }
}

// ---------- datos ----------
$cuentas = $pdo->query('SELECT * FROM cuentas ORDER BY id DESC LIMIT 500')->fetchAll();
$filas = ''; $nAct = $nLect = $nBloq = 0; $mrr = 0;
foreach ($cuentas as $c) {
  $x = cargar_acceso($pdo, $c); $s = $x['sub'];
  if ($x['acceso'] === 'activo') $nAct++; elseif ($x['acceso'] === 'bloqueado') $nBloq++; else $nLect++;
  if ($s && $s['estado'] === 'authorized' && $x['acceso'] === 'activo' && $s['moneda'] === 'ARS') $mrr += (int)round($s['monto_cent'] * 30 / max(1, (int)$s['periodo_dias']));
  $csrf = '<input type="hidden" name="csrf" value="' . esc(csrf_token()) . '"><input type="hidden" name="cuenta" value="' . (int)$c['id'] . '">';
  $opts = ''; foreach (['auto' => 'Automático', 'activo' => 'Cortesía (activo)', 'bloqueado' => 'Bloqueado'] as $k => $l) $opts .= '<option value="' . $k . '"' . ($c['override'] === $k ? ' selected' : '') . '>' . $l . '</option>';
  $filas .= '<tr><td>' . esc($c['nombre']) . '<br><small>' . esc($c['email']) . '</small></td>'
    . '<td><b class="t-' . esc($x['acceso']) . '">' . esc(str_replace('_', ' ', $x['acceso'])) . '</b><br><small>' . esc($x['motivo']) . '</small></td>'
    . '<td>' . ($s ? esc($s['estado']) . ' <small>(' . (es_paypal((string)$s['preapproval_id']) ? 'PayPal' : 'MP') . ')</small><br><small>' . plata((int)$s['monto_cent'], $s['moneda']) . ' · próx. ' . cuando($s['proximo_cobro']) . '</small>' : '—') . '</td>'
    . '<td>' . cuando($x['ultimo_pago']) . '</td><td>' . cuando($c['creada']) . '<br><small>últ. ingreso ' . cuando($c['ultimo_login']) . '</small></td>'
    . '<td><form method="post" action="admin.php" class="in"><input type="hidden" name="a" value="override">' . $csrf . '<select name="valor">' . $opts . '</select><button>Guardar</button></form>'
    . '<form method="post" action="admin.php" class="in"><input type="hidden" name="a" value="link_clave">' . $csrf . '<button class="g">Link de clave</button></form>'
    . ($s ? '<form method="post" action="admin.php" class="in"><input type="hidden" name="a" value="resync"><input type="hidden" name="csrf" value="' . esc(csrf_token()) . '"><input type="hidden" name="pre" value="' . esc($s['preapproval_id']) . '"><button class="g">Sincronizar</button></form>' : '') . '</td></tr>';
}
$sinCuenta = $pdo->query('SELECT * FROM suscripciones WHERE cuenta_id IS NULL ORDER BY id DESC LIMIT 50')->fetchAll();
$pagos = $pdo->query('SELECT p.*, c.email FROM pagos p LEFT JOIN suscripciones s ON s.preapproval_id = p.preapproval_id LEFT JOIN cuentas c ON c.id = s.cuenta_id ORDER BY p.id DESC LIMIT 100')->fetchAll();
$eventos = $pdo->query('SELECT * FROM eventos_mp ORDER BY id DESC LIMIT 40')->fetchAll();
$audit = $pdo->query('SELECT * FROM auditoria ORDER BY id DESC LIMIT 40')->fetchAll();

$tPag = ''; foreach ($pagos as $p) $tPag .= '<tr><td>' . cuando($p['fecha_debito'] ?: $p['creada']) . '</td><td>' . esc((string)$p['email']) . '</td><td>' . esc($p['estado']) . ($p['reintento'] ? ' (reintento ' . (int)$p['reintento'] . ')' : '') . '<br><small>' . esc($p['detalle']) . '</small></td><td>' . plata((int)$p['monto_cent'], $p['moneda']) . '</td></tr>';
$tEv = ''; foreach ($eventos as $e) $tEv .= '<tr><td>' . cuando($e['recibido']) . '</td><td>' . esc($e['topic']) . '</td><td>' . esc($e['data_id']) . '</td><td>' . ($e['firma_ok'] ? 'ok' : '<b>no</b>') . '</td><td>' . esc($e['resultado']) . '<br><small>' . esc($e['detalle']) . '</small></td></tr>';
$tAu = ''; foreach ($audit as $e) $tAu .= '<tr><td>' . cuando($e['ts']) . '</td><td>' . esc($e['actor']) . '</td><td>' . esc($e['accion']) . '</td><td><small>' . esc($e['detalle']) . '</small></td></tr>';
$tSin = ''; foreach ($sinCuenta as $s) $tSin .= '<tr><td>' . esc($s['payer_email'] ?: '—') . '</td><td>' . esc($s['estado']) . '</td><td>' . cuando($s['creada']) . '</td><td><small>' . esc($s['preapproval_id']) . '</small></td></tr>';

cabeceras_seguras();
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
header('Content-Type: text/html; charset=utf-8'); header('Cache-Control: no-store');
?><!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Panel · Zuhause</title><style>
:root{--bg:#f6f3ee;--ink:#2b2420;--mut:#7a6f66;--ac:#b4532a;--card:#fff;--line:#e6dccf;--ok:#17602b;--bad:#8a1f17;--warn:#8a5a00}
@media(prefers-color-scheme:dark){:root{--bg:#1d1916;--ink:#f3ebe2;--mut:#a89c91;--ac:#e0875a;--card:#27211d;--line:#3a312b;--ok:#6fd08a;--bad:#ff8c80;--warn:#f0c060}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;padding:16px}
.w{max-width:1200px;margin:0 auto}h1{margin:0}h2{margin:28px 0 8px;font-size:1.1rem}.top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}.k div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}.k b{display:block;font-size:1.5rem}.k span{color:var(--mut);font-size:.85rem}
.tw{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:14px}table{width:100%;border-collapse:collapse;min-width:720px}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
small{color:var(--mut)}.t-activo{color:var(--ok)}.t-solo_lectura{color:var(--warn)}.t-bloqueado{color:var(--bad)}
.o{background:#e9f6ec;color:#17602b;padding:10px 12px;border-radius:10px;margin:12px 0}.e{background:#fdeceb;color:#8a1f17;padding:10px 12px;border-radius:10px;margin:12px 0}
form.in{display:flex;gap:4px;margin:0 0 4px}select,button{font:inherit;padding:5px 8px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}button{background:var(--ac);color:#fff;border:0;cursor:pointer}button.g{background:var(--bg);color:var(--ink);border:1px solid var(--line)}
a.btn{background:var(--ac);color:#fff;padding:8px 14px;border-radius:10px;text-decoration:none;font-weight:600}a{color:var(--ac)}
</style></head><body><div class="w">
<div class="top"><h1>Zuhause · Panel</h1><div><a class="btn" href="admin.php?descargar=centro">Descargar para Centro de operaciones</a> &nbsp; <a href="admin.php?salir=1">Salir</a></div></div>
<?= $aviso ?>
<div class="k"><div><b><?= count($cuentas) ?></b><span>Clientes</span></div><div><b><?= $nAct ?></b><span>Con acceso activo</span></div><div><b><?= $nLect ?></b><span>Solo lectura (no pagan)</span></div><div><b><?= $nBloq ?></b><span>Bloqueados</span></div><div><b><?= esc(plata($mrr)) ?></b><span>Ingreso mensual en pesos (activos)</span></div></div>
<h2>Clientes</h2><div class="tw"><table><tr><th>Cliente</th><th>Acceso</th><th>Suscripción</th><th>Último pago</th><th>Alta</th><th>Acciones</th></tr><?= $filas ?: '<tr><td colspan="6">Todavía no hay clientes.</td></tr>' ?></table></div>
<?php if ($tSin): ?><h2>Pagaron pero no crearon su acceso</h2><div class="tw"><table><tr><th>Email del pago</th><th>Estado</th><th>Fecha</th><th>ID de la suscripción</th></tr><?= $tSin ?></table></div><?php endif; ?>
<h2>Pagos (cuotas)</h2><div class="tw"><table><tr><th>Fecha</th><th>Cliente</th><th>Estado</th><th>Monto</th></tr><?= $tPag ?: '<tr><td colspan="4">Sin pagos todavía.</td></tr>' ?></table></div>
<h2>Notificaciones de Mercado Pago y PayPal</h2><div class="tw"><table><tr><th>Recibido</th><th>Tema</th><th>ID</th><th>Firma</th><th>Resultado</th></tr><?= $tEv ?: '<tr><td colspan="5">Ninguna todavía.</td></tr>' ?></table></div>
<h2>Auditoría</h2><div class="tw"><table><tr><th>Fecha</th><th>Quién</th><th>Acción</th><th>Detalle</th></tr><?= $tAu ?></table></div>
</div></body></html>
