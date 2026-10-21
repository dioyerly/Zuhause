<?php
return [
  'DB_DSN' => 'mysql:host=127.0.0.1;dbname=nc_saas;charset=utf8mb4', 'DB_USER' => 'gestion', 'DB_PASS' => 'gestion_pw',
  'APP_URL' => 'http://127.0.0.1:8791', 'SUSCRIBIRME_URL' => 'https://mp.example/suscribirme',
  'MP_ACCESS_TOKEN' => 'TEST-TOKEN', 'MP_WEBHOOK_SECRET' => 'secreto-de-prueba-123', 'MP_API_BASE' => 'http://127.0.0.1:8792', 'GRACIA_DIAS' => 5,
  'ADMIN_EMAIL' => 'dueno@test.ar', 'ADMIN_PASSWORD_HASH' => password_hash('Admin-Clave-Larga-2026', PASSWORD_DEFAULT),
  'EXPORT_TOKEN' => 'tok_export_0123456789abcdef0123456789abcdef', 'EXPORT_ORIGIN' => 'http://centro.local',
  'MAIL_FROM' => 'Test <t@test.ar>', 'MAIL_MODE' => 'log',
];
