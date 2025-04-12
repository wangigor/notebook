import os
from dotenv import load_dotenv
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy import create_engine
from app.database import Base

# 加载环境变量
load_dotenv()

def init_db():
    # 获取数据库URL
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("错误: 未找到数据库连接URL环境变量")
        return False
    
    try:
        # 创建引擎
        engine = create_engine(db_url)
        
        # 检查数据库是否存在，不存在则创建
        if not database_exists(engine.url):
            print(f"创建数据库: {engine.url.database}")
            create_database(engine.url)
            print("数据库创建成功")
        else:
            print(f"数据库 {engine.url.database} 已经存在")
        
        # 创建所有表
        print("创建所有表...")
        Base.metadata.create_all(engine)
        print("表创建成功")
        
        return True
    except Exception as e:
        print(f"初始化数据库时出错: {e}")
        return False

if __name__ == "__main__":
    print("开始初始化数据库...")
    if init_db():
        print("数据库初始化成功")
    else:
        print("数据库初始化失败") 