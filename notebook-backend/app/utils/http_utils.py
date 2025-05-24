import urllib.parse
from typing import Optional


def format_content_disposition(disposition_type: str, filename: str) -> str:
    """
    根据RFC 6266标准格式化Content-Disposition头，正确处理包含非ASCII字符的文件名
    
    Args:
        disposition_type: 'inline'或'attachment'
        filename: 文件名，可以包含非ASCII字符
        
    Returns:
        正确格式化的Content-Disposition头值
    
    参考: https://datatracker.ietf.org/doc/html/rfc6266
    """
    ascii_filename = True
    
    # 检查文件名是否只包含ASCII字符
    try:
        filename.encode('ascii')
    except UnicodeEncodeError:
        ascii_filename = False
    
    if ascii_filename:
        # 如果文件名只包含ASCII字符，使用简单格式
        return f'{disposition_type}; filename="{filename}"'
    else:
        # 对于包含非ASCII字符的文件名，使用扩展格式
        encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
        return f'{disposition_type}; filename*=UTF-8\'\'{encoded_filename}' 