import RPi.GPIO as GPIO
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QLCDNumber, QMessageBox
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal

# Global Configuration
# GPIO Relay ทั้งหมด Active LOW เพื่อเริ่มทำงาน
CFG_REPAY = [5, 6, 13, 16, 19, 20, 21, 26] # สำหรับควบคุมมอเตอร์รางสินค้า (1 relay ต่อ 1 ราง หรือตามการออกแบบ)

# Button ทั้งหมด กด สั่งงาน Relay ด้วยปุ่ม
CFG_BUTTON = [27, 22, 9, 10, 11]


BTN_INFO = {}
RELAY_INFO = {}
ii = 0
for i in range(8):
    RELAY_INFO[i] = CFG_REPAY[i]

for i in range(5):
    BTN_INFO[CFG_BUTTON[i]] = i



# เซ็นเซอร์นับรอบการขายสินค้าแบบตก
ACTIVE_LED_PIN = 25 # สัมผัสถึงการหมุนครบ 1 รอบ

# เซ็นเซอร์เครื่องเหรียญ
SENSOR_COIN = 12

# Product Information (ตัวอย่าง)
PRODUCTS = {
    1: {"name": "Cola", "price": 15, "relay_pin": CFG_REPAY[0]},
    2: {"name": "Water", "price": 10, "relay_pin": CFG_REPAY[1]},
    3: {"name": "Snack", "price": 20, "relay_pin": CFG_REPAY[2]},
    4: {"name": "Coffee", "price": 25, "relay_pin": CFG_REPAY[3]},
    5: {"name": "Milk", "price": 30, "relay_pin": CFG_REPAY[4]},
}


RUNNING_ID = None
selected_product_id = None

rotation_sensor_last = None

clickBtn = 0
def button_callback(channel):
   global clickBtn
   currnet_time = time.time()
   print("calbtn",currnet_time,clickBtn)
   clickBtn = currnet_time

   print(BTN_INFO[channel])
   print(RELAY_INFO[BTN_INFO[channel]])
   #activate_relay(RELAY_INFO[BTN_INFO[channel]])
   print("Start",RELAY_INFO[BTN_INFO[channel]])

def rotation_sensor_callback(channel) :
    global rotation_sensor_last,RUNNING_ID,selected_product_id
    if RUNNING_ID == None :
      return True
    else :
      current_state = GPIO.input(channel)
      if current_state == 0 and rotation_sensor_last == 1 :
         GPIO.output(RUNNING_ID,GPIO.HIGH)
         rotation_sensor_last = None
         RUNNING_ID = None
         print("Close Relay")
         return False

      rotation_sensor_last = current_state
    print("Callback",selected_product_id,RUNNING_ID,rotation_sensor_last,current_state)

def coin_callback(channel) :
   coin_current_state = GPIO.input(channel)
   print("coin_callback",channel,coin_current_state)

# --- GPIO Setup ---
def setup_gpio():

    GPIO.setmode(GPIO.BCM) # ใช้โหมด BCM (หมายเลข GPIO)
    # Setup Relays (Active LOW)
    for pin in CFG_REPAY:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH) # ตั้งค่าเริ่มต้นเป็น HIGH เพื่อปิด Relay

 
    # Setup Buttons with Pull-up resistors
    for pin in CFG_BUTTON:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(pin, GPIO.FALLING, callback=button_callback, bouncetime=10)
    # Setup Coin Sensor
    GPIO.setup(SENSOR_COIN, GPIO.IN, pull_up_down=GPIO.PUD_UP) # สมมติว่า Active LOW เมื่อมีเหรียญ
    GPIO.add_event_detect(SENSOR_COIN, GPIO.FALLING, callback=coin_callback, bouncetime=1)

    # Setup Rotation Sensor
    GPIO.setup(ACTIVE_LED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(ACTIVE_LED_PIN, GPIO.BOTH, callback=rotation_sensor_callback, bouncetime=1) # bouncetime อาจต้องปรับ

# --- GPIO Control Functions ---
def activate_relay(pin):
    global RUNNING_ID
    RUNNING_ID = pin
    print(f"Activating relay on GPIO {pin} (LOW)")
    GPIO.output(pin, GPIO.LOW) # Active LOW
    checkLoop = 0
    while True :
       if RUNNING_ID == None :
          GPIO.output(pin, GPIO.HIGH)
          break
       if checkLoop >= 5 :
          break
       checkLoop =+1
       time.sleep(1)
    # Relay ควรจะ Active LOW เพียงชั่วขณะหนึ่งเพื่อให้มอเตอร์หมุน 1 รอบ
    # คุณอาจจะต้องหน่วงเวลาหรือรอสัญญาณจากเซ็นเซอร์ ACTIVE_LED_PIN
    # สำหรับการควบคุมมอเตอร์ อาจจะต้องใช้ PWM หรือ H-bridge ร่วมด้วย
    # สำหรับตู้หยอดเหรียญทั่วไป มอเตอร์จะหมุน 1 รอบแล้วหยุดเอง หรือคุณต้องควบคุมเวลา
    # ถ้ามอเตอร์เป็นแบบ pulse เดียวจบ ก็แค่ low สั้นๆ แล้ว high กลับ
    # ถ้ามอเตอร์เป็นแบบต้องจ่ายไฟค้าง คุณต้องรอเซ็นเซอร์แล้วค่อยสั่ง high กลับ
    #time.sleep(5) # ตัวอย่าง: เปิดค้างไว้ 0.5 วินาที
    #
    
# --- GPIO Control Functions ---

def stop_relay(pin):
    global RUNNING_ID
    RUNNING_ID = None
    GPIO.output(pin, GPIO.HIGH) # ปิด Relay กลับ (HIGH)
    print(f"Deactivating relay on GPIO {pin} (HIGH)")


# --- Thread สำหรับตรวจสอบเซ็นเซอร์เหรียญ (Non-blocking) ---
class CoinSensorThread(QThread):
    coin_inserted = pyqtSignal(int) # ส่งสัญญาณเมื่อตรวจพบเหรียญ (อาจจะส่งค่าเหรียญ)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.last_state = GPIO.input(SENSOR_COIN) # สถานะเริ่มต้นของเซ็นเซอร์

    def run(self):
        while self.running:
            current_state = GPIO.input(SENSOR_COIN)
            if current_state != self.last_state:
                if current_state == GPIO.LOW: # ตรวจจับการเปลี่ยนแปลงจาก HIGH ไป LOW (ถ้าเป็น Active LOW)
                    print("Coin detected!")
                    # ในระบบจริง คุณต้องมีวงจรสำหรับนับ/แยกชนิดเหรียญ
                    # สมมติว่า 1 เหรียญที่ตรวจจับได้คือ 10 บาท (ตัวอย่าง)
                    self.coin_inserted.emit(10)
                self.last_state = current_state
            time.sleep(0.05) # ตรวจสอบทุกๆ 50ms

    def stop(self):
        self.running = False
        self.wait() # รอให้ thread ทำงานเสร็จก่อนปิด

class RotationSensorThread(QThread):
    rotation_completed = pyqtSignal(int) # ส่งสัญญาณเมื่อหมุนครบ 1 รอบ (อาจจะส่ง Product ID ที่เกี่ยวข้อง)
    # เพิ่มสัญญาณแจ้งเมื่อตรวจพบ HIGH เพื่อแสดงว่าเริ่มหมุนแล้ว (ไม่บังคับ แต่มีประโยชน์ในการ debug)
    rotation_started = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.waiting_for_rotation = False
        self.product_id_on_rotation = -1
        self.has_seen_high = False # Flag เพื่อตรวจสอบว่าเคยเห็น HIGH แล้วหรือยัง

    def set_wait_for_rotation(self, product_id):
        self.waiting_for_rotation = True
        self.product_id_on_rotation = product_id
        self.has_seen_high = False # รีเซ็ตสถานะเมื่อเริ่มรอการหมุนใหม่
        print(f"Waiting for rotation for product ID: {product_id}. Expecting HIGH then LOW.")
        # อ่านสถานะเริ่มต้นของเซ็นเซอร์เมื่อเริ่มรอ เพื่อไม่ให้พลาดขอบแรก
        # GPIO.input(ACTIVE_LED_PIN) # ไม่ต้องเก็บ last_state ใน thread เพราะจะตรวจสอบขอบโดยตรง

    def run(self):
        while self.running:
            if self.waiting_for_rotation:
                current_state = GPIO.input(ACTIVE_LED_PIN)
                if not self.has_seen_high and current_state == GPIO.HIGH:
                    # ตรวจพบสถานะ HIGH เป็นครั้งแรกหลังเริ่มรอ
                    self.has_seen_high = True
                    print(f"Rotation started (HIGH detected) for product {self.product_id_on_rotation}")
                    self.rotation_started.emit(self.product_id_on_rotation) # ส่งสัญญาณว่าเริ่มหมุน
                elif self.has_seen_high and current_state == GPIO.LOW:
                    # ตรวจพบสถานะ LOW หลังจากเคยเห็น HIGH มาแล้ว
                    print(f"Rotation completed (LOW detected after HIGH) for product {self.product_id_on_rotation}!")
                    self.waiting_for_rotation = False # หยุดรอการหมุนสำหรับสินค้านี้
                    self.has_seen_high = False # รีเซ็ตสำหรับรอบถัดไป
                    self.rotation_completed.emit(self.product_id_on_rotation)
                    #GPIO.output(RUNNING_ID, GPIO.HIGH) # ปิด Relay กลับ (HIGH)
            time.sleep(0.01) # ตรวจสอบถี่ขึ้นเพื่อจับขอบได้ดีขึ้น

    def stop(self):
        self.running = False
        self.wait()


current_credit = 100

# --- GUI Application ---
class VendingMachineApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vending Machine")
        self.setGeometry(0, 0, 800, 480) # ขนาดจอ 800x480
        self.current_credit = current_credit
        self.selected_product_id = None
        self.init_ui()
        self.init_gpio_threads()

    def init_ui(self):
        layout = QVBoxLayout()

        # Credit Display
        self.credit_label = QLabel(f"Credit: {self.current_credit} THB")
        self.credit_label.setAlignment(Qt.AlignCenter)
        self.credit_label.setStyleSheet("font-size: 36px; font-weight: bold; color: green;")
        layout.addWidget(self.credit_label)

        # Product Buttons
        product_button_layout = QVBoxLayout()
        self.product_buttons = {}
        for product_id, product_info in PRODUCTS.items():
            btn = QPushButton(f"{product_info['name']} ({product_info['price']} THB)")
            btn.setFixedSize(700, 80) # ปุ่มใหญ่ขึ้นสำหรับจอสัมผัส
            btn.setStyleSheet("font-size: 30px;")
            btn.clicked.connect(lambda _, pid=product_id: self.select_product(pid))
            self.product_buttons[product_id] = btn
            product_button_layout.addWidget(btn)
        layout.addLayout(product_button_layout)

        # Status Message
        self.status_label = QLabel("Please insert coins or select a product.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 24px; color: blue;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def init_gpio_threads(self):
        # Initialize Coin Sensor Thread
        self.coin_thread = CoinSensorThread()
        self.coin_thread.coin_inserted.connect(self.add_credit)
        self.coin_thread.start()

        # Initialize Rotation Sensor Thread
        self.rotation_thread = RotationSensorThread()
        self.rotation_thread.rotation_completed.connect(self.product_delivered)
        self.rotation_thread.start()


    def add_credit(self, amount):
        self.current_credit += amount
        self.credit_label.setText(f"Credit: {self.current_credit} THB")
        self.status_label.setText(f"Credit added: {amount} THB. Total: {self.current_credit} THB")

    def select_product(self, product_id):
        self.selected_product_id = product_id
        product = PRODUCTS.get(product_id)
        if not product:
            self.status_label.setText("Invalid product selected.")
            return

        self.status_label.setText(f"Selected: {product['name']}. Price: {product['price']} THB")
        if self.current_credit >= product['price']:
            #reply = QMessageBox.question(self, 'Confirm Purchase',
            #                             f"Buy {product['name']} for {product['price']} THB?",
            #                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            #if reply == QMessageBox.Yes:
            self.dispense_product(product_id)
            #else:
            #    self.status_label.setText("Purchase cancelled.")
            #    self.selected_product_id = None
        else:
            self.status_label.setText(f"Insufficient credit. Need {product['price'] - self.current_credit} THB more.")

    def dispense_product(self, product_id):
        product = PRODUCTS.get(product_id)
        if not product:
            return

        self.current_credit -= product['price']
        self.credit_label.setText(f"Credit: {self.current_credit} THB")
        self.status_label.setText(f"Dispensing {product['name']}...")
        self.rotation_thread.set_wait_for_rotation(product_id)

        self.relay_activation_thread = RelayActivationThread(product['relay_pin'])
        self.relay_activation_thread.finished.connect(lambda: print(f"Relay {product['relay_pin']} activation finished."))
        self.relay_activation_thread.start()


    def product_delivered(self, product_id):
        # This slot is called when rotation_thread emits rotation_completed
        product = PRODUCTS.get(product_id)
        if product:
            self.status_label.setText(f"'{product['name']}' delivered! Thank you!")
        else:
            self.status_label.setText("Product delivered! Thank you!")
        self.selected_product_id = None
        # Optionally, you can give change here if current_credit > 0

    def closeEvent(self, event):
        # Stop threads gracefully when the application closes
        if hasattr(self, 'coin_thread') and self.coin_thread.isRunning():
            self.coin_thread.stop()
        if hasattr(self, 'rotation_thread') and self.rotation_thread.isRunning():
            self.rotation_thread.stop()
        GPIO.cleanup()
        super().closeEvent(event)

# A simple thread for activating relay
class RelayActivationThread(QThread):
    def __init__(self, pin):
        super().__init__()
        self.pin = pin

    def run(self):
        activate_relay(self.pin)


if __name__ == '__main__':
    setup_gpio() # จำเป็นต้องเรียก setup_gpio ก่อน
    app = QApplication([])
    window = VendingMachineApp()
    window.showMaximized() # แสดงผลเต็มหน้าจอ
    app.exec_()

