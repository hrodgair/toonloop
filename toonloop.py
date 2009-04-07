#!/usr/bin/env python
#
# ToonLoop for Python
#
# Copyright 2008 Alexandre Quessy & Tristan Matthews
# <alexandre@quessy.net> & <le.businessman@gmail.com>
# http://www.toonloop.com
#
# Original idea by Alexandre Quessy
# http://alexandre.quessy.net
#
# ToonLoop is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ToonLoop is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the gnu general public license
# along with ToonLoop.  If not, see <http://www.gnu.org/licenses/>.
#

"""
ToonLoop is a realtime stop motion performance tool. 

The idea is to spread its use for teaching new medias to children and to 
give a professional tool for movie creators.

In the left window, you can see what is seen by the live camera.
In the right window, it is the result of the stop motion loop.

Usage :
 - Press the SPACE bar to grab a frame.
 - Press DELETE or BACKSPACE to delete the last frame.
 - Press 'r' to reset and start the current sequence. (an remove all its frames)
 - Press 's' to save the current sequence as a QuickTime movie.
 - Press 'i' to print current loop frame number, number of frames in loop 
   and global framerate.
 - Press 'h' to print a help message.
 - Press UP to increase frame rate.
 - Press DOWN to decrease frame rate.
 - Press 'a' to toggle on/off the auto recording. 
   (it records one frame on every frame) It is an intervalometer.
   Best used to create timelapse sequences automatically.
 - Press 'k' or 'j' to increase or decrease the auto rate.

INSTALLATION NOTES : 
The camera module for pygame is available from pygame's svn revision 
1744 or greater
svn co svn://seul.org/svn/pygame/trunk
"""
# TODO:
# - Press numbers from 0 to 9 to switch to an other sequence.
# - Press 'p' to open the Quicktime video camera settings dialog. (if available)
# - Press LEFT or RIGHT to move the insertion point
# - OSC messages to set intervalometer rate (timelapse) and enable it.
# - onion peal
# - text for frame number on both sides
# - OSC callbacks and sends

import sys
from time import strftime
import os

from toon import opensoundcontrol
from toon import mencoder
from rats import render

import pygame
import pygame.camera
from pygame.locals import *
from pygame import time

from twisted.internet import reactor

__version__ = "1.0.2 alpha"


class ToonSequence(object):
    """
    ToonLoop sequence. 

    A sequence is made of many shots.
    
    An act include one or more sequences; sequences comprise one or more scenes; 
    and scenes may be thought of as being built out of shots (if one is thinking visually) 
    or beats (if one is thinking in narrative terms).
    """
    # TODO: translate, rotate
    # animate, pause... 
    # keyframe, interpolate
    # tween
    pass

class ToonShot(object):
    """
    ToonLoop shot.

    A shot is a serie of frames. 
    """
    def __init__(self, fps=12):
        self.writehead = 0
        self.playhead = 0
        self.frames = []
        self.fps = fps

    def reset(self):
        pass

    def delete_frame(self):
        pass

    def add_frame(self):
        pass

    def next_frame(self):
        pass

#  int captureFrameNum = 0; //the next captured frame number ... might wrap around
#  int playFrameNum = 0;
#  PImage[] images = new PImage[LOOP_MAX_NUM_FRAME];
#  int seqFrameRate = FRAME_RATE;
#  int getFrameRate() 

class ToonLoopError(Exception):
    """
    Any error ToonLoop might encouter
    """
    pass

class ToonLoop(render.Game):
    """
    ToonLoop is a realtime stop motion tool.
    """
    def __init__(self, **argd):
        """
        Startup poutine.
        """
        self.img_width = 640
        self.height = 480 
        self.last_image = pygame.Surface((self.img_width, self.height))
        self.running = True
        self.paused = False
        pygame.display.set_caption("ToonLoop")
        self.video_device = 0 
        self.__dict__.update(**argd) # overrides some attributes whose defaults and names are below

        if os.uname()[0] == 'Darwin':
            self.is_mac = True
        else:
            self.is_mac = False
        self.width = self.img_width * 2
        self.size = (self.width, self.height)
        self.surface = pygame.display.set_mode(self.size)
        try:
            pygame.camera.init() 
        except Exception, e:
            print "error calling pygame.camera.init()", e.message
            print sys.exc_info()
            raise ToonLoopError("Error initializing the video camera. %s" % (e.message))
        try:
            print "cameras :", pygame.camera.list_cameras()
            if self.is_mac:
                self.camera = pygame.camera.Camera(self.video_device, (self.img_width, self.height))
            else:
                self.camera = pygame.camera.Camera("/dev/video%d" % (self.video_device), (self.img_width, self.height))
            self.camera.start()
        except SystemError, e:
            print sys.exc_info()
            raise ToonLoopError("Invalid camera. %s" % (str(e.message)))
        except Exception, e:
            print sys.exc_info()
            raise ToonLoopError("Invalid camera. %s" % (str(e.message)))
        self.clock = pygame.time.Clock()
        self.fps = 0 # for statistics
        self.image_list = []
        self.image_idx = 0
        self.renderer = None # Twisted Renderer instance that owns it.
        self.auto_enabled = False
        self.auto_rate = 3.0 # in seconds
        self.auto_delayed_id = None
        self.osc = opensoundcontrol.ToonOsc(self)

    def get_and_flip(self):
        """
        Image capture from the video camera and pygame pixels update.
        """
        if self.is_mac:
            self.camera.get_image(self.last_image)
        else:
            self.last_image = self.camera.get_image()
        self.surface.blit(self.last_image, (0, 0))
        if len(self.image_list) > self.image_idx:
            self.surface.blit(self.image_list[self.image_idx], (self.img_width, 0))
            self.image_idx += 1
        else:
            self.image_idx = 0
        pygame.display.update()

    def toggle_auto(self):
        """
        Toggles on/off the auto mode
        """
        self.auto_enabled = not self.auto_enabled
        if self.auto_enabled:
            self.auto_delayed_id = reactor.callLater(0, self.auto_grab)
            print "enabled intervalometer"
        elif self.auto_delayed_id.active():
            self.auto_delayed_id.cancel()
            print "disabled intervalometer"

        # self.auto_enabled = False
        # self.auto_rate = 3.0 # in seconds
        # self.auto_delayed_id = None
    
    def increment_auto_rate(self, dir=1):
        """
        Increase or decreases the intervalometer rate. (in seconds)
        :param dir: by how much increment it.
        """
        will_be = self.auto_rate + dir
        if will_be > 0 and will_be <= 60:
            self.auto_rate = will_be
            print "auto rate:", will_be

    def auto_grab(self):
        """
        Called when it is time to utomatically grab an image.

        The auto mode is like an intervalometer to create timelapse animations.
        """
        # self.get_and_flip()
        self.grab_image()
        sys.stdout.write("grab ")
        sys.stdout.flush()
        if self.auto_enabled:
            self.auto_delayed_id = reactor.callLater(self.auto_rate, self.auto_grab)


    def grab_image(self):
        """
        Copies the last grabbed to the list of images.
        """
        if self.is_mac:
            self.image_list.append(self.last_image.copy())
        else:
            self.image_list.append(self.last_image)

    def pause(self):
        """
        Toggles on/off the pause
        """
        self.paused = not self.paused

    def reset_loop(self):
        """
        Deletes all frames from the current animation
        """
        self.image_list = []
        self.reset_playback_window()

    def save_images(self):
        """
        Saves all images as jpeg
        """
        # TODO : in a thread or using reactor.callLater()
        datetime = strftime("%Y-%m-%d_%Hh%Mm%S")
        print "Saving images ", datetime, " " 
        reactor.callLater(0, self._save_next_image, datetime, 0)

    def _save_next_image(self, datetime, index):
        """
        Saves each image using twisted in order not to freeze the app.
        """
        if index < len(self.image_list):
            name = ("%s_%4d.jpg" % (datetime, index)).replace(' ', '0')
            sys.stdout.write("%d " % index)
            pygame.image.save(self.image_list[index], name)
            reactor.callLater(0, self._save_next_image, datetime, index + 1)
        else:
            print "\nConverting to mjpeg" # done
            filename_pattern = "%s_" % (datetime)
            path = os.getcwd()
            fps = self.renderer.desired_fps 
            deferred = mencoder.jpeg_to_movie(filename_pattern, path, fps)

    def pop_one_frame(self):
        """
        Deletes the last frame from the current list of images.
        """
        if self.image_list != []:
            self.image_list.pop()
            if self.image_list == []:
                self.reset_playback_window()

    def reset_playback_window(self):
        """
        Sets all pixels of the window as black.
        """
        blank_surface = pygame.Surface((self.img_width, self.height))
        playback_pos = (self.img_width, 0)
        self.surface.blit(blank_surface, playback_pos)

    def print_help(self):
        """
        Prints help and usage.
        """
        print "Usage: "
        print "<Space bar> = add image to loop "
        print "<Backspace> = remove image from loop "
        print "r = reset loop"
        print "p = pause"
        print "i = print current loop frame number, number of frames in loop and global framerate"
        print "h = print this help message"
        print "s = saves all images as jpeg"
        print "a = enable the intervalometer auto grab"
        print "k = increase the intervalometer interval"
        print "j = decrease the intervalometer interval"
        print "<Esc> or q = quit program\n"

    def print_stats(self):
        """
        Print statistics
        """
        print "Frame idx: " + str(self.image_idx)
        print "Num images: " + str(len(self.image_list))
        print "FPS: %s" % (self.fps)
    
    def increment_fps(self, dir=1):
        """
        Increase or decreases the FPS
        :param dir: by how much increment it.
        """
        if self.renderer is not None:
            # accesses the Renderer instance that owns this.
            will_be = self.renderer.desired_fps + dir
            if will_be > 0 and will_be <= 60:
                self.renderer.desired_fps = will_be
                print "FPS:", will_be
    
    def process_events(self, events):
        """
        Processes pygame events.
        :param events: got them using pygame.event.get()
        """
        # events = pygame.event.get()
        for e in events:
            if e.type == QUIT:
                self.running = False
            elif e.type == KEYDOWN: 
                if e.key == K_k:
                    self.increment_auto_rate(1)
                if e.key == K_j:
                    self.increment_auto_rate(-1)
                if e.key == K_UP:
                    self.increment_fps(1)
                if e.key == K_DOWN:
                    self.increment_fps(-1)
                if e.key == K_SPACE:
                    self.grab_image()
                elif e.key == K_r:
                    self.reset_loop()
                elif e.key == K_p:
                    self.pause()
                elif e.key == K_i: 
                    self.print_stats()
                elif e.key == K_h:
                    self.print_help()
                elif e.key == K_s:
                    self.save_images()
                if e.key == K_a:
                    self.toggle_auto()
                elif e.key == K_BACKSPACE:
                    self.pop_one_frame()
                elif e.key == K_ESCAPE or e.key == K_q:
                    self.running = False
    
    def draw(self):
        """
        Renders one frame.
        Called from the event loop. (twisted)
        """
        if not self.paused:
            self.get_and_flip()
            self.clock.tick()
            self.fps = self.clock.get_fps()
    
    def cleanup(self):
        """
        Called before quitting the application.
        """
        pass


if __name__ == "__main__":
    """
    Starts the application, reading the command-line arguments.
    """
    from optparse import OptionParser

    parser = OptionParser(usage="%prog [version]", version=str(__version__))
    parser.add_option("-d", "--device", dest="device", default=0, type="int", \
        help="Specifies v4l2 device to grab image from.")
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true", \
        help="Sets the output to verbose.")
    parser.add_option("-f", "--fps", type="int", default=12, \
        help="Sets the desired fps.")
    parser.add_option("-t", "--intervalometer", type="int", default=3, \
        help="Sets intervalometer interval in seconds.")
    parser.add_option("-i", "--enable-intervalometer", \
        dest="enable_intervalometer", action="store_true", \
        help="Enables the intervalometer at startup.")
    (options, args) = parser.parse_args()
    
    print "ToonLoop - Version " + str(__version__)
    print "Copyright 2008 Alexandre Quessy & Tristan Matthews"
    print "Released under the GNU General Public License"
    print "Using video device %d" % options.device
    print "Press h for usage and instructions\n"
    #print "options:", options
    
    pygame.init()
    try:
        toonloop = ToonLoop(video_device=options.device, \
            auto_rate=options.intervalometer, \
            auto_enabled=options.enable_intervalometer == True, \
            verbose=options.verbose == True)
    except ToonLoopError, e:
        print str(e.message)
        print "\nnow exiting"
        sys.exit(1)
    pygame_timer = render.Renderer(toonloop, options.verbose)
    pygame_timer.desired_fps = options.fps
    try:
        reactor.run()
    except KeyboardInterrupt:
        pass
    print "\nExiting toonloop"
    sys.exit(0)

