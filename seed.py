# 从你刚才写的 main.py 里，把应用实例、数据库工具和帖子模型引进来
from main import app, db, Post

# 准备咱们的真实测试数据 
# (注意：因为数据库里 imgs 字段是 String，所以我把多张图片用逗号拼成了一个字符串)
posts_data = [
    { 
        "name": "股海弄潮儿", 
        "avatar": "https://cdn.uviewui.com/uview/album/1.jpg", 
        "time": "5分钟前", 
        "content": "今天大盘走势极其诡异，我看好半导体板块尤其是【中芯国际(688981)】的后市机会！另外【北方华创(002371)】也值得关注。", 
        "imgs": "https://cdn.uviewui.com/uview/album/2.jpg", 
        "comments": 14, 
        "likes": 38
    },
    { 
        "name": "小散逆袭记", 
        "avatar": "https://cdn.uviewui.com/uview/album/3.jpg", 
        "time": "32分钟前", 
        "content": "刚跟朋友聊了下，稳打稳扎才是王道，今日【贵州茅台(600519)】股价逆势上涨就是最好的证明。", 
        # 多张图片，用逗号连起来存进数据库
        "imgs": "https://cdn.uviewui.com/uview/album/4.jpg,https://cdn.uviewui.com/uview/album/5.jpg", 
        "comments": 8, 
        "likes": 25
    }
]

# 在应用的上下文中执行数据库操作
with app.app_context():
    # 1. 先清空表里可能有的旧数据（方便咱们以后反复测试）
    db.session.query(Post).delete()
    
    # 2. 循环把上面的数据塞进数据库
    for item in posts_data:
        # 实例化一个 Post 模型对象 (相当于在表里新建一行)
        new_post = Post(
            name=item['name'],
            avatar=item['avatar'],
            time=item['time'],
            content=item['content'],
            imgs=item['imgs'],
            likes=item['likes'],
            comments=item['comments']
        )
        # 把这行数据放进暂存区
        db.session.add(new_post)
    
    # 3. 提交保存 (这一步才是真正执行 SQL 语句，把数据焊死在硬盘上！)
    db.session.commit()
    print("✅ 报告老兵：两条初始帖子数据，已经成功灌入 zhihui.db 数据库！")