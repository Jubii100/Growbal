#!/bin/bash
# Hard-coded credentials; no env vars needed
set -euo pipefail

DB="growbal_db"
USER="sql"
PASS="1234"

echo "🔧  Creating $USER@$DB with SYSTEM_VARIABLES_ADMIN …"

mysql -uroot <<EOSQL
CREATE USER IF NOT EXISTS '$USER'@'%' IDENTIFIED BY '$PASS';
GRANT ALL PRIVILEGES        ON \`${DB}\`.* TO '$USER'@'%';
GRANT SYSTEM_VARIABLES_ADMIN ON *.*       TO '$USER'@'%';
FLUSH PRIVILEGES;
EOSQL

echo "✅  $USER now has full DB + global privilege"

