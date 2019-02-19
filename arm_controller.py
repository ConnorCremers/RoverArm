
from __future__ import division

from UDPComms import Subscriber, timeout
from roboclaw_interface import RoboClaw
import math
import time


FIRST_LINK = 457.2
SECOND_LINK = 457.2

# native angles = 0 at extension

def find_serial_port():
    return '/dev/serial0'
    return '/dev/tty.usbmodem1411'
    return '/dev/ttyUSB0'
    return '/dev/ttyACM0'
    return '/dev/tty.usbmodem1141'

class Arm:
    def __init__(self):
        self.target_vel = Subscriber(8410)

        self.xyz_names = ["x", "y", "yaw", "pitch"]

        self.motor_names = ["shoulder", "elbow", "yaw", "pitch"]

        self.native_positions = { motor:0 for motor in self.motor_names}
        self.CPR = {'shoulder': 10.4 * 1288.848, 
                    'elbow'   :-10.4 * 921.744,
                    'yaw'     : float(48)/28 * 34607 ,
                    'pitch'   : 2 * 34607}

        # self.CPR = { 'shoulder': 10, 'elbow':10}
        self.SPEED_SCALE = 0.5

        self.rc = RoboClaw(find_serial_port(), names = self.motor_names, addresses = [128, 129] ) # addresses = [128, 129, 130])


        try:
            while 1:
                start_time = time.time()
                self.update()
                while (time.time() - start_time) < 0.1:
                    pass
        except KeyboardInterrupt:
            self.send_speeds( {motor: 0 for motor in self.motor_names} )
            raise
        except:
            self.send_speeds( {motor: 0 for motor in self.motor_names} )
            raise

    def send_speeds(self, speeds):
        for motor in self.motor_names:
            #print('driving', motor, 'at', int(self.SPEED_SCALE * self.CPR[motor] * speeds[motor]))
            self.rc.drive_speed(motor, int(self.SPEED_SCALE * self.CPR[motor] * speeds[motor]))

    def get_location(self, locs):
        for i,motor in enumerate(self.motor_names):
            self.native_positions[motor] = 2 * math.pi * self.rc.read_encoder(motor)[1]/self.CPR[motor]
            # self.native_positions[motor] = 2 * math.pi * locs[i]

        self.xyz_positions = self.native_to_xyz(self.native_positions)
        print("Current Native: ", self.native_positions)
        print("Current    XYZ: ", self.xyz_positions)

    def xyz_to_native(self, xyz):
        native = {}

        distance = math.sqrt(xyz['x']**2 + xyz['y']**2)
        angle = math.atan2(xyz['x'], xyz['y'])

        offset = math.acos( ( FIRST_LINK**2 + distance**2 - SECOND_LINK**2  ) / (2*distance * FIRST_LINK) )
        inside = math.acos( ( FIRST_LINK**2 + SECOND_LINK**2 - distance**2  ) / (2*SECOND_LINK * FIRST_LINK) )

        native['shoulder'] = angle + offset
        native['elbow']    = - (math.pi - inside) 

        native['yaw']      = xyz['yaw']  + native['shoulder'] - native['elbow']
        native['pitch']    = xyz['pitch']

        return native

    def native_to_xyz(self, native):
        xyz = {}
        xyz['x'] = FIRST_LINK * math.sin(native['shoulder']) + SECOND_LINK * math.sin(native['shoulder'] + native['elbow'])
        xyz['y'] = FIRST_LINK * math.cos(native['shoulder']) + SECOND_LINK * math.cos(native['shoulder'] + native['elbow'])

        xyz['yaw'] =  native['yaw']  - native['shoulder'] + native['elbow'] 
        xyz['pitch']    = native['pitch']
        return xyz

    def dnative(self, dxyz):
        x = self.xyz_positions['x']
        y = self.xyz_positions['y']

        shoulder_diff_x = y/(x**2 + y**2) - (x/(FIRST_LINK*math.sqrt(x**2 + y**2)) - x*(FIRST_LINK**2 - SECOND_LINK**2 + x**2 + y**2)/(2*FIRST_LINK*(x**2 + y**2)**(3/2)))/math.sqrt(1 - (FIRST_LINK**2 - SECOND_LINK**2 + x**2 + y**2)**2/(4*FIRST_LINK**2*(x**2 + y**2)))

        shoulder_diff_y = -x/(x**2 + y**2) - (y/(FIRST_LINK*math.sqrt(x**2 + y**2)) - y*(FIRST_LINK**2 - SECOND_LINK**2 + x**2 + y**2)/(2*FIRST_LINK*(x**2 + y**2)**(3/2)))/math.sqrt(1 - (FIRST_LINK**2 - SECOND_LINK**2 + x**2 + y**2)**2/(4*FIRST_LINK**2*(x**2 + y**2)))

        elbow_diff_x = -x/(FIRST_LINK*SECOND_LINK*math.sqrt(1 - (FIRST_LINK**2 + SECOND_LINK**2 - x**2 - y**2)**2/(4*FIRST_LINK**2*SECOND_LINK**2)))

        elbow_diff_y = -y/(FIRST_LINK*SECOND_LINK*math.sqrt(1 - (FIRST_LINK**2 + SECOND_LINK**2 - x**2 - y**2)**2/(4*FIRST_LINK**2*SECOND_LINK**2)))

        dnative = {}
        dnative['shoulder'] = shoulder_diff_x * dxyz['x'] + shoulder_diff_y * dxyz['y'] 
        dnative['elbow']    = elbow_diff_x    * dxyz['x']    + elbow_diff_y * dxyz['y'] 

        print("Dxyz   : ", dxyz)
        print("Dnative: ", dnative)
        print("new location: ", self.native_to_xyz ( {motor:dnative[motor] + self.native_positions[motor] for motor in self.motor_names}) )
        return dnative

    def dnative2(self, dxyz):
        h = 0.00000001
       # print dxyz, self.xyz_positions
        x_plus_h = { axis:self.xyz_positions[axis] + h*dxyz[axis] for axis in self.xyz_names}

        f_x_plus_h = self.xyz_to_native(x_plus_h)
        f_x        = self.xyz_to_native(self.xyz_positions)

        dnative = {motor:(f_x_plus_h[motor] - f_x[motor])/h for motor in self.motor_names}



        print("Dxyz   : ", dxyz)
        print("Dnative: ", dnative)
        print("new location: ", self.native_to_xyz ( {motor:dnative[motor] + f_x[motor] for motor in self.motor_names}) )
        return dnative


    def update(self):
        print()
        print("new iteration")
        self.get_location([ -0.01, 0] )

        try:
            target = self.target_vel.get()
            target = {bytes(key): value for key, value in target.iteritems()}
            # targt = [0,-0.1]

            speeds = self.dnative2(target)

            print "SPEEDS", speeds

        except timeout:
            speeds = {motor: 0 for motor in self.motor_names}
        except:
            speeds = {motor: 0 for motor in self.motor_names}
            raise
        finally:
            zero = {motor: 0 for motor in self.motor_names}
            self.send_speeds(speeds)
        # exit()




if __name__ == "__main__":
    a = Arm()
