from PyQt5 import QtGui


def setForeground(widget, color):
    color = QtGui.QColor(color)
    palette = widget.palette()
    palette.setColor(widget.foregroundRole(), color)
    widget.setPalette(palette)


def setBackground(widget, color):
    color = QtGui.QColor(color)
    palette = widget.palette()
    palette.setColor(widget.backgroundRole(), color)
    widget.setPalette(palette)


class Colors:

    red = "red"
    green = "green"
    white = "white"
