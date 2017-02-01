#!/usr/bin/env python
# coding=utf-8

#优化工作: 0%
#GUI: 0%

import numpy as np
import copy

#不作为类,用作为结构体,记录车的各种参数
class Car:
    def __init__(self):
        self.name = 'default'               #车类名称,用于统计
        self.length = 1.0                   #车身长度
        self.vDistance = 0.0                #最小车距
        self.slowacc = 0.5                  #慢加速度/s
        self.acc = 1.0                      #加速度/s
        self.negacc = 1.0                   #减速度/s
        self.view = 0                       #司机视野距离
        self.v = 0.0                        #当前速度
        self.locate = 0.0                   #当前所在位置
        self.lane = 0                       #当前所在车道
        self.height = 0.0                   #汽车高度,暂时没用
        self.bn = False                     #刹车灯
        self.tst = 0                        #敏感时间
        self.stoped = False                 #上一个时刻受到了阻挡后刹车的标记
        self.changeFlag = False
        
class Road(object):
    'Road && Cars'

    def __init__(self, carBox, vmax, length, lanes = 1,
                 enterCars = 0, enterFlag = False, connectRoad = None):
        self.carBox = carBox                    #道路上所有车辆及其具体状态和参数
        self.enterCars = enterCars              #已进入此路的车辆数
        self.leaveCars = [0]*lanes              #离开此路的车辆数
        self.vmax = vmax                        #道路最大车速
        self.length = length                    #道路长度
        self.lanes = lanes                      #车道数,默认为单车道
        self.laneFlag = 0                       #标记当前操作的车道号
        self.endCars = np.array([])             #list的长度表示有多少车辆需要进入其他道路,键值为其速度
        self.enterFlag = enterFlag              #标记此道是否是入口,如果非入口,
                                                #locate初始化值必须为[np.array([-1.0])],vBox必须为[np.array([0])](单车道,
                                                #多车道只需向list多添加初始值就可以了)
        self.changeSwitch = False
        self.alpha = 0.6                        #减速概率的alpha因子,不能随意修改,除非你知道自己在干什么
        self.beta = 0.2                         #减速概率的beta因子,同上
        self.autoAdderSwitch = False            #是否自动添加车辆
        self.autoAdderByTime = False            #是否按时间自动添加车辆,与前一个Flag冲突
        self.autoAdderBox = None                #自动添加车辆的初始速度
        self.connectRoad = connectRoad          #连接的公路(入口),默认值为空
        self.autoAddTime = 0                    #用户定义的自动添加车辆的时间间隔
        self.timeCounter = 0                    #系统内部用于自动添加车辆的时间计数器
        self.wholeTime = 0                      #总的运行时间
        self.stableP = 0.4                      #固定减速因子,一旦设定,那么alpha和beta就会失效
        self.waitLine = []                      #等待添加的车辆列队
        self.pers = None

    def __str__(self):
        des = '\n车道数:'+str(self.lanes)+'\n道路长度:'+str(self.length)+'\n运行时间(/s):'+str(self.wholeTime)+'\n是否为入口:'+str(self.enterFlag)
        carsCounter = []
        for index, lane in enumerate(self.carBox):
            carsCounter.append(len(lane))
            des += '\n'+'车量-车道'+str(index)+':'+str(len(lane))
        des += '\n'+'车总量:'+str(sum(carsCounter))
        return des

    #标记线内的为public func
    #-----------------------------------------------------
    def getCarsLocate(self):
        output = []
        for lane in self.carBox:
            output.append(np.array([car.locate for car in lane]))
        return output

    def getCarsV(self):
        output = []
        for lane in self.carBox:
            output.append(np.array([car.v for car in lane]))
        return output

    def ViewCars(self, car, viewBox, offset = 0.0):
        tempLocate = np.array([])
        for locate in viewBox:
            tempLocate = np.append(tempLocate, locate.v)
        temp = car.locate + car.view - tempLocate - offset
        temp = temp[temp >= 0]
        return temp.size

    #考虑视野距离计算实时随机减速概率
    def pCounter(self, carsNum, car):
        A = (float(carsNum)/car.view)**self.alpha
        B = (car.v/self.vmax)**self.beta
        return A*B

    def setAlphaBeta(self, alpha, beta):
        self.alpha = alpha
        self.beta = beta
    def setStabelP(self, p):
        self.stableP = p
    def getCarsInfo(self):
        return self.carBox

    def getRoadLanes(self):
        return self.lanes
    def getEndCarsNum(self):
        return self.endCars.size
    def getRoadLength(self):
        return self.length
    def getRoadVMax(self):
        return self.vmax
    def getLeaveCars(self):
        return self.leaveCars
    def getExecTime(self):
        return self.wholeTime

    #=====================模型=========================

    #慢启动规则
    def TT(self, car, nextCar, pt):
        if car.v == 0:
            if nextCar != None:
                if (car.length + nextCar.length)/2 +car.vDistance < nextCar.locate - car.locate <= (car.length + nextCar.length) + car.vDistance*2:
                    return 1.0 - pt
            else:
                return None
        else:
            return None

    def BJH(self, flag, ps):
        if flag:
            return 1.0 - ps
        else:
            return 0

    def VDR(self, flag, p0):
        if flag == False:
            return self.stableP
        else:
            return p0

    #减速规则
    def VE(self, car ,nextCar, next2Car):
        dn = (car.length + nextCar.length)/2 + car.vDistance
        dnc = (nextCar.length + next2Car.length)/2 + nextCar.vDistance
        vc = min(self.vmax - car.acc, nextCar.v, max(0,dnc - nextCar.acc))
        car.v = min(car.v + car.acc, dn + vc)

    #Kerner,Klenov,Wolf's Models
    
    #==================================================
    #减少需要进入其他道路车辆的计数,并且返回那辆车的信息
    def reduceEndCars(self):
        car = self.endCars[0]
        self.endCars = np.delete(self.endCars, 0)
        return car

class execRoad(Road):
    def __init__(self, carBox, vmax, length, lanes = 1,
                 enterCars = 0, enterFlag = False, connectRoad = None):
        super(execRoad, self).__init__(carBox, vmax, length, lanes,
                     enterCars, enterFlag, connectRoad)
        
        self.setMCDPara()
        self.execRule = self.MCD
        
        
        self.TTFlag = False
        self.TTPt = 0

        self.BJHFlag = False
        self.BJHPs = 0
        self.BJHflag = False

        self.VDRFlag = False
        self.VDRP0 = 0

        self.VEFlag = False
    
    def setMCDPara(self, h = 6, gap = 7, pb = 0.94, p0 = 0.5, 
                    pd = 0.1, tc = 10):
        self.h = h
        self.gap = gap
        self.pb = pb
        self.p0 = p0
        self.pd = pd
        self.tc = tc

    def setTT(self, switch, TTPt = 0.75):
        self.TTFlag = switch
        if switch == True:
            self.TTPt = TTPt

    def setBJH(self, switch, BJHPs = 0.75):
        self.BJHFlag = switch
        if switch == True:
            self.BJHPS = BJHPs

    def setVDR(self, switch, VDRP0 = 0.75):
        self.VDRFlag = switch
        if switch == True:
            self.VDRP0 = VDRP0

    def setVE(self, switch):
        self.VEFlag = switch

    #最基础的NS模型
    def NS(self, car, nextCar):
        #step1:加速
        if self.TTFlag:
            tempP = self.TT(car, nextCar, self.TTPt)
            if tempP == None or np.random.random() < tempP:
                car.v = min(car.v + car.acc, self.vmax)

        else:
            car.v = min(car.v + car.acc, self.vmax)

        if self.BJHFlag:
                tempP = self.BJH(car.stoped, self.BJHPs)
                if np.random.random() < tempP:
                    car.v = 0
        if self.BJHFlag or self.VDRFlag:
            car.stoped = False

        #step2:减速
        if nextCar != None:
            dn = (car.length+nextCar.length)/2 + car.vDistance
            distance = nextCar.locate - car.locate
        else:
            dn = 0.0
            distance = car.v*2
        if car.v + dn >= distance:
            d = max(0, distance - dn)
            car.v = min(car.v, d)
            if (self.VDRFlag or self.BJHFlag) and car.v == 0:
                car.stoped = True

        #step3:随机慢化
        if self.VDRFlag:
            tempP = self.VDR(car.stoped, self.VDRP0)
            if np.random.random() < tempP:
                car.v = max(car.v - car.negacc, 0)
        elif np.random.random() < self.stableP:
            car.v = max(car.v - car.negacc, 0)

        #step4:运动
        return car.v

    #舒适驾驶模型
    def CD(self, car, nextCar, next2Car):
        ts = min(car.v, self.h)
        if nextCar != None:
            nextCarbn = nextCar.bn
            dn = nextCar.locate - car.locate - (car.length + nextCar.length)/2 - car.vDistance
        else:
            nextCarbn = 0
            dn = ts*car.v + 1
        if car.v != 0:
            th = dn/car.v
        else:
            th = ts + 1
        #step1:确定随机慢化概率p
        if nextCarbn == 1 and th < ts:
            p = self.pb
        elif car.v == 0:
            p = self.p0
        else:
            p = self.pd
        nextbn = 0
        #step2:加速
        if (nextCarbn == 0 and car.bn == 0) or (th >= ts):
            nextv = min(car.v + car.acc, self.vmax)
        else:
            nextv = car.v
        #step3:减速
        if nextCar == None:
            deff = nextv + 1
        else:
            if next2Car == None:
                dnc = nextCar.v + 1
            else:
                dnc = next2Car.locate - nextCar.locate - (nextCar.length + next2Car.length)/2 - nextCar.vDistance
            vanti = min(dnc, nextCar.v)
            deff = max(dn + max(vanti - self.gap, 0), 0)
        
        nextv = min(deff, nextv)
        if nextv < car.v:
            nextbn = 1
        #step4:慢化
        if np.random.random() <= p:
            nextv = max(nextv - car.negacc, 0)
            if p == self.pb:
                nextbn = 1
        #step5:更新速度
        return nextv

    #改进的CD模型
    def MCD(self, car, nextCar, next2Car):
        ts = min(car.v, self.h)
        if nextCar != None:
            nextCarbn = nextCar.bn
            dn = nextCar.locate - car.locate - (car.length + nextCar.length)/2 - car.vDistance
        else:
            nextCarbn = 0
            dn = ts*car.v + 1
        if car.v != 0:
            th = dn/car.v
        else:
            th = ts + 1

        #step1:确定随机慢化概率
        if nextCarbn == 1 and th < ts:
            p = self.pb
        elif car.v == 0 and car.tst >= self.tc:
            p = self.p0
        else:
            p = self.pd

        #step2:加速
        if (nextCarbn == 0 or th >= ts) and car.v > 0:
            nextv = min(car.v + car.acc, self.vmax)
        elif car.v == 0:
            nextv = min(car.v + car.slowacc, self.vmax)
        else:
            nextv = car.v

        #step3:减速
        if nextCar == None:
            deff = nextv + 1
        else:
            if next2Car == None:
                dnc = nextCar.v + 1
            else:
                dnc = next2Car.locate - nextCar.locate - (nextCar.length + next2Car.length)/2 - nextCar.vDistance
            vanti = min(dnc, nextCar.v)
            deff = max(dn + max(vanti - self.gap, 0), 0)
        
        nextv = min(deff, nextv)

        #step4:慢化
        if np.random.random() <= p:
            nextv = max(nextv - car.negacc, 0)

        #step5:确定刹车灯状态bnc
        if nextv < car.v:
            nextbn = 1
        elif nextv > car.v:
            nextbn = 0
        else:
            nextbn = car.bn

        #step6:确定tst
        if nextv > 0:
            car.tst = 0
        else:
            car.tst += 1

        #step7:位置更新
        return nextv
    
    def KKW(self, car, nextCar):
        #参数确定
        #paras needs:vfree,d,p0
        dn = (car.length + nextCar.length)/2 + car.vDistance
        gn = nextCar.locate - car.locate - dn

        #request paras:k,p0,p,pa1,pa2,vp
        if self.modelKind == 1:
            D = self.modelPara['d'] + self.modelPara['k']*car.v*tao
            if car.v > 0:
                pb = self.modelPara['p']
            else:
                pb = self.modelPara['p0']

            if car.v < vp:
                pa = self.modelPara['pa1']
            else:
                pa = self.modelPara['pa2']

        #request paras:beta,p0
        elif self.modelKind == 2:
            D = self.modelPara['d'] + car.v*tao + self.modelPara['beta']*np.power(car.v, 2)/(car.acc*2)
            if car.v > 0:
                pb = self.modelPara['p']
            else:
                pb = self.modelPara['p0']

        #request paras:pa=0,beta,p0,p
        elif self.modelKind == 3:
            D = self.modelPara['d'] + car.v*tao + self.modelPara['beta']*np.power(car.v, 2)/(car.acc<<1)
            if 0 < car.v < self.modelPara['vfree']:
                pb = self.modelPara['p']
            elif car.v == 0:
                pb = self.modelPara['p0']
            elif car.v == self.modelPara['vfree']:
                pb = 0

        #request paras:d1<d,k,p0,p,pa
        elif self.modelKind == 4:
            D = self.modelPara['d1'] + self.modelPara['k']*car.v*tao
            if car.v > 0:
                pb = self.modelPara['p']
            else:
                pb = self.modelPara['p0']
        else:
            print 'Unkonw modelKind'

        vsafe = gn/self.tao

        #随机过程
        if gn > D - dn:
            vdes = car.v + car.acc*self.tao
        else:
            vdes = car.v + car.acc*self.tao*np.sign(nextCar.v - car.v)

        vc = max(0, min(vfree, vsafe, vdes))

        #确定过程
        rand = np.random.random()
        if rand < pb:
            era = -1
        elif pb <= rand < pb + pa:
            era = 1
        else:
            era = 0
        car.v = max(0,min(vc + car.acc*tao*era, vc + car.acc*tao, vfree, vsafe))

        car.locate += car.v 

    def reflushStatus(self):
        self.timer()   
        #每个车道分别计算,也就是车不会中途改变车道
        for lane in xrange(0,self.lanes):
            tempVSaver = []
            tempLocateSaver = []
            if len(self.carBox[lane]) == 0:
                continue
            if len(self.carBox[lane]) >= 2:
                for i in xrange(0, len(self.carBox[lane]) - 1):
                    opCar = self.carBox[lane][i]
                    opCar.lane = lane
                    nextCar = self.carBox[lane][i+1]
                    try:
                        next2Car = self.carBox[lane][i+2]
                    except:
                        next2Car = None
                    v = self.execRule(opCar, nextCar, next2Car)
                    tempVSaver.append(v)
                    tempLocateSaver.append(opCar.locate + v)
            #最前的车单独计算
            opCar = self.carBox[lane][-1]
            opCar.lane = lane
            nextCar = None
            next2Car = None
            if self.connectRoad != None:
                opLane = self.connectRoad.getNextEnterLane()
                info = self.connectRoad.getCarsInfo()
                if len(info[opLane]) > 0:
                    nextCar = info[opLane][0]
            v = self.execRule(opCar, nextCar, next2Car)
            tempVSaver.append(v)
            tempLocateSaver.append(opCar.locate + v)
            
            endCars = []
            for i in xrange(len(tempVSaver)):
                opCar = self.carBox[lane][i]
                opCar.v = tempVSaver[i]
                opCar.locate = tempLocateSaver[i]
                if opCar.locate >= self.length:
                    endCars.append(opCar)
            
            for opCar in endCars:
                opCar.locate -= self.length
                self.leaveCars[lane] += 1
                #如果出口连接了其他的道路,则自动将离开的车加入其入口
                if self.connectRoad != None:
                    self.connectRoad.addCar(opCar)
                self.carBox[lane].remove(opCar)
                #如果需要自动添加车辆,每离开一辆车就自动在起始初添加一辆车(一般用于入口)
                if self.autoAdderSwitch == True:
                    self.addCar(self.autoAdder)
        self.reflushWaitLine()
        #如果有需要,按时间添加车辆的LOOP
        if self.autoAdderByTime == True:
            if self.autoAddTime == self.timer(get = True):
                self.timer(reset = True)
                self.addCar(self.autoAdder)

    def reflushWaitLine(self):
        opLane = 0
        while(len(self.waitLine) is not 0):
            opCar = self.waitLine[0]
            addCar = copy.deepcopy(opCar)
            if addCar.lane is opLane:
                self.carBox[opLane].insert(0, addCar)
                self.waitLine.remove(opCar)
            elif addCar.lane > self.lanes:
                opLane = np.random.random()*self.lanes
                self.carBox[opLane].insert(0, addCar)
                self.waitLine.remove(opCar)
            else:
                pass

            if opLane < self.lanes:
                opLane += 1
            else:
                opLane = 0

    def changeLane(self, opCar, nextCar):
        dis = self.vmax + opCar.vDistance + opCar.length
        

        #判断是否需要换道
        if self.changeSwitch is False or opCar.lane - 1 < 0 or opCar.lane + 1 >= self.lanes or nextCar is None or nextCar.locate - opCar.locate > dis:
            return False
        insertIndex = 0
        carsLocate = self.getCarsLocate()
        
        # 左道优先
        opLane = opCar.lane - 1
        carsDistance = opCar.locate - carsLocate[opLane]
        carsInBound = carsDistance[abs(carsDistance) <= dis]    
        if carsInBound.size is 0:
            insertIndex = carsDistance.size
            for offset, index in enumerate(carsDistance):
                if offset > 0:
                    insertIndex = index + 1
                    break
            self.carBox[opLane].insert(opCar, insertIndex)
            self.carBox[car.lane].remove(opCar)
            return True
        
        # 右道
        opLane = opCar.lane + 1
        carsDistance = opCar.locate - carsLocate[opLane]
        carsInBound = carsDistance[abs(carsDistance) <= dis]
        if carsInBound.size is 0:
            insertIndex = carsDistance.size
            for offset, index in enumerate(carsDistance):
                if offset > 0:
                    insertIndex = index + 1
                    break
            self.carBox[opLane].insert(opCar, insertIndex)
            self.carBox[car.lane].remove(opCar)
            return True


    def addCar(self, car):
        car = copy.deepcopy(car)    #深复制一个对象(新建一辆车)
        self.enterCars += 1
        self.waitLine.append(car)

    #清空离开道路车辆数的计数
    def reLeave(self):
        self.leaveCars = [0]*self.lanes

    #自动添加车辆(每离开一辆就添加一辆)
    def cycleBoundaryCondition(self, switch, carTemplateBox, pers = None):
        if self.autoAdderByTime != True:
            self.pers = pers
            self.autoAdderSwitch = switch
            self.autoAdder = carTemplateBox
        else:
            print 'Set add car automatic failed,there alreadly existed another mode'

    #按时间间隔添加车辆,与前一个冲突
    def timeBoundaryCondition(self, switch, carTemplateBox, pers = None, timeStep = 1, nums = 1):
        if self.autoAdderSwitch != True:
            self.autoAdderByTime = switch
            self.autoAdder = car
            if timeStep > 0:
                self.autoAddTime = timeStep
            else:
                print 'timeStep must bigger than ZERO'
        else:
            print 'Set add car automatic by time failed,there alreadly existed another mode'

    def setConnectTo(self, road):
        self.connectRoad = road

    #---------------------------------------------------
    def timer(self, get = False,reset = False):
        self.wholeTime += 1
        if get == True:
            return self.timeCounter
        if reset == True:
            self.timeCounter = 0
        else:
            self.timeCounter += 1

    def getNextEnterLane(self):
        number = self.laneFlag
        if number + 1 < self.lanes:
            number += 1
        else:
            number = 0
        return number

class ProcessWriter(object):
    def __init__(self, road, label, plantime):
        self.road = road
        self.label = label
        self.savePath = r'./'+'ProcessInfo_'+label+r'.csv'
        self.setFlag = False
        self.outputFlow = None
        self.plantime = plantime

    def reSetPath(self, path):
        if self.setFlag != True:
            self.savePath = path
        else:
            print 'alreadly init'

    def setInit(self):
        if self.setFlag is not True:
            self.outputFlow = open(self.savePath,'w+')
            self.outputFlow.write('Time Locate V\n')
            self.outputFlow.write(str(self.plantime) + ' ' + str(self.road.getRoadLanes()) + ' ' +
                    str(self.road.getRoadLength()) + '\n')
            self.setFlag = True
        else:
            pass

    def writeInfo(self):
        if self.setFlag is True:
            flag = False
            carBox = self.road.getCarsInfo()
            outputLocate = ''
            outputV = ''
            for lane in carBox:
                if flag is False:
                    flag = True
                else:
                    outputLocate += ':'
                    outputV += ':'
                for i in xrange(len(lane)):
                    outputLocate += (str(round(lane[i].locate, FLOAT_PREC)))
                    outputV += (str(round(lane[i].v, FLOAT_PREC)))
                    if i != len(lane)-1:
                        outputLocate += ','
                        outputV += ','
            #这里的-1只是一个占位符号,并没有实际用处,作用是防止在只有一辆车的时候pandas读取报错
            if outputLocate != '':
                self.outputFlow.write(str(self.road.getExecTime())+' '+'-1,'+outputLocate+' '+'-1,'+outputV+'\n')
        else:
            raise 'write failed'
    def cleanAll(self):
        self.outputFlow.close()

def initEmptyRoad(lanes):
    if lanes <= 0 :
        raise 'InitFailed: lanes must greater than ZERO!'
    output = []
    for i in xrange(lanes):
        output.append([])
    return output

#在指定长度上初始化指定数量的车辆,可以指定分布,默认线性均匀分布
def initCarsDistributed(length, carTemplateBox, carsNum = None, lanes = 1, dis = 'maxium', pers = None):
    output = []
    if length <= 0:
        raise 'InitFailed: Road length must greater than ZERO!'
    if carsNum <= 0 and carsNum is not None:
        raise 'InitFailed: Cars num must greater than ZERO! '

    #if type(carTemplateBox) is not list or type(carTemplateBox[0]) is not type(Car):
    #    raise 'InitFailed: Unkonw car template type'

    # 最密填充
    if dis == 'maxium':
        if len(carTemplateBox) == 1 and pers == None:
            for lane in xrange(lanes):
                adder = 0.0
                temp = []
                while adder <= length:
                    newCar = copy.deepcopy(carTemplateBox[0])
                    newCar.locate = adder
                    adder += (newCar.length + newCar.vDistance)
                    temp.append(newCar)
                output.append(temp)
            return output
        elif len(carTemplateBox) == pers:
            if sum(per) != 1.0:
                raise 'InitFailed:'
            for lane in xrange(lanes):
                adder = 0.0
                temp = []
                while adder <= length:
                    dice = np.random.random()
                    upper = 0.0
                    lower = 0.0
                    for i in xrange(len(pers)):
                        upper += pers[i]
                        if lower <= dice < upper:
                            newCar = copy.deepcopy(carTemplateBox[i])
                            break
                        lower += pers[i]
                    newCar.locate = adder
                    adder += (newCar.length + newCar.vDistance)
                    temp.append(newCar)
                output.append(temp)
        else:
            raise 'InitFailed: '