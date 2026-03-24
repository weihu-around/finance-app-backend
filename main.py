from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
#引入 Flask 内置的密码加密和校验工具！
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

# 大语言模型相关
from openai import OpenAI
from flask import Response, stream_with_context
import json

app = Flask(__name__)
SECRET_KEY = "zhihui_finance_888" # 这个密钥是用来加密 JWT 的，实际项目中一定要换成更复杂的字符串，并且妥善保管！


# 配置你的 AI 客户端 
# 注意：真实项目中，API_KEY 绝对不能硬编码在代码里，必须写在 .env 环境变量文件里！
AI_API_KEY = "你的 DeepSeek API Key" 
client = OpenAI(api_key=AI_API_KEY, base_url="https://api.deepseek.com")


# ================= Token 检验保安 (装饰器) =================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # 1. 保安开始搜身：检查请求头里有没有带 Authorization
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            # 行业规范：前端传来的格式必须是 "Bearer 你的token字符串"
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]  # 把前面的 Bearer 切掉，只拿真 Token
                
        # 如果没带 Token，直接打回！
        if not token:
            return jsonify({"code": 401, "msg": "缺少认证令牌(Token)，请先登录！"})
            
        try:
            # 2. 保安开始验真伪：用咱们的 SECRET_KEY 去解密这个 Token
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            
            # 3. 解密成功后，里面藏着 user_id。咱们去数据库把这个活人捞出来
            current_user = db.session.get(User, data['user_id'])
            if not current_user:
                return jsonify({"code": 401, "msg": "Token无效，未找到该用户！"})
                
        except jwt.ExpiredSignatureError:
            return jsonify({"code": 401, "msg": "登录已过期，请重新登录！"})
        except jwt.InvalidTokenError:
            return jsonify({"code": 401, "msg": "非法的Token！"})
            
        # 4. 一切安全！保安放行，并且把捞出来的 current_user (当前用户) 递给后面的业务去用
        return f(current_user, *args, **kwargs)
        
    return decorated

# 确保 JSON 响应里的中文能正常显示，而不是被转义成 Unicode 字符串
app.json.ensure_ascii = False
CORS(app)

# =================👉 1. 数据库核心配置 =================
# 告诉程序，我们的数据库文件叫 zhihui.db，存放在当前目录下
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'zhihui.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 召唤数据库神仙工具
db = SQLAlchemy(app)

# ================= 设计【用户表】模型 =================
class User(db.Model):
    __tablename__ = 'users'
    
    # --- 基础信息 ---
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False) # 金融App用手机号做账号
    password_hash = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(50), default="理财新手")
    avatar = db.Column(db.String(255), default="https://cdn.uviewui.com/uview/album/1.jpg")
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- 💰 金融专属信息 (面试亮点) ---
    # 注意：算钱绝对不能用 Float，会丢精度！必须用 Numeric(10, 2) 代表最多10位数，保留2位小数
    balance = db.Column(db.Numeric(10, 2), default=Decimal('0.00')) 
    total_assets = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    risk_level = db.Column(db.String(20), default="未评估") # 保守型/稳健型/激进型
    is_verified = db.Column(db.Boolean, default=False)      # 实名认证状态

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "create_time": self.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            # 把 Decimal 转成字符串传给前端，防止前端 JS 精度丢失
            "balance": str(self.balance),
            "total_assets": str(self.total_assets),
            "risk_level": self.risk_level,
            "is_verified": self.is_verified
        }

# ================= 设计【帖子表】模型 (核心灵魂) =================
# 你在这里写的是 Python 类，底层会自动变成数据库里的表！
class Post(db.Model):
    __tablename__ = 'posts'  # 数据库里的表名
    
    id = db.Column(db.Integer, primary_key=True)         # 帖子ID (主键，自动递增)
    name = db.Column(db.String(50), nullable=False)      # 发帖人昵称
    avatar = db.Column(db.String(255))                   # 头像链接
    time = db.Column(db.String(50))                      # 发布时间
    content = db.Column(db.Text, nullable=False)         # 帖子正文
    imgs = db.Column(db.String(500))                     # 图片链接(多张图用逗号拼起来存)
    likes = db.Column(db.Integer, default=0)             # 点赞数 (默认0)
    comments = db.Column(db.Integer, default=0)          # 评论数 (默认0)

    # 这是一个魔法方法：方便咱们一会把数据库里的对象，直接转换成前端需要的 JSON 字典！
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "avatar": self.avatar,
            "time": self.time,
            "content": self.content,
            # 前端需要数组，我们把存入的字符串用逗号切开还给前端
            "imgs": self.imgs.split(',') if self.imgs else [], 
            "likes": self.likes,
            "comments": self.comments,
            "isLiked": False  # 留给后续用户系统做判断
        }

# =================  设计【评论表】模型 =================
class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False) # 评论内容
    time = db.Column(db.DateTime, default=datetime.utcnow) # 评论时间
    
    # 👉 极其关键的外键 1：这条评论是谁发的？(关联 users 表的 id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 👉 极其关键的外键 2：这条评论是发在哪个帖子下的？(关联 posts 表的 id)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

    # 👉 建立反向查询关系：这样我们在查评论时，能直接带出用户的昵称和头像！
    user = db.relationship('User', backref=db.backref('comments', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "time": self.time.strftime('%Y-%m-%d %H:%M'),
            "user_id": self.user_id,
            "post_id": self.post_id,
            # 直接把发评论人的信息也带出去，前端就不需要再去查一遍了！极其方便！
            "author_name": self.user.nickname if self.user else "未知用户",
            "author_avatar": self.user.avatar if self.user else ""
        }

# ================= 设计【点赞记录表】(防止无限刷赞) =================
class Like(db.Model):
    __tablename__ = 'likes'
    
    id = db.Column(db.Integer, primary_key=True)
    # 谁点的赞？
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # 点的哪篇帖子？
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    # 点赞时间
    create_time = db.Column(db.DateTime, default=datetime.utcnow)

# =================👉 3. 接口 =================
# 接口：获取社区帖子列表
# =================👉 获取真实帖子列表 (公开接口，千人千面) =================
@app.route('/api/community/posts', methods=['GET'])
def get_posts():
    # 👉 1. 温柔查验：尝试看看有没有人登录 (解析 Token，但不强制拦截)
    current_user_id = None
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                # 尝试用大门的钥匙解密一下
                data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
                current_user_id = data['user_id']
            except:
                pass # 如果没登录、或者 Token 过期了，千万别报错，就当游客处理！
                
    # 👉 2. 从数据库捞出所有的帖子 (按 ID 倒序，最新的在上面)
    posts = Post.query.order_by(Post.id.desc()).all()
    
    result = []
    for post in posts:
        # 把帖子转成字典 (注意：这里根据你前面 Post 表的实际字段来，这里演示最全的)
        post_data = {
            "id": post.id,
            "name": post.name,
            "avatar": post.avatar,
            "time": post.time,
            "content": post.content,
            # 图片如果是存的字符串数组，可能需要 eval 或 json.loads，这里先简单给空数组防报错
            "imgs": [], 
            "likes": post.likes,
            "comments": post.comments # 绝对真实的评论数！
        }
        
        # 👉 3. 灵魂一击：动态判断当前用户是否点赞了这个帖子！
        is_liked = False
        if current_user_id:
            # 拿着当前用户的 ID，去 Like 表里找证据
            like_record = Like.query.filter_by(user_id=current_user_id, post_id=post.id).first()
            if like_record:
                is_liked = True # 找到证据了，他点过赞！
                
        # 把这个极其珍贵的布尔值塞进数据里，发给前端！
        post_data['isLiked'] = is_liked
        result.append(post_data)
        
    return jsonify({
        "code": 200,
        "msg": "获取社区列表成功",
        "data": result
    })

# 接口 ：获取单个帖子详情
@app.route('/api/community/posts/<int:post_id>', methods=['GET'])
def get_post_detail(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"code": 404, "msg": "帖子不存在"})
        
    # 1. 先把基础数据转成字典
    post_data = post.to_dict()
    
    # 👉 2. 查验 Token，判断当前登录用户的点赞状态 (和列表页逻辑一模一样)
    current_user_id = None
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
                current_user_id = data['user_id']
            except:
                pass 
                
    # 👉 3. 去 Like 表里查证据
    is_liked = False
    if current_user_id:
        like_record = Like.query.filter_by(user_id=current_user_id, post_id=post.id).first()
        if like_record:
            is_liked = True
            
    # 👉 4. 覆盖掉原本写死的 False！
    post_data['isLiked'] = is_liked
        
    return jsonify({
        "code": 200,
        "msg": "获取详情成功",
        "data": post_data
    })

# 接口: 点赞/取消点赞 (机密接口，必须登录才能操作！)
@app.route('/api/community/posts/<int:post_id>/like', methods=['POST'])
@token_required
def toggle_like(current_user, post_id):
    data = request.get_json()
    action = data.get('action') # 前端传来的指令：'like' 或 'unlike'
    
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"code": 404, "msg": "帖子不存在"})
        
    # 👉 核心防御：去 Like 表里查，当前这个人是不是已经点过这篇帖子了？
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if action == 'like':
        if existing_like:
            return jsonify({"code": 400, "msg": "你已经点过赞啦，请勿重复点击！"})
        
        # 1. 记录在案：把这个人点赞的证据写进 Like 表
        new_like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        # 2. 帖子的总赞数 +1
        post.likes += 1
        
    elif action == 'unlike':
        if not existing_like:
            return jsonify({"code": 400, "msg": "你还没点过赞呢！"})
            
        # 1. 销毁证据：从 Like 表里把这条记录删掉
        db.session.delete(existing_like)
        # 2. 帖子的总赞数 -1
        post.likes -= 1
        
    # 提交数据库修改
    db.session.commit()
    
    # 返回给前端最新的、绝对真实的赞数！
    return jsonify({
        "code": 200, 
        "msg": "操作成功", 
        "data": {"likes": post.likes} 
    })

# 接口： 发布新帖子 (机密接口，防游客乱发) 
@app.route('/api/community/posts', methods=['POST'])
@token_required
def create_post(current_user):
    data = request.get_json()
    content = data.get('content')
    # 接收前端传来的图片链接，如果没有就默认为空字符串
    imgs = data.get('imgs', '') 
    
    if not content:
        return jsonify({"code": 400, "msg": "发帖内容不能为空！"})
        
    # 获取当前真实时间作为发帖时间 (转成字符串存入)
    from datetime import datetime
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # 极其优雅：自动读取当前操作用户的昵称和头像！
    new_post = Post(
        name=current_user.nickname,
        avatar=current_user.avatar,
        time=now_str,
        content=content,
        imgs=imgs,
        likes=0,
        comments=0
    )
    
    db.session.add(new_post)
    db.session.commit()
    
    return jsonify({"code": 200, "msg": "发布成功！"})

# 接口: 用户注册接口 
@app.route('/api/user/register', methods=['POST'])
def register():
    data = request.get_json()
    phone = data.get('phone')
    password = data.get('password')
    nickname = data.get('nickname')
    
    if not phone or not password or not nickname:
        return jsonify({"code": 400, "msg": "手机号、密码和用户名都不能为空！"})
        
    # 检查数据库里是不是已经有这个账号了
    existing_user = User.query.filter_by(phone=phone).first()
    if existing_user:
        return jsonify({"code": 400, "msg": "该账号已被注册！"})
        
    # 创建新用户
    new_user = User(phone=phone, nickname=nickname)
    new_user.set_password(password) # 加密密码！
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"code": 200, "msg": "注册成功，欢迎加入智汇理财！"})

# 接口：用户登录接口 
@app.route('/api/user/login', methods=['POST'])
def login():
    data = request.get_json()
    phone = data.get('phone')
    password = data.get('password')
    
    if not phone or not password:
        return jsonify({"code": 400, "msg": "账号或密码不能为空！"})
        
    # 从数据库里捞人
    user = User.query.filter_by(phone=phone).first()
    
    # 人不存在，或者密码不对
    if not user or not user.check_password(password):
        return jsonify({"code": 401, "msg": "账号或密码错误！"})
    
    # ================= 生成真实的 JWT Token =================
    # 把用户的 id 藏进 Token 里，设置 7 天后过期
    payload = {
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(days=7) 
    }
    # 生成 Token 字符串
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

    # 把用户基础信息拿出来，并且把 token 塞进去一起给前端
    user_data = user.to_dict()
    user_data['token'] = token
        
    # 登录成功，把用户信息发给前端存起来
    return jsonify({
        "code": 200, 
        "msg": "登录成功！", 
        "data": user_data
    })

# 接口： 获取某个帖子的所有评论 (公开接口)  
@app.route('/api/community/posts/<int:post_id>/comments', methods=['GET'])
def get_post_comments(post_id):
    # 检查帖子在不在
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"code": 404, "msg": "帖子不存在"})
        
    # 从评论表里，捞出所有属于这个帖子的评论，按时间倒序排（最新的在最上面）
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.time.desc()).all()
    comments_data = [comment.to_dict() for comment in comments]
    
    return jsonify({
        "code": 200,
        "msg": "获取评论成功",
        "data": comments_data
    })

# 接口： 发表真实评论 (机密接口，需要保安检查 Token) 
# 注意看：@token_required 就挂在路由下面！
@app.route('/api/community/posts/<int:post_id>/comments', methods=['POST'])
@token_required 
def create_comment(current_user, post_id): # 保安查验通过后，会把 current_user 塞进来！
    
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"code": 404, "msg": "帖子不存在"})
        
    data = request.get_json()
    content = data.get('content')
    
    if not content:
        return jsonify({"code": 400, "msg": "评论内容不能为空"})
        
    # 1. 创建新评论，自动绑定当前正在操作的 user_id！
    new_comment = Comment(
        content=content,
        user_id=current_user.id, # 极其优雅！不需要前端传 user_id，直接从 Token 里解密出来用，绝对安全防篡改！
        post_id=post_id
    )
    
    # 2. 顺手把这个帖子的总评论数 +1
    post.comments += 1
    
    # 3. 提交到数据库
    db.session.add(new_comment)
    db.session.commit()
    
    return jsonify({
        "code": 200,
        "msg": "评论发表成功！",
        "data": new_comment.to_dict() # 把刚发成功的评论传回给前端，方便直接显示
    })

# =================👉 AI 财务助手接口 (支持流式/非流式双引擎) =================
@app.route('/api/ai/chat', methods=['POST', 'OPTIONS'])
# @token_required # 如果你想让游客也能用，可以把这行保安注释掉；如果为了防白嫖，必须加上！
def ai_chat():
    # 👉 🚀 新增 CORS OPTIONS 预检请求拦截逻辑！
    if request.method == 'OPTIONS':
        response = app.make_response('')
        # 允许跨域
        response.headers['Access-Control-Allow-Origin'] = '*'
        # 允许请求头 (带上咱们鉴权用的 Authorization)
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        # 允许请求方法
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        # 预检结果缓存 10 分钟
        response.headers['Access-Control-Max-Age'] = '600'
        return response
    
    data = request.get_json()
    user_message = data.get('message')
    is_stream = data.get('is_stream', False) # 前端传来的开关，默认非流式
    
    if not user_message:
        return jsonify({"code": 400, "msg": "你想问我什么呢？"})

    # 👉 赋予 AI 灵魂 (System Prompt)
    messages = [
        {"role": "system", "content": "你是一位拥有 10 年经验的资深金融理财顾问。请用专业、简练、通俗的语言回答用户的理财和股票问题。每次回答控制在 200 字以内。"},
        {"role": "user", "content": user_message}
    ]

    # 🚀 模式 A：非流式 (传统一发一收，憋大招)
    if not is_stream:
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=False
            )
            answer = response.choices[0].message.content
            return jsonify({"code": 200, "data": {"content": answer}})
        except Exception as e:
            return jsonify({"code": 500, "msg": f"AI 思考时睡着了: {str(e)}"})

    # 🚀 模式 B：流式 (SSE 服务器推送，打字机效果)
    # 亮点：这里使用了 Server-Sent Events (SSE) 协议
    else:
        # def generate():
        #     try:
        #         response = client.chat.completions.create(
        #             model="deepseek-chat",
        #             messages=messages,
        #             stream=True
        #         )
        #         for chunk in response:
        #             # 提取每个字的碎片
        #             if chunk.choices and chunk.choices[0].delta.content:
        #                 text_frag = chunk.choices[0].delta.content
        #                 # 必须严格按照 SSE 格式返回：data: {json}\n\n
        #                 yield f"data: {json.dumps({'content': text_frag})}\n\n"
                
        #         # 结束标记
        #         yield "data: [DONE]\n\n"
        #     except Exception as e:
        #         yield f"data: {json.dumps({'error': str(e)})}\n\n"

        # # 使用 Flask 的 Response 和 stream_with_context 来保持连接不断开
        # return Response(stream_with_context(generate()), content_type='text/event-stream')
        def generate():
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    stream=True
                )
                for chunk in response:
                    # 提取每个字的碎片
                    if chunk.choices and chunk.choices[0].delta.content:
                        text_frag = chunk.choices[0].delta.content
                        # 必须严格按照 SSE 格式返回：data: {json}\n\n
                        yield f"data: {json.dumps({'content': text_frag})}\n\n"
                
                # 结束标记
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        # 👉 1. 先把流式对象存到变量里
        stream_response = Response(stream_with_context(generate()), content_type='text/event-stream')
        
        # 👉 2. 强行打上跨域“免死金牌”和防缓存印记！
        stream_response.headers['Access-Control-Allow-Origin'] = '*'
        stream_response.headers['Cache-Control'] = 'no-cache'
        stream_response.headers['Connection'] = 'keep-alive'
        
        # 👉 3. 发射！
        return stream_response
    
# =================👉 4. 启动并自动建表 =================
if __name__ == '__main__':
    # 启动服务器前，强行检查并创建所有表！
    with app.app_context():
        db.create_all()
        print("✅ 报告老兵：zhihui.db 数据库及表已成功创建！")
        
    app.run(host='0.0.0.0', port=5000, debug=True)