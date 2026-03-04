from PIL import Image, ImageDraw

def create_default_avatar():
    """创建默认头像"""
    size = 200  # 头像尺寸
    img = Image.new('RGBA', (size, size), (240, 240, 240, 255))
    draw = ImageDraw.Draw(img)

    # 绘制圆形背景
    draw.ellipse([0, 0, size, size], fill=(220, 220, 220, 255))

    # 绘制人物头部（圆形）
    head_size = 60
    head_x = (size - head_size) // 2
    head_y = size // 3
    draw.ellipse([head_x, head_y, head_x + head_size, head_y + head_size],
                 fill=(180, 180, 180, 255))

    # 绘制人物身体（半圆形）
    body_width = 100
    body_height = 80
    body_x = (size - body_width) // 2
    body_y = head_y + head_size - 10
    draw.ellipse([body_x, body_y, body_x + body_width, body_y + body_height * 2],
                 fill=(180, 180, 180, 255))

    img.save('default-avatar.png')
    print("Created default-avatar.png")

if __name__ == '__main__':
    create_default_avatar()
    print("Default avatar created successfully!")
