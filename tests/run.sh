#!/bin/bash
# Reinicia la base de pruebas, levanta MP falso + PHP, corre las suites y apaga todo.
cd "$(dirname "$0")"; ROOT="$(cd .. && pwd)"; T=/tmp/nc-tests; mkdir -p $T
mariadb -e "DROP DATABASE IF EXISTS nc_saas; CREATE DATABASE nc_saas CHARACTER SET utf8mb4; GRANT ALL ON nc_saas.* TO 'gestion'@'localhost' IDENTIFIED BY 'gestion_pw';" || exit 1
mariadb nc_saas < "$ROOT/schema.sql" || exit 1
rm -f "$ROOT/storage/mail.log"
python3 fake_mp.py 8792 > $T/mp.log 2>&1 & echo $! > $T/mp.pid
python3 fake_paypal.py 8793 > $T/pp.log 2>&1 & echo $! > $T/pp.pid
PHP_CLI_SERVER_WORKERS=8 NC_CONFIG="$PWD/config.test.php" php -d opcache.enable=0 -d post_max_size=40M -d upload_max_filesize=40M -d memory_limit=512M -S 127.0.0.1:8791 -t "$ROOT" > $T/php.log 2>&1 & echo $! > $T/php.pid
sleep 1.5
FAIL=0
for s in "$@"; do python3 "$s" || FAIL=1; done
kill $(cat $T/mp.pid) $(cat $T/pp.pid) $(cat $T/php.pid) 2>/dev/null
rm -f "$ROOT/storage/mail.log"
exit $FAIL
