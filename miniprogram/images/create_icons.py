from PIL import Image, ImageDraw

def create_icon(filename, color, icon_type):
    """创建简单的图标"""
    size = 81  # 微信小程序推荐的 tabBar 图标尺寸
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    if icon_type == 'home':
        # 绘制房子图标
        # 屋顶
        draw.polygon([(20, 40), (40, 20), (60, 40)], fill=color)
        # 房子主体
        draw.rectangle([25, 40, 55, 65], fill=color)
        # 门
        draw.rectangle([35, 50, 45, 65], fill=(255, 255, 255, 255))
    
    elif icon_type == 'invoice':
        # 绘制发票图标（文档形状）
        draw.rectangle([25, 15, 55, 65], fill=color)
        # 文档折角
        draw.polygon([(55, 15), (55, 25), (45, 15)], fill=(200, 200, 200, 255))
        # 文字线条
        draw.rectangle([30, 30, 50, 33], fill=(255, 255, 255, 255))
        draw.rectangle([30, 38, 50, 41], fill=(255, 255, 255, 255))
        draw.rectangle([30, 46, 50, 49], fill=(255, 255, 255, 255))
    
    elif icon_type == 'settings':
        # 绘制设置图标（齿轮）
        center = 40
        # 外圆
        draw.ellipse([25, 25, 55, 55], fill=color)
        # 内圆（白色）
        draw.ellipse([32, 32, 48, 48], fill=(255, 255, 255, 255))
        # 齿轮齿
        for i in range(8):
            angle = i * 45
            import math
            x = center + 18 * math.cos(math.radians(angle))
            y = center + 18 * math.sin(math.radians(angle))
            draw.rectangle([x-2, y-2, x+2, y+2], fill=color)
    
    img.save(filename)
    print(f"Created {filename}")

# 创建所有图标
# 未选中状态 - 灰色
create_icon('home.png', (150, 150, 150, 255), 'home')
create_icon('invoice.png', (150, 150, 150, 255), 'invoice')
create_icon('settings.png', (150, 150, 150, 255), 'settings')

# 选中状态 - 蓝色
create_icon('home-active.png', (25, 137, 250, 255), 'home')
create_icon('invoice-active.png', (25, 137, 250, 255), 'invoice')
create_icon('settings-active.png', (25, 137, 250, 255), 'settings')

print("All icons created successfully!")
