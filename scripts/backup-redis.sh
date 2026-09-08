#!/bin/sh
# Off-box backup of the board. The droplet's volume is a single copy of the whole
# product — an AOF that only ever lived on the disk that died is not a backup.
#
# crontab -e (hourly):
#   0 * * * * BACKUP_DEST=s3://pixelwars-backups BACKUP_ENDPOINT=https://fra1.digitaloceanspaces.com /srv/pixelwars/backend/scripts/backup-redis.sh >> /var/log/pixelwars-backup.log 2>&1
#
# Retention is the bucket's job (lifecycle rule), not this script's.
set -eu

: "${BACKUP_DEST:?set BACKUP_DEST, e.g. s3://pixelwars-backups or /mnt/backups}"

cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
NAME="dump-$(date -u +%Y%m%dT%H%M%SZ).rdb"

# BGSAVE is async. Watch LASTSAVE move instead of sleeping a guessed interval —
# otherwise we ship whatever stale dump.rdb happens to be on disk.
lastsave() { docker compose exec -T redis redis-cli LASTSAVE | tr -dc '0-9'; }

before=$(lastsave)
docker compose exec -T redis redis-cli BGSAVE

i=0
while [ "$(lastsave)" = "$before" ]; do
	i=$((i + 1))
	if [ "$i" -gt 60 ]; then
		echo "BGSAVE did not complete within 60s" >&2
		exit 1
	fi
	sleep 1
done

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
docker compose cp "redis:/data/dump.rdb" "$TMP/$NAME"

case "$BACKUP_DEST" in
	s3://*) aws s3 cp "$TMP/$NAME" "$BACKUP_DEST/$NAME" ${BACKUP_ENDPOINT:+--endpoint-url "$BACKUP_ENDPOINT"} ;;
	*) rsync -a "$TMP/$NAME" "$BACKUP_DEST/$NAME" ;;
esac

echo "backed up $NAME ($(wc -c < "$TMP/$NAME") bytes) to $BACKUP_DEST"
