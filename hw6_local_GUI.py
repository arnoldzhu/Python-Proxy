import sys
import os
import traceback
import humanfriendly
import logging

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtNetwork import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebSockets import *

class Window(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        self.startBtn = QPushButton(parent=self, text='Start')
        self.startBtn.resize(325,30)
        self.startBtn.move(35, 290)
        self.startBtn.clicked.connect(self.startClicked)

        # 此处为界面布局
        self.address_prompt = QLabel(parent=self, text='Remote Proxy Address')
        self.address_prompt.move(25, 29)

        self.remoteHostLine = QLineEdit(parent=self, text='127.0.0.1')
        self.remoteHostLine.resize(175, 25)
        self.remoteHostLine.move(190, 25)

        self.port_prompt = QLabel(parent=self, text='Remote Proxy Port')
        self.port_prompt.move(25, 64)

        self.remotePortLine = QLineEdit(parent=self, text='8888')
        self.remotePortLine.resize(175,25)
        self.remotePortLine.move(190, 60)

        self.username_prompt = QLabel(parent=self, text='Username')
        self.username_prompt.move(25,114)

        self.usernameLine = QLineEdit(parent=self, text='')
        self.usernameLine.resize(175,25)
        self.usernameLine.move(190, 110)

        self.password_prompt = QLabel(parent=self, text='Password')
        self.password_prompt.move(25,149)

        self.passwordLine = QLineEdit(parent=self, text='')
        self.passwordLine.setEchoMode(QLineEdit.Password)
        self.passwordLine.resize(175,25)
        self.passwordLine.move(190, 145)

        # 显示登录状态
        self.connection_prompt = QLabel(parent=self, text='Connection Status:')
        self.connection_prompt.move(35, 191)

        self.connectionLine = QLabel(parent=self, text='Disconnected')
        self.connectionLine.move(209, 191)

        self.sendBandwidthLine = QLabel(parent=self, text='Send Bandwidth: 0 bytes')
        self.sendBandwidthLine.resize(300, 15)
        self.sendBandwidthLine.move(35, 224)

        self.recvBandwidthLine = QLabel(parent=self, text='Recv Bandwidth: 0 bytes')
        self.recvBandwidthLine.resize(300, 15)
        self.recvBandwidthLine.move(35, 257)
        
        # 创建一个进程类，其中关联三个操作：
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        # 1. 进程结束
        self.process.finished.connect(self.processFinished)
        # 2. 进程开始
        self.process.started.connect(self.processStarted)
        # 3. 报文来到，开始要读取
        self.process.readyReadStandardOutput.connect(self.processReadyRead)
        
    def processReadyRead(self):
        # 读取所有传输过来的内容
        data = self.process.readAll()
        
    def processStarted(self):
        process = self.sender() # 此处等同于 self.process 只不过使用sender适应性更好
        processId = process.processId()
        logging.debug(f'pid={processId}')
        self.startBtn.setText('Stop')

        self.websocket = QWebSocket()
        self.websocket.connected.connect(self.websocketConnected)
        self.websocket.disconnected.connect(self.websocketDisconnected)
        self.websocket.textMessageReceived.connect(self.websocketMsgRcvd)
        # 默认端口：6666
        self.websocket.open(QUrl(f'ws://127.0.0.1:6666/'))

    def processFinished(self):
        self.process.kill()

    def startClicked(self):
        btn = self.sender()
        text = btn.text().lower()
        
        # 得到和开启的进程相关的信息
        if text.startswith('start'):
            # 默认 1080 端口（以后可拓展该功能）
            listenPort = '1080'

            username = self.usernameLine.text()
            password = self.passwordLine.text()

            # 默认 6666 端口（以后可拓展该功能）
            # consolePort = 6666
            remoteHost = self.remoteHostLine.text()
            remotePort = int(self.remotePortLine.text())
            pythonExec = os.path.basename(sys.executable)
            # 从localgui启动localproxy直接使用-w 提供用户密码，不再使用命令行交互输入，因为有些许问题
            cmdLine = f'{pythonExec} hw6_local_server.py -u {username} -w {password} -rh {remoteHost} -rp {remotePort}'
            
            print(f'cmd={cmdLine}')
            self.process.start(cmdLine)

            # TODO: 验证

            self.connectionLine.setText('Connected')

        else:
            self.process.kill()
            self.connectionLine.setText('Disconnected')
            self.sendBandwidthLine.setText('Send Bandwidth: 0 b/s')
            self.recvBandwidthLine.setText('Send Bandwidth: 0 b/s')
            self.startBtn.setText('Start')

    def websocketConnected(self):
        self.websocket.sendTextMessage('secret')

    def websocketDisconnected(self):
        self.process.kill()

    def websocketMsgRcvd(self, msg):
        print(f'msg={msg}')
        sendBandwidth, recvBandwidth, *_ = msg.split()
        nowTime = QDateTime.currentDateTime().toString('hh:mm:ss')
        self.sendBandwidthLine.setText(f'Send Bandwidth: {nowTime} {humanfriendly.format_size(int(sendBandwidth))}')
        self.recvBandwidthLine.setText(f'Recv Bandwidth: {nowTime} {humanfriendly.format_size(int(recvBandwidth))}')

def main():
    app = QApplication(sys.argv)

    w = Window()
    w.resize(400,330)
    w.move(300,300)
    w.setWindowTitle('Local GUI')
    w.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()