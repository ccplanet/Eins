#!/usr/bin/env python
# coding=utf-8
import numpy as np
import basicroad as br
import basicplot as bp
import road
import statistics as st
import pandas as pd
plantime = 50
carsNum = 10
vmax = 20
carTemp = road.Car()
carTemp.safedistance = 5
carTemp.length = 5
InitCar = road.initCarsDistributed(
    100, [carTemp] )
if __name__ == '__main__':
    
    
    print 'Process start'
    
    rd = road.execRoad(InitCar, vmax, 2000, enterflag=True, lanes=1)
    #rd2 = br.Road(br.initEmptyRoad(2), vmax, 500, lanes_=2)
    #rd.setConnectTo(rd2)
    rd.cycleBoundaryCondition(True, carTemp)
    #rd.addCarAutomaticByBound(True, carTemp)
    bp.addRoad(np.array([20.0, 70.0]), np.array([50.0, 50.0]), rd)
    bp.plot()
    

    '''
    #rd.setTT(True)
    rdinfo = br.ProcessWriter(rd,'road2',plantime)
    rdinfo.setInit()
    for i in xrange(0,plantime):
        rd.reflushStatus()
        rdinfo.writeInfo()
    rdinfo.cleanAll()
    '''
    print 'Done'
    
