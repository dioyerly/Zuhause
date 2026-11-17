<?php
declare(strict_types=1);
require_once __DIR__ . '/lib/export.php';
/* Lectura de métricas para el Centro de operaciones. Solo lectura, con token.
   GET export.php  ·  Authorization: Bearer EXPORT_TOKEN  ·  ?desde=AAAA-MM-DD (opcional) */
cabeceras_seguras(); header('Content-Type: application/json; charset=utf-8'); header('Cache-Control: no-store');
$origen = (string)($_SERVER['HTTP_ORIGIN'] ?? ''); $permitido = (string)cfg('EXPORT_ORIGIN');
if ($permitido !== '' && $origen === $permitido) { header('Access-Control-Allow-Origin: ' . $origen); header('Vary: Origin'); header('Access-Control-Allow-Headers: Authorization'); header('Access-Control-Allow-Methods: GET'); }
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') { http_response_code(204); exit; }
function f(int $c, array $d): void { http_response_code($c); echo json_encode($d, JSON_UNESCAPED_UNICODE); exit; }
$tokenCfg = (string)cfg('EXPORT_TOKEN');
if ($tokenCfg === '' || strlen($tokenCfg) < 32) f(503, ['error' => 'Exportación no configurada']);
if (freno_bloqueado('export', '', 20, 15)) f(429, ['error' => 'Demasiados intentos']);
$h = (string)($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
$dado = preg_match('/^Bearer\s+(\S+)$/', $h, $m) ? $m[1] : '';
if (!hash_equals($tokenCfg, $dado)) { freno_falla('export', ''); f(401, ['error' => 'No autorizado']); }
$desde = isset($_GET['desde']) && preg_match('/^\d{4}-\d{2}-\d{2}$/', (string)$_GET['desde']) ? (string)$_GET['desde'] : null;
f(200, ['generado' => date('c'), 'events' => eventos_centro(db(), $desde)]);
