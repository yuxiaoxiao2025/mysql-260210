#!/bin/bash
# 用法：./scripts/backup_metadata.sh [dev|prod]

ENV=${1:-dev}
SOURCE_DIR="data/${ENV}/chroma_db"
BACKUP_DIR="data/${ENV}/backups/chroma_db_$(date +%Y%m%d_%H%M%S)"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ 错误：$SOURCE_DIR 不存在"
    exit 1
fi

mkdir -p "$BACKUP_DIR"
cp -r "$SOURCE_DIR"/* "$BACKUP_DIR"/

# 同时备份知识图谱 JSON
cp "data/${ENV}/table_graph.json" "$BACKUP_DIR"/ 2>/dev/null || echo "⚠️ table_graph.json 不存在"

echo "✅ 备份完成：$BACKUP_DIR"
echo "📊 备份大小：$(du -sh $BACKUP_DIR | cut -f1)"
