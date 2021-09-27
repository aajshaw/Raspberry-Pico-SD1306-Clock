# Micro Python

from machine import Pin, I2C
import framebuf
import time
from time import sleep
from ssd1306 import SSD1306_I2C

WIDTH = 128
HEIGHT = 32

i2c = I2C(0)

class Button():
    DEBOUNCE_TIME = 250
    
    def __init__(self, pin, callback):
        self.button = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self.callback = callback
        self.button.irq(trigger = machine.Pin.IRQ_RISING, handler = lambda pin: Button._pressed(self))
        self.pressed_at = 0
        self.checked_at = 0
    
    def _pressed(self):
        now = time.ticks_ms()
        if now > self.pressed_at + Button.DEBOUNCE_TIME:
            self.pressed_at = now
            if self.callback:
                self.callback()
    
    def value(self):
        now = time.ticks_ms()
        if now > self.checked_at + Button.DEBOUNCE_TIME:
            self.checked_at = now
            return self.button.value()
        else:
            return False
            self.pressed_at = now

class Display(SSD1306_I2C):
    FONT_SIZE_1 = 1
    FONT_SIZE_2 = 2
    FONT_SIZE_3 = 3
    FONT_SIZE_4 = 4
    
    def __init__(self, width, height, i2c, addr = 0x3C, external_vcc = False):
        super().__init__(width, height, i2c, addr, external_vcc)
        self.font = [{} for ndx in range(15)]
    
    def clear(self):
        self.fill(0)

    def text(self, s, x, y, color = 1, x_size = 1, y_size = 1):
        if x_size < 1 or x_size > 4:
            raise ValueError('x_size must be greater than 0 and less than 5')
        if y_size < 1 or y_size > 4:
            raise ValueError('y_size must be greater than 0 and less than 5')
        if x_size == 1 and y_size == 1:
            super().text(s, x, y, color)
        else:
            char_ndx = 0
            for t in s:
                fb = self._get_fb_for_character(t, x_size, y_size)
                super().blit(fb, x + (char_ndx * 8 * x_size), y)
                char_ndx += 1

    def _get_fb_for_character(self, c, x_size, y_size):
        fb_dict = self.font[(((y_size - 1) * 4) + (x_size - 1)) - 1]
        if c in fb_dict:
            return fb_dict[c]
        else:
            standard_buffer = bytearray(8)
            standard_fb = framebuf.FrameBuffer(standard_buffer, 8, 8, framebuf.MONO_HLSB)
            standard_fb.text(c, 0, 0)
            
            sized_buffer = bytearray((y_size * 8) * x_size)
            sized_fb = framebuf.FrameBuffer(sized_buffer, 8 * x_size, 8 * y_size, framebuf.MONO_HLSB)
            
            for standard_y in range(8):
                for standard_x in range(8):
                    value = standard_fb.pixel(standard_x, standard_y)
                    for sized_y in range(y_size):
                        for sized_x in range(x_size):
                            sized_fb.pixel((standard_x * x_size) + sized_x, (standard_y * y_size) + sized_y, value)
            
            fb_dict[c] = sized_fb
            return fb_dict[c]
        
    def put_icon(self, frame_buffer, x, y):
        super().blit(frame_buffer, x, y)

    def make_icon(buffer, x_size = 16, y_size = 16, mode = framebuf.MONO_HLSB):
        return framebuf.FrameBuffer(buffer, x_size, y_size, mode)
    
class Clock:
    DISPLAY_SHOW_TIME = 1
    DISPLAY_SET_TIME = 2
    DISPLAY_SETTING_TIME = 3
    DISPLAY_SET_ALARM = 4
    DISPLAY_SETTING_ALARM = 5
    DISPLAY_ALARM_ENABLE = 6
    DISPLAY_ALARM_ENABLING = 7
    DISPLAY_SET_AM_PM_24 = 8
    DISPLAY_SETTING_AM_PM_24 = 9
    
    SET_TIME_NONE = 0
    SET_TIME_HOURS = 1
    SET_TIME_MINUTES = 2
    
    SHOW_TIME_24_HR = 1
    SHOW_TIME_AM_PM = 2

    def __init__(self):
        self.rtc = machine.RTC()
        self.display = Display(WIDTH, HEIGHT, i2c)
        self.display.clear()
        self.display_state = Clock.DISPLAY_SHOW_TIME
        self.display_state_entered_at = time.ticks_ms()
        self.set_time_state = Clock.SET_TIME_NONE
        self.set_time = None
        self.time_mode = Clock.SHOW_TIME_AM_PM
        self.alarm_enabled = False
        self.alarm_time = [0, 0]
        self.alarm_time_match = False
        self.alarm_playing = False
        self.alarm_buzzer = machine.PWM(machine.Pin(15))
        self.alarm_buzzer.freq(1000)
        self.alarm_icon = Display.make_icon(bytearray(b'\x01\x80\x03\xC0\x07\xE0\x0F\xF0\x0F\xF0\x0F\xF0\x0F\xF0\x1F\xF8\x1F\xF8\x3F\xFC\x01\x80\x01\x80'), x_size = 16, y_size = 12)
        self.menu_button = Button(0, self._menu_pressed)
        self.select_button = Button(1, self._select_pressed)
        
    def show(self):
        if self.display_state == Clock.DISPLAY_SHOW_TIME:
            self._show_time()
        elif self.display_state == Clock.DISPLAY_SET_TIME:
            self._set_time()
        elif self.display_state == Clock.DISPLAY_SETTING_TIME:
            self._setting_time()
        elif self.display_state == Clock.DISPLAY_SET_ALARM:
            self._set_alarm()
        elif self.display_state == Clock.DISPLAY_SETTING_ALARM:
            self._setting_alarm()
        elif self.display_state == Clock.DISPLAY_ALARM_ENABLE:
            self._enable_alarm()
        elif self.display_state == Clock.DISPLAY_ALARM_ENABLING:
            self._enabling_alarm()
        elif self.display_state == Clock.DISPLAY_SET_AM_PM_24:
            self._set_am_pm_24()
        elif self.display_state == Clock.DISPLAY_SETTING_AM_PM_24:
            self._setting_am_pm_24()
    
    def _menu_pressed(self):
        if self.display_state == Clock.DISPLAY_SHOW_TIME:
            self._set_display_state(Clock.DISPLAY_SET_TIME)
        elif self.display_state == Clock.DISPLAY_SET_TIME:
            self._set_display_state(Clock.DISPLAY_SET_ALARM)
        elif self.display_state == Clock.DISPLAY_SETTING_TIME:
            if self.set_time_state == Clock.SET_TIME_HOURS:
                self.set_time[4] += 1
                if self.set_time[4] > 23:
                    self.set_time[4] = 0
            elif self.set_time_state == Clock.SET_TIME_MINUTES:
                self.set_time[5] += 1
                if self.set_time[5] > 59:
                    self.set_time[5] = 0
        elif self.display_state == Clock.DISPLAY_SET_ALARM:
            self._set_display_state(Clock.DISPLAY_ALARM_ENABLE)
        elif self.display_state == Clock.DISPLAY_SETTING_ALARM:
            if self.set_time_state == Clock.SET_TIME_HOURS:
                self.alarm_time[0] += 1
                if self.alarm_time[0] > 23:
                    self.alarm_time[0] = 0
            elif self.set_time_state == Clock.SET_TIME_MINUTES:
                self.alarm_time[1] += 1
                if self.alarm_time[1] > 59:
                    self.alarm_time[1] = 0
        elif self.display_state == Clock.DISPLAY_ALARM_ENABLING:
            self.alarm_enabled = not self.alarm_enabled
        elif self.display_state == Clock.DISPLAY_ALARM_ENABLE:
            self._set_display_state(Clock.DISPLAY_SET_AM_PM_24)
        elif self.display_state == Clock.DISPLAY_SET_AM_PM_24:
            self._set_display_state(Clock.DISPLAY_SHOW_TIME)
        elif self.display_state == Clock.DISPLAY_SETTING_AM_PM_24:
            if self.time_mode == Clock.SHOW_TIME_AM_PM:
                self.time_mode = Clock.SHOW_TIME_24_HR
            else:
                self.time_mode = Clock.SHOW_TIME_AM_PM
        else:
            self._set_display_state(Clock.DISPLAY_SHOW_TIME)
    
    def _set_display_state(self, new_state):
        self.display_state_entered_at = time.ticks_ms()
        self.display_state = new_state
    
    def _select_pressed(self):
        if self.display_state == Clock.DISPLAY_SHOW_TIME:
            if self.alarm_playing:
                self.alarm_playing = False
        elif self.display_state == Clock.DISPLAY_SET_TIME:
            self._set_display_state(Clock.DISPLAY_SETTING_TIME)
            self.set_time = list(self.rtc.datetime())
            self._update_time_set_state()
        elif self.display_state == Clock.DISPLAY_SETTING_TIME:
            self._update_time_set_state()
        elif self.display_state == Clock.DISPLAY_SET_ALARM:
            self._set_display_state(Clock.DISPLAY_SETTING_ALARM)
            self._update_alarm_set_state()
        elif self.display_state == Clock.DISPLAY_SETTING_ALARM:
            self._update_alarm_set_state()
        elif self.display_state == Clock.DISPLAY_ALARM_ENABLE:
            self._set_display_state(Clock.DISPLAY_ALARM_ENABLING)
        elif self.display_state == Clock.DISPLAY_ALARM_ENABLING:
            self._set_display_state(Clock.DISPLAY_SHOW_TIME)
        elif self.display_state == Clock.DISPLAY_SET_AM_PM_24:
            self._set_display_state(Clock.DISPLAY_SETTING_AM_PM_24)
        elif self.display_state == Clock.DISPLAY_SETTING_AM_PM_24:
            self._set_display_state(Clock.DISPLAY_SHOW_TIME)
    
    def _test_alarm_time(self, hours, minutes, ms):
        if self.alarm_enabled:
            if not self.alarm_time_match:
                if hours == self.alarm_time[0] and minutes == self.alarm_time[1]:
                    self.alarm_time_match = True
                    self.alarm_playing = True
            else:
                if not (hours == self.alarm_time[0] and minutes == self.alarm_time[1]):
                    self.alarm_time_match = False
                    self.alarm_playing = False
            if self.alarm_playing and ms % 1000 < 500:
                self.alarm_buzzer.duty_u16(32767)
            else:
                self.alarm_buzzer.duty_u16(0)
                
    def _build_time_display(self, hours, minutes, show_hours = True, show_minutes = True, show_colon = True):
        if show_hours:
            if self.time_mode == Clock.SHOW_TIME_24_HR:
                display_time = '{:02n}'.format(hours)
            else:
                # Allow midnight + 15 minutes to show as 00:15 and mid-day + 15 to show as 12:15
                if hours < 13:
                    display_time = '{:02n}'.format(hours)
                else:
                    display_time = '{:02n}'.format(hours - 12)
        else:
            display_time = '  '
            
        if show_colon:
            display_time += ':'
        else:
            display_time += ' '
        
        if show_minutes:
            display_time += '{:02n}'.format(minutes)
        else:
            display_time += '  '

        self.display.text(display_time, 0, 0, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_4)

        if self.time_mode == Clock.SHOW_TIME_24_HR:
            self.display.text('24 hr', 80, 24)
        elif self.time_mode == Clock.SHOW_TIME_AM_PM:
            if hours >= 12:
                self.display.text('PM', 80, 24)
            else:
                self.display.text('AM', 80, 24)
    
    def _show_time(self):
        ms = time.ticks_ms()
        (year, month, day, weekday, hours, minutes, seconds, subseconds) = self.rtc.datetime()
        
        self._test_alarm_time(hours, minutes, ms)
                
        self.display.clear()
        self._build_time_display(hours, minutes, show_colon = (ms % 1000 < 500))
        
        if self.alarm_enabled:
            self.display.put_icon(self.alarm_icon, 96, 4)
        self.display.show()
    
    def _set_time(self):
        self.display.clear()
        self.display.text('Set', 40, 0, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
        self.display.text('Time', 32, 16, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
        self.display.show()
    
    def _setting_time(self):
        while self.display_state == Clock.DISPLAY_SETTING_TIME:
            self.display.clear()
            offset = time.ticks_ms() - self.display_state_entered_at
            if offset % 1000 < 500:
                self._build_time_display(self.set_time[4], self.set_time[5])
            else:
                self._build_time_display(self.set_time[4], self.set_time[5], show_hours = not self.set_time_state == Clock.SET_TIME_HOURS, show_minutes = not self.set_time_state == Clock.SET_TIME_MINUTES)
            self.display.show()
            
    def _update_time_set_state(self):
        if self.set_time_state == Clock.SET_TIME_NONE:
            self.set_time_state = Clock.SET_TIME_HOURS
        elif self.set_time_state == Clock.SET_TIME_HOURS:
            self.set_time_state = Clock.SET_TIME_MINUTES
        elif self.set_time_state == Clock.SET_TIME_MINUTES:
            self.set_time_state = Clock.SET_TIME_NONE
            self._set_display_state(Clock.DISPLAY_SHOW_TIME)
            self.set_time[6] = 0
            self.set_time[7] = 0
            self.rtc.datetime(tuple(self.set_time))
    
    def _set_alarm(self):
        self.display.clear()
        self.display.text('Set', 40, 0, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
        self.display.text('Alarm', 24, 16, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
        self.display.show()

    def _setting_alarm(self):
        while self.display_state == Clock.DISPLAY_SETTING_ALARM:
            self.display.clear()
            offset = time.ticks_ms() - self.display_state_entered_at
            if offset % 1000 < 500:
                self._build_time_display(self.alarm_time[0], self.alarm_time[1])
            else:
                self._build_time_display(self.alarm_time[0], self.alarm_time[1], show_hours = not self.set_time_state == Clock.SET_TIME_HOURS, show_minutes = not self.set_time_state == Clock.SET_TIME_MINUTES)
            self.display.show()

    def _update_alarm_set_state(self):
        if self.set_time_state == Clock.SET_TIME_NONE:
            self.set_time_state = Clock.SET_TIME_HOURS
        elif self.set_time_state == Clock.SET_TIME_HOURS:
            self.set_time_state = Clock.SET_TIME_MINUTES
        elif self.set_time_state == Clock.SET_TIME_MINUTES:
            self.set_time_state = Clock.SET_TIME_NONE
            self._set_display_state(Clock.DISPLAY_SHOW_TIME)
    
    def _enable_alarm(self):
        self.display.clear()
        self.display.text('Enable', 16, 0, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
        self.display.text('Alarm', 24, 16, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
        self.display.show()
    
    def _enabling_alarm(self):
        while self.display_state == Clock.DISPLAY_ALARM_ENABLING:
            offset = time.ticks_ms() - self.display_state_entered_at
            self.display.clear()
            self.display.text('Alarm', 24, 0, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
            if offset % 1000 < 500:
                if self.alarm_enabled:
                    self.display.text('On', 48, 16, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
                else:
                    self.display.text('Off', 40, 16, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
            self.display.show()
    
    def _set_am_pm_24(self):
        self.display.clear()
        self.display.text('Set', 40, 0, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
        self.display.text('AM-PM/24 Hr', 20, 16, x_size = Display.FONT_SIZE_1, y_size = Display.FONT_SIZE_2)
        self.display.show()

    def _setting_am_pm_24(self):
        while self.display_state == Clock.DISPLAY_SETTING_AM_PM_24:
            offset = time.ticks_ms() - self.display_state_entered_at
            self.display.clear()
            self.display.text('AM-PM/24 Hr', 20, 0, x_size = Display.FONT_SIZE_1, y_size = Display.FONT_SIZE_2)
            if offset % 1000 < 500:
                if self.time_mode == Clock.SHOW_TIME_AM_PM:
                    self.display.text('AM/PM', 24, 16, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
                else:
                    self.display.text('24 Hr', 24, 16, x_size = Display.FONT_SIZE_2, y_size = Display.FONT_SIZE_2)
            self.display.show()

clock = Clock()

while True:
    clock.show()
    