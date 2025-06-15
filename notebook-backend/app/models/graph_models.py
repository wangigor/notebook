from enum import Enum
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime

class NodeType(str, Enum):
    """节点类型枚举"""
    
    # 基础实体类型
    ENTITY = "Entity"
    CONCEPT = "Concept"
    
    # 人物相关
    PERSON = "Person"
    ORGANIZATION = "Organization"
    
    # 地理位置
    LOCATION = "Location"
    COUNTRY = "Country"
    CITY = "City"
    
    # 时间相关
    EVENT = "Event"
    DATE = "Date"
    TIME_PERIOD = "TimePeriod"
    
    # 文档相关
    DOCUMENT = "Document"
    DOCUMENT_CHUNK = "DocumentChunk"
    TOPIC = "Topic"
    KEYWORD = "Keyword"
    
    # 专业领域
    TECHNOLOGY = "Technology"
    PRODUCT = "Product"
    SERVICE = "Service"
    PROJECT = "Project"
    
    # 学术相关
    RESEARCH = "Research"
    THEORY = "Theory"
    METHOD = "Method"
    
    # 其他
    UNKNOWN = "Unknown"

class RelationshipType(str, Enum):
    """关系类型枚举"""
    
    # 基础关系
    RELATES_TO = "RELATES_TO"
    CONNECTED_TO = "CONNECTED_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    
    # 层次关系
    PART_OF = "PART_OF"
    CONTAINS = "CONTAINS"
    BELONGS_TO = "BELONGS_TO"
    MEMBER_OF = "MEMBER_OF"
    
    # 时间关系
    HAPPENED_BEFORE = "HAPPENED_BEFORE"
    HAPPENED_AFTER = "HAPPENED_AFTER"
    OCCURRED_DURING = "OCCURRED_DURING"
    
    # 空间关系
    LOCATED_IN = "LOCATED_IN"
    NEAR_TO = "NEAR_TO"
    
    # 人物关系
    WORKS_FOR = "WORKS_FOR"
    FOUNDED_BY = "FOUNDED_BY"
    MANAGED_BY = "MANAGED_BY"
    COLLABORATED_WITH = "COLLABORATED_WITH"
    
    # 文档关系
    MENTIONS = "MENTIONS"
    DESCRIBES = "DESCRIBES"
    REFERENCES = "REFERENCES"
    DERIVED_FROM = "DERIVED_FROM"
    SIMILAR_TO = "SIMILAR_TO"
    
    # 因果关系
    CAUSES = "CAUSES"
    RESULTS_IN = "RESULTS_IN"
    INFLUENCES = "INFLUENCES"
    
    # 语义关系
    SYNONYM_OF = "SYNONYM_OF"
    ANTONYM_OF = "ANTONYM_OF"
    BROADER_THAN = "BROADER_THAN"
    NARROWER_THAN = "NARROWER_THAN"
    
    # 技术关系
    IMPLEMENTS = "IMPLEMENTS"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    REPLACES = "REPLACES"

class GraphEntity(BaseModel):
    """图谱实体基础模型"""
    
    name: str = Field(..., description="实体名称")
    entity_type: NodeType = Field(default=NodeType.ENTITY, description="实体类型")
    description: Optional[str] = Field(None, description="实体描述")
    aliases: List[str] = Field(default_factory=list, description="实体别名")
    properties: Dict[str, Any] = Field(default_factory=dict, description="实体属性")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")
    source_document_id: Optional[int] = Field(None, description="来源文档ID")
    source_chunk_index: Optional[int] = Field(None, description="来源文档块索引")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="更新时间")
    
    class Config:
        use_enum_values = True

class GraphRelationship(BaseModel):
    """图谱关系模型"""
    
    source_entity: str = Field(..., description="源实体名称")
    target_entity: str = Field(..., description="目标实体名称")
    relationship_type: RelationshipType = Field(..., description="关系类型")
    description: Optional[str] = Field(None, description="关系描述")
    properties: Dict[str, Any] = Field(default_factory=dict, description="关系属性")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")
    source_document_id: Optional[int] = Field(None, description="来源文档ID")
    source_chunk_index: Optional[int] = Field(None, description="来源文档块索引")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="创建时间")
    
    class Config:
        use_enum_values = True

class DocumentNode(GraphEntity):
    """文档节点模型"""
    
    entity_type: NodeType = Field(default=NodeType.DOCUMENT, description="节点类型")
    document_id: int = Field(..., description="文档ID")
    title: Optional[str] = Field(None, description="文档标题")
    file_path: Optional[str] = Field(None, description="文件路径")
    file_type: Optional[str] = Field(None, description="文件类型")
    file_size: Optional[int] = Field(None, description="文件大小")
    page_count: Optional[int] = Field(None, description="页数")
    language: Optional[str] = Field(None, description="语言")

class DocumentChunkNode(GraphEntity):
    """文档分块节点模型"""
    
    entity_type: NodeType = Field(default=NodeType.DOCUMENT_CHUNK, description="节点类型")
    chunk_index: int = Field(..., description="分块索引")
    content: str = Field(..., description="分块内容")
    start_char: Optional[int] = Field(None, description="开始字符位置")
    end_char: Optional[int] = Field(None, description="结束字符位置")
    vector_id: Optional[str] = Field(None, description="向量ID")
    embedding: Optional[List[float]] = Field(None, description="嵌入向量")

class PersonNode(GraphEntity):
    """人物节点模型"""
    
    entity_type: NodeType = Field(default=NodeType.PERSON, description="节点类型")
    full_name: Optional[str] = Field(None, description="全名")
    title: Optional[str] = Field(None, description="职位/头衔")
    organization: Optional[str] = Field(None, description="所属组织")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="电话")

class OrganizationNode(GraphEntity):
    """组织节点模型"""
    
    entity_type: NodeType = Field(default=NodeType.ORGANIZATION, description="节点类型")
    official_name: Optional[str] = Field(None, description="官方名称")
    organization_type: Optional[str] = Field(None, description="组织类型")
    industry: Optional[str] = Field(None, description="行业")
    founded_year: Optional[int] = Field(None, description="成立年份")
    location: Optional[str] = Field(None, description="位置")
    website: Optional[str] = Field(None, description="网站")

class LocationNode(GraphEntity):
    """地理位置节点模型"""
    
    entity_type: NodeType = Field(default=NodeType.LOCATION, description="节点类型")
    full_name: Optional[str] = Field(None, description="完整名称")
    country: Optional[str] = Field(None, description="国家")
    region: Optional[str] = Field(None, description="地区/省份")
    coordinates: Optional[Dict[str, float]] = Field(None, description="坐标")

class ConceptNode(GraphEntity):
    """概念节点模型"""
    
    entity_type: NodeType = Field(default=NodeType.CONCEPT, description="节点类型")
    definition: Optional[str] = Field(None, description="定义")
    category: Optional[str] = Field(None, description="类别")
    domain: Optional[str] = Field(None, description="领域")

class GraphExtractionResult(BaseModel):
    """图谱抽取结果模型"""
    
    entities: List[GraphEntity] = Field(default_factory=list, description="抽取的实体列表")
    relationships: List[GraphRelationship] = Field(default_factory=list, description="抽取的关系列表")
    document_id: int = Field(..., description="源文档ID")
    chunk_index: Optional[int] = Field(None, description="分块索引")
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow, description="抽取时间")
    llm_model: Optional[str] = Field(None, description="使用的LLM模型")
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="整体抽取置信度")
    processing_time: Optional[float] = Field(None, description="处理时间（秒）")

class GraphStatistics(BaseModel):
    """图谱统计信息模型"""
    
    total_nodes: int = Field(default=0, description="总节点数")
    total_relationships: int = Field(default=0, description="总关系数")
    node_type_counts: Dict[str, int] = Field(default_factory=dict, description="各类型节点数量")
    relationship_type_counts: Dict[str, int] = Field(default_factory=dict, description="各类型关系数量")
    average_node_degree: float = Field(default=0.0, description="平均节点度数")
    connected_components: int = Field(default=0, description="连通分量数")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="最后更新时间")

class GraphQueryRequest(BaseModel):
    """图谱查询请求模型"""
    
    query_type: str = Field(..., description="查询类型")
    entity_name: Optional[str] = Field(None, description="实体名称")
    entity_types: Optional[List[NodeType]] = Field(None, description="实体类型列表")
    relationship_types: Optional[List[RelationshipType]] = Field(None, description="关系类型列表")
    depth: int = Field(default=1, ge=1, le=5, description="查询深度")
    limit: int = Field(default=100, ge=1, le=1000, description="结果数量限制")
    filters: Dict[str, Any] = Field(default_factory=dict, description="过滤条件")

class GraphQueryResponse(BaseModel):
    """图谱查询响应模型"""
    
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="节点列表")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="关系列表")
    query_time: float = Field(..., description="查询耗时")
    total_count: int = Field(..., description="总结果数")
    has_more: bool = Field(default=False, description="是否有更多结果")

# 预定义的实体类型映射
ENTITY_TYPE_MAPPING = {
    "人物": NodeType.PERSON,
    "人员": NodeType.PERSON,
    "个人": NodeType.PERSON,
    "组织": NodeType.ORGANIZATION,
    "机构": NodeType.ORGANIZATION,
    "公司": NodeType.ORGANIZATION,
    "企业": NodeType.ORGANIZATION,
    "地点": NodeType.LOCATION,
    "位置": NodeType.LOCATION,
    "地理": NodeType.LOCATION,
    "事件": NodeType.EVENT,
    "时间": NodeType.DATE,
    "日期": NodeType.DATE,
    "技术": NodeType.TECHNOLOGY,
    "产品": NodeType.PRODUCT,
    "服务": NodeType.SERVICE,
    "项目": NodeType.PROJECT,
    "概念": NodeType.CONCEPT,
    "理论": NodeType.THEORY,
    "方法": NodeType.METHOD,
}

# 预定义的关系类型映射
RELATIONSHIP_TYPE_MAPPING = {
    "属于": RelationshipType.BELONGS_TO,
    "包含": RelationshipType.CONTAINS,
    "位于": RelationshipType.LOCATED_IN,
    "工作于": RelationshipType.WORKS_FOR,
    "创立": RelationshipType.FOUNDED_BY,
    "管理": RelationshipType.MANAGED_BY,
    "合作": RelationshipType.COLLABORATED_WITH,
    "提及": RelationshipType.MENTIONS,
    "描述": RelationshipType.DESCRIBES,
    "引用": RelationshipType.REFERENCES,
    "导致": RelationshipType.CAUSES,
    "影响": RelationshipType.INFLUENCES,
    "使用": RelationshipType.USES,
    "依赖": RelationshipType.DEPENDS_ON,
    "实现": RelationshipType.IMPLEMENTS,
    "相关": RelationshipType.RELATES_TO,
    "连接": RelationshipType.CONNECTED_TO,
    "关联": RelationshipType.ASSOCIATED_WITH,
} 