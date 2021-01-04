import telnetlib
import time


class TelnetConnect():
    def __init__(self, host_ip, username, password):
        self.tn = telnetlib.Telnet()
        self.host_ip = host_ip
        self.username = username
        self.password = password

    # 此函数实现telnet登录路由器
    def login_host(self):
        try:
            self.tn.open(self.host_ip, port=23)
        except NetworkError:
            print('%s网络连接失败' % self.host_ip)
        else:
            # 等待Password出现后输入用户名，最多等待10秒
            self.tn.read_until(b'Password: ', timeout=10)
            self.tn.write(self.password.encode('ascii') + b'\n')
            # 延时两秒再收取返回结果，给服务端足够响应时间
            time.sleep(2)
            # 获取登录结果
            # read_very_eager()获取到的是的是上次获取之后本次获取之前的所有输出
            command_result = self.tn.read_very_eager().decode('ascii')
            if 'Login incorrect' not in command_result:
                self.tn.write('enable'.encode('ascii') + b'\n')
                self.tn.read_until(b'Password: ', timeout=10)
                self.tn.write(self.password.encode('ascii') + b'\n')
                print('%s登录成功' % self.host_ip)
                return True
            else:
                print('%s登录失败，用户名或密码错误' % self.host_ip)
                return False

    # 此函数实现执行传过来的命令，并输出其执行结果
    def execute_some_command(self, command):
        responses = []
        for i in range(len(command)):
            # 执行命令
            self.tn.write(command[i].encode('ascii') + b'\n')
            time.sleep(10) if command == 'ip nat inside' else time.sleep(2)
            # 获取命令结果
            command_result = self.tn.read_very_eager().decode('ascii')
            responses.append(command_result)
            print('命令执行结果：\n%s' % command_result)
        return responses

    # 退出telnet
    def logout_host(self):
        self.tn.write(b"exit\n")
        return True


class NetworkError(RuntimeError):
    def __init__(self, arg):
        self.args = arg
