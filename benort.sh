#!/usr/bin/env bash
# chmod +x /Users/benserver/.local/bin/benort
# benort start|stop|status|restart|ip

set -euo pipefail

PROJECT_PATH="/Users/benserver/Desktop/Benort"
cd "$PROJECT_PATH"

VENV_PATH="$PROJECT_PATH/venv"
PYTHON="$VENV_PATH/bin/python"
PIP="$VENV_PATH/bin/pip"
PID_FILE="flask.pid"
INFO_FILE="server.info"
LOG_FILE="flask.log"

# 加载 .env（若存在）
if [ -f ".env" ]; then
  set -o allexport
  source ".env"
  set +o allexport
fi

# 激活虚拟环境
if [ -d "$VENV_PATH" ]; then
  source "$VENV_PATH/bin/activate"
else
  echo "❌ 找不到虚拟环境: $VENV_PATH"
  echo "请先运行: python3 -m venv venv && source venv/bin/activate"
  exit 1
fi

# 检查并安装依赖
check_deps() {
  echo "🔍 正在检查依赖..."
  if [ -f "pyproject.toml" ]; then
    echo "📦 解析 pyproject.toml 中的依赖"

    # 提取 dependencies (支持 [project] 或 [tool.poetry.dependencies])
    DEPS=$($PYTHON - <<'EOF'
import tomllib, sys
try:
    data = tomllib.load(open("pyproject.toml", "rb"))
except Exception as e:
    sys.exit(1)

deps = []
if "project" in data and "dependencies" in data["project"]:
    deps = data["project"]["dependencies"]
elif "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
    deps = [k+(" "+v if isinstance(v,str) else "") for k,v in data["tool"]["poetry"]["dependencies"].items() if k.lower()!="python"]

if deps:
    print(" ".join(deps))
EOF
)

    if [ -n "$DEPS" ]; then
      echo "📦 安装依赖: $DEPS"
      $PIP install $DEPS
    else
      echo "⚠️ 未找到依赖字段，跳过"
    fi
  elif [ -f "requirements.txt" ]; then
    echo "📦 根据 requirements.txt 安装依赖"
    $PIP install -r requirements.txt
  else
    echo "⚠️ 没有找到 requirements.txt 或 pyproject.toml，将逐个检查常见依赖..."
    for pkg in flask gunicorn pyyaml; do
      if ! $PYTHON -c "import $pkg" >/dev/null 2>&1; then
        read -p "❓ 缺少依赖 [$pkg]，是否安装？(y/n) " yn
        if [[ $yn == "y" ]]; then
          $PIP install "$pkg"
        else
          echo "❌ 缺少依赖，无法继续运行"
          exit 1
        fi
      fi
    done
  fi
  echo "✅ 依赖检查完成"
  echo "ℹ️ 当前 LLM provider: ${LLM_PROVIDER:-openai}, embedding model: ${LLM_EMBEDDING_MODEL:-text-embedding-3-large}, embedding path: ${LLM_EMBEDDING_PATH:-/embeddings}"
}
# 获取本机IP
get_ip() {
  for iface in en0 en1; do
    ip=$(ipconfig getifaddr $iface 2>/dev/null || true)
    if [ -n "$ip" ]; then
      echo "$iface: $ip"
    fi
  done
}

case "${1:-}" in
  start)
    check_deps
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      echo "⚠️ Flask 已经在运行 (PID=$(cat $PID_FILE))"
    else
      echo "🚀 启动 Flask..."
      nohup gunicorn -w 4 -b 0.0.0.0:5004 benort:app > "$LOG_FILE" 2>&1 &
      echo $! > "$PID_FILE"
      sleep 2

      if ! kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "❌ 启动失败，日志如下："
        tail -n 20 "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
      fi

      get_ip > "$INFO_FILE"

      echo "✅ Flask 已启动 (PID=$(cat $PID_FILE))"
      echo "🌐 本机访问: http://localhost:5004"
      echo "🌐 局域网访问:"
      while read -r line; do
        iface=$(echo $line | cut -d: -f1)
        ip=$(echo $line | cut -d: -f2- | xargs)
        echo "   - $iface: http://$ip:5004"
      done < "$INFO_FILE"

      open http://localhost:5004
    fi
    ;;
  stop)
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      echo "🛑 停止 Flask (PID=$(cat $PID_FILE))..."
      kill $(cat "$PID_FILE") && rm -f "$PID_FILE" "$INFO_FILE"
      echo "✅ 已停止"
    else
      echo "⚠️ Flask 未运行"
      rm -f "$PID_FILE" "$INFO_FILE"
    fi
    ;;
  status)
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      echo "✅ Flask 正在运行 (PID=$(cat $PID_FILE))"
      [ -f "$INFO_FILE" ] && cat "$INFO_FILE" | while read -r line; do
        iface=$(echo $line | cut -d: -f1)
        ip=$(echo $line | cut -d: -f2- | xargs)
        echo "   - $iface: http://$ip:5004"
      done
    else
      echo "⚠️ Flask 未运行"
    fi
    ;;
  restart)
    $0 stop
    $0 start
    ;;
  ip)
    if [ -f "$INFO_FILE" ]; then
      echo "📡 当前局域网 IP:"
      cat "$INFO_FILE" | while read -r line; do
        iface=$(echo $line | cut -d: -f1)
        ip=$(echo $line | cut -d: -f2- | xargs)
        echo "   - $iface: http://$ip:5004"
      done
    else
      echo "⚠️ 服务未运行，无法获取IP"
    fi
    ;;
  *)
    echo "用法: $0 {start|stop|status|restart|ip}"
    ;;
esac
