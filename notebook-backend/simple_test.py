"""
非常简单的测试脚本
只检查DocumentService的构造函数是否需要vector_store参数
"""

def test_document_service_constructor():
    """
    打印出DocumentService.__init__的参数
    """
    import inspect
    from app.services.document_service import DocumentService
    
    # 使用inspect获取构造函数的签名
    signature = inspect.signature(DocumentService.__init__)
    print(f"DocumentService.__init__ 参数: {signature}")
    
    # 检查是否有vector_store参数
    has_vector_store = 'vector_store' in signature.parameters
    print(f"DocumentService.__init__ 是否有vector_store参数: {has_vector_store}")
    
    if has_vector_store:
        print("确认需要传入vector_store参数，我们的修复是正确的!")
    else:
        print("没有找到vector_store参数，可能不需要修复或者看错了代码")

if __name__ == "__main__":
    test_document_service_constructor() 