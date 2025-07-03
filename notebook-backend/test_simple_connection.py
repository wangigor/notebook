#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化的Neo4j连接测试脚本
仅测试基本连接和服务初始化
"""

import os
import sys
import asyncio
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.neo4j_service import Neo4jService
from app.services.neo4j_graph_service import Neo4jGraphService

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_neo4j_connection():
    """测试Neo4j基本连接"""
    logger.info("🚀 开始Neo4j连接测试")
    logger.info(f"📋 配置信息:")
    logger.info(f"   URI: {settings.NEO4J_URI}")
    logger.info(f"   Database: {settings.NEO4J_DATABASE}")
    logger.info(f"   Username: {settings.NEO4J_USERNAME}")
    logger.info("")
    
    try:
        # 1. 测试基础Neo4j服务连接
        logger.info("1️⃣ 测试基础Neo4j服务连接...")
        neo4j_service = Neo4jService()
        result = neo4j_service.execute_query("RETURN 'Neo4j基础连接成功' as message")
        if result:
            logger.info(f"✅ 基础连接成功: {result[0]['message']}")
        else:
            logger.error("❌ 基础连接失败：无返回结果")
            return False
        
        # 2. 测试图谱服务初始化
        logger.info("2️⃣ 测试图谱服务初始化...")
        graph_service = Neo4jGraphService()
        test_result = await graph_service.test_connection()
        if test_result:
            logger.info("✅ 图谱服务初始化成功")
        else:
            logger.error("❌ 图谱服务初始化失败")
            return False
        
        # 3. 测试简单查询
        logger.info("3️⃣ 测试基本查询功能...")
        query_result = graph_service.neo4j_service.execute_query("MATCH (n) RETURN count(n) as node_count")
        if query_result:
            node_count = query_result[0]['node_count']
            logger.info(f"✅ 查询成功：数据库中共有 {node_count} 个节点")
        else:
            logger.warning("⚠️ 查询执行成功，但数据库可能为空")
        
        # 4. 测试索引创建
        logger.info("4️⃣ 测试索引管理功能...")
        await graph_service.ensure_indexes()
        logger.info("✅ 索引管理功能正常")
        
        logger.info("")
        logger.info("🎉 所有连接测试通过！Neo4j服务正常运行。")
        return True
        
    except Exception as e:
        logger.error(f"❌ 连接测试失败: {str(e)}")
        return False

async def main():
    """主函数"""
    success = await test_neo4j_connection()
    if success:
        logger.info("✨ Neo4j替换准备就绪，可以正常使用！")
        return 0
    else:
        logger.error("💥 连接测试失败，请检查Neo4j配置和服务状态")
        return 1

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试执行异常: {str(e)}")
        sys.exit(1) 