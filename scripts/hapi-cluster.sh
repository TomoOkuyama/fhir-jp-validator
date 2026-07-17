#!/usr/bin/env bash
# HAPI FHIR Validator 6 JVM cluster manager
#
# Usage:
#   scripts/hapi-cluster.sh start   # 6 サーバ起動 (port 3001-3006)
#   scripts/hapi-cluster.sh stop    # 全サーバ停止
#   scripts/hapi-cluster.sh status  # 稼働状況表示
#
# 前提: Java 11+ (host 側)、jp_core/package (JP Core IG) が存在すること
# validator_cli.jar は .hapi-cache/ に自動ダウンロード (177MB, gitignore 対象)
#
# 実測目安 (M3 Max 14 core): 構成・データにより 170-440 res/sec 幅がある。
#   - JP Core + JP-CLINS + jpfhir-terminology + LOINC + SNOMED 全 load (cache warm, chunk=50 parallel=32):
#     205 rps 前後、343k res を 28 分 (docs/benchmarks.md 参照)
#   - tx 検証をスキップ or code が未登録 CodeSystem 中心 (validator が terminology check を即 skip):
#     440 rps 前後まで到達可能
# rps は data の terminology 充実度と `-tx` 設定に強く依存する

set -euo pipefail

# ------------------------------------------------------------
# 設定
# ------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE_DIR="${HAPI_CACHE_DIR:-$REPO_ROOT/.hapi-cache}"
VALIDATOR_JAR="$CACHE_DIR/validator_cli.jar"
VALIDATOR_URL="https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar"
IG_DIR="${HAPI_IG_DIR:-$REPO_ROOT/jp_core/package}"
# 追加 IG (colon 区切り、順不同)。JP-CLINS 等の subsidiary IG を渡す。
# 各エントリはディレクトリ / .tgz ファイル / package spec (name#version) いずれも可。
HAPI_IG_EXTRA_DIRS="${HAPI_IG_EXTRA_DIRS:-$REPO_ROOT/tx-server-build/terminology/fhir-server/clinical-information-sharing#1.12.0/package:$REPO_ROOT/tx-server-build/terminology/fhir-server/jpfhir-terminology#2.2606.0/package}"
FHIR_VERSION="${HAPI_FHIR_VERSION:-4.0.1}"
JVM_HEAP="${HAPI_JVM_HEAP:-3g}"
PORTS=(3001 3002 3003 3004 3005 3006)
# Terminology server 指定
#   default (未指定): local fhirserver (http://localhost:8181/r4) を使用
#                    docker compose up -d fhirserver で起動しておくこと
#   "default"       : HAPI 内蔵デフォルト (tx.fhir.org) にフォールバック
#   "n/a"           : 外部 tx 検証を完全スキップ (structure/slice のみ、最速)
#   任意 URL         : 他の HL7 approve 済 tx server
HAPI_TX="${HAPI_TX:-http://localhost:8181/r4}"

# Terminology response の local cache ディレクトリ (default: .hapi-cache/tx-cache)
# 初回 warm-up 後は cache hit で高速化、複数 JVM 共有可
HAPI_TX_CACHE="${HAPI_TX_CACHE:-$REPO_ROOT/.hapi-cache/tx-cache}"

# HAPI validator への追加引数 (default: なし)
# 例: HAPI_EXTRA_ARGS="-best-practice ignore -check-display Ignore"
#     で Best Practice 系 warning と display 検証をスキップ
HAPI_EXTRA_ARGS="${HAPI_EXTRA_ARGS:-}"

# ------------------------------------------------------------
# 共通処理
# ------------------------------------------------------------
require_java() {
  if ! command -v java >/dev/null 2>&1; then
    echo "ERROR: java コマンドが見つかりません。JDK 11+ をインストールしてください" >&2
    exit 1
  fi
}

require_ig() {
  if [ ! -d "$IG_DIR" ]; then
    echo "ERROR: JP Core IG が見つかりません: $IG_DIR" >&2
    echo "       jp_core/package/ が展開済みか確認、または HAPI_IG_DIR を設定" >&2
    exit 1
  fi
}

ensure_validator() {
  mkdir -p "$CACHE_DIR"
  if [ ! -f "$VALIDATOR_JAR" ]; then
    echo "validator_cli.jar が無いためダウンロード中 (~177MB)..."
    curl -fSL -o "$VALIDATOR_JAR" "$VALIDATOR_URL"
  fi
}

# ------------------------------------------------------------
# start
# ------------------------------------------------------------
cmd_start() {
  require_java
  require_ig
  ensure_validator

  mkdir -p "$CACHE_DIR/logs"

  # 既に稼働中ならスキップ
  local running=0
  for port in "${PORTS[@]}"; do
    if lsof -Pi :"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      running=$((running+1))
    fi
  done
  if [ "$running" -gt 0 ]; then
    echo "既に $running プロセスが稼働中。先に stop してください"
    exit 1
  fi

  local tx_args=()
  local tx_display="$HAPI_TX"
  if [ "$HAPI_TX" = "default" ] || [ -z "$HAPI_TX" ]; then
    # HAPI 内蔵デフォルト (tx.fhir.org) を使う場合は -tx を渡さない
    tx_display="default(tx.fhir.org)"
  else
    tx_args=(-tx "$HAPI_TX")
  fi

  # -txCache は "n/a" 以外の場合に有効
  local cache_display="disabled"
  if [ "$HAPI_TX" != "n/a" ] && [ -n "$HAPI_TX_CACHE" ]; then
    mkdir -p "$HAPI_TX_CACHE"
    tx_args+=(-txCache "$HAPI_TX_CACHE")
    cache_display="$HAPI_TX_CACHE"
  fi

  # -ig 引数を組立 (プライマリ + 追加)
  local ig_args=(-ig "$IG_DIR")
  local ig_display="$IG_DIR"
  if [ -n "$HAPI_IG_EXTRA_DIRS" ]; then
    local IFS=':'
    for extra in $HAPI_IG_EXTRA_DIRS; do
      [ -z "$extra" ] && continue
      if [ ! -e "$extra" ]; then
        echo "WARN: 追加 IG が見つかりません、skip: $extra" >&2
        continue
      fi
      ig_args+=(-ig "$extra")
      ig_display+=", $extra"
    done
    unset IFS
  fi

  echo "HAPI validator cluster 起動中 (${#PORTS[@]} JVM, heap=$JVM_HEAP, FHIR $FHIR_VERSION, IG=$ig_display, tx=$tx_display, txCache=$cache_display)"

  # HAPI_EXTRA_ARGS を配列に展開 (空白区切り、簡易 shell parse)
  local extra_args=()
  if [ -n "$HAPI_EXTRA_ARGS" ]; then
    # shellcheck disable=SC2206
    extra_args=($HAPI_EXTRA_ARGS)
    echo "extra args: ${extra_args[*]}"
  fi

  for port in "${PORTS[@]}"; do
    nohup java "-Xmx$JVM_HEAP" -jar "$VALIDATOR_JAR" server "$port" \
      -version "$FHIR_VERSION" \
      "${ig_args[@]}" \
      ${tx_args[@]:+"${tx_args[@]}"} \
      ${extra_args[@]:+"${extra_args[@]}"} \
      > "$CACHE_DIR/logs/$port.log" 2>&1 &
    echo $! > "$CACHE_DIR/logs/$port.pid"
    echo "  port $port started (PID $!)"
  done

  echo "全 ${#PORTS[@]} サーバ ready 待機中..."
  local start_ts elapsed
  start_ts=$(date +%s)
  while true; do
    local ready=0
    for port in "${PORTS[@]}"; do
      if grep -q "started on" "$CACHE_DIR/logs/$port.log" 2>/dev/null; then
        ready=$((ready+1))
      fi
    done
    if [ "$ready" -eq "${#PORTS[@]}" ]; then
      elapsed=$(( $(date +%s) - start_ts ))
      echo "全 ${#PORTS[@]} サーバ ready ($elapsed 秒)"
      break
    fi
    elapsed=$(( $(date +%s) - start_ts ))
    if [ "$elapsed" -gt 120 ]; then
      echo "ERROR: 起動タイムアウト (120秒)。$CACHE_DIR/logs/*.log を確認" >&2
      exit 1
    fi
    sleep 2
  done

  echo
  echo "エンドポイント: http://localhost:{$(IFS=,; echo "${PORTS[*]}")}/validateResource"
  echo "停止: scripts/hapi-cluster.sh stop"
}

# ------------------------------------------------------------
# stop
# ------------------------------------------------------------
cmd_stop() {
  local stopped=0
  if [ -d "$CACHE_DIR/logs" ]; then
    for pidfile in "$CACHE_DIR/logs"/*.pid; do
      [ -f "$pidfile" ] || continue
      local pid; pid=$(cat "$pidfile")
      if kill -TERM "$pid" 2>/dev/null; then
        stopped=$((stopped+1))
      fi
      rm -f "$pidfile"
    done
  fi
  # PID ファイル外の取りこぼしを念のため掃除
  pkill -f "validator_cli.jar server" 2>/dev/null || true
  sleep 1
  # pgrep は該当なしで exit 1 を返し、set -e + pipefail で abort するため、
  # exit code だけを見る (pgrep -f は match ゼロで 1、1 以上で 0)。
  if pgrep -f "validator_cli.jar server" >/dev/null 2>&1; then
    pkill -9 -f "validator_cli.jar server" 2>/dev/null || true
  fi
  echo "$stopped プロセス停止"
}

# ------------------------------------------------------------
# status
# ------------------------------------------------------------
cmd_status() {
  local ready=0
  local rss_total=0
  echo "| port | listening | PID    | RSS      | ready |"
  echo "|-----:|----------:|-------:|---------:|:------|"
  for port in "${PORTS[@]}"; do
    local listen="no" pid="-" rss="-" started="no"
    if lsof -Pi :"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      listen="yes"
    fi
    if [ -f "$CACHE_DIR/logs/$port.pid" ]; then
      pid=$(cat "$CACHE_DIR/logs/$port.pid")
      if kill -0 "$pid" 2>/dev/null; then
        local rss_kb
        rss_kb=$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ')
        if [ -n "$rss_kb" ]; then
          rss=$(awk -v k="$rss_kb" 'BEGIN{printf "%.0f MB", k/1024}')
          rss_total=$((rss_total + rss_kb))
        fi
      fi
    fi
    if grep -q "started on" "$CACHE_DIR/logs/$port.log" 2>/dev/null; then
      started="yes"
      ready=$((ready+1))
    fi
    printf "| %4s | %9s | %6s | %8s | %s |\n" "$port" "$listen" "$pid" "$rss" "$started"
  done
  echo
  echo "ready: $ready / ${#PORTS[@]}"
  if [ "$rss_total" -gt 0 ]; then
    awk -v k="$rss_total" 'BEGIN{printf "RSS 合計: %.2f GB\n", k/1024/1024}'
  fi
}

# ------------------------------------------------------------
# dispatch
# ------------------------------------------------------------
case "${1:-}" in
  start)  cmd_start ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  *)
    echo "Usage: $0 {start|stop|status}" >&2
    exit 1
    ;;
esac
