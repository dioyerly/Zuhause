<?php
// Copiá este archivo como config.php (nunca lo subas a GitHub ni lo dejes público).
return [
  'DB_DSN'  => 'mysql:host=localhost;dbname=zuhause;charset=utf8mb4',
  'DB_USER' => 'usuario',
  'DB_PASS' => 'clave',

  // URL pública de la app, sin barra final. Se usa en los links de los mails.
  'APP_URL' => 'https://zuhause.tudominio.com',
  // Link que lleva a Mercado Pago a pagar la suscripción (el que creás vos en MP).
  'SUSCRIBIRME_URL' => 'https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=TU_PLAN',

  // --- Mercado Pago ---
  'MP_ACCESS_TOKEN'   => '',   // Credenciales > Access Token (de prueba primero, producción después)
  'MP_WEBHOOK_SECRET' => '',   // Tus integraciones > Webhooks > Clave secreta
  'MP_API_BASE'       => 'https://api.mercadopago.com',
  // Días que se mantiene el acceso completo si falla un cobro, antes de pasar a solo lectura.
  'GRACIA_DIAS' => 5,

  // --- PayPal (suscripciones para clientes del exterior, se cobra en dólares) — opcional ---
  // developer.paypal.com > Apps & Credentials > (Live) tu app. Las claves las pegás vos acá, nunca en un chat ni en GitHub.
  'PAYPAL_CLIENT_ID'  => '',
  'PAYPAL_SECRET'     => '',
  'PAYPAL_WEBHOOK_ID' => '',   // ID del webhook de la app (URL https://TU-DOMINIO/paypal-webhook.php)
  'PAYPAL_MODE'       => 'live',   // 'sandbox' para probar con cuentas de prueba

  // --- Panel del dueño (solo vos) ---
  'ADMIN_EMAIL'         => 'vos@tudominio.com',
  // php -r "echo password_hash('TU-CLAVE-LARGA', PASSWORD_DEFAULT);"
  'ADMIN_PASSWORD_HASH' => '',
  // Token para que el Centro de operaciones lea las métricas. Generá uno: php -r "echo bin2hex(random_bytes(24));"
  'EXPORT_TOKEN' => '',
  // Origen desde donde abrís el Centro de operaciones (para permitir la lectura). '' = no permitir lectura desde otra web.
  'EXPORT_ORIGIN' => '',

  // --- Mails ---
  'MAIL_FROM' => 'Zuhause <no-responder@tudominio.com>',
  'MAIL_MODE' => 'mail',   // 'mail' = función mail() de Hostinger | 'log' = solo escribe en storage/mail.log (pruebas)
];
