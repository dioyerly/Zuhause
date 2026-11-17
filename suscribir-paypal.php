<?php
declare(strict_types=1);
require_once __DIR__ . '/lib/paypal.php';
/* Botón "Pagar desde el exterior": crea la suscripción en PayPal y manda al cliente a aprobarla.
   PayPal lo devuelve a alta.php?subscription_id=... donde crea su usuario y su clave. */
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') { header('Location: ./'); exit; }
if (!empty($_POST['web'])) exit;   // trampa para bots
if (!pp_configurado()) { pagina('Zuhause', '<h1>No disponible</h1><p>El pago con PayPal todavía no está habilitado. Escribinos y te ayudamos.</p>'); exit; }
if (freno_bloqueado('pp_alta', '', 10, 30)) { pagina('Zuhause', '<h1>Demasiados intentos</h1><p>Esperá unos minutos y volvé a intentar.</p>'); exit; }
freno_falla('pp_alta', '');
try { [$id, $url] = pp_crear_suscripcion(); }
catch (Throwable $e) {
  error_log('suscribir-paypal: ' . $e->getMessage());
  pp_aviso_dueno('Zuhause: falló iniciar una suscripción con PayPal', "Alguien intentó suscribirse y no se pudo crear en PayPal.\nMotivo: " . $e->getMessage());
  pagina('Zuhause', '<h1>No pudimos iniciar el pago</h1><p>Probá de nuevo en unos minutos o escribinos.</p>'); exit;
}
header('Location: ' . $url); exit;
