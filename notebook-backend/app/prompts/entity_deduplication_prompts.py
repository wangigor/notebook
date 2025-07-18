# -*- coding: utf-8 -*-
"""
实体去重提示词模板（工具调用增强版）
为LangGraph实体去重Agent提供智能工具调用提示词
"""

from typing import List, Dict, Any

def build_tool_aware_analysis_prompt(prescreened_pairs: List[Dict[str, Any]], entity_type: str) -> str:
    """构建工具感知的分析提示词
    
    Args:
        prescreened_pairs: 预筛选的实体对
        entity_type: 实体类型
        
    Returns:
        工具感知的分析提示词
    """
    
    type_mapping = {
        "组织": "Organization", "人物": "Person", "地点": "Location", 
        "产品": "Product", "技术": "Technology", "时间": "Time", "事件": "Event"
    }
    english_type = type_mapping.get(entity_type, entity_type)
    
    prompt = "你是一个专业的{}实体去重专家，拥有丰富的世界知识和智能工具使用能力。".format(english_type) + """

🎯 任务目标：
分析以下预筛选的实体对，判断哪些是重复的同一实体，哪些是不同实体。

🧠 智能分析策略：
作为大语言模型，你已经掌握了大量的实体知识。请优先使用你的内在知识进行判断：

1. **优先依托内在知识**：
   - 对于知名实体（苹果公司、微软、斯坦福大学等），直接基于你的知识判断
   - 对于常见的人物、组织、产品，信任你的训练数据中的信息
   - 只有当你真正不确定或遇到模糊情况时，才考虑使用外部工具

2. **智能工具使用决策**：
   - 当实体名称存在歧义时（如"苹果"可能是水果或公司）
   - 当遇到不熟悉的专业术语或新兴概念时
   - 当两个实体看似相关但你不能确定是否为同一实体时
   - 当你的置信度低于80%时

🔧 可用工具（按需使用）：
- search_wikipedia_entity: 搜索Wikipedia获取权威信息
  - 使用场景：仅当你基于内在知识无法确定时
  - 参数：entity_name (实体名称), entity_type (实体类型，可选)
  - 请在工具描述中说明为什么需要搜索此实体

⚠️ 超保守原则：
- 宁可保留重复，也不能错误合并不同实体
- 只有99%确信是同一实体时才建议合并
- 对于竞争对手（如苹果vs微软）绝不合并

💡 决策示例：
- "苹果公司" vs "Apple Inc" → 直接判断：同一实体（无需搜索）
- "蒂姆·库克" vs "史蒂夫·乔布斯" → 直接判断：不同人物（无需搜索）
- "某个不熟悉的专业术语" → 可考虑搜索验证

📊 待分析的实体对：
"""
    
    for i, pair in enumerate(prescreened_pairs[:25]):  # 限制数量以控制prompt长度
        prompt += "\n对 {}:\n".format(i+1)
        prompt += "  实体A: {}\n".format(pair['entity1_name'])
        prompt += "  实体B: {}\n".format(pair['entity2_name'])
        prompt += "  向量相似度: {:.3f}\n".format(pair.get('vector_similarity', 0.0))
    
    if len(prescreened_pairs) > 25:
        prompt += "\n... 还有 {} 对实体（仅显示前25对）\n".format(len(prescreened_pairs) - 25)
    
    prompt += """

📋 智能分析步骤：
1. **知识检索阶段**：逐个分析每对实体，优先使用你的内在知识
2. **置信度评估**：如果基于内在知识的置信度 ≥ 80%，直接做出判断
3. **可选验证阶段**：仅对置信度 < 80% 的情况考虑使用工具验证
4. **最终决策**：综合内在知识和（可选的）外部信息做出判断

⚖️ 判断标准：
- high confidence (0.95+): 确信是同一实体（如"苹果公司"vs"Apple Inc"）
- medium confidence (0.7-0.94): 可能相同，但建议保持独立（超保守）
- low confidence (<0.7): 明显不同，保持独立

🎯 工具使用建议：
- 对于著名公司、知名人物、常见产品：无需搜索，直接判断
- 对于专业术语、模糊概念、不确定实体：可考虑搜索
- 搜索决策应基于"真实需要"而非"可能有用"

🎯 最终输出格式：
完成所有分析后，请提供JSON格式的结果：

```json
{
  "analysis_summary": "完成""" + str(len(prescreened_pairs)) + """对实体的智能分析",
  "merge_groups": [
    {
      "primary_entity_index": 0,
      "duplicate_indices": [1],
      "merged_name": "确认的实体名称",
      "merged_description": "合并理由",
      "confidence": 0.98,
      "reason": "基于Wikipedia搜索确认为同一实体",
      "wikipedia_evidence": "具体的Wikipedia证据"
    }
  ],
  "independent_entities": [2, 3, 4, 5],
  "uncertain_cases": [
    {
      "entities": [6, 7],
      "reason": "信息不足，建议保持独立"
    }
  ]
}
```

开始智能分析吧！请优先使用你的内在知识，仅在必要时使用search_wikipedia_entity工具。"""
    
    return prompt


def parse_tool_aware_analysis_result(response_content: str) -> Dict[str, Any]:
    """解析工具感知分析结果
    
    Args:
        response_content: LLM响应内容
        
    Returns:
        解析后的分析结果
    """
    import json
    import re
    
    try:
        # 尝试提取JSON内容
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
            return json.loads(json_content)
        
        # 尝试直接查找JSON对象
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)
        if json_match:
            json_content = json_match.group(0)
            return json.loads(json_content)
        
        # 如果没有找到JSON，返回基于文本的解析
        return {
            "analysis_summary": "无法解析JSON格式，基于文本分析",
            "merge_groups": [],
            "independent_entities": [],
            "uncertain_cases": [],
            "raw_response": response_content
        }
        
    except Exception as e:
        # 解析失败，返回保守结果
        return {
            "analysis_summary": "解析失败: {}".format(str(e)),
            "merge_groups": [],
            "independent_entities": [],
            "uncertain_cases": [],
            "parse_error": str(e),
            "raw_response": response_content
        }


def process_entity_pairs_from_tool_analysis(analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从工具分析结果中处理实体对
    
    Args:
        analysis_result: 分析结果
        
    Returns:
        处理后的实体对列表
    """
    entity_pairs = []
    
    # 处理合并组
    for group in analysis_result.get("merge_groups", []):
        primary_idx = group.get("primary_entity_index")
        duplicate_indices = group.get("duplicate_indices", [])
        
        for dup_idx in duplicate_indices:
            entity_pairs.append({
                "entity1_index": primary_idx,
                "entity2_index": dup_idx,
                "entity1_name": "Entity {}".format(primary_idx),
                "entity2_name": "Entity {}".format(dup_idx),
                "confidence": group.get("confidence", 0.0),
                "similarity_score": group.get("confidence", 0.0),
                "reason": group.get("reason", ""),
                "needs_verification": False,  # 已经通过工具验证
                "wikipedia_evidence": group.get("wikipedia_evidence", ""),
                "tool_verified": True
            })
    
    return entity_pairs


# === 向后兼容性类 ===

class EntityDeduplicationPrompts:
    """向后兼容的实体去重提示词类
    
    这个类提供与旧版本兼容的接口，内部使用新的工具感知函数
    """
    
    def __init__(self):
        """初始化提示词类"""
        pass
    
    def generate_deduplication_prompt(self, entities: List[Dict[str, Any]], entity_type: str) -> str:
        """生成去重提示词（兼容性方法）
        
        Args:
            entities: 实体列表
            entity_type: 实体类型
            
        Returns:
            生成的提示词字符串
        """
        # 将实体列表转换为实体对格式，以适配新的函数
        prescreened_pairs = []
        
        # 生成所有可能的实体对
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                prescreened_pairs.append({
                    "entity1_index": i,
                    "entity2_index": j,
                    "entity1_name": entities[i].get("name", "Entity {}".format(i)),
                    "entity2_name": entities[j].get("name", "Entity {}".format(j)),
                    "vector_similarity": 0.5  # 默认相似度
                })
        
        # 使用新的工具感知提示词函数，但移除工具相关内容用于传统模式
        tool_aware_prompt = build_tool_aware_analysis_prompt(prescreened_pairs, entity_type)
        
        # 转换为传统模式的提示词（移除工具调用相关内容）
        traditional_prompt = self._convert_to_traditional_prompt(tool_aware_prompt, prescreened_pairs, entity_type)
        
        return traditional_prompt
    
    def _convert_to_traditional_prompt(self, tool_aware_prompt: str, prescreened_pairs: List[Dict[str, Any]], entity_type: str) -> str:
        """将工具感知提示词转换为传统提示词"""
        
        type_mapping = {
            "组织": "Organization", "人物": "Person", "地点": "Location", 
            "产品": "Product", "技术": "Technology", "时间": "Time", "事件": "Event"
        }
        english_type = type_mapping.get(entity_type, entity_type)
        
        # 构建传统的分析提示词（不包含工具调用）
        prompt = "你是一个专业的{}实体去重专家。".format(english_type) + """

🎯 任务目标：
分析以下实体对，判断哪些是重复的同一实体，哪些是不同实体。

⚠️ 超保守原则：
- 宁可保留重复，也不能错误合并不同实体
- 只有99%确信是同一实体时才建议合并
- 对于人名、组织名等，即使相似也要极度谨慎

📊 待分析的实体对：
"""
        
        for i, pair in enumerate(prescreened_pairs[:30]):  # 限制数量
            prompt += "\n对 {}:\n".format(i+1)
            prompt += "  实体A: {}\n".format(pair['entity1_name'])
            prompt += "  实体B: {}\n".format(pair['entity2_name'])
            if pair.get('vector_similarity'):
                prompt += "  相似度: {:.3f}\n".format(pair['vector_similarity'])
        
        if len(prescreened_pairs) > 30:
            prompt += "\n... 还有 {} 对实体（仅显示前30对）\n".format(len(prescreened_pairs) - 30)
        
        prompt += """

⚖️ 判断标准：
- high confidence (0.95+): 确信是同一实体（如"苹果公司"vs"Apple Inc"）
- medium confidence (0.7-0.94): 可能相同，但需要更多验证
- low confidence (<0.7): 不太可能相同，建议保持独立

🎯 输出格式：
请提供JSON格式的分析结果：

```json
{
  "analysis_summary": "保守分析完成",
  "merge_groups": [
    {
      "primary_entity_index": 0,
      "duplicate_indices": [1],
      "merged_name": "确认的实体名称",
      "merged_description": "合并理由",
      "confidence": 0.98,
      "reason": "基于名称分析确认为同一实体"
    }
  ],
  "independent_entities": [2, 3, 4, 5],
  "uncertain_cases": [
    {
      "entities": [6, 7],
      "reason": "信息不足，建议保持独立"
    }
  ]
}
```

开始分析吧！"""
        
        return prompt