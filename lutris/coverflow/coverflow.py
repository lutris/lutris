#!/usr/bin/python
# -*- coding:Utf-8 -*-
# Coverflow with Pyglet
# Homepage : http://groups.google.com/group/pyglet-users/browse_thread/thread/1bbc2bc03bc65a3e
# See also : http://macslow.net/?p=104

#Copyright (c)
#              2007, Mirco "MacSlow" Müller ( macslow@gmail.com )
#              2008, Naveen Michaud-Agrawal ( naveen.michaudagrawal@gmail.com )
#              2009, Mathieu Comandon ( strycore@gmail.com )
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.




import glob
import lutris.constants
try:
    import pyglet
    from pyglet.gl import *
    from pyglet import window
    #from pyglet import clock
    PYGLET_ENABLED = True
    import lutris.coverflow.covergl
    import lutris.coverflow.anim
except ImportError,msg:
    print "Pyglet Error: %s" % str(msg)
    PYGLET_ENABLED = False
except pyglet.window.NoSuchConfigException,msg:
    print "Pyglet Error: %s" % str(msg)
    PYGLET_ENABLED = False

Z_NEAR = 1.0
Z_FAR  = 50.0
FOVY   = 20.0

def setup():
    afLightDiffuse = [0.76, 0.75, 0.65, 1.0]
    
    # set some GL-states
    glClearColor(1.0, 0.5, 0.25, 1.0)
    glColor4f(0.25, 0.5, 1.0, 1.0)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_TEXTURE_RECTANGLE_ARB)
    glEnable(GL_BLEND)
    glBlendFunc (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glLightModeli(GL_LIGHT_MODEL_TWO_SIDE, 1)
    glDisable(GL_DEPTH_TEST)

    # lights and so on */
    glDisable(GL_LIGHTING)
    glDisable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (GLfloat * len(afLightDiffuse))(*afLightDiffuse))

    # setup "camera" */
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    gluLookAt(0.0, 0.0, Z_NEAR,
           0.0, 0.0, 0.0,
           0.0, 1.0, 0.0)
    glTranslatef(0.0, 0.0, -Z_NEAR)

def coverflow():
    if not PYGLET_ENABLED:
        return "NOPYGLET"
    width, height = 640, 480
    path = lutris.constants.cover_path
    filenames = glob.glob(path+"/*")[:200]
    filenames.sort()
    #curdir = os.path.abspath(os.curdir)
    covers = []
    tracks = []
    if not filenames:
        return "NOCOVERS"
    try:
        # Try and create a window with multisampling (antialiasing)
        #config = Config(sample_buffers=1, samples=4, 
        #                depth_size=16, double_buffer=True,)
        config = Config(depth_size=16, double_buffer=True,)
        w = window.Window(config=config,fullscreen=True )
        #w = window.Window(width=width, height=height, resizable=True, config=config )
    except window.NoSuchConfigException:
        print "No multisampling"
        # Fall back to no multisampling for old hardware
        w = window.Window(width=width, height=height, resizable=True)

    @w.event
    def on_resize(w, h):
        # Override the default on_resize handler to create a 3D projection
        glViewport (0, 0, w, h)
        lutris.coverflow.covergl.change_projection(True, w, h)
        glClear(GL_COLOR_BUFFER_BIT)

    setup()
    lutris.coverflow.covergl.setup_values()
    w.clicked = False


    for i, fname in enumerate(filenames):
        cover = lutris.coverflow.covergl.Cover(2.0, fname, angle=-70)
        x = i*0.75
        cover.fX.set(x)
        covers.append(cover)
        tracks.append(x)
    covers[0].focus()

    advance = lutris.coverflow.covergl.mk_advance(tracks, covers)
    @w.event
    def on_key_press(symbol, modifiers):
        if symbol == window.key.LEFT: advance(True)
        elif symbol == window.key.RIGHT: advance(False)


    @w.event
    def on_mouse_motion(x, y, dx, dy, tmp_dx=[0]):
        """
        This is if you want to advance in the covers by moving the mouse
        """
        tmp_dx[0] += dx
        if tmp_dx[0] > 20:
            tmp_dx[0] = 0
            #advance(False)
        elif tmp_dx[0] < -20:
            tmp_dx[0] = 0
            #advance(True)
            
    @w.event
    def on_mouse_scroll(x, y, scroll_x, scroll_y):
        if scroll_y > 0:
            advance(True)
        else:
            advance(False)
           
    
    @w.event
    def on_mouse_press(x, y, button, modifiers):
        if button == window.mouse.LEFT:
            #filename = filenames[advance.i]
            w.clicked = True
            w.close()
            pyglet.app.exit()

    @w.event
    def on_draw():
        w.clear()
        w.dispatch_events()
        lutris.coverflow.covergl.display(w.width, w.height, covers)
        w.flip()

    clock = pyglet.clock.get_default()
    clock.set_fps_limit(60)
    clock.schedule(lutris.coverflow.anim.add_time)
    pyglet.app.run()
    if w.clicked:
        return filenames[advance.i]
    else:
        return None
