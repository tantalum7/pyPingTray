# coding: utf-8
import logging
import os, sys, json, re, statistics, time
from PyQt5 import QtGui, QtWidgets, QtCore

# Project imports
import pypong


class pingTrayQt:

    def __init__(self):

        # Initialise qt app
        self.app = QtWidgets.QApplication(sys.argv)

        # Initialise icons
        self.ICON_DEFAULT   = QtGui.QIcon('icons/white_thumb_up.png')
        self.ICON_GOOD      = QtGui.QIcon('icons/green_thumb_up.png')
        self.ICON_WARNING   = QtGui.QIcon('icons/orange_thumb_up.png')
        self.ICON_BAD       = QtGui.QIcon('icons/red_thumb_down.png')

        # Initialise ping settings
        self.net_up_ping_dest = "8.8.8.8"
        self.server_up_ping_list = ["www.google.com"]
        self.last_ping_latency = -1
        self._ping_interval = 10
        self.ping_warning_threshold = 100

        # Initialise ping stats
        self.ping_history = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.ping_jitter = 0
        self.ping_mean = 0
        self.packet_loss = 0
        self.packet_loss_time = time.time()
        self.packet_loss_interval = 60
        self.internet_down_time = None

        # Initialise timestamps to stop repeat warnings
        self.no_internet_warning_interval = 10 * 60
        self.no_internet_warning_last = 0
        self.warning_messageBox = None

        # Initialise systray widget
        self.systray_widget = self.SystemTrayWidget(icon=self.ICON_DEFAULT)
        self.systray_widget.config_action.triggered.connect(self.show_config_menu)
        self.systray_widget.show()

        # Initialise timer for the ping test
        self.ping_qtimer = QtCore.QTimer()
        self.ping_qtimer.timeout.connect(self.ping_test)
        self.ping_qtimer.start(self.ping_interval*1000)
        self.ping_test()
        self.ping_history = [self.last_ping_latency for x in range(10)]

    @property
    def ping_interval(self):
        return self._ping_interval

    @ping_interval.setter
    def ping_interval(self, value):
        self._ping_interval = int(value)
        self.ping_qtimer.stop()
        self.ping_qtimer.start(self._ping_interval*1000)

    def run(self):
        return self.app.exec_()

    def set_icon(self, icon):
        self.systray_widget.setIcon(icon)

    def show_config_menu(self):

        # Spawn menu
        self.config_menu = self.ConfigMenuUI( ping_interval         = self.ping_interval,
                                              net_up_ping_dest      = self.net_up_ping_dest,
                                              server_up_ping_list   =", ".join(self.server_up_ping_list),
                                              warning_threshold     = self.ping_warning_threshold )

        # Connect buttons
        self.config_menu.apply_Button.clicked.connect(lambda: self.apply_config_settings(self.config_menu))

        # Shoe menu
        self.config_menu.show()

    def apply_config_settings(self, config_menu):

        # Update the internet up? test server address
        self.net_up_ping_dest = config_menu.internet_up_lineEdit.text()

        # Update the ping interval
        self.ping_interval = config_menu.ping_interval_SpinBox.value()

        # Update the ping warning threshold
        self.ping_warning_threshold = config_menu.ping_warning_threshold_SpinBox.value()

        # Clear the previous server ping list
        self.server_up_ping_list = []

        # Grab the new ping test list as plain text
        ping_list_plain_text = config_menu.server_ping_list_PlainEdit.toPlainText()

        # Split the plain text list into lines, and split each line up by typical separators (space, tab, comma,
        # semicolon etc). Put all the results into the sever ping list
        for line in ping_list_plain_text.splitlines():
            self.server_up_ping_list.extend(re.split(r'[\,\s+;\t]/g', line))

        # Remove any empty strings that might get put in
        self.server_up_ping_list = filter(None, self.server_up_ping_list)

        # Close the widget
        config_menu.close()

    def no_internet_warning(self):

        #if self.no_internet_warning_last + self.no_internet_warning_interval < time.time() and self.warning_messageBox is None:
        #    self.no_internet_warning_last = time.time()
        #    self.warning_messageBox = self.MsgBox()
        #    pass

    def ping_test(self):

        try: self.last_ping_latency = int(pypong.ping(self.net_up_ping_dest) * 1000)

        except (pypong.HostLookupFailed, pypong.ReplyTimeout, pypong.HostUnreachable): self.last_ping_latency = -1

        except (pypong.BadReply): print("not sure what to do?")

        except: raise

        self.calc_stats()

        if self.last_ping_latency == -1:
            self.set_icon(self.ICON_BAD)
        elif self.last_ping_latency > self.ping_warning_threshold:
            self.set_icon(self.ICON_WARNING)
        else:
            self.set_icon(self.ICON_GOOD)


        if self.ping_mean < 0:
            self.systray_widget.setToolTip("No internet connectivity!")
            self.no_internet_warning()
        else:
            self.systray_widget.setToolTip("Latency: {0}ms({1}ms avg) Jitter: {2}ms Packet Loss: {3}(in {4}s)"
                                           .format(self.last_ping_latency, self.ping_mean, self.ping_jitter,
                                                   self.packet_loss, self.packet_loss_interval))

    def calc_stats(self):

        # Shuffle along rolling history of values
        for index in reversed(range(1, len(self.ping_history))):
            self.ping_history[index] = self.ping_history[index-1]
        self.ping_history[0] = self.last_ping_latency

        # Calculate the mean and the standard deviation (jitter)
        mean = statistics.mean(self.ping_history)
        self.ping_mean = int(mean)
        self.ping_jitter = int( statistics.stdev(self.ping_history, mean) )

        # Reset packet loss counter if we've gone passed the packet loss time interval
        if self.packet_loss_time + self.packet_loss_interval > time.time():
            self.packet_loss = 0

        # If the last ping was -1, it means we never got a reply. Increment the packet loss counter.
        if self.last_ping_latency == -1:
            self.packet_loss += 1

    class MsgBox(QtWidgets.QWidget):
        def __init__(self):
            super(self.MsgBox, self).__init__()
            self.setGeometry(800, 500, 250, 100)
            self.setWindowTitle('New mail!')
            self.lbl = QtWidgets.QLabel('', self)
            self.lbl.move(15, 10)

        def closeEvent(self, event):
            # don't exit
            self.hide()
            event.ignore()

    class ConfigMenuUI(QtWidgets.QWidget):
        def __init__(self, ping_interval=10, net_up_ping_dest="8.8.8.8", server_up_ping_list="", warning_threshold=100):
            QtWidgets.QWidget.__init__(self)
            self.setObjectName("config_menu")
            self.resize(319, 269)
            sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
            sizePolicy.setHorizontalStretch(0)
            sizePolicy.setVerticalStretch(0)
            sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
            self.setSizePolicy(sizePolicy)
            self.setMinimumSize(QtCore.QSize(319, 269))
            self.setMaximumSize(QtCore.QSize(319, 269))

            self.centralWidget = QtWidgets.QWidget(self)
            self.centralWidget.setObjectName("centralWidget")

            self.server_ping_list_PlainEdit = QtWidgets.QPlainTextEdit(self.centralWidget)
            self.server_ping_list_PlainEdit.setGeometry(QtCore.QRect(20, 80, 271, 91))
            self.server_ping_list_PlainEdit.setObjectName("server_ping_list_PlainEdit")
            self.server_ping_list_PlainEdit.setPlainText(server_up_ping_list)

            self.internet_up_lineEdit = QtWidgets.QLineEdit(self.centralWidget)
            self.internet_up_lineEdit.setGeometry(QtCore.QRect(20, 30, 271, 20))
            self.internet_up_lineEdit.setObjectName("internet_up_lineEdit")
            self.internet_up_lineEdit.setText(net_up_ping_dest)
            self.label = QtWidgets.QLabel(self.centralWidget)
            self.label.setGeometry(QtCore.QRect(20, 10, 161, 16))
            self.label.setObjectName("label")
            self.label.setText("Internet Up? Ping Server")

            self.ping_interval_SpinBox = QtWidgets.QDoubleSpinBox(self.centralWidget)
            self.ping_interval_SpinBox.setGeometry(QtCore.QRect(20, 200, 62, 22))
            self.ping_interval_SpinBox.setDecimals(1)
            self.ping_interval_SpinBox.setMinimum(0.5)
            self.ping_interval_SpinBox.setMaximum(1000.0)
            self.ping_interval_SpinBox.setProperty("value", float(ping_interval))
            self.ping_interval_SpinBox.setObjectName("ping_interval_SpinBox")
            self.label_3 = QtWidgets.QLabel(self.centralWidget)
            self.label_3.setGeometry(QtCore.QRect(20, 180, 91, 16))
            self.label_3.setObjectName("label_3")
            self.label_3.setText("Ping Interval")

            self.apply_Button = QtWidgets.QPushButton(self.centralWidget)
            self.apply_Button.setGeometry(QtCore.QRect(220, 230, 75, 23))
            self.apply_Button.setObjectName("ok_Button")
            self.setWindowTitle("config_menu")
            self.apply_Button.setText("Apply")

            self.label_2 = QtWidgets.QLabel(self.centralWidget)
            self.label_2.setGeometry(QtCore.QRect(20, 60, 161, 16))
            self.label_2.setObjectName("label_2")
            self.label_2.setText("Server Ping List")

            self.ping_warning_threshold_SpinBox = QtWidgets.QDoubleSpinBox(self.centralWidget)
            self.ping_warning_threshold_SpinBox.setGeometry(QtCore.QRect(160, 200, 62, 22))
            self.ping_warning_threshold_SpinBox.setDecimals(0)
            self.ping_warning_threshold_SpinBox.setMinimum(1.0)
            self.ping_warning_threshold_SpinBox.setMaximum(1000.0)
            self.ping_warning_threshold_SpinBox.setSingleStep(5.0)
            self.ping_warning_threshold_SpinBox.setProperty("value", warning_threshold)
            self.ping_warning_threshold_SpinBox.setObjectName("ping_warning_threshold_SpinBox")
            self.label_4 = QtWidgets.QLabel(self.centralWidget)
            self.label_4.setGeometry(QtCore.QRect(160, 180, 131, 16))
            self.label_4.setObjectName("label_4")
            self.label_4.setText("Ping Warning Threshold")

            self.label_5 = QtWidgets.QLabel(self.centralWidget)
            self.label_5.setGeometry(QtCore.QRect(230, 200, 31, 16))
            self.label_5.setObjectName("label_5")
            self.label_6 = QtWidgets.QLabel(self.centralWidget)
            self.label_6.setGeometry(QtCore.QRect(90, 200, 31, 16))
            self.label_6.setObjectName("label_6")
            self.label_5.setText("ms")
            self.label_6.setText("s")


        def closeEvent(self, event):

            # don't exit
            self.hide()
            event.ignore()


    class SystemTrayWidget(QtWidgets.QSystemTrayIcon):
        def __init__(self, icon, parent=None):
            QtWidgets.QSystemTrayIcon.__init__(self, icon, parent)
            self.menu = QtWidgets.QMenu(parent)
            self.config_action = self.menu.addAction("Config")
            exitAction = self.menu.addAction("Exit")
            exitAction.triggered.connect(QtWidgets.qApp.quit)
            self.setContextMenu(self.menu)




    """
    def main():
        global msg, tray
        app = QtWidgets.QApplication(sys.argv)
        icon = QtGui.QIcon('icons/white_thumb_up.png')  # need a icon
        tray = SystemTrayIcon(icon)
        config_menu = MsgBox2()
        config_menu.show()
        timer = QTimer()
        timer.timeout.connect(bop)
        timer.start(30000)  # every 30 secs
        QTimer.singleShot(3000, bop)  # check on open

        msg = MsgBox()
        tray.show()
        sys.exit(app.exec_())
    """

if __name__ == '__main__':

    app = pingTrayQt()
    sys.exit( app.run() )