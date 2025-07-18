# -*- coding: utf-8 -*-
"""
自主Agent专用工具集
为自主实体去重Agent提供优化的工具
"""
from typing import Dict, Any, List
from langchain_core.tools import tool
import logging

from app.services.wikipedia_mcp_server import get_wikipedia_mcp_server
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


@tool
def smart_entity_search(entity_name: str, entity_type: str = None, context: str = None) -> dict:
    """智能实体搜索 - 自主Agent专用的增强搜索工具
    
    这是一个为自主Agent优化的搜索工具，提供更智能的搜索策略和结果分析。
    
    Args:
        entity_name: 要搜索的实体名称
        entity_type: 实体类型（如"组织"、"人物"、"产品"等）
        context: 额外的上下文信息，帮助消除歧义
    
    Returns:
        包含搜索结果和智能分析的字典：
        - found: 是否找到匹配结果
        - primary_result: 主要搜索结果
        - disambiguation: 消歧义信息
        - confidence: 结果可信度
        - analysis: 智能分析结果
        - suggestions: 后续建议
    """
    try:
        logger.info(f"智能搜索: {entity_name} (类型: {entity_type})")
        
        # 获取Wikipedia服务
        wikipedia_server = get_wikipedia_mcp_server()
        
        # 执行基础搜索
        base_result = wikipedia_server.search_entity(
            entity_name=entity_name,
            entity_type=entity_type
        )
        
        # 增强结果分析
        enhanced_result = _enhance_search_result(base_result, entity_name, entity_type, context)
        
        logger.info(f"智能搜索完成: {entity_name} -> 置信度={enhanced_result.get('confidence', 0)}")
        
        return enhanced_result
        
    except Exception as e:
        logger.error(f"智能搜索失败: {str(e)}")
        return {
            "found": False,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "error": str(e),
            "confidence": 0.0,
            "analysis": "搜索过程中出现错误",
            "suggestions": ["尝试使用不同的搜索词", "检查实体名称拼写"]
        }


@tool  
def compare_entities_semantic(entity1_name: str, entity2_name: str, 
                            entity1_desc: str = "", entity2_desc: str = "") -> dict:
    """语义实体比较 - 深度语义相似度分析
    
    使用高级语义分析技术比较两个实体的相似度，专为自主Agent优化。
    
    Args:
        entity1_name: 第一个实体名称
        entity2_name: 第二个实体名称  
        entity1_desc: 第一个实体描述（可选）
        entity2_desc: 第二个实体描述（可选）
    
    Returns:
        详细的语义比较结果：
        - similarity_score: 语义相似度分数 (0-1)
        - name_similarity: 名称相似度
        - description_similarity: 描述相似度  
        - analysis: 详细分析
        - confidence: 分析置信度
        - recommendation: 合并建议
    """
    try:
        logger.info(f"语义比较: {entity1_name} vs {entity2_name}")
        
        # 获取embedding服务
        embedding_service = get_embedding_service()
        
        # 计算名称相似度
        name_similarity = _calculate_name_similarity(entity1_name, entity2_name)
        
        # 计算描述相似度（如果有描述）
        description_similarity = 0.0
        if entity1_desc and entity2_desc:
            description_similarity = _calculate_description_similarity(
                entity1_desc, entity2_desc, embedding_service
            )
        
        # 综合相似度
        overall_similarity = _calculate_overall_similarity(
            name_similarity, description_similarity, entity1_desc, entity2_desc
        )
        
        # 生成分析和建议
        analysis, recommendation = _generate_similarity_analysis(
            entity1_name, entity2_name, name_similarity, 
            description_similarity, overall_similarity
        )
        
        result = {
            "similarity_score": overall_similarity,
            "name_similarity": name_similarity,
            "description_similarity": description_similarity,
            "analysis": analysis,
            "confidence": _calculate_comparison_confidence(name_similarity, description_similarity),
            "recommendation": recommendation,
            "entity1_name": entity1_name,
            "entity2_name": entity2_name
        }
        
        logger.info(f"语义比较完成: 相似度={overall_similarity:.3f}, 建议={recommendation}")
        
        return result
        
    except Exception as e:
        logger.error(f"语义比较失败: {str(e)}")
        return {
            "similarity_score": 0.0,
            "name_similarity": 0.0,
            "description_similarity": 0.0,
            "analysis": f"比较过程中出现错误: {str(e)}",
            "confidence": 0.0,
            "recommendation": "keep_separate",
            "error": str(e)
        }


def _enhance_search_result(base_result: dict, entity_name: str, 
                          entity_type: str, context: str) -> dict:
    """增强搜索结果"""
    enhanced = base_result.copy()
    
    # 计算置信度
    confidence = 0.0
    if base_result.get("found"):
        confidence = 0.8  # 基础置信度
        
        # 根据标题匹配度调整
        title = base_result.get("title", "")
        if title and entity_name.lower() in title.lower():
            confidence += 0.1
        
        # 根据类型匹配度调整
        if entity_type and _type_matches_content(entity_type, base_result.get("summary", "")):
            confidence += 0.1
    
    enhanced["confidence"] = min(confidence, 1.0)
    
    # 生成智能分析
    enhanced["analysis"] = _generate_search_analysis(base_result, entity_name, entity_type)
    
    # 生成建议
    enhanced["suggestions"] = _generate_search_suggestions(base_result, confidence)
    
    return enhanced


def _calculate_name_similarity(name1: str, name2: str) -> float:
    """计算名称相似度"""
    name1_clean = name1.lower().strip()
    name2_clean = name2.lower().strip()
    
    # 完全匹配
    if name1_clean == name2_clean:
        return 1.0
    
    # 包含关系
    if name1_clean in name2_clean or name2_clean in name1_clean:
        return 0.8
    
    # 词汇重叠
    words1 = set(name1_clean.split())
    words2 = set(name2_clean.split())
    
    if words1 and words2:
        overlap = len(words1 & words2) / len(words1 | words2)
        return overlap * 0.7
    
    return 0.0


def _calculate_description_similarity(desc1: str, desc2: str, embedding_service) -> float:
    """计算描述相似度"""
    try:
        # 这里可以使用更复杂的语义相似度计算
        # 简化版本：基于词汇重叠
        words1 = set(desc1.lower().split())
        words2 = set(desc2.lower().split())
        
        if words1 and words2:
            overlap = len(words1 & words2) / len(words1 | words2)
            return overlap
        
        return 0.0
    except Exception:
        return 0.0


def _calculate_overall_similarity(name_sim: float, desc_sim: float, 
                                desc1: str, desc2: str) -> float:
    """计算综合相似度"""
    if desc1 and desc2:
        # 有描述时，名称和描述各占50%
        return (name_sim + desc_sim) / 2
    else:
        # 只有名称时，主要依靠名称相似度
        return name_sim


def _generate_similarity_analysis(entity1: str, entity2: str, name_sim: float,
                                desc_sim: float, overall_sim: float) -> tuple:
    """生成相似度分析和建议"""
    analysis_parts = []
    
    if name_sim >= 0.8:
        analysis_parts.append("名称高度相似")
    elif name_sim >= 0.5:
        analysis_parts.append("名称中等相似")
    else:
        analysis_parts.append("名称相似度低")
    
    if desc_sim > 0:
        if desc_sim >= 0.7:
            analysis_parts.append("描述内容相关")
        else:
            analysis_parts.append("描述存在差异")
    
    analysis = ", ".join(analysis_parts)
    
    # 生成建议
    if overall_sim >= 0.85:
        recommendation = "merge_recommended"
    elif overall_sim >= 0.6:
        recommendation = "needs_verification"
    else:
        recommendation = "keep_separate"
    
    return analysis, recommendation


def _calculate_comparison_confidence(name_sim: float, desc_sim: float) -> float:
    """计算比较置信度"""
    confidence = 0.7  # 基础置信度
    
    if name_sim >= 0.9 or name_sim <= 0.1:
        confidence += 0.2  # 极端相似度值增加置信度
    
    if desc_sim > 0:
        confidence += 0.1  # 有描述比较增加置信度
    
    return min(confidence, 1.0)


def _type_matches_content(entity_type: str, content: str) -> bool:
    """检查实体类型是否与内容匹配"""
    type_keywords = {
        "组织": ["company", "corporation", "organization", "企业", "公司", "机构"],
        "人物": ["person", "人", "个人", "born", "died"],
        "产品": ["product", "software", "device", "产品", "设备"],
        "地点": ["city", "country", "location", "地区", "城市", "国家"]
    }
    
    keywords = type_keywords.get(entity_type, [])
    content_lower = content.lower()
    
    return any(keyword in content_lower for keyword in keywords)


def _generate_search_analysis(result: dict, entity_name: str, entity_type: str) -> str:
    """生成搜索分析"""
    if not result.get("found"):
        return f"未找到'{entity_name}'的相关信息，可能是新兴实体或拼写错误"
    
    analysis_parts = []
    title = result.get("title", "")
    summary = result.get("summary", "")
    
    if title:
        if entity_name.lower() in title.lower():
            analysis_parts.append("标题与搜索实体高度匹配")
        else:
            analysis_parts.append("标题与搜索实体部分匹配")
    
    if summary and len(summary) > 100:
        analysis_parts.append("找到详细的实体信息")
    elif summary:
        analysis_parts.append("找到基础的实体信息")
    
    return "; ".join(analysis_parts) if analysis_parts else "找到相关信息"


def _generate_search_suggestions(result: dict, confidence: float) -> List[str]:
    """生成搜索建议"""
    suggestions = []
    
    if not result.get("found"):
        suggestions.extend([
            "尝试使用实体的别名或全称搜索",
            "检查实体名称的拼写",
            "考虑使用更通用的搜索词"
        ])
    elif confidence < 0.7:
        suggestions.extend([
            "结果可信度较低，建议进一步验证",
            "考虑搜索相关实体进行对比"
        ])
    else:
        suggestions.append("搜索结果可信度较高，可用于决策参考")
    
    return suggestions


def get_autonomous_agent_tools() -> List:
    """获取自主Agent专用工具集"""
    return [
        smart_entity_search,
        compare_entities_semantic
    ]