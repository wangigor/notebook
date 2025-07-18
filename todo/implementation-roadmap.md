# 技术实现路线图

## 第一阶段：数据层改造（4周）

### Week 1: 模型扩展
- [ ] 扩展实体模型：增加别名、置信度、向量表示
- [ ] 扩展关系模型：增加权重、相似度、质量分数
- [ ] 更新数据库schema和索引

### Week 2: 实体统一服务
**目标**：将简单去重升级为智能实体统一，嵌入文档解析流程

#### Day 1-2: 多维度相似度计算引擎
- [ ] 语义相似度计算器（基于embedding向量，权重40%）
  - 实体名称embedding生成
  - cosine相似度计算
  - 缓存机制优化
- [ ] 词汇相似度计算器（编辑距离+别名匹配，权重30%）
  - 字符串标准化处理
  - 编辑距离算法实现
  - 别名匹配逻辑
- [ ] 上下文相似度计算器（类型+描述+共现，权重30%）
  - 实体类型匹配
  - 描述文本相似度
  - 源文本上下文重叠度

#### Day 3-4: 自动合并决策引擎
- [ ] 阈值分级决策系统
  - 高置信度（≥0.85）：自动合并
  - 中等置信度（0.65-0.84）：冲突检测后决策
  - 低置信度（<0.65）：不合并
- [ ] 基础冲突检测机制
  - 实体类型冲突检测
  - 描述矛盾识别
  - 冲突解决策略
- [ ] 合并操作执行器
  - 主实体选择算法（按置信度）
  - 别名列表合并
  - 属性信息融合

#### Day 5: 集成到现有流程
- [ ] 修改KnowledgeExtractionService
  - 替换简单_deduplicate_entities方法
  - 集成EntitySimilarityCalculator
  - 集成EntityMergeDecisionEngine和EntityMerger
- [ ] 实体统一核心算法
  - _unify_entities_intelligently方法实现
  - 相似度矩阵构建
  - 聚类合并算法
- [ ] 性能优化和测试
  - 批量embedding生成
  - 并行相似度计算
  - 单元测试和集成测试

### Week 3: 关系增强
- [ ] 添加相似性关系计算
- [ ] 实现动态权重系统
- [ ] 构建关系质量评估

### Week 4: API接口
- [ ] 实体管理API（CRUD + 合并）
- [ ] 关系管理API（查询 + 统计）
- [ ] 图谱维护API（清理 + 优化）

## 第二阶段：搜索引擎重构（4周）

### Week 5-6: 并行搜索引擎
- [ ] 实现四种搜索策略类
  - Chunk向量搜索
  - 关系扩展搜索
  - 社区摘要搜索
  - 多跳联想搜索
- [ ] 构建并行执行框架
- [ ] 开发结果融合算法

### Week 7-8: 搜索优化
- [ ] 实现多级缓存系统
- [ ] 性能调优和索引优化
- [ ] 机器学习排序模型

## 第三阶段：Agent工作流（4周）

### Week 9-10: LangGraph工作流
- [ ] 定义Agent状态和节点
- [ ] 实现质量检测系统
- [ ] 构建差异点分析器

### Week 11-12: 迭代优化机制
- [ ] 开发迭代控制逻辑
- [ ] 实现增量搜索策略
- [ ] 构建答案融合算法

## 第四阶段：用户体验（3周）

### Week 13-14: 流式交互
- [ ] WebSocket连接管理
- [ ] 渐进式前端展示
- [ ] 实时状态同步

### Week 15: 界面完善
- [ ] 答案结构化展示
- [ ] 反馈收集机制
- [ ] 个性化设置

## 第五阶段：学习优化（2周）

### Week 16-17: 自学习系统
- [ ] 用户行为分析
- [ ] 图谱动态更新
- [ ] 性能监控告警

## 核心技术组件

### 1. 增强数据模型
```python
class EnhancedEntity:
    # 基础属性
    id: str
    name: str  
    type: str
    description: str
    properties: Dict[str, Any]
    confidence: float
    
    # 🆕 实体统一增强字段
    aliases: List[str] = []           # 别名列表
    embedding: List[float] = None     # 向量表示  
    quality_score: float = 1.0        # 质量分数
    
class EnhancedRelation: 
    # 基础关系 + 权重 + 相似度 + 质量分数
    weight: float = 1.0
    similarity_score: float = None
    quality_score: float = 1.0
```

### 2. 并行搜索引擎
```python
class ParallelSearchEngine:
    async def unified_search(query, strategies) -> results
    def fuse_results(results, query) -> ranked_results
```

### 3. Agent工作流
```python
initial_search -> generate_answer -> assess_quality -> 
analyze_gaps -> supplementary_search -> enhance_answer -> finalize
```

### 4. 流式交互
```python
WebSocket: 初始答案 -> 状态更新 -> 答案改进 -> 最终结果
```

## 关键算法

### 实体统一核心算法
```python
async def unify_entities_intelligently(entities):
    """智能实体统一主算法"""
    # 1. 为所有实体生成embedding向量
    await generate_embeddings_for_entities(entities)
    
    # 2. 构建N×N相似度矩阵
    similarity_matrix = await build_similarity_matrix(entities)
    
    # 3. 基于相似度进行聚类合并
    unified_entities = await cluster_and_merge_entities(entities, similarity_matrix)
    
    return unified_entities
```

### 多维度相似度计算
```python
def calculate_similarity(entity1, entity2):
    # 语义相似度（embedding向量cosine）40%
    semantic_sim = cosine_similarity(entity1.embedding, entity2.embedding)
    
    # 词汇相似度（编辑距离+别名匹配）30%  
    lexical_sim = max(
        edit_distance_ratio(entity1.name, entity2.name),
        check_alias_match(entity1.aliases, entity2.aliases)
    )
    
    # 上下文相似度（类型+描述+共现）30%
    contextual_sim = (
        0.5 * type_match_score(entity1.type, entity2.type) +
        0.3 * description_similarity(entity1.description, entity2.description) +
        0.2 * context_overlap(entity1.source_text, entity2.source_text)
    )
    
    return 0.4 * semantic_sim + 0.3 * lexical_sim + 0.3 * contextual_sim
```

### 自动合并决策逻辑
```python
def should_merge(entity1, entity2, similarity):
    if similarity >= 0.85:
        return True, "high_confidence_auto_merge"
    elif similarity >= 0.65:
        # 检测类型冲突
        type_conflict = entity1.type != entity2.type
        return not type_conflict, f"type_conflict: {type_conflict}"
    else:
        return False, "similarity_too_low"
```

### 实体合并执行算法
```python
def merge_entities(primary_entity, secondary_entity):
    return Entity(
        id=primary_entity.id,
        name=primary_entity.name,  # 保留主实体名称
        type=primary_entity.type,
        description=merge_descriptions(primary_entity.desc, secondary_entity.desc),
        aliases=merge_aliases(primary_entity.aliases, secondary_entity.aliases, secondary_entity.name),
        confidence=max(primary_entity.confidence, secondary_entity.confidence),
        embedding=primary_entity.embedding,
        quality_score=calculate_merged_quality(primary_entity, secondary_entity)
    )
```

### 搜索结果融合
- 去重 -> 分数归一化 -> 动态权重 -> 加权融合

### 质量评估
- 相关性 + 完整性 + 一致性 = 综合质量分数

## 验收标准

### 功能指标
- [x] 四种搜索模式正常工作
- [x] 实体统一准确率 > 85%
- [x] Agent工作流完整执行

### 性能指标  
- [x] 初始答案 < 2秒
- [x] 最终答案 < 10秒
- [x] 搜索召回率提升 > 40%

## 风险与应对

### 技术风险
1. **并行搜索性能** -> 资源限制 + 降级策略
2. **实体合并错误** -> 基础回滚机制 + 质量监控 + 阈值调优
3. **工作流复杂度** -> 模块化设计 + 充分测试 + 监控告警
4. **相似度计算性能** -> 批量处理 + 缓存优化 + 并行计算

### 业务风险
1. **响应时间** -> 性能优化 + 渐进式展示
2. **数据质量** -> 质量控制 + 定期清理

---

*总计17周，需要2-3名高级工程师投入* 