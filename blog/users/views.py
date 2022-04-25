import re
from users.models import User
from django.shortcuts import render
from django.db import DatabaseError
# Create your views here.
from django.views import View
from django.shortcuts import redirect
from django.http.response import HttpResponseBadRequest
from django.urls import reverse
from django.contrib.auth import authenticate
from django.contrib.auth import login

# 注册视图
class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')
    def post(self,request):
        """
        1. 接收数据
        2. 验证数据
            2.1 验证参数是否齐全
            2.2 手机号格式是否正确
            2.3 密码是否符合格式
            2.4 密码和确认密码是否一致
            2.5 短信验证码是否和redis中的一致
        3. 保存注册信息
        4. 返回响应跳转到指定页面
        :param request:
        :return:
        """
        # 1. 接收数据
        mobile=request.POST.get('mobile')
        password=request.POST.get('password')
        password2=request.POST.get('password2')
        smscode=request.POST.get('sms_code')
        # 2. 验证数据
        #     2.1 验证参数是否齐全
        if not all([mobile,password,password2,smscode]):
            return HttpResponseBadRequest('缺少必要的参数')
        #     2.2 手机号格式是否正确
        if not re.match(r'^1[3-9]\d{9}$',mobile):
            return HttpResponseBadRequest('手机号不符合规则')
        #     2.3 密码是否符合格式
        if not re.match(r'[0-9A-Za-z]{8,20}$',password):
            return HttpResponseBadRequest('请输入8-20位密码，密码是数字，字母')
        #     2.4 密码和确认密码是否一致
        if password != password2:
            return HttpResponseBadRequest('两次密码不一致')
        #     2.5 短信验证码是否和redis中的一致
        redis_conn=get_redis_connection('default')
        redis_sms_code=redis_conn.get('sms:%s' % mobile)
        if redis_sms_code is None:
            return HttpResponseBadRequest('短信验证码也过期')
        if smscode != redis_sms_code.decode():
            return HttpResponseBadRequest('短信验证码不存在')
        # 3. 保存注册信息
        #create user可以使用系统的方法来对密码进行加密
        try:
            user=User.objects.create_user(username=mobile,mobile=mobile,password=password)
        except DatabaseError as e:
            logger.error(e)
            return HttpResponseBadRequest('注册失败')
        # 4. 返回响应跳转到指定页面
        from django.contrib.auth import login
        login(request,user)
        #redirect是重定向
        #reverse是通过namespace:name来获取视图对应的路由
        response= redirect(reverse('home:index'))
        response.set_cookie('is_login',True)
        response.set_cookie('username', user.username,max_age=7*24*3600)

        return response
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

from django.http.response import JsonResponse
from utils.response_code import RETCODE
import logging
logger=logging.getLogger('django')
from random import randint
from libs.SMS.sms import send_message
class SmsCodeView(View):
    def get(self,request):
        '''
        1.接收参数
        2.参数的验证
          2.1 验证参数是否齐全
          2.2 图片验证码的验证
          连接redis，获取redis中的图片验证码
          判断图片验证码是否存在
          如果图片验证码威过去，获取到以后删除验证码
          比对图片验证码
        3.生产短信验证码
        4.保存短信验证码到redis中
        5.发送短信
        6.返回响应
        :param request:
        :return:
        '''

        # 1.接收参数（查询字符串）
        mobile= request.GET.get('mobile')
        image_code= request.GET.get('image_code')
        uuid= request.GET.get('uuid')
        # 2.参数的验证
        #   2.1 验证参数是否齐全
        if not all([mobile,image_code,uuid]):
            return JsonResponse({'code':RETCODE.NECESSARYPARAMERR,'errmsg':'缺少必要的参数'})
        #   2.2 图片验证码的验证
        #   连接redis，获取redis中的图片验证码
        redis_conn=get_redis_connection('default')
        redis_image_code=redis_conn.get('img:%s' % uuid)
        #   判断图片验证码是否存在
        if redis_image_code is None:
            return JsonResponse({'code':RETCODE.IMAGECODEERR,'errmsg':'图片验证码已过期'})
        #   如果图片验证码威过去，获取到以后删除验证码
        try:
            redis_conn.delete('img:%s' % uuid)
        except Exception as e:
            logger.error(e)
        #   比对图片验证码,注意大小写的问题，redis的数据是byte类型
        if redis_image_code.decode().lower()!= image_code.lower():
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图片验证码错误'})
        # 3.生产短信验证码
        sms_code= '%06d'%randint(0,999999)
        #为了后期比对方便
        logger.info(sms_code)
        # 4.保存短信验证码到redis中
        redis_conn.setex('sms:%s' % mobile, 300, sms_code)
        # 5.发送短信
        send_message(mobile,[sms_code,5],1)
        # 6.返回响应
        return JsonResponse({'code':RETCODE.OK,'errmsg':'短信发送成功'})
class LoginView(View):
    def get(self,request):
        return render(request,'login.html')
    def post(self,request):
        '''
        1.接收参数
        2.参数的验证
          2.1 验证参数是否齐全
          2.2 参数是否正确
          连接mysql库，读取mysql数据信息
          判断用户名是否存在
          判断密码是否正确
        3.用户状态的登录
        4.状态的保持
        5.根据用户选择的是否记住登录状态来判断
        6.为了首页显示，我们设置了一些cookie信息
        7.返回响应
        :param request:
        :return:
        '''
        # 1.接收参数
        mobile= request.POST.get('mobile')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        # 2.参数的验证
        #   2.1 验证手机号
        if not re.match(r'^1[3-9]\d{9}$',mobile):
            return HttpResponseBadRequest('手机号不符合规则')
        #   2.2 验证密码
        if not re.match(r'[0-9A-Za-z]{8,20}$',password):
            return HttpResponseBadRequest('请输入8-20位密码，密码是数字，字母')
        #   连接mysql库，读取mysql数据信息
        #   判断用户名是否存在
        #   判断密码是否正确
        # 3.用户状态的登录,采用系统自带的方法进行认证，如果用户名密码正确，返回user，否则返回None
        # 默认的认证字段是用户名，现在我们是手机号，需要对模型进行修改
        user=authenticate(mobile=mobile,password=password)
        if user is None:
            return HttpResponseBadRequest('用户名或者密码错误')
        # 4.状态的保持
        login(request,user)
        # 5.根据用户选择的是否记住登录状态来判断
        response= redirect(reverse('home:index'))
        if remember != 'on':
            request.session.set_expiry(0)
            response.set_cookie('is_login',True)
            response.set_cookie('username',user.username,max_age=14*24*3600)
        else:
            request.session.set_expiry(None)
            response.set_cookie('is_login',True,max_age=14*24*3600)
            response.set_cookie('username',user.username,max_age=14*24*3600)
        # 6.为了首页显示，我们设置了一些cookie信息
        # 7.返回响应
        return response