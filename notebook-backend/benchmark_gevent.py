#!/usr/bin/env python3
"""
Gevent vs Prefork性能基准测试
"""
import time
import asyncio
import requests
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CeleryBenchmark:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        
    def create_test_task(self) -> str:
        """创建测试任务并返回task_id"""
        try:
            response = requests.post(
                f"{self.api_url}/tasks/community-detection",
                headers={"Authorization": "Bearer test_token"},
                json={"user_id": 1}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("task_id")
        except Exception as e:
            logger.error(f"创建测试任务失败: {e}")
            return None
    
    def monitor_task(self, task_id: str, timeout: int = 300) -> Dict[str, Any]:
        """监控任务执行情况"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"{self.api_url}/tasks/{task_id}",
                    headers={"Authorization": "Bearer test_token"}
                )
                response.raise_for_status()
                data = response.json()
                
                status = data.get("status")
                if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    return {
                        "status": status,
                        "duration": time.time() - start_time,
                        "task_data": data
                    }
                
                time.sleep(2)  # 每2秒检查一次
                
            except Exception as e:
                logger.error(f"监控任务失败: {e}")
                time.sleep(2)
        
        return {
            "status": "TIMEOUT",
            "duration": timeout,
            "task_data": None
        }
    
    def run_single_test(self) -> Dict[str, Any]:
        """运行单个测试"""
        logger.info("开始单个测试...")
        
        # 创建任务
        task_id = self.create_test_task()
        if not task_id:
            return {"error": "Failed to create task"}
        
        logger.info(f"创建任务: {task_id}")
        
        # 监控任务
        result = self.monitor_task(task_id)
        logger.info(f"任务完成: {result['status']}, 耗时: {result['duration']:.2f}秒")
        
        return result
    
    def run_concurrent_tests(self, num_tasks: int = 3) -> List[Dict[str, Any]]:
        """运行并发测试"""
        logger.info(f"开始并发测试，任务数: {num_tasks}")
        
        results = []
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_tasks) as executor:
            futures = [executor.submit(self.run_single_test) for _ in range(num_tasks)]
            
            for i, future in enumerate(futures):
                try:
                    result = future.result(timeout=600)  # 10分钟超时
                    results.append(result)
                    logger.info(f"任务 {i+1} 完成")
                except Exception as e:
                    logger.error(f"任务 {i+1} 失败: {e}")
                    results.append({"error": str(e)})
        
        total_time = time.time() - start_time
        logger.info(f"并发测试完成，总耗时: {total_time:.2f}秒")
        
        return results
    
    def benchmark_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成基准测试报告"""
        successful_tasks = [r for r in results if r.get("status") == "COMPLETED"]
        failed_tasks = [r for r in results if r.get("status") == "FAILED"]
        error_tasks = [r for r in results if "error" in r]
        
        if successful_tasks:
            durations = [r["duration"] for r in successful_tasks]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
        else:
            avg_duration = min_duration = max_duration = 0
        
        return {
            "total_tasks": len(results),
            "successful_tasks": len(successful_tasks),
            "failed_tasks": len(failed_tasks),
            "error_tasks": len(error_tasks),
            "avg_duration": avg_duration,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "success_rate": len(successful_tasks) / len(results) if results else 0
        }

def main():
    """主函数"""
    logger.info("开始Celery性能基准测试")
    
    benchmark = CeleryBenchmark()
    
    # 单任务测试
    logger.info("=" * 50)
    logger.info("单任务测试")
    logger.info("=" * 50)
    
    single_result = benchmark.run_single_test()
    print(f"单任务结果: {json.dumps(single_result, indent=2, default=str)}")
    
    # 并发测试
    logger.info("=" * 50)
    logger.info("并发测试 (3个任务)")
    logger.info("=" * 50)
    
    concurrent_results = benchmark.run_concurrent_tests(3)
    report = benchmark.benchmark_report(concurrent_results)
    
    print("=" * 50)
    print("基准测试报告")
    print("=" * 50)
    print(f"总任务数: {report['total_tasks']}")
    print(f"成功任务数: {report['successful_tasks']}")
    print(f"失败任务数: {report['failed_tasks']}")
    print(f"错误任务数: {report['error_tasks']}")
    print(f"成功率: {report['success_rate']:.2%}")
    print(f"平均耗时: {report['avg_duration']:.2f}秒")
    print(f"最短耗时: {report['min_duration']:.2f}秒")
    print(f"最长耗时: {report['max_duration']:.2f}秒")
    
    # 保存结果
    timestamp = int(time.time())
    filename = f"benchmark_results_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "single_task": single_result,
            "concurrent_tasks": concurrent_results,
            "report": report
        }, f, indent=2, default=str)
    
    logger.info(f"结果已保存到: {filename}")

if __name__ == "__main__":
    main() 