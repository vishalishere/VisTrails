############################################################################
##
## Copyright (C) 2006-2010 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################
from PyQt4 import QtCore, QtGui
from gui.theme import CurrentTheme
import core.debug
import StringIO
import api
import cgi

################################################################################


class DebugView(QtGui.QDialog):
    """ Class used for showing error messages and
        debugging QT signals.

        Example of usage:
           import gui.debug
           gui.debug.watch_signal(my_signal)
     """
    #Singleton technique
    _instance = None
    class DebugViewSingleton():
        def __call__(self, *args, **kw):
            if DebugView._instance is None:
                obj = DebugView(*args, **kw)
                DebugView._instance = obj
            return DebugView._instance
        
    getInstance = DebugViewSingleton()

    def __init__(self, parent = None):
        QtGui.QDialog.__init__(self, parent)
        core.debug.DebugPrint.getInstance().set_stream(debugStream(self.write)) 
        self.setWindowTitle('VisTrails Messages')
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)

        # top message filter buttons
        filterHolder = QtGui.QGridLayout()
        layout.addLayout(filterHolder)
        filter = QtGui.QGridLayout()
        filterHolder.addLayout(filter, 0, 0, QtCore.Qt.AlignLeft)

        filterLabel = QtGui.QLabel('Filter:')
        filterLabel.setFixedWidth(40)
        filter.addWidget(filterLabel, 0, 0)

        self.infoFilter = QtGui.QPushButton('Info', self)
        self.infoFilter.setCheckable(True)
        self.infoFilter.setChecked(True)
        self.infoFilter.setFixedWidth(70)
        self.infoFilter.setStyleSheet('color:' +
                                 CurrentTheme.DEBUG_INFO_COLOR.name())
        self.connect(self.infoFilter, QtCore.SIGNAL('toggled(bool)'),
                     self.toggleInfo)
        filter.addWidget(self.infoFilter, 0, 1)

        self.warningFilter = QtGui.QPushButton('Warning', self)
        self.warningFilter.setCheckable(True)
        self.warningFilter.setChecked(True)
        self.warningFilter.setFixedWidth(70)
        self.warningFilter.setStyleSheet('color:' +
                                    CurrentTheme.DEBUG_WARNING_COLOR.name())
        self.connect(self.warningFilter, QtCore.SIGNAL('toggled(bool)'),
                     self.toggleWarning)
        filter.addWidget(self.warningFilter, 0, 2)

        self.criticalFilter = QtGui.QPushButton('Critical', self)
        self.criticalFilter.setCheckable(True)
        self.criticalFilter.setChecked(True)
        self.criticalFilter.setFixedWidth(70)
        self.criticalFilter.setStyleSheet('color:' +
                                    CurrentTheme.DEBUG_CRITICAL_COLOR.name())
        self.connect(self.criticalFilter, QtCore.SIGNAL('toggled(bool)'),
                     self.toggleCritical)
        filter.addWidget(self.criticalFilter, 0, 3)

        # message list
        self.list = QtGui.QListWidget()
        self.connect(self.list,
                     QtCore.SIGNAL('currentItemChanged(QListWidgetItem *, QListWidgetItem *)'),
                     self.showMessage)
        layout.addWidget(self.list)

        # message details field
        self.text = QtGui.QTextEdit()
        self.text.setReadOnly(True)
        self.text.hide()
        layout.addWidget(self.text)

        # bottom buttons
        buttons = QtGui.QGridLayout()
        layout.addLayout(buttons)
        leftbuttons = QtGui.QGridLayout()
        buttons.addLayout(leftbuttons, 0, 0, QtCore.Qt.AlignLeft)
        rightbuttons = QtGui.QGridLayout()
        buttons.addLayout(rightbuttons, 0, 1, QtCore.Qt.AlignRight)

        close = QtGui.QPushButton('&Close', self)
        close.setFixedWidth(120)
        close.setDefault(True)
        leftbuttons.addWidget(close, 0, 0)
        self.connect(close, QtCore.SIGNAL('clicked()'),
                     self, QtCore.SLOT('close()'))

        copy = QtGui.QPushButton('Copy &Message', self)
        copy.setToolTip('Copy selected message to clipboard')
        copy.setFixedWidth(120)
        rightbuttons.addWidget(copy, 0, 0)
        self.connect(copy, QtCore.SIGNAL('clicked()'),
                     self.copyMessage)

        copyAll = QtGui.QPushButton('Copy &All', self)
        copyAll.setToolTip('Copy all messages to clipboard (Can be a lot)')
        copyAll.setFixedWidth(120)
        rightbuttons.addWidget(copyAll, 0, 1)
        self.connect(copyAll, QtCore.SIGNAL('clicked()'),
                     self.copyAll)
        self.msg_box = None
        self.itemQueue = []
        self.resize(700, 400)

    def toggleType(self, s, visible):
        for item in [self.list.item(i) for i in xrange(self.list.count())]:
            if str(item.data(32).toString()).split('\n')[0] == s:
                self.list.setItemHidden(item, not visible)

    def toggleInfo(self, visible):
        self.toggleType('INFO', visible)

    def toggleWarning(self, visible):
        self.toggleType('WARNING', visible)

    def toggleCritical(self, visible):
        self.toggleType('CRITICAL', visible)
        
    def copyMessage(self):
        """ copy selected message to clipboard """
        items = self.list.selectedItems()
        if len(items)>0:
            text = str(items[0].data(32).toString())
            api.VistrailsApplication.clipboard().setText(text)

    def copyAll(self):
        """ copy selected message to clipboard """
        texts = []
        for i in range(self.list.count()):
            texts.append(str(self.list.item(i).data(32).toString()))
        text = '\n'.join(texts)
        api.VistrailsApplication.clipboard().setText(text)

    def showMessage(self, item, olditem):
        """ show item data in a messagebox """
        s = str(item.data(32).toString())
        msgs = s.split('\n')
        msgs = [cgi.escape(i) for i in msgs]
        format = {'INFO': 'Message:',
                  'WARNING': 'Warning message:',
                  'CRITICAL': 'Critical message:'}
        
        text = '<HTML><BODY BGCOLOR="#FFFFFF">'
        text += '<H4>%s</H4>' % format.get(msgs[0], 'Message:')
        text += '<H4>%s<br></H4>' % msgs[3]
        text += '<table border="0">'
        if len(msgs)>4:
            text += '<tr><td>&nbsp;</td><td align=left>%s</td></tr>' % '<br>'.join(msgs[4:])
            text += '<tr><td>&nbsp;</td><td>&nbsp;</td></tr>'
        text += '<tr><td align=right><b>Time:</b></td><td>%s</td></tr>' % msgs[1]
        text += '<tr><td align=right><b>Location:</b></td><td>%s</td></tr>' % msgs[2]
        text += '</table></BODY></HTML>'

        self.text.setHtml(text)
        self.text.show()

    def watch_signal(self, obj, sig):
        """self.watch_signal(QObject, QSignal) -> None. Connects a debugging
        call to a signal so that every time signal is emitted, it gets
        registered on the log.
        """
        self.connect(obj, sig, self.__debugSignal)

    def __debugSignal(self, *args):
        """ Receives debug signal """
        debug(str(args))

    def updateMessageBox(self, item):
        self.currentItem = item
        msg_box = self.msg_box
        # update messagebox with data from item
        s = str(item.data(32).toString())
        msgs = s.split('\n')
        if msgs[0] == "INFO":
            msg_box.setIcon(QtGui.QMessageBox.Information)
            msg_box.setWindowTitle("Information")
        elif msgs[0] == "WARNING":
            msg_box.setIcon(QtGui.QMessageBox.Warning)
            msg_box.setWindowTitle("Warning")
        elif msgs[0] == "CRITICAL":
            msg_box.setIcon(QtGui.QMessageBox.Critical)
            msg_box.setWindowTitle("Critical error")
        msg_box.setText(msgs[3])

    def showMessageBox(self, item):
        """ Displays the current message in a messagebox
            if a message is already shown the same message is shown again
            but with a "next message"-button
        """
        msg_box = self.msg_box
        if not msg_box or not msg_box.isVisible():
            # create messagebox
            # app segfaults if the handle to the old messagebox is removed
            self.old_msg_box = msg_box
            msg_box = QtGui.QMessageBox(self.parent())
            self.msg_box = msg_box
            msg_box.setStandardButtons(QtGui.QMessageBox.Ok)
            msg_box.setDefaultButton(QtGui.QMessageBox.Ok)
            msg_box.setEscapeButton(QtGui.QMessageBox.Ok)
            msg_box.addButton('&Show Messages', msg_box.RejectRole)
            self.manyButton = None
            self.connect(msg_box,
                         QtCore.SIGNAL('buttonClicked(QAbstractButton *)'),
                         self.messageButtonClicked)
            self.updateMessageBox(item)
        else:
            self.itemQueue.append(item)

        # check queue
        if self.itemQueue:
            # need to set nextmessage-button
            many = len(self.itemQueue)
            text = '&Next Message (%s more)' % many
            if not self.manyButton:
                # create button
                self.manyButton=QtGui.QPushButton(text)
                msg_box.addButton(self.manyButton, msg_box.DestructiveRole)
            else:
                self.manyButton.setText(text)
        else:
            # remove button if it exist
            if self.manyButton:
                print "removing", self.manyButton
                msg_box.removeButton(self.manyButton)
                self.manyButton = None
        if not msg_box.isVisible():
            msg_box.show()
        msg_box.resize(msg_box.sizeHint())
        msg_box.updateGeometry()
        msg_box.activateWindow()
        msg_box.raise_()

    def messageButtonClicked(self, button):
        role = self.msg_box.buttonRole(button)
        if role == self.msg_box.RejectRole:
            self.itemQueue = []
            self.show()
            self.list.setCurrentItem(self.currentItem)
            self.list.scrollToItem(self.currentItem)
        elif role == self.msg_box.DestructiveRole:
            # show next message
            item = self.itemQueue[0]
            del self.itemQueue[0]
            self.showMessageBox(item)
        else:
            self.itemQueue = []
        
    def write(self, s):
        """write(s) -> None
        adds the string s to the message list and displays it
        if it is critical."""
        # adds the string s to the list and 
        s = str(s).strip()
        msgs = s.split('\n')
        text = msgs[3] if len(msgs)>2 else ''
        item = QtGui.QListWidgetItem(text)
        item.setData(32, s)
        item.setFlags(item.flags()&~QtCore.Qt.ItemIsEditable)
        self.list.addItem(item)
        if msgs[0] == "INFO":
            item.setForeground(QtGui.QBrush(CurrentTheme.DEBUG_INFO_COLOR))
            self.list.setItemHidden(item, not self.infoFilter.isChecked())
        elif msgs[0] == "WARNING":
            item.setForeground(QtGui.QBrush(CurrentTheme.DEBUG_WARNING_COLOR))
            self.list.setItemHidden(item, not self.warningFilter.isChecked())
        elif msgs[0] == "CRITICAL":
            item.setForeground(QtGui.QBrush(CurrentTheme.DEBUG_CRITICAL_COLOR))
            self.list.setItemHidden(item, not self.criticalFilter.isChecked())
        self.list.scrollToItem(item)
        if msgs[0] == "CRITICAL":
            self.showMessageBox(item)

    def closeEvent(self, e):
        """closeEvent(e) -> None
        Event handler called when the dialog is about to close."""
        self.emit(QtCore.SIGNAL("messagesView(bool)"), False)

    def showEvent(self, e):
        """closeEvent(e) -> None
        Event handler called when the dialog is about to close."""
        self.emit(QtCore.SIGNAL("messagesView(bool)"), True)

    def reject(self):
        """ Captures Escape key and closes window correctly """
        self.close()

class debugStream(StringIO.StringIO):
    def __init__(self, write):
        StringIO.StringIO.__init__(self)
        self.write = write

def watch_signal(obj, sig):
    DebugView.getInstance().watch_signal(obj, sig)


critical     = core.debug.critical
warning      = core.debug.warning
log          = core.debug.log
debug        = core.debug.debug
