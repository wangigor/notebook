#!/bin/bash

# macOS 系统需要设置此环境变量避免fork安全问题
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# 设置环境变量
export PYTHONPATH=$PYTHONPATH:$(pwd)
export ENVIRONMENT=${ENVIRONMENT:-development}

# 启动Celery工作节点
echo "启动Celery工作节点..."
celery -A app.celery_app worker -l info -Q document_processing -c 2 