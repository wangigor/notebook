#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API端点测试脚本
测试Neo4j替换后的API功能
"""

import os
import sys
import asyncio
import logging
import requests
import json
import time

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIEndpointTester:
    """API端点测试器"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
    
    def log_test_result(self, test_name: str, success: bool, message: str, details: dict = None):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "message": message,
            "details": details or {}
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} | {test_name}: {message}")
        if details:
            logger.info(f"        Details: {details}")
    
    def test_health_check(self):
        """测试健康检查端点"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                self.log_test_result(
                    "健康检查", True, "服务运行正常",
                    {"status_code": response.status_code, "response": response.json()}
                )
                return True
            else:
                self.log_test_result(
                    "健康检查", False, f"服务状态异常: {response.status_code}",
                    {"status_code": response.status_code}
                )
                return False
        except Exception as e:
            self.log_test_result(
                "健康检查", False, f"连接失败: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    def test_agent_config(self):
        """测试代理配置端点"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/agents/config")
            if response.status_code == 200:
                config = response.json()
                # 检查是否包含Neo4j相关配置
                vector_store_url = config.get("vector_store_url", "")
                if "neo4j" in vector_store_url.lower() or "bolt://" in vector_store_url:
                    self.log_test_result(
                        "代理配置", True, "配置已更新为Neo4j",
                        {"vector_store_url": vector_store_url, "config": config}
                    )
                    return True
                else:
                    self.log_test_result(
                        "代理配置", False, "配置未更新为Neo4j",
                        {"vector_store_url": vector_store_url}
                    )
                    return False
            else:
                self.log_test_result(
                    "代理配置", False, f"获取配置失败: {response.status_code}",
                    {"status_code": response.status_code}
                )
                return False
        except Exception as e:
            self.log_test_result(
                "代理配置", False, f"请求失败: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    def test_agent_query(self):
        """测试代理查询端点"""
        try:
            test_payload = {
                "query": "什么是图数据库？",
                "context": {"use_retrieval": True},
                "session_id": "test_session_001"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/agents/query",
                json=test_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if "answer" in result:
                    self.log_test_result(
                        "代理查询", True, "查询成功",
                        {
                            "query": test_payload["query"],
                            "answer_length": len(result["answer"]),
                            "has_sources": "sources" in result
                        }
                    )
                    return True
                else:
                    self.log_test_result(
                        "代理查询", False, "响应格式不正确",
                        {"response": result}
                    )
                    return False
            else:
                self.log_test_result(
                    "代理查询", False, f"查询失败: {response.status_code}",
                    {"status_code": response.status_code, "response": response.text}
                )
                return False
        except Exception as e:
            self.log_test_result(
                "代理查询", False, f"请求异常: {str(e)}",
                {"error": str(e)}
            )
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始API端点测试")
        logger.info(f"🔧 测试目标: {self.base_url}")
        logger.info("")
        
        # 执行所有测试
        tests = [
            ("健康检查", self.test_health_check),
            ("代理配置", self.test_agent_config),
            ("代理查询", self.test_agent_query)
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"测试 {test_name} 执行异常: {str(e)}")
                all_passed = False
        
        # 输出测试报告
        self.print_test_report(all_passed)
        return all_passed
    
    def print_test_report(self, all_passed: bool):
        """打印测试报告"""
        logger.info("=" * 80)
        logger.info("📊 API测试报告")
        logger.info("=" * 80)
        
        passed_count = sum(1 for result in self.test_results if result["success"])
        failed_count = len(self.test_results) - passed_count
        
        logger.info(f"总测试数: {len(self.test_results)}")
        logger.info(f"通过测试: {passed_count} ✅")
        logger.info(f"失败测试: {failed_count} ❌")
        logger.info(f"通过率: {(passed_count/len(self.test_results)*100):.1f}%")
        logger.info("")
        
        if failed_count > 0:
            logger.info("❌ 失败的测试:")
            for result in self.test_results:
                if not result["success"]:
                    logger.info(f"   - {result['test_name']}: {result['message']}")
        
        logger.info("")
        overall_status = "✅ 所有测试通过" if all_passed else "❌ 部分测试失败"
        logger.info(f"🎯 总体结果: {overall_status}")
        
        if all_passed:
            logger.info("🎉 API端点工作正常！Neo4j替换后系统功能完整。")
        else:
            logger.warning("⚠️  部分API端点存在问题，需要进一步检查。")
        
        logger.info("=" * 80)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="API端点测试")
    parser.add_argument("--url", default="http://localhost:8000", help="API基础URL")
    args = parser.parse_args()
    
    tester = APIEndpointTester(args.url)
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        result = main()
        sys.exit(result)
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试执行异常: {str(e)}")
        sys.exit(1) 