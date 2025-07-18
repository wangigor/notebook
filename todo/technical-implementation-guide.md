# 🔧 图知识库升级技术实现指南

## 📁 项目结构设计

### 新增目录结构
```
notebook-backend/app/
├── core/
│   └── graph_rag/                    # 新增：GraphRAG核心模块
│       ├── __init__.py
│       ├── search_engine.py          # 并行搜索引擎
│       ├── entity_unification.py     # 实体统一服务
│       ├── relation_enhancement.py   # 关系增强服务
│       └── agent_workflow.py         # Agent工作流
├── models/
│   ├── enhanced_entities.py          # 增强的实体模型
│   └── enhanced_relations.py         # 增强的关系模型
├── services/
│   ├── search/                       # 搜索服务模块
│   │   ├── chunk_vector_search.py
│   │   ├── relation_expansion_search.py
│   │   ├── community_summary_search.py
│   │   └── multi_hop_search.py
│   ├── learning/                     # 学习优化模块
│   │   ├── user_behavior_analyzer.py
│   │   ├── graph_learning_service.py
│   │   └── quality_feedback_service.py
│   └── streaming/                    # 流式交互模块
│       ├── websocket_handler.py
│       └── progressive_response.py
```

## 🏗️ 核心技术架构

### 1. 数据模型扩展

#### 增强实体模型（简化版）
```python
class EnhancedEntity(BaseModel):
    # 基础属性（保留现有Entity字段）
    id: str
    name: str
    type: str
    description: Optional[str] = None
    properties: Dict[str, Any]
    confidence: float
    source_text: str
    start_pos: int
    end_pos: int
    
    # 🆕 实体统一增强字段
    aliases: List[str] = []           # 别名列表
    embedding: Optional[List[float]] = None  # 向量表示
    quality_score: float = 1.0        # 质量分数
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
```

#### 增强关系模型
```python
class EnhancedRelation(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    relation_name: str
    
    # 增强属性
    weight: float = 1.0
    confidence: float = 1.0
    similarity_score: Optional[float] = None
    
    # 使用统计
    usage_count: int = 0
    success_rate: float = 1.0
    
    # 质量评估
    quality_score: float = 1.0
    user_feedback_score: Optional[float] = None
```

### 2. 并行搜索引擎

#### 搜索策略接口
```python
class BaseSearchStrategy(ABC):
    @abstractmethod
    async def search(self, query: str, k: int = 4) -> List[SearchResult]:
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        pass

class ParallelSearchEngine:
    def __init__(self):
        self.strategies: Dict[str, BaseSearchStrategy] = {}
        
    async def unified_search(self, query: str, k: int = 10) -> Dict[str, List[SearchResult]]:
        # 并行执行所有搜索策略
        tasks = [strategy.search(query, k) for strategy in self.strategies.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return self._organize_results(results)
    
    def fuse_results(self, search_results: Dict[str, List[SearchResult]], query: str) -> List[SearchResult]:
        # 去重、归一化、加权融合
        unique_results = self._deduplicate_results(search_results)
        normalized_results = self._normalize_scores(unique_results)
        weights = self._calculate_dynamic_weights(query, search_results)
        return self._apply_weighted_fusion(normalized_results, weights)
```

### 3. Agent工作流设计

#### 工作流状态
```python
@dataclass
class AgentState:
    query: str
    current_answer: Optional[str] = None
    search_results: Dict[str, Any] = None
    quality_score: float = 0.0
    iteration_count: int = 0
    gaps_identified: List[str] = None
    final_answer: Optional[str] = None
    status: str = "initialized"
```

#### LangGraph工作流
```python
class GraphRAGAgent:
    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("initial_search", self._initial_search)
        workflow.add_node("generate_answer", self._generate_answer)
        workflow.add_node("assess_quality", self._assess_quality)
        workflow.add_node("analyze_gaps", self._analyze_gaps)
        workflow.add_node("supplementary_search", self._supplementary_search)
        workflow.add_node("enhance_answer", self._enhance_answer)
        workflow.add_node("finalize", self._finalize)
        
        # 设置流程
        workflow.set_entry_point("initial_search")
        workflow.add_edge("initial_search", "generate_answer")
        workflow.add_conditional_edges(
            "assess_quality",
            self._should_continue_iteration,
            {"continue": "analyze_gaps", "finalize": "finalize"}
        )
        
        return workflow.compile()
```

### 4. 实体统一服务（嵌入文档解析流程）

#### 集成到KnowledgeExtractionService
```python
class KnowledgeExtractionService:
    def __init__(self):
        # ... 现有初始化 ...
        
        # 🆕 实体统一组件
        self.embedding_service = EmbeddingService()
        self.similarity_calculator = EntitySimilarityCalculator(self.embedding_service)
        self.merge_decision_engine = EntityMergeDecisionEngine()
        self.entity_merger = EntityMerger()

    async def extract_knowledge_from_chunks(self, chunks):
        # ... 现有LLM实体抽取逻辑 ...
        
        # 🔄 替换简单去重为智能统一
        unified_entities = await self._unify_entities_intelligently(all_entities)
        
        return unified_entities, relationships
```

#### 智能实体统一核心算法
```python
async def _unify_entities_intelligently(self, entities):
    """智能实体统一主算法"""
    logger.info(f"开始智能统一 {len(entities)} 个实体")
    
    # 1. 批量生成embedding向量
    await self._generate_embeddings_for_entities(entities)
    
    # 2. 构建相似度矩阵
    similarity_matrix = await self._build_similarity_matrix(entities)
    
    # 3. 基于相似度进行聚类合并
    unified_entities = await self._cluster_and_merge_entities(entities, similarity_matrix)
    
    logger.info(f"智能统一完成: {len(entities)} -> {len(unified_entities)}")
    return unified_entities

async def _generate_embeddings_for_entities(self, entities):
    """批量为实体生成embedding向量"""
    entity_names = [entity.name for entity in entities if entity.embedding is None]
    if entity_names:
        embeddings = await self.embedding_service.get_embeddings(entity_names)
        embedding_idx = 0
        for entity in entities:
            if entity.embedding is None:
                entity.embedding = embeddings[embedding_idx]
                embedding_idx += 1

async def _cluster_and_merge_entities(self, entities, similarity_matrix):
    """基于相似度聚类并合并实体"""
    n = len(entities)
    merged = [False] * n
    unified_entities = []
    
    for i in range(n):
        if merged[i]:
            continue
            
        # 寻找与当前实体相似的所有实体
        cluster = [i]
        for j in range(i + 1, n):
            if merged[j]:
                continue
                
            similarity = similarity_matrix[i][j]
            should_merge, reason = self.merge_decision_engine.should_merge(
                entities[i], entities[j], similarity
            )
            
            if should_merge:
                cluster.append(j)
                merged[j] = True
        
        # 合并聚类中的所有实体
        if len(cluster) == 1:
            unified_entities.append(entities[i])
        else:
            # 选择置信度最高的作为主实体
            primary_idx = max(cluster, key=lambda idx: entities[idx].confidence)
            primary_entity = entities[primary_idx]
            
            # 将其他实体合并到主实体
            for idx in cluster:
                if idx != primary_idx:
                    primary_entity = self.entity_merger.merge_entities(
                        primary_entity, entities[idx]
                    )
            
            unified_entities.append(primary_entity)
        
        merged[i] = True
    
    return unified_entities
```

#### 多维度相似度计算器
```python
class EntitySimilarityCalculator:
    def __init__(self, embedding_service):
        self.embedding_service = embedding_service
    
    async def calculate_similarity(self, entity1, entity2) -> float:
        # 语义相似度 (40%)
        semantic_sim = await self._calculate_semantic_similarity(entity1, entity2)
        
        # 词汇相似度 (30%)  
        lexical_sim = self._calculate_lexical_similarity(entity1, entity2)
        
        # 上下文相似度 (30%)
        contextual_sim = self._calculate_contextual_similarity(entity1, entity2)
        
        return 0.4 * semantic_sim + 0.3 * lexical_sim + 0.3 * contextual_sim
    
    async def _calculate_semantic_similarity(self, entity1, entity2) -> float:
        """基于embedding计算语义相似度"""
        try:
            if entity1.embedding is None or entity2.embedding is None:
                return 0.0
            
            import numpy as np
            vec1 = np.array(entity1.embedding)
            vec2 = np.array(entity2.embedding)
            
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            cosine_sim = np.dot(vec1, vec2) / (norm1 * norm2)
            return max(0.0, min(1.0, cosine_sim))
        except Exception as e:
            logger.warning(f"计算语义相似度失败: {str(e)}")
            return 0.0
    
    def _calculate_lexical_similarity(self, entity1, entity2) -> float:
        """计算词汇相似度"""
        import difflib
        
        name1 = self._normalize_entity_name(entity1.name)
        name2 = self._normalize_entity_name(entity2.name)
        
        # 编辑距离相似度
        edit_sim = difflib.SequenceMatcher(None, name1, name2).ratio()
        
        # 检查别名匹配
        alias_sim = 0.0
        all_names1 = [name1] + [self._normalize_entity_name(alias) for alias in entity1.aliases]
        all_names2 = [name2] + [self._normalize_entity_name(alias) for alias in entity2.aliases]
        
        for n1 in all_names1:
            for n2 in all_names2:
                if n1 == n2:
                    alias_sim = 1.0
                    break
            if alias_sim == 1.0:
                break
        
        return max(edit_sim, alias_sim)
    
    def _calculate_contextual_similarity(self, entity1, entity2) -> float:
        """计算上下文相似度"""
        # 类型匹配
        type_sim = 1.0 if entity1.type == entity2.type else 0.0
        
        # 描述相似度
        desc_sim = 0.0
        if entity1.description and entity2.description:
            desc_sim = difflib.SequenceMatcher(None, 
                                             entity1.description.lower(), 
                                             entity2.description.lower()).ratio()
        
        # 上下文重叠度
        context_sim = 0.0
        if entity1.source_text and entity2.source_text:
            context_sim = difflib.SequenceMatcher(None,
                                                entity1.source_text.lower(),
                                                entity2.source_text.lower()).ratio()
        
        return 0.5 * type_sim + 0.3 * desc_sim + 0.2 * context_sim
```

#### 自动合并决策引擎
```python
class EntityMergeDecisionEngine:
    def should_merge(self, entity1, entity2, similarity: float) -> Tuple[bool, str]:
        """简化的自动合并决策（无人工审核）"""
        if similarity >= 0.85:
            return True, "high_confidence_auto_merge"
        elif similarity >= 0.65:
            # 中等置信度检测基本冲突
            has_conflict = self._check_basic_conflicts(entity1, entity2)
            return not has_conflict, f"type_conflict: {has_conflict}"
        else:
            return False, "similarity_too_low"
    
    def _check_basic_conflicts(self, entity1, entity2) -> bool:
        """检测基本冲突（主要是类型冲突）"""
        return entity1.type != entity2.type
```

#### 实体合并器
```python
class EntityMerger:
    def merge_entities(self, primary_entity, secondary_entity):
        """合并两个实体，返回合并后的实体"""
        
        # 合并别名（包含次要实体的名称）
        merged_aliases = list(set(
            primary_entity.aliases + 
            secondary_entity.aliases + 
            [secondary_entity.name]
        ))
        
        # 移除主实体名称（避免自己成为自己的别名）
        if primary_entity.name in merged_aliases:
            merged_aliases.remove(primary_entity.name)
        
        # 合并属性
        merged_properties = {}
        merged_properties.update(secondary_entity.properties)
        merged_properties.update(primary_entity.properties)  # 主实体优先
        
        # 取高置信度
        merged_confidence = max(primary_entity.confidence, secondary_entity.confidence)
        
        # 重新计算质量分数
        merged_quality = self._calculate_merged_quality(primary_entity, secondary_entity)
        
        # 创建合并后的实体
        merged_entity = Entity(
            id=primary_entity.id,  # 保留主实体ID
            name=primary_entity.name,  # 保留主实体名称
            type=primary_entity.type,
            description=self._merge_descriptions(primary_entity.description, secondary_entity.description),
            properties=merged_properties,
            confidence=merged_confidence,
            source_text=primary_entity.source_text,
            start_pos=primary_entity.start_pos,
            end_pos=primary_entity.end_pos,
            aliases=merged_aliases,
            embedding=primary_entity.embedding,
            quality_score=merged_quality
        )
        
        return merged_entity
    
    def _calculate_merged_quality(self, entity1, entity2) -> float:
        """计算合并后实体的质量分数"""
        confidence_factor = (entity1.confidence + entity2.confidence) / 2
        desc_factor = 1.1 if entity1.description or entity2.description else 1.0
        alias_factor = min(1.2, 1.0 + len(entity1.aliases + entity2.aliases) * 0.05)
        
        return min(1.0, confidence_factor * desc_factor * alias_factor)
```

### 5. 流式交互系统

#### WebSocket处理器
```python
class ProgressiveResponseHandler:
    async def send_initial_answer(self, answer: str):
        await self.websocket.send_json({
            "type": "initial_answer",
            "content": answer,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_answer_update(self, enhanced_answer: str, iteration: int):
        await self.websocket.send_json({
            "type": "answer_update", 
            "content": enhanced_answer,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_status(self, status: str):
        await self.websocket.send_json({
            "type": "status",
            "message": status,
            "timestamp": datetime.now().isoformat()
        })
```

## 🔌 API设计

### RESTful接口
```python
@router.post("/search")
async def enhanced_search(query: str, strategies: Optional[List[str]] = None, k: int = 10):
    search_engine = get_search_engine()
    results = await search_engine.unified_search(query, k, strategies)
    fused_results = search_engine.fuse_results(results, query)
    
    return {
        "query": query,
        "results": fused_results,
        "strategy_breakdown": results
    }

@router.websocket("/chat")
async def enhanced_chat_websocket(websocket: WebSocket):
    await websocket.accept()
    agent = get_graph_rag_agent(websocket)
    
    while True:
        data = await websocket.receive_json()
        query = data.get("query")
        if query:
            final_answer = await agent.process_query(query)
```

## 📊 性能优化策略

### 1. 缓存机制
- 查询结果缓存
- 向量计算缓存
- 实体相似度缓存

### 2. 并发控制
- 异步搜索执行
- 连接池管理
- 资源限制

### 3. 索引优化
- 向量索引优化
- 全文搜索索引
- 图谱查询优化

## 🧪 测试策略

### 1. 单元测试
- 各搜索策略测试
- **实体统一算法测试**
  - 多维度相似度计算测试
  - 合并决策引擎测试
  - 实体合并器测试
  - embedding生成和缓存测试
  - 边界情况处理测试
- 工作流节点测试

### 2. 集成测试
- 端到端搜索流程
- **实体统一集成测试**
  - 文档解析流程中的实体统一测试
  - 跨文档实体合并测试
  - 大量实体统一性能测试
  - 实体统一准确率测试
- WebSocket通信测试
- 性能基准测试

### 3. 质量评估
- 答案准确性评估
- 搜索召回率测试
- **实体统一质量评估**
  - 实体合并准确率（目标>85%）
  - 误合并率（目标<5%）
  - 实体重复率降低程度
  - 别名丰富度提升评估
  - 知识图谱节点数量优化效果
- 用户满意度调研

---

本技术实现指南提供了完整的架构设计和关键代码示例，确保升级项目的技术可行性和实施效率。 