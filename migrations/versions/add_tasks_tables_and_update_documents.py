"""添加任务表和更新文档表

Revision ID: 
Create Date: 

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_tasks_tables'
down_revision = None  # 替换为实际的上一个迁移版本
branch_labels = None
depends_on = None


def upgrade():
    # 1. 创建tasks表
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column('overall_progress', sa.Integer(), nullable=True, server_default="0"),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('estimated_completion_time', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 2. 创建task_details表
    op.create_table(
        'task_details',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(36), nullable=False),
        sa.Column('step_name', sa.String(50), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column('progress', sa.Integer(), nullable=True, server_default="0"),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 3. 添加索引
    op.create_index(op.f('ix_tasks_created_by'), 'tasks', ['created_by'], unique=False)
    op.create_index(op.f('ix_tasks_document_id'), 'tasks', ['document_id'], unique=False)
    op.create_index(op.f('ix_task_details_task_id'), 'task_details', ['task_id'], unique=False)
    
    # 4. 修改Documents表，添加新字段
    op.add_column('documents', sa.Column('task_id', sa.String(36), nullable=True))
    op.add_column('documents', sa.Column('processing_status', sa.String(20), nullable=True, server_default="PENDING"))
    
    # 5. 添加MinIO存储相关字段
    op.add_column('documents', sa.Column('bucket_name', sa.String(100), nullable=True))
    op.add_column('documents', sa.Column('object_key', sa.String(255), nullable=True))
    op.add_column('documents', sa.Column('content_type', sa.String(100), nullable=True))
    op.add_column('documents', sa.Column('file_size', sa.BigInteger(), nullable=True))
    op.add_column('documents', sa.Column('etag', sa.String(100), nullable=True))
    
    # 6. 添加向量索引相关字段
    op.add_column('documents', sa.Column('vector_store_id', sa.String(255), nullable=True))
    op.add_column('documents', sa.Column('vector_collection_name', sa.String(255), nullable=True))
    op.add_column('documents', sa.Column('vector_count', sa.Integer(), nullable=True))
    
    # 7. 添加外键约束
    op.create_foreign_key('fk_documents_task_id', 'documents', 'tasks', ['task_id'], ['id'])
    
    # 8. 添加文档表索引
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)
    op.create_index(op.f('ix_documents_user_processing'), 'documents', ['user_id', 'processing_status'], unique=False)


def downgrade():
    # 1. 删除外键约束
    op.drop_constraint('fk_documents_task_id', 'documents', type_='foreignkey')
    
    # 2. 删除Documents表索引
    op.drop_index(op.f('ix_documents_user_processing'), table_name='documents')
    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    
    # 3. 删除Documents表中新增字段
    op.drop_column('documents', 'vector_count')
    op.drop_column('documents', 'vector_collection_name')
    op.drop_column('documents', 'vector_store_id')
    op.drop_column('documents', 'etag')
    op.drop_column('documents', 'file_size')
    op.drop_column('documents', 'content_type')
    op.drop_column('documents', 'object_key')
    op.drop_column('documents', 'bucket_name')
    op.drop_column('documents', 'processing_status')
    op.drop_column('documents', 'task_id')
    
    # 4. 删除索引
    op.drop_index(op.f('ix_task_details_task_id'), table_name='task_details')
    op.drop_index(op.f('ix_tasks_document_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_created_by'), table_name='tasks')
    
    # 5. 删除表
    op.drop_table('task_details')
    op.drop_table('tasks') 