# -*- coding: utf-8 -*-
import os
import sys
import subprocess
from PyQt4 import uic, QtGui, QtCore

import numpy as np
import cv2

import json
import math

reload(sys)
sys.setdefaultencoding('utf-8')

class Webcam():
  def __init__(self):
    self.conf = QtCore.QSettings()
    self.MainWindow = uic.loadUi('gui.ui')
    self.MainWindow.segmentos.setEnabled(False)

    try:
      img  = cv2.imread('jpg0.jpg')
      self.alto, self.ancho, channels = img.shape
    except:
      msg = QtGui.QMessageBox(QtGui.QMessageBox.Critical, "Imagen no encontrada","Verifique la ubicación", QtGui.QMessageBox.Ok, self.MainWindow)
      msg.exec_()
      sys.exit()

    self.zoom = 3
    self.targetH = self.alto * self.zoom
    self.targetW = self.ancho  * self.zoom
    self.detailH = 75
    self.detailW = 75
    self.mouse_x = 0
    self.mouse_y = 0

    self.cadenas = []
    self.posicion = -1
    self.capturando = ['',0]
    self.cargarDimensiones()
    self.mostrarDimensiones(0)


    self.img = cv2.resize(img,(self.targetW, self.targetH), interpolation = cv2.INTER_CUBIC)

    print "Camera resolution: %dx%d" % (self.ancho, self.alto)
    print "Target resolution: %dx%d" % (self.targetW, self.targetH)
    self.roi = ROI.fromWH((self.targetW-self.detailW)/2, (self.targetH-self.detailH)/2, self.detailW, self.detailH, self.targetW, self.targetH)

    pixmap   = self.cvFrame2pixmap(self.img)
    self.MainWindow.liveView.setPixmap(pixmap)

    print self.MainWindow.tablaDimensiones
    self.MainWindow.b_anadirPos.clicked.connect(self.anadirPos)

    self.MainWindow.b_cabeza.clicked.connect(self.capturar_cabeza)
    self.MainWindow.b_tronco.clicked.connect(self.capturar_tronco)
    self.MainWindow.b_brazo.clicked.connect(self.capturar_brazo)
    self.MainWindow.b_antebrazo.clicked.connect(self.capturar_antebrazo)
    self.MainWindow.b_mano.clicked.connect(self.capturar_mano)
    self.MainWindow.b_muslo.clicked.connect(self.capturar_muslo)
    self.MainWindow.b_pantorrilla.clicked.connect(self.capturar_pantorrilla)
    self.MainWindow.b_pie.clicked.connect(self.capturar_pie)

    self.MainWindow.b_torques.clicked.connect(self.calcular_torques)

    self.MainWindow.cb_posiciones.currentIndexChanged.connect(self.seleccionarPosicion)
    self.MainWindow.cbTablaDimensiones.currentIndexChanged.connect(self.mostrarDimensiones)

    self.MainWindow.actionCargar.triggered.connect(self.cargar)
    self.MainWindow.actionExportar.triggered.connect(self.exportar)

    customControl(self.MainWindow.liveView).connect(self.mouseTracker)

  def exportar(self):
    with open('coordenadas.json', 'w') as outfile:
      json.dump(self.cadenas, outfile)

  def cargar(self):
    with open('coordenadas.json', 'r') as infile:    
      self.cadenas = json.load(infile)
      self.MainWindow.cb_posiciones.clear()
      for i in range(len(self.cadenas)):
        self.MainWindow.cb_posiciones.addItem('%d' % i)
      self.posicion = i
      self.MainWindow.segmentos.setEnabled(True)
      self.MainWindow.cb_posiciones.setCurrentIndex(self.posicion);
      self.redraw()

  def anadirPos(self):
    self.posicion += 1
    self.MainWindow.cb_posiciones.addItem('%d' % self.posicion);
    self.MainWindow.cb_posiciones.setCurrentIndex(self.posicion);
    self.cadenas.append({});
    self.MainWindow.segmentos.setEnabled(True)

  def seleccionarPosicion(self, indx):
    self.posicion = indx
    self.redraw()

  def establecer_llave(self, llave):
    self.capturando = [llave,0]
#    if not llave in self.cadenas[self.posicion]:
    self.cadenas[self.posicion][llave] = {'coordenadas':[[],[]], 'COM':[0,0]}

  def capturar_cabeza(self):
    self.establecer_llave('cabeza')
  def capturar_tronco(self):
    self.establecer_llave('tronco')
  def capturar_brazo(self):
    self.establecer_llave('brazo')
  def capturar_antebrazo(self):
    self.establecer_llave('antebrazo')
  def capturar_mano(self):
    self.establecer_llave('mano')
  def capturar_muslo(self):
    self.establecer_llave('muslo')
  def capturar_pantorrilla(self):
    self.establecer_llave('pantorrilla')
  def capturar_pie(self):
    self.establecer_llave('pie')

  def cvFrame2pixmap(self, frame):
    data = frame.tostring()
    height, width, channels = frame.shape
    image = QtGui.QImage(data, width, height, channels * width, QtGui.QImage.Format_RGB888)
    pixmap = QtGui.QPixmap()
    pixmap.convertFromImage(image.rgbSwapped())
    return pixmap

  def calcularCOMSegmento(self, segmento, coordenadas):
    i = self.MainWindow.cbTablaDimensiones.currentIndex() 
    escala = self.dimensiones[i][segmento][0]/100
    x = coordenadas[0][0]+escala*(coordenadas[1][0]-coordenadas[0][0])
    y = coordenadas[0][1]+escala*(coordenadas[1][1]-coordenadas[0][1])
    return [int(x),int(y)]

  def calcularCOM(self, indx):
    i = self.MainWindow.cbTablaDimensiones.currentIndex() 
    x = 0
    y = 0
    pesoT = 0
    cadena = self.cadenas[indx]
    for segmento in cadena:
      if segmento == 'COM':
        continue
      peso = self.dimensiones[i][segmento][1] 
      com = cadena[segmento]['COM']
      x += com[0] * peso
      y += com[1] * peso
      pesoT +=  peso
    x = x / pesoT
    y = y / pesoT
    self.cadenas[indx]['COM'] = [int(x),int(y)]

  def calcular_torques(self):
    ta = self.MainWindow.cbTablaDimensiones.currentIndex() 
    i=0
    self.torques = []
    for cadena in self.cadenas:
      print '\n\n\n------------------------\nPostura %d:' %i
      self.torques.append({});
      com = cadena['COM']
      torqueT = 0
      for segmento in cadena:
        if segmento == 'COM':
          continue
        com_segmento = cadena[segmento]['COM']

        d = [com_segmento[0]-com[0], com[1]-com_segmento[1]] #Invertir y para coincidir con sistema de referencia
        d = math.sqrt(math.pow(d[0],2)+math.pow(d[1],2))
        t = self.dimensiones[ta][segmento][1] * math.pow(d,2)
        x = self.ordenSegmentos.index(segmento)
        if x >=2: #Si es pierna o brazo va doble
          t =t*2
        dir = 1
        if com_segmento[0]-com[0]<0: dir = -1
        self.torques[i][segmento] = {'distancia':d, 'torque':t, 'direccion': dir};
        torqueT += t*dir
        print segmento, t, torqueT
#        print segmento,": ", d
      self.torques[i]['total'] = torqueT
      i+=1
#    print self.torques
    self.exportar_torques()

  def exportar_torques(self):
    header = ','
    out = ''
    for segmento in self.ordenSegmentos:
      out += segmento.title()
      for torque in self.torques:
        out += ',%.2f,%.2f' % (torque[segmento]['distancia'], torque[segmento]['torque'])
      else:
        out += '\n'
    out += 'Total'
    for torque in self.torques:
      out += ',,%.2f' % (torque['total'])
    out += '\n'
    print out

  def mouseTracker(self, obj, type, x, y):
    self.mouse_x = x
    self.mouse_y = y
    if type == customControlOps.actionCapture and self.posicion > -1:
      if self.capturando[0]!='' and self.capturando[1]<2:
        self.cadenas[self.posicion][self.capturando[0]]['coordenadas'][self.capturando[1]] = [x,y] 
        self.capturando[1] += 1
        if self.capturando[1] > 1:
          self.cadenas[self.posicion][self.capturando[0]]['COM'] = self.calcularCOMSegmento(self.capturando[0], self.cadenas[self.posicion][self.capturando[0]]['coordenadas']) 
          self.calcularCOM(self.posicion)
    self.redraw()

  def redraw(self):
    capture = self.img.copy()
    i=0
    for cadena in self.cadenas:
      if self.posicion == i:
        color = (18,0,251)
        colorCOM = (0,149,255)
      else:
        color = (0,219,255)
        colorCOM = (0,229,134)
      for segmento in cadena:
        if segmento == 'COM':
          com = cadena[segmento]
          cv2.circle(capture,(com[0],com[1]) , 7, colorCOM, -1)
          self.sistema_referencia(capture, com[0], com[1])
          continue
        previo = []
        com = cadena[segmento]['COM']
        for coordenadas in cadena[segmento]['coordenadas']:
          if coordenadas != []:
            cv2.circle(capture,(coordenadas[0],coordenadas[1]) , 1, color, -1)
            if previo != []:
              cv2.line(capture,(previo[0],previo[1]),(coordenadas[0],coordenadas[1]), color, 1)
              cv2.circle(capture,(com[0],com[1]) , 3, color, -1)
            previo = coordenadas
      i+=1
    if self.capturando[1]==1:
      color = (0,219,255)
      previo = self.cadenas[self.posicion][self.capturando[0]]['coordenadas'][0]
      cv2.line(capture,(previo[0],previo[1]),(self.mouse_x,self.mouse_y), color, 1)
    self.cruceta(capture, self.mouse_x, self.mouse_y, (0,0,255))
    pixmap = self.cvFrame2pixmap(capture)
    self.MainWindow.liveView.setPixmap(pixmap)
    self.roi.moveToXY(self.mouse_x, self.mouse_y,True)
    detail = capture[self.roi.start_Y:self.roi.end_Y, self.roi.start_X:self.roi.end_X]
    detail = cv2.resize(detail,(self.detailW*3, self.detailH*3), interpolation = cv2.INTER_CUBIC)
    pixmap = self.cvFrame2pixmap(detail)
    self.MainWindow.l_detail.setPixmap(pixmap)

  def move_cap_x(self, value):
    self.roi.moveToPartX(value)
  def move_cap_y(self, value):
    self.roi.moveToPartY(value)

  def cruceta(self, frame, x, y, color = (0,0,0), w=1):
    cv2.line(frame,(int(x),0),(int(x),int(y-1)), color,1)
    cv2.line(frame,(int(x),int(y+1)),(int(x),int(self.targetH)), color,1)
    cv2.line(frame,(0,int(y)),(int(x-1),int(y)),color,w)
    cv2.line(frame,(int(x+1),int(y)),(int(self.targetW),int(y)),color,w)
    cv2.circle(frame,(x,y) , 7, color, 1)

  def sistema_referencia(self, frame, x, y):
    l = 17
    w = 2
    a = 3
    cv2.line(frame,(int(x),int(y)),(int(x),int(y-l)), (255,0,0),w)
    cv2.line(frame,(int(x),int(y)),(int(x+l),int(y)), (0,255,0),w)
#    cv2.fillPoly(frame,[(int(x+l-3),int(y+3)),(int(x+l),int(y)),(int(x+l-3),int(y-3))], (0,255,0))

  def raya_vertical(self, frame, x, color = (0,0,0), w=1):
    cv2.line(frame,(int(x),0),(int(x),int(self.targetH)),color,w)

  def raya_horizontal(self, frame, y, color =(0,0,0), w=1):
    cv2.line(frame,(0,int(y)),(int(self.targetW),int(y)),color,w)

  def vertical_frontal(self, frame, color = (0,0,0)):
    self.raya_vertical(frame, self.targetW/2,	color)
    self.raya_vertical(frame, (self.targetW/2)+120,	color)
    self.raya_vertical(frame, (self.targetW/2)-120,	color)
    self.raya_vertical(frame, (self.targetW/2)+144,	color)
    self.raya_vertical(frame, (self.targetW/2)-144,	color)

  def vertical_lateral(self, frame, color = (0,0,0)):
    self.raya_vertical(frame, (self.targetW/2)+144, color)
    self.raya_vertical(frame, (self.targetW/2)-144, color)

  def horizontal(self, frame, color = (0,0,0)):
    self.raya_horizontal(frame, 253,	color)
    self.raya_horizontal(frame, 287,	color)
    self.raya_horizontal(frame, 322,	color)

  def __del__(self):
    print "Terminando..."

  def mostrarDimensiones(self, i):
    suma = 0
    for llave, valores in self.dimensiones[i].items():
      x = self.ordenSegmentos.index(llave)
      item = QtGui.QTableWidgetItem('%.1f'%valores[0])
      self.MainWindow.tablaDimensiones.setItem(x, 0, item)
      item = QtGui.QTableWidgetItem('%.3f'%valores[1])
      self.MainWindow.tablaDimensiones.setItem(x, 1, item)
#      x = self.ordenSegmentos.index(llave)
#      if x <2:
#        suma += valores[1]
#      else:
#        suma += 2*valores[1]
#    print suma

  def cargarDimensiones(self):
    self.dimensiones = [
      { #Hombre
        'cabeza':	[53.6, 0.073],
        'tronco':	[56.2, 0.507],
        'brazo':	[50.9, 0.026],
        'antebrazo':	[58.2, 0.016],
        'mano':		[52.0, 0.007],
        'muslo':	[60.0, 0.103],
        'pantorrilla':	[58.2, 0.043],
        'pie':		[55.1, 0.015]
      },
      { #Mujer
        'cabeza':	[45.0, 0.082],
        'tronco':	[61.0, 0.452],
        'brazo':	[54.2, 0.029],
        'antebrazo':	[56.6, 0.016],
        'mano':		[53.2, 0.005],
        'muslo':	[57.2, 0.118],
        'pantorrilla':	[58.1, 0.054],
        'pie':		[50.0, 0.013]
      }
    ]
    self.ordenSegmentos = [
      'cabeza',
      'tronco',
      'brazo',
      'antebrazo',
      'mano',
      'muslo',
      'pantorrilla',
      'pie'
    ]

class customControlOps:
  actionMouseMove = 0
  actionCapture = 1

def customControl(widget):
  class Filter(QtCore.QObject):
    motion = QtCore.pyqtSignal(QtCore.QObject, int, int, int)
    def eventFilter(self, obj, event):
      if obj == widget:
        if event.type() == QtCore.QEvent.MouseMove or event.type() == QtCore.QEvent.MouseButtonRelease:
          if obj.rect().contains(event.pos()):
            x = event.pos().x()
            y = event.pos().y()
            if event.type() == QtCore.QEvent.MouseButtonRelease:
              action = customControlOps.actionCapture
            else:
              action = customControlOps.actionMouseMove

            self.motion.emit(obj, action, x, y)
            return True
      return False
  filter = Filter(widget)
  widget.installEventFilter(filter)
  return filter.motion

class ROI():
  def __init__(self,start_X, end_X, start_Y, end_Y, max_X, max_Y):
    self.start_X = int(start_X)
    self.end_X   = int(end_X)
    self.start_Y = int(start_Y)
    self.end_Y   = int(end_Y)
    self.width   = int(end_X-start_X)
    self.height  = int(end_Y-start_Y)
    self.max_X   = int(max_X)
    self.max_Y   = int(max_Y)

  @classmethod
  def fromWH(cls, start_X, start_Y, width, height, max_X, max_Y):
    end_X = start_X + width
    end_Y = start_Y + height
    return cls(start_X, end_X, start_Y, end_Y, max_X, max_Y)

  def moveToCenter(self):
    width  = end_X-start_X
    height = end_Y-start_Y 
    self.start_X = (max_X-width)/2
    self.end_X   = (max_X+width)/2
    self.start_Y = (max_Y-height)/2
    self.end_Y   = (max_Y+height)/2

  def moveToXY(self, x, y, center=False):
    x = int(x)
    y = int(y)
    if center:
      x = x-self.width/2
      y = y-self.height/2
    if x>self.max_X-self.width:
      x = self.max_X-self.width
    elif x<0:
      x=0
    if y>self.max_Y-self.height:
      y = self.max_Y-self.height
    elif y<0:
      y=0
    self.start_X = x
    self.end_X = self.start_X + self.width
    self.start_Y = y
    self.end_Y = self.start_Y + self.height

  def moveToPartX(self, value):
    if value>100:
      value = 100
    elif value<0:
      value=0
    to = int(value*(self.max_X-self.width)/100)
    self.start_X = to
    self.end_X = self.start_X + self.width
  def moveX(self, n):
    if n<0:
      self.moveLeft(-n)
    else:
      self.moveRight(n)
  def moveLeft(self, n):
    self.start_X -= n
    if self.start_X < 0:
      self.start_X=0
    self.end_X = self.start_X + self.width
  def moveRight(self, n):
    self.end_X += n
    if self.end_X > self.max_X:
      self.end_X=self.max_X
    self.start_X = self.end_X - self.width

  def moveToPartY(self, value):
    if value>100:
      value = 100
    elif value<0:
      value=0
    to = int(value*(self.max_Y-self.height)/100)
    self.start_Y = to
    self.end_Y = self.start_Y + self.height
  def moveY(self, n):
    if n<0:
      self.moveUp(-n)
    else:
      self.moveDown(n)
  def moveUp(self, n):
    self.start_Y -= n
    if self.start_Y < 0:
      self.start_Y=0
    self.end_Y = self.start_Y + self.height
  def moveDown(self, n):
    self.end_Y += n
    if self.end_Y > self.max_Y:
      self.end_Y=self.max_Y
    self.start_Y = self.end_Y - self.height

#  def __init__(self,start_X, end_X, start_Y, end_Y, max_X, max_Y):
  def zoomTo(self, x, y, zoom, ancho, alto):
    print "Zoom"
#Calcular ¿?
    self.max_X   = int(self.max_X*zoom)
    self.max_Y   = int(self.max_Y*zoom)
    if self.max_X != ancho or self.max_Y != alto:
      print "Resolution Bug...  Fixme"
      self.max_X   = int(ancho)
      self.max_Y   = int(alto)

    self.start_X = int(zoom*(self.start_X-x)+x)
    if self.start_X < 0:
      self.start_X = 0
    self.end_X   = self.start_X + self.width
    if self.end_X > self.max_X:
      self.end_X = self.max_X
      self.start_X = self.end_X - self.width

    self.start_Y = int(zoom*(self.start_Y-y)+y) 
    if self.start_Y < 0:
      self.start_Y = 0
    self.end_Y   = self.start_Y + self.height
    if self.end_Y > self.max_Y:
      self.end_Y = self.max_Y
      self.start_Y = self.end_Y - self.height

if __name__ == "__main__":
#  QtCore.QCoreApplication.setOrganizationName("División Científica")
#  QtCore.QCoreApplication.setOrganizationDomain("pf.gob.mx");
#  QtCore.QCoreApplication.setApplicationName("BioCapture");
  app = QtGui.QApplication(sys.argv)
  webcam = Webcam()
  webcam.MainWindow.showMaximized()
  app.exec_()
