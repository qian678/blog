from ronglian_sms_sdk import SmsSDK

accId = '8aaf0708802d0d85018049fdee820726'
accToken = '7ca74cb4134c494b8c26519f1dd6bec6'
appId = '8aaf0708802d0d85018049fdef7c072c'

def send_message(mobile,data,timer,tid):
    sdk = SmsSDK(accId, accToken, appId)
    datas = (data, timer)
    resp = sdk.sendMessage(tid, mobile, datas)
    print(resp)

if __name__ == '__main__':
    send_message(18116258561,223344,5,1)