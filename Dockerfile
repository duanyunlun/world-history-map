# ---------- 单阶段构建 + 运行：使用本地已有基础镜像 ----------
# 基础镜像来自本地（m.daocloud.io 源），无需访问 Docker Hub
FROM python:3.13-slim

WORKDIR /srv

# 构建所需：数据 + 模板 + 构建脚本
COPY build.py merge_events.py ./
COPY src/ ./src/
COPY data/ ./data/

# 烘焙为单文件自包含站点，随后清理构建期文件（镜像更小）
RUN python3 build.py \
 && test -f index.html \
 && echo "site built: $(wc -c < index.html) bytes" \
 && rm -rf /srv/data/events_parts

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/',timeout=2).status==200 else 1)"

# 静态服务（标准库，零额外依赖）
CMD ["python3", "-m", "http.server", "8000", "--bind", "0.0.0.0", "--directory", "/srv"]
