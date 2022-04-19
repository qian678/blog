from django.shortcuts import render
# Create your views here.
from django.views import View


# 注册视图
class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')


from django.http.response import HttpResponseBadRequest
from libs.captcha.captcha import captcha
from django_redis import get_redis_connection
from django.http.response import HttpResponse

class ImageCodeView(View):
    def get(self, request):
        """
       1. 接收前端传递过来的uuid
       2. 判断uuid是否获取到
       3. 通过调用captcha生成图片验证码（图片二进制和图片内容）
       4. 图片内容保存到redis，uuid为key，内容为value，同时设置一个时效
       5. 图片二进制返回给前端
       :param request: 
       :return: 
       """
        # 1. 接收前端传递过来的uuid
        uuid = request.GET.get('uuid')
        # 2. 判断uuid是否获取到
        if uuid is None:
            return HttpResponseBadRequest('没有传递uuid')
        # 3. 通过调用captcha生成图片验证码（图片二进制和图片内容）
        text, image = captcha.generate_captcha()
        # 4. 图片内容保存到redis，uuid为key，内容为value，同时设置一个时效
        redis_conn = get_redis_connection('default')
        # key上设置为uuid
        # seconds 过期秒数 300秒 5分钟过期时间
        # value text
        redis_conn.setex('img:%s' % uuid, 300, text)
        # 5. 图片二进制返回给前端
        return HttpResponse(image, content_type='image/jpeg')
